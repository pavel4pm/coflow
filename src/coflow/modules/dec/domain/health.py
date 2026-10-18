"""Health on two axes (spec §3.7): ``pool``, ``unverifiable_share``, ``ground``, ``timeliness``,
``health`` (THE EVALUATION ORDER IS THE CONTRACT) and ``is_bet``. Returns ``model.HealthResult``;
the named vectors H1-H18 and the independent oracle (``tests/oracle/health_oracle.py``, track S)
pin it (AT-D3).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

The public entry point is ``health(d, T, cfg) -> HealthResult`` over a view at ``T``
(``states.view_at``). The composite label follows the fixed table of §3.7: an owner flag, then a
known violation, then an overdue review (never masked by missing data), then insufficient data,
then watch (drift, no review date, an overdue check, or stale "holding"), then on track, then
awaiting checks. The unverifiable share is the first line of every card (``share_line``).

Reason texts are the spec's own sentences, verbatim, so that the words agree wherever they are
shown; every reason also carries its structure (``axis``, ``kind``, ``code``, ``day``, ``source``).

Spec notes:

- ``missing_for_activation`` (§3.2) is needed in I1 only for the reason of a ``DRAFT`` label (v1
  mirrors may be drafts). It lives here until I2's ``domain/activation.py`` takes it over. An
  ``attendance`` decision always misses ``occasion_window``: occasions arrive at stage 3.
- ``SUPERSEDED`` names the successor from the latest ``supersede`` review; the ``supersedes`` link
  is stored on the successor, which a single decision's view does not hold.
- ``share`` is computed for every status (the pool does not depend on the status); ``ground`` is
  ``None`` for terminal and draft decisions.
- ``share_text`` (the decimal stored in ``unverifiable_at_seal`` and the review snapshots) is the
  share rounded half-even to four places, ``None`` without a pool.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from coflow.kernel.context import EvalTime
from coflow.kernel.ports.decision_directory import DecisionState
from coflow.modules.dec.domain import due as _due
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.model import (
    AssumptionState,
    AssumptionView,
    DecConfig,
    DecisionView,
    GroundValue,
    HealthLabel,
    HealthReason,
    HealthResult,
    TimelinessKind,
)

__all__ = [
    "effective_states",
    "ground",
    "health",
    "is_bet",
    "label_reason",
    "missing_for_activation",
    "outcome_badge",
    "pct",
    "pool",
    "share_line",
    "share_text",
    "short",
    "timeliness",
    "to_state",
    "unverifiable_share",
]


# ==================================================================================================
# Words


def short(text: str | None, n: int = 80) -> str:
    """``text`` cut to ``n`` characters with an ellipsis."""
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def pct(share: Decimal) -> str:
    """A share as a whole percentage, rounded half up: ``Decimal('0.6667')`` -> ``'67%'``."""
    return f"{int((share * 100).to_integral_value(rounding=ROUND_HALF_UP))}%"


# ==================================================================================================
# The pool and the share


def pool(d: DecisionView) -> list[AssumptionView]:
    """The assumptions the decision rests on: the active critical ones, else every active one."""
    act = _states.active_assumptions(d)
    crit = [a for a in act if a.is_critical]
    return crit or act


def effective_states(d: DecisionView, T: EvalTime, cfg: DecConfig) -> dict[int, AssumptionState]:
    """The effective state of every active assumption, by assumption id."""
    return {a.id: _states.effective_state(d, a, T, cfg) for a in _states.active_assumptions(d)}


def _share(p: Sequence[AssumptionView], s: Mapping[int, AssumptionState]) -> Decimal | None:
    if not p:
        return None
    return Decimal(sum(1 for a in p if s[a.id] == "UNVERIFIABLE")) / len(p)


def unverifiable_share(d: DecisionView, T: EvalTime, cfg: DecConfig) -> Decimal | None:
    """The share of the pool that is UNVERIFIABLE; ``None`` without a pool (§3.7)."""
    return _share(pool(d), effective_states(d, T, cfg))


def share_line(d: DecisionView, T: EvalTime, cfg: DecConfig) -> str:
    """The first line of every decision view: "2 of 5 assumptions it rests on cannot be
    checked"."""
    p = pool(d)
    if not p:
        return "no assumption recorded: nothing it rests on can be checked"
    s = effective_states(d, T, cfg)
    u = sum(1 for a in p if s[a.id] == "UNVERIFIABLE")
    return f"{u} of {len(p)} assumptions it rests on cannot be checked"


