"""The prefix registry (IDN-2, spec §2.2): which prefixes exist, their widths, owners and blocks.

Owned by track K; increment I1, spec §12.2. The track implements the functions; ``SLICE_PREFIXES``
is fixed by the skeleton from spec §2.2 and the owner's answer of 18 October 2026 (decision numbers
keep v1's as ``D-0NNN``, natives from ``D-1001``; forks ``Q``; commitments ``F`` with natives from
``F-10001``), because every track renders codes with these widths. K seeds ``sys_id_prefixes`` from
it at ``init`` and a test asserts the two agree.

Spec note: §2.2 registers prefixes for people, companies, directions, goals, tasks, meetings and
sessions "so nothing collides" without naming them; the slice issues none of them, so they are left
to the modules that own them (stage 1) and are not in this table.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from coflow.kernel.errors import RefusalCode, Refused

__all__ = ["SLICE_PREFIXES", "PrefixSpec", "prefix_spec", "prefix_table", "registry_row"]


@dataclass(frozen=True, slots=True, kw_only=True)
class PrefixSpec:
    """One row of ``sys_id_prefixes``.

    ``scoped_under`` names the parent prefixes of a scoped code (``A`` lives under ``D``: the code
    ``D-0042_A-03``); ``block_start`` is the first number the instance issues while a foreign issuer
    (``V1``) owns the low range (§6.4).
    """

    prefix: str
    entity: str
    width: int
    owner_module: str
    block_start: int | None = None
    scoped_under: tuple[str, ...] = ()
    description: str = ""


SLICE_PREFIXES: tuple[PrefixSpec, ...] = (
    PrefixSpec(
        prefix="D",
        entity="decision",
        width=4,
        owner_module="dec",
        block_start=1001,
        description="v1 numbers kept (D907 -> D-0907); natives from the reserved block D-1001",
    ),
    PrefixSpec(prefix="Q", entity="fork", width=4, owner_module="dec", description="open question"),
    PrefixSpec(
        prefix="F",
        entity="commitment",
        width=5,
        owner_module="cmt",
        block_start=10001,
        description="numbered promises; natives from F-10001",
    ),
    PrefixSpec(prefix="A", entity="assumption", width=2, owner_module="dec", scoped_under=("D",)),
    PrefixSpec(prefix="O", entity="option", width=2, owner_module="dec", scoped_under=("D", "Q")),
    PrefixSpec(prefix="E", entity="edition", width=2, owner_module="dec", scoped_under=("D",)),
    PrefixSpec(prefix="R", entity="review", width=2, owner_module="dec", scoped_under=("D",)),
    PrefixSpec(prefix="L", entity="learning", width=2, owner_module="dec", scoped_under=("D",)),
    PrefixSpec(prefix="FT", entity="fact", width=3, owner_module="dec", scoped_under=("D",)),
    PrefixSpec(prefix="CK", entity="check", width=3, owner_module="dec", scoped_under=("A",)),
    PrefixSpec(prefix="RD", entity="reading", width=3, owner_module="dec", scoped_under=("A",)),
)


_BY_PREFIX: Mapping[str, PrefixSpec] = {p.prefix: p for p in SLICE_PREFIXES}


def prefix_spec(prefix: str) -> PrefixSpec:
    """The registered spec of ``prefix``; ``Refused(PREFIX_UNKNOWN)`` for an unregistered one."""
    spec = _BY_PREFIX.get(prefix)
    if spec is None:
        raise Refused(
            RefusalCode.PREFIX_UNKNOWN,
            f"{prefix!r} is not a registered id prefix",
            allowed=sorted(_BY_PREFIX),
        )
    return spec


def prefix_table() -> Mapping[str, PrefixSpec]:
    """Every registered prefix (the static registry of the slice)."""
    return _BY_PREFIX


def registry_row(spec: PrefixSpec) -> dict[str, str | int | None]:
    """The ``sys_id_prefixes`` row ``init`` seeds for ``spec`` (``scoped_under``: a JSON array)."""
    return {
        "prefix": spec.prefix,
        "entity": spec.entity,
        "width": spec.width,
        "owner_module": spec.owner_module,
        "block_start": spec.block_start,
        "scoped_under": json.dumps(list(spec.scoped_under)) if spec.scoped_under else None,
        "description": spec.description,
    }
