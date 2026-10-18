"""Track S: the DEC schema (spec §2.4, §2.6), the loaders of ``store/repo.py``, the version replay
and the mirror guard (AT-S4)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import Refused
from coflow.kernel.store.api import Store, read_connection
from coflow.modules.dec import api as dec
from coflow.modules.dec.store import mirror, repo, versions
from tests.modules.dec.import_helpers import import_family, rows

DEC_TABLES = {
    # table: (data class, append_only)
    "dec_decisions": ("work", 0),
    "dec_editions": ("work", 1),
    "dec_options": ("work", 1),
    "dec_forks": ("work", 0),
    "dec_assumptions": ("work", 0),
    "dec_checks": ("work", 1),
    "dec_readings": ("work", 1),
    "dec_facts": ("work", 1),
    "dec_fact_assumptions": ("work", 1),
    "dec_reviews": ("work", 1),
    "dec_outcomes": ("work", 1),
    "dec_learnings": ("work", 1),
    "dec_stakes": ("financial", 1),
    "dec_links": ("work", 1),
    "dec_foreign_context": ("system", 0),
    "dec_proposals": ("work", 0),
    "dec_versions": ("work", 1),
    "dec_import_runs": ("system", 0),
    "dec_mirror_state": ("system", 0),
    "dec_shadow_items": ("system", 1),
    "dec_cases": ("system", 0),
}


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


@pytest.fixture
def imported(env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path) -> Any:
    import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path / "inbox")
    return env


# ==================================================================================================
# The schema


def test_every_dec_table_is_registered_strict_and_classed(dev_store: Store) -> None:
    registry = {
        r["table_name"]: r for r in rows("SELECT * FROM sys_table_registry WHERE module = 'dec'")
    }
    assert set(registry) == set(DEC_TABLES)
    for table, (data_class, append_only) in DEC_TABLES.items():
        assert registry[table]["data_class"] == data_class, table
        assert registry[table]["append_only"] == append_only, table
        strict = rows("SELECT strict FROM pragma_table_list WHERE name = ?", (table,))
        assert strict == [{"strict": 1}], table
        cols = {r["name"] for r in rows(f"PRAGMA table_info({table})")}
        assert {"tx", "recorded_at"} <= cols, table


def _raw(data_root: Path) -> sqlite3.Connection:
    """A plain SQLite connection, as any client would open the file (triggers still hold)."""
    db = next(data_root.rglob("*.db"), None) or next(data_root.rglob("*.sqlite*"))
    return sqlite3.connect(db)


def test_the_check_log_is_append_only_by_trigger(imported: Any, data_root: Path) -> None:
    conn = _raw(data_root)
    try:
        check_id = conn.execute(
            "SELECT id FROM dec_checks WHERE state <> 'DRIFTING' LIMIT 1"
        ).fetchone()[0]
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE dec_checks SET state = 'DRIFTING' WHERE id = ?", (check_id,))
        with pytest.raises(sqlite3.DatabaseError, match="DELETE"):
            conn.execute("DELETE FROM dec_checks WHERE id = ?", (check_id,))
        conn.execute(
            "UPDATE dec_checks SET voided_at = '2026-11-15T10:00:00.000Z' WHERE id = ?",
            (check_id,),
        )
        with pytest.raises(sqlite3.DatabaseError, match="set once"):
            conn.execute(
                "UPDATE dec_checks SET voided_at = '2026-11-15T11:00:00.000Z' WHERE id = ?",
                (check_id,),
            )
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE dec_editions SET seal_hash = 'x'")
    finally:
        conn.rollback()
        conn.close()


def test_assumption_basis_columns_are_immutable(imported: Any, data_root: Path) -> None:
    conn = _raw(data_root)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE dec_assumptions SET threshold_text = 'other'")
        conn.execute("UPDATE dec_assumptions SET next_check_at = '2026-12-01'")  # mutable
    finally:
        conn.rollback()
        conn.close()


# ==================================================================================================
# The loaders


def test_load_decision_returns_every_row_typed(imported: Any) -> None:
    with read_connection() as conn:
        d = repo.load_decision(conn, "D-0907")
        assert repo.load_decision(conn, "D-0999") is None
    assert d is not None
    assert d.public_id == "D-0907"
    assert d.number == 907
    assert d.decided_at == date(2026, 11, 2)
    assert d.review_due == date(2026, 11, 12)
    assert d.origin_recorded_at == datetime(2026, 11, 2, 19, 2, 11, tzinfo=UTC)
    assert d.known_at == d.origin_recorded_at
    assert d.recorded_at == datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
    assert d.unknowns == ("whether the small room has enough power",)
    assert d.mirror_of == "V1_D907"
    assert d.absent_since_run_id is None
    assert [o.code for o in d.options] == ["O-01", "O-02"]
    assert d.options[0].ref == "D-0907_O-01"
    assert [a.ref for a in d.assumptions] == ["D-0907_A-01"]
    assert d.assumptions[0].is_critical is True
    assert [f.ref for f in d.facts] == ["D-0907_FT-001"]
    assert d.facts[0].occurred_at == date(2026, 11, 9)
    assert [b.assumption_id for b in d.facts[0].bearings] == [d.assumptions[0].id]
    assert [e.ref for e in d.editions] == ["D-0907_E-01"]
    assert [(link.role, link.target_ref) for link in d.links] == [
        ("serves", "V1_G901"),
        ("foreign_attachment", "V1_K9001"),
        ("about", "V1_C-901"),
    ]
    assert [(v.field, v.old_value) for v in d.versions] == [("review_due", "2026-11-08")]
    assert d.stored["public_id"] == "D-0907"
    assert d.editions[0].stored["seal_hash"] == d.editions[0].seal_hash


def test_checks_are_ordered_by_observed_time_then_knowledge(imported: Any) -> None:
    with read_connection() as conn:
        d = repo.load_decision(conn, "D-0910")
    assert d is not None
    check = d.assumptions[0].checks[0]
    assert check.ref == "D-0910_A-01_CK-001"
    assert check.observed_at == datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
    assert check.observed_precision == "instant"
    assert check.reconstructed is True
    assert check.due_answered is None


def test_load_decisions_filters_and_orders(imported: Any) -> None:
    with read_connection() as conn:
        everything = repo.load_decisions(conn)
        closed = repo.load_decisions(conn, statuses=["closed"])
        mirrors = repo.load_decisions(conn, mirror_issuer="V1")
        none = repo.load_decisions(conn, mirror_issuer="CF2LOG")
        some = repo.load_decisions(conn, refs=["D-0910", "D-0904"])
        empty = repo.load_decisions(conn, kinds=[])
    assert [d.number for d in everything] == list(range(903, 911))
    assert [d.public_id for d in closed] == ["D-0903"]
    assert len(mirrors) == 8
    assert none == []
    assert [d.public_id for d in some] == ["D-0904", "D-0910"]
    assert empty == []
    d903 = closed[0]
    assert [o.basis for o in d903.outcomes] == ["reported"]
    assert [x.legacy_text for x in d903.learnings] == [
        "Evening sessions filled up; small groups worked better"
    ]
    assert d903.reviews[0].ref == "D-0903_R-01"
    assert d903.reviews[0].occurred_at == date(2026, 10, 30)


def test_load_assumption_and_runs(imported: Any) -> None:
    with read_connection() as conn:
        found = repo.load_assumption(conn, "D-0908_A-02")
        assert repo.load_assumption(conn, "D-0908_A-09") is None
        assert repo.load_assumption(conn, "D-0999_A-01") is None
        run = repo.load_import_run(conn)
        assert repo.load_import_run(conn, issuer="CF2LOG") is None
        assert repo.load_forks(conn) == []
        assert repo.load_proposals(conn, statuses=["proposed"]) == []
    assert found is not None
    decision, assumption = found
    assert decision.public_id == "D-0908"
    assert assumption.is_critical is False
    assert run is not None
    assert (run.status, run.report_status, run.source_issuer) == ("applied", "written", "V1")
    assert run.as_of_date == date(2026, 11, 15)
    assert json.loads(run.counts_json)["decisions"]["new"] == 8


def test_replay_undoes_hidden_versions(imported: Any) -> None:
    with read_connection() as conn:
        d = repo.load_decision(conn, "D-0907")
    assert d is not None
    replayed = versions.replay_decision(d, d.versions)
    assert replayed.review_due == date(2026, 11, 8)
    assert replayed.stored["review_due"] == "2026-11-08"
    assert versions.replay_decision(d, []) is d
    assert versions.value_text(True) == "1"
    assert versions.typed_value("confidence", "70") == 70


# ==================================================================================================
# AT-S4: the mirror guard


@pytest.mark.parametrize("ctx_name", ["owner_ctx", "mcp_ctx"])
def test_at_s4_every_write_on_a_v1_mirror_is_refused(
    imported: Any, ctx_name: str, request: pytest.FixtureRequest
) -> None:
    ctx: CommandContext = request.getfixturevalue(ctx_name)
    assert ctx.channel in ("cli", "mcp")
    with read_connection() as conn:
        d = repo.load_decision(conn, "D-0907")
    assert d is not None
    for command in mirror.DEC_WRITE_COMMANDS:
        with pytest.raises(Refused) as e:
            mirror.guard_mirror(d, op=command, fields=["notes"])
        assert str(e.value.code) == "MIRRORED"
        assert "V1 is the system of record" in e.value.detail
        assert command in e.value.detail


def test_the_log_owns_only_its_fields() -> None:
    log_mirror = {"public_id": "D-1004", "mirror_of": "CF2LOG_D-037", "mirror_scope": "basis_only"}
    mirror.guard_mirror(log_mirror, op="add_assumption", fields=["assumption"])
    mirror.guard_mirror(log_mirror, op="update_decision", fields=["question", "review_due"])
    with pytest.raises(Refused) as e:
        mirror.guard_mirror(log_mirror, op="update_decision", fields=["statement", "question"])
    assert str(e.value.code) == "MIRRORED"
    assert "project's decision log" in e.value.detail
    assert e.value.allowed == ("question",)
    with pytest.raises(Refused):
        mirror.guard_mirror(log_mirror, op="add_option", fields=["option_text"])
    native = {"public_id": "D-1001", "mirror_of": None, "mirror_scope": None}
    mirror.guard_mirror(native, op="update_decision", fields=["statement"])


def test_mirror_lines_and_authorities() -> None:
    assert mirror.issuer_of("V1_D907") == "V1"
    assert mirror.issuer_of(None) is None
    assert mirror.authority_of("CF2LOG_D-037").scope == "basis_only"  # type: ignore[union-attr]
    unknown = mirror.authority_of("ZZ_X1")
    assert unknown is not None
    assert unknown.owned is None
    assert mirror.mirror_line("V1_D907", "2026-11-15T05:00:12.000Z") == (
        "mirrored from V1, snapshot exported at 2026-11-15T05:00:12.000Z; read-only here"
    )
    assert mirror.mirror_line(None, None) is None