def share_text(d: DecisionView, T: EvalTime, cfg: DecConfig) -> str | None:
    """The share as stored text (four decimal places), or ``None`` without a pool."""
    share = unverifiable_share(d, T, cfg)
    if share is None:
        return None
    return format(share.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN), "f")


def is_bet(d: DecisionView, T: EvalTime, cfg: DecConfig) -> bool:
    """A badge, informative only: most of what the decision rests on cannot be checked."""
    s = unverifiable_share(d, T, cfg)
    return s is not None and s > cfg.unverifiable_share_limit


# ==================================================================================================
# The two axes


def _ground(
    d: DecisionView,
    act: Sequence[AssumptionView],
    p: Sequence[AssumptionView],
    s: Mapping[int, AssumptionState],
    cfg: DecConfig,
) -> tuple[GroundValue, list[HealthReason]]:
    def r(kind: str, text: str, code: str | None = None) -> HealthReason:
        return HealthReason(axis="ground", kind=kind, text=text, code=code)

    if not act:
        if d.depth == "light":
            return "NOT_MONITORED", [r("NOT_MONITORED", "light decision: review date only")]
        return "NO_ASSUMPTIONS", [r("NO_ASSUMPTIONS", "no assumption recorded")]
    viol = [a for a in p if s[a.id] == "VIOLATED"]
    if viol:
        return "VIOLATED", [
            r("VIOLATED", f"{a.code} violated: {short(a.statement)}", a.code) for a in viol
        ]
    share = _share(p, s)
    if share is not None and share > cfg.unverifiable_share_limit:
        text = f"{pct(share)} of the assumptions it rests on cannot be checked"
        return "INSUFFICIENT", [r("INSUFFICIENT", text)]
    in_pool = {a.id for a in p}
    drift = [r("DRIFTING", f"{a.code} drifting", a.code) for a in p if s[a.id] == "DRIFTING"]
    drift += [
        r("DRIFTING", f"{a.code} (non-critical) violated", a.code)
        for a in act
        if a.id not in in_pool and s[a.id] == "VIOLATED"
    ]
    if drift:
        return "DRIFTING", drift
    checkable = [a for a in p if s[a.id] != "UNVERIFIABLE"]
    if checkable and all(s[a.id] == "HOLDING" for a in checkable):
        return "HOLDING", [r("HOLDING", "every checkable assumption it rests on holds")]
    n = sum(1 for a in p if s[a.id] in ("NOT_YET_DUE", "UNCHECKED", "UNKNOWN"))
    return "AWAITING", [r("AWAITING", f"{n} assumptions without a result yet")]


def ground(d: DecisionView, T: EvalTime, cfg: DecConfig) -> tuple[GroundValue, list[HealthReason]]:
    """The ground axis: what the decision rests on (§3.7)."""
    return _ground(d, _states.active_assumptions(d), pool(d), effective_states(d, T, cfg), cfg)


