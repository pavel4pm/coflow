"""Assumption states (spec §3.4) and visibility (§3.15): ``visible``, ``voided_by``, ``view_at``,
``latest_assessment``, ``effective_state`` with the computed ``NOT_YET_DUE`` and ``UNCHECKED``, and
the helpers of §3.6 that every computed value uses (``K``, ``observed_date``,
``active_assumptions``, ``live_links``, ``reviewed_on_or_after``, ``last_activity_date``,
``decided_date``).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

**Filter first, then compute.** ``view_at(d, T, cfg, axis=...)`` returns the decision as it was
visible at ``T`` on an axis: rows not visible at ``T`` and rows voided by ``T`` are dropped, and the
mutable heads (the decision, its assumptions) are replayed back through their ``dec_versions``
rows. Every computed function of ``domain/`` then works on such a view and only excludes rows voided
by ``T`` itself; this is the spec's ``compute_all(view, local_date(T))`` of §3.15. Called on a view
loaded "now" (every row visible), ``view_at`` changes nothing, so the domain functions may also be
called on a loaded view directly.

Spec notes:

- **Order of checks.** "Ordered by observed_at, then K" (§3.4): the key is the owner-zone observed
  date, then the observed instant (a day- or month-precision time counts from the start of that
  local day; an unknown time counts from K), then K, then the row id.
- **Occurrence axis.** Rows that describe an event (facts, checks, readings, reviews, outcomes) are
  visible when their event time is known and not after ``T`` (a date counts when it is not after
  ``T.date``); rows with an unknown time are excluded and counted (``unknown_event_rows``).
  Rows that have no event time at all (options, assumptions, links, stakes, learnings, editions,
  versions) and a decision with an unknown decided time use the knowledge time K on this axis.
- **Removed links.** A link carries only ``removed_tx``, not a removal instant. In a view at ``T``
  a removed link is live again only when a ``dec_versions`` row of entity ``link`` records the
  removal and that row is not visible at ``T``; otherwise it stays removed.
- **Tombstones.** ``absent_since_run_id`` is kept as loaded: a run id carries no instant in the
  view, so an as-of view in the past still shows the current tombstone.
- **The current edition** of a view is the highest edition visible at ``T`` (0 when none is).
- **Undated reconstructions** (found in review). An imported assessment with an unknown observed
  time (``reconstructed`` and no ``observed_at``: the importer's "first state of a new mirror
  without last_checked_at", §6.3) gives the assumption its state, but not a date: it is left out
  of ``floor_date``, ``assessed_since`` and ``last_activity_date`` (``dated_assessments``).
  Otherwise ``observed_date``'s fallback to K would date it on the import day, moving the due
  floor and masking NO_DATA_SINCE, which v1 never did. An owner's check with an unknown time still
  counts by its K.
- **Head replay** undoes the hidden ``dec_versions`` rows newest first in application (id) order,
  on the stored row, and rebuilds the typed attributes of the changed columns. A version whose
  field is not a column of its entity is history only and changes nothing.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from coflow.kernel.context import Axis, EvalTime, local_date, parse_instant, start_of_local_day
from coflow.modules.dec.domain import due as _due
from coflow.modules.dec.domain.model import (
    AssumptionState,
    AssumptionView,
    CheckView,
    DecConfig,
    DecisionView,
    EventAt,
    FactView,
    LinkView,
    OptionView,
    OutcomeView,
    ReadingView,
    ReviewView,
    RowStamp,
    VersionView,
)

__all__ = [
    "active_assumptions",
    "assessments",
    "chosen_option",
    "current_outcome",
    "dated_assessments",
    "decided_date",
    "effective_state",
    "event_date",
    "k_date",
    "last_activity_date",
    "latest_assessment",
    "live_links",
    "live_options",
    "live_reviews",
    "observed_date",
    "occurred_date",
    "reviewed_on_or_after",
    "successor_ref",
    "unknown_event_rows",
    "view_at",
    "visible",
    "voided_by",
]


# ==================================================================================================
# Times of a row


def k_date(row: RowStamp, cfg: DecConfig) -> date:
    """``date(K(row))``: the owner-zone date of the row's knowledge time (§2.1)."""
    return local_date(row.known_at, cfg.tz)


def event_date(at: EventAt, cfg: DecConfig) -> date | None:
    """The owner-zone date of an event-time value: an instant's local date, a day or month as
    stored (a month is its first day), ``None`` for an unknown time."""
    if at is None:
        return None
    if isinstance(at, datetime):
        return local_date(at, cfg.tz)
    return at


def _event_instant(at: EventAt, row: RowStamp, cfg: DecConfig) -> datetime:
    if isinstance(at, datetime):
        return at
    if isinstance(at, date):
        return start_of_local_day(at, cfg.tz)
    return row.known_at


