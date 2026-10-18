"""Assumption states (spec §3.4) and visibility, as-of views and head replay (spec §3.15)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

from coflow.kernel.context import EvalTime
from coflow.modules.dec.domain.health import health
from coflow.modules.dec.domain.states import (
    effective_state,
    last_activity_date,
    latest_assessment,
    live_links,
    unknown_event_rows,
    view_at,
    visible,
)
from tests.modules.dec.domain_builders import (
    CFG,
    CK,
    A,
    D,
    F,
    L,
    T,
    V,
    at_day,
    days,
    noon,
    sealed,
)

# --------------------------------------------------------------------------------------------------
# Effective states (§3.4)


def test_the_last_known_state_however_old() -> None:
    d = D(1001, review_due=days(20), assumptions=[A(1, checks=[CK(days(-200), "DRIFTING")])])
    assert effective_state(d, d.assumptions[0], T, CFG) == "DRIFTING"


def test_unverifiable_not_yet_due_and_unchecked_are_computed() -> None:
    d = D(
        1002,
        review_due=days(20),
        assumptions=[
            A(1, source="none"),
            A(2, threshold_text="by 20.11"),
            A(3, threshold_text="by 14.11"),
            A(4, threshold_text=None),
        ],
    )
    states = [effective_state(d, a, T, CFG) for a in d.assumptions]
    assert states == ["UNVERIFIABLE", "NOT_YET_DUE", "UNCHECKED", "NOT_YET_DUE"]
    no_review = D(1003, review_due=None, assumptions=[A(1, threshold_text=None)])
    assert effective_state(no_review, no_review.assumptions[0], T, CFG) == "NOT_YET_DUE"


def test_an_assessment_beats_the_source_kind_and_unknown_is_not_unverifiable() -> None:
    d = D(
        1004,
        review_due=days(20),
        assumptions=[
            A(1, source="none", checks=[CK(days(-1), "HOLDING")]),
            A(2, checks=[CK(days(-1), "UNKNOWN")]),
        ],
    )
    assert [effective_state(d, a, T, CFG) for a in d.assumptions] == ["HOLDING", "UNKNOWN"]


def test_checks_are_ordered_by_observed_time_not_by_record_time() -> None:
    late_record = CK(datetime(2026, 11, 14, 8, 0, tzinfo=UTC), "HOLDING", recorded=noon(days(0)))
    early_record = CK(
        datetime(2026, 11, 14, 11, 0, tzinfo=UTC), "VIOLATED", recorded=noon(days(-1))
    )
    d = D(1005, review_due=days(20), assumptions=[A(1, checks=[late_record, early_record])])
    last = latest_assessment(d.assumptions[0], T, CFG)
    assert last is not None
    assert last.state == "VIOLATED"
    same_day = [CK(days(-1), "HOLDING", recorded=noon(days(-1))), CK(days(-1), "DRIFTING")]
    d = D(1006, review_due=days(20), assumptions=[A(1, checks=same_day)])
    assert effective_state(d, d.assumptions[0], T, CFG) == "DRIFTING"  # then by K


def test_postponements_and_voided_checks_are_not_assessments() -> None:
    a = A(
        1,
        threshold_text=None,
        checks=[
            CK(days(-5), "VIOLATED"),
            CK(days(-3), "HOLDING", voided_at=noon(days(-2))),
            CK(days(-1), None, kind="postponement", next_check_set=days(5)),
        ],
    )
    d = D(1007, review_due=days(20), assumptions=[a])
    assert effective_state(d, d.assumptions[0], T, CFG) == "VIOLATED"
    # before the void, the HOLDING check stood
    assert effective_state(d, d.assumptions[0], at_day(days(-3)), CFG) == "HOLDING"


# --------------------------------------------------------------------------------------------------
# Visibility and the as-of view (§3.15)


def test_knowledge_and_instance_axes_for_a_late_import() -> None:
    """AT-S8's shape: created in v1 on day 2, imported on day 30."""
    d = D(
        907,
        mirror_of="V1_D907",
        created=noon(date(2026, 11, 30)),
        origin_recorded=noon(date(2026, 11, 2)),
        review_due=date(2026, 12, 1),
    )
    day5 = at_day(date(2026, 11, 5))
    assert view_at(d, day5, CFG, axis="knowledge") is not None
    assert view_at(d, day5, CFG, axis="instance") is None
    assert visible(d, day5, "knowledge", cfg=CFG)
    assert not visible(d, day5, "instance", cfg=CFG)


