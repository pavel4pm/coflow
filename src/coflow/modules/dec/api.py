"""DEC's public facade: every command and query of spec §5.2 and §5.3.

Skeleton file (spec §12.1). Outside ``coflow.modules.dec`` only this module (and ``events``) may be
imported (the ``api-only`` contract, ``tests/architecture``). Each function delegates to the file
its track owns; the signatures here are the contract (a change is a reviewed skeleton pull request).

- Every function takes the module's environment first (``DecEnv``: the ports DEC uses). The store is
  the process-wide binding of ``kernel.store.api``; "now" is that store's clock.
- Commands take ``ctx`` (``CommandContext``), run as one unit of work and return
  ``CommandResult[...]`` (value, ``tx``, event ids). ``ctx.expected_version`` carries optimistic
  concurrency; ``ctx.idempotency_key`` makes a retry return the first result.
- Queries have no side effects and return ``Answer[...]`` (value, as-of, axis, coverage, staleness
  and the instance role).
- Errors are the typed errors of ``kernel.errors``; besides ``NotFound`` and ``Conflict`` every
  write on a V1 mirror is ``Refused(MIRRORED)``, naming V1 as the system of record.
- Result and input types are reached through this module too: ``api.model`` (views, computed and
  query results, the waiting-list DTOs) and ``api.inputs`` (command inputs and results).

Increments: I1 builds the queries ``decision_context``, ``list_decisions``, ``waiting``,
``assumption_due``, ``health``, ``integrity``, ``as_of``, ``shadow_report`` and the command
``import_snapshot``. I2 and I3 entries are stubs whose signatures are provisional (see
``domain/inputs.py``).

Spec note: §5.2 writes ``decided_at (+ precision, basis)`` and ``occurred_at?``; here they are one
``When`` argument (``decided``, ``observed``, ``occurred``, ``opened``). ``integrity`` takes a ref
or the literal ``'all'``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

from coflow.kernel.context import Answer, Axis, CommandContext, CommandResult
from coflow.kernel.ports.attachment_probe import DecisionAttachmentProbe, Period
from coflow.kernel.ports.decision_directory import DecisionDirectory, WaitingItem
from coflow.kernel.ports.evidence_resolver import EvidenceResolver
from coflow.kernel.ports.goal_directory import GoalDirectory
from coflow.kernel.ports.undo import UndoEntry, UndoHandler, UndoResult
from coflow.modules.dec import directory as _directory
from coflow.modules.dec import goals_shadow as _goals_shadow
from coflow.modules.dec import queries as _queries
from coflow.modules.dec import queries_reports as _reports
from coflow.modules.dec import undo as _undo
from coflow.modules.dec.commands import assumptions as _assumptions
from coflow.modules.dec.commands import checks as _checks
from coflow.modules.dec.commands import decisions as _decisions
from coflow.modules.dec.commands import facts as _facts
from coflow.modules.dec.commands import flags as _flags
from coflow.modules.dec.commands import forks as _forks
from coflow.modules.dec.commands import links as _links
from coflow.modules.dec.commands import proposals as _proposals
from coflow.modules.dec.commands import readings as _readings
from coflow.modules.dec.commands import reviews as _reviews
from coflow.modules.dec.domain import inputs as inputs
from coflow.modules.dec.domain import model as model
from coflow.modules.dec.domain.inputs import (
    ActivationResult,
    AddAssumptionResult,
    AdoptionResult,
    AssumptionInput,
    CaseLine,
    CaseResult,
    CheckResult,
    CodeResult,
    CreateDecisionResult,
    DraftItem,
    EditionResult,
    EvidenceInput,
    ExpectedInput,
    FactResult,
    ForkLine,
    GroundInput,
    HistoryResult,
    LearningInput,
    LinkInput,
    LinkResult,
    LoopMetrics,
    OptionInput,
    OriginInput,
    OutcomeInput,
    PostponeResult,
    ProposalLine,
    ProposalResult,
    ReadingResult,
    RelatedLearning,
    ReviewResult,
    RevisionInput,
    StakeInput,
    TriggerInput,
    UnlinkedReport,
    UpdateResult,
    When,
)
from coflow.modules.dec.domain.model import (
    AsOfView,
    AssumptionDue,
    Audience,
    Bearing,
    CheckState,
    ClaimedOutcome,
    DecEnv,
    Decider,
    DecisionContext,
    DecisionKind,
    DecisionLine,
    Depth,
    Detail,
    FactKind,
    FactPhase,
    HealthResult,
    ImportMode,
    ImportReport,
    IntegrityReport,
    LinkRole,
    ManualFlag,
    Publishability,
    ReadingSourceKind,
    Reversibility,
    ReviewAction,
    ReviewTrigger,
    ReviseBasis,
    ShadowReport,
)
from coflow.modules.dec.importer import adopt as _adopt
from coflow.modules.dec.importer import project_log as _project_log
from coflow.modules.dec.importer import snapshot as _snapshot
from coflow.modules.dec.shadow import cases as _cases
from coflow.modules.dec.shadow import compare as _compare

__all__ = [
    "DecEnv",
    "activate_decision",
    "add_assumption",
    "add_fact",
    "add_option",
    "adopt_mirrors",
    "approve_proposal",
    "as_of",
    "assumption_due",
    "cases",
    "complete_decision",
    "correct_fact",
    "create_decision",
    "decide_fork",
    "decision_context",
    "decision_history",
    "default_env",
    "delegate_fork",
    "directory",
    "dissolve_fork",
    "drafts_to_finish",
    "drop_assumption",
    "forks",
    "health",
    "import_decision_log",
    "import_snapshot",
    "inputs",
    "integrity",
    "link",
    "list_decisions",
    "loop_metrics",
    "model",
    "move_fork_deadline",
    "open_fork",
    "postpone_check",
    "proposals",
    "propose_decision",
    "record_check",
    "record_reading",
    "reject_proposal",
    "related_learnings",
    "review_decision",
    "run_case",
    "set_manual_flag",
    "set_publishability",
    "shadow_report",
    "supersede_assumption",
    "undo",
    "undo_handler",
    "unlink",
    "unlinked_report",
    "update_decision",
    "waiting",
]


# ==================================================================================================
# Wiring


def default_env(
    *,
    goal_directory: GoalDirectory | None = None,
    attachment_probes: Sequence[DecisionAttachmentProbe] = (),
    evidence_resolvers: Sequence[EvidenceResolver] = (),
) -> DecEnv:
    """DEC's environment; without a goal directory it uses the shadow adapter over mirrored goal
    context (``goals_shadow.py``), as the slice does until WRK implements the port (stage 1)."""
    return DecEnv(
        goal_directory=goal_directory or _goals_shadow.ShadowGoalDirectory(),
        attachment_probes=tuple(attachment_probes),
        evidence_resolvers=tuple(evidence_resolvers),
    )


def directory(env: DecEnv) -> DecisionDirectory:
    """DEC's implementation of the ``DecisionDirectory`` port, for the composition root."""
    return _directory.DecDirectory(env)