def observed_date(c: CheckView | ReadingView, cfg: DecConfig) -> date:
    """The owner-zone date of ``c.observed_at``; for an unknown time, the date of K(c) (§3.6)."""
    return event_date(c.observed_at, cfg) or k_date(c, cfg)


def occurred_date(row: FactView | ReviewView | OutcomeView, cfg: DecConfig) -> date:
    """The owner-zone date of ``occurred_at``; for an unknown time, the date of K(row)."""
    return event_date(row.occurred_at, cfg) or k_date(row, cfg)


def decided_date(d: DecisionView, cfg: DecConfig) -> date | None:
    """The owner-zone date of ``d.decided_at``, or ``None`` when unknown (§3.6)."""
    return event_date(d.decided_at, cfg)


def _check_key(c: CheckView | ReadingView, cfg: DecConfig) -> tuple[date, datetime, datetime, int]:
    return (observed_date(c, cfg), _event_instant(c.observed_at, c, cfg), c.known_at, c.id)


# ==================================================================================================
# Visibility (§3.15)

_EVENT_ATTR: Mapping[type, str] = {
    FactView: "occurred_at",
    CheckView: "observed_at",
    ReadingView: "observed_at",
    ReviewView: "occurred_at",
    OutcomeView: "occurred_at",
}


def voided_by(row: object, T: EvalTime) -> bool:
    """The row was voided at or before ``T`` (``voided_at`` set once by undo or correction)."""
    voided_at = getattr(row, "voided_at", None)
    return voided_at is not None and voided_at <= T.instant


def visible(row: RowStamp, T: EvalTime, axis: Axis = "knowledge", *, cfg: DecConfig) -> bool:
    """Is ``row`` visible at ``T`` on ``axis`` (§3.15; see the module's spec note for rows without
    an event time on the occurrence axis)."""
    if axis == "knowledge":
        return row.known_at <= T.instant
    if axis == "instance":
        return row.recorded_at <= T.instant
    attr = _EVENT_ATTR.get(type(row))
    if attr is None:
        if isinstance(row, DecisionView) and row.decided_at is not None:
            return _event_not_after(row.decided_at, T)
        return row.known_at <= T.instant
    at = getattr(row, attr)
    return at is not None and _event_not_after(at, T)


def _event_not_after(at: datetime | date, T: EvalTime) -> bool:
    if isinstance(at, datetime):
        return at <= T.instant
    return at <= T.date


def unknown_event_rows(d: DecisionView) -> int:
    """How many event rows of ``d`` have an unknown event time (excluded on the occurrence axis)."""
    rows: list[object] = [*d.facts, *d.reviews, *d.outcomes]
    for a in d.assumptions:
        rows += [*a.checks, *a.readings]
    return sum(1 for r in rows if getattr(r, _EVENT_ATTR[type(r)]) is None)


def _version_visible(v: VersionView, T: EvalTime, axis: Axis) -> bool:
    if axis == "instance":
        return v.recorded_at <= T.instant
    return v.known_at <= T.instant  # versions have no event time: K on the occurrence axis too


# ==================================================================================================
# The view at T


_DEC_DATES = frozenset({"review_due", "review_due_initial", "expected_by"})
_DEC_INSTANTS = frozenset({"activated_at", "closed_at"})
_DEC_INTS = frozenset(
    {"number", "confidence", "current_edition", "version", "a_seq", "o_seq", "r_seq", "l_seq"}
    | {"ft_seq", "erased_tx"}
)
_DEC_BOOLS = frozenset({"completion_pending", "third_party_sensitive", "reconstructed"})
_DEC_EVENTS: Mapping[str, str] = {"decided_at": "decided_precision"}

_ASM_DATES = frozenset({"by_date", "judge_from", "next_check_at"})
_ASM_INSTANTS = frozenset({"probability_recorded_at"})
_ASM_INTS = frozenset(
    {"code_n", "position", "probability", "superseded_by", "added_in_edition", "version"}
    | {"ck_seq", "rd_seq", "erased_tx"}
)
_ASM_BOOLS = frozenset({"is_critical", "shareable"})


@dataclasses.dataclass(frozen=True, slots=True)
class _Columns:
    dates: frozenset[str]
    instants: frozenset[str]
    ints: frozenset[str]
    bools: frozenset[str]
    events: Mapping[str, str]


_DECISION_COLUMNS = _Columns(_DEC_DATES, _DEC_INSTANTS, _DEC_INTS, _DEC_BOOLS, _DEC_EVENTS)
_ASSUMPTION_COLUMNS = _Columns(_ASM_DATES, _ASM_INSTANTS, _ASM_INTS, _ASM_BOOLS, {})


