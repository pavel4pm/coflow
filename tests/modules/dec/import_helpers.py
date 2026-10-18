"""Helpers for track S's import and shadow tests: importing the synthetic family, reading rows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coflow.kernel.context import CommandContext, CommandResult, FakeClock
from coflow.kernel.store.api import read_connection
from coflow.modules.dec import api as dec
from tests.modules.dec import snapshot_builder as sb

# When each family member is imported: shortly after its export, as the daily job would.
IMPORT_AT: dict[str, datetime] = {
    "s1.json": datetime(2026, 11, 15, 9, 30, tzinfo=UTC),
    "s1_prime.json": datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
    "s1_double_prime.json": datetime(2026, 12, 11, 9, 0, tzinfo=UTC),
}


def rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with read_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(sql: str, params: tuple[Any, ...] = ()) -> Any:
    with read_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def table_counts(*tables: str) -> dict[str, int]:
    return {t: int(one(f"SELECT count(*) FROM {t}")) for t in tables}


ALL_DEC_TABLES = (
    "dec_decisions",
    "dec_options",
    "dec_assumptions",
    "dec_checks",
    "dec_facts",
    "dec_fact_assumptions",
    "dec_reviews",
    "dec_outcomes",
    "dec_learnings",
    "dec_links",
    "dec_versions",
    "dec_editions",
    "dec_foreign_context",
    "dec_import_runs",
    "dec_mirror_state",
    "dec_shadow_items",
)


def fingerprint() -> dict[str, Any]:
    """Every DEC row plus the event, transaction-log and id-registry counts."""
    out: dict[str, Any] = {}
    with read_connection() as conn:
        for t in ALL_DEC_TABLES:
            out[t] = [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        for t in ("sys_events", "sys_tx_log", "sys_id_foreign", "sys_id_burned", "sys_id_aliases"):
            out[t] = int(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
    return out


def import_family(
    env: Any,
    name: str,
    *,
    clock: FakeClock,
    ctx: CommandContext,
    directory: Path,
    at: datetime | None = None,
) -> CommandResult[Any]:
    """Import one member of the committed family, as a file in an inbox directory."""
    source = sb.SNAPSHOT_DIR / name
    target = directory / name
    directory.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    clock.set(at or IMPORT_AT[name])
    return dec.import_snapshot(env, target, ctx=ctx)


def import_doc(
    env: Any,
    doc: dict[str, Any],
    path: Path,
    *,
    clock: FakeClock,
    ctx: CommandContext,
    at: datetime,
    mode: str = "shadow",
) -> CommandResult[Any]:
    sb.write(doc, path)
    clock.set(at)
    return dec.import_snapshot(env, path, mode=mode, ctx=ctx)  # type: ignore[arg-type]


def planted(base: Callable[[], dict[str, Any]], edit: Callable[[dict[str, Any]], None]) -> Any:
    return sb.planted(base, edit)
