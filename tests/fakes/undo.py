"""A fake ``UndoHandler``: accepts entries inside a window, records what it undid."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from coflow.kernel.context import CommandContext
from coflow.kernel.errors import Accept, RefusalCode, Refused
from coflow.kernel.ports.undo import UndoEntry, UndoResult


@dataclass
class FakeUndoHandler:
    module: str = "fake"
    tools: frozenset[str] = frozenset({"fake_write"})
    window: timedelta = timedelta(hours=24)
    not_undoable: frozenset[str] = frozenset()
    undone: list[str] = field(default_factory=list)

    def check(self, entry: UndoEntry, now: datetime) -> Accept | Refused:
        if entry.tool in self.not_undoable:
            return Refused(RefusalCode.NOT_UNDOABLE, f"{entry.tool} is not undoable")
        if now - entry.recorded_at > self.window:
            return Refused(RefusalCode.UNDO_WINDOW_PASSED, "the undo window has passed")
        if entry.entry_id in self.undone:
            return Refused(RefusalCode.UNDO_HAS_LATER_WRITES, "already undone")
        return Accept()

    def undo(self, entry: UndoEntry, ctx: CommandContext) -> UndoResult:
        self.undone.append(entry.entry_id)
        return UndoResult(entry_id=entry.entry_id, restored=(entry.target_ref,))
