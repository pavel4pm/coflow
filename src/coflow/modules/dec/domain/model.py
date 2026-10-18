"""DEC's frozen views, computed results and configuration: the contract between tracks D, S and X.

Skeleton file (spec §12.1). Track S assembles the views from rows (``modules/dec/store/repo.py``),
track D computes over them (``domain/*.py``, ``queries.py``), track X renders the results. A change
is a reviewed skeleton pull request (spec §12.5).

Representation rules:

- Instants are aware UTC ``datetime``; local dates are ``date``; decimals stay decimal **strings**
  exactly as stored (``threshold_value='150'``): code compares them as ``Decimal``.
- An event time is three fields named after the column: ``<x>_at``, ``<x>_precision`` and
  ``<x>_basis``. ``<x>_at`` is a ``datetime`` for precision ``instant``, a ``date`` for ``day``, the
  first day of the month for ``month``, and ``None`` for ``unknown``.
- Views hold **every** row of a decision, voided and later rows included. Visibility at ``T`` on an
  axis (§3.15) is track D's filter, so one loaded view answers any as-of question.
- ``stored`` holds the row's column values exactly as SQLite returned them (``str | int | None``).
  It is the only input of hashing (seals and integrity, §3.3), so a seal made at import (track S)
  and the integrity check (track D) hash the same bytes.
- ``code`` is the scoped code within its parent (``A-03``, ``CK-002``); ``ref`` is the full
  canonical reference (``D-0042_A-03_CK-002``).

The waiting-list DTOs (``Reason``, ``QuestionContext``, ``WaitingItem``) and ``GoalState`` are the
port DTOs of ``kernel.ports`` and are re-exported here, so the CLI, MCP and the ports share one
type.

Spec notes:

- ``dec_decisions`` (§2.4) lists ``origin_ref`` both as the common [O] column and as the "decided
  in" reference. The table has one column; it holds the "decided in" ref (``V1_S90001`` for a mirror
  whose v1 record names a session, §6.3). A mirror's own source id is ``mirror_of``.
- ``dec_forks`` has no ``number`` column; ``ForkView.number`` is the counter of its public id.
- ``HealthResult`` carries the per-assumption effective states and the pool, because the shadow
  rules of §6.6 are conditions on v2's own computed values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from coflow.kernel.ports.attachment_probe import AttachmentSummary, DecisionAttachmentProbe
from coflow.kernel.ports.decision_directory import (
    AskedPart,
    DecisionState,
    FactLine,
    GoalLine,
    QuestionContext,
    Reason,
    SubjectKind,
    WaitingItem,
    WaitingKind,
)
from coflow.kernel.ports.evidence_resolver import EvidenceResolver
from coflow.kernel.ports.goal_directory import GoalDirectory, GoalState

__all__ = [
    "AsOfView",
    "AskedPart",
    "AssumptionCard",
    "AssumptionDue",
    "AssumptionState",
    "AssumptionView",
    "Audience",
    "CheckState",
    "CheckView",
    "DecConfig",
    "DecEnv",
    "DecisionContext",
    "DecisionLine",
    "DecisionState",
    "DecisionStatus",
    "DecisionView",
    "Detail",
    "DueResult",
    "EditionView",
    "EntityCounts",
    "EventAt",
    "FactBearing",
    "FactLine",
    "FactView",
    "ForkView",
    "GoalChange",
    "GoalLine",
    "GoalState",
    "HealthLabel",
    "HealthReason",
    "HealthResult",
    "ImportMode",
    "ImportReport",
    "ImportRunView",
    "IntegrityLine",
    "IntegrityReport",
    "LearningView",
    "LinkView",
    "NextCheck",
    "OptionView",
    "OutcomeView",
    "ProposalView",
    "QuestionContext",
    "ReadingView",
    "Reason",
    "ReviewView",
    "RowStamp",
    "ShadowItem",
    "ShadowReport",
    "StakeView",
    "SubjectKind",
    "VersionView",
    "WaitingItem",
    "WaitingKind",
]

# ==================================================================================================
# Enumerations (Appendix A of the spec). Plain string literals: the stored values.

DecisionStatus = Literal["draft", "active", "closed", "cancelled", "superseded", "withdrawn"]
TERMINAL_STATUSES: frozenset[str] = frozenset({"closed", "cancelled", "superseded", "withdrawn"})
DecisionKind = Literal["choice", "test", "pursue", "attendance", "advisee", "forecast_container"]
MIRROR_ONLY_KINDS: frozenset[str] = frozenset({"advisee", "forecast_container"})
Decider = Literal["self", "joint", "other"]
DeciderBasis = Literal["stated", "mapped", "assumed"]
Depth = Literal["light", "full"]
DepthBasis = Literal["computed", "owner", "import"]
Reversibility = Literal["cheap", "costly", "irreversible", "unknown"]
ManualFlag = Literal["ZOMBIE", "OFF_TRACK"]
OriginKind = Literal[
    "owner_note",
    "cli",
    "bot",
    "meeting",
    "session",
    "chat",
    "agent_session",
    "occasion",
    "app",
    "proposal",
    "fork",
    "import",
    "not_recorded",
]
Publishability = Literal["private", "publishable_abstracted", "public"]
MirrorScope = Literal["full", "basis_only"]
EditionReason = Literal[
    "activation", "revise", "correction", "completion", "import", "source_changed"
]

CheckState = Literal["HOLDING", "DRIFTING", "VIOLATED", "UNVERIFIABLE", "UNKNOWN"]
"""Stored by owner-approved assessments (§3.4)."""
AssumptionState = Literal[
    "HOLDING", "DRIFTING", "VIOLATED", "UNVERIFIABLE", "UNKNOWN", "NOT_YET_DUE", "UNCHECKED"
]
"""Effective states: the stored ones plus the computed ``NOT_YET_DUE`` and ``UNCHECKED``."""
CheckKind = Literal["assessment", "postponement"]
NextCheckRule = Literal[
    "explicit", "frequency", "ad_hoc_clear", "kept", "dropped", "none", "postpone", "import"
]
DataSourceKind = Literal["manual", "internal_query", "external_system", "none"]
CheckFrequency = Literal["weekly", "monthly", "quarterly", "ad_hoc"]
Comparator = Literal[">=", "<=", ">", "<", "=", "!=", "between"]
CheckCost = Literal["minutes", "hours", "day_plus", "unknown"]
AssumptionStatus = Literal["active", "superseded", "dropped"]
DueSource = Literal["explicit", "by_date", "text", "review"]
ProposedState = Literal["HOLDING", "DRIFTING", "VIOLATED"]
NoProposalReason = Literal["text_threshold", "before_judge_from", "unit_mismatch", "no_value"]
CheckProposedBy = Literal["owner", "model", "rule", "app", "import"]
ReadingSourceKind = Literal["owner_statement", "internal_query", "app", "document", "import"]
ReadingProposedBy = Literal["owner", "rule", "app", "import"]

Precision = Literal["instant", "day", "month", "unknown"]
TimeBasis = Literal[
    "live", "stated", "source_time", "conversation_date", "record_date", "import", "unknown"
]
EventAt = datetime | date | None
"""An event-time value: see the representation rules in the module docstring."""

FactPhase = Literal["ground", "monitoring"]
FactKind = Literal[
    "observation", "action", "statement", "context_change", "outcome_report", "external_decision"
]
ClaimedOutcome = Literal["success", "failure", "mixed", "done", "not_done"]
EvidenceKind = Literal[
    "segment",
    "message",
    "session",
    "document",
    "owner_statement",
    "agent_session",
    "app_envelope",
    "foreign",
    "none",
]
ReportedBy = Literal["owner", "counterpart", "app", "agent", "import"]
Bearing = Literal["bears_on", "supports", "contradicts"]

ReviewAction = Literal["keep", "adjust", "revise", "close", "cancel", "supersede"]
ReviseBasis = Literal["trigger_fact", "change_of_mind", "correction"]
ReviewTrigger = Literal[
    "scheduled",
    "violated_assumption",
    "outside_fact",
    "non_occurrence",
    "goal_change",
    "fork",
    "owner_initiative",
    "import",
]
OutcomeKind = Literal["success", "failure", "mixed", "unknown"]
OutcomeBasis = Literal["resolved", "reported", "not_confirmed"]
ResolvedBy = Literal["owner", "import"]
SameAgain = Literal["yes", "no", "unsure"]

StakeType = Literal["money", "hours", "attention"]
StakePeriod = Literal["once", "week", "month", "quarter", "year"]
StakeDirection = Literal["cost", "income", "at_risk"]

LinkRole = Literal[
    "follows",
    "supersedes",
    "depends_on",
    "part_of",
    "contradicts",
    "tests",
    "serves",
    "about",
    "informed_by",
    "foreign_attachment",
]
LinkTargetKind = Literal[
    "decision",
    "learning",
    "goal",
    "direction",
    "person",
    "company",
    "foreign_task",
    "foreign_goal",
    "foreign_topic",
    "foreign_session",
]
LinkResolution = Literal["resolved", "foreign", "pending", "dangling"]
OptionOrigin = Literal["owner", "agent", "import", "app"]
RecordedBeforeChoice = Literal["yes", "no", "unknown"]

ForkStatus = Literal["open", "decided", "dissolved", "delegated"]
ProposalType = Literal["decision_new", "fact"]
ProposalStatus = Literal["proposed", "approved", "rejected", "withdrawn", "expired"]
VersionEntity = Literal["decision", "assumption", "fork", "link", "proposal"]
VersionCause = Literal["command", "review", "check", "import", "undo", "adoption"]

GroundValue = Literal[
    "VIOLATED", "INSUFFICIENT", "DRIFTING", "HOLDING", "AWAITING", "NOT_MONITORED", "NO_ASSUMPTIONS"
]
TimelinessKind = Literal[
    "REVIEW_OVERDUE", "NO_REVIEW_DATE", "CHECK_OVERDUE", "NO_DATA_SINCE", "DUE_TODAY", "ON_SCHEDULE"
]
HealthLabel = Literal[
    "DRAFT",
    "ZOMBIE",
    "OFF_TRACK",
    "REVIEW_REQUIRED",
    "STALE",
    "INSUFFICIENT_DATA",
    "WATCH",
    "ON_TRACK",
    "AWAITING_CHECKS",
    "CLOSED",
    "CANCELLED",
    "SUPERSEDED",
    "WITHDRAWN",
]
IntegrityStatus = Literal["ok", "ok_with_erasures", "changed", "drift", "completion_pending"]

ImportMode = Literal["shadow", "final", "dry_run"]
ImportStatus = Literal["applied", "noop", "partial", "refused", "failed"]
ReportStatus = Literal["pending", "written", "blocked"]
ShadowAspect = Literal[
    "health", "waiting_membership", "waiting_reasons", "due", "order", "count", "basis_drift"
]
ShadowClassification = Literal["same", "expected", "unexpected", "finding"]

Audience = Literal["owner", "agent"]
"""Projections of the slice (§4.4); ``event_app``, ``live_app``, ``team_tool`` come later."""
Detail = Literal["brief", "full"]

# ==================================================================================================
# Configuration


@dataclass(frozen=True, slots=True, kw_only=True)
class DecConfig:
    """DEC's configuration (spec §2.1 keys), passed explicitly to every computed function.

    Built from ``kernel.config.settings.load_settings`` and the owner profile by ``from_settings``;
    absent keys take the spec's defaults.
    """

    timezone: str
    currency: str = "EUR"
    locale: str = "en"
    issuer: str = "CF"
    foreign_issuers: tuple[str, ...] = ("V1", "CF2LOG")
    drift_margin: Decimal = Decimal("0.15")
    unverifiable_share_limit: Decimal = Decimal("0.5")
    no_data_days: int = 30
    retroactive_days: int = 3
    full_depth_review_days: int = 30
    full_depth_money_threshold: Decimal | None = None
    review_step_days: int = 30
    postpone_max_days: int = 90
    undo_window_hours: int = 24
    drafts_stale_days: int = 7
    related_learnings_max: int = 5
    history_window_days: int = 14
    class_tags: tuple[str, ...] = (
        "demand",
        "payment",
        "timeline",
        "people",
        "technical",
        "cost",
        "other",
    )
    proposal_switch_off_share: Decimal = Decimal("0.2")
    proposal_switch_off_window: int = 30
    import_unit_max_rows: int = 5000
    shadow_clean_runs: int = 14
    config_version: str = "1"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def from_settings(cls, settings: Mapping[str, str], *, timezone: str) -> DecConfig:
        """Typed configuration from the stored settings; unknown ``dec.*`` keys are ignored."""
        s = settings

        def dec(key: str, default: Decimal) -> Decimal:
            return Decimal(s[key]) if key in s else default

        def num(key: str, default: int) -> int:
            return int(s[key]) if key in s else default

        def tags(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
            if key not in s:
                return default
            return tuple(t.strip() for t in s[key].split(",") if t.strip())

        base = cls(timezone=timezone)
        threshold = s.get("dec.full_depth_money_threshold")
        switch_off = s.get("dec.proposal_switch_off", "")
        share, _, window = switch_off.partition("/")
        return cls(
            timezone=timezone,
            currency=s.get("owner.currency", base.currency),
            locale=s.get("owner.locale", base.locale),
            issuer=s.get("ids.issuer", base.issuer),
            foreign_issuers=tags("ids.foreign_issuers", base.foreign_issuers),
            drift_margin=dec("dec.drift_margin", base.drift_margin),
            unverifiable_share_limit=dec(
                "dec.unverifiable_share_limit", base.unverifiable_share_limit
            ),
            no_data_days=num("dec.no_data_days", base.no_data_days),
            retroactive_days=num("dec.retroactive_days", base.retroactive_days),
            full_depth_review_days=num("dec.full_depth_review_days", base.full_depth_review_days),
            full_depth_money_threshold=Decimal(threshold) if threshold else None,
            review_step_days=num("dec.review_step_days", base.review_step_days),
            postpone_max_days=num("dec.postpone_max_days", base.postpone_max_days),
            undo_window_hours=num("dec.undo_window_hours", base.undo_window_hours),
            drafts_stale_days=num("dec.drafts_stale_days", base.drafts_stale_days),
            related_learnings_max=num("dec.related_learnings_max", base.related_learnings_max),
            history_window_days=num("dec.history_window_days", base.history_window_days),
            class_tags=tags("dec.class_tags", base.class_tags),
            proposal_switch_off_share=Decimal(share) if share else base.proposal_switch_off_share,
            proposal_switch_off_window=int(window) if window else base.proposal_switch_off_window,
            import_unit_max_rows=num("dec.import_unit_max_rows", base.import_unit_max_rows),
            shadow_clean_runs=num("dec.shadow_clean_runs", base.shadow_clean_runs),
            config_version=s.get("dec.config_version", base.config_version),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecEnv:
    """The ports DEC uses, wired by the composition root (``dec.api.default_env`` in the slice).

    The store is not here: it is the process-wide binding of ``kernel.store.api``, and "now" is that
    store's clock.
    """

    goal_directory: GoalDirectory
    attachment_probes: tuple[DecisionAttachmentProbe, ...] = ()
    evidence_resolvers: tuple[EvidenceResolver, ...] = ()


# ==================================================================================================
# Views: one row each, as stored, plus its children


@dataclass(frozen=True, slots=True, kw_only=True)
class RowStamp:
    """What the store stamped on a row (§2.1), and the row as stored."""

    tx: int
    recorded_at: datetime
    origin_recorded_at: datetime | None = None
    origin_ref: str | None = None
    stored: Mapping[str, str | int | None] = field(default_factory=dict, repr=False, compare=False)

    @property
    def known_at(self) -> datetime:
        """``K(row) = origin_recorded_at if set, else recorded_at``: the knowledge time (§2.1)."""
        return self.origin_recorded_at or self.recorded_at


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionView(RowStamp):
    id: int
    decision_id: int | None
    fork_id: int | None
    code_n: int
    code: str
    ref: str
    text: str
    chosen: bool | None
    why_rejected: str | None
    recorded_before_choice: RecordedBeforeChoice | None
    added_in_edition: int | None
    origin: OptionOrigin
    salt: str
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckView(RowStamp):
    """One check-log row: an owner assessment or a postponement (§2.4 table 6)."""

    id: int
    assumption_id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    kind: CheckKind
    state: CheckState | None
    reading_id: int | None
    observed_value: str | None
    observed_text: str | None
    observed_at: EventAt
    observed_precision: Precision
    observed_basis: TimeBasis
    due_answered: date | None
    due_source_answered: DueSource | None
    next_check_set: date | None
    next_check_rule: NextCheckRule
    evidence_kind: str | None
    evidence_ref: str | None
    evidence_quote: str | None
    quote_verified: bool | None
    note: str | None
    proposed_by: CheckProposedBy
    reconstructed: bool
    voided_at: datetime | None = None
    voided_reason: str | None = None
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingView(RowStamp):
    """A measured value that proposes a state; it never changes one (§3.5)."""

    id: int
    assumption_id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    value: str | None
    unit: str | None
    value_text: str | None
    observed_at: EventAt
    observed_precision: Precision
    observed_basis: TimeBasis
    source_kind: ReadingSourceKind
    source_ref: str | None
    quote: str | None
    proposed_state: ProposedState | None
    no_proposal_reason: NoProposalReason | None
    proposed_by: ReadingProposedBy
    accepted_by_check_id: int | None
    voided_at: datetime | None = None
    voided_reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssumptionView(RowStamp):
    """An assumption with its whole check log and readings (§2.4 table 5). There is no stored state:
    the effective state is computed (§3.4)."""

    id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    position: int
    statement: str
    metric: str | None
    comparator: Comparator | None
    threshold_value: str | None
    threshold_value2: str | None
    unit: str | None
    threshold_text: str | None
    by_date: date | None
    judge_from: date | None
    drift_margin: str | None
    data_source_kind: DataSourceKind
    data_source_text: str | None
    data_source_ref: str | None
    check_frequency: CheckFrequency | None
    next_check_at: date | None
    is_critical: bool
    scope: str | None
    check_cost: CheckCost | None
    class_tag: str | None
    probability: int | None
    probability_by: Literal["owner", "import"] | None
    probability_recorded_at: datetime | None
    shareable: bool
    status: AssumptionStatus
    superseded_by: int | None
    drop_reason: str | None
    added_in_edition: int | None
    salt: str
    version: int
    erased_tx: int | None = None
    checks: tuple[CheckView, ...] = ()  # every row, ordered by observed time, then K
    readings: tuple[ReadingView, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class FactBearing:
    assumption_id: int
    bearing: Bearing


@dataclass(frozen=True, slots=True, kw_only=True)
class FactView(RowStamp):
    """A ground or monitoring fact, including outcome reports (§2.4 table 8)."""

    id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    phase: FactPhase
    kind: FactKind
    claimed_outcome: ClaimedOutcome | None
    text: str
    occurred_at: EventAt
    occurred_precision: Precision
    occurred_basis: TimeBasis
    evidence_kind: EvidenceKind
    evidence_ref: str | None
    evidence_quote: str | None
    quote_verified: bool | None
    source_text: str | None
    reported_by: ReportedBy
    added_in_edition: int | None
    corrects_fact_id: int | None
    salt: str
    reconstructed: bool
    bearings: tuple[FactBearing, ...] = ()
    voided_at: datetime | None = None
    voided_reason: str | None = None
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewView(RowStamp):
    """The owner's verdict on the whole decision at a time (§2.4 table 10)."""

    id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    action: ReviewAction
    verdict: str | None
    notes: str | None
    revise_basis: ReviseBasis | None
    trigger: ReviewTrigger
    trigger_ref: str | None
    trigger_at: EventAt
    occurred_at: EventAt
    occurred_precision: Precision
    occurred_basis: TimeBasis
    next_review_due: date | None
    status_before: str | None
    review_due_before: date | None
    edition_before: int | None
    edition_after: int | None
    health_before: str | None
    ground_before: str | None
    timeliness_before: str | None
    unverifiable_before: str | None
    unverifiable_after: str | None
    reasons_answered_json: str | None
    execution_summary_json: str | None
    successor_ref: str | None
    is_correction: bool
    legacy_health_at_review: str | None
    reconstructed: bool
    voided_at: datetime | None = None
    voided_reason: str | None = None
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class OutcomeView(RowStamp):
    """An outcome resolution with its basis (§2.4 table 11); reports are facts, never this."""

    id: int
    decision_id: int
    review_id: int | None
    kind: OutcomeKind
    basis: OutcomeBasis
    evidence_refs: tuple[str, ...]
    measured_value: str | None
    expected_vs_actual: str | None
    occurred_at: EventAt
    occurred_precision: Precision
    occurred_basis: TimeBasis
    resolved_by: ResolvedBy
    supersedes_outcome_id: int | None
    reconstructed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningView(RowStamp):
    id: int
    decision_id: int
    code_n: int
    code: str
    ref: str
    edition: int
    review_id: int | None
    outcome_id: int | None
    confirmed: str | None
    refuted: str | None
    limits: str | None
    next_step: str | None
    same_again: SameAgain | None
    legacy_text: str | None
    salt: str
    reconstructed: bool
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StakeView(RowStamp):
    """A structured stake; data class FINANCIAL (amounts are withheld per destination)."""

    id: int
    decision_id: int
    type: StakeType
    amount: str | None
    currency: str | None
    period: StakePeriod | None
    count_periods: int | None
    direction: StakeDirection | None
    note: str | None
    planned: bool
    added_in_edition: int | None
    salt: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkView(RowStamp):
    """A DEC-owned link (§2.10); live while ``removed_tx`` is ``None``."""

    id: int
    decision_id: int
    role: LinkRole
    target_ref: str
    target_kind: LinkTargetKind
    resolution: LinkResolution
    note: str | None
    removed_tx: int | None = None
    removed_reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EditionView(RowStamp):
    """A sealed edition (§2.4 table 2). JSON columns stay CFJ-1 text; ``stored`` holds them as
    stored for integrity."""

    decision_id: int
    n: int
    code: str  # "E-02"
    ref: str  # "D-0042_E-02"
    reason: EditionReason
    fields_json: str
    field_salts_json: str
    field_hashes_json: str
    items_json: str
    seal_hash: str
    canon_version: int
    sealed_at: datetime
    sealed_by: str
    review_id: int | None
    reason_text: str | None
    unverifiable_at_seal: str | None
    reconstructed: bool
    erased_fields_json: str = "[]"
    erased_tx: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionView(RowStamp):
    """One changed field of a mutable head (§2.4 table 17)."""

    id: int
    entity: VersionEntity
    entity_id: int
    field: str
    old_value: str | None
    new_value: str | None
    reason: str | None
    cause_kind: VersionCause
    cause_ref: str | None
    reconstructed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionView(RowStamp):
    """A decision with every child row (§2.4 table 1 and its children)."""

    id: int
    public_id: str
    number: int
    title: str
    question: str | None
    statement: str | None
    kind: DecisionKind
    decider: Decider
    decider_basis: DeciderBasis
    decider_ref: str | None
    depth: Depth
    depth_basis: DepthBasis
    reversibility: Reversibility
    status: DecisionStatus
    manual_flag: ManualFlag | None
    manual_flag_reason: str | None
    context: str | None
    known: str | None
    would_help: str | None
    unknowns: tuple[str, ...]
    success_criterion: str | None
    expected_metric: str | None
    expected_target: str | None
    expected_unit: str | None
    expected_by: date | None
    expected_text: str | None
    confidence: int | None
    not_doing: str | None
    review_due: date | None
    review_due_initial: date | None
    decided_at: EventAt
    decided_precision: Precision
    decided_basis: TimeBasis
    activated_at: datetime | None
    closed_at: datetime | None
    current_edition: int
    completion_pending: bool
    origin_kind: OriginKind
    origin_quote: str | None
    publishability: Publishability
    third_party_sensitive: bool
    reconstructed: bool
    mirror_of: str | None
    mirror_scope: MirrorScope | None
    notes: str | None
    legacy_json: str | None
    version: int
    erased_tx: int | None = None
    # bookkeeping from dec_mirror_state (None for natives)
    absent_since_run_id: int | None = None
    adopted_at: datetime | None = None
    # children: every row, in code order (assumptions by position)
    options: tuple[OptionView, ...] = ()
    assumptions: tuple[AssumptionView, ...] = ()
    facts: tuple[FactView, ...] = ()
    reviews: tuple[ReviewView, ...] = ()
    outcomes: tuple[OutcomeView, ...] = ()
    learnings: tuple[LearningView, ...] = ()
    stakes: tuple[StakeView, ...] = ()
    links: tuple[LinkView, ...] = ()
    editions: tuple[EditionView, ...] = ()
    versions: tuple[VersionView, ...] = ()  # entities 'decision', 'assumption' and 'link' of it


