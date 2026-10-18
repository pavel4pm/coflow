"""CMT's public facade: the commands and queries of spec §5.4 [I3].

Skeleton file (spec §12.1); signatures provisional until the I3 skeleton review, when track C takes
the file over (§12.4). Conventions are DEC's (``modules/dec/api.py``): the environment first,
``ctx`` for commands, ``CommandResult`` / ``Answer``, typed errors. CMT reaches decisions only
through ``CmtEnv.decision_directory`` (``accepts_attachment`` refusals ``DECISION_ENDED`` and
``MIRRORED`` pass through unchanged).
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.context import Answer, CommandContext, CommandResult
from coflow.kernel.ports.attachment_probe import DecisionAttachmentProbe
from coflow.kernel.ports.decision_directory import DecisionDirectory
from coflow.kernel.ports.goal_directory import GoalDirectory
from coflow.modules.cmt import commands as _commands
from coflow.modules.cmt import model as model
from coflow.modules.cmt import probe as _probe
from coflow.modules.cmt import queries as _queries
from coflow.modules.cmt.model import (
    CmtEnv,
    CommitmentLine,
    CommitmentResult,
    CommitmentStatus,
    CommitmentView,
    DoneAt,
    DueBasis,
    NoDecisionReason,
)

__all__ = [
    "CmtEnv",
    "change_commitment_status",
    "commitment",
    "create_commitment",
    "default_env",
    "link_commitment",
    "model",
    "open_commitments",
    "probe",
    "shift_commitment_due",
]


def default_env(
    *, decision_directory: DecisionDirectory, goal_directory: GoalDirectory | None = None
) -> CmtEnv:
    return CmtEnv(decision_directory=decision_directory, goal_directory=goal_directory)


def probe(env: CmtEnv) -> DecisionAttachmentProbe:
    """CMT's ``DecisionAttachmentProbe`` (kind ``commitment``), for the composition root."""
    return _probe.CommitmentProbe(env)


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
    """Neither ``decision_ref`` nor ``no_decision_reason`` stores ``link_answer = unanswered``."""
    return _commands.create_commitment(
        env,
        debtor_ref=debtor_ref,
        creditor_ref=creditor_ref,
        what=what,
        due_basis=due_basis,
        success_criterion=success_criterion,
        due_date=due_date,
        decision_ref=decision_ref,
        no_decision_reason=no_decision_reason,
        goal_ref=goal_ref,
        source_ref=source_ref,
        source_quote=source_quote,
        ctx=ctx,
    )


def change_commitment_status(
    env: CmtEnv,
    ref: str,
    to: CommitmentStatus,
    *,
    reason: str | None = None,
    done_at: DoneAt | None = None,
    ctx: CommandContext,
) -> CommandResult[None]:
    return _commands.change_commitment_status(env, ref, to, reason=reason, done_at=done_at, ctx=ctx)


def shift_commitment_due(
    env: CmtEnv, ref: str, *, new_due: date | None, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _commands.shift_commitment_due(env, ref, new_due=new_due, reason=reason, ctx=ctx)


def link_commitment(
    env: CmtEnv,
    ref: str,
    *,
    decision_ref: str | None = None,
    no_decision_reason: NoDecisionReason | None = None,
    ctx: CommandContext,
) -> CommandResult[None]:
    return _commands.link_commitment(
        env, ref, decision_ref=decision_ref, no_decision_reason=no_decision_reason, ctx=ctx
    )


def open_commitments(
    env: CmtEnv,
    *,
    debtor: str | None = None,
    creditor: str | None = None,
    decision_ref: str | None = None,
    due_before: date | None = None,
) -> Answer[list[CommitmentLine]]:
    return _queries.open_commitments(
        env, debtor=debtor, creditor=creditor, decision_ref=decision_ref, due_before=due_before
    )


def commitment(env: CmtEnv, ref: str) -> Answer[CommitmentView]:
    return _queries.commitment(env, ref)
