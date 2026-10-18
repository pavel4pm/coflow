"""CMT commands (spec §5.4): create, change status, shift the due date, link.

Owned by track C (commitments, K's agent); increment I3, spec §12.4. The signatures are the targets
of ``cmt.api`` (provisional until the I3 skeleton review); the track implements them.
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.cmt.model import (
    CmtEnv,
    CommitmentResult,
    CommitmentStatus,
    DoneAt,
    DueBasis,
    NoDecisionReason,
)

__all__ = [
    "change_commitment_status",
    "create_commitment",
    "link_commitment",
    "shift_commitment_due",
]

_TODO = "track C: modules/cmt/commands.py"


def create_commitment(
    env: CmtEnv,
    *,
    debtor_ref: str,
    creditor_ref: str,
    what: str,
    due_basis: DueBasis,
    success_criterion: str | None = None,
    due_date: date | None = None,
    decision_ref: str | None = None,
    no_decision_reason: NoDecisionReason | None = None,
    goal_ref: str | None = None,
    source_ref: str | None = None,
    source_quote: str | None = None,
    ctx: CommandContext,
) -> CommandResult[CommitmentResult]:
    raise NotImplementedError(_TODO)


def change_commitment_status(
    env: CmtEnv,
    ref: str,
    to: CommitmentStatus,
    *,
    reason: str | None = None,
    done_at: DoneAt | None = None,
    ctx: CommandContext,
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def shift_commitment_due(
    env: CmtEnv, ref: str, *, new_due: date | None, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def link_commitment(
    env: CmtEnv,
    ref: str,
    *,
    decision_ref: str | None = None,
    no_decision_reason: NoDecisionReason | None = None,
    ctx: CommandContext,
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)
