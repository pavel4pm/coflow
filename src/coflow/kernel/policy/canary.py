"""Canary values: a synthetic marker written into a record must never appear in ``sys_events``,
logs or MCP answers (spec §4.6, AT-K6, AT-N10).

Owned by track K (kernel); increment I1, spec §12.2.

A canary is a deterministic, unmistakable marker (``make_canary('journal')``). A test writes it
into a field that must stay inside its table (a decision's statement, a journal-class source's
text) and then scans every place it must never reach: the event tables, other tables, log output,
MCP answers. ``scan_database`` looks through every text column of every table (or the listed
ones); ``scan_texts`` through any strings (rendered answers, captured logs).

``JOURNAL_CANARY`` is the journal canary fixture of PRV-1 / NFR-6 for the slice: the value a fake
journal-class evidence source returns, which no DEC or CMT table, event, log or answer may contain.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CANARY_PREFIX",
    "JOURNAL_CANARY",
    "CanaryHit",
    "make_canary",
    "scan_database",
    "scan_texts",
    "scan_value",
]

CANARY_PREFIX = "CANARY"


def make_canary(label: str) -> str:
    """A marker no real text contains: ``CANARY-<LABEL>-<10 hex>``, the same for the same label."""
    digest = hashlib.sha256(f"coflow-canary-{label}".encode()).hexdigest()[:10]
    safe = "".join(ch for ch in label.upper() if ch.isalnum()) or "X"
    return f"{CANARY_PREFIX}-{safe}-{digest}"


JOURNAL_CANARY = make_canary("journal")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanaryHit:
    table: str
    column: str
    rowid: int


def scan_database(
    conn: sqlite3.Connection,
    canary: str,
    *,
    tables: Iterable[str] | None = None,
    exclude: Iterable[str] = (),
) -> list[CanaryHit]:
    """Every (table, column, rowid) whose text contains ``canary``."""
    skip = set(exclude)
    if tables is None:
        names = [
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " ORDER BY name"
            )
        ]
    else:
        names = list(tables)
    hits: list[CanaryHit] = []
    for table in names:
        if table in skip:
            continue
        columns = [str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')]
        for column in columns:
            rows = conn.execute(
                f'SELECT rowid FROM "{table}" WHERE instr(CAST("{column}" AS TEXT), ?) > 0',
                (canary,),
            ).fetchall()
            hits.extend(CanaryHit(table=table, column=column, rowid=int(r[0])) for r in rows)
    return hits


def scan_value(canary: str, value: Any) -> bool:
    """Whether ``canary`` appears anywhere in a JSON-like value (an MCP answer, a payload)."""
    if isinstance(value, str):
        return canary in value
    if isinstance(value, Mapping):
        return any(scan_value(canary, k) or scan_value(canary, v) for k, v in value.items())
    if isinstance(value, list | tuple | set | frozenset):
        return any(scan_value(canary, v) for v in value)
    if value is None or isinstance(value, bool | int | float):
        return False
    return canary in json.dumps(value, default=str)


def scan_texts(canary: str, texts: Iterable[str]) -> list[int]:
    """The positions of the texts that contain ``canary`` (captured logs, rendered output)."""
    return [i for i, text in enumerate(texts) if canary in text]
