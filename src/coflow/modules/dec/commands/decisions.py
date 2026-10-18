"""Decision commands (spec §5.2, §3.1, §3.2). Owned by track S (store, import, shadow); increment
I2. The signatures are the targets of ``dec.api`` and are fixed by the facade (provisional until
the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    ActivationResult,
    AssumptionInput,
    CodeResult,
    CreateDecisionResult,
    EditionResult,
    ExpectedInput,
    GroundInput,
    LinkInput,
    OptionInput,
    OriginInput,
    StakeInput,
    UpdateResult,
    When,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
    Decider,
    DecisionKind,
    Depth,
    Publishability,
    Reversibility,
)

_TODO = "track S: modules/dec/commands/decisions.py"


def create_decision(
    env: DecEnv,
    *,
    title: str,
    question: str | None = None,
    statement: str | None = None,
    kind: DecisionKind = "choice",
    decider: Decider = "self",
    decider_ref: str | None = None,
    depth: Depth | None = None,
    reversibility: Reversibility = "unknown",
    context: str | None = None,
    known: str | None = None,
    unknowns: Sequence[str] = (),
    would_help: str | None = None,
    success_criterion: str | None = None,
    expected: ExpectedInput | None = None,
    confidence: int | None = None,
    stakes: Sequence[StakeInput] = (),
    not_doing: str | None = None,
    review_due: date | None = None,
    decided: When | None = None,
    origin: OriginInput | None = None,
    options: Sequence[OptionInput] = (),
    grounds: Sequence[GroundInput] = (),
    assumptions: Sequence[AssumptionInput] = (),
    links: Sequence[LinkInput] = (),
    publishability: Publishability = "private",
    third_party_sensitive: bool | None = None,
    activate: bool = False,
    ctx: CommandContext,
) -> CommandResult[CreateDecisionResult]:
    raise NotImplementedError(_TODO)


def update_decision(
    env: DecEnv,
    ref: str,
    *,
    fields: Mapping[str, object],
    reason: str | None = None,
    ctx: CommandContext,
) -> CommandResult[UpdateResult]:
    raise NotImplementedError(_TODO)


def activate_decision(
    env: DecEnv,
    ref: str,
    *,
    chosen_option: str | None = None,
    decided: When | None = None,
    ctx: CommandContext,
) -> CommandResult[ActivationResult]:
    raise NotImplementedError(_TODO)


def complete_decision(
    env: DecEnv, ref: str, *, ctx: CommandContext
) -> CommandResult[EditionResult]:
    raise NotImplementedError(_TODO)


def add_option(
    env: DecEnv,
    *,
    decision_ref: str | None = None,
    fork_ref: str | None = None,
    text: str,
    chosen: bool = False,
    why_rejected: str | None = None,
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    raise NotImplementedError(_TODO)
