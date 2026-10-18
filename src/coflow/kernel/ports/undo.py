"""``UndoHandler``: the inverse of an MCP write, run as the owning module's own unit of work.

Skeleton file (ARCHITECTURE §5.1, §6.1; spec §5.5, §12.1). Every write tool reachable over MCP has
an undo handler in its owning module, or is marked "not undoable" in the MCP catalogue (MCP-4).
DEC's handlers arrive in I2 (``modules/dec/undo.py``), CMT's in I3; ACT takes the port over at
stage 2.

Refusals: ``UNDO_WINDOW_PASSED`` (``dec.undo_window_hours``), ``UNDO_HAS_LATER_WRITES``,
``NOT_UNDOABLE``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from coflow.kernel.context import CommandContext
from coflow.kernel.errors import Accept, Refused

__all__ = ["UndoEntry", "UndoHandler", "UndoMark", "UndoResult"]

UndoMark = Literal["undoable", "not_undoable"]
"""How the MCP catalogue marks each write tool (AT-X3)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UndoEntry:
    """One undoable write: which tool wrote what, in which unit of work, under which interaction."""

    entry_id: str
    module: str
    tool: str
    target_ref: str
    tx: int
    recorded_at: datetime
    interaction_id: str
    payload: Mapping[str, object] = field(default_factory=dict)  # ids and prior values only


@dataclass(frozen=True, slots=True, kw_only=True)
class UndoResult:
    entry_id: str
    restored: tuple[str, ...] = ()  # refs or field names restored
    note: str = ""


@runtime_checkable
class UndoHandler(Protocol):
    module: str
    tools: frozenset[str]

    def check(self, entry: UndoEntry, now: datetime) -> Accept | Refused:
        """Whether ``entry`` can still be undone at ``now`` (window, later writes, undoability)."""
        ...

    def undo(self, entry: UndoEntry, ctx: CommandContext) -> UndoResult: ...
