"""The waiting list (spec §3.8): one list for the CLI, MCP and, from stage 2, the plan and the bot.
``KIND_RANK``, the reasons, the urgency order (a critical violation first, then the oldest due
date, then the subject kind, then the number), and ``drafts_to_finish`` as a separate list
(AT-D4).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2. In I1 the query
lists decisions only (§12.2); the pure function already takes forks and proposals, so I2 and I3
only pass them in.

Every function works on views at ``T`` (``states.view_at``). The review reason is independent of
health, so an overdue review waits even when the ground is INSUFFICIENT; every violated assumption
waits, critical or not, with its criticality shown, so health and the list agree (v1 defect 4).

Spec note: reason texts render dates as ISO dates (``2026-11-15``), the form every other answer
uses; the source of a check's date is named in words ("from its threshold date").
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from coflow.kernel.context import EvalTime
from coflow.kernel.ports.decision_directory import WAITING_KINDS, Reason, WaitingItem
from coflow.kernel.ports.goal_directory import GoalDirectory
from coflow.modules.dec.domain import due as _due
from coflow.modules.dec.domain import goals as _goals
from coflow.modules.dec.domain import health as _health
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.inputs import DraftItem
from coflow.modules.dec.domain.model import (
    DecConfig,
    DecisionView,
    ForkView,
    ProposalView,
)

__all__ = [
    "DUE_SOURCE_WORDS",
    "KIND_RANK",
    "SUBJECT_ORDER",
    "decision_item",
    "decision_reasons",
    "drafts_to_finish",
    "reason_sort_key",
    "urgency",
    "waiting",
]

KIND_RANK: tuple[str, ...] = WAITING_KINDS
SUBJECT_ORDER = {"decision": 0, "fork": 1, "proposal": 2}

DUE_SOURCE_WORDS = {
    "explicit": "from its next check date",
    "by_date": "from its threshold date",
    "text": "from a date in its text",
    "review": "from the review date",
}


def reason_sort_key(r: Reason) -> tuple[int, date, str]:
    """Reasons within an item: by kind rank, then due date, then code (§3.8)."""
    return (KIND_RANK.index(r.kind), r.due or date.max, r.code or "")


def _ago(due: date, T: EvalTime) -> str:
    days = (T.date - due).days
    if days <= 0:
        return ""
    return f" ({days} day{'s' if days != 1 else ''} ago)"


def decision_reasons(
    d: DecisionView, T: EvalTime, cfg: DecConfig, goals: GoalDirectory
) -> list[Reason]:
    """Why an active decision waits at ``T``, sorted; empty when it does not wait (§3.8)."""
    if d.status != "active" or d.absent_since_run_id is not None:
        return []  # only active decisions wait; tombstoned mirrors never do
    in_pool = {a.id for a in _health.pool(d)}
    act = _states.active_assumptions(d)
    rs: list[Reason] = []
    for a in act:  # EVERY assumption, critical or not
        if _states.effective_state(d, a, T, cfg) != "VIOLATED":
            continue
        last = _states.latest_assessment(a, T, cfg)
        day = _states.observed_date(last, cfg) if last is not None else _states.k_date(a, cfg)
        critical = a.id in in_pool
        words = "critical" if critical else "non-critical"
        statement = _health.short(a.statement, 60)
        rs.append(
            Reason(
                kind="violated",
                due=day,
                code=a.code,
                critical=critical,
                text=f"{a.code} violated ({words}), checked {day}: {statement}",
            )
        )
    rd = d.review_due
    if rd is not None and rd <= T.date and not _states.reviewed_on_or_after(d, rd, T, cfg):
        if rd < T.date:
            text = f"review was due {rd}, {(T.date - rd).days} days ago"
            rs.append(Reason(kind="review_overdue", due=rd, text=text))
        else:
            rs.append(Reason(kind="review_today", due=rd, text="review today"))
    for g in _goals.goal_changes_unanswered(d, T, cfg, goals):  # asked once, until a review
        title = f" ({g.title})" if g.title else ""
        rs.append(
            Reason(
                kind="goal_changed",
                due=g.changed,
                code=g.ref,
                status=g.status,
                text=f"goal {g.ref}{title} {g.status} on {g.changed}",
            )
        )
    for a in act:
        cd = _due.check_due(d, a, T, cfg)
        if cd is None or cd.due is None:
            continue
        source = DUE_SOURCE_WORDS.get(cd.source or "", "")
        rs.append(
            Reason(
                kind="check_due",
                due=cd.due,
                code=a.code,
                critical=a.id in in_pool,
                due_source=cd.source,
                text=f"{a.code}: check due {cd.due}, {source}{_ago(cd.due, T)}",
            )
        )
    if d.mirror_of and rd is None:  # an imported active record without a review date
        rs.append(
            Reason(
                kind="incomplete",
                due=_states.k_date(d, cfg),
                text="imported active without a review date: set one",
            )
        )
    return sorted(rs, key=reason_sort_key)


def decision_item(
    d: DecisionView, T: EvalTime, cfg: DecConfig, goals: GoalDirectory
) -> WaitingItem | None:
    """The waiting item of one decision (without its question context), or ``None``."""
    rs = decision_reasons(d, T, cfg, goals)
    if not rs:
        return None
    h = _health.health(d, T, cfg)
    return WaitingItem(
        subject_kind="decision",
        ref=d.public_id,
        number=d.number,
        title=d.title,
        health=_health.to_state(d.public_id, h, d.review_due),
        reasons=tuple(rs),
    )


def _fork_item(f: ForkView, T: EvalTime) -> WaitingItem | None:
    if f.status != "open" or f.deadline is None or f.deadline > T.date:
        return None
    text = "deadline today" if f.deadline == T.date else f"deadline {f.deadline} passed"
    return WaitingItem(
        subject_kind="fork",
        ref=f.public_id,
        number=f.number,
        title=f.question,
        health=None,
        reasons=(Reason(kind="fork_due", due=f.deadline, text=text),),
    )


def _proposal_item(p: ProposalView, cfg: DecConfig) -> WaitingItem | None:
    if p.status != "proposed":
        return None
    day = _states.k_date(p, cfg)
    return WaitingItem(
        subject_kind="proposal",
        ref=p.ref,
        number=p.id,
        title=p.title,
        health=None,
        reasons=(
            Reason(
                kind="proposal_waiting",
                due=day,
                text=f"proposed {day}, waiting for the owner's approval",
            ),
        ),
    )


def urgency(i: WaitingItem) -> tuple[int, date, int, int]:
    """A critical violation first, then the oldest due date, then the subject kind, then the
    number; proposals always last (§3.8)."""
    if i.subject_kind == "proposal":
        return (2, i.reasons[0].due or date.max, 0, i.number)
    critical = any(r.kind == "violated" and r.critical for r in i.reasons)
    dues = [r.due for r in i.reasons if r.due]
    return (
        0 if critical else 1,
        min(dues) if dues else date.max,
        SUBJECT_ORDER[i.subject_kind],
        i.number,
    )


def waiting(
    decisions: Iterable[DecisionView],
    T: EvalTime,
    cfg: DecConfig,
    *,
    goals: GoalDirectory,
    forks: Iterable[ForkView] = (),
    proposals: Iterable[ProposalView] = (),
) -> list[WaitingItem]:
    """The waiting list at ``T`` over views at ``T`` (§3.8), in urgency order."""
    items: list[WaitingItem] = []
    for d in decisions:
        item = decision_item(d, T, cfg, goals)
        if item is not None:
            items.append(item)
    for f in forks:
        fork = _fork_item(f, T)
        if fork is not None:
            items.append(fork)
    for p in proposals:
        prop = _proposal_item(p, cfg)
        if prop is not None:
            items.append(prop)
    return sorted(items, key=urgency)


def drafts_to_finish(
    decisions: Sequence[DecisionView], T: EvalTime, cfg: DecConfig
) -> list[DraftItem]:
    """Drafts the owner left for ``dec.drafts_stale_days`` or longer, with what they miss; a
    separate short list, never mixed into the waiting list (§3.8). Proposals are not drafts."""
    out: list[DraftItem] = []
    for d in sorted(decisions, key=lambda d: d.number):
        if d.status != "draft" or d.origin_kind == "proposal":
            continue
        age = (T.date - _states.k_date(d, cfg)).days
        if age >= cfg.drafts_stale_days:
            missing = tuple(_health.missing_for_activation(d, T))
            out.append(
                DraftItem(decision_ref=d.public_id, title=d.title, missing=missing, age_days=age)
            )
    return out
