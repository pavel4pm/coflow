"""``EvidenceResolver``: how DEC validates evidence it does not own.

Skeleton file (spec §4.2, §12.1). Implemented by evidence owners (built-ins in I2; SIG at stage 1,
MTG at stage 5, GOL at stage 3, FIN at 8.1a) and used by DEC in the prepare phase of ``add_fact``,
``record_check``, ``record_reading`` and grounds, as reads before the unit of work (AP-4).

Rules DEC applies with it: a journal-class source is refused (``JOURNAL_CLASS_INPUT``, P-2); a quote
that does not match is refused for owner input (``QUOTE_NOT_IN_SOURCE``) and stored with
``quote_verified = 0`` for imports; an unresolvable ref is stored with ``quote_verified = 0``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

__all__ = ["Evidence", "EvidenceResolver", "normalise_quote", "quote_in_text"]

_WS = re.compile(r"\s+")


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    """A resolved piece of evidence; ``data_class`` is 'journal', 'financial', 'work' or
    'system'."""

    kind: str
    ref: str
    occurred_at: date | datetime | None
    data_class: str
    text: str | None = None  # for the quote check only; never stored by DEC
    offset: int | None = None


def normalise_quote(text: str) -> str:
    """NFC plus whitespace collapsed to single spaces: the one normalisation for quote checks."""
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


def quote_in_text(quote: str, text: str) -> bool:
    """Exact substring after ``normalise_quote`` on both sides (§4.2)."""
    q = normalise_quote(quote)
    return bool(q) and q in normalise_quote(text)


@runtime_checkable
class EvidenceResolver(Protocol):
    """``kinds`` are the evidence kinds it resolves: 'segment', 'message', 'session', 'document',
    'app_envelope', ..."""

    kinds: frozenset[str]

    def resolve(self, ref: str) -> Evidence | None: ...

    def quote_matches(self, ref: str, quote: str) -> bool:
        """Exact substring after NFC and whitespace normalisation (use ``quote_in_text``)."""
        ...
