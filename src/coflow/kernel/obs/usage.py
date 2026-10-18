"""Usage signals (``sys_usage_signals``, spec §3.16, §9.3, P-13).

Owned by track K; increment I1, spec §12.2. ``record_usage`` is fixed by the skeleton because track
X records every waiting-list pull by channel (``dec_waiting``, ``coflow dec waiting``); the track
implements it.

One row per (signal, owner-zone day, channel) holds a decimal total as text; ``record_usage`` adds
to it in its own ``obs`` unit, so the unit's ``sys_tx_log`` row also records who pulled (the
context's actor and channel). ``detail`` keys are merged into ``detail_json`` (the latest value of a
key wins); detail values are short labels, never record content. ``usage_signals`` reads them back
(loop metrics, ``dec metrics``).

Spec note: the call must not run inside another unit (units never nest); interfaces record a pull
after the query has answered.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coflow.kernel.config.profile import load_profile
from coflow.kernel.context import CommandContext, local_date
from coflow.kernel.errors import ContractViolation
from coflow.kernel.store.api import current_store, read_connection, unit_of_work

__all__ = ["UsageSignal", "record_usage", "usage_signals"]

_SIGNAL = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
_LABEL = re.compile(r"^[A-Za-z0-9_.:\- ]{0,64}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageSignal:
    signal: str
    day: date
    channel: str
    value: Decimal
    detail: Mapping[str, str]


def _cfj(value: Mapping[str, str]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_usage(
    signal: str,
    *,
    ctx: CommandContext,
    value: int = 1,
    day: date | None = None,
    detail: Mapping[str, str] | None = None,
) -> None:
    """Add ``value`` to the signal's row for (``signal``, ``day``, ``ctx.channel``) in its own unit
    of work (owner ``obs``). ``day`` defaults to today in the owner's zone. Example signal names:
    ``dec.waiting.pull``, ``dec.shadow.opened``."""
    if not _SIGNAL.match(signal):
        raise ContractViolation(f"{signal!r} is not a signal name (dotted lower-case names)")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractViolation("a usage value is an integer")
    extra = dict(detail or {})
    for key, label in extra.items():
        if not _SIGNAL.match(f"d.{key}") or not isinstance(label, str) or not _LABEL.match(label):
            raise ContractViolation(f"detail {key!r} holds a short label, not record content")
    if day is None:
        with read_connection() as conn:
            tz = load_profile(conn).timezone
        day = local_date(current_store().clock.now(), tz)
    key = {"signal": signal, "day": day.isoformat(), "channel": ctx.channel}
    with unit_of_work("obs", ctx, command="record_usage") as unit:
        row = unit.fetch_one(
            "SELECT value, detail_json FROM sys_usage_signals"
            " WHERE signal = ? AND day = ? AND channel = ?",
            (signal, key["day"], ctx.channel),
        )
        if row is None:
            unit.insert(
                "sys_usage_signals", {**key, "value": str(value), "detail_json": _cfj(extra)}
            )
            return
        merged = {**json.loads(str(row["detail_json"])), **extra}
        unit.update_mutable(
            "sys_usage_signals",
            key,
            value=str(Decimal(str(row["value"])) + value),
            detail_json=_cfj(merged),
        )


def usage_signals(
    conn: sqlite3.Connection,
    *,
    signal: str | None = None,
    since: date | None = None,
    until: date | None = None,
) -> list[UsageSignal]:
    """Stored signals, oldest day first (``signal`` and the day range are optional filters)."""
    sql = "SELECT signal, day, channel, value, detail_json FROM sys_usage_signals WHERE 1 = 1"
    params: list[str] = []
    if signal is not None:
        sql += " AND signal = ?"
        params.append(signal)
    if since is not None:
        sql += " AND day >= ?"
        params.append(since.isoformat())
    if until is not None:
        sql += " AND day <= ?"
        params.append(until.isoformat())
    sql += " ORDER BY day, signal, channel"
    return [
        UsageSignal(
            signal=str(r[0]),
            day=date.fromisoformat(str(r[1])),
            channel=str(r[2]),
            value=Decimal(str(r[3])),
            detail=json.loads(str(r[4])),
        )
        for r in conn.execute(sql, params).fetchall()
    ]
