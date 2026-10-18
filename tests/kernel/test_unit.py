"""The unit of work: atomicity, stamping, ownership, idempotency, data classes (AT-K5; P-14,
NFR-13)."""

from __future__ import annotations

import itertools
import json
import threading

import pytest

from coflow.kernel.context import CommandContext, FakeClock, format_instant
from coflow.kernel.errors import Conflict, ContractViolation, NotFound, RefusalCode, Refused
from coflow.kernel.events.publish import publish
from coflow.kernel.ids import tap
from coflow.kernel.policy.classes import declare_inputs
from coflow.kernel.store import api
from coflow.kernel.store.db import SqliteStore
from coflow.kernel.store.txlog import load_tx
from tests.kernel.helpers import count, ctx

_TABLES = ("tst_items", "tst_checks", "tst_heads", "sys_events", "sys_tx_log", "sys_command_keys")


class Fault(Exception):
    """Injected after the n-th statement of a unit."""


def _counts(store: SqliteStore) -> dict[str, int]:
    with store.read_connection() as conn:
        out = {t: count(conn, t) for t in _TABLES}
        out["next_d"] = conn.execute(
            "SELECT next_n FROM sys_id_sequence WHERE prefix = 'D'"
        ).fetchone()[0]
    return out


def _body() -> int:
    """A unit with every kind of write: rows, a number, events, a set-once and a head update."""
    item = api.insert("tst_items", {"title": "Rent the small room"})
    check = api.insert("tst_checks", {"item_id": item, "state": "HOLDING"})
    number = tap.issue("D")
    head = api.insert("tst_heads", {"public_id": number.public_id, "title": "Move the workshop"})
    publish("coflow.tst.item.added", subject=number.public_id, entity="item", changed=["title"])
    api.set_once("tst_checks", check, voided_reason="duplicate")
    api.update_head("tst_heads", head, 1, status="active")
    publish("coflow.tst.head.updated", subject=number.public_id, entity="head", changed=["status"])
    return head


def test_at_k5_fault_after_every_statement_leaves_all_or_nothing(kstore: SqliteStore) -> None:
    before = _counts(kstore)
    for k in itertools.count(1):
        seen = 0

        def hook(sql: str, k: int = k) -> None:
            nonlocal seen
            seen += 1
            if seen == k:
                raise Fault(f"after statement {k}: {sql[:30]}")

        kstore.statement_hook = hook
        try:
            with api.unit_of_work("tst", ctx(), command="everything"):
                _body()
        except Fault:
            kstore.statement_hook = None
            assert _counts(kstore) == before, f"fault {k} left a partial unit"
            continue
        kstore.statement_hook = None
        break
    assert k > 10, "the unit ran more statements than that"
    after = _counts(kstore)
    assert after["tst_items"] == before["tst_items"] + 1
    assert after["sys_events"] == before["sys_events"] + 2
    assert after["sys_tx_log"] == before["sys_tx_log"] + 1
    assert after["next_d"] == before["next_d"] + 1


def test_at_k5_tx_and_recorded_at_come_from_the_store(
    kstore: SqliteStore, clock: FakeClock
) -> None:
    clock.advance(minutes=5)
    with api.unit_of_work("tst", ctx(), command="stamp") as unit:
        item = api.insert("tst_items", {"title": "Measure the room"})
        tx, at = unit.tx, unit.committed_at
    assert at == clock.now()
    with api.read_connection() as conn:
        row = conn.execute("SELECT tx, recorded_at FROM tst_items WHERE id = ?", (item,)).fetchone()
        rec = load_tx(conn, tx)
    assert (row["tx"], row["recorded_at"]) == (tx, format_instant(at))
    assert rec is not None
    assert rec.committed_at == format_instant(at)


@pytest.mark.parametrize("stamp", ["recorded_at", "tx"])
def test_at_k5_a_caller_supplied_stamp_is_refused(kstore: SqliteStore, stamp: str) -> None:
    before = _counts(kstore)
    value: str | int = "2026-01-01T00:00:00.000Z" if stamp == "recorded_at" else 1
    with (
        pytest.raises(ContractViolation, match="stamped by the store"),
        api.unit_of_work("tst", ctx(), command="stamp"),
    ):
        api.insert("tst_items", {"title": "Measure the room", stamp: value})
    assert _counts(kstore) == before


