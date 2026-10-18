"""``DecisionAttachmentProbe``: how DEC sees the execution of a decision without importing spokes.

Skeleton file (spec §4.2, §12.1). Implemented by each spoke (CMT in I3; WRK, MTG, FIN, RHY later)
and registered by the composition root; DEC iterates over the registered probes. A missing module
simply has no probe. Probes return ids, counts and change names only, so DEC stores another module's
data only as frozen counts in ``dec_reviews.execution_summary_json``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable

__all__ = [
    "LINK_BUCKETS",
    "AttachmentEvent",
    "AttachmentSummary",
    "DecisionAttachmentProbe",
    "Period",
    "UnlinkedCounts",
]

LINK_BUCKETS: tuple[str, ...] = ("linked", "explicit_none", "unanswered", "not_offered")


@dataclass(frozen=True, slots=True)
class Period:
    """A half-open interval of instants ``[start, end)``, both timezone-aware UTC."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("period bounds must be timezone-aware")
        if self.end < self.start:
            raise ValueError("period ends before it starts")

    def contains(self, instant: datetime) -> bool:
        return self.start <= instant < self.end


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentSummary:
    """Execution of one decision by one spoke kind, as of a time."""

    kind: str
    total: int = 0
    open: int = 0
    done: int = 0
    dropped: int = 0
    overdue: int = 0
    shifted: int = 0  # count of due-date shifts
    last_activity_at: datetime | None = None
    refs: tuple[str, ...] = ()  # ids only

    def counts(self) -> dict[str, int]:
        return {
            "total": self.total,
            "open": self.open,
            "done": self.done,
            "dropped": self.dropped,
            "overdue": self.overdue,
            "shifted": self.shifted,
        }

    def counts_and_ids(self) -> dict[str, object]:
        """The frozen form stored in ``dec_reviews.execution_summary_json``."""
        return {**self.counts(), "refs": list(self.refs)}


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentEvent:
    """One change of an attached record: ids and change names only, e.g. ``('F-10003', 'done')``."""

    occurred_at: date | datetime | None
    recorded_at: datetime
    ref: str
    change: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnlinkedCounts:
    """The four link buckets of one spoke kind in a period (§3.14)."""

    kind: str
    total: int = 0
    linked: int = 0
    explicit_none: int = 0
    explicit_none_by_reason: Mapping[str, int] = field(default_factory=dict)
    unanswered: int = 0
    not_offered: int = 0
    goal_only: int = 0
    refs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # bucket -> refs


@runtime_checkable
class DecisionAttachmentProbe(Protocol):
    """Implemented by each spoke; ``kind`` is 'commitment', 'task', 'meeting', 'ledger_entry' or
    'time_span'."""

    kind: str

    def summary(self, decision_ref: str, as_of: datetime) -> AttachmentSummary: ...

    def timeline(
        self, decision_ref: str, between: tuple[datetime, datetime]
    ) -> list[AttachmentEvent]: ...

    def unlinked(self, period: Period) -> UnlinkedCounts: ...
