"""Assumption commands (spec §5.2, §3.4). Owned by track S (store, import, shadow); increment I2.
The signatures are the targets of ``dec.api`` and are fixed by the facade (provisional until the
I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Mapping

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    AddAssumptionResult,
    AssumptionInput,
    CodeResult,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
)

_TODO = "track S: modules/dec/commands/assumptions.py"


def add_assumption(
    env: DecEnv, ref: str, *, assumption: AssumptionInput, ctx: CommandContext
) -> CommandResult[AddAssumptionResult]:
    raise NotImplementedError(_TODO)


def supersede_assumption(
    env: DecEnv,
    assumption_ref: str,
    *,
    changes: Mapping[str, object],
    reason: str,
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    raise NotImplementedError(_TODO)


def drop_assumption(
    env: DecEnv, assumption_ref: str, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)
