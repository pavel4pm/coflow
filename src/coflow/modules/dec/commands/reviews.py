"""Reviews, revisions, corrections, completion, outcome and learning (spec §3.10, §3.11). Owned by
track S (store, import, shadow); increment I2. The signatures are the targets of ``dec.api`` and
are fixed by the facade (provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    LearningInput,
    OutcomeInput,
    ReviewResult,
    RevisionInput,
    When,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
    ReviewAction,
    ReviewTrigger,
    ReviseBasis,
)

_TODO = "track S: modules/dec/commands/reviews.py"


def review_decision(
    env: DecEnv,
    ref: str,
    action: ReviewAction,
    *,
    verdict: str | None = None,
    notes: str | None = None,
    next_review_due: date | None = None,
    trigger: ReviewTrigger | None = None,
    trigger_ref: str | None = None,
    revision: RevisionInput | None = None,
    revise_basis: ReviseBasis | None = None,
    is_correction: bool = False,
    outcome: OutcomeInput | None = None,
    learning: LearningInput | None = None,
    successor_ref: str | None = None,
    occurred: When | None = None,
    ctx: CommandContext,
) -> CommandResult[ReviewResult]:
    raise NotImplementedError(_TODO)
