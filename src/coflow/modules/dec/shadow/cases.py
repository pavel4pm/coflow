"""The owner's real cases on a throw-away copy (spec §6.7). Owned by track S (store, import,
shadow); increment I3. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I3 skeleton review); the track implements them.
"""

from __future__ import annotations

from pathlib import Path

from coflow.kernel.context import Answer, CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    CaseLine,
    CaseResult,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
)

_TODO = "track S: modules/dec/shadow/cases.py"


def run_case(env: DecEnv, case_file: Path, *, ctx: CommandContext) -> CommandResult[CaseResult]:
    raise NotImplementedError(_TODO)


def list_cases(env: DecEnv) -> Answer[list[CaseLine]]:
    raise NotImplementedError(_TODO)
