"""Facts: grounds and monitoring, outcome reports (spec §5.2). Owned by track S (store, import,
shadow); increment I2. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Sequence

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    EvidenceInput,
    FactResult,
    When,
)
from coflow.modules.dec.domain.model import (
    Bearing,
    ClaimedOutcome,
    DecEnv,
    FactKind,
    FactPhase,
)

_TODO = "track S: modules/dec/commands/facts.py"


def add_fact(
    env: DecEnv,
    ref: str,
    *,
    text: str,
    phase: FactPhase = "monitoring",
    kind: FactKind = "observation",
    claimed_outcome: ClaimedOutcome | None = None,
    occurred: When | None = None,
    evidence: EvidenceInput | None = None,
    assumption_refs: Sequence[str] = (),
    bearing: Bearing = "bears_on",
    ctx: CommandContext,
) -> CommandResult[FactResult]:
    raise NotImplementedError(_TODO)


def correct_fact(
    env: DecEnv, fact_ref: str, *, text: str, reason: str, ctx: CommandContext
) -> CommandResult[FactResult]:
    raise NotImplementedError(_TODO)
