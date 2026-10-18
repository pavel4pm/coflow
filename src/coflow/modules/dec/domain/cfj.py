"""CFJ-1 canonical JSON, salted hashes and the seal envelope (spec §3.3).

Owned by track D (decision domain); increment I1, spec §12.2 (AT-K8). The names below are fixed by
the skeleton because track S seals mirrors at import with them (spec §6.5) and track D verifies
seals with the same functions. ``BASIS_FIELDS`` and ``ITEM_KEYS`` are spec text (§3.3) and must not
change without a new canonical version.

Hash inputs are **stored values** (``str | int | None`` as SQLite returns them, see
``model.RowStamp.stored``): CFJ-1 refuses floats, so a basis never passes through float formatting.
For an object of string keys and integer values ``cfj`` is byte-identical to the forecast pilot's
canonicalisation (``json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(',', ':'))``),
and ``unit_hash`` has the pilot's ``sha256(salt + canonical)`` shape, so pilot seals verify with
these functions.

Spec notes:

- ``normalise`` accepts any ``Mapping`` (not only ``dict``) and any non-string sequence that is a
  list or tuple, so a ``sqlite3.Row`` converted with ``dict(row)`` and a frozen view's tuple hash
  the same way.
- ``basis_value`` and ``item_content`` read a stored row. SQLite has no boolean type, so a stored
  row never holds ``True``/``False``; if a caller passes one anyway it is hashed as ``1``/``0``,
  which is what SQLite would have returned. Without this, a seal made from an inserted mapping
  (``True``) and its verification from the read row (``1``) would disagree.
- The read side of ``integrity`` (``verify_edition``, ``integrity_lines``) lives here in I1, next
  to the hashing it recomputes; I2's ``domain/seal.py`` adds the write side. It reads every hash
  input from ``stored`` (the edition's own ``sealed_at`` text included), never from typed
  attributes. ``seal_items(d)`` lists what an edition of ``d`` seals now, for any caller that has
  a loaded view.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from coflow.kernel.context import format_instant, new_salt
from coflow.modules.dec.domain.model import (
    DecisionView,
    EditionView,
    IntegrityLine,
    IntegrityReport,
    IntegrityStatus,
    RowStamp,
)

__all__ = [
    "BASIS_FIELDS",
    "CANON_VERSION",
    "ITEM_KEYS",
    "EditionDraft",
    "SealItem",
    "basis_value",
    "build_edition",
    "cfj",
    "cfj_text",
    "integrity_lines",
    "integrity_report",
    "item_content",
    "item_hash",
    "new_salt",
    "normalise",
    "seal_envelope",
    "seal_hash",
    "seal_items",
    "sha256_hex",
    "unit_hash",
    "verify_edition",
]

CANON_VERSION = 1  # CFJ-1

BASIS_FIELDS: tuple[str, ...] = (
    "kind",
    "decider",
    "decider_ref",
    "depth",
    "reversibility",
    "question",
    "statement",
    "context",
    "known",
    "unknowns",
    "would_help",
    "success_criterion",
    "expected_metric",
    "expected_target",
    "expected_unit",
    "expected_by",
    "expected_text",
    "confidence",
    "not_doing",
    "review_due_initial",
    "decided_at",
    "decided_precision",
    "decided_basis",
    "reconstructed",
)
"""The inline basis fields of an edition, in the order of §3.3."""

ITEM_KEYS: Mapping[str, tuple[str, ...]] = {
    "option": ("code", "text", "chosen", "why_rejected", "recorded_before_choice", "origin"),
    "ground": (
        "code",
        "text",
        "occurred_at",
        "occurred_precision",
        "occurred_basis",
        "evidence_kind",
        "evidence_ref",
        "evidence_quote",
    ),
    "assumption": (
        "code",
        "statement",
        "metric",
        "comparator",
        "threshold_value",
        "threshold_value2",
        "unit",
        "threshold_text",
        "by_date",
        "judge_from",
        "data_source_kind",
        "data_source_text",
        "check_frequency",
        "is_critical",
        "scope",
        "class_tag",
        "probability",
        "probability_by",
    ),
    "stake": ("id", "type", "amount", "currency", "period", "count_periods", "direction", "note"),
}
"""The content of each basis item kind (§3.3 ``ITEM``); every item row carries its own salt."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SealItem:
    """One basis item to seal: its kind, its scoped code (``O-01``, ``FT-003``, ``A-02``; the
    stake's id as text for stakes), its stored row and its salt."""

    kind: str
    code: str
    row: Mapping[str, str | int | None]
    salt: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EditionDraft:
    """Everything ``dec_editions`` needs from the hashing; the caller adds reason, review id, the
    unverifiable share at seal, ``reconstructed`` and inserts the row."""

    n: int
    fields_json: str
    field_salts_json: str
    field_hashes_json: str
    items_json: str
    seal_hash: str
    sealed_at: str  # format_instant text, exactly as stored and hashed
    sealed_by: str