def timeliness(
    d: DecisionView, T: EvalTime, cfg: DecConfig
) -> tuple[frozenset[TimelinessKind], list[HealthReason]]:
    """The timeliness axis: the review, overdue checks and silence; every applicable reason is
    listed (§3.7)."""
    kinds: set[TimelinessKind] = set()
    reasons: list[HealthReason] = []

    def add(
        kind: TimelinessKind,
        text: str,
        *,
        code: str | None = None,
        day: date | None = None,
        source: str | None = None,
    ) -> None:
        kinds.add(kind)
        reasons.append(
            HealthReason(axis="timeliness", kind=kind, text=text, code=code, day=day, source=source)
        )

    rd = d.review_due
    if rd is None:
        add("NO_REVIEW_DATE", "no review date")
    elif rd < T.date and not _states.reviewed_on_or_after(d, rd, T, cfg):
        add(
            "REVIEW_OVERDUE",
            f"review was due {rd}, {(T.date - rd).days} days ago",
            day=rd,
            source="review",
        )
    elif rd == T.date and not _states.reviewed_on_or_after(d, rd, T, cfg):
        add("DUE_TODAY", "review today", day=rd, source="review")
    for a in _states.active_assumptions(d):
        cd = _due.check_due(d, a, T, cfg)
        if cd is not None and cd.due is not None and cd.due < T.date:
            add(
                "CHECK_OVERDUE",
                f"{a.code} check was due {cd.due} (from {cd.source})",
                code=a.code,
                day=cd.due,
                source=cd.source,
            )
    last = _states.last_activity_date(d, T, cfg)
    if last is not None and (T.date - last).days > cfg.no_data_days:
        add("NO_DATA_SINCE", f"nothing recorded since {last}", day=last)
    return frozenset(kinds or {"ON_SCHEDULE"}), reasons


# ==================================================================================================
# The composite label


def outcome_badge(d: DecisionView) -> tuple[str | None, bool]:
    """``('success · resolved', True)``: only a resolved success shows green; reported and not
    confirmed show grey (§3.11)."""
    o = _states.current_outcome(d)
    if o is None:
        return None, False
    return f"{o.kind} · {o.basis}", o.kind == "success" and o.basis == "resolved"


def missing_for_activation(d: DecisionView, T: EvalTime) -> list[str]:
    """What blocks activation (§3.2); see the module's spec note."""
    m: list[str] = []
    if not d.title:
        m.append("title")
    if not (d.statement or _states.chosen_option(d)):
        m.append("statement")
    if d.review_due is None or d.review_due <= T.date:
        m.append("review_due")
    if d.decided_at is None and d.decided_basis != "unknown":
        m.append("decided_at")
    if d.kind == "test" and not _states.live_links(d, ("tests",)):
        m.append("tests_link")
    if d.kind == "attendance":
        m.append("occasion_window")  # occasions arrive at stage 3
    if d.depth == "full":
        act = _states.active_assumptions(d)
        if not d.question:
            m.append("question")
        if len(_states.live_options(d)) < 2:
            m.append("options")
        if not d.unknowns:
            m.append("unknown")
        if not d.success_criterion:
            m.append("success_criterion")
        if not act:
            m.append("assumption")
        for a in act:
            if a.comparator is None and not a.threshold_text:
                m.append(f"{a.code}.threshold")
    return m


def _label(label: HealthLabel, text: str | None = None) -> tuple[HealthReason, ...]:
    return (HealthReason(axis="label", kind=label, text=text),) if text else ()


