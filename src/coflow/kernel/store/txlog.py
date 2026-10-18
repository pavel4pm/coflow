"""``sys_tx_log``: one append-only row per unit of work with actor, channel, owner-channel flag,
interaction id, approval ref, instance role, code version and command (spec §2.3).

Owned by track K (kernel); increment I1, spec §12.2.

The unit of work writes the row when it opens (so every row it inserts can carry the ``tx``) and
the row commits or rolls back with the unit. Readers (history, as-of, provenance in answers) use
``load_tx`` / ``load_txs`` on any read connection.

Spec note: besides the columns of §2.3 the row records ``owner_module`` (whose unit it was) and
``source_ref`` (the context's source), so provenance needs no second lookup. A unit that wrote
nothing is rolled back and leaves no row.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from coflow.kernel.context import CommandContext

__all__ = ["TxRecord", "insert_tx", "load_tx", "load_txs"]

_COLUMNS = (
    "tx, committed_at, actor, channel, owner_channel, interaction_id, source_ref, approval_ref,"
    " instance_role, code_version, owner_module, command"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class TxRecord:
    """One ``sys_tx_log`` row: who wrote a unit of work, how, and under which approval."""

    tx: int
    committed_at: str
    actor: str
    channel: str
    owner_channel: bool
    interaction_id: str
    source_ref: str | None
    approval_ref: str | None
    instance_role: str
    code_version: str
    owner_module: str
    command: str | None


def insert_tx(
    conn: sqlite3.Connection,
    *,
    ctx: CommandContext,
    committed_at: str,
    instance_role: str,
    code_version: str,
    owner_module: str,
    command: str | None,
) -> int:
    """Write the unit's row and return its ``tx`` (the writer calls this in ``system`` mode)."""
    cur = conn.execute(
        "INSERT INTO sys_tx_log (committed_at, actor, channel, owner_channel, interaction_id,"
        " source_ref, approval_ref, instance_role, code_version, owner_module, command)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            committed_at,
            ctx.actor,
            ctx.channel,
            1 if ctx.owner_channel else 0,
            ctx.interaction_id,
            ctx.source_ref,
            ctx.approval_ref,
            instance_role,
            code_version,
            owner_module,
            command,
        ),
    )
    tx = cur.lastrowid
    assert tx is not None
    return int(tx)


def _record(row: tuple[object, ...] | sqlite3.Row) -> TxRecord:
    values = tuple(row)
    return TxRecord(
        tx=int(str(values[0])),
        committed_at=str(values[1]),
        actor=str(values[2]),
        channel=str(values[3]),
        owner_channel=bool(values[4]),
        interaction_id=str(values[5]),
        source_ref=None if values[6] is None else str(values[6]),
        approval_ref=None if values[7] is None else str(values[7]),
        instance_role=str(values[8]),
        code_version=str(values[9]),
        owner_module=str(values[10]),
        command=None if values[11] is None else str(values[11]),
    )


def load_tx(conn: sqlite3.Connection, tx: int) -> TxRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM sys_tx_log WHERE tx = ?", (tx,)).fetchone()
    return None if row is None else _record(row)


def load_txs(conn: sqlite3.Connection, txs: Iterable[int]) -> dict[int, TxRecord]:
    """The rows of several units at once (history and provenance lines)."""
    wanted = sorted(set(txs))
    out: dict[int, TxRecord] = {}
    for i in range(0, len(wanted), 500):
        chunk = wanted[i : i + 500]
        marks = ",".join("?" * len(chunk))
        for row in conn.execute(
            f"SELECT {_COLUMNS} FROM sys_tx_log WHERE tx IN ({marks})", chunk
        ).fetchall():
            rec = _record(row)
            out[rec.tx] = rec
    return out
