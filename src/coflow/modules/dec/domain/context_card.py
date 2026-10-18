"""The rule-built question context and likely actions (spec §3.9): no waiting item without its
context; every date in an action equals what the write would store (AT-N11, AT-N23).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

The first review question v1 ever asked was answered "I don't understand the context". So every
waiting item carries, built by rules and without a model: one line about the decision, the share
line, health with its reasons, the reasons with their dates and date sources, the last fact with
its age, the dates that have passed, the goals it serves, what exactly is asked, the execution
counts from every registered probe, the postponements since the last review, and the likely
actions. Action dates come from ``due.next_check_after`` and ``dec.review_step_days``, the same
values the writes use.

Spec notes:

- The last fact is the newest non-voided fact of either phase, by event date (fallback K), then K.
- "Postponements since the last review" counts postponements recorded (K) after the last
  non-voided review was recorded; all of them when there is no review.
- A structured threshold is shown in words (``signed >= 3 by 2026-11-20``); otherwise the threshold
  text as stored.
- **Which reason leads the actions.** §3.9 takes the actions of the first reason; AT-N23 expects a
  card whose review is overdue and whose served goal was dropped to lead with close and cancel,
  although ``review_overdue`` ranks before ``goal_changed``. The simplest reading that satisfies
  both: the first reason leads, except that an unanswered goal change leads over a review reason
  (a goal that ended is the stronger question). The spec text of §3.9 should say so.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import date, timedelta

from coflow.kernel.context import EvalTime
from coflow.kernel.ports.attachment_probe import DecisionAttachmentProbe
from coflow.kernel.ports.decision_directory import (
    AskedPart,
    FactLine,
    QuestionContext,
    WaitingItem,
)
from coflow.kernel.ports.goal_directory import GoalDirectory
from coflow.modules.dec.domain import due as _due
from coflow.modules.dec.domain import goals as _goals
from coflow.modules.dec.domain import health as _health
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.model import AssumptionView, DecConfig, DecisionView

__all__ = [
    "POSTPONE_STEP_DAYS",
    "asked_part",
    "last_fact",
    "leading_kind",
    "likely_actions",
    "one_line",
    "passed_dates",
    "postponements_since_review",
    "question_context",
    "threshold_words",
    "with_question_context",
]

POSTPONE_STEP_DAYS = 7
"""The postponement a check card offers: one week from ``T.date`` (§3.9)."""


def one_line(item: WaitingItem, d: DecisionView | None) -> str:
    """``D-0907 · <title> — <statement or question, 120 characters>``."""
    if d is None:
        return item.title
    head = f"{item.ref} · {item.title}"
    body = d.statement or d.question
    return f"{head} — {_health.short(body, 120)}" if body else head


def last_fact(d: DecisionView, T: EvalTime, cfg: DecConfig) -> FactLine | None:
    """The newest fact: code, text cut to 120 characters, event time, age in days, evidence."""
    facts = [f for f in d.facts if not _states.voided_by(f, T)]
    if not facts:
        return None
    f = max(facts, key=lambda f: (_states.occurred_date(f, cfg), f.known_at, f.id))
    day = _states.occurred_date(f, cfg)
    if f.evidence_ref:
        evidence: str | None = f.evidence_ref
    else:
        evidence = "no source" if f.evidence_kind == "none" else f.evidence_kind
    return FactLine(
        ref=f.ref,
        text=_health.short(f.text, 120),
        occurred_at=f.occurred_at,
        age_days=(T.date - day).days,
        evidence=evidence,
    )


def passed_dates(d: DecisionView, T: EvalTime) -> tuple[tuple[str, date], ...]:
    """The review date, the expected-by date and assumption by-dates on or before ``T.date``."""
    candidates: list[tuple[str, date | None]] = [
        ("review date", d.review_due),
        ("expected by", d.expected_by),
    ]
    candidates += [(f"{a.code} by-date", a.by_date) for a in _states.active_assumptions(d)]
    return tuple((label, day) for label, day in candidates if day is not None and day <= T.date)


def threshold_words(a: AssumptionView) -> str | None:
    """The threshold in words: structured when a comparator exists, else the stored text."""
    if a.comparator is None:
        return a.threshold_text
    metric = a.metric or "value"
    unit = f" {a.unit}" if a.unit else ""
    if a.comparator == "between":
        words = f"{metric} between {a.threshold_value} and {a.threshold_value2}{unit}"
    else:
        words = f"{metric} {a.comparator} {a.threshold_value}{unit}"
    return f"{words} by {a.by_date}" if a.by_date else words


def _assumption(d: DecisionView | None, code: str | None) -> AssumptionView | None:
    if d is None or code is None:
        return None
    return next((a for a in d.assumptions if a.code == code), None)


def asked_part(
    item: WaitingItem, d: DecisionView | None, T: EvalTime, cfg: DecConfig
) -> AskedPart | None:
    """What the question asks about: the assumption with its threshold, due date and source; or
    the review, the goal, the missing review date, the fork or the proposal."""
    if not item.reasons:
        return None
    r = item.reasons[0]
    if r.kind in ("violated", "check_due"):
        a = _assumption(d, r.code)
        if a is None or d is None:
            return None
        due = _due.assumption_due(d, a, T, cfg)
        return AskedPart(
            kind="assumption",
            ref=a.ref,
            statement=a.statement,
            threshold_text=threshold_words(a),
            due=r.due if r.kind == "check_due" else due.due,
            due_source=r.due_source if r.kind == "check_due" else due.source,
        )
    if r.kind in ("review_overdue", "review_today"):
        return AskedPart(kind="review", ref=item.ref, due=r.due, due_source="review")
    if r.kind == "goal_changed":
        return AskedPart(kind="goal", ref=r.code or "", statement=r.text, due=r.due)
    if r.kind == "incomplete":
        return AskedPart(kind="incomplete", ref=item.ref, statement="review date")
    if r.kind == "fork_due":
        return AskedPart(kind="fork", ref=item.ref, statement=item.title, due=r.due)
    return AskedPart(kind="proposal", ref=item.ref, statement=item.title, due=r.due)


def postponements_since_review(d: DecisionView, T: EvalTime) -> int:
    """Postponements of ``d``'s assumptions recorded after its last review (see the spec note)."""
    reviews = _states.live_reviews(d, T)
    since = max((r.known_at for r in reviews), default=None)
    return sum(
        1
        for a in d.assumptions
        for c in a.checks
        if c.kind == "postponement"
        and not _states.voided_by(c, T)
        and (since is None or c.known_at > since)
    )