def health(d: DecisionView, T: EvalTime, cfg: DecConfig) -> HealthResult:
    """The composite label with both axes and every reason (§3.7). THE EVALUATION ORDER IS THE
    CONTRACT."""
    act = _states.active_assumptions(d)
    p = pool(d)
    s = effective_states(d, T, cfg)
    share = _share(p, s)
    states = {a.code: s[a.id] for a in act}
    codes = tuple(a.code for a in p)

    def make(
        label: HealthLabel,
        g: GroundValue | None,
        t: frozenset[TimelinessKind],
        reasons: tuple[HealthReason, ...],
        badge: str | None = None,
        green: bool = False,
    ) -> HealthResult:
        return HealthResult(
            label=label,
            ground=g,
            timeliness=t,
            reasons=reasons,
            share=share,
            bet=share is not None and share > cfg.unverifiable_share_limit,
            states=states,
            pool=codes,
            badge=badge,
            badge_green=green,
        )

    if d.status == "closed":
        badge, green = outcome_badge(d)
        text = badge or "no outcome recorded"
        return make("CLOSED", None, frozenset(), _label("CLOSED", text), badge, green)
    if d.status == "cancelled":
        return make("CANCELLED", None, frozenset(), ())
    if d.status == "superseded":
        successor = _states.successor_ref(d, T) or "a successor not recorded here"
        return make("SUPERSEDED", None, frozenset(), _label("SUPERSEDED", f"by {successor}"))
    if d.status == "withdrawn":
        return make("WITHDRAWN", None, frozenset(), ())
    if d.status == "draft":
        missing = missing_for_activation(d, T)
        text = f"missing: {', '.join(missing)}" if missing else "nothing missing: ready to activate"
        return make("DRAFT", None, frozenset(), _label("DRAFT", text))

    g, gr = _ground(d, act, p, s, cfg)
    t, tr = timeliness(d, T, cfg)
    reasons = (*gr, *tr)

    def result(label: HealthLabel, extra: tuple[HealthReason, ...] = ()) -> HealthResult:
        return make(label, g, t, (*extra, *reasons))

    if d.manual_flag:  # 1 the owner's judgement
        return result(d.manual_flag, _label(d.manual_flag, "set by the owner"))
    if g == "VIOLATED":  # 2 a known violation beats fog and calendar
        return result("REVIEW_REQUIRED")
    if "REVIEW_OVERDUE" in t:  # 3 never masked by missing data
        return result("STALE")
    if g in ("INSUFFICIENT", "NO_ASSUMPTIONS"):  # 4
        return result("INSUFFICIENT_DATA")
    if (
        g == "DRIFTING"
        or t & {"NO_REVIEW_DATE", "CHECK_OVERDUE"}
        or ("NO_DATA_SINCE" in t and g == "HOLDING")
    ):  # 5 an overdue or stale "holding" is not on track
        return result("WATCH")
    if g in ("HOLDING", "NOT_MONITORED"):  # 6
        return result("ON_TRACK")
    return result("AWAITING_CHECKS")  # 7 replaces v1's signal-less "WATCH: not yet checked"


# ==================================================================================================
# Presenting a result

_LABEL_DRIVERS: Mapping[str, tuple[tuple[str, frozenset[str]], ...]] = {
    "ZOMBIE": (("label", frozenset({"ZOMBIE"})),),
    "OFF_TRACK": (("label", frozenset({"OFF_TRACK"})),),
    "REVIEW_REQUIRED": (("ground", frozenset({"VIOLATED"})),),
    "STALE": (("timeliness", frozenset({"REVIEW_OVERDUE"})),),
    "WATCH": (
        ("ground", frozenset({"DRIFTING"})),
        ("timeliness", frozenset({"NO_REVIEW_DATE", "CHECK_OVERDUE", "NO_DATA_SINCE"})),
    ),
}


def label_reason(h: HealthResult) -> HealthReason | None:
    """The reason that decides the label (for one-line lists): the violation of REVIEW_REQUIRED,
    the overdue review of STALE, the first watch cause of WATCH, else the first reason."""
    for axis, kinds in _LABEL_DRIVERS.get(h.label, ()):
        for r in h.reasons:
            if r.axis == axis and r.kind in kinds:
                return r
    return h.reasons[0] if h.reasons else None


def to_state(ref: str, h: HealthResult, review_due: date | None) -> DecisionState:
    """The port form of a health result (``DecisionDirectory.state``, waiting items)."""
    return DecisionState(
        ref=ref,
        label=h.label,
        ground=h.ground,
        timeliness=frozenset(h.timeliness),
        reasons=h.words,
        share=h.share,
        review_due=review_due,
        bet=h.bet,
        badge=h.badge,
    )