def test_the_tx_log_row_records_provenance(kstore: SqliteStore) -> None:
    approved = CommandContext(
        actor="owner",
        channel="cli",
        owner_channel=True,
        interaction_id="int-9",
        source_ref="V1_S90001",
        approval_ref="card-7",
    )
    with api.unit_of_work("tst", approved, command="approve") as unit:
        api.insert("tst_items", {"title": "Approved item"})
        tx = unit.tx
    mcp = CommandContext(
        actor="mcp_client-a", channel="mcp", owner_channel=False, interaction_id="m"
    )
    with api.unit_of_work("tst", mcp, command="propose") as unit:
        api.insert("tst_items", {"title": "Proposed item"})
        tx_mcp = unit.tx
    with api.read_connection() as conn:
        rec = load_tx(conn, tx)
        rec_mcp = load_tx(conn, tx_mcp)
    assert rec is not None
    assert rec_mcp is not None
    assert (rec.actor, rec.channel, rec.owner_channel, rec.approval_ref) == (
        "owner",
        "cli",
        True,
        "card-7",
    )
    assert (rec.source_ref, rec.instance_role, rec.owner_module, rec.command) == (
        "V1_S90001",
        "dev",
        "tst",
        "approve",
    )
    assert rec.code_version
    assert (rec_mcp.channel, rec_mcp.owner_channel) == ("mcp", False)


def test_a_unit_that_wrote_nothing_leaves_no_trace(kstore: SqliteStore) -> None:
    before = _counts(kstore)
    with api.unit_of_work("tst", ctx(), command="read"):
        api.current_unit().fetch_all("SELECT * FROM tst_items")
    assert _counts(kstore) == before


def test_writes_happen_only_inside_a_unit(kstore: SqliteStore) -> None:
    with pytest.raises(ContractViolation, match="no unit"):
        api.insert("tst_items", {"title": "Loose write"})
    with (
        api.unit_of_work("tst", ctx(), command="nest"),
        pytest.raises(ContractViolation),
        api.unit_of_work("tst", ctx(), command="inner"),
    ):
        pass
    with (
        pytest.raises(ContractViolation, match="do not nest"),
        kstore.unit_of_work("tst", ctx(), command="outer"),
        kstore.unit_of_work("tst", ctx(), command="inner"),
    ):
        pass


def test_a_unit_writes_only_its_own_tables(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="own"):
        with pytest.raises(ContractViolation, match="owned by 'oth'"):
            api.insert("oth_items", {"title": "Not mine"})
        with pytest.raises(ContractViolation, match="kernel services"):
            api.insert("sys_id_sequence", {"prefix": "Z", "next_n": 1})
        with pytest.raises(ContractViolation, match="not a registered table"):
            api.insert("sqlite_schema", {"name": "x"})
        unit = api.current_unit()
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("INSERT INTO oth_items (title, tx, recorded_at) VALUES ('x', 1, 'x')")
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("DELETE FROM tst_items")
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("COMMIT")
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("PRAGMA foreign_keys = OFF")
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("ATTACH DATABASE ':memory:' AS other")
        with pytest.raises(ContractViolation, match="not authorized"):
            unit.fetch_one("DROP TABLE tst_items")
        api.insert("tst_items", {"title": "Mine"})
    with api.unit_of_work("oth", ctx(), command="own"):
        api.insert("oth_items", {"title": "Mine too"})


def test_values_are_str_int_or_none(kstore: SqliteStore) -> None:
    from decimal import Decimal

    with api.unit_of_work("tst", ctx(), command="types"):
        for bad in (0.5, Decimal("1.5"), b"bytes", format_instant):
            with pytest.raises(ContractViolation, match="stored values"):
                api.insert("tst_stakes", {"amount": bad})  # type: ignore[dict-item]
        with pytest.raises(ContractViolation, match="unknown columns"):
            api.insert("tst_items", {"title": "x", "colour": "blue"})
        api.insert("tst_stakes", {"amount": "120.50"})


def test_update_head_versions_and_conflicts(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="create"):
        head = api.insert("tst_heads", {"public_id": "D-1001", "title": "Adopt a release train"})
    with api.unit_of_work("tst", ctx(), command="update"):
        assert api.update_head("tst_heads", head, 1, title="Adopt a weekly release train") == 2
        with pytest.raises(Conflict) as conflict:
            api.update_head("tst_heads", head, 1, status="active")
        assert conflict.value.current_version == 2
        with pytest.raises(NotFound):
            api.update_head("tst_heads", 999, 1, status="active")
        with pytest.raises(ContractViolation, match="not mutable"):
            api.update_head("tst_heads", head, 2, public_id="D-1002")
        with pytest.raises(ContractViolation, match="not mutable"):
            api.update_head("tst_heads", head, 2, recorded_at="2026-01-01T00:00:00.000Z")
        with pytest.raises(ContractViolation, match="versioned head"):
            api.update_mutable("tst_heads", {"id": head}, status="active")
    with api.read_connection() as conn:
        row = conn.execute("SELECT title, version FROM tst_heads WHERE id = ?", (head,)).fetchone()
    assert (row["title"], row["version"]) == ("Adopt a weekly release train", 2)


