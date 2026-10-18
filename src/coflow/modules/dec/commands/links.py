"""DEC-owned links of the hub registry (spec §2.10). Owned by track S (store, import, shadow);
increment I2. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I2 skeleton review); the track implements them.
"""

from __future__ import annotations

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    LinkResult,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
    LinkRole,
)

_TODO = "track S: modules/dec/commands/links.py"


def link(
    env: DecEnv,
    ref: str,
    role: LinkRole,
    target_ref: str,
    *,
    note: str | None = None,
    ctx: CommandContext,
) -> CommandResult[LinkResult]:
    raise NotImplementedError(_TODO)


def unlink(env: DecEnv, link_id: int, *, reason: str, ctx: CommandContext) -> CommandResult[None]:
    raise NotImplementedError(_TODO)