def undo_handler(env: DecEnv) -> UndoHandler:
    """DEC's ``UndoHandler`` for its MCP write tools [I2]."""
    return _undo.DecUndoHandler(env)


# ==================================================================================================
# I1: queries


def decision_context(
    env: DecEnv,
    ref: str,
    *,
    detail: Detail = "brief",
    as_of: datetime | None = None,
    axis: Axis = "knowledge",
    audience: Audience = "owner",
) -> Answer[DecisionContext]:
    """The card (§5.3). ``ref`` accepts any input form (``D907``, ``V1_D907``, ``D-0907``)."""
    return _queries.decision_context(
        env, ref, detail=detail, as_of=as_of, axis=axis, audience=audience
    )


def list_decisions(
    env: DecEnv,
    *,
    status: str | None = None,
    kind: str | None = None,
    health: str | None = None,
    linked_to: str | None = None,
    mirror: str | None = None,
    limit: int = 50,
) -> Answer[list[DecisionLine]]:
    """One line per decision: id, title, label, share, review date, first reason (§5.3)."""
    return _queries.list_decisions(
        env,
        status=status,
        kind=kind,
        health=health,
        linked_to=linked_to,
        mirror=mirror,
        limit=limit,
    )


def waiting(
    env: DecEnv, *, today: date | None = None, as_of: datetime | None = None
) -> Answer[list[WaitingItem]]:
    """The waiting list (§3.8), each item with its question context (§3.9).

    ``T.date`` is ``today`` (default: the store clock's owner-zone date); ``T.instant`` is ``as_of``
    (default: the end of ``today`` when ``today`` is given, else now). The shadow passes both.
    """
    return _queries.waiting(env, today=today, as_of=as_of)