def test_update_mutable_on_unversioned_tables(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="count"):
        api.insert("tst_counters", {"key": "pulls", "value": 1})
        assert api.update_mutable("tst_counters", {"key": "pulls"}, value=2) == 1
        assert api.update_mutable("tst_counters", {"key": "none"}, value=2) == 0
        with pytest.raises(ContractViolation, match="not mutable"):
            api.update_mutable("tst_counters", {"key": "pulls"}, tx=1)


def test_idempotency_keys_return_the_first_result(kstore: SqliteStore) -> None:
    keyed = ctx(key="k-1")

    def command() -> tuple[dict[str, int], bool]:
        with api.unit_of_work("tst", keyed, command="add_item") as unit:
            if unit.prior_result is not None:  # type: ignore[attr-defined]
                return json.loads(unit.prior_result), True  # type: ignore[attr-defined]
            item = api.insert("tst_items", {"title": "Once only"})
            result = {"item": item}
            unit.remember(json.dumps(result))  # type: ignore[attr-defined]
            return result, False

    first, replayed_first = command()
    second, replayed_second = command()
    assert first == second
    assert not replayed_first
    assert replayed_second
    with api.read_connection() as conn:
        assert conn.execute("SELECT count(*) FROM tst_items").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM sys_command_keys").fetchone()[0] == 1
    with (
        pytest.raises(ContractViolation, match="was used by"),
        api.unit_of_work("tst", keyed, command="another_command"),
    ):
        pass


def test_journal_input_is_refused_and_classes_never_flow_down(kstore: SqliteStore) -> None:
    before = _counts(kstore)

    def journal_fact() -> None:
        with api.unit_of_work("tst", ctx(), command="fact"):
            declare_inputs("journal")
            api.insert("tst_items", {"title": "From the journal"})

    with pytest.raises(Refused) as refused:
        journal_fact()
    assert refused.value.code is RefusalCode.JOURNAL_CLASS_INPUT
    assert _counts(kstore) == before
    with api.unit_of_work("tst", ctx(), command="stake"):
        declare_inputs("financial")
        api.insert("tst_stakes", {"amount": "40.00"})
        with pytest.raises(ContractViolation, match="financial-class input"):
            api.insert("tst_items", {"title": "An amount in a work table"})
    with api.unit_of_work("tst", ctx(), command="work"):
        declare_inputs("work")
        api.insert("tst_counters", {"key": "rows", "value": 1})  # work feeds system bookkeeping


def test_read_connections_cannot_write(kstore: SqliteStore) -> None:
    import sqlite3

    with api.read_connection() as conn:
        for sql in (
            "INSERT INTO tst_items (title, tx, recorded_at) VALUES ('x', 1, 'x')",
            "PRAGMA query_only = OFF",
            "ATTACH DATABASE ':memory:' AS other",
        ):
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(sql)


def test_read_connections_see_one_snapshot(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="seed"):
        api.insert("tst_items", {"title": "First"})
    with api.read_connection() as conn:
        assert count(conn, "tst_items") == 1
        done = threading.Event()

        def write() -> None:
            with api.unit_of_work("tst", ctx("other"), command="seed"):
                api.insert("tst_items", {"title": "Second"})
            done.set()

        threading.Thread(target=write).start()
        assert done.wait(10)
        assert count(conn, "tst_items") == 1, "the read transaction keeps its snapshot"
    with api.read_connection() as conn:
        assert count(conn, "tst_items") == 2


def test_units_from_threads_are_serialised(kstore: SqliteStore) -> None:
    order: list[str] = []
    inside = threading.Event()
    release = threading.Event()

    def first() -> None:
        with api.unit_of_work("tst", ctx("first"), command="slow"):
            api.insert("tst_items", {"title": "First"})
            order.append("first-in")
            inside.set()
            release.wait(10)
            order.append("first-out")

    def second() -> None:
        inside.wait(10)
        with api.unit_of_work("tst", ctx("second"), command="fast"):
            order.append("second-in")
            api.insert("tst_items", {"title": "Second"})

    a, b = threading.Thread(target=first), threading.Thread(target=second)
    a.start()
    b.start()
    inside.wait(10)
    release.set()
    a.join(10)
    b.join(10)
    assert order == ["first-in", "first-out", "second-in"]


def test_a_closed_or_read_only_store_has_no_writer(kstore: SqliteStore, clock: FakeClock) -> None:
    from coflow.kernel.store.db import open_store

    ro = open_store(kstore.data_root, clock=clock, read_only=True)
    try:
        with pytest.raises(ContractViolation, match="read-only"):
            ro.unit_of_work("tst", ctx())
        with ro.read_connection() as conn:
            assert count(conn, "sys_instance") == 1
    finally:
        ro.close()
    ro.close()
    with pytest.raises(ContractViolation, match="closed"):
        ro.read_connection().__enter__()
