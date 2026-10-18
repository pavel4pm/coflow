"""Track S: the snapshot importer (spec §6.2-§6.5). AT-S1, AT-S2, AT-S3, AT-S6, AT-S7, AT-S8 and the
importer's part of AT-K9; the refusal codes in the order of §6.5."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.config.settings import set_setting
from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import NotFound, Refused
from coflow.kernel.ids import aliases
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store import api as store_api
from coflow.kernel.store.api import Store, read_connection, unit_of_work
from coflow.modules.dec import api as dec
from coflow.modules.dec.importer import apply as apply_mod
from coflow.modules.dec.importer import snapshot as snapshot_mod
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import (
    fingerprint,
    import_doc,
    import_family,
    one,
    planted,
    rows,
)

S1_AT = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


@pytest.fixture
def inbox(tmp_path: Path) -> Path:
    return tmp_path / "inbox" / "snapshots"


def _import(env: Any, name: str, clock: FakeClock, ctx: CommandContext, inbox: Path) -> Any:
    return import_family(env, name, clock=clock, ctx=ctx, directory=inbox).value


# ==================================================================================================
# AT-S1


def test_at_s1_imports_the_eight_mirrors(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    report = _import(env, "s1.json", clock, owner_ctx, inbox)
    doc = sb.s1()

    assert report.status == "applied"
    assert report.report_status == "written"
    assert report.synthetic is True
    for entity, declared in doc["counts"].items():
        assert report.counts[entity].seen == declared, entity
        assert report.counts[entity].new == declared, entity

    heads = rows("SELECT * FROM dec_decisions ORDER BY number")
    assert [h["public_id"] for h in heads] == [f"D-{n:04d}" for n in range(903, 911)]
    for h in heads:
        assert h["depth"] == "full"
        assert h["depth_basis"] == "import"
        assert h["reconstructed"] == 1
        assert h["mirror_of"] == f"V1_D{h['number']}"
        assert h["mirror_scope"] == "full"
        assert h["current_edition"] == 1
    editions = rows(
        "SELECT d.public_id, e.n, e.reason, e.reconstructed FROM dec_editions e "
        "JOIN dec_decisions d ON d.id = e.decision_id ORDER BY d.number"
    )
    assert [(e["n"], e["reason"], e["reconstructed"]) for e in editions] == [(1, "import", 1)] * 8

    with read_connection() as conn:
        assert aliases.resolve(conn, "V1_D907") == "D-0907"
    card = dec.decision_context(env, "V1_D907").value
    assert card.decision.public_id == "D-0907"

    outcome = rows(
        "SELECT o.* FROM dec_outcomes o JOIN dec_decisions d ON d.id = o.decision_id "
        "WHERE d.public_id = 'D-0903'"
    )
    assert len(outcome) == 1
    assert outcome[0]["kind"] == "success"
    assert outcome[0]["basis"] == "reported"
    assert outcome[0]["resolved_by"] == "import"
    assert outcome[0]["reconstructed"] == 1
    learning = rows("SELECT * FROM dec_learnings")
    assert [(x["legacy_text"], x["edition"], x["reconstructed"]) for x in learning] == [
        ("Evening sessions filled up; small groups worked better", 0, 1)
    ]

    reset = rows(
        "SELECT c.* FROM dec_checks c JOIN dec_assumptions a ON a.id = c.assumption_id "
        "JOIN dec_decisions d ON d.id = a.decision_id WHERE d.public_id = 'D-0910'"
    )
    assert [(c["state"], c["note"], c["proposed_by"], c["reconstructed"]) for c in reset] == [
        ("UNKNOWN", "state reset in V1", "import", 1)
    ]


def test_at_s1_numbers_seals_and_events(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    result = import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=inbox)

    foreign = rows("SELECT prefix, n, issuer FROM sys_id_foreign ORDER BY n")
    assert [(f["prefix"], f["n"], f["issuer"]) for f in foreign] == [
        ("D", n, "V1") for n in range(903, 911)
    ]
    burned = rows("SELECT n, reason FROM sys_id_burned ORDER BY n")
    assert [(b["n"], b["reason"]) for b in burned] == [
        (901, "numbering_gap"),
        (902, "numbering_gap"),
    ]

    reports = dec.integrity(env, "all").value
    assert len(reports) == 8
    assert all(r.ok for r in reports), [r for r in reports if not r.ok]

    types = [r["type"] for r in rows("SELECT type FROM sys_events ORDER BY rowid")]
    assert types.count("coflow.dec.decision.imported") == 8
    assert types.count("coflow.dec.edition.sealed") == 8
    assert types.count("coflow.dec.import.completed") == 1
    assert len(result.event_ids) == 17
    log = rows(
        "SELECT actor, channel, owner_channel FROM sys_tx_log WHERE command = ?",
        ("import_snapshot",),
    )
    assert log == [{"actor": "import_v1", "channel": "import", "owner_channel": 0}]


def test_at_s1_field_mapping(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    d907 = rows("SELECT * FROM dec_decisions WHERE public_id = 'D-0907'")[0]
    assert d907["decided_at"] == "2026-11-02"
    assert d907["decided_precision"] == "day"
    assert d907["decided_basis"] == "import"
    assert d907["origin_recorded_at"] == "2026-11-02T19:02:11.000Z"
    assert d907["review_due"] == "2026-11-12"
    assert d907["review_due_initial"] == "2026-11-08"  # the first version's old value
    assert json.loads(d907["unknowns_json"]) == ["whether the small room has enough power"]
    assert d907["question"] is None
    assert d907["success_criterion"] is None
    assert json.loads(d907["legacy_json"])["investment"] == "about 6 hours of moving"
    assert d907["decider"] == "self"
    assert d907["decider_basis"] == "mapped"

    options = rows(
        "SELECT o.* FROM dec_options o JOIN dec_decisions d ON d.id = o.decision_id "
        "WHERE d.public_id = 'D-0907' ORDER BY code_n"
    )
    assert [
        (o["code_n"], o["chosen"], o["origin"], o["recorded_before_choice"]) for o in options
    ] == [
        (1, 1, "import", "unknown"),
        (2, 0, "import", "unknown"),
    ]
    assert options[0]["text"] == d907["statement"]
    assert all(o["added_in_edition"] == 1 for o in options)

    a = rows("SELECT * FROM dec_assumptions WHERE decision_id = ?", (d907["id"],))[0]
    assert a["code_n"] == 1
    assert a["threshold_text"] == "confirmation by 10.11"
    assert a["comparator"] is None
    assert a["data_source_kind"] == "manual"
    assert a["check_frequency"] == "ad_hoc"
    assert a["added_in_edition"] == 1
    unverifiable = rows(
        "SELECT data_source_kind FROM dec_assumptions a JOIN dec_decisions d "
        "ON d.id = a.decision_id WHERE d.public_id = 'D-0906' ORDER BY code_n"
    )
    assert [u["data_source_kind"] for u in unverifiable] == ["none", "none", "manual"]

    fact = rows("SELECT * FROM dec_facts WHERE decision_id = ?", (d907["id"],))[0]
    assert (fact["phase"], fact["evidence_kind"], fact["evidence_ref"]) == (
        "monitoring",
        "foreign",
        "V1_S90001",
    )
    assert (fact["occurred_at"], fact["occurred_precision"]) == ("2026-11-09", "day")
    bearing = rows("SELECT * FROM dec_fact_assumptions WHERE fact_id = ?", (fact["id"],))
    assert [b["assumption_id"] for b in bearing] == [a["id"]]

    links = rows(
        "SELECT role, target_ref, target_kind, resolution FROM dec_links "
        "WHERE decision_id = ? ORDER BY id",
        (d907["id"],),
    )
    assert links == [
        {
            "role": "serves",
            "target_ref": "V1_G901",
            "target_kind": "foreign_goal",
            "resolution": "foreign",
        },
        {
            "role": "foreign_attachment",
            "target_ref": "V1_K9001",
            "target_kind": "foreign_task",
            "resolution": "foreign",
        },
        {
            "role": "about",
            "target_ref": "V1_C-901",
            "target_kind": "company",
            "resolution": "foreign",
        },
    ]
    d903 = rows("SELECT origin_kind, origin_ref FROM dec_decisions WHERE public_id = 'D-0903'")[0]
    assert d903 == {"origin_kind": "session", "origin_ref": "V1_S90002"}
    d908 = rows(
        "SELECT third_party_sensitive, publishability FROM dec_decisions WHERE public_id = 'D-0908'"
    )[0]
    assert d908 == {"third_party_sensitive": 1, "publishability": "private"}

    goals = rows(
        "SELECT foreign_ref, status, status_changed_at, status_changed_precision "
        "FROM dec_foreign_context WHERE kind = 'goal' ORDER BY foreign_ref"
    )
    assert goals == [
        {
            "foreign_ref": "G901",
            "status": "dropped",
            "status_changed_at": "2026-11-05",
            "status_changed_precision": "day",
        },
        {
            "foreign_ref": "G902",
            "status": "active",
            "status_changed_at": None,
            "status_changed_precision": "unknown",
        },
    ]
    versions = rows("SELECT * FROM dec_versions")
    assert [
        (
            v["entity"],
            v["field"],
            v["old_value"],
            v["new_value"],
            v["cause_kind"],
            v["reconstructed"],
            v["origin_recorded_at"],
        )
        for v in versions
    ] == [
        (
            "decision",
            "review_due",
            "2026-11-08",
            "2026-11-12",
            "import",
            1,
            "2026-11-03T09:30:00.000Z",
        )
    ]


# ==================================================================================================
# AT-S2


def test_at_s2_the_same_file_twice_is_a_noop(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path, tmp_path: Path
) -> None:
    first = _import(env, "s1.json", clock, owner_ctx, inbox)
    before = fingerprint()
    again = import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path / "other")
    assert again.tx is None
    assert again.event_ids == ()
    assert again.value.noop is True
    assert again.value.status == "noop"
    assert again.value.run_id == first.run_id
    assert fingerprint() == before


def test_a_newer_file_with_the_same_content_changes_nothing_but_bookkeeping(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path, inbox: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    same = planted(sb.s1, lambda d: d.update(exported_at="2026-11-15T06:00:00Z"))
    before = {
        t: rows(f"SELECT * FROM {t} ORDER BY rowid")
        for t in (
            "dec_decisions",
            "dec_assumptions",
            "dec_checks",
            "dec_facts",
            "dec_versions",
            "dec_editions",
            "dec_links",
        )
    }
    report = import_doc(
        env, same, tmp_path / "s1-again.json", clock=clock, ctx=owner_ctx, at=S1_AT
    ).value
    assert report.status == "applied"
    assert report.counts["decisions"].unchanged == 8
    after = {t: rows(f"SELECT * FROM {t} ORDER BY rowid") for t in before}
    assert after == before
    events = [r["type"] for r in rows("SELECT type FROM sys_events ORDER BY rowid")]
    assert events.count("coflow.dec.decision.imported") == 8  # only the first run's
    assert events.count("coflow.dec.import.completed") == 2


# ==================================================================================================
# AT-S3


def test_at_s3_reimport_with_changes(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    checks_before = int(one("SELECT count(*) FROM dec_checks"))
    report = _import(env, "s1_prime.json", clock, owner_ctx, inbox)
    run = rows("SELECT * FROM dec_import_runs WHERE id = ?", (report.run_id,))[0]

    # a version row: the statement of D-0908 changed without a v1 version row
    new_versions = rows(
        "SELECT v.*, d.public_id FROM dec_versions v JOIN dec_decisions d "
        "ON d.id = v.entity_id WHERE v.tx = ?",
        (run["tx"],),
    )
    assert [(v["public_id"], v["entity"], v["field"], v["new_value"]) for v in new_versions] == [
        ("D-0908", "decision", "statement", "List all four cases at a lower fixed price")
    ]
    assert new_versions[0]["origin_recorded_at"] == "2026-11-16T05:00:00.000Z"

    # the removed decision is a tombstone, not a delete, and never waits
    assert report.absent == ("D-0905",)
    state = rows(
        "SELECT * FROM dec_mirror_state WHERE source_kind = 'decision' AND source_id = '905'"
    )[0]
    assert state["absent_since_run_id"] == report.run_id
    assert one("SELECT count(*) FROM dec_decisions WHERE public_id = 'D-0905'") == 1
    waiting = dec.waiting(env, today=date(2026, 11, 26)).value
    assert "D-0905" not in {i.ref for i in waiting}  # its review (11-25) would be overdue

    # E-02 (source_changed) for D-0908, a basis_drift finding; E-01 still verifies
    editions = rows(
        "SELECT n, reason FROM dec_editions e JOIN dec_decisions d "
        "ON d.id = e.decision_id WHERE d.public_id = 'D-0908' ORDER BY n"
    )
    assert editions == [{"n": 1, "reason": "import"}, {"n": 2, "reason": "source_changed"}]
    integrity = dec.integrity(env, "D-0908").value[0]
    assert [(line.edition, line.status) for line in integrity.lines] == [(1, "ok"), (2, "ok")]
    shadow = dec.shadow_report(env, run_id=report.run_id).value
    assert [(i.decision_ref, i.aspect, i.subject_ref) for i in shadow.findings] == [
        ("D-0908", "basis_drift", "D-0908_E-02")
    ]

    # exactly one reconstructed assessment: D-0909's check moved to 11-14
    added = rows("SELECT c.* FROM dec_checks c WHERE c.tx = ?", (run["tx"],))
    assert int(one("SELECT count(*) FROM dec_checks")) == checks_before + 1
    assert [
        (c["state"], c["observed_at"], c["observed_precision"], c["proposed_by"]) for c in added
    ] == [("HOLDING", "2026-11-14", "day", "import")]

    # the reworded fact: the old one voided, the new one corrects it
    facts = rows(
        "SELECT f.* FROM dec_facts f JOIN dec_decisions d ON d.id = f.decision_id "
        "WHERE d.public_id = 'D-0907' ORDER BY code_n"
    )
    assert [(f["text"], f["voided_reason"]) for f in facts] == [
        ("The landlord asked for one more week", "changed in V1"),
        ("The landlord asked for two more weeks", None),
    ]
    assert facts[1]["corrects_fact_id"] == facts[0]["id"]
    assert facts[0]["voided_at"] == "2026-11-16T05:00:00.000Z"


def test_a_tombstoned_decision_that_returns_is_live_again(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path, tmp_path: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    _import(env, "s1_prime.json", clock, owner_ctx, inbox)
    back = planted(
        sb.s1,
        lambda d: d.update(
            exported_at="2026-11-17T05:00:00Z",
            as_of="2026-11-17T05:00:00Z",
            as_of_date="2026-11-17",
        ),
    )
    import_doc(
        env,
        back,
        tmp_path / "back.json",
        clock=clock,
        ctx=owner_ctx,
        at=datetime(2026, 11, 17, 9, 0, tzinfo=UTC),
    )
    state = rows(
        "SELECT absent_since_run_id FROM dec_mirror_state "
        "WHERE source_kind = 'decision' AND source_id = '905'"
    )[0]
    assert state["absent_since_run_id"] is None


# ==================================================================================================
# AT-S6


def _fault_on(monkeypatch: pytest.MonkeyPatch, v1_id: int) -> None:
    real = apply_mod.apply_decision

    def faulty(src: Any, run: Any) -> Any:
        if src["v1_id"] == v1_id:
            raise RuntimeError(f"injected fault at decision {v1_id}")
        return real(src, run)

    monkeypatch.setattr(apply_mod, "apply_decision", faulty)


def test_at_s6_a_fault_in_one_unit_applies_nothing(
    env: Any,
    clock: FakeClock,
    owner_ctx: CommandContext,
    inbox: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fault_on(monkeypatch, 906)
    with pytest.raises(RuntimeError, match="injected fault"):
        _import(env, "s1.json", clock, owner_ctx, inbox)
    assert one("SELECT count(*) FROM dec_decisions") == 0
    assert one("SELECT count(*) FROM sys_id_foreign") == 0
    assert one("SELECT count(*) FROM dec_editions") == 0
    run = rows("SELECT * FROM dec_import_runs")
    assert [(r["status"], r["report_status"]) for r in run] == [("failed", "blocked")]
    assert "RuntimeError" in run[0]["error"]
    assert dec.shadow_report(env, run_id=run[0]["id"]).value.report_status == "blocked"

    monkeypatch.undo()
    report = _import(env, "s1.json", clock, owner_ctx, inbox)
    assert report.run_id == run[0]["id"]
    assert (report.status, report.report_status) == ("applied", "written")
    assert one("SELECT count(*) FROM dec_decisions") == 8


def test_at_s6_chunks_stay_partial_until_the_rerun_completes_them(
    env: Any,
    clock: FakeClock,
    owner_ctx: CommandContext,
    inbox: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 30
    with unit_of_work("cfg", owner_ctx):
        set_setting("dec.import_unit_max_rows", str(limit))
    plan = snapshot_mod.build_plan(sb.s1(), {}, {})
    chunks = plan.chunks(limit)
    assert len(chunks) >= 3
    second = chunks[1][0][0].src["v1_id"]
    first_chunk = {p.src["v1_id"] for p in chunks[0][0]}

    _fault_on(monkeypatch, second)
    with pytest.raises(RuntimeError, match="injected fault"):
        _import(env, "s1.json", clock, owner_ctx, inbox)
    runs = rows("SELECT * FROM dec_import_runs")
    assert [(r["status"], r["report_status"]) for r in runs] == [("partial", "blocked")]
    present = {r["number"] for r in rows("SELECT number FROM dec_decisions")}
    assert present == first_chunk
    blocked = dec.shadow_report(env, run_id=runs[0]["id"])
    assert blocked.value.report_status == "blocked"
    assert blocked.value.items == ()
    assert any("partial" in note for note in blocked.coverage)

    monkeypatch.undo()
    report = _import(env, "s1.json", clock, owner_ctx, inbox)
    assert report.run_id == runs[0]["id"]
    assert (report.status, report.report_status) == ("applied", "written")
    assert one("SELECT count(*) FROM dec_decisions") == 8
    assert report.counts["decisions"].new == 8  # the counts of the run's first attempt
    shadow = dec.shadow_report(env).value
    assert shadow.totals["unexpected"] == 0


# ==================================================================================================
# AT-S7 and the goal adapter


def _goal_reasons(env: Any, today: date) -> list[Any]:
    items = dec.waiting(env, today=today).value
    return [r for i in items if i.ref == "D-0907" for r in i.reasons if r.kind == "goal_changed"]


def test_at_s7_goal_changed_once_until_a_review_answers_it(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    reasons = _goal_reasons(env, date(2026, 11, 15))
    assert [(r.due, r.code, r.status) for r in reasons] == [
        (date(2026, 11, 5), "V1_G901", "dropped")
    ]
    _import(env, "s1_double_prime.json", clock, owner_ctx, inbox)  # a review dated 11-10
    assert _goal_reasons(env, date(2026, 12, 11)) == []


def test_the_goal_adapter_answers_as_known_at_a_time(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    goals = dec.default_env().goal_directory
    now = goals.state("V1_G901")
    assert now is not None
    assert (now.status, now.status_changed_date, now.first_seen_date, now.title) == (
        "dropped",
        date(2026, 11, 5),
        date(2026, 11, 15),
        "Cut fixed costs",
    )
    assert goals.state("V1_G901", as_of=datetime(2026, 11, 6, 12, 0, tzinfo=UTC)) is not None
    assert goals.state("V1_G901", as_of=datetime(2026, 11, 4, 12, 0, tzinfo=UTC)) is None
    active = goals.state("V1_G902", as_of=datetime(2026, 11, 15, 6, 0, tzinfo=UTC))
    assert active is not None
    assert active.status == "active"
    assert goals.state("V1_G902", as_of=datetime(2026, 11, 15, 4, 0, tzinfo=UTC)) is None
    assert goals.state("V1_G999") is None
    assert goals.state("G901") is None  # a bare source ref is no foreign ref
    with pytest.raises(NotImplementedError):
        goals.likely_goals("anything")


# ==================================================================================================
# AT-S8


def test_at_s8_knowledge_time_is_the_source_record_time(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path
) -> None:
    day30 = datetime(2026, 11, 30, 12, 0, tzinfo=UTC)
    import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=inbox, at=day30)
    day5 = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    known = dec.as_of(env, "D-0907", day5, axis="knowledge").value
    assert known.decision.public_id == "D-0907"
    with pytest.raises(NotFound):
        dec.as_of(env, "D-0907", day5, axis="instance")


# ==================================================================================================
# Refusals, in the order of §6.5


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _code(excinfo: Any) -> str:
    return str(excinfo.value.code)


def test_unknown_fields_floats_and_bad_json_are_format_errors(
    env: Any, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    doc = sb.s1()
    doc["decisions"][0]["surprise"] = 1
    doc["content_hash"] = sb.content_hash(doc)
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "a.json", sb.dumps(doc)), ctx=owner_ctx)
    assert _code(e) == "IMPORT_FORMAT_UNSUPPORTED"

    text = sb.dumps(sb.s1()).replace('"confidence": 70', '"confidence": 70.0')
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "b.json", text), ctx=owner_ctx)
    assert _code(e) == "IMPORT_FORMAT_UNSUPPORTED"
    assert "float" in e.value.detail

    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "c.json", "{not json"), ctx=owner_ctx)
    assert _code(e) == "IMPORT_FORMAT_UNSUPPORTED"

    other = planted(sb.s1, lambda d: d.update(format_version=2))
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "d.json", sb.dumps(other)), ctx=owner_ctx)
    assert _code(e) == "IMPORT_FORMAT_UNSUPPORTED"

    wrong_ref = planted(sb.s1, lambda d: d["decisions"][0].update(v1_ref="D999"))
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "e.json", sb.dumps(wrong_ref)), ctx=owner_ctx)
    assert _code(e) == "IMPORT_FORMAT_UNSUPPORTED"
    assert one("SELECT count(*) FROM dec_import_runs") == 0  # a refusal writes nothing


def test_a_changed_document_fails_its_content_hash(
    env: Any, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    text = sb.dumps(sb.s1()).replace("Cut fixed costs", "Cut fixed costs now")
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "s1.json", text), ctx=owner_ctx)
    assert _code(e) == "IMPORT_HASH_MISMATCH"


def test_at_k9_a_dev_instance_refuses_a_real_snapshot(
    env: Any, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    real = planted(sb.s1, lambda d: d.update(synthetic=False))
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "real.json", sb.dumps(real)), ctx=owner_ctx)
    assert _code(e) == "IMPORT_NOT_SYNTHETIC"
    assert one("SELECT count(*) FROM dec_decisions") == 0


def test_at_k9_a_validation_instance_accepts_a_real_snapshot(
    data_root: Path, clock: FakeClock, owner_tz: str, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    init_instance(data_root, role="validation", clock=clock, timezone=owner_tz)
    store = store_api.open_store(data_root, clock=clock)
    try:
        with store_api.use_store(store):
            real = planted(sb.s1, lambda d: d.update(synthetic=False))
            report = dec.import_snapshot(
                dec.default_env(), _write(tmp_path, "real.json", sb.dumps(real)), ctx=owner_ctx
            ).value
            assert (report.status, report.synthetic) == ("applied", False)
            assert one("SELECT count(*) FROM dec_decisions") == 8
    finally:
        store.close()


def test_other_roles_refuse_imports(
    env: Any, owner_ctx: CommandContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_load = snapshot_mod.load_instance

    def as_production(conn: Any) -> Any:
        return dataclasses.replace(real_load(conn), role="production")

    monkeypatch.setattr(snapshot_mod, "load_instance", as_production)
    path = _write(tmp_path, "s1.json", sb.dumps(sb.s1()))
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, path, ctx=owner_ctx)
    assert _code(e) == "IMPORT_ROLE"


def test_numbers_in_the_native_block_conflict(
    env: Any, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    high = planted(sb.s1, lambda d: d["id_space"]["decision"].update(highest_issued=1001))
    with pytest.raises(Refused) as e:
        dec.import_snapshot(env, _write(tmp_path, "high.json", sb.dumps(high)), ctx=owner_ctx)
    assert _code(e) == "IMPORT_SOURCE_CONFLICT"


def test_adopted_mirrors_refuse_changes(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path, tmp_path: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)
    with unit_of_work("dec", owner_ctx):
        store_api.update_mutable(
            "dec_mirror_state",
            {"issuer": "V1", "source_kind": "decision", "source_id": "908"},
            adopted_at="2026-12-01T00:00:00.000Z",
        )
    with pytest.raises(Refused) as e:
        import_family(env, "s1_prime.json", clock=clock, ctx=owner_ctx, directory=tmp_path / "x")
    assert _code(e) == "IMPORT_ADOPTED"
    assert "D-0908" in e.value.detail


def test_dry_run_plans_without_writing(env: Any, owner_ctx: CommandContext, tmp_path: Path) -> None:
    path = _write(tmp_path, "s1.json", sb.dumps(sb.s1()))
    report = dec.import_snapshot(env, path, mode="dry_run", ctx=owner_ctx)
    assert report.tx is None
    assert report.value.run_id is None
    assert report.value.counts["decisions"].new == 8
    assert one("SELECT count(*) FROM dec_import_runs") == 0
    assert one("SELECT count(*) FROM dec_decisions") == 0


# ==================================================================================================
# Children that change or disappear in the source


def test_children_removed_or_changed_in_the_source(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, inbox: Path, tmp_path: Path
) -> None:
    _import(env, "s1.json", clock, owner_ctx, inbox)

    def edit(d: dict[str, Any]) -> None:
        d.update(as_of="2026-11-16T05:00:00Z", as_of_date="2026-11-16")
        by = {x["v1_id"]: x for x in d["decisions"]}
        by[907]["facts"] = []
        by[907]["links"] = [x for x in by[907]["links"] if x["kind"] != "task"]
        by[904]["assumptions"] = [a for a in by[904]["assumptions"] if a["v1_id"] != 9041]
        by[906]["assumptions"][2]["threshold"] = "access confirmed in writing"
        by[908]["assumptions"][0]["next_check_at"] = "2026-11-20"

    report = import_doc(
        env,
        planted(sb.s1, edit),
        tmp_path / "changed.json",
        clock=clock,
        ctx=owner_ctx,
        at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
    ).value

    fact = rows(
        "SELECT f.voided_reason FROM dec_facts f JOIN dec_decisions d "
        "ON d.id = f.decision_id WHERE d.public_id = 'D-0907'"
    )
    assert fact == [{"voided_reason": "deleted in V1"}]
    links = rows(
        "SELECT l.target_ref, l.removed_tx, l.removed_reason FROM dec_links l "
        "JOIN dec_decisions d ON d.id = l.decision_id WHERE d.public_id = 'D-0907' "
        "AND l.role = 'foreign_attachment'"
    )
    assert len(links) == 1
    assert links[0]["removed_tx"] is not None
    assert links[0]["removed_reason"] == "removed in V1"

    a904 = rows(
        "SELECT a.code_n, a.status, a.drop_reason FROM dec_assumptions a "
        "JOIN dec_decisions d ON d.id = a.decision_id WHERE d.public_id = 'D-0904' "
        "ORDER BY code_n"
    )
    assert a904 == [
        {"code_n": 1, "status": "dropped", "drop_reason": "deleted in V1"},
        {"code_n": 2, "status": "active", "drop_reason": None},
    ]
    a906 = rows(
        "SELECT a.id, a.code_n, a.status, a.superseded_by, a.threshold_text "
        "FROM dec_assumptions a JOIN dec_decisions d ON d.id = a.decision_id "
        "WHERE d.public_id = 'D-0906' ORDER BY code_n"
    )
    assert [(a["code_n"], a["status"]) for a in a906] == [
        (1, "active"),
        (2, "active"),
        (3, "superseded"),
        (4, "active"),
    ]
    assert a906[2]["superseded_by"] == a906[3]["id"]
    assert a906[3]["threshold_text"] == "access confirmed in writing"
    assert any("D-0906_A-03 changed in V1" in f for f in report.findings)
    successor_checks = rows(
        "SELECT state, observed_at FROM dec_checks WHERE assumption_id = ?", (a906[3]["id"],)
    )
    assert successor_checks == [{"state": "HOLDING", "observed_at": "2026-11-10"}]

    changed = rows(
        "SELECT v.field, v.new_value FROM dec_versions v WHERE v.entity = 'assumption' "
        "ORDER BY v.id"
    )
    assert {"field": "next_check_at", "new_value": "2026-11-20"} in changed
    assert {"field": "status", "new_value": "dropped"} in changed
    assert {"field": "status", "new_value": "superseded"} in changed

    sealed = rows(
        "SELECT d.public_id, e.n, e.reason FROM dec_editions e JOIN dec_decisions d "
        "ON d.id = e.decision_id WHERE e.n > 1 ORDER BY d.number"
    )
    assert [(e["public_id"], e["reason"]) for e in sealed] == [
        ("D-0904", "source_changed"),
        ("D-0906", "source_changed"),
    ]
    assert all(r.ok for r in dec.integrity(env, "all").value)
    shadow = dec.shadow_report(env, run_id=report.run_id).value
    counts = {
        i.subject_ref: (i.v1_value, i.v2_value, i.classification)
        for i in shadow.items
        if i.aspect == "count"
    }
    assert counts["assumptions"] == ("10", "10", "same")
    assert counts["facts"] == ("1", "1", "same")
    assert counts["links"] == ("4", "4", "same")
