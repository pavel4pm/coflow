"""CFG settings and profile, OBS usage signals, POL classes and canaries."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from coflow.kernel.config.profile import OwnerProfile, load_profile, validate_profile
from coflow.kernel.config.settings import load_settings, set_setting
from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import ContractViolation, NotFound
from coflow.kernel.obs.usage import record_usage, usage_signals
from coflow.kernel.policy.canary import (
    JOURNAL_CANARY,
    make_canary,
    scan_texts,
    scan_value,
)
from coflow.kernel.policy.classes import may_store, most_restrictive
from coflow.kernel.store import api
from coflow.kernel.store.db import SqliteStore
from coflow.kernel.store.txlog import load_tx
from tests.kernel.helpers import ctx

# --------------------------------------------------------------------------------------------------
# CFG


def test_settings_are_a_history_and_the_latest_wins(kstore: SqliteStore) -> None:
    with api.unit_of_work("cfg", ctx(), command="set") as unit:
        set_setting("dec.no_data_days", "21")
        first_tx = unit.tx
    with api.unit_of_work("cfg", ctx(), command="set"):
        set_setting("dec.no_data_days", "28")
        set_setting("dec.no_data_days", "28")  # unchanged: no new row
    with api.read_connection() as conn:
        settings = load_settings(conn)
        rows = conn.execute(
            "SELECT value, tx FROM cfg_settings WHERE key = 'dec.no_data_days' ORDER BY id"
        ).fetchall()
    assert settings["dec.no_data_days"] == "28"
    assert [r["value"] for r in rows] == ["21", "28"]
    assert rows[0]["tx"] == first_tx


def test_settings_are_written_in_cfg_units_with_valid_keys(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="set"), pytest.raises(ContractViolation):
        set_setting("dec.no_data_days", "21")
    with api.unit_of_work("cfg", ctx(), command="set"):
        for key in ("NoDots", "dec", "dec..x", "dec.Margin"):
            with pytest.raises(ContractViolation):
                set_setting(key, "1")
        with pytest.raises(ContractViolation, match="fixed at init"):
            set_setting("ids.issuer", "ZZ")
        with pytest.raises(ContractViolation):
            set_setting("dec.drift_margin", 0.2)  # type: ignore[arg-type]


def test_profile_validation() -> None:
    good = OwnerProfile(display_name="Owner", timezone="Europe/Berlin", locale="en", currency="EUR")
    assert validate_profile(good) == []
    bad = OwnerProfile(display_name="", timezone="Nowhere/City", locale="de", currency="eu")
    assert len(validate_profile(bad)) == 4


def test_load_profile_needs_a_profile(kstore: SqliteStore) -> None:
    with api.read_connection() as conn:
        assert load_profile(conn).display_name == "Owner"
    import sqlite3

    empty = sqlite3.connect(":memory:")
    empty.execute(
        "CREATE TABLE cfg_profile (id INTEGER, display_name TEXT, timezone TEXT,"
        " locale TEXT, currency TEXT)"
    )
    with pytest.raises(NotFound):
        load_profile(empty)
    empty.close()


# --------------------------------------------------------------------------------------------------
# OBS


def test_usage_signals_count_per_day_and_channel(kstore: SqliteStore, clock: FakeClock) -> None:
    mcp = CommandContext(
        actor="mcp_client-a", channel="mcp", owner_channel=False, interaction_id="m"
    )
    record_usage("dec.waiting.pull", ctx=ctx())
    record_usage("dec.waiting.pull", ctx=ctx(), detail={"brief": "yes"})
    record_usage("dec.waiting.pull", ctx=mcp, value=3)
    clock.set(datetime(2026, 11, 15, 23, 30, tzinfo=UTC))  # 00:30 on the 16th in Berlin
    record_usage("dec.waiting.pull", ctx=ctx())
    record_usage("dec.shadow.opened", ctx=ctx(), day=date(2026, 11, 1))
    with api.read_connection() as conn:
        signals = usage_signals(conn, signal="dec.waiting.pull")
        everything = usage_signals(conn, since=date(2026, 11, 1), until=date(2026, 11, 1))
        actors = {
            r[0] for r in conn.execute("SELECT actor FROM sys_tx_log WHERE owner_module = 'obs'")
        }
    got = {(s.day.isoformat(), s.channel): s.value for s in signals}
    assert got == {
        ("2026-11-15", "cli"): Decimal(2),
        ("2026-11-15", "mcp"): Decimal(3),
        ("2026-11-16", "cli"): Decimal(1),
    }
    assert next(s for s in signals if s.channel == "cli").detail == {"brief": "yes"}
    assert [s.signal for s in everything] == ["dec.shadow.opened"]
    assert actors == {"owner", "mcp_client-a"}


def test_usage_signals_refuse_bad_input_and_nesting(kstore: SqliteStore) -> None:
    for bad in ("pull", "Dec.Pull", "dec pull"):
        with pytest.raises(ContractViolation):
            record_usage(bad, ctx=ctx())
    with pytest.raises(ContractViolation):
        record_usage(
            "dec.waiting.pull", ctx=ctx(), detail={"text": "a whole statement, with commas"}
        )
    with pytest.raises(ContractViolation):
        record_usage("dec.waiting.pull", ctx=ctx(), value=True)
    with api.unit_of_work("tst", ctx(), command="query"), pytest.raises(ContractViolation):
        record_usage("dec.waiting.pull", ctx=ctx(), day=date(2026, 11, 15))


def test_a_pull_is_one_obs_unit(kstore: SqliteStore) -> None:
    record_usage("dec.waiting.pull", ctx=ctx(), day=date(2026, 11, 15))
    with api.read_connection() as conn:
        tx = conn.execute("SELECT tx FROM sys_usage_signals").fetchone()[0]
        rec = load_tx(conn, tx)
    assert rec is not None
    assert (rec.owner_module, rec.command) == ("obs", "record_usage")


# --------------------------------------------------------------------------------------------------
# POL


def test_classes_order_and_flow() -> None:
    assert most_restrictive("work", "financial", "system") == "financial"
    assert most_restrictive("work", "journal") == "journal"
    assert may_store("financial", "work")
    assert may_store("system", "work")
    assert not may_store("work", "financial")
    assert not may_store("work", "journal")
    with pytest.raises(ContractViolation):
        most_restrictive()
    with pytest.raises(ContractViolation):
        may_store("secret", "work")


def test_canaries_are_deterministic_and_found() -> None:
    assert make_canary("journal") == JOURNAL_CANARY
    assert make_canary("journal") != make_canary("statement")
    assert JOURNAL_CANARY.startswith("CANARY-JOURNAL-")
    answer = {"items": [{"statement": "Keep the room", "notes": [f"from {JOURNAL_CANARY}"]}]}
    assert scan_value(JOURNAL_CANARY, answer)
    assert not scan_value(JOURNAL_CANARY, {"items": [1, 2.5, None, True]})
    assert scan_texts(JOURNAL_CANARY, ["clean", f"log {JOURNAL_CANARY}", "clean"]) == [1]
