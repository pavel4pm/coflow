"""Aliases (``sys_id_aliases``) and resolution of any accepted input to a canonical id (IDN-9).

Owned by track K; increment I1, spec §12.2. The signatures below are fixed by the skeleton because
track S registers aliases at import and tracks D and X resolve user input; the track implements
them.

``V1_D907 -> D-0907`` is a ``foreign`` alias registered by the importer; ``CF2LOG_D-037 -> D-1004``
by the project-log importer (I2); renames and merges add ``rename`` / ``merge`` aliases later.

An alias is stored normalised (``alias_norm``: NFKC, look-alike letters to Latin, upper case,
spaces and slashes to ``_``), so ``v1_d907`` and ``V1 D907`` find ``V1_D907``. Foreign source ids
are otherwise kept as received (``CF2LOG_D-037`` is not ``CF2LOG_D37``).

Spec note: ``resolve`` does not strip the instance's own issuer (``CF_D-0042``); outward
references are produced on export (stage 6), and only then read back.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Literal, get_args

from coflow.kernel.errors import ContractViolation, NotFound, Refused
from coflow.kernel.ids.codes import canonical as tolerant_canonical
from coflow.kernel.ids.codes import is_issuer_code, normalise_input, parse
from coflow.kernel.store.api import current_unit
from coflow.kernel.store.unit import Unit

__all__ = ["AliasKind", "add_alias", "aliases_of", "normalise_alias", "resolve"]

AliasKind = Literal["legacy", "rename", "merge", "foreign"]


def normalise_alias(text: str) -> str:
    """The stored form of an alias: ``normalise_input`` plus ``_`` for spaces and slashes."""
    return re.sub(r"[\s/]+", "_", normalise_input(text))


def add_alias(alias: str, canonical: str, *, issuer: str, kind: AliasKind) -> None:
    """Register ``alias`` (normalised) for ``canonical`` inside the current unit of work; idempotent
    when the same alias already points at the same id."""
    if kind not in get_args(AliasKind):
        raise ContractViolation(f"unknown alias kind {kind!r}")
    if not is_issuer_code(issuer):
        raise ContractViolation(f"{issuer!r} is not an issuer code")
    try:
        target = parse(canonical)
    except (NotFound, Refused) as exc:
        raise ContractViolation(f"an alias points at a canonical id, not {canonical!r}") from exc
    if target.is_foreign or target.canonical != canonical:
        raise ContractViolation(f"an alias points at a canonical native id, not {canonical!r}")
    norm = normalise_alias(alias)
    if not norm:
        raise ContractViolation("an empty alias")
    unit = current_unit()
    if not isinstance(unit, Unit):
        raise ContractViolation("aliases are written inside a kernel unit of work")
    existing = unit.fetch_one("SELECT canonical FROM sys_id_aliases WHERE alias_norm = ?", (norm,))
    if existing is not None:
        if str(existing["canonical"]) == canonical:
            return
        raise ContractViolation(f"alias {norm} already points at {existing['canonical']}")
    unit.kernel_insert(
        "sys_id_aliases",
        {"alias_norm": norm, "canonical": canonical, "issuer": issuer, "kind": kind},
    )


def resolve(conn: sqlite3.Connection, text: str) -> str:
    """The canonical id for ``text``: canonical form, tolerant form or alias (in that order).

    Raises ``NotFound(text)`` or ``Ambiguous(candidates)``. It does not check that a record with the
    id exists; the owning module does.
    """
    refusal: Refused | None = None
    foreign = False
    try:
        ref = tolerant_canonical(text)  # Ambiguous propagates: a bare number names no one id
    except Refused as exc:  # an unknown prefix: an alias may still know the text
        refusal = exc
    except NotFound:
        pass
    else:
        foreign = parse(ref).is_foreign
        if not foreign:
            return ref
    row = conn.execute(
        "SELECT canonical FROM sys_id_aliases WHERE alias_norm = ?", (normalise_alias(text),)
    ).fetchone()
    if row is not None:
        return str(row[0])
    if refusal is not None:
        raise refusal
    detail = "no alias for this foreign reference" if foreign else "not an id"
    raise NotFound(text, detail)


def aliases_of(conn: sqlite3.Connection, canonical: str) -> list[str]:
    """Every alias that points at ``canonical`` (shown on a card's history line)."""
    rows = conn.execute(
        "SELECT alias_norm FROM sys_id_aliases WHERE canonical = ? ORDER BY alias_norm",
        (canonical,),
    ).fetchall()
    return [str(r[0]) for r in rows]