@dataclass(frozen=True, slots=True, kw_only=True)
class ForkView(RowStamp):
    """An open question (§2.4 table 4)."""

    id: int
    public_id: str
    number: int
    question: str
    trigger_text: str | None
    trigger_ref: str | None
    opened_at: EventAt
    opened_precision: Precision
    opened_basis: TimeBasis
    decider: Decider
    decider_ref: str | None
    deadline: date | None
    status: ForkStatus
    outcome_not_heard: bool
    decision_id: int | None
    closed_at: datetime | None
    close_reason: str | None
    delegated_to_ref: str | None
    version: int
    options: tuple[OptionView, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ProposalView(RowStamp):
    """An inferred, unapproved record (§2.4 table 16). ``ref`` is ``"proposal <id>"`` (§3.12);
    ``title`` is the payload's title, else its statement or question."""

    id: int
    ref: str
    title: str
    type: ProposalType
    decision_id: int | None
    payload_json: str
    payload_hash: str
    origin_kind: str
    origin_quote: str | None
    proposed_by: str
    match_candidates_json: str
    status: ProposalStatus
    decided_tx: int | None
    reject_class: str | None
    reject_reason: str | None
    result_ref: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportRunView(RowStamp):
    """One snapshot import run (§2.6 ``dec_import_runs``)."""

    id: int
    source_issuer: str
    format: str
    format_version: int
    synthetic: bool
    file_hash: str
    exported_at: datetime | None
    as_of: datetime | None
    as_of_date: date | None
    mode: ImportMode
    status: ImportStatus
    counts_json: str
    v2_output_json: str | None
    report_status: ReportStatus
    error: str | None


# ==================================================================================================
# Computed results (track D; pure functions of views, T and DecConfig)


@dataclass(frozen=True, slots=True, kw_only=True)
class DueResult:
    """``assumption_due`` / ``check_due``: a date and its source, or neither (§3.6)."""

    due: date | None
    source: DueSource | None


@dataclass(frozen=True, slots=True, kw_only=True)
class NextCheck:
    """``next_check_after``: the next check date and the rule that set it (§3.6)."""

    next: date | None
    rule: NextCheckRule


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthReason:
    """One health reason, in structure and in words (§3.7): ``axis`` is 'ground', 'timeliness' or
    'label' (owner flag, draft, outcome); ``kind`` is the axis value or timeliness kind it
    explains."""

    axis: Literal["ground", "timeliness", "label"]
    kind: str
    text: str
    code: str | None = None
    day: date | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthResult:
    """``health(d, T)`` with both axes (§3.7). The evaluation order of the label is the contract.

    ``ground`` is ``None`` for terminal and draft decisions. ``states`` maps each active
    assumption's code to its effective state at T; ``pool`` lists the codes the decision rests on
    (the critical ones, else all). ``badge`` is the outcome badge of a closed decision ("success ·
    resolved"), ``badge_green`` only for a resolved success.
    """

    label: HealthLabel
    ground: GroundValue | None
    timeliness: frozenset[TimelinessKind]
    reasons: tuple[HealthReason, ...]
    share: Decimal | None
    bet: bool
    states: Mapping[str, AssumptionState] = field(default_factory=dict)
    pool: tuple[str, ...] = ()
    badge: str | None = None
    badge_green: bool = False

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(r.text for r in self.reasons)


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalChange:
    """A served or tested goal that ended after the decision and was not yet answered (§3.13)."""

    ref: str
    title: str | None
    status: str
    changed: date


@dataclass(frozen=True, slots=True, kw_only=True)
class IntegrityLine:
    """One line of ``integrity`` (§3.3): per edition ``ok`` / ``ok_with_erasures`` / ``changed``;
    the ``live`` line for ``drift`` and ``completion_pending``. ``items`` names what failed."""

    edition: int | Literal["live"]
    status: IntegrityStatus
    items: tuple[str, ...] = ()
    seal12: str | None = None  # the first 12 hex characters of the seal


@dataclass(frozen=True, slots=True, kw_only=True)
class IntegrityReport:
    decision_ref: str
    lines: tuple[IntegrityLine, ...]

    @property
    def ok(self) -> bool:
        return all(line.status in ("ok", "ok_with_erasures") for line in self.lines)


# ==================================================================================================
# Query results (track D's ``queries.py``; rendered by track X)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssumptionCard:
    """An assumption as the card shows it: effective state, due date and source, last check."""

    assumption: AssumptionView
    state: AssumptionState
    due: DueResult
    last_check: CheckView | None
    readings: tuple[ReadingView, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionContext:
    """``decision_context``: the card, in the order of spec §5.3.

    ``integrity_line`` is set only when integrity is not ``ok``. ``mirror_line`` states the
    authority for mirrors ("mirrored from V1, snapshot exported at ...; read-only here").
    ``execution`` maps each registered probe kind to its summary. ``brief`` detail leaves the
    long lists empty.
    """

    decision: DecisionView
    integrity_line: str | None
    share_line: str
    health: HealthResult
    waiting_reasons: tuple[Reason, ...]
    question_context: QuestionContext | None
    assumptions: tuple[AssumptionCard, ...]
    ground_facts: tuple[FactView, ...]
    monitoring_facts: tuple[FactView, ...]
    reviews: tuple[ReviewView, ...]
    outcome: OutcomeView | None
    learnings: tuple[LearningView, ...]
    editions: tuple[IntegrityLine, ...]
    links: tuple[LinkView, ...]
    execution: Mapping[str, AttachmentSummary] = field(default_factory=dict)
    mirror_line: str | None = None
    detail: Detail = "brief"
    audience: Audience = "owner"


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionLine:
    """``list_decisions``: one line per decision."""

    public_id: str
    title: str
    status: DecisionStatus
    kind: DecisionKind
    label: HealthLabel
    share: Decimal | None
    review_due: date | None
    first_reason: str | None
    mirror_of: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssumptionDue:
    """``assumption_due``: the due date with its source, and the last assessment."""

    assumption_ref: str
    due: DueResult
    last_assessment: CheckView | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AsOfView:
    """``as_of``: the record as known at ``t`` on an axis, with what v2 computes at ``t``."""

    decision: DecisionView  # filtered to rows visible at t, head replayed from versions
    health: HealthResult
    dues: Mapping[str, DueResult]  # assumption code -> due
    waiting_reasons: tuple[Reason, ...]
    coverage: tuple[str, ...] = ()


# ==================================================================================================
# Import and shadow results (track S)


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityCounts:
    seen: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    absent: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportReport:
    """The run report of ``import_snapshot`` (§6.5). ``counts`` maps an entity ('decisions',
    'assumptions', 'facts', 'reviews', 'links', 'versions') to its counts; ``absent`` lists the
    tombstoned refs; ``findings`` lists basis drift and other findings in words."""

    run_id: int | None
    status: ImportStatus
    mode: ImportMode
    file_hash: str
    source_issuer: str
    synthetic: bool
    exported_at: datetime | None
    as_of: datetime | None
    as_of_date: date | None
    counts: Mapping[str, EntityCounts]
    absent: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    report_status: ReportStatus = "pending"
    noop: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowItem:
    """One compared aspect (§2.6 ``dec_shadow_items``)."""

    decision_ref: str
    aspect: ShadowAspect
    subject_ref: str | None
    v1_value: str | None
    v2_value: str | None
    classification: ShadowClassification
    rule_id: str | None = None  # "SR-n" for 'expected'


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowReport:
    """``shadow_report`` (§6.6): totals per class, counts per rule, every unexpected line with both
    values. ``report_status`` 'blocked' means the run is still ``partial``."""

    run_id: int
    as_of_date: date | None
    report_status: ReportStatus
    totals: Mapping[str, int]  # same, expected, unexpected, finding
    by_rule: Mapping[str, int]
    unexpected: tuple[ShadowItem, ...]
    findings: tuple[ShadowItem, ...]
    items: tuple[ShadowItem, ...] = ()
    runs_since_last_unexpected: int | None = None
