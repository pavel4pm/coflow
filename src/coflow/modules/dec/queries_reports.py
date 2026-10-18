"""History and report queries: decision history, the unlinked report, loop metrics (spec
§3.14-§3.16). Owned by track D (decision domain); increment I3. The signatures are the targets
of ``dec.api`` and are fixed by the facade (provisional until the I3 skeleton review); the track
implements them.
"""

from __future__ import annotations

from coflow.kernel.context import Answer
from coflow.kernel.ports.attachment_probe import Period
from coflow.modules.dec.domain.inputs import (
    HistoryResult,
    LoopMetrics,
    UnlinkedReport,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
)

_TODO = "track D: modules/dec/queries_reports.py"


def decision_history(env: DecEnv, scope: str, period: Period) -> Answer[HistoryResult]:
    raise NotImplementedError(_TODO)


def unlinked_report(env: DecEnv, period: Period) -> Answer[UnlinkedReport]:
    raise NotImplementedError(_TODO)


def loop_metrics(env: DecEnv, period: Period) -> Answer[LoopMetrics]:
    raise NotImplementedError(_TODO)