def assumption_due(
    env: DecEnv, assumption_ref: str, *, at: datetime | None = None
) -> Answer[AssumptionDue]:
    """``(date, source)`` and the last assessment (§3.6)."""
    return _queries.assumption_due(env, assumption_ref, at=at)


def health(env: DecEnv, ref: str, *, as_of: datetime | None = None) -> Answer[HealthResult]:
    """Label, ground, timeliness, reasons, share and the ``bet`` badge (§3.7)."""
    return _queries.health(env, ref, as_of=as_of)


def integrity(env: DecEnv, ref: str) -> Answer[list[IntegrityReport]]:
    """Per edition ``ok`` / ``ok_with_erasures`` / ``changed``; live drift; completion pending
    (§3.3). ``ref`` is a decision ref or ``'all'``."""
    return _queries.integrity(env, ref)


def as_of(env: DecEnv, ref: str, t: datetime, *, axis: Axis = "knowledge") -> Answer[AsOfView]:
    """The record as known at ``t`` on an axis, with what v2 computes at ``t`` (§3.15)."""
    return _queries.as_of(env, ref, t, axis=axis)


def shadow_report(env: DecEnv, *, run_id: int | None = None) -> Answer[ShadowReport]:
    """The shadow comparison of a run (default: the latest) (§6.6)."""
    return _compare.shadow_report(env, run_id=run_id)


# ==================================================================================================
# I1: command


def import_snapshot(
    env: DecEnv, file: Path, *, mode: ImportMode = "shadow", ctx: CommandContext
) -> CommandResult[ImportReport]:
    """Import a ``coflow.import.decisions`` v1 snapshot (§6.5): validation role, or synthetic files
    in a dev instance. The same file twice is a no-op."""
    return _snapshot.import_snapshot(env, file, mode=mode, ctx=ctx)


# ==================================================================================================
# I2: commands (provisional signatures)


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
    return _decisions.create_decision(
        env,
        title=title,
        question=question,
        statement=statement,
        kind=kind,
        decider=decider,
        decider_ref=decider_ref,
        depth=depth,
        reversibility=reversibility,
        context=context,
        known=known,
        unknowns=unknowns,
        would_help=would_help,
        success_criterion=success_criterion,
        expected=expected,
        confidence=confidence,
        stakes=stakes,
        not_doing=not_doing,
        review_due=review_due,
        decided=decided,
        origin=origin,
        options=options,
        grounds=grounds,
        assumptions=assumptions,
        links=links,
        publishability=publishability,
        third_party_sensitive=third_party_sensitive,
        activate=activate,
        ctx=ctx,
    )


def update_decision(
    env: DecEnv,
    ref: str,
    *,
    fields: Mapping[str, object],
    reason: str | None = None,
    ctx: CommandContext,
) -> CommandResult[UpdateResult]:
    return _decisions.update_decision(env, ref, fields=fields, reason=reason, ctx=ctx)


def activate_decision(
    env: DecEnv,
    ref: str,
    *,
    chosen_option: str | None = None,
    decided: When | None = None,
    ctx: CommandContext,
) -> CommandResult[ActivationResult]:
    return _decisions.activate_decision(
        env, ref, chosen_option=chosen_option, decided=decided, ctx=ctx
    )


def complete_decision(
    env: DecEnv, ref: str, *, ctx: CommandContext
) -> CommandResult[EditionResult]:
    return _decisions.complete_decision(env, ref, ctx=ctx)


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
    return _decisions.add_option(
        env,
        decision_ref=decision_ref,
        fork_ref=fork_ref,
        text=text,
        chosen=chosen,
        why_rejected=why_rejected,
        ctx=ctx,
    )


def add_assumption(
    env: DecEnv, ref: str, *, assumption: AssumptionInput, ctx: CommandContext
) -> CommandResult[AddAssumptionResult]:
    return _assumptions.add_assumption(env, ref, assumption=assumption, ctx=ctx)


