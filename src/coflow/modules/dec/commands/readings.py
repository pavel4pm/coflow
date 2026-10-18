"""Readings that propose a state (spec §3.5). Owned by track S (store, import, shadow); increment
I2. The signatures are the targets of ``dec.api`` and are fixed by the facade (provisional until
the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    ReadingResult,
    When,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
    ReadingSourceKind,
)

_TODO = "track S: modules/dec/commands/readings.py"


def record_reading(
    env: DecEnv,
    assumption_ref: str,
    *,
    value: str | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    observed: When | None = None,
    source_kind: ReadingSourceKind = "owner_statement",
    source_ref: str | None = None,
    quote: str | None = None,
    ctx: CommandContext,
) -> CommandResult[ReadingResult]:
    raise NotImplementedError(_TODO)
