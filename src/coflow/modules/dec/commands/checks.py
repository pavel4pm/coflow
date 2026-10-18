"""The check log: assessments and postponements (spec §3.6). Owned by track S (store, import,
shadow); increment I2. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    CheckResult,
    EvidenceInput,
    PostponeResult,
    When,
)
from coflow.modules.dec.domain.model import (
    CheckState,
    DecEnv,
)

_TODO = "track S: modules/dec/commands/checks.py"


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
    raise NotImplementedError(_TODO)


def postpone_check(
    env: DecEnv, assumption_ref: str, *, until: date, reason: str, ctx: CommandContext
) -> CommandResult[PostponeResult]:
    raise NotImplementedError(_TODO)
