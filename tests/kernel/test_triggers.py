"""Generated triggers: append-only rows, set-once columns, erasure (AT-K4; DEC-13, NFR-13).

The rules hold for any SQLite client, so most of these tests edit the database directly through a
raw connection, as a hand edit would.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

import pytest

from coflow.kernel.context import CommandContext, format_instant
from coflow.kernel.errors import ContractViolation
from coflow.kernel.store import api
from coflow.kernel.store.db import SqliteStore
from coflow.kernel.store.registry import load_registry
from coflow.kernel.store.triggers import TRIGGER_PREFIX, trigger_sql
from tests.kernel.helpers import ctx, raw_row

Raw = Callable[[], sqlite3.Connection]


def _check(store: SqliteStore) -> tuple[int, int]:
    with api.unit_of_work("tst", ctx(), command="seed") as unit:
        item = api.insert("tst_items", {"title": "Measure the room"})
        check = api.insert("tst_checks", {"item_id": item, "state": "VIOLATED", "note": "late"})
        return check, unit.tx


def test_at_k4_append_only_set_once_and_erasure(kstore: SqliteStore, raw: Raw) -> None:
    check, tx = _check(kstore)
    conn = raw()

    with pytest.raises(sqlite3.IntegrityError, match=r"tst_checks\.state is immutable"):
        conn.execute("UPDATE tst_checks SET state = 'HOLDING' WHERE id = ?", (check,))

    conn.execute(
        "UPDATE tst_checks SET voided_at = '2026-11-15T09:31:00.000Z' WHERE id = ?", (check,)
    )
    with pytest.raises(sqlite3.IntegrityError, match="voided_at is set once"):
        conn.execute(
            "UPDATE tst_checks SET voided_at = '2026-11-16T09:31:00.000Z' WHERE id = ?", (check,)
        )

    with pytest.raises(sqlite3.IntegrityError, match="changes only by erasure"):
        conn.execute("UPDATE tst_checks SET note = NULL WHERE id = ?", (check,))
    conn.execute("UPDATE tst_checks SET note = NULL, erased_tx = ? WHERE id = ?", (tx + 1, check))
    row = conn.execute("SELECT note, erased_tx FROM tst_checks WHERE id = ?", (check,)).fetchone()
    assert (row["note"], row["erased_tx"]) == (None, tx + 1)
    with pytest.raises(sqlite3.IntegrityError, match="erased_tx only increases"):
        conn.execute("UPDATE tst_checks SET erased_tx = ? WHERE id = ?", (tx, check))

    with pytest.raises(sqlite3.IntegrityError, match="accepts no DELETE"):
        conn.execute("DELETE FROM tst_checks WHERE id = ?", (check,))
    with pytest.raises(sqlite3.IntegrityError, match="recorded_at is immutable"):
        conn.execute("UPDATE tst_checks SET recorded_at = 'x' WHERE id = ?", (check,))


def test_at_k4_through_the_unit_of_work(kstore: SqliteStore) -> None:
    check, _ = _check(kstore)
    erasure = CommandContext(actor="owner", channel="cli", owner_channel=True, interaction_id="e")
    with api.unit_of_work("tst", ctx(), command="void") as unit:
        api.set_once("tst_checks", check, voided_at=format_instant(unit.committed_at))
    with api.unit_of_work("tst", ctx(), command="void"):
        with pytest.raises(ContractViolation, match="already set"):
            api.set_once("tst_checks", check, voided_at="2026-11-16T00:00:00.000Z")
        with pytest.raises(ContractViolation, match="not set-once"):
            api.set_once("tst_checks", check, state="HOLDING")
        with pytest.raises(ContractViolation, match="not a versioned head"):
            api.update_head("tst_checks", check, 1, state="HOLDING")
    with (
        api.unit_of_work("tst", ctx(), command="erase") as not_pol,
        pytest.raises(ContractViolation, match="only POL"),
    ):
        not_pol.erase("tst_checks", check, note=None)  # type: ignore[attr-defined]
    with api.unit_of_work("pol", erasure, command="erase") as unit:
        unit.erase("tst_checks", check, note=None)  # type: ignore[attr-defined]
        erased_by = unit.tx
    with api.read_connection() as conn:
        row = conn.execute(
            "SELECT note, erased_tx FROM tst_checks WHERE id = ?", (check,)
        ).fetchone()
    assert (row["note"], row["erased_tx"]) == (None, erased_by)


def test_heads_keep_identity_columns_and_change_mutable_ones(kstore: SqliteStore, raw: Raw) -> None:
    with api.unit_of_work("tst", ctx(), command="seed"):
        head = api.insert("tst_heads", {"public_id": "D-1001", "title": "Adopt a release train"})
    conn = raw()
    conn.execute(
        "UPDATE tst_heads SET title = 'Adopt a weekly release train' WHERE id = ?", (head,)
    )
    with pytest.raises(sqlite3.IntegrityError, match="public_id is immutable"):
        conn.execute("UPDATE tst_heads SET public_id = 'D-1002' WHERE id = ?", (head,))
    with pytest.raises(sqlite3.IntegrityError, match="tx is immutable"):
        conn.execute("UPDATE tst_heads SET tx = 99 WHERE id = ?", (head,))
    with pytest.raises(sqlite3.IntegrityError, match="accepts no DELETE"):
        conn.execute("DELETE FROM tst_heads")
    # REPLACE deletes the old row; with recursive triggers on (as on CoFlow's own connections)
    # the delete trigger sees it.
    conn.execute("PRAGMA recursive_triggers = ON")
    with pytest.raises(sqlite3.IntegrityError, match="accepts no DELETE"):
        conn.execute(
            "INSERT OR REPLACE INTO tst_heads (id, public_id, title, tx, recorded_at)"
            " VALUES (?, 'D-1001', 'x', 1, 'x')",
            (head,),
        )


def test_every_registered_table_has_its_generated_triggers(dev_store: SqliteStore) -> None:
    """Fitness: the triggers in the database are exactly what the registry declares, for the
    kernel's tables and every module's (DEC and CMT once their migrations exist)."""
    with dev_store.read_connection() as conn:
        registry = load_registry(conn)
        existing = {
            (str(r[0]), str(r[1]))
            for r in conn.execute(
                "SELECT tbl_name, name FROM sqlite_schema WHERE type = 'trigger'"
                " AND substr(name, 1, ?) = ?",
                (len(TRIGGER_PREFIX), TRIGGER_PREFIX),
            )
        }
    expected = {(decl.table, name) for decl in registry.values() for name, _ in trigger_sql(decl)}
    assert existing == expected
    for decl in registry.values():
        assert (decl.table, f"{TRIGGER_PREFIX}{decl.table}__delete") in existing


def test_at_k4_on_the_real_dec_checks(dev_store: SqliteStore, raw: Raw) -> None:
    """The spec's own statements against ``dec_checks`` once track S's migration declares it."""
    registry = dev_store.registry
    if "dec_checks" not in registry:
        pytest.skip("dec_checks is not declared yet (track S's migration)")
    decl = registry["dec_checks"]
    assert decl.append_only
    assert "voided_at" in decl.set_once
    assert "state" not in decl.set_once | decl.erasable | decl.mutable
    conn = raw()
    erasable = sorted(decl.erasable)
    filled = {erasable[0]: "a note"} if erasable else {}
    rowid = raw_row(conn, "dec_checks", state="UNKNOWN", voided_at=None, erased_tx=None, **filled)
    with pytest.raises(sqlite3.IntegrityError, match="is immutable"):
        conn.execute("UPDATE dec_checks SET state = 'HOLDING' WHERE rowid = ?", (rowid,))
    conn.execute(
        "UPDATE dec_checks SET voided_at = '2026-11-15T10:00:00.000Z' WHERE rowid = ?", (rowid,)
    )
    with pytest.raises(sqlite3.IntegrityError, match="set once"):
        conn.execute(
            "UPDATE dec_checks SET voided_at = '2026-11-15T11:00:00.000Z' WHERE rowid = ?", (rowid,)
        )
    if erasable:
        column = erasable[0]
        with pytest.raises(sqlite3.IntegrityError, match="only by erasure"):
            conn.execute(f'UPDATE dec_checks SET "{column}" = NULL WHERE rowid = ?', (rowid,))
        conn.execute(
            f'UPDATE dec_checks SET "{column}" = NULL, erased_tx = 7 WHERE rowid = ?', (rowid,)
        )
