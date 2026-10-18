"""The project's public decision log as native data, selected entries only (spec §6.8). Owned by
track K (kernel); increment I2. The signatures are the targets of ``dec.api`` and are fixed by
the facade (provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.model import (
    DecEnv,
    ImportReport,
)

_TODO = "track K: modules/dec/importer/project_log.py"


def import_decision_log(
    env: DecEnv, file: Path, *, only: Sequence[str], ctx: CommandContext
) -> CommandResult[ImportReport]:
    raise NotImplementedError(_TODO)
