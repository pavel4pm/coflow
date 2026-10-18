"""Proposals and their approval in an owner channel (spec §3.12). Owned by track S (store, import,
shadow); increment I3. The signatures are the targets of ``dec.api`` and are fixed by the facade
(provisional until the I3 skeleton review); the track implements them.
"""

from __future__ import annotations

from collections.abc import Mapping

from coflow.kernel.context import Answer, CommandContext, CommandResult
from coflow.modules.dec.domain.inputs import (
    CodeResult,
    OriginInput,
    ProposalLine,
    ProposalResult,
)
from coflow.modules.dec.domain.model import (
    DecEnv,
)

_TODO = "track S: modules/dec/commands/proposals.py"


def propose_decision(
    env: DecEnv, *, payload: Mapping[str, object], origin: OriginInput, ctx: CommandContext
) -> CommandResult[ProposalResult]:
    raise NotImplementedError(_TODO)


def approve_proposal(
    env: DecEnv,
    proposal_id: int,
    *,
    edits: Mapping[str, object] | None = None,
    ctx: CommandContext,
) -> CommandResult[CodeResult]:
    raise NotImplementedError(_TODO)


def reject_proposal(
    env: DecEnv, proposal_id: int, *, reject_class: str, reason: str, ctx: CommandContext
) -> CommandResult[None]:
    raise NotImplementedError(_TODO)


def list_proposals(
    env: DecEnv, *, status: str | None = None, origin_kind: str | None = None
) -> Answer[list[ProposalLine]]:
    raise NotImplementedError(_TODO)