def supersede_assumption(
    env: DecEnv,
    assumption_ref: str,
    *,
    changes: Mapping[str, object],
    reason: str,
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    return _assumptions.supersede_assumption(
        env, assumption_ref, changes=changes, reason=reason, ctx=ctx
    )


def drop_assumption(
    env: DecEnv, assumption_ref: str, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _assumptions.drop_assumption(env, assumption_ref, reason=reason, ctx=ctx)


def record_check(
    env: DecEnv,
    assumption_ref: str,
    *,
    state: CheckState,
    observed_value: str | None = None,
    observed_text: str | None = None,
    observed: When | None = None,
    evidence: EvidenceInput | None = None,
    note: str | None = None,
    next_check_at: date | None = None,
    accept_reading: str | None = None,
    ctx: CommandContext,
) -> CommandResult[CheckResult]:
    return _checks.record_check(
        env,
        assumption_ref,
        state=state,
        observed_value=observed_value,
        observed_text=observed_text,
        observed=observed,
        evidence=evidence,
        note=note,
        next_check_at=next_check_at,
        accept_reading=accept_reading,
        ctx=ctx,
    )


def record_reading(
    env: DecEnv,
    assumption_ref: str,
    *,
    value: str | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    observed: When | None = None,
    source_kind: ReadingSourceKind = "owner_statement",
    source_ref: str | None = None,
    quote: str | None = None,
    ctx: CommandContext,
) -> CommandResult[ReadingResult]:
    return _readings.record_reading(
        env,
        assumption_ref,
        value=value,
        value_text=value_text,
        unit=unit,
        observed=observed,
        source_kind=source_kind,
        source_ref=source_ref,
        quote=quote,
        ctx=ctx,
    )


def postpone_check(
    env: DecEnv, assumption_ref: str, *, until: date, reason: str, ctx: CommandContext
) -> CommandResult[PostponeResult]:
    return _checks.postpone_check(env, assumption_ref, until=until, reason=reason, ctx=ctx)


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
    return _facts.add_fact(
        env,
        ref,
        text=text,
        phase=phase,
        kind=kind,
        claimed_outcome=claimed_outcome,
        occurred=occurred,
        evidence=evidence,
        assumption_refs=assumption_refs,
        bearing=bearing,
        ctx=ctx,
    )


def correct_fact(
    env: DecEnv, fact_ref: str, *, text: str, reason: str, ctx: CommandContext
) -> CommandResult[FactResult]:
    return _facts.correct_fact(env, fact_ref, text=text, reason=reason, ctx=ctx)


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
    return _reviews.review_decision(
        env,
        ref,
        action,
        verdict=verdict,
        notes=notes,
        next_review_due=next_review_due,
        trigger=trigger,
        trigger_ref=trigger_ref,
        revision=revision,
        revise_basis=revise_basis,
        is_correction=is_correction,
        outcome=outcome,
        learning=learning,
        successor_ref=successor_ref,
        occurred=occurred,
        ctx=ctx,
    )


def set_manual_flag(
    env: DecEnv, ref: str, flag: ManualFlag | None, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _flags.set_manual_flag(env, ref, flag, reason=reason, ctx=ctx)


def set_publishability(
    env: DecEnv, ref: str, value: Publishability, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _flags.set_publishability(env, ref, value, reason=reason, ctx=ctx)


def link(
    env: DecEnv,
    ref: str,
    role: LinkRole,
    target_ref: str,
    *,
    note: str | None = None,
    ctx: CommandContext,
) -> CommandResult[LinkResult]:
    return _links.link(env, ref, role, target_ref, note=note, ctx=ctx)


def unlink(env: DecEnv, link_id: int, *, reason: str, ctx: CommandContext) -> CommandResult[None]:
    return _links.unlink(env, link_id, reason=reason, ctx=ctx)


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
    return _forks.open_fork(
        env,
        question=question,
        trigger=trigger,
        opened=opened,
        decider=decider,
        decider_ref=decider_ref,
        deadline=deadline,
        options=options,
        ctx=ctx,
    )


def decide_fork(
    env: DecEnv,
    fork_ref: str,
    *,
    chosen_option: str,
    decision: Mapping[str, object] | None = None,
    activate: bool = False,
    ctx: CommandContext,
) -> CommandResult[CreateDecisionResult]:
    return _forks.decide_fork(
        env, fork_ref, chosen_option=chosen_option, decision=decision, activate=activate, ctx=ctx
    )


def dissolve_fork(
    env: DecEnv, fork_ref: str, *, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _forks.dissolve_fork(env, fork_ref, reason=reason, ctx=ctx)


def delegate_fork(
    env: DecEnv, fork_ref: str, *, to_ref: str, ctx: CommandContext
) -> CommandResult[None]:
    return _forks.delegate_fork(env, fork_ref, to_ref=to_ref, ctx=ctx)


def move_fork_deadline(
    env: DecEnv, fork_ref: str, *, deadline: date, ctx: CommandContext
) -> CommandResult[None]:
    return _forks.move_fork_deadline(env, fork_ref, deadline=deadline, ctx=ctx)


def undo(env: DecEnv, undo_entry: UndoEntry, *, ctx: CommandContext) -> CommandResult[UndoResult]:
    return _undo.undo(env, undo_entry, ctx=ctx)


def import_decision_log(
    env: DecEnv, file: Path, *, only: Sequence[str], ctx: CommandContext
) -> CommandResult[ImportReport]:
    """The project's decision log, selected entries only (§6.8)."""
    return _project_log.import_decision_log(env, file, only=only, ctx=ctx)


# ==================================================================================================
# I3: commands (provisional signatures)


def propose_decision(
    env: DecEnv, *, payload: Mapping[str, object], origin: OriginInput, ctx: CommandContext
) -> CommandResult[ProposalResult]:
    return _proposals.propose_decision(env, payload=payload, origin=origin, ctx=ctx)


def approve_proposal(
    env: DecEnv,
    proposal_id: int,
    *,
    edits: Mapping[str, object] | None = None,
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    """Owner channel only: an MCP call can never approve (``OWNER_CHANNEL_REQUIRED``, P-4)."""
    return _proposals.approve_proposal(env, proposal_id, edits=edits, ctx=ctx)


def reject_proposal(
    env: DecEnv, proposal_id: int, *, reject_class: str, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    return _proposals.reject_proposal(
        env, proposal_id, reject_class=reject_class, reason=reason, ctx=ctx
    )


def run_case(env: DecEnv, case_file: Path, *, ctx: CommandContext) -> CommandResult[CaseResult]:
    """A real case on a throw-away copy of the validation database (§6.7)."""
    return _cases.run_case(env, case_file, ctx=ctx)


def adopt_mirrors(
    env: DecEnv, *, issuer: str, confirm_phrase: str, ctx: CommandContext
) -> CommandResult[AdoptionResult]:
    """The adoption gate enforced in code (§6.10): ``ADOPTION_GATE`` names every missing
    condition."""
    return _adopt.adopt_mirrors(env, issuer=issuer, confirm_phrase=confirm_phrase, ctx=ctx)


# ==================================================================================================
# I2 and I3: queries (provisional signatures)


def drafts_to_finish(env: DecEnv, *, today: date | None = None) -> Answer[list[DraftItem]]:
    return _queries.drafts_to_finish(env, today=today)


def related_learnings(
    env: DecEnv,
    *,
    kind: str | None = None,
    subjects: Sequence[str] = (),
    class_tags: Sequence[str] = (),
) -> Answer[list[RelatedLearning]]:
    return _queries.related_learnings(env, kind=kind, subjects=subjects, class_tags=class_tags)


def forks(env: DecEnv, *, status: str | None = None) -> Answer[list[ForkLine]]:
    return _queries.forks(env, status=status)


def decision_history(env: DecEnv, scope: str, period: Period) -> Answer[HistoryResult]:
    return _reports.decision_history(env, scope, period)


def proposals(
    env: DecEnv, *, status: str | None = None, origin_kind: str | None = None
) -> Answer[list[ProposalLine]]:
    return _proposals.list_proposals(env, status=status, origin_kind=origin_kind)


def unlinked_report(env: DecEnv, period: Period) -> Answer[UnlinkedReport]:
    return _reports.unlinked_report(env, period)


def loop_metrics(env: DecEnv, period: Period) -> Answer[LoopMetrics]:
    return _reports.loop_metrics(env, period)


def cases(env: DecEnv) -> Answer[list[CaseLine]]:
    return _cases.list_cases(env)