# --------------------------------------------------------------------------------------------------
# CFJ-1


def normalise(x: object) -> object:
    """NFC strings; bool, None and int as they are; Decimal as plain digits; date and datetime as
    ISO text; lists, tuples and dicts recursively; a float raises ``TypeError``."""
    if isinstance(x, str):
        return unicodedata.normalize("NFC", x)
    if x is None or isinstance(x, bool | int):
        return x
    if isinstance(x, float):
        raise TypeError("CFJ-1 refuses floats; use Decimal strings or int")
    if isinstance(x, Decimal):
        if not x.is_finite():
            raise TypeError("CFJ-1 refuses non-finite decimals")
        return format(x, "f")
    if isinstance(x, date | datetime):
        return x.isoformat()
    if isinstance(x, list | tuple):
        return [normalise(v) for v in x]
    if isinstance(x, Mapping):
        return {_key(k): normalise(v) for k, v in x.items()}
    raise TypeError(f"CFJ-1 cannot encode {type(x).__name__}")


def _key(k: object) -> str:
    return unicodedata.normalize("NFC", k) if isinstance(k, str) else str(k)


def cfj(obj: object) -> bytes:
    """CFJ-1: ``json.dumps(normalise(obj), sort_keys=True, ensure_ascii=False,
    separators=(',', ':'), allow_nan=False).encode('utf-8')``."""
    return json.dumps(
        normalise(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def cfj_text(obj: object) -> str:
    """CFJ-1 as text, the form ``TEXT`` JSON columns store."""
    return cfj(obj).decode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unit_hash(salt: str, content: object) -> str:
    """``sha256(salt.encode('ascii') + cfj(content)).hexdigest()``."""
    return sha256_hex(salt.encode("ascii") + cfj(content))


# --------------------------------------------------------------------------------------------------
# Basis values and items (stored rows in, hash inputs out)


def _stored(value: object) -> object:
    """A stored value as SQLite returns it: booleans are 0/1 (see the module's spec note)."""
    if isinstance(value, bool):
        return int(value)
    return value


def basis_value(decision: Mapping[str, str | int | None], key: str) -> object:
    """The value of basis field ``key`` from a stored ``dec_decisions`` row (``unknowns`` is the
    parsed ``unknowns_json`` list)."""
    if key not in BASIS_FIELDS:
        raise KeyError(f"{key} is not a basis field")
    if key == "unknowns":
        raw = decision.get("unknowns_json")
        if raw is None or raw == "":
            return []
        parsed = json.loads(str(raw))
        if not isinstance(parsed, list):
            raise TypeError("unknowns_json must hold a JSON array")
        return parsed
    return _stored(decision[key])


def item_content(kind: str, row: Mapping[str, str | int | None], *, code: str) -> dict[str, object]:
    """``ITEM[kind](row)`` of §3.3: the keys of ``ITEM_KEYS[kind]`` from the stored row, with
    ``code`` supplied by the caller."""
    keys = ITEM_KEYS[kind]
    out: dict[str, object] = {}
    for k in keys:
        out[k] = code if k == "code" else _stored(row[k])
    return out


# --------------------------------------------------------------------------------------------------
# The seal


def seal_envelope(
    *,
    public_id: str,
    n: int,
    field_hashes: Mapping[str, str],
    items: Sequence[Sequence[str]],
    sealed_at: str,
    sealed_by: str,
    cv: int = CANON_VERSION,
) -> dict[str, object]:
    """``{'cv', 'decision', 'edition', 'field_hashes', 'items', 'sealed_at', 'sealed_by'}``."""
    return {
        "cv": cv,
        "decision": public_id,
        "edition": n,
        "field_hashes": dict(field_hashes),
        "items": [list(i) for i in items],
        "sealed_at": sealed_at,
        "sealed_by": sealed_by,
    }


def seal_hash(envelope: Mapping[str, object]) -> str:
    """``sha256(cfj(envelope)).hexdigest()``."""
    return sha256_hex(cfj(envelope))


def item_hash(item: SealItem) -> str:
    """The hash of one basis item: ``unit_hash(row.salt, ITEM[kind](row))``."""
    return unit_hash(item.salt, item_content(item.kind, item.row, code=item.code))


def build_edition(
    *,
    public_id: str,
    n: int,
    decision: Mapping[str, str | int | None],
    items: Sequence[SealItem],
    sealed_at: str,
    sealed_by: str,
) -> EditionDraft:
    """Seal edition ``n`` (§3.3 ``seal``): one fresh salt per basis field (``new_salt``), the field
    hashes, the sorted ``[kind, code, item_hash]`` list and the seal hash over the envelope."""
    fields = {k: basis_value(decision, k) for k in BASIS_FIELDS}
    salts = {k: new_salt() for k in BASIS_FIELDS}
    hashes = {k: unit_hash(salts[k], fields[k]) for k in BASIS_FIELDS}
    sealed = sorted([i.kind, i.code, item_hash(i)] for i in items)
    env = seal_envelope(
        public_id=public_id,
        n=n,
        field_hashes=hashes,
        items=sealed,
        sealed_at=sealed_at,
        sealed_by=sealed_by,
    )
    return EditionDraft(
        n=n,
        fields_json=cfj_text(fields),
        field_salts_json=cfj_text(salts),
        field_hashes_json=cfj_text(hashes),
        items_json=cfj_text(sealed),
        seal_hash=seal_hash(env),
        sealed_at=sealed_at,
        sealed_by=sealed_by,
    )


# --------------------------------------------------------------------------------------------------
# Integrity, the read side (§3.3 ``integrity``)


def seal_items(d: DecisionView) -> list[SealItem]:
    """What an edition of ``d`` seals now: its options, its ground facts, its active assumptions
    and its planned stakes (§3.3 ``basis_items``), over a view whose voided rows are gone."""
    items: list[SealItem] = []
    items += [
        SealItem(kind="option", code=o.code, row=o.stored, salt=o.salt)
        for o in d.options
        if o.decision_id == d.id and o.fork_id is None
    ]
    items += [
        SealItem(kind="ground", code=f.code, row=f.stored, salt=f.salt)
        for f in d.facts
        if f.phase == "ground" and f.voided_at is None
    ]
    items += [
        SealItem(kind="assumption", code=a.code, row=a.stored, salt=a.salt)
        for a in d.assumptions
        if a.status == "active"
    ]
    items += [
        SealItem(kind="stake", code=str(s.id), row=s.stored, salt=s.salt)
        for s in d.stakes
        if s.planned
    ]
    return items


def _item_row(d: DecisionView, kind: str, code: str) -> RowStamp | None:
    rows: Sequence[RowStamp]
    if kind == "option":
        rows = [o for o in d.options if o.decision_id == d.id and o.code == code]
    elif kind == "ground":
        rows = [f for f in d.facts if f.code == code]
    elif kind == "assumption":
        rows = [a for a in d.assumptions if a.code == code]
    elif kind == "stake":
        rows = [s for s in d.stakes if str(s.id) == code]
    else:
        return None
    return rows[0] if rows else None


def _edition_stored(e: EditionView, column: str, fallback: object) -> object:
    return e.stored.get(column, fallback)


def _empty(value: object) -> bool:
    return value is None or value == "" or value == []


def verify_edition(
    d: DecisionView, e: EditionView, *, rows: DecisionView | None = None
) -> IntegrityLine:
    """Recompute one edition's seal, field hashes and item hashes (§3.3).

    ``rows`` is where the sealed items are looked up (default ``d``). A view at ``T`` has dropped
    the rows voided by ``T``, but an edition still lists the rows it sealed, voided since or not:
    pass the loaded decision (every row) so a later void is not read as a changed seal.
    """
    source = d if rows is None else rows
    seal12 = e.seal_hash[:12]
    sealed_at = _edition_stored(e, "sealed_at", None)
    if not isinstance(sealed_at, str):
        sealed_at = format_instant(e.sealed_at)
    env = seal_envelope(
        public_id=d.public_id,
        n=e.n,
        field_hashes=json.loads(e.field_hashes_json),
        items=json.loads(e.items_json),
        sealed_at=sealed_at,
        sealed_by=e.sealed_by,
        cv=e.canon_version,
    )
    if seal_hash(env) != e.seal_hash:
        return IntegrityLine(edition=e.n, status="changed", items=("seal",), seal12=seal12)
    fields = json.loads(e.fields_json)
    salts = json.loads(e.field_salts_json)
    hashes = json.loads(e.field_hashes_json)
    erased_fields = set(json.loads(e.erased_fields_json or "[]"))
    bad: list[str] = []
    erased = 0
    for k, h in hashes.items():
        if k in erased_fields:
            erased += 1
            continue
        if k not in fields or not salts.get(k) or unit_hash(salts[k], fields[k]) != h:
            bad.append(k)
    for kind, code, h in json.loads(e.items_json):
        row = _item_row(source, kind, code)
        if row is None:
            bad.append(f"{kind} {code}")
            continue
        if getattr(row, "erased_tx", None):
            erased += 1
            continue
        salt = getattr(row, "salt", "")
        content = item_content(kind, row.stored, code=code)
        if not salt or unit_hash(salt, content) != h:
            bad.append(f"{kind} {code}")
    status: IntegrityStatus = "changed" if bad else ("ok_with_erasures" if erased else "ok")
    return IntegrityLine(edition=e.n, status=status, items=tuple(bad), seal12=seal12)


def integrity_lines(d: DecisionView, *, rows: DecisionView | None = None) -> list[IntegrityLine]:
    """Per edition ``ok`` / ``ok_with_erasures`` / ``changed``; the live line ``drift`` when a
    basis field changed outside revise; ``completion_pending`` with what waits for the next
    edition (§3.3). ``changed`` and ``drift`` come first.

    Spec notes: on a record whose completion is pending, a basis field that was empty in the current
    edition and is filled now is a completion, not drift; a field erased from the current edition
    cannot be compared, so it is never drift. ``rows`` is passed to ``verify_edition``: on a view at
    ``T``, the loaded decision with every row, so the editions are those visible at ``T`` and the
    items they sealed are found even when voided since.
    """
    editions = sorted(d.editions, key=lambda e: e.n)
    lines = [verify_edition(d, e, rows=rows) for e in editions]
    live: list[IntegrityLine] = []
    current = next((e for e in editions if e.n == d.current_edition), None)
    sealed: dict[str, object] = json.loads(current.fields_json) if current else {}
    erased = set(json.loads(current.erased_fields_json or "[]")) if current else set()
    if d.status == "active" and current is not None:
        drift = [
            k
            for k in BASIS_FIELDS
            if k not in erased
            and normalise(basis_value(d.stored, k)) != sealed.get(k)
            and not (d.completion_pending and _empty(sealed.get(k)))
        ]
        if drift:
            live.append(IntegrityLine(edition="live", status="drift", items=tuple(drift)))
    if d.completion_pending:
        pending = [
            k
            for k in BASIS_FIELDS
            if current is not None
            and _empty(sealed.get(k))
            and normalise(basis_value(d.stored, k)) != sealed.get(k)
        ]
        pending += [
            f"{i.kind} {i.code}" for i in seal_items(d) if i.row.get("added_in_edition") is None
        ]
        live.append(
            IntegrityLine(edition="live", status="completion_pending", items=tuple(pending))
        )
    bad_first = sorted(
        [*lines, *live], key=lambda line: 0 if line.status in ("changed", "drift") else 1
    )
    return bad_first


def integrity_report(d: DecisionView) -> IntegrityReport:
    return IntegrityReport(decision_ref=d.public_id, lines=tuple(integrity_lines(d)))
