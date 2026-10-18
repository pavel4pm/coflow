"""Fakes of the kernel ports (spec §12.1): in-memory, deterministic, offline.

Skeleton package; tracks may add fakes here (append only). Each fake satisfies its port protocol
(``tests/test_smoke.py`` checks it) and records the calls it received in ``calls``.
"""

from tests.fakes.attachment_probe import FakeAttachmentProbe
from tests.fakes.decision_directory import FakeDecisionDirectory
from tests.fakes.evidence_resolver import FakeEvidenceResolver
from tests.fakes.goal_directory import FakeGoalDirectory
from tests.fakes.undo import FakeUndoHandler

__all__ = [
    "FakeAttachmentProbe",
    "FakeDecisionDirectory",
    "FakeEvidenceResolver",
    "FakeGoalDirectory",
    "FakeUndoHandler",
]