def _stored_from_text(column: str, text: str | None, cols: _Columns) -> str | int | None:
    """A ``dec_versions`` value (TEXT) back in its stored type."""
    if text is None:
        return None
    if column in cols.ints or column in cols.bools:
        return int(text)
    return text


def _typed(column: str, stored: Mapping[str, Any], cols: _Columns) -> object:
    value = stored.get(column)
    if value is None:
        return None
    typed = cols.dates | cols.instants | cols.ints | cols.bools
    if value == "" and column in typed:
        return None
    if column in cols.dates:
        return date.fromisoformat(str(value)[:10])
    if column in cols.instants:
        return parse_instant(str(value))
    if column in cols.bools:
        return bool(int(value))
    if column in cols.ints:
        return int(value)
    if column in cols.events:
        return _event_value(value, stored.get(cols.events[column]))
    return value


def _event_value(value: object, precision: object) -> EventAt:
    if value is None or value == "" or precision == "unknown":
        return None
    text = str(value)
    if precision == "instant":
        return parse_instant(text)
    if precision == "month":
        return date(int(text[:4]), int(text[5:7]), 1)
    return date.fromisoformat(text[:10])


def _attr_for(column: str) -> str:
    return "unknowns" if column == "unknowns_json" else column


def _replay(view: Any, undo: Sequence[VersionView], cols: _Columns) -> Any:
    """Undo ``undo`` (newest first) on the view's stored row and rebuild the changed attributes."""
    if not undo:
        return view
    stored = dict(view.stored)
    changed: set[str] = set()
    for v in sorted(undo, key=lambda v: v.id, reverse=True):  # application order, newest first
        column = "unknowns_json" if v.field == "unknowns" else v.field
        if column not in stored or column in ("id", "tx", "recorded_at"):
            continue  # not a column of the entity: history only
        stored[column] = _stored_from_text(column, v.old_value, cols)
        changed.add(column)
        if column in cols.events:
            changed.add(cols.events[column])
        for event, precision in cols.events.items():
            if column == precision:
                changed.add(event)
    names = {f.name for f in dataclasses.fields(view)}
    updates: dict[str, object] = {}
    for column in changed:
        attr = _attr_for(column)
        if attr not in names:
            continue
        if attr == "unknowns":
            raw = stored.get("unknowns_json")
            updates[attr] = tuple(json.loads(str(raw))) if raw else ()
        else:
            updates[attr] = _typed(column, stored, cols)
    return dataclasses.replace(view, stored=stored, **updates)


def view_at(
    d: DecisionView, T: EvalTime, cfg: DecConfig, *, axis: Axis = "knowledge"
) -> DecisionView | None:
    """The decision as visible at ``T`` on ``axis`` (§3.15), or ``None`` when the decision itself
    is not visible then."""
    if not visible(d, T, axis, cfg=cfg):
        return None

    def keep(rows: Iterable[Any]) -> tuple[Any, ...]:
        return tuple(r for r in rows if visible(r, T, axis, cfg=cfg) and not voided_by(r, T))

    hidden = [v for v in d.versions if not _version_visible(v, T, axis)]
    head = _replay(
        d,
        [v for v in hidden if v.entity == "decision" and v.entity_id == d.id],
        _DECISION_COLUMNS,
    )
    assumptions = []
    for a in keep(d.assumptions):
        a2 = _replay(
            a,
            [v for v in hidden if v.entity == "assumption" and v.entity_id == a.id],
            _ASSUMPTION_COLUMNS,
        )
        assumptions.append(
            dataclasses.replace(a2, checks=keep(a2.checks), readings=keep(a2.readings))
        )
    links = []
    for link in keep(d.links):
        live = _link_at(link, d.versions, T, axis)
        if live is not None:
            links.append(live)
    editions = keep(d.editions)
    return dataclasses.replace(
        head,
        options=keep(d.options),
        assumptions=tuple(assumptions),
        facts=keep(d.facts),
        reviews=keep(d.reviews),
        outcomes=keep(d.outcomes),
        learnings=keep(d.learnings),
        stakes=keep(d.stakes),
        links=tuple(links),
        editions=editions,
        versions=tuple(v for v in d.versions if _version_visible(v, T, axis)),
        current_edition=max((e.n for e in editions), default=0),
    )


def _link_at(
    link: LinkView, versions: Sequence[VersionView], T: EvalTime, axis: Axis
) -> LinkView | None:
    if link.removed_tx is None:
        return link
    removal = [v for v in versions if v.entity == "link" and v.entity_id == link.id]
    if removal and not any(_version_visible(v, T, axis) for v in removal):
        return dataclasses.replace(link, removed_tx=None, removed_reason=None)
    return None


# ==================================================================================================
# The helpers of §3.6 (over a view at T; rows voided by T excluded)


