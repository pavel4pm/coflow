"""A fake ``DecisionAttachmentProbe``: canned summaries, timelines and link buckets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from coflow.kernel.ports.attachment_probe import (
    AttachmentEvent,
    AttachmentSummary,
    Period,
    UnlinkedCounts,
)


@dataclass
class FakeAttachmentProbe:
    """``summaries`` and ``events`` are keyed by decision ref; unknown refs give empty answers.

    AT-N23 uses it for "two commitments overdue": ``FakeAttachmentProbe(summaries={'D-1003':
    AttachmentSummary(kind='commitment', total=2, open=2, overdue=2)})``.
    """

    kind: str = "commitment"
    summaries: dict[str, AttachmentSummary] = field(default_factory=dict)
    events: dict[str, list[AttachmentEvent]] = field(default_factory=dict)
    unlinked_counts: UnlinkedCounts | None = None
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def summary(self, decision_ref: str, as_of: datetime) -> AttachmentSummary:
        self.calls.append(("summary", (decision_ref, as_of)))
        return self.summaries.get(decision_ref, AttachmentSummary(kind=self.kind))

    def timeline(
        self, decision_ref: str, between: tuple[datetime, datetime]
    ) -> list[AttachmentEvent]:
        self.calls.append(("timeline", (decision_ref, between)))
        start, end = between
        return [
            e
            for e in self.events.get(decision_ref, [])
            if isinstance(e.occurred_at, datetime) and start <= e.occurred_at < end
        ]

    def unlinked(self, period: Period) -> UnlinkedCounts:
        self.calls.append(("unlinked", (period,)))
        return self.unlinked_counts or UnlinkedCounts(kind=self.kind)
