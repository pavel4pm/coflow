"""The independent health oracle: a second implementation of spec §3.7 written from the text only,
without reading ``modules/dec/domain/health.py`` (spec §12.5). It must agree with the module on
the whole enumerated space of §3.7 (AT-D3); a disagreement is resolved by correcting the spec
text first, then the losing side.

It may import ``coflow.modules.dec.domain.model`` (the views) and ``coflow.kernel``, never
another file of ``coflow.modules.dec.domain`` (``tests/architecture`` checks this).

Owned by track S (store, import, shadow); increment I1, spec §12.2.

What it implements, all over the rows visible at ``T`` on the knowledge axis (``K(row) <= T``,
§3.15) with voided rows (``voided_at <= T``) excluded:

- §3.4 ``effective_state`` (and ``latest_assessment``, ordered by observed time, then K);
- §3.6 ``assumption_due``, ``check_due``, ``floor_date`` and the three date patterns of the table
  (after HTML unescaping, in order of appearance; ``day.month`` takes the year of the base, or the
  next year when it would fall before the base);
- §3.7 ``pool``, ``unverifiable_share``, ``ground``, ``timeliness``, ``health`` and ``is_bet``.

Readings of the spec text where it is terse (each is the plain meaning of the words):

- ``observed_date`` and every other event date: an instant's date in the owner's zone, a date as
  it is, an unknown time falls back to the date of ``K``.
- ``reviewed_on_or_after(d, day)``: a visible, non-voided review whose occurred date (unknown: its
  K date) is on or after ``day``.
- ``last_activity_date``: the latest event date of the visible, non-voided facts, assessments,
  readings and reviews; if none, the activation date, or the decided date for a mirror.
- Terminal and draft labels carry no ground and no timeliness here; only the label is computed.
- ``K(a) = v1 created_at for imports`` (§3.6 ``floor_date``): an imported assumption whose basis
  changed in the source is a successor row known from that snapshot, so for a mirror the floor's
  K is the earliest K of the assumptions with the same ``origin_ref`` (the same source row).
- An imported, reconstructed assessment with no observed time states a state but no day: it
  decides the effective state but does not date the floor, ``assessed_since`` or the last activity.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from coflow.kernel.context import EvalTime, local_date, start_of_local_day
from coflow.modules.dec.domain.model import (
    AssumptionView,
    CheckView,
    DecConfig,
    DecisionView,
)

__all__ = ["OracleHealth", "dates_in", "oracle_health"]

_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)"),
    re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(20\d{2})(?!\d)"),
    re.compile(r"(?<![\d.,])(\d{2})\.(\d{2})(?![\d.,])"),
)
_TERMINAL = {"closed": "CLOSED", "cancelled": "CANCELLED", "superseded": "SUPERSEDED"}


@dataclass(frozen=True, slots=True)
class OracleHealth:
    label: str
    ground: str | None
    timeliness: frozenset[str]
    share: Decimal | None
    bet: bool
    states: dict[str, str] = field(default_factory=dict)
    pool: tuple[str, ...] = ()


# ----------------------------------------------------------------------------------------- dates


def dates_in(text: str | None, base: date) -> list[date]:
    """The dates of the §3.6 table in ``text``, in order of appearance (invalid ones skipped)."""
    if not text:
        return []
    text = html.unescape(text)
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []
    for index, pattern in enumerate(_PATTERNS):
        for m in pattern.finditer(text):
            if any(s <= m.start() < e for s, e in taken):
                continue  # a day.month inside a day.month.year already found
            try:
                if index == 0:
                    day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif index == 1:
                    day = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    day = date(base.year, int(m.group(2)), int(m.group(1)))
                    if day < base:
                        day = date(base.year + 1, day.month, day.day)
            except ValueError:
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), day))
    return [d for _, d in sorted(found, key=lambda x: x[0])]


# ------------------------------------------------------------------------------ visible rows at T


def _k(row: Any) -> datetime:
    return row.origin_recorded_at or row.recorded_at


def _visible(row: Any, t: EvalTime) -> bool:
    if _k(row) > t.instant:
        return False
    voided = getattr(row, "voided_at", None)
    return voided is None or voided > t.instant


def _event_date(value: object, row: Any, tz: str) -> date:
    if isinstance(value, datetime):
        return local_date(value, tz)
    if isinstance(value, date):
        return value
    return local_date(_k(row), tz)


def _sort_instant(value: object, row: Any, tz: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return start_of_local_day(value, tz)
    return _k(row)


class _Decision:
    """A decision as seen at T, with the helpers of §3.6 and §3.7."""

    def __init__(self, d: DecisionView, t: EvalTime, cfg: DecConfig) -> None:
        self.d, self.t, self.cfg, self.tz = d, t, cfg, cfg.timezone

    # -- rows
    def active_assumptions(self) -> list[AssumptionView]:
        rows = [a for a in self.d.assumptions if a.status == "active" and _visible(a, self.t)]
        return sorted(rows, key=lambda a: (a.position, a.code_n))

    def assessments(self, a: AssumptionView) -> list[CheckView]:
        rows = [c for c in a.checks if c.kind == "assessment" and _visible(c, self.t)]
        return sorted(rows, key=lambda c: (_sort_instant(c.observed_at, c, self.tz), _k(c), c.id))

    def latest_assessment(self, a: AssumptionView) -> CheckView | None:
        rows = self.assessments(a)
        return rows[-1] if rows else None

    def observed_date(self, c: CheckView) -> date:
        return _event_date(c.observed_at, c, self.tz)

    def decided_date(self) -> date | None:
        value = self.d.decided_at
        if isinstance(value, datetime):
            return local_date(value, self.tz)
        if isinstance(value, date):
            return value
        return None

    # -- §3.4 / §3.6
    def effective_state(self, a: AssumptionView) -> str:
        last = self.latest_assessment(a)
        if last is not None:
            return str(last.state)
        if a.data_source_kind == "none":
            return "UNVERIFIABLE"
        due, _ = self.assumption_due(a)
        if due is None or due > self.t.date:
            return "NOT_YET_DUE"
        return "UNCHECKED"

    def dated(self, a: AssumptionView) -> list[CheckView]:
        return [c for c in self.assessments(a) if not (c.reconstructed and c.observed_at is None)]

    def floor_date(self, a: AssumptionView) -> date:
        dated = self.dated(a)
        observed = self.observed_date(dated[-1]) if dated else date.min
        k = local_date(_k(a), self.tz)
        if self.d.mirror_of and a.origin_ref:
            k = min(
                [k]
                + [
                    local_date(_k(p), self.tz)
                    for p in self.d.assumptions
                    if p.origin_ref == a.origin_ref
                ]
            )
        return max(observed, k)

    def assumption_due(self, a: AssumptionView) -> tuple[date | None, str | None]:
        if a.status != "active":
            return None, None
        if a.next_check_at:
            return a.next_check_at, "explicit"
        floor = self.floor_date(a)
        if a.by_date and a.by_date > floor:
            return a.by_date, "by_date"
        base = self.decided_date() or local_date(_k(self.d), self.tz)
        for text in (a.threshold_text, a.statement):
            for day in dates_in(text, base):
                if day > floor:
                    return day, "text"
        if self.d.review_due:
            return self.d.review_due, "review"
        return None, None

    def assessed_since(self, a: AssumptionView, day: date) -> bool:
        return any(self.observed_date(c) >= day for c in self.dated(a))

    def check_due(self, a: AssumptionView) -> tuple[date, str] | None:
        if self.effective_state(a) in ("VIOLATED", "UNVERIFIABLE"):
            return None
        due, source = self.assumption_due(a)
        if source not in ("explicit", "by_date", "text") or due is None or due > self.t.date:
            return None
        if self.assessed_since(a, due):
            return None
        return due, str(source)

    def reviews(self) -> Iterator[Any]:
        return (r for r in self.d.reviews if _visible(r, self.t))

    def reviewed_on_or_after(self, day: date) -> bool:
        return any(_event_date(r.occurred_at, r, self.tz) >= day for r in self.reviews())

    def last_activity_date(self) -> date | None:
        days: list[date] = []
        days += [
            _event_date(f.occurred_at, f, self.tz) for f in self.d.facts if _visible(f, self.t)
        ]
        for a in self.d.assumptions:
            days += [self.observed_date(c) for c in self.dated(a)]
            days += [
                _event_date(r.observed_at, r, self.tz) for r in a.readings if _visible(r, self.t)
            ]
        days += [_event_date(r.occurred_at, r, self.tz) for r in self.reviews()]
        if days:
            return max(days)
        if self.d.mirror_of:
            return self.decided_date()
        if self.d.activated_at is not None:
            return local_date(self.d.activated_at, self.tz)
        return None

    # -- §3.7
    def pool(self) -> list[AssumptionView]:
        act = self.active_assumptions()
        critical = [a for a in act if a.is_critical]
        return critical or act

    def unverifiable_share(self) -> Decimal | None:
        p = self.pool()
        if not p:
            return None
        unverifiable = sum(self.effective_state(a) == "UNVERIFIABLE" for a in p)
        return Decimal(unverifiable) / len(p)

    def ground(self) -> str:
        act = self.active_assumptions()
        if not act:
            return "NOT_MONITORED" if self.d.depth == "light" else "NO_ASSUMPTIONS"
        p = self.pool()
        codes_in_pool = {a.id for a in p}
        s = {a.id: self.effective_state(a) for a in act}
        if any(s[a.id] == "VIOLATED" for a in p):
            return "VIOLATED"
        share = self.unverifiable_share()
        assert share is not None
        if share > self.cfg.unverifiable_share_limit:
            return "INSUFFICIENT"
        drifting = any(s[a.id] == "DRIFTING" for a in p) or any(
            a.id not in codes_in_pool and s[a.id] == "VIOLATED" for a in act
        )
        if drifting:
            return "DRIFTING"
        checkable = [a for a in p if s[a.id] != "UNVERIFIABLE"]
        if checkable and all(s[a.id] == "HOLDING" for a in checkable):
            return "HOLDING"
        return "AWAITING"

    def timeliness(self) -> frozenset[str]:
        kinds: set[str] = set()
        rd = self.d.review_due
        today = self.t.date
        if rd is None:
            kinds.add("NO_REVIEW_DATE")
        elif rd < today and not self.reviewed_on_or_after(rd):
            kinds.add("REVIEW_OVERDUE")
        elif rd == today and not self.reviewed_on_or_after(rd):
            kinds.add("DUE_TODAY")
        for a in self.active_assumptions():
            cd = self.check_due(a)
            if cd is not None and cd[0] < today:
                kinds.add("CHECK_OVERDUE")
        last = self.last_activity_date()
        if last is not None and (today - last).days > self.cfg.no_data_days:
            kinds.add("NO_DATA_SINCE")
        return frozenset(kinds or {"ON_SCHEDULE"})


def _label(g: str, t: frozenset[str], manual_flag: str | None) -> str:
    if manual_flag:
        return manual_flag
    if g == "VIOLATED":
        return "REVIEW_REQUIRED"
    if "REVIEW_OVERDUE" in t:
        return "STALE"
    if g in ("INSUFFICIENT", "NO_ASSUMPTIONS"):
        return "INSUFFICIENT_DATA"
    if (
        g == "DRIFTING"
        or t & {"NO_REVIEW_DATE", "CHECK_OVERDUE"}
        or ("NO_DATA_SINCE" in t and g == "HOLDING")
    ):
        return "WATCH"
    if g in ("HOLDING", "NOT_MONITORED"):
        return "ON_TRACK"
    return "AWAITING_CHECKS"


def oracle_health(d: DecisionView, t: EvalTime, cfg: DecConfig) -> OracleHealth:
    """§3.7 ``health(d, T)`` with both axes, the share and the ``bet`` badge."""
    if d.status in _TERMINAL:
        return OracleHealth(_TERMINAL[d.status], None, frozenset(), None, False)
    if d.status == "withdrawn":
        return OracleHealth("WITHDRAWN", None, frozenset(), None, False)
    if d.status == "draft":
        return OracleHealth("DRAFT", None, frozenset(), None, False)
    x = _Decision(d, t, cfg)
    g, kinds, share = x.ground(), x.timeliness(), x.unverifiable_share()
    states = {a.code: x.effective_state(a) for a in x.active_assumptions()}
    return OracleHealth(
        label=_label(g, kinds, d.manual_flag),
        ground=g,
        timeliness=kinds,
        share=share,
        bet=share is not None and share > cfg.unverifiable_share_limit,
        states=states,
        pool=tuple(a.code for a in x.pool()),
    )


def due_of(d: DecisionView, a: AssumptionView, t: EvalTime, cfg: DecConfig) -> Any:
    """§3.6 ``assumption_due`` of one assumption (for tests that pin due dates)."""
    return _Decision(d, t, cfg).assumption_due(a)
