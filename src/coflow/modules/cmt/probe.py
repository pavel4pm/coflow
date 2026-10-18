"""CMT's ``DecisionAttachmentProbe`` (kind ``commitment``, spec §4.2).

Owned by track C (commitments, K's agent); increment I3, spec §12.4. The class is fixed by the
skeleton because ``cmt.api.probe`` constructs it; the track implements it. It returns ids, counts
and change names only.
"""

from __future__ import annotations

from datetime import datetime

from coflow.kernel.ports.attachment_probe import (
    AttachmentEvent,
    AttachmentSummary,
    Period,
    UnlinkedCounts,
)
from coflow.modules.cmt.model import CmtEnv

__all__ = ["CommitmentProbe"]

_TODO = "track C: modules/cmt/probe.py"


class CommitmentProbe:
    """Implements ``kernel.ports.attachment_probe.DecisionAttachmentProbe``."""

    kind = "commitment"

    def __init__(self, env: CmtEnv) -> None:
        self.env = env

    def summary(self, decision_ref: str, as_of: datetime) -> AttachmentSummary:
        raise NotImplementedError(_TODO)

    def timeline(
        self, decision_ref: str, between: tuple[datetime, datetime]
    ) -> list[AttachmentEvent]:
        raise NotImplementedError(_TODO)

    def unlinked(self, period: Period) -> UnlinkedCounts:
        raise NotImplementedError(_TODO)
