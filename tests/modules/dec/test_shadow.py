"""Track S: the shadow report (spec §6.6). AT-S5 on the synthetic family, each expected-difference
rule SR-1 to SR-10 with its own test, the injected mismatches, and the report's life cycle."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import NotFound
from coflow.kernel.ports.decision_directory import Reason
from coflow.kernel.store.api import Store, read_connection, unit_of_work, update_mutable
from coflow.modules.dec import api as dec
from coflow.modules.dec.domain.model import HealthResult
from coflow.modules.dec.shadow import compare, rules
from coflow.modules.dec.store import repo
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import import_doc, import_family, one, planted, rows

S1_AT = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


def _items(report: Any, aspect: str) -> list[Any]:
    return [i for i in report.items if i.aspect == aspect]


# ==================================================================================================
# AT-S5 on the family


def test_at_s5_the_family_classifies_every_rule_and_nothing_unexpected(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    inbox = tmp_path / "inbox"
    seen: set[str] = set()
    for name in ("s1.json", "s1_prime.json", "s1_double_prime.json"):
        run_id = import_family(env, name, clock=clock, ctx=owner_ctx, directory=inbox).value.run_id
        report = dec.shadow_report(env, run_id=run_id).value
        assert report.report_status == "written"
        assert report.unexpected == (), [str(i) for i in report.unexpected]
        dues = _items(report, "due")
        assert dues
        assert all(i.classification == "same" for i in dues)
        assert all(i.classification == "same" for i in _items(report, "count"))
        seen |= set(report.by_rule)
    assert seen == set(rules.RULE_IDS)


def test_at_s5_s1_alone(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    run_id = import_family(
        env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path
    ).value.run_id
    report = dec.shadow_report(env, run_id=run_id).value
    health = {i.decision_ref: (i.classification, i.rule_id) for i in _items(report, "health")}
    assert health == {
        "D-0903": ("same", None),
        "D-0904": ("expected", "SR-2"),
        "D-0905": ("same", None),
        "D-0906": ("expected", "SR-3"),
        "D-0907": ("same", None),
        "D-0908": ("expected", "SR-7"),
        "D-0909": ("expected", "SR-5"),
        "D-0910": ("expected", "SR-1"),
    }
    membership = {
        i.decision_ref: (i.classification, i.rule_id) for i in _items(report, "waiting_membership")
    }
    assert membership == {
        "D-0904": ("same", None),
        "D-0906": ("expected", "SR-8"),
        "D-0907": ("same", None),
        "D-0908": ("expected", "SR-7"),
        "D-0909": ("same", None),
    }
    extra = [
        (i.decision_ref, i.v2_value, i.rule_id)
        for i in _items(report, "waiting_reasons")
        if i.classification == "expected"
    ]
    assert extra == [
        ("D-0906", "incomplete 2026-10-20", "SR-8"),
        ("D-0907", "goal_changed 2026-11-05 V1_G901", "SR-9"),
        ("D-0908", "violated 2026-11-09 A-02", "SR-7"),
    ]
    order = {i.decision_ref: (i.v1_value, i.v2_value) for i in _items(report, "order")}
    assert order == {"D-0904": ("1", "1"), "D-0909": ("2", "2")}
    assert all(i.classification == "same" for i in _items(report, "order"))
    assert report.totals["unexpected"] == 0
    assert report.runs_since_last_unexpected == 1


def test_an_injected_due_date_mismatch_is_unexpected(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    doc = planted(
        sb.s1, lambda d: d["v1_computed"]["assumption_due"]["9091"].update(due="2026-11-11")
    )
    run_id = import_doc(env, doc, tmp_path / "due.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    report = dec.shadow_report(env, run_id=run_id.value.run_id).value
    assert [(i.aspect, i.subject_ref, i.v1_value, i.v2_value) for i in report.unexpected] == [
        ("due", "D-0909_A-01", "2026-11-11 explicit", "2026-11-10 explicit")
    ]
    assert report.runs_since_last_unexpected == 0


def test_an_injected_order_swap_is_unexpected(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    def swap(d: dict[str, Any]) -> None:
        waiting = d["v1_computed"]["waiting"]
        d["v1_computed"]["waiting"] = [waiting[2], waiting[0], waiting[1]]  # 909 before 904

    doc = planted(sb.s1, swap)
    result = import_doc(env, doc, tmp_path / "order.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    report = dec.shadow_report(env, run_id=result.value.run_id).value
    swapped = [(i.decision_ref, i.aspect, i.v1_value, i.v2_value) for i in report.unexpected]
    assert swapped == [("D-0904", "order", "2", "1"), ("D-0909", "order", "1", "2")]


def test_a_v1_reason_v2_does_not_give_and_a_count_mismatch_are_unexpected(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    def edit(d: dict[str, Any]) -> None:
        d["v1_computed"]["waiting"].append(
            {"v1_id": 905, "reasons": [{"kind": "review_today", "due": "2026-11-15"}]}
        )
        d["v1_computed"]["health"]["905"]["label"] = "ON_TRACK"

    doc = planted(sb.s1, edit)
    doc["counts"]["facts"] = 3
    doc["content_hash"] = sb.content_hash(doc)
    result = import_doc(env, doc, tmp_path / "x.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    report = dec.shadow_report(env, run_id=result.value.run_id).value
    got = {(i.decision_ref, i.aspect, i.v1_value, i.v2_value) for i in report.unexpected}
    assert got == {
        ("*", "count", "3", "2"),
        ("D-0905", "health", "ON_TRACK", "INSUFFICIENT_DATA"),
        ("D-0905", "waiting_membership", "listed", "absent"),
        ("D-0905", "waiting_reasons", "review_today 2026-11-15", None),
    }


# ==================================================================================================
# The report's life cycle


def test_a_stored_report_and_a_recomputed_one_agree(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    run_id = import_family(
        env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path
    ).value.run_id
    stored = dec.shadow_report(env, run_id=run_id).value
    with unit_of_work("dec", owner_ctx):
        update_mutable("dec_import_runs", {"id": run_id}, report_status="pending")
    recomputed = dec.shadow_report(env, run_id=run_id)
    assert recomputed.value.report_status == "pending"
    assert any("not stored" in note for note in recomputed.coverage)
    assert sorted(map(str, recomputed.value.items)) == sorted(map(str, stored.items))
    assert recomputed.instance_role == "dev"


def test_runs_since_the_last_unexpected_line(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    bad = planted(sb.s1, lambda d: d["v1_computed"]["assumption_due"]["9091"].update(due=None))
    import_doc(env, bad, tmp_path / "bad.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    for n in (1, 2):
        clean = planted(sb.s1, lambda d, n=n: d.update(exported_at=f"2026-11-15T0{5 + n}:00:00Z"))
        result = import_doc(
            env, clean, tmp_path / f"clean{n}.json", clock=clock, ctx=owner_ctx, at=S1_AT
        )
        assert dec.shadow_report(env).value.run_id == result.value.run_id
        assert dec.shadow_report(env).value.runs_since_last_unexpected == n


def test_the_latest_applied_run_is_the_default_and_none_is_not_found(env: Any) -> None:
    with pytest.raises(NotFound):
        dec.shadow_report(env)


def test_v2_output_is_recorded_with_the_report(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    run_id = import_family(
        env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path
    ).value.run_id
    output = json.loads(one("SELECT v2_output_json FROM dec_import_runs WHERE id = ?", (run_id,)))
    assert output["algorithm_version"] == compare.ALGORITHM_VERSION
    assert len(output["input_hash"]) == 64
    assert output["as_of_date"] == "2026-11-15"
    assert output["health"]["D-0904"]["label"] == "STALE"
    assert output["due"]["D-0909_A-01"] == ["2026-11-10", "explicit"]
    assert [w["ref"] for w in output["waiting"]] == [
        "D-0906",
        "D-0904",
        "D-0907",
        "D-0908",
        "D-0909",
    ]
    stored = rows("SELECT count(*) AS n FROM dec_shadow_items WHERE run_id = ?", (run_id,))
    assert stored[0]["n"] == len(dec.shadow_report(env, run_id=run_id).value.items)
    with read_connection() as conn:
        run = repo.load_import_run(conn, run_id)
    assert run is not None
    assert run.report_status == "written"


# ==================================================================================================
# Each rule, on v2's own values


def _health(
    label: str,
    ground: str | None,
    timeliness: set[str],
    *,
    states: dict[str, str] | None = None,
    pool: tuple[str, ...] = (),
    share: str | None = "0",
    badge: str | None = None,
) -> HealthResult:
    return HealthResult(
        label=label,  # type: ignore[arg-type]
        ground=ground,  # type: ignore[arg-type]
        timeliness=frozenset(timeliness),  # type: ignore[arg-type]
        reasons=(),
        share=None if share is None else Decimal(share),
        bet=False,
        states=states or {},  # type: ignore[arg-type]
        pool=pool,
        badge=badge,
    )


def _facts(
    h: HealthResult,
    *,
    review_due: date | None = date(2026, 12, 1),
    manual_flag: str | None = None,
    mirror: bool = True,
) -> rules.RuleFacts:
    return rules.RuleFacts(
        health=h,
        status="active",
        is_mirror=mirror,
        review_due=review_due,
        manual_flag=manual_flag,
        share_limit=Decimal("0.5"),
    )


def test_sr1_awaiting_checks_replaces_a_signal_less_watch() -> None:
    h = _health(
        "AWAITING_CHECKS", "AWAITING", {"ON_SCHEDULE"}, states={"A-01": "UNKNOWN"}, pool=("A-01",)
    )
    assert rules.classify_health("WATCH", _facts(h)) == ("expected", "SR-1")
    overdue = _health("AWAITING_CHECKS", "AWAITING", {"CHECK_OVERDUE"})
    assert rules.classify_health("WATCH", _facts(overdue)) == ("unexpected", None)


def test_sr2_an_overdue_review_is_not_masked_by_missing_data() -> None:
    fog = _health(
        "STALE",
        "INSUFFICIENT",
        {"REVIEW_OVERDUE"},
        states={"A-01": "UNVERIFIABLE", "A-02": "UNVERIFIABLE"},
        pool=("A-01", "A-02"),
        share="1",
    )
    assert rules.classify_health("INSUFFICIENT_DATA", _facts(fog)) == ("expected", "SR-2")
    empty = _health("STALE", "NO_ASSUMPTIONS", {"REVIEW_OVERDUE"}, share=None)
    assert rules.classify_health("INSUFFICIENT_DATA", _facts(empty)) == ("expected", "SR-2")
    partly = _health(
        "STALE",
        "INSUFFICIENT",
        {"REVIEW_OVERDUE"},
        states={"A-01": "UNVERIFIABLE", "A-02": "HOLDING"},
        pool=("A-01", "A-02"),
    )
    assert rules.classify_health("INSUFFICIENT_DATA", _facts(partly)) == ("unexpected", None)


def test_sr3_a_mostly_uncheckable_ground_is_insufficient_data() -> None:
    h = _health("INSUFFICIENT_DATA", "INSUFFICIENT", {"NO_REVIEW_DATE"}, share="0.6667")
    assert rules.classify_health("WATCH", _facts(h)) == ("expected", "SR-3")
    all_fog = _health("INSUFFICIENT_DATA", "INSUFFICIENT", {"ON_SCHEDULE"}, share="1")
    assert rules.classify_health("WATCH", _facts(all_fog)) == ("unexpected", None)


def test_sr4_holding_with_some_unverifiable_is_on_track() -> None:
    h = _health(
        "ON_TRACK",
        "HOLDING",
        {"ON_SCHEDULE"},
        states={"A-01": "HOLDING", "A-02": "UNVERIFIABLE"},
        pool=("A-01", "A-02"),
        share="0.5",
    )
    assert rules.classify_health("WATCH", _facts(h)) == ("expected", "SR-4")
    today = _health(
        "ON_TRACK",
        "HOLDING",
        {"DUE_TODAY"},
        states={"A-01": "HOLDING", "A-02": "UNVERIFIABLE"},
        pool=("A-01", "A-02"),
        share="0.5",
    )
    assert rules.classify_health("WATCH", _facts(today)) == ("expected", "SR-4")
    clean = _health(
        "ON_TRACK", "HOLDING", {"ON_SCHEDULE"}, states={"A-01": "HOLDING"}, pool=("A-01",)
    )
    assert rules.classify_health("WATCH", _facts(clean)) == ("unexpected", None)


def test_sr5_an_overdue_check_is_not_on_track() -> None:
    h = _health("WATCH", "HOLDING", {"CHECK_OVERDUE"})
    assert rules.classify_health("ON_TRACK", _facts(h)) == ("expected", "SR-5")


def test_sr6_stale_holding_is_not_on_track() -> None:
    h = _health("WATCH", "HOLDING", {"NO_DATA_SINCE"})
    assert rules.classify_health("ON_TRACK", _facts(h)) == ("expected", "SR-6")
    both = _health("WATCH", "HOLDING", {"NO_DATA_SINCE", "CHECK_OVERDUE"})
    assert rules.classify_health("ON_TRACK", _facts(both)) == ("expected", "SR-5")  # first rule


def test_sr7_a_non_critical_violation_counts() -> None:
    h = _health(
        "WATCH",
        "DRIFTING",
        {"ON_SCHEDULE"},
        states={"A-01": "HOLDING", "A-02": "VIOLATED"},
        pool=("A-01",),
    )
    assert rules.classify_health("ON_TRACK", _facts(h)) == ("expected", "SR-7")
    reason = Reason(kind="violated", due=date(2026, 11, 9), code="A-02", critical=False)
    assert rules.classify_extra_reason(reason, _facts(h)) == "SR-7"
    drifting = _health(
        "WATCH", "DRIFTING", {"ON_SCHEDULE"}, states={"A-01": "DRIFTING"}, pool=("A-01",)
    )
    assert rules.classify_health("ON_TRACK", _facts(drifting)) == ("unexpected", None)


def test_sr8_an_active_mirror_without_a_review_date_waits() -> None:
    h = _health("WATCH", "HOLDING", {"NO_REVIEW_DATE"})
    assert rules.classify_health("ON_TRACK", _facts(h, review_due=None)) == ("expected", "SR-8")
    reason = Reason(kind="incomplete", due=date(2026, 10, 20))
    assert rules.classify_extra_reason(reason, _facts(h, review_due=None)) == "SR-8"
    assert rules.classify_extra_reason(reason, _facts(h, review_due=None, mirror=False)) is None


def test_sr9_a_goal_that_ended_asks_once() -> None:
    h = _health("STALE", "AWAITING", {"REVIEW_OVERDUE"})
    reason = Reason(kind="goal_changed", due=date(2026, 11, 5), code="V1_G901", status="dropped")
    assert rules.classify_extra_reason(reason, _facts(h)) == "SR-9"


def test_sr10_violations_wait_under_a_manual_flag() -> None:
    h = _health("ZOMBIE", "VIOLATED", {"ON_SCHEDULE"}, states={"A-01": "VIOLATED"}, pool=("A-01",))
    critical = Reason(kind="violated", due=date(2026, 12, 1), code="A-01", critical=True)
    assert rules.classify_extra_reason(critical, _facts(h, manual_flag="ZOMBIE")) == "SR-10"
    assert rules.classify_extra_reason(critical, _facts(h)) is None
    assert rules.classify_health("ZOMBIE", _facts(h, manual_flag="ZOMBIE")) == ("same", None)


def test_v1_labels_map_to_v2() -> None:
    assert rules.map_v1_label("CLOSED_SUCCESS") == ("CLOSED", "success")
    assert rules.map_v1_label("WATCH") == ("WATCH", None)
    closed = _health("CLOSED", None, set(), share=None, badge="success · reported")
    assert rules.classify_health("CLOSED_SUCCESS", _facts(closed)) == ("same", None)
    assert rules.classify_health("CLOSED_FAILURE", _facts(closed)) == ("unexpected", None)
    assert rules.classify_health("CANCELLED", _facts(_health("CANCELLED", None, set()))) == (
        "same",
        None,
    )
    review = Reason(kind="review_overdue", due=date(2026, 11, 1))
    assert rules.classify_extra_reason(review, _facts(closed)) is None