def leading_kind(item: WaitingItem) -> str:
    """The reason kind whose actions lead the card (see the module's spec note)."""
    kinds = [r.kind for r in item.reasons]
    if kinds and kinds[0] in ("review_overdue", "review_today") and "goal_changed" in kinds:
        return "goal_changed"
    return kinds[0] if kinds else ""


def likely_actions(
    item: WaitingItem, d: DecisionView | None, T: EvalTime, cfg: DecConfig
) -> tuple[str, ...]:
    """The buttons of the card; their dates come from the same functions the writes use (§3.9)."""
    if not item.reasons:
        return ()
    k = leading_kind(item)
    step = T.date + timedelta(days=cfg.review_step_days)
    if k == "violated":
        return ("revise", f"adjust · next review {step}", "close", "cancel")
    if k in ("review_overdue", "review_today"):
        return (
            f"keep · next review {step}",
            f"adjust · next review {step}",
            "close",
            "cancel",
            "supersede",
        )
    if k == "goal_changed":
        return ("close", "cancel", f"keep (give a reason) · next review {step}")
    if k == "check_due":
        a = _assumption(d, item.reasons[0].code)
        nxt = _due.next_check_after(a, T.date).next if a is not None else None
        postpone = T.date + timedelta(days=POSTPONE_STEP_DAYS)
        return (
            f"holding · next check {nxt or 'none (falls back)'}",
            "drifting",
            "violated",
            "can't judge this time",
            "nothing to check with",
            f"postpone to {postpone}",
        )
    if k == "incomplete":
        return ("set a review date (keep)", "complete fields", "cancel")
    if k == "fork_due":
        return ("decide (pick an option)", "move the deadline", "dissolve", "delegate")
    return ("approve (owner channel)", "edit and approve", "reject with a class")


def question_context(
    item: WaitingItem,
    d: DecisionView | None,
    T: EvalTime,
    cfg: DecConfig,
    *,
    goals: GoalDirectory,
    probes: Sequence[DecisionAttachmentProbe] = (),
) -> QuestionContext:
    """The context of one waiting item (§3.9); ``d`` is the decision's view at ``T`` (``None``
    for forks and proposals)."""
    if d is None:
        return QuestionContext(
            one_line=one_line(item, None),
            share_line=None,
            health=None,
            reasons=item.reasons,
            last_fact=None,
            passed=(),
            goals=(),
            asked=asked_part(item, None, T, cfg),
            likely_actions=likely_actions(item, None, T, cfg),
        )
    health = item.health
    if health is None:
        health = _health.to_state(d.public_id, _health.health(d, T, cfg), d.review_due)
    return QuestionContext(
        one_line=one_line(item, d),
        share_line=_health.share_line(d, T, cfg),
        health=health,
        reasons=item.reasons,
        last_fact=last_fact(d, T, cfg),
        passed=passed_dates(d, T),
        goals=tuple(_goals.served_goals(d, T, goals)),
        asked=asked_part(item, d, T, cfg),
        execution={p.kind: p.summary(d.public_id, as_of=T.instant).counts() for p in probes},
        postponements_since_review=postponements_since_review(d, T),
        likely_actions=likely_actions(item, d, T, cfg),
    )


def with_question_context(
    item: WaitingItem,
    d: DecisionView | None,
    T: EvalTime,
    cfg: DecConfig,
    *,
    goals: GoalDirectory,
    probes: Sequence[DecisionAttachmentProbe] = (),
) -> WaitingItem:
    """``item`` with its question context attached."""
    qc = question_context(item, d, T, cfg, goals=goals, probes=probes)
    return dataclasses.replace(item, question_context=qc)
