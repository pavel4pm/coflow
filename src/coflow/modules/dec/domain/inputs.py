"""Inputs and results of DEC commands (spec §5.2), used by the facade signatures of ``dec.api``.

Skeleton file (spec §12.1). Only ``import_snapshot`` is built in I1; the DTOs of I2 and I3 are
**provisional**: the I2 and I3 skeleton reviews may refine them before those tracks start. A change
is a reviewed skeleton pull request (spec §12.5).

Spec note: an argument that §5.2 writes as ``x{a,b,c}`` is a frozen dataclass here (``OriginInput``,
``ThresholdInput``, ...). An event time an owner states is a ``When``; ``None`` where §5.2 says
"default live" means the command's own instant (basis ``live``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from coflow.modules.dec.domain.model import (
    Comparator,
    DataSourceKind,
    DecisionStatus,
    Depth,
    DueResult,
    EvidenceKind,
    HealthResult,
    LinkResolution,
    LinkRole,
    NoProposalReason,
    OriginKind,
    OutcomeBasis,
    OutcomeKind,
    Precision,
    ProposedState,
    SameAgain,
    StakeDirection,
    StakePeriod,
    StakeType,
    TimeBasis,
)

__all__ = [
    "ActivationResult",
    "AddAssumptionResult",
    "AdoptionResult",
    "AssumptionInput",
    "CaseLine",
    "CaseResult",
    "CheckResult",
    "CodeResult",
    "CreateDecisionResult",
    "DataSourceInput",
    "DraftItem",
    "EditionResult",
    "EvidenceInput",
    "ExpectedInput",
    "FactResult",
    "ForkLine",
    "GroundInput",
    "HistoryResult",
    "LearningInput",
    "LinkInput",
    "LinkResult",
    "LoopMetrics",
    "OptionInput",
    "OriginInput",
    "OutcomeInput",
    "PostponeResult",
    "ProposalLine",
    "ProposalResult",
    "ReadingResult",
    "RelatedLearning",
    "ReviewResult",
    "RevisionInput",
    "StakeInput",
    "ThresholdInput",
    "TriggerInput",
    "UnlinkedReport",
    "UpdateResult",
    "When",
]

# ==================================================================================================
# Inputs


@dataclass(frozen=True, slots=True, kw_only=True)
class When:
    """An event time as the caller states it (§2.1): never defaulted silently to a record time."""

    at: datetime | date | None
    precision: Precision
    basis: TimeBasis = "stated"


@dataclass(frozen=True, slots=True, kw_only=True)
class OriginInput:
    """``origin{kind,ref,quote}``. Over MCP an empty ``quote`` is refused
    (``OWNER_QUOTE_REQUIRED``)."""

    kind: OriginKind
    ref: str | None = None
    quote: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpectedInput:
    metric: str | None = None
    target: str | None = None
    unit: str | None = None
    by: date | None = None
    text: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceInput:
    kind: EvidenceKind
    ref: str | None = None
    quote: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ThresholdInput:
    """``threshold{comparator,value,value2,unit,by_date,text}``; values are decimal strings."""

    comparator: Comparator | None = None
    value: str | None = None
    value2: str | None = None
    unit: str | None = None
    by_date: date | None = None
    text: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSourceInput:
    """``data_source{kind,text,ref}``; kind ``none`` records honestly that nothing can check it."""

    kind: DataSourceKind
    text: str | None = None
    ref: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionInput:
    text: str
    chosen: bool = False
    why_rejected: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GroundInput:
    text: str
    occurred: When | None = None
    evidence: EvidenceInput | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssumptionInput:
    statement: str
    data_source: DataSourceInput
    metric: str | None = None
    threshold: ThresholdInput | None = None
    judge_from: date | None = None
    frequency: Literal["weekly", "monthly", "quarterly", "ad_hoc"] | None = None
    next_check_at: date | None = None
    critical: bool = True
    scope: str | None = None
    check_cost: Literal["minutes", "hours", "day_plus", "unknown"] | None = None
    class_tag: str | None = None
    probability: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StakeInput:
    type: StakeType
    amount: str | None = None
    currency: str | None = None
    period: StakePeriod | None = None
    count_periods: int | None = None
    direction: StakeDirection | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkInput:
    role: LinkRole
    target_ref: str
    note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TriggerInput:
    text: str | None = None
    ref: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class OutcomeInput:
    kind: OutcomeKind
    basis: OutcomeBasis
    evidence_refs: tuple[str, ...] = ()
    measured_value: str | None = None
    expected_vs_actual: str | None = None
    owner_statement: str | None = None
    occurred: When | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningInput:
    confirmed: str | None = None
    refuted: str | None = None
    limits: str | None = None
    next_step: str | None = None
    same_again: SameAgain | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RevisionInput:
    """What a revise changes (§3.10): basis fields set, assumptions superseded, items appended."""

    fields: Mapping[str, object] = field(default_factory=dict)
    add_options: tuple[OptionInput, ...] = ()
    add_grounds: tuple[GroundInput, ...] = ()
    add_assumptions: tuple[AssumptionInput, ...] = ()
    supersede_assumptions: Mapping[str, AssumptionInput] = field(default_factory=dict)
    add_stakes: tuple[StakeInput, ...] = ()


# ==================================================================================================
# Command results


@dataclass(frozen=True, slots=True, kw_only=True)
class RelatedLearning:
    """A learning of an earlier closed or cancelled decision shown to a new one (§3.11)."""

    ref: str  # "D-0031_L-01"
    decision_ref: str
    matched: tuple[str, ...]  # 'kind', 'about', 'serves', 'class_tag'
    fate: str  # "2 of 3 earlier demand assumptions were violated"


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDecisionResult:
    public_id: str
    status: DecisionStatus
    missing_for_activation: tuple[str, ...]
    advisory: tuple[str, ...]
    proposed_depth: Depth
    related_learnings: tuple[RelatedLearning, ...] = ()
    follows_candidates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateResult:
    changed: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivationResult:
    edition: int
    seal: str  # 12 hex characters
    health: HealthResult
    related_learnings: tuple[RelatedLearning, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class EditionResult:
    edition: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeResult:
    code: str
    ref: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AddAssumptionResult:
    code: str
    ref: str
    due: DueResult
    added_after_seal: bool
    completion_pending: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckResult:
    check_ref: str
    next_due: DueResult
    decision_state: HealthResult
    review_now: bool = False  # set when the check recorded VIOLATED


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingResult:
    reading_ref: str
    proposed_state: ProposedState | None
    no_proposal_reason: NoProposalReason | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PostponeResult:
    next_due: date


@dataclass(frozen=True, slots=True, kw_only=True)
class FactResult:
    fact_ref: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewResult:
    review_ref: str
    status: DecisionStatus
    edition: int
    health: HealthResult


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkResult:
    link_id: int
    resolution: LinkResolution


@dataclass(frozen=True, slots=True, kw_only=True)
class ProposalResult:
    proposal_id: int
    match_candidates: tuple[Mapping[str, str], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseResult:
    case_id: str
    result: Literal["pass", "fail"]
    source_run_id: int | None
    failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class AdoptionResult:
    issuer: str
    adopted: int
    next_native_number: int


# ==================================================================================================
# Query results of I2 and I3


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftItem:
    decision_ref: str
    title: str
    missing: tuple[str, ...]
    age_days: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ForkLine:
    fork_ref: str
    question: str
    status: str
    age_days: int
    deadline: date | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProposalLine:
    proposal_id: int
    type: str
    title: str
    origin_kind: str
    status: str
    approval_rate: Decimal | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseLine:
    case_id: str
    title: str
    last_result: Literal["pass", "fail"] | None
    last_run_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryResult:
    """``decision_history`` (§3.15): state changes with their preceding evidence and following
    actions and reviews, sealed editions after E-01, outcomes, and a coverage note."""

    changes: tuple[Mapping[str, object], ...]
    outcomes: tuple[str, ...]
    coverage: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnlinkedReport:
    """``unlinked_report`` (§3.14)."""

    by_kind: tuple[Mapping[str, object], ...]
    shares: Mapping[str, Decimal | None]
    goal_only: int
    decisions_without_execution: tuple[str, ...]
    decisions_without_goal: tuple[str, ...]
    decisions_without_origin: tuple[str, ...]
    voids: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True, kw_only=True)
class LoopMetrics:
    """``loop_metrics`` (§3.16): metric name -> value, each split as the spec's table says."""

    values: Mapping[str, object]
    period_start: datetime
    period_end: datetime
