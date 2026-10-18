"""The numbering tap (IDN-1, IDN-10, spec §2.2, §6.4): one place issues every public number.

Owned by track K; increment I1, spec §12.2. The signatures below are fixed by the skeleton because
track S (import) calls ``register_foreign`` and ``burn``; the track implements them.

All three run inside the caller's unit of work (``kernel.store.api.unit_of_work``). The tap never
issues a foreign number (``sys_id_foreign``), a burned number (``sys_id_burned``) or a number below
the prefix's ``block_start`` while a foreign issuer owns the low range (AT-K1).

How a number is chosen: ``n = max(next_n, block_start or 1)``, then past every foreign or burned
number at or above it; ``next_n`` becomes ``n + 1`` in the same unit, so the number commits with
the record that uses it, and a unit that rolls back gives it back unseen. The writer serialises
units, so concurrent issues never collide.

Spec notes: only top-level prefixes (``D``, ``Q``, ``F``) are issued here; scoped codes (``A``,
``CK``, ...) are counted by their parent row (§2.2), and asking the tap for one is a
``ContractViolation``. ``register_foreign`` refuses (``IMPORT_SOURCE_CONFLICT``) a number this
instance already issued, and a number another issuer already registered. The burn reason
``rollback`` is kept for numbers shown outside a unit that then failed; the slice has none, because
an issued number becomes visible only when its unit commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from coflow.kernel.errors import ContractViolation, RefusalCode, Refused
from coflow.kernel.ids.codes import is_issuer_code, render
from coflow.kernel.ids.registry import PrefixSpec, prefix_spec
from coflow.kernel.store.api import current_unit
from coflow.kernel.store.unit import Unit

__all__ = ["BurnReason", "IssuedId", "burn", "issue", "register_foreign"]

BurnReason = Literal["rollback", "undo", "deleted_in_source", "numbering_gap"]


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedId:
    prefix: str
    n: int
    public_id: str  # canonical, e.g. "D-1001"


def _unit() -> Unit:
    unit = current_unit()
    if not isinstance(unit, Unit):
        raise ContractViolation("the tap runs inside a kernel unit of work")
    return unit


def _top_level(prefix: str) -> PrefixSpec:
    spec = prefix_spec(prefix)
    if spec.scoped_under:
        raise ContractViolation(f"{prefix} is a scoped code: its parent row counts it")
    return spec


def _check_n(spec: PrefixSpec, n: int) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n < 10**spec.width:
        raise ContractViolation(f"{spec.prefix} counts 1 to {10**spec.width - 1}, not {n!r}")


def _sequence(unit: Unit, prefix: str) -> tuple[int, int | None]:
    row = unit.fetch_one(
        "SELECT s.next_n, p.block_start FROM sys_id_sequence AS s"
        " JOIN sys_id_prefixes AS p ON p.prefix = s.prefix WHERE s.prefix = ?",
        (prefix,),
    )
    if row is None:
        raise ContractViolation(f"{prefix} is not seeded in this instance (coflow init)")
    block = row["block_start"]
    return int(row["next_n"]), None if block is None else int(block)


def issue(prefix: str) -> IssuedId:
    """Issue the next number of ``prefix`` inside the current unit of work."""
    spec = _top_level(prefix)
    unit = _unit()
    next_n, block_start = _sequence(unit, prefix)
    n = max(next_n, block_start or 1)
    taken = unit.fetch_all(
        "SELECT n FROM sys_id_foreign WHERE prefix = ? AND n >= ?"
        " UNION SELECT n FROM sys_id_burned WHERE prefix = ? AND n >= ? ORDER BY n",
        (prefix, n, prefix, n),
    )
    for row in taken:
        value = int(row["n"])
        if value == n:
            n += 1
        elif value > n:
            break
    if n >= 10**spec.width:
        raise ContractViolation(f"{prefix} is exhausted at width {spec.width}")
    unit.kernel_update("sys_id_sequence", {"prefix": prefix}, next_n=n + 1)
    return IssuedId(prefix=prefix, n=n, public_id=render(prefix, n))


def register_foreign(prefix: str, n: int, *, issuer: str, source_id: str) -> None:
    """Record that ``n`` is taken by another issuing space (``V1``); idempotent per (prefix, n)."""
    spec = _top_level(prefix)
    _check_n(spec, n)
    if not is_issuer_code(issuer):
        raise ContractViolation(f"{issuer!r} is not an issuer code")
    unit = _unit()
    existing = unit.fetch_one(
        "SELECT issuer FROM sys_id_foreign WHERE prefix = ? AND n = ?", (prefix, n)
    )
    if existing is not None:
        if str(existing["issuer"]) == issuer:
            return
        raise Refused(
            RefusalCode.IMPORT_SOURCE_CONFLICT,
            f"{render(prefix, n)} is already registered for {existing['issuer']}",
        )
    next_n, block_start = _sequence(unit, prefix)
    if (block_start or 1) <= n < next_n:
        raise Refused(
            RefusalCode.IMPORT_SOURCE_CONFLICT,
            f"{render(prefix, n)} was issued by this instance; {issuer} cannot own it",
        )
    unit.kernel_insert(
        "sys_id_foreign", {"prefix": prefix, "n": n, "issuer": issuer, "source_id": source_id}
    )


def burn(prefix: str, n: int, *, reason: BurnReason, issuer: str | None = None) -> None:
    """Record that ``n`` must never be issued; idempotent per (prefix, n)."""
    spec = _top_level(prefix)
    _check_n(spec, n)
    if reason not in get_args(BurnReason):
        raise ContractViolation(f"unknown burn reason {reason!r}")
    if issuer is not None and not is_issuer_code(issuer):
        raise ContractViolation(f"{issuer!r} is not an issuer code")
    unit = _unit()
    if unit.fetch_one("SELECT 1 FROM sys_id_burned WHERE prefix = ? AND n = ?", (prefix, n)):
        return
    unit.kernel_insert(
        "sys_id_burned", {"prefix": prefix, "n": n, "reason": reason, "issuer": issuer}
    )