def test_rows_known_after_t_and_voided_by_t_are_dropped() -> None:
    d = D(
        1008,
        review_due=days(20),
        facts=[
            F(days(-10), "before"),
            F(days(-1), "after"),
            F(days(-8), "voided", voided_at=noon(days(-6))),
        ],
        assumptions=[A(1, checks=[CK(days(-9), "HOLDING"), CK(days(-2), "VIOLATED")])],
    )
    at = at_day(days(-5))
    v = view_at(d, at, CFG)
    assert v is not None
    assert [f.text for f in v.facts] == ["before"]
    assert [c.state for c in v.assumptions[0].checks] == ["HOLDING"]
    assert health(v, at, CFG).ground == "HOLDING"
    assert health(d, T, CFG).ground == "VIOLATED"
    at_7 = at_day(days(-7))
    assert [f.text for f in view_at(d, at_7, CFG).facts] == ["before", "voided"]  # type: ignore[union-attr]


def test_now_changes_nothing() -> None:
    d = D(1009, review_due=days(20), facts=[F(days(-3))], assumptions=[A(1)])
    assert view_at(d, T, CFG) == d


def test_the_head_is_replayed_through_its_versions() -> None:
    d = D(1010, review_due=date(2026, 12, 1), created=noon(date(2026, 11, 1)))
    versions = (
        V(
            "decision",
            d.id,
            "review_due",
            "2026-11-12",
            "2026-12-01",
            recorded=noon(date(2026, 11, 10)),
        ),
        V("decision", d.id, "status", "active", "closed", recorded=noon(date(2026, 11, 14))),
        V("decision", d.id, "manual_flag", None, "ZOMBIE", recorded=noon(date(2026, 11, 13))),
        V("decision", d.id, "no_such_column", "a", "b", recorded=noon(date(2026, 11, 14))),
    )
    closed = dataclasses.replace(d, status="closed", manual_flag="ZOMBIE", versions=versions)
    closed = dataclasses.replace(
        closed, stored={**closed.stored, "status": "closed", "manual_flag": "ZOMBIE"}
    )
    v8 = view_at(closed, at_day(date(2026, 11, 8)), CFG)
    assert v8 is not None
    assert (v8.review_due, v8.status, v8.manual_flag) == (date(2026, 11, 12), "active", None)
    assert v8.stored["review_due"] == "2026-11-12"
    v11 = view_at(closed, at_day(date(2026, 11, 11)), CFG)
    assert v11 is not None
    assert (v11.review_due, v11.status, v11.manual_flag) == (date(2026, 12, 1), "active", None)
    v14 = view_at(closed, at_day(date(2026, 11, 14)), CFG)  # 10:30, before the closing at noon
    assert v14 is not None
    assert (v14.status, v14.manual_flag) == ("active", "ZOMBIE")
    assert view_at(closed, T, CFG).status == "closed"  # type: ignore[union-attr]
    assert "no_such_column" not in v8.stored


def test_two_changes_of_one_field_are_undone_in_application_order() -> None:
    d = D(1011, review_due=date(2026, 12, 20), created=noon(date(2026, 11, 1)))
    versions = (
        V("decision", d.id, "review_due", "2026-11-10", "2026-11-30", recorded=noon(days(-6))),
        V("decision", d.id, "review_due", "2026-11-30", "2026-12-20", recorded=noon(days(-6))),
    )
    v = view_at(dataclasses.replace(d, versions=versions), at_day(days(-7)), CFG)
    assert v is not None
    assert v.review_due == date(2026, 11, 10)


