"""Canonical ids and scoped codes, and tolerant input (IDN-2, IDN-9, spec §2.2).

Owned by track K; increment I1, spec §12.2. The signatures below are fixed by the skeleton because
tracks S, D and X render and parse codes; the track implements them (AT-K2, AT-K3).

The canonical form: each parameter is ``prefix-counter`` with a fixed-width counter; a hyphen joins
the parts of one parameter, an underscore separates parameters, and there is no colon anywhere:
``D-0042``, ``D-0042_A-03``, ``D-0042_A-03_CK-002``, ``Q-0007_O-01``. A cross-system reference is
``<ISSUER>_<id as the issuer wrote it>``: ``V1_D907``, ``CF2LOG_D-037``. Input is tolerant, output
is canonical: ``D907``, ``d907``, ``D 907``, ``d-907``, ``D0907`` and the locale's look-alike
letters resolve to ``D-0907``; ``D907 A2``, ``D907_A2``, ``D907/A2`` and ``D-0907_A02`` resolve to
``D-0907_A-02``. Only fields declared as references are parsed, never free text.

Rules the implementation adds (spec notes):

- A counter fills its width exactly: ``D`` runs from ``D-0001`` to ``D-9999``. ``render`` of a
  number outside ``1 .. 10**width - 1`` is a ``ContractViolation``; tolerant input with too many
  digits names no id (``NotFound``).
- A scoped code follows its parent: ``A``, ``E``, ``R``, ``L``, ``FT`` under ``D``; ``O`` under
  ``D`` or ``Q``; ``CK`` and ``RD`` under ``A``. ``Q-0007_A-01`` is no id.
- An issuer code is upper-case letters and digits and never a registered prefix followed by digits
  (``V1`` and ``CF2LOG`` are issuers; ``D907`` could not be one), so ``V1_D907`` is always a foreign
  reference and ``D907_A1`` always a tolerant native one.
- Look-alike letters: ``canonical`` applies the R1 locale packs (CFG-3: English and Russian) unless
  the caller passes its own mapping. The Russian pack maps the Cyrillic letters an owner types for
  the id letters: Д → D, Ф → F, Л → L and the visual twins А, Е, К, О, С, Т. Р is left out on
  purpose: it looks like P but stands for R.
- A bare number (``907``) is ``Ambiguous`` between the top-level prefixes; the owning module
  filters the candidates by existence.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from coflow.kernel.errors import Ambiguous, ContractViolation, NotFound, Refused
from coflow.kernel.ids.registry import prefix_spec, prefix_table

__all__ = [
    "LOCALE_LOOK_ALIKES",
    "ParsedRef",
    "canonical",
    "foreign_ref",
    "is_issuer_code",
    "normalise_input",
    "parse",
    "render",
    "render_scoped",
]

_CYRILLIC = {
    "А": "A",
    "Д": "D",
    "Е": "E",
    "К": "K",
    "Л": "L",
    "О": "O",
    "С": "C",
    "Т": "T",
    "Ф": "F",
}
LOCALE_LOOK_ALIKES: Mapping[str, Mapping[str, str]] = {
    "en": {},
    "ru": {**_CYRILLIC, **{k.lower(): v.lower() for k, v in _CYRILLIC.items()}},
}
_DEFAULT_LOOK_ALIKES: Mapping[str, str] = {
    k: v for pack in LOCALE_LOOK_ALIKES.values() for k, v in pack.items()
}

_PART = re.compile(r"^([A-Z]{1,3})-(\d+)$")
_ISSUER = re.compile(r"^[A-Z][A-Z0-9]{0,15}$")
_UNIT = re.compile(r"([A-Z]+)[ \t\-]*(\d+)")
_UNIT_SEP = re.compile(r"[\s_/]*")
_SOURCE_ID = re.compile(r"^[^\s:]+$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedRef:
    """A parsed canonical reference: ``parts`` is ((prefix, n), ...), outermost first;
    ``issuer`` is set for a foreign reference (whose ``source_id`` is kept as written)."""

    parts: tuple[tuple[str, int], ...]
    issuer: str | None = None
    source_id: str | None = None

    @property
    def canonical(self) -> str:
        if self.issuer is not None:
            return f"{self.issuer}_{self.source_id}"
        return "_".join(render(prefix, n) for prefix, n in self.parts)

    @property
    def is_foreign(self) -> bool:
        return self.issuer is not None

    @property
    def leaf(self) -> tuple[str, int]:
        """The innermost part: ``('A', 3)`` for ``D-0042_A-03``."""
        if not self.parts:
            raise ContractViolation("a foreign reference has no parts")
        return self.parts[-1]

    @property
    def root(self) -> str:
        """The top-level id: ``D-0042`` for ``D-0042_A-03_CK-002``."""
        if not self.parts:
            raise ContractViolation("a foreign reference has no parts")
        prefix, n = self.parts[0]
        return render(prefix, n)

    @property
    def parent(self) -> str | None:
        """The canonical parent: ``D-0042_A-03`` for ``D-0042_A-03_CK-002``; None at the top."""
        if len(self.parts) < 2:
            return None
        return "_".join(render(p, n) for p, n in self.parts[:-1])


def render(prefix: str, n: int) -> str:
    """``render('D', 907) == 'D-0907'``; ``Refused(PREFIX_UNKNOWN)`` for an unregistered prefix."""
    spec = prefix_spec(prefix)
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n < 10**spec.width:
        raise ContractViolation(f"{prefix} counts 1 to {10**spec.width - 1}, not {n!r}")
    return f"{prefix}-{n:0{spec.width}d}"


def render_scoped(parent_ref: str, prefix: str, n: int) -> str:
    """``render_scoped('D-0042', 'A', 3) == 'D-0042_A-03'``."""
    parent = parse(parent_ref)
    if parent.is_foreign:
        raise ContractViolation(f"{parent_ref} is a foreign reference; codes scope native ids")
    spec = prefix_spec(prefix)
    if parent.leaf[0] not in spec.scoped_under:
        raise ContractViolation(f"{prefix} is not scoped under {parent.leaf[0]}")
    return f"{parent.canonical}_{render(prefix, n)}"


def is_issuer_code(code: str) -> bool:
    """An issuer code: letters and digits, never a registered prefix followed by digits."""
    if not _ISSUER.match(code):
        return False
    letters = re.match(r"^([A-Z]+)(\d*)$", code)
    return not (letters and letters.group(1) in prefix_table())


def foreign_ref(issuer: str, source_id: str) -> str:
    """``foreign_ref('V1', 'D907') == 'V1_D907'``."""
    if not is_issuer_code(issuer):
        raise ContractViolation(f"{issuer!r} is not an issuer code")
    if not source_id or not _SOURCE_ID.match(source_id):
        raise ContractViolation(f"{source_id!r} is not a source id (no spaces, no colon)")
    return f"{issuer}_{source_id}"


def _chain(parts: list[tuple[str, int]], text: str) -> None:
    """Refuse a sequence whose scoping is wrong (``Q-0007_A-01``)."""
    for i, (prefix, _n) in enumerate(parts):
        spec = prefix_spec(prefix)
        if i == 0 and spec.scoped_under:
            raise NotFound(text, f"{prefix} is a scoped code; it follows its parent")
        if i > 0 and parts[i - 1][0] not in spec.scoped_under:
            raise NotFound(text, f"{prefix} is not scoped under {parts[i - 1][0]}")


def parse(text: str) -> ParsedRef:
    """Parse a canonical reference; ``parse(render(...))`` is the identity (AT-K2)."""
    if not isinstance(text, str) or not text or text != text.strip():
        raise NotFound(str(text), "not a canonical id")
    segments = text.split("_")
    head = segments[0]
    if _PART.match(head) is None:
        if len(segments) > 1 and is_issuer_code(head):
            source = "_".join(segments[1:])
            if _SOURCE_ID.match(source):
                return ParsedRef(parts=(), issuer=head, source_id=source)
        raise NotFound(text, "not a canonical id")
    parts: list[tuple[str, int]] = []
    for seg in segments:
        m = _PART.match(seg)
        if m is None:
            raise NotFound(text, "not a canonical id")
        prefix, digits = m.group(1), m.group(2)
        spec = prefix_spec(prefix)
        if len(digits) != spec.width or int(digits) < 1:
            raise NotFound(text, f"{prefix} has exactly {spec.width} digits, from 1")
        parts.append((prefix, int(digits)))
    _chain(parts, text)
    return ParsedRef(parts=tuple(parts))


def normalise_input(text: str, look_alikes: Mapping[str, str] | None = None) -> str:
    """NFKC, look-alike letters to Latin, trimmed, upper case: the first step of every lookup."""
    mapping = _DEFAULT_LOOK_ALIKES if look_alikes is None else look_alikes
    s = unicodedata.normalize("NFKC", text)
    s = "".join(mapping.get(ch, ch) for ch in s)
    return s.strip().upper()


def _units(s: str) -> list[tuple[str, int]] | None:
    units: list[tuple[str, int]] = []
    pos = 0
    while pos < len(s):
        if units:
            sep = _UNIT_SEP.match(s, pos)
            pos = sep.end() if sep else pos
        m = _UNIT.match(s, pos)
        if m is None:
            return None
        units.append((m.group(1), int(m.group(2))))
        pos = m.end()
    return units or None


def canonical(text: str, *, look_alikes: Mapping[str, str] | None = None) -> str:
    """Tolerant input to the canonical form (AT-K3). ``look_alikes`` comes from the CFG-3 locale
    pack (for example a Cyrillic letter for ``D``). Raises ``NotFound`` when the text is no id."""
    if not isinstance(text, str):
        raise NotFound(str(text), "not an id")
    s = normalise_input(text, look_alikes)
    if not s:
        raise NotFound(text, "empty")
    try:
        return parse(s).canonical
    except (NotFound, Refused):
        pass
    if s.isdigit():
        n = int(s)
        candidates = [
            render(p.prefix, n)
            for p in prefix_table().values()
            if not p.scoped_under and 1 <= n < 10**p.width
        ]
        raise Ambiguous(candidates, f"{text!r} is a bare number")
    head, sep, rest = _head(s)
    if sep and rest and is_issuer_code(head) and _SOURCE_ID.match(rest):
        return f"{head}_{rest}"
    units = _units(s)
    if units is None:
        raise NotFound(text, "not an id")
    for prefix, n in units:
        spec = prefix_spec(prefix)  # Refused(PREFIX_UNKNOWN) for an unknown prefix
        if not 1 <= n < 10**spec.width:
            raise NotFound(text, f"{prefix} has {spec.width} digits")
    _chain(units, text)
    return "_".join(render(p, n) for p, n in units)


def _head(s: str) -> tuple[str, str, str]:
    m = re.match(r"^([^\s_/]+)([\s_/]+)(.*)$", s)
    if m is None:
        return s, "", ""
    return m.group(1), m.group(2), m.group(3)
