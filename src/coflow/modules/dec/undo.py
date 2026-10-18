"""DEC's undo handlers for its MCP write tools (spec §5.5, MCP-4).

Owned by track S (store, import, shadow); increment I2. ``undo`` is the target of ``dec.api.undo``
and ``DecUndoHandler`` is constructed by ``dec.api.undo_handler``; the signatures are fixed by the
facade (provisional until the I2 skeleton review) and the track implements them.
"""

from __future__ import annotations

from datetime import datetime

from coflow.kernel.context import CommandContext, CommandResult
from coflow.kernel.errors import Accept, Refused
from coflow.kernel.ports.undo import UndoEntry, UndoResult
from coflow.modules.dec.domain.model import DecEnv

__all__ = ["DecUndoHandler", "undo"]

_TODO = "track S: modules/dec/undo.py"


def undo(env: DecEnv, undo_entry: UndoEntry, *, ctx: CommandContext) -> CommandResult[UndoResult]:
    raise NotImplementedError(_TODO)


class DecUndoHandler:
    """Implements ``kernel.ports.undo.UndoHandler`` for the ``dec_`` write tools [I2]."""

    module = "dec"
    tools: frozenset[str] = frozenset()

    def __init__(self, env: DecEnv) -> None:
        self.env = env

    def check(self, entry: UndoEntry, now: datetime) -> Accept | Refused:
        raise NotImplementedError(_TODO)

    def undo(self, entry: UndoEntry, ctx: CommandContext) -> UndoResult:
        raise NotImplementedError(_TODO)