def active_assumptions(d: DecisionView) -> list[AssumptionView]:
    """Assumptions of ``d`` with status ``active``, ordered by position (§3.6)."""
    return sorted(
        (a for a in d.assumptions if a.status == "active"), key=lambda a: (a.position, a.code_n)
    )


def live_options(d: DecisionView) -> list[OptionView]:
    """The options of the decision itself (not of a fork), in code order."""
    return sorted(
        (o for o in d.options if o.decision_id == d.id and o.fork_id is None),
        key=lambda o: o.code_n,
    )


def chosen_option(d: DecisionView) -> OptionView | None:
    return next((o for o in live_options(d) if o.chosen), None)


def live_links(d: DecisionView, roles: Iterable[str]) -> list[LinkView]:
    """``dec_links`` of ``d`` with ``removed_tx IS NULL`` and a role in ``roles`` (§3.6)."""
    wanted = set(roles)
    return [link for link in d.links if link.removed_tx is None and link.role in wanted]


def live_reviews(d: DecisionView, T: EvalTime) -> list[ReviewView]:
    return [r for r in d.reviews if not voided_by(r, T)]


def assessments(a: AssumptionView, T: EvalTime, cfg: DecConfig) -> list[CheckView]:
    """The non-voided assessments of ``a`` in check order (observed time, then K)."""
    rows = [c for c in a.checks if c.kind == "assessment" and not voided_by(c, T)]
    return sorted(rows, key=lambda c: _check_key(c, cfg))


def dated_assessments(a: AssumptionView, T: EvalTime, cfg: DecConfig) -> list[CheckView]:
    """``assessments`` without the undated reconstructions (see the module's spec note): the rows
    that date a check for the floor, ``assessed_since`` and the last activity."""
    return [c for c in assessments(a, T, cfg) if not (c.reconstructed and c.observed_at is None)]


def latest_assessment(a: AssumptionView, T: EvalTime, cfg: DecConfig) -> CheckView | None:
    """The last non-voided assessment, ordered by observed time, then K (§3.4)."""
    rows = assessments(a, T, cfg)
    return rows[-1] if rows else None


def effective_state(
    d: DecisionView, a: AssumptionView, T: EvalTime, cfg: DecConfig
) -> AssumptionState:
    """§3.4: the last known state, however old; else UNVERIFIABLE (nothing to check with), else
    NOT_YET_DUE or UNCHECKED (its date has come and nobody checked)."""
    c = latest_assessment(a, T, cfg)
    if c is not None and c.state is not None:
        return c.state
    if a.data_source_kind == "none":
        return "UNVERIFIABLE"
    due = _due.assumption_due(d, a, T, cfg).due
    if due is None or due > T.date:
        return "NOT_YET_DUE"
    return "UNCHECKED"


def reviewed_on_or_after(d: DecisionView, day: date, T: EvalTime, cfg: DecConfig) -> bool:
    """Any non-voided review of ``d`` whose occurred date is on or after ``day`` (§3.6)."""
    return any(occurred_date(r, cfg) >= day for r in live_reviews(d, T))


def last_activity_date(d: DecisionView, T: EvalTime, cfg: DecConfig) -> date | None:
    """The latest event date (fallback: K date) of ``d``'s facts, assessments, readings and
    reviews; if none, the activation date (the decided date for mirrors) (§3.6).

    Spec note: when that date is unknown too, the decided date and then the K date of the decision
    stand in, so a decision always has a last activity.
    """
    days = [occurred_date(f, cfg) for f in d.facts if not voided_by(f, T)]
    for a in d.assumptions:
        days += [observed_date(c, cfg) for c in dated_assessments(a, T, cfg)]
        days += [observed_date(r, cfg) for r in a.readings if not voided_by(r, T)]
    days += [occurred_date(r, cfg) for r in live_reviews(d, T)]
    if days:
        return max(days)
    if d.mirror_of:
        return decided_date(d, cfg) or k_date(d, cfg)
    activated = local_date(d.activated_at, cfg.tz) if d.activated_at else None
    return activated or decided_date(d, cfg) or k_date(d, cfg)


def current_outcome(d: DecisionView) -> OutcomeView | None:
    """The outcome resolution no later resolution supersedes (the newest by K when several)."""
    superseded = {o.supersedes_outcome_id for o in d.outcomes if o.supersedes_outcome_id}
    live = [o for o in d.outcomes if o.id not in superseded]
    return max(live, key=lambda o: (o.known_at, o.id)) if live else None


def successor_ref(d: DecisionView, T: EvalTime) -> str | None:
    """The successor named by the latest ``supersede`` review, if any."""
    reviews = [r for r in live_reviews(d, T) if r.action == "supersede" and r.successor_ref]
    if not reviews:
        return None
    return max(reviews, key=lambda r: (r.known_at, r.id)).successor_ref
