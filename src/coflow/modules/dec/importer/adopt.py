"""The adoption gate and the adoption of mirrors (spec §6.10). Owned by track S (store, import,
shadow); increment I3. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I3 skeleton review); the track implements them.
"""

from __future__ import annotations

from coflow.kernel.context import CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    AdoptionResult,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
)

_TODO = "track S: modules/dec/importer/adopt.py"


def adopt_mirrors(
    env: DecEnv, *, issuer: str, confirm_phrase: str, ctx: CommandContext
) -> CommandResult[AdoptionResult]:
    raise NotImplementedError(_TODO)
