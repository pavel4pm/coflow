"""CMT queries (spec §5.4): open commitments (annotated when their decision ended) and one
commitment with its history.

Owned by track C (commitments, K's agent); increment I3, spec §12.4. The signatures are the targets
of ``cmt.api`` (provisional until the I3 skeleton review); the track implements them.
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.context import Answer
from coflow.modules.cmt.model import CmtEnv, CommitmentLine, CommitmentView

__all__ = ["commitment", "open_commitments"]

_TODO = "track C: modules/cmt/queries.py"


def open_commitments(
    env: CmtEnv,
    *,
    debtor: str | None = None,
    creditor: str | None = None,
    decision_ref: str | None = None,
    due_before: date | None = None,
) -> Answer[list[CommitmentLine]]:
    raise NotImplementedError(_TODO)


def commitment(env: CmtEnv, ref: str) -> Answer[CommitmentView]:
    raise NotImplementedError(_TODO)
