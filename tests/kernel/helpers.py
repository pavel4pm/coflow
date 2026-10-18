"""Small helpers shared by the kernel tests."""

from __future__ import annotations

import sqlite3

from coflow.kernel.context import CommandContext


def count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def ctx(actor: str = "owner", *, channel: str = "cli", key: str | None = None) -> CommandContext:
    """An owner-channel context at the CLI (or another channel), optionally with an idempotency
    key."""
    return CommandContext(
        actor=actor,
        channel=channel,  # type: ignore[arg-type]
        owner_channel=channel in ("cli", "bot"),
        interaction_id=f"int-{actor}",
        idempotency_key=key,
    )


def raw_row(conn: sqlite3.Connection, table: str, **values: object) -> int:
    """Insert a row through a raw connection with dummy values for every NOT NULL column, ignoring
    CHECK and foreign-key constraints: a direct edit as any SQLite client could make it."""
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA ignore_check_constraints = ON")
    row: dict[str, object] = {}
    for info in conn.execute(f'PRAGMA table_info("{table}")').fetchall():
        name, kind, notnull, default, pk = info[1], str(info[2]).upper(), info[3], info[4], info[5]
        if name in values:
            row[name] = values[name]
        elif pk or not notnull or default is not None:
            continue
        else:
            row[name] = 1 if kind == "INTEGER" else "x"
    cols = ", ".join(f'"{c}"' for c in row)
    marks = ", ".join("?" for _ in row)
    cur = conn.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({marks})', tuple(row.values()))
    conn.execute("PRAGMA ignore_check_constraints = OFF")
    return int(cur.lastrowid or 0)
