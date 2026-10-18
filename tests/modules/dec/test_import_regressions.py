"""Track S: regressions found by the I1 review, each on synthetic data built from the S1 family.

Every test imports S1 and then a variant of it (``_variant``: the same document with a later
``as_of`` and an edit), the way the daily job applies one snapshot after another.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.config.settings import set_setting
from coflow.kernel.context import CommandContext, FakeClock, parse_instant
from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.store.api import Store, read_connection, unit_of_work
from coflow.modules.dec import api as dec
from coflow.modules.dec.domain.model import DecConfig
from coflow.modules.dec.importer import apply as apply_mod
from coflow.modules.dec.shadow import compare
from coflow.modules.dec.store import repo
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import (
    fingerprint,
    import_doc,
    import_family,
    one,
    rows,
)

Doc = dict[str, Any]


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


def _at(text: str) -> datetime:
    return parse_instant(text)


def _variant(base: Callable[[], Doc], as_of: str, *edits: Callable[[Doc], None]) -> Doc:
    """``base`` exported at ``as_of`` (an instant) with ``edits`` applied, re-sealed."""

    def edit(doc: Doc) -> None:
        doc["as_of"] = as_of
        doc["exported_at"] = as_of.replace(":00Z", ":09Z")
        doc["as_of_date"] = as_of[:10]
        for e in edits:
            e(doc)

    return sb.planted(base, edit)


def _decision(doc: Doc, v1_id: int) -> Doc:
    return next(d for d in doc["decisions"] if d["v1_id"] == v1_id)


def _assumption(doc: Doc, decision: int, v1_id: int) -> Doc:
    return next(a for a in _decision(doc, decision)["assumptions"] if a["v1_id"] == v1_id)


def _run(env: Any, doc: Doc, path: Path, clock: FakeClock, ctx: CommandContext) -> Any:
    at = _at(doc["as_of"]) + timedelta(hours=4)
    return import_doc(env, doc, path, clock=clock, ctx=ctx, at=at).value


def _s1(env: Any, clock: FakeClock, ctx: CommandContext, tmp_path: Path) -> Any:
    return import_family(env, "s1.json", clock=clock, ctx=ctx, directory=tmp_path / "inbox").value


# ==================================================================================================
# The card verifies editions against every row, not only the rows visible at T


def test_a_reworded_ground_fact_is_no_tamper_alarm_on_the_card(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _s1(env, clock, owner_ctx, tmp_path)

    def reword(doc: Doc) -> None:
        _decision(doc, 903)["facts"][0]["fact"] = "Spring sessions averaged five or six people"

    _run(
        env, _variant(sb.s1, "2026-11-16T05:00:00Z", reword), tmp_path / "v.json", clock, owner_ctx
    )

    voided = rows(
        "SELECT f.voided_at FROM dec_facts f JOIN dec_decisions d ON d.id = f.decision_id "
        "WHERE d.public_id = 'D-0903' ORDER BY f.code_n"
    )
    assert [r["voided_at"] is not None for r in voided] == [True, False]
    integrity = dec.integrity(env, "D-0903").value[0]
    assert [(line.edition, line.status) for line in integrity.lines] == [(1, "ok"), (2, "ok")]

    card = dec.decision_context(env, "D-0903").value
    assert card.integrity_line is None
    full = dec.decision_context(env, "D-0903", detail="full").value
    assert [(e.edition, e.status) for e in full.editions] == [(1, "ok"), (2, "ok")]
    before = dec.decision_context(
        env, "D-0903", detail="full", as_of=_at("2026-11-15T12:00:00Z")
    ).value
    assert before.integrity_line is None
    assert [(e.edition, e.status) for e in before.editions] == [(1, "ok")]


# ==================================================================================================
# Snapshots are applied in order


def test_an_older_snapshot_after_a_newer_one_is_refused_and_writes_nothing(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    inbox = tmp_path / "inbox"
    import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=inbox)
    import_family(env, "s1_double_prime.json", clock=clock, ctx=owner_ctx, directory=inbox)
    before = fingerprint()
    with pytest.raises(Refused) as excinfo:
        import_family(env, "s1_prime.json", clock=clock, ctx=owner_ctx, directory=inbox)
    assert excinfo.value.code == RefusalCode.IMPORT_SOURCE_CONFLICT
    assert "older than run 2" in str(excinfo.value)
    assert fingerprint() == before
    assert one("SELECT review_due FROM dec_decisions WHERE public_id = 'D-0907'") == "2026-12-31"


def test_the_same_instant_exported_earlier_is_refused_and_later_is_accepted(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _s1(env, clock, owner_ctx, tmp_path)  # exported 05:00:12 for as_of 05:00:00
    earlier = sb.planted(sb.s1, lambda d: d.update(exported_at="2026-11-15T05:00:05Z"))
    with pytest.raises(Refused) as excinfo:
        _run(env, earlier, tmp_path / "earlier.json", clock, owner_ctx)
    assert excinfo.value.code == RefusalCode.IMPORT_SOURCE_CONFLICT
    later = sb.planted(sb.s1, lambda d: d.update(exported_at="2026-11-15T06:00:00Z"))
    assert _run(env, later, tmp_path / "later.json", clock, owner_ctx).status == "applied"


# ==================================================================================================
# Assumption head changes the source versions itself are stored once


def test_a_v1_versioned_next_check_is_one_version_row(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _s1(env, clock, owner_ctx, tmp_path)

    def checked(doc: Doc) -> None:
        a = _assumption(doc, 909, 9091)
        a["next_check_at"] = "2026-11-23"
        a["last_checked_at"] = "2026-11-16"
        _decision(doc, 909)["versions"].append(
            {
                "v1_id": 90911,
                "entity": "assumption",
                "entity_v1_id": 9091,
                "field": "next_check_at",
                "old_value": "2026-11-10",
                "new_value": "2026-11-23",
                "source": "app",
                "changed_by": "owner",
                "changed_at": "2026-11-16T10:00:00Z",
            }
        )

    _run(
        env, _variant(sb.s1, "2026-11-17T05:00:00Z", checked), tmp_path / "v.json", clock, owner_ctx
    )

    versions = rows(
        "SELECT v.old_value, v.new_value, v.origin_recorded_at FROM dec_versions v "
        "JOIN dec_assumptions a ON v.entity = 'assumption' AND v.entity_id = a.id "
        "JOIN dec_decisions d ON d.id = a.decision_id "
        "WHERE d.public_id = 'D-0909' AND v.field = 'next_check_at'"
    )
    assert versions == [
        {
            "old_value": "2026-11-10",
            "new_value": "2026-11-23",
            "origin_recorded_at": "2026-11-16T10:00:00.000Z",
        }
    ]
    between = dec.assumption_due(env, "D-0909_A-01", at=_at("2026-11-16T12:00:00Z")).value
    assert (between.due.due, between.due.source) == (date(2026, 11, 23), "explicit")
    before = dec.assumption_due(env, "D-0909_A-01", at=_at("2026-11-16T09:00:00Z")).value
    assert (before.due.due, before.due.source) == (date(2026, 11, 10), "explicit")


# ==================================================================================================
# Rows that first appear in a later run are known from that run


def _changed_basis(doc: Doc) -> None:
    d907 = _decision(doc, 907)
    _assumption(doc, 907, 9071)["threshold"] = "written confirmation by 10.11"
    d907["alternatives"].append(
        {"option": "Share a room with a second group", "why_rejected": None}
    )
    d907["links"] = [link for link in d907["links"] if link["ref"] != "K9001"]


def test_a_later_basis_change_does_not_rewrite_earlier_views(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    first = _s1(env, clock, owner_ctx, tmp_path)
    early = _at("2026-11-15T09:00:00Z")
    pool_before = dec.health(env, "D-0907", as_of=early).value.pool
    view_before = dec.as_of(env, "D-0907", early).value.decision
    assert pool_before == ("A-01",)

    _run(
        env,
        _variant(sb.s1, "2026-11-16T05:00:00Z", _changed_basis),
        tmp_path / "v.json",
        clock,
        owner_ctx,
    )

    # before the second snapshot: the record as it was, one assumption, two options, both links
    assert dec.health(env, "D-0907", as_of=early).value.pool == ("A-01",)
    view = dec.as_of(env, "D-0907", early).value.decision
    assert [o.text for o in view.options] == [o.text for o in view_before.options]
    assert sorted(link.target_ref for link in view.links) == sorted(
        link.target_ref for link in view_before.links
    )
    assert "V1_K9001" in {link.target_ref for link in view.links}

    # after it: the successor, the new option, the link removed
    late = _at("2026-11-16T09:00:00Z")
    assert dec.health(env, "D-0907", as_of=late).value.pool == ("A-02",)
    after = dec.as_of(env, "D-0907", late).value.decision
    assert "Share a room with a second group" in {o.text for o in after.options}
    assert "V1_K9001" not in {link.target_ref for link in after.links}
    removal = rows("SELECT * FROM dec_versions WHERE entity = 'link'")
    assert [(v["field"], v["origin_recorded_at"]) for v in removal] == [
        ("removed_tx", "2026-11-16T05:00:00.000Z")
    ]

    # the successor keeps v1's base for its due date: "10.11" is after the source row's creation
    due = dec.assumption_due(env, "D-0907_A-02", at=late).value.due
    assert (due.due, due.source) == (date(2026, 11, 10), "text")

    # the first run's report, recomputed now, still compares the same health and due dates
    with read_connection() as conn:
        run1 = repo.load_import_run(conn, first.run_id)
    assert run1 is not None
    stored = dec.shadow_report(env, run_id=first.run_id).value.items
    recomputed, _ = compare.compute_shadow(env, run1)

    def kept(items: Any) -> list[Any]:
        return [i for i in items if i.aspect in ("health", "due", "waiting_reasons", "order")]

    assert kept(recomputed) == kept(stored)


# ==================================================================================================
# review_due_initial is set once


def test_a_close_that_clears_the_review_date_seals_no_edition(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _s1(env, clock, owner_ctx, tmp_path)

    def close(doc: Doc) -> None:
        d909 = _decision(doc, 909)
        d909.update(status="closed", review_due=None, closed_at="2026-11-15T20:00:00Z")

    report = _run(
        env, _variant(sb.s1, "2026-11-16T05:00:00Z", close), tmp_path / "v.json", clock, owner_ctx
    )
    editions = rows(
        "SELECT e.n, e.reason FROM dec_editions e JOIN dec_decisions d ON d.id = e.decision_id "
        "WHERE d.public_id = 'D-0909' ORDER BY e.n"
    )
    assert editions == [{"n": 1, "reason": "import"}]
    assert one("SELECT review_due_initial FROM dec_decisions WHERE public_id = 'D-0909'") == (
        "2026-12-01"
    )
    assert not [f for f in report.findings if "D-0909" in f]
    shadow = dec.shadow_report(env, run_id=report.run_id).value
    assert [i for i in shadow.findings if i.decision_ref == "D-0909"] == []


def test_the_source_s_earliest_review_version_still_sets_the_initial_date(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    """A version row that names an earlier first review date corrects review_due_initial."""
    _s1(env, clock, owner_ctx, tmp_path)

    def earlier(doc: Doc) -> None:
        _decision(doc, 909)["versions"].append(
            {
                "v1_id": 90901,
                "entity": "decision",
                "entity_v1_id": 909,
                "field": "review_due",
                "old_value": "2026-11-20",
                "new_value": "2026-12-01",
                "source": "app",
                "changed_by": "owner",
                "changed_at": "2026-10-06T08:00:00Z",
            }
        )

    _run(
        env, _variant(sb.s1, "2026-11-16T05:00:00Z", earlier), tmp_path / "v.json", clock, owner_ctx
    )
    assert one("SELECT review_due_initial FROM dec_decisions WHERE public_id = 'D-0909'") == (
        "2026-11-20"
    )


# ==================================================================================================
# The latest run, whatever its status


def test_the_default_report_is_blocked_by_a_newer_partial_run(
    env: Any,
    clock: FakeClock,
    owner_ctx: CommandContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean = _s1(env, clock, owner_ctx, tmp_path)
    assert dec.shadow_report(env).value.run_id == clean.run_id

    with unit_of_work("cfg", owner_ctx):
        set_setting("dec.import_unit_max_rows", "30")
    real = apply_mod.apply_decision

    def faulty(src: Any, run: Any) -> Any:
        if src["v1_id"] == 908:
            raise RuntimeError("injected fault")
        return real(src, run)

    monkeypatch.setattr(apply_mod, "apply_decision", faulty)
    partial_doc = _variant(sb.s1, "2026-11-16T05:00:00Z")
    with pytest.raises(RuntimeError):
        _run(env, partial_doc, tmp_path / "partial.json", clock, owner_ctx)
    monkeypatch.undo()
    partial_id = int(one("SELECT max(id) FROM dec_import_runs"))
    assert one("SELECT status FROM dec_import_runs WHERE id = ?", (partial_id,)) == "partial"

    latest = dec.shadow_report(env)
    assert latest.value.run_id == partial_id
    assert latest.value.report_status == "blocked"
    assert any("partial" in note for note in latest.coverage)

    # a newer snapshot completes the state; the overtaken partial run is named, not resumable
    newer = _run(
        env, _variant(sb.s1, "2026-11-17T05:00:00Z"), tmp_path / "n.json", clock, owner_ctx
    )
    assert newer.status == "applied"
    report = dec.shadow_report(env)
    assert report.value.run_id == newer.run_id
    assert any(f"run {partial_id} stayed partial" in note for note in report.coverage)
    with pytest.raises(Refused) as excinfo:
        _run(env, partial_doc, tmp_path / "partial.json", clock, owner_ctx)
    assert excinfo.value.code == RefusalCode.IMPORT_SOURCE_CONFLICT


# ==================================================================================================
# An undated reconstructed state gives no date


def test_an_undated_imported_state_moves_neither_the_floor_nor_the_last_activity(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    def undated(doc: Doc) -> None:
        _assumption(doc, 907, 9071)["state"] = "UNVERIFIABLE"  # has a source, never checked
        a = _assumption(doc, 909, 9091)
        a.update(last_checked_at=None, next_check_at=None)

    _run(
        env, _variant(sb.s1, "2026-11-15T05:00:00Z", undated), tmp_path / "s.json", clock, owner_ctx
    )
    reconstructed = rows(
        "SELECT c.state, c.observed_precision FROM dec_checks c JOIN dec_decisions d "
        "ON d.id = c.decision_id WHERE d.public_id IN ('D-0907', 'D-0909') ORDER BY d.number"
    )
    assert reconstructed == [
        {"state": "UNVERIFIABLE", "observed_precision": "unknown"},
        {"state": "HOLDING", "observed_precision": "unknown"},
    ]
    at = _at("2026-11-15T05:00:00Z")
    due = dec.assumption_due(env, "D-0907_A-01", at=at).value.due
    assert (due.due, due.source) == (date(2026, 11, 10), "text")  # v1's date, not the review
    health = dec.health(env, "D-0909", as_of=at).value
    assert health.states == {"A-01": "HOLDING"}
    assert "NO_DATA_SINCE" in health.timeliness  # nothing dated since the decision (10-05)


# ==================================================================================================
# A deleted child that comes back is live again


def test_children_deleted_in_the_source_and_restored_are_live_again(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _s1(env, clock, owner_ctx, tmp_path)

    def delete(doc: Doc) -> None:
        _decision(doc, 907)["facts"] = []
        _decision(doc, 903)["reviews"] = []
        d908 = _decision(doc, 908)
        d908["assumptions"] = [a for a in d908["assumptions"] if a["v1_id"] != 9082]

    _run(
        env, _variant(sb.s1, "2026-11-16T05:00:00Z", delete), tmp_path / "d.json", clock, owner_ctx
    )
    back = _run(env, _variant(sb.s1, "2026-11-17T05:00:00Z"), tmp_path / "b.json", clock, owner_ctx)

    facts = rows(
        "SELECT f.text, f.voided_at, f.origin_recorded_at FROM dec_facts f JOIN dec_decisions d "
        "ON d.id = f.decision_id WHERE d.public_id = 'D-0907' ORDER BY f.code_n"
    )
    assert [(f["text"], f["voided_at"] is None) for f in facts] == [
        ("The landlord asked for one more week", False),
        ("The landlord asked for one more week", True),
    ]
    assert facts[1]["origin_recorded_at"] == "2026-11-17T05:00:00.000Z"
    reviews = rows(
        "SELECT r.voided_at FROM dec_reviews r JOIN dec_decisions d ON d.id = r.decision_id "
        "WHERE d.public_id = 'D-0903' ORDER BY r.code_n"
    )
    assert [r["voided_at"] is None for r in reviews] == [False, True]
    assumptions = rows(
        "SELECT a.code_n, a.status, a.origin_recorded_at FROM dec_assumptions a "
        "JOIN dec_decisions d ON d.id = a.decision_id WHERE d.public_id = 'D-0908' "
        "AND a.statement LIKE 'A buyer collects%' ORDER BY a.code_n"
    )
    assert [a["status"] for a in assumptions] == ["dropped", "active"]
    assert assumptions[1]["origin_recorded_at"] == "2026-11-17T05:00:00.000Z"
    assert any("is back in V1" in f for f in back.findings)
    states = dec.health(env, "D-0908", as_of=_at("2026-11-17T06:00:00Z")).value.states
    assert sorted(states.values()) == ["HOLDING", "VIOLATED"]

    shadow = dec.shadow_report(env, run_id=back.run_id).value
    counts = [i for i in shadow.items if i.aspect == "count"]
    assert counts
    assert all(i.classification == "same" for i in counts), counts


# ==================================================================================================
# The recorded input hash covers the effective configuration


def test_the_input_hash_changes_with_any_setting(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    report = _s1(env, clock, owner_ctx, tmp_path)
    with read_connection() as conn:
        run = repo.load_import_run(conn, report.run_id)
    assert run is not None
    base = DecConfig(timezone="Europe/Berlin")
    hashes = {
        compare.input_hash(run, cfg)
        for cfg in (
            base,
            dataclasses.replace(base, no_data_days=31),
            dataclasses.replace(base, unverifiable_share_limit=base.unverifiable_share_limit / 2),
            dataclasses.replace(base, drift_margin=base.drift_margin * 2),
            dataclasses.replace(base, timezone="UTC"),
        )
    }
    assert len(hashes) == 5
    assert compare.input_hash(run, base) == compare.input_hash(
        run, DecConfig(timezone="Europe/Berlin")
    )