def test_decided_at_is_replayed_with_its_precision_and_unknowns_as_a_list() -> None:
    d = D(1012, decided=date(2026, 11, 3), review_due=days(20), unknowns=("b",))
    versions = (
        V(
            "decision",
            d.id,
            "decided_at",
            "2026-10-30T08:00:00.000Z",
            "2026-11-03",
            recorded=noon(days(-2)),
        ),
        V("decision", d.id, "decided_precision", "instant", "day", recorded=noon(days(-2))),
        V("decision", d.id, "unknowns_json", '["a"]', '["b"]', recorded=noon(days(-2))),
    )
    v = view_at(dataclasses.replace(d, versions=versions), at_day(days(-3)), CFG)
    assert v is not None
    assert v.decided_at == datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
    assert v.decided_precision == "instant"
    assert v.unknowns == ("a",)


def test_assumption_heads_are_replayed() -> None:
    a = A(1, next_check_at=date(2026, 11, 25), threshold_text=None)
    d = D(1013, review_due=days(30), assumptions=[a])
    aid = d.assumptions[0].id
    versions = (
        V("assumption", aid, "next_check_at", "2026-11-12", "2026-11-25", recorded=noon(days(-1))),
    )
    v = view_at(dataclasses.replace(d, versions=versions), at_day(days(-2)), CFG)
    assert v is not None
    assert v.assumptions[0].next_check_at == date(2026, 11, 12)
    assert effective_state(v, v.assumptions[0], at_day(days(-2)), CFG) == "UNCHECKED"


def test_a_removed_link_is_live_before_its_removal() -> None:
    d = D(1014, review_due=days(20), links=[L("serves", "V1_G901", removed_tx=9)])
    link_id = d.links[0].id
    removal = V("link", link_id, "removed_tx", None, "9", recorded=noon(days(-1)))
    with_history = dataclasses.replace(d, versions=(removal,))
    before = view_at(with_history, at_day(days(-2)), CFG)
    assert before is not None
    assert [x.target_ref for x in live_links(before, ("serves",))] == ["V1_G901"]
    assert live_links(view_at(with_history, T, CFG), ("serves",)) == []  # type: ignore[arg-type]
    assert view_at(d, at_day(days(-2)), CFG).links == ()  # type: ignore[union-attr]


def test_the_current_edition_is_the_last_visible_one() -> None:
    d = sealed(D(1015, review_due=days(20)), sealed_at=noon(days(-10)))
    d = sealed(d, reason="revise", sealed_at=noon(days(-2)))
    assert d.current_edition == 2
    v = view_at(d, at_day(days(-5)), CFG)
    assert v is not None
    assert (v.current_edition, [e.n for e in v.editions]) == (1, [1])


def test_the_occurrence_axis_uses_event_times() -> None:
    d = D(
        1016,
        created=noon(days(-30)),
        review_due=days(20),
        facts=[
            F(days(-10), "happened early, told late", recorded=noon(days(-1))),
            F(None, "unknown time", recorded=noon(days(-20))),
            F(days(-2), "happened late"),
        ],
    )
    at = at_day(days(-5))
    occ = view_at(d, at, CFG, axis="occurrence")
    know = view_at(d, at, CFG, axis="knowledge")
    assert occ is not None
    assert know is not None
    assert [f.text for f in occ.facts] == ["happened early, told late"]
    assert [f.text for f in know.facts] == ["unknown time"]
    assert unknown_event_rows(d) == 1


def test_last_activity_falls_back_to_activation_or_the_decided_date() -> None:
    native = D(1017, created=noon(days(-50)), activated=noon(days(-40)), review_due=days(20))
    assert last_activity_date(native, T, CFG) == days(-40)
    mirror = D(917, mirror_of="V1_D917", decided=days(-33), created=noon(days(-1)))
    assert last_activity_date(mirror, T, CFG) == days(-33)
    busy = D(
        1018,
        review_due=days(20),
        facts=[F(None, recorded=noon(days(-4)))],
        assumptions=[A(1, checks=[CK(days(-6))])],
    )
    assert last_activity_date(busy, T, CFG) == days(-4)  # an unknown event time counts by K


def test_t_date_is_the_owners_date() -> None:
    late_evening = datetime(2026, 11, 14, 23, 30, tzinfo=UTC)  # already 15 November in Berlin
    d = D(1019, review_due=date(2026, 11, 15))
    T_ = EvalTime.at(late_evening, CFG.timezone)
    assert T_.date == date(2026, 11, 15)
    assert "DUE_TODAY" in health(d, T_, CFG).timeliness
