"""The check-date table ported from v1 (spec §3.6): ``DATE_PATTERNS`` applied after HTML
unescaping, in order of appearance; ``dates_in(text, base)``. Its vectors are acceptance tests
(AT-D1).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

The rules, unchanged from v1:

- three patterns, tried in this order: ISO ``2026-11-15``; ``day.month.year`` with one or two
  digits for day and month (``15.11.2026``, ``5.11.2026``); ``day.month`` with exactly two digits
  each (``15.11``);
- a neighbouring digit, dot or comma means "not a date", so ``1.5``, ``0.80`` and ``12.5 %`` are
  never dates;
- an invalid calendar date (``31.02``) is skipped;
- a match lying inside an already found date (a ``day.month`` inside ``day.month.year``) is not
  taken twice;
- a ``day.month`` takes the year of ``base``, and the next year when it falls before ``base``;
- the result is in order of appearance in the text.

Locale formats arrive through CFG-3 as new versioned rows, each with its own vectors; the slice has
exactly this table (``DATE_TABLE_VERSION = 1``).

Spec note: ``base`` is required. v1 fell back to the host's "today" when a decision had no date; in
v2 the caller always has one (the decision's decided date, else its K date, §3.6), and a host date
would break determinism (§12.5).
"""

from __future__ import annotations

import html
import re
from datetime import date

__all__ = ["DATE_PATTERNS", "DATE_TABLE_VERSION", "dates_in"]

DATE_TABLE_VERSION = 1

DATE_PATTERNS: tuple[str, ...] = (
    r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)",  # 2026-11-15
    r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(20\d{2})(?!\d)",  # 15.11.2026, 5.11.2026
    r"(?<![\d.,])(\d{2})\.(\d{2})(?![\d.,])",  # 15.11: year of base; next year if earlier
)

_RX_ISO, _RX_DMY, _RX_DM = (re.compile(p) for p in DATE_PATTERNS)


def dates_in(text: str | None, base: date) -> list[date]:
    """Every date in ``text`` in order of appearance (see the module docstring for the rules)."""
    if not text:
        return []
    plain = html.unescape(str(text))
    found: list[tuple[int, int, date]] = []
    for rx, kind in ((_RX_ISO, "iso"), (_RX_DMY, "dmy"), (_RX_DM, "dm")):
        for m in rx.finditer(plain):
            try:
                if kind == "iso":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif kind == "dmy":
                    d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    d = date(base.year, int(m.group(2)), int(m.group(1)))
                    if d < base:
                        d = date(base.year + 1, d.month, d.day)
            except ValueError:
                continue  # not a calendar date (31.02), or 29.02 rolled into a non-leap year
            if any(m.start() >= s and m.end() <= e for s, e, _ in found):
                continue  # inside an already found date: the same date, not taken twice
            found.append((m.start(), m.end(), d))
    return [d for _, _, d in sorted(found, key=lambda x: x[0])]
