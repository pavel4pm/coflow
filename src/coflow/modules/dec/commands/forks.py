"""Forks: open questions with options (spec §3.12). Owned by track S (store, import, shadow);
increment I2. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    CodeResult,
    CreateDecisionResult,
    OptionInput,
    TriggerInput,
    When,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
    Decider,
)

_TODO = "track S: modules/dec/commands/forks.py"


def open_fork(
    env: DecEnv,
    *,
    question: str,
    trigger: TriggerInput | None = None,
    opened: When | None = None,
    decider: Decider = "self",
    decider_ref: str | None = None,
    deadline: date | None = None,
    options: Sequence[OptionInput] = (),
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    raise NotImplementedError(_TODO)


def decide_fork(
    env: DecEnv,
    fork_ref: str,
    *,
    chosen_option: str,
    decision: Mapping[str, object] | None = None,
    activate: bool = False,
    ctx: CommandContext,
) -> CommandResult[CreateDecisionResult]:
    raise NotImplementedError(_TODO)


def dissolve_fork(
    env: DecEnv, fork_ref: str, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def delegate_fork(
    env: DecEnv, fork_ref: str, *, to_ref: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def move_fork_deadline(
    env: DecEnv, fork_ref: str, *, deadline: date, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)
