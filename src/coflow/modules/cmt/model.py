"""CMT's views, inputs and results (spec §2.5, §5.4): the contract between track C and track X.

Skeleton file (spec §12.1); provisional until the I3 skeleton review. The representation rules are
DEC's (``modules/dec/domain/model.py``): aware UTC instants, ``date`` for local dates, event times
as ``<x>_at`` / ``<x>_precision`` / ``<x>_basis``, every row loaded, ``stored`` as stored.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from coflow.kernel.ports.decision_directory import DecisionDirectory
from coflow.kernel.ports.goal_directory import GoalDirectory

__all__ = [
    "CmtEnv",
    "CommitmentHistoryView",
    "CommitmentLine",
    "CommitmentResult",
    "CommitmentStatus",
    "CommitmentView",
    "DoneAt",
    "DueBasis",
    "LinkAnswer",
    "NoDecisionReason",
]

CommitmentStatus = Literal["open", "suggested_done", "done", "dropped", "unclear"]
DueBasis = Literal["stated", "inferred", "none"]
DoneBasis = Literal["stated", "live", "unknown"]
LinkAnswer = Literal["linked", "explicit_none", "unanswered", "not_offered"]
NoDecisionReason = Literal["routine", "personal", "admin", "not_yet_decided", "other"]
CommitmentOrigin = Literal["cli", "mcp", "bot", "meeting_outcome", "app", "import"]
HistoryField = Literal["status", "due_date", "decision_ref", "what", "debtor_ref", "creditor_ref"]
DoneAt = date | datetime | Literal["now", "unknown"]
"""``done_at`` as the owner states it (§5.4): a date, ``now`` or ``unknown``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CmtEnv:
    """The ports CMT uses, wired by the composition root."""

    decision_directory: DecisionDirectory
    goal_directory: GoalDirectory | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitmentHistoryView:
    tx: int
    recorded_at: datetime
    id: int
    commitment_id: int
    field: HistoryField
    old_value: str | None
    new_value: str | None
    reason: str | None
    occurred_at: datetime | date | None
    occurred_precision: str
    occurred_basis: str
    origin_recorded_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitmentView:
    tx: int
    recorded_at: datetime
    id: int
    public_id: str  # F-10001
    number: int
    debtor_ref: str
    creditor_ref: str
    what: str
    success_criterion: str | None
    due_date: date | None
    due_basis: DueBasis
    status: CommitmentStatus
    done_at: datetime | date | None
    done_precision: str | None
    done_basis: DoneBasis | None
    decision_ref: str | None
    no_decision_reason: NoDecisionReason | None
    link_answer: LinkAnswer
    goal_ref: str | None
    source_ref: str | None
    source_quote: str | None
    origin: CommitmentOrigin
    external_ref: str | None
    version: int
    origin_recorded_at: datetime | None = None
    origin_ref: str | None = None
    erased_tx: int | None = None
    history: tuple[CommitmentHistoryView, ...] = ()
    stored: Mapping[str, str | int | None] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitmentLine:
    """``open_commitments``: one line, annotated when its decision has ended (§4.3)."""

    public_id: str
    what: str
    debtor_ref: str
    creditor_ref: str
    due_date: date | None
    status: CommitmentStatus
    decision_ref: str | None
    decision_ended_note: str | None = None  # "decision ended: keep, drop or move?"


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitmentResult:
    public_id: str
    link_answer: LinkAnswer
