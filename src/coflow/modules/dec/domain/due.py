"""Due dates (spec §3.6): ``floor_date``, ``assumption_due`` (explicit, by-date, text, review),
``check_due``, ``assessed_since`` and THE one ``next_check_after`` that ``record_check``, buttons
and cards use (AT-D1, AT-D2).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

Every function works on a view at ``T`` (``states.view_at``) and excludes rows voided by ``T``.
``next_check_after`` is the single source of a next check date: the write (``record_check``, I2),
the likely actions of a question card (§3.9) and the card itself call it, so a date shown on a
button equals the date the write stores (v1 defect 2, AT-N11).

Spec notes (found in review):

- ``floor_date``'s K of an imported assumption is "v1 created_at for imports" (§3.6). When v1
  changes an assumption's basis in place, the importer stores a successor known from that
  snapshot, so the floor takes the earliest K among the mirror's assumptions with the same
  ``origin_ref`` (the same source row): due dates keep v1's base.
- The floor and ``assessed_since`` use ``states.dated_assessments``: an undated reconstructed
  assessment states a state, not a day.
"""

from __future__ import annotations

from datetime import date, timedelta

from coflow.kernel.context import EvalTime
from coflow.kernel.errors import RefusalCode, Refused
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.dates import dates_in
from coflow.modules.dec.domain.model import (
    AssumptionView,
    DecConfig,
    DecisionView,
    DueResult,
    NextCheck,
)

__all__ = [
    "MAX_NEXT_CHECK_DAYS",
    "STEP",
    "assessed_since",
    "assumption_due",
    "check_due",
    "floor_date",
    "next_check_after",
]

STEP: dict[str, int] = {"weekly": 7, "monthly": 30, "quarterly": 90}
"""Days added by a check frequency; ``ad_hoc`` clears the next date instead (no hidden +30)."""

MAX_NEXT_CHECK_DAYS = 730

_NONE = DueResult(due=None, source=None)


def floor_date(
    a: AssumptionView, T: EvalTime, cfg: DecConfig, *, decision: DecisionView | None = None
) -> date:
    """A date in the text or the by-date counts only if strictly later than this: the latest of the
    last dated assessment's observed date and the assumption's own K date (§3.6); see the module's
    spec notes for ``decision`` (an imported successor keeps the source row's K)."""
    dated = _states.dated_assessments(a, T, cfg)
    observed = _states.observed_date(dated[-1], cfg) if dated else date.min
    return max(observed, _basis_k_date(a, cfg, decision))


def _basis_k_date(a: AssumptionView, cfg: DecConfig, d: DecisionView | None) -> date:
    k = _states.k_date(a, cfg)
    if d is None or not d.mirror_of or not a.origin_ref:
        return k
    same_source = [_states.k_date(p, cfg) for p in d.assumptions if p.origin_ref == a.origin_ref]
    return min([k, *same_source])


def assumption_due(d: DecisionView, a: AssumptionView, T: EvalTime, cfg: DecConfig) -> DueResult:
    """``(date | None, source)`` (§3.6): an explicit next date; else the by-date, if later than the
    floor (structured beats text); else the first date in the threshold text, then in the
    statement, that is later than the floor; else the decision's review date."""
    if a.status != "active":
        return _NONE
    if a.next_check_at is not None:
        return DueResult(due=a.next_check_at, source="explicit")
    floor = floor_date(a, T, cfg, decision=d)
    if a.by_date is not None and a.by_date > floor:
        return DueResult(due=a.by_date, source="by_date")
    base = _states.decided_date(d, cfg) or _states.k_date(d, cfg)
    for text in (a.threshold_text, a.statement):
        for day in dates_in(text, base):
            if day > floor:
                return DueResult(due=day, source="text")
    if d.review_due is not None:
        return DueResult(due=d.review_due, source="review")
    return _NONE


def assessed_since(a: AssumptionView, day: date, T: EvalTime, cfg: DecConfig) -> bool:
    """A non-voided assessment observed on or after ``day`` exists (§3.6)."""
    return any(_states.observed_date(c, cfg) >= day for c in _states.dated_assessments(a, T, cfg))


def check_due(d: DecisionView, a: AssumptionView, T: EvalTime, cfg: DecConfig) -> DueResult | None:
    """The check that has fallen due and is not answered yet, or ``None`` (§3.6).

    VIOLATED waits as a review question and UNVERIFIABLE has nothing to check with, so neither is
    a check due; a review-sourced date is covered by the review reason, never repeated here.
    """
    if _states.effective_state(d, a, T, cfg) in ("VIOLATED", "UNVERIFIABLE"):
        return None
    due = assumption_due(d, a, T, cfg)
    if due.source not in ("explicit", "by_date", "text") or due.due is None or due.due > T.date:
        return None
    if assessed_since(a, due.due, T, cfg):
        return None
    return due


def next_check_after(
    a: AssumptionView, observed_date: date, explicit: date | None = None
) -> NextCheck:
    """THE next check date after a check observed on ``observed_date`` (§3.6).

    An explicit date must lie after the observed date and within 730 days of it
    (``NEXT_CHECK_OUT_OF_RANGE``). Otherwise the frequency steps from the observed date; ad hoc
    clears the date (it falls back to the threshold text or the review); without a frequency a
    future ``next_check_at`` is kept and a past one is dropped.
    """
    if explicit is not None:
        latest = observed_date + timedelta(days=MAX_NEXT_CHECK_DAYS)
        if not (observed_date < explicit <= latest):
            raise Refused(
                RefusalCode.NEXT_CHECK_OUT_OF_RANGE,
                f"the next check must fall after {observed_date} and no later than {latest}",
            )
        return NextCheck(next=explicit, rule="explicit")
    if a.check_frequency in STEP:
        return NextCheck(
            next=observed_date + timedelta(days=STEP[a.check_frequency]), rule="frequency"
        )
    if a.check_frequency == "ad_hoc":
        return NextCheck(next=None, rule="ad_hoc_clear")
    if a.next_check_at is not None and a.next_check_at > observed_date:
        return NextCheck(next=a.next_check_at, rule="kept")
    return NextCheck(next=None, rule="dropped" if a.next_check_at is not None else "none")
