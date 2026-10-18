"""``BEFORE UPDATE`` and ``BEFORE DELETE`` triggers generated from the table registry at migration
time: append-only rows, set-once columns, erasure (spec §2.1, AT-K4).

Owned by track K (kernel); increment I1, spec §12.2.

Per registered table the generator writes:

- ``coflow_<table>__delete``: no row of a registered table is ever deleted;
- one ``BEFORE UPDATE OF <col>`` trigger per column that is not mutable:
  - an **immutable** column (neither mutable, set-once nor erasable) never changes;
  - a **set-once** column changes only from NULL (``voided_at`` once, then never again);
  - an **erasable** column changes only in an update that stamps a new ``erased_tx`` (POL's
    erasure unit); a column both set-once and erasable may do either;
  - ``erased_tx`` itself only ever increases.

The triggers are plain SQL (``RAISE(ABORT, 'coflow: ...')``), so they hold for a direct edit with
any SQLite client, not only for CoFlow's own connections. Mutable columns of heads, and ``version``,
are guarded by the commands that own them (``update_head``), not by triggers.

Spec note: ``UPDATE OF`` triggers fire when the column is assigned, which every change of it needs.
``INSERT OR REPLACE`` would bypass delete triggers only with ``recursive_triggers`` off; CoFlow's
connections turn it on, and the authorizer refuses DELETE from units anyway.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from coflow.kernel.store.registry import STAMP_COLUMNS, TableDecl

__all__ = ["TRIGGER_PREFIX", "regenerate_triggers", "trigger_sql"]

TRIGGER_PREFIX = "coflow_"


def _raise(message: str) -> str:
    return "SELECT RAISE(ABORT, '" + message.replace("'", "''") + "');"


def trigger_sql(decl: TableDecl) -> list[tuple[str, str]]:
    """(name, CREATE TRIGGER statement) for every trigger of one table."""
    t = decl.table
    out = [
        (
            f"{TRIGGER_PREFIX}{t}__delete",
            f'CREATE TRIGGER "{TRIGGER_PREFIX}{t}__delete" BEFORE DELETE ON "{t}" '
            f"BEGIN {_raise(f'coflow: {t} accepts no DELETE')} END",
        )
    ]
    free = set(decl.mutable)
    if decl.versioned:
        free.add("version")
    for col in decl.columns:
        if col in free:
            continue
        changed = f'NEW."{col}" IS NOT OLD."{col}"'
        erasure = 'NEW."erased_tx" IS NOT NULL AND NEW."erased_tx" IS NOT OLD."erased_tx"'
        if col == "erased_tx" and decl.erasable:
            when = (
                f'{changed} AND (NEW."erased_tx" IS NULL OR '
                f'(OLD."erased_tx" IS NOT NULL AND NEW."erased_tx" <= OLD."erased_tx"))'
            )
            message = f"coflow: {t}.erased_tx only increases"
        elif col in decl.set_once and col in decl.erasable and col not in STAMP_COLUMNS:
            when = f'{changed} AND OLD."{col}" IS NOT NULL AND NOT ({erasure})'
            message = f"coflow: {t}.{col} is set once (or erased)"
        elif col in decl.set_once and col not in STAMP_COLUMNS:
            when = f'{changed} AND OLD."{col}" IS NOT NULL'
            message = f"coflow: {t}.{col} is set once"
        elif col in decl.erasable and col not in STAMP_COLUMNS:
            when = f"{changed} AND NOT ({erasure})"
            message = f"coflow: {t}.{col} changes only by erasure"
        else:
            when = changed
            message = f"coflow: {t}.{col} is immutable"
        name = f"{TRIGGER_PREFIX}{t}__{col}"
        out.append(
            (
                name,
                f'CREATE TRIGGER "{name}" BEFORE UPDATE OF "{col}" ON "{t}" '
                f"WHEN {when} BEGIN {_raise(message)} END",
            )
        )
    return out


def regenerate_triggers(conn: sqlite3.Connection, decls: Iterable[TableDecl]) -> int:
    """Drop and recreate the generated triggers of ``decls``; returns how many exist afterwards.

    Runs inside the migration's transaction, so a file and its triggers commit together.
    """
    count = 0
    for decl in decls:
        existing = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'trigger' AND tbl_name = ? "
            "AND substr(name, 1, ?) = ?",
            (decl.table, len(TRIGGER_PREFIX), TRIGGER_PREFIX),
        ).fetchall()
        for (name,) in existing:
            conn.execute(f'DROP TRIGGER "{name}"')
        for _name, sql in trigger_sql(decl):
            conn.execute(sql)
            count += 1
    return count
