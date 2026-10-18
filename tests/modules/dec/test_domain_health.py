"""Health on two axes, the composite label and its reasons (spec §3.7; AT-D3, the named vectors).

The vectors H1-H18 are the spec's table, hand-checked; review dates are relative to today
(2026-11-15). "Fresh" means the last activity lies within ``dec.no_data_days`` (30). The agreement
with the independent oracle over the enumerated space is track S's half of AT-D3.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import pytest

from coflow.modules.dec.domain.health import (
    health,
    is_bet,
    label_reason,
    missing_for_activation,
    pool,
    share_line,
    share_text,
    to_state,
    unverifiable_share,
)
from coflow.modules.dec.domain.model import AssumptionView, DecisionView
from coflow.modules.dec.domain.waiting import decision_reasons, urgency, waiting
from tests.fakes import FakeGoalDirectory
from tests.modules.dec.domain_builders import (
    CFG,
    CK,
    OC,
    OP,
    A,
    D,
    R,
    T,
    days,
    noon,
)

# --------------------------------------------------------------------------------------------------
# Assumptions in a given effective state (at T, today 2026-11-15)


def holding(n: int, *, critical: bool = True, **kw: object) -> AssumptionView:
    return A(n, critical=critical, checks=[CK(days(-2), "HOLDING")], **kw)  # type: ignore[arg-type]


def state(n: int, s: str, *, critical: bool = True) -> AssumptionView:
    return A(n, critical=critical, checks=[CK(days(-2), s)])


def unverifiable(n: int, *, critical: bool = True) -> AssumptionView:
    return A(n, critical=critical, source="none", threshold_text=None)


def not_yet_due(n: int, *, critical: bool = True) -> AssumptionView:
    return A(n, critical=critical, threshold_text="no date in it")


def unchecked_since_yesterday(n: int) -> AssumptionView:
    return A(n, threshold_text="confirmed by 14.11")


@dataclass(frozen=True)
class Vector:
    build: Callable[[], DecisionView]
    label: str
    ground: str | None
    share: Decimal | None
    timeliness: frozenset[str] | None = None


def _d(**kw: object) -> DecisionView:
    return D(1001, **kw)  # type: ignore[arg-type]


VECTORS: dict[str, Vector] = {
    "H1": Vector(
        lambda: _d(depth="full", review_due=days(10)),
        "INSUFFICIENT_DATA",
        "NO_ASSUMPTIONS",
        None,
    ),
    "H2": Vector(
        lambda: _d(depth="light", review_due=days(10)),
        "ON_TRACK",
        "NOT_MONITORED",
        None,
        frozenset({"ON_SCHEDULE"}),
    ),
    "H3": Vector(
        lambda: _d(review_due=days(-3), assumptions=[state(1, "VIOLATED"), holding(2)]),
        "REVIEW_REQUIRED",
        "VIOLATED",
        Decimal(0),
    ),
    "H4": Vector(
        lambda: _d(review_due=days(-3), assumptions=[unverifiable(1), unverifiable(2)]),
        "STALE",
        "INSUFFICIENT",
        Decimal(1),
    ),
    "H5": Vector(
        lambda: _d(review_due=days(5), assumptions=[unverifiable(1), unverifiable(2), holding(3)]),
        "INSUFFICIENT_DATA",
        "INSUFFICIENT",
        Decimal(2) / 3,
    ),
    "H6": Vector(
        lambda: _d(review_due=days(5), assumptions=[unverifiable(1), holding(2)]),
        "ON_TRACK",
        "HOLDING",
        Decimal("0.5"),
        frozenset({"ON_SCHEDULE"}),
    ),
    "H7": Vector(
        lambda: _d(review_due=days(20), assumptions=[not_yet_due(i) for i in (1, 2, 3)]),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        frozenset({"ON_SCHEDULE"}),
    ),
    "H8": Vector(
        lambda: _d(review_due=days(20), assumptions=[unchecked_since_yesterday(1), not_yet_due(2)]),
        "WATCH",
        "AWAITING",
        Decimal(0),
        frozenset({"CHECK_OVERDUE"}),
    ),
    "H9": Vector(
        lambda: _d(
            review_due=days(20),
            assumptions=[
                A(
                    1,
                    frequency="weekly",
                    next_check_at=days(-3),
                    checks=[CK(days(-10), "HOLDING")],
                )
            ],
        ),
        "WATCH",
        "HOLDING",
        Decimal(0),
        frozenset({"CHECK_OVERDUE"}),
    ),
    "H10": Vector(
        lambda: _d(
            created=noon(days(-60)),
            review_due=days(60),
            assumptions=[
                A(i, frequency="ad_hoc", checks=[CK(days(-45), "HOLDING")]) for i in (1, 2)
            ],
        ),
        "WATCH",
        "HOLDING",
        Decimal(0),
        frozenset({"NO_DATA_SINCE"}),
    ),
    "H11": Vector(
        lambda: _d(review_due=days(0), assumptions=[state(1, "DRIFTING"), holding(2)]),
        "WATCH",
        "DRIFTING",
        Decimal(0),
        frozenset({"DUE_TODAY"}),
    ),
    "H12": Vector(
        lambda: _d(review_due=days(20), manual_flag="ZOMBIE", assumptions=[holding(1), holding(2)]),
        "ZOMBIE",
        "HOLDING",
        Decimal(0),
        frozenset({"ON_SCHEDULE"}),
    ),
    "H13": Vector(
        lambda: _d(
            review_due=days(20), assumptions=[state(1, "VIOLATED", critical=False), holding(2)]
        ),
        "WATCH",
        "DRIFTING",
        Decimal(0),
        frozenset({"ON_SCHEDULE"}),
    ),
    "H14": Vector(
        lambda: _d(mirror_of="V1_D1001", review_due=None, assumptions=[holding(1)]),
        "WATCH",
        "HOLDING",
        Decimal(0),
        frozenset({"NO_REVIEW_DATE"}),
    ),
    "H15": Vector(
        lambda: _d(status="closed", outcomes=[OC("success", "reported")]),
        "CLOSED",
        None,
        None,
    ),
    "H16": Vector(
        lambda: _d(review_due=days(20), assumptions=[state(1, "UNKNOWN"), holding(2)]),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        frozenset({"ON_SCHEDULE"}),
    ),
    "H17": Vector(
        lambda: _d(
            review_due=days(20),
            assumptions=[state(1, "VIOLATED", critical=False), holding(2, critical=False)],
        ),
        "REVIEW_REQUIRED",
        "VIOLATED",
        Decimal(0),
    ),
    "H18": Vector(
        lambda: _d(
            created=noon(days(-40)),
            review_due=days(20),
            assumptions=[not_yet_due(1), not_yet_due(2)],
        ),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        frozenset({"NO_DATA_SINCE"}),
    ),
}


@pytest.mark.parametrize("name", list(VECTORS))
def test_named_vector(name: str) -> None:
    v = VECTORS[name]
    h = health(v.build(), T, CFG)
    assert h.label == v.label, h.words
    assert h.ground == v.ground, h.words
    assert h.share == v.share
    if v.timeliness is not None:
        assert h.timeliness == v.timeliness, h.words


def test_h5_share_shows_as_0_67() -> None:
    d = VECTORS["H5"].build()
    assert round(unverifiable_share(d, T, CFG) or 0, 2) == Decimal("0.67")
    assert share_text(d, T, CFG) == "0.6667"
    assert is_bet(d, T, CFG)
    assert health(d, T, CFG).bet


def test_h3_states_and_pool_are_reported() -> None:
    h = health(VECTORS["H3"].build(), T, CFG)
    assert dict(h.states) == {"A-01": "VIOLATED", "A-02": "HOLDING"}
    assert h.pool == ("A-01", "A-02")
    assert h.reasons[0].kind == "VIOLATED"
    assert h.reasons[0].text.startswith("A-01 violated: ")
    assert "REVIEW_OVERDUE" in h.timeliness  # every applicable reason is listed


def test_h4_overdue_review_is_never_masked_by_missing_data() -> None:
    h = health(VECTORS["H4"].build(), T, CFG)
    assert h.words == (
        "100% of the assumptions it rests on cannot be checked",
        "review was due 2026-11-12, 3 days ago",
    )


def test_h7_states_are_computed_not_stored() -> None:
    h = health(VECTORS["H7"].build(), T, CFG)
    assert set(h.states.values()) == {"NOT_YET_DUE"}
    assert h.words == ("3 assumptions without a result yet",)


def test_h8_unchecked_and_its_overdue_check_reason() -> None:
    h = health(VECTORS["H8"].build(), T, CFG)
    assert h.states["A-01"] == "UNCHECKED"
    assert h.states["A-02"] == "NOT_YET_DUE"
    overdue = [r for r in h.reasons if r.kind == "CHECK_OVERDUE"]
    assert [(r.code, r.day, r.source) for r in overdue] == [("A-01", days(-1), "text")]
    assert overdue[0].text == "A-01 check was due 2026-11-14 (from text)"


def test_h10_and_h18_name_the_silence() -> None:
    h10 = health(VECTORS["H10"].build(), T, CFG)
    assert "nothing recorded since 2026-10-01" in h10.words
    h18 = health(VECTORS["H18"].build(), T, CFG)
    assert "nothing recorded since 2026-10-06" in h18.words


def test_h11_lists_review_today_as_a_reason() -> None:
    h = health(VECTORS["H11"].build(), T, CFG)
    assert h.words == ("A-01 drifting", "review today")


def test_h12_keeps_the_computed_reasons_behind_the_owner_flag() -> None:
    h = health(VECTORS["H12"].build(), T, CFG)
    assert h.words == ("set by the owner", "every checkable assumption it rests on holds")
    assert label_reason(h) is not None
    assert label_reason(h).text == "set by the owner"  # type: ignore[union-attr]


def test_h13_non_critical_violation_watches_and_waits_at_rank_one() -> None:
    d = VECTORS["H13"].build()
    h = health(d, T, CFG)
    assert h.words == ("A-01 (non-critical) violated",)
    assert [a.code for a in pool(d)] == ["A-02"]
    reasons = decision_reasons(d, T, CFG, FakeGoalDirectory())
    assert [(r.kind, r.code, r.critical) for r in reasons] == [("violated", "A-01", False)]
    (item,) = waiting([d], T, CFG, goals=FakeGoalDirectory())
    assert urgency(item)[0] == 1


def test_h14_mirror_without_review_date_waits_as_incomplete() -> None:
    d = VECTORS["H14"].build()
    reasons = decision_reasons(d, T, CFG, FakeGoalDirectory())
    assert [r.kind for r in reasons] == ["incomplete"]


def test_h15_closed_shows_the_outcome_badge_grey() -> None:
    h = health(VECTORS["H15"].build(), T, CFG)
    assert (h.badge, h.badge_green) == ("success · reported", False)
    assert h.words == ("success · reported",)


def test_h17_without_criticals_the_pool_is_every_assumption() -> None:
    d = VECTORS["H17"].build()
    assert [a.code for a in pool(d)] == ["A-01", "A-02"]


# --------------------------------------------------------------------------------------------------
# The evaluation order and the rest of the label table


def test_the_owner_flag_beats_a_known_violation() -> None:
    d = _d(review_due=days(-3), manual_flag="OFF_TRACK", assumptions=[state(1, "VIOLATED")])
    h = health(d, T, CFG)
    assert h.label == "OFF_TRACK"
    assert h.ground == "VIOLATED"


def test_a_review_on_or_after_the_review_date_clears_the_overdue() -> None:
    d = _d(review_due=days(-3), reviews=[R(days(-3))], assumptions=[holding(1)])
    h = health(d, T, CFG)
    assert h.label == "ON_TRACK"
    assert h.timeliness == frozenset({"ON_SCHEDULE"})
    late = _d(review_due=days(-3), reviews=[R(days(-4))], assumptions=[holding(1)])
    assert health(late, T, CFG).label == "STALE"
    voided = _d(
        review_due=days(-3),
        reviews=[R(days(-2), voided_at=noon(days(-1)))],
        assumptions=[holding(1)],
    )
    assert health(voided, T, CFG).label == "STALE"


def test_stale_holding_is_watch_but_stale_awaiting_is_awaiting() -> None:
    assert VECTORS["H10"].label == "WATCH"
    assert VECTORS["H18"].label == "AWAITING_CHECKS"


def test_insufficient_share_needs_more_than_the_limit() -> None:
    d = _d(review_due=days(5), assumptions=[unverifiable(1), holding(2)])
    assert unverifiable_share(d, T, CFG) == Decimal("0.5")
    assert not is_bet(d, T, CFG)


def test_non_critical_unverifiable_assumptions_do_not_count_in_the_share() -> None:
    d = _d(review_due=days(5), assumptions=[unverifiable(1, critical=False), holding(2)])
    assert unverifiable_share(d, T, CFG) == Decimal(0)
    assert share_line(d, T, CFG) == "0 of 1 assumptions it rests on cannot be checked"


def test_share_line_is_always_there() -> None:
    assert share_line(VECTORS["H4"].build(), T, CFG) == (
        "2 of 2 assumptions it rests on cannot be checked"
    )
    assert share_line(VECTORS["H1"].build(), T, CFG) == (
        "no assumption recorded: nothing it rests on can be checked"
    )
    assert share_text(VECTORS["H1"].build(), T, CFG) is None


def test_dropped_and_superseded_assumptions_are_not_in_the_pool() -> None:
    d = _d(
        review_due=days(20),
        assumptions=[
            A(1, status="dropped", checks=[CK(days(-2), "VIOLATED")]),
            A(2, status="superseded", source="none"),
            holding(3),
        ],
    )
    h = health(d, T, CFG)
    assert (h.label, h.ground, h.pool) == ("ON_TRACK", "HOLDING", ("A-03",))


@pytest.mark.parametrize(
    ("status", "label", "words"),
    [
        ("cancelled", "CANCELLED", ()),
        ("withdrawn", "WITHDRAWN", ()),
        ("superseded", "SUPERSEDED", ("by D-1005",)),
    ],
)
def test_terminal_labels(status: str, label: str, words: tuple[str, ...]) -> None:
    reviews = [R(days(-1), "supersede", successor_ref="D-1005")] if status == "superseded" else []
    h = health(_d(status=status, reviews=reviews), T, CFG)
    assert (h.label, h.ground, h.words) == (label, None, words)


def test_closed_resolved_success_is_green_and_a_later_resolution_wins() -> None:
    first = OC("success", "reported")
    second = OC("success", "resolved", supersedes=first.id)
    h = health(_d(status="closed", outcomes=[first, second]), T, CFG)
    assert (h.badge, h.badge_green) == ("success · resolved", True)
    none = health(_d(status="closed"), T, CFG)
    assert (none.badge, none.words) == (None, ("no outcome recorded",))


def test_draft_names_what_is_missing() -> None:
    d = _d(
        status="draft",
        depth="full",
        question=None,
        unknowns=(),
        success_criterion=None,
        review_due=days(17),
    )
    assert missing_for_activation(d, T) == [
        "question",
        "options",
        "unknown",
        "success_criterion",
        "assumption",
    ]
    h = health(d, T, CFG)
    assert (h.label, h.words) == (
        "DRAFT",
        ("missing: question, options, unknown, success_criterion, assumption",),
    )


def test_missing_for_activation_details() -> None:
    light = _d(status="draft", depth="light", statement=None, review_due=days(0))
    assert missing_for_activation(light, T) == ["statement", "review_due"]
    chosen = _d(
        status="draft",
        depth="light",
        statement=None,
        review_due=days(3),
        options=[OP("Rent it", chosen=True)],
    )
    assert missing_for_activation(chosen, T) == []
    full = _d(
        status="draft",
        review_due=days(30),
        options=[OP("a", chosen=True), OP("b")],
        assumptions=[A(1, threshold_text=None), A(2, threshold_text="at least three")],
        kind="test",
    )
    assert missing_for_activation(full, T) == ["tests_link", "A-01.threshold"]
    assert health(_d(status="draft", depth="light", review_due=days(3)), T, CFG).words == (
        "nothing missing: ready to activate",
    )


def test_label_reason_names_what_decides_the_label() -> None:
    def first(name: str) -> str | None:
        r = label_reason(health(VECTORS[name].build(), T, CFG))
        return r.text if r else None

    assert first("H3") == "A-01 violated: The assumption holds"
    assert first("H4") == "review was due 2026-11-12, 3 days ago"
    assert first("H9") == "A-01 check was due 2026-11-12 (from explicit)"
    assert first("H14") == "no review date"
    assert first("H7") == "3 assumptions without a result yet"


def test_to_state_is_the_port_form() -> None:
    d = VECTORS["H11"].build()
    s = to_state(d.public_id, health(d, T, CFG), d.review_due)
    assert (s.ref, s.label, s.ground, s.review_due) == ("D-1001", "WATCH", "DRIFTING", days(0))
    assert s.reasons == ("A-01 drifting", "review today")
