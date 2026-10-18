"""The manual flag and publishability (spec §5.2, PRV-10). Owned by track S (store, import,
shadow); increment I2. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.model import (
    DecEnv,
    ManualFlag,
    Publishability,
)

_TODO = "track S: modules/dec/commands/flags.py"


def set_manual_flag(
    env: DecEnv, ref: str, flag: ManualFlag | None, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def set_publishability(
    env: DecEnv, ref: str, value: Publishability, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)
