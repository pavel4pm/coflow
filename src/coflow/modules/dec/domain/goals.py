"""Goal propagation (spec §3.13): ``goal_changes_unanswered(d, T, cfg, goals)`` over the
``GoalDirectory`` port; a question, never a state change (AT-S7). ``served_goals`` gives the goal
lines of a question card (§3.9).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2.

A served or tested goal that ended (``ENDED_GOAL_STATUSES``) after the decision was decided asks
``goal_changed`` once: any later review answers it, because that review's card showed the goal.

Spec notes:

- A goal whose change date and first-seen date are both unknown cannot be dated against the
  decision, so it asks nothing (the shadow adapter always knows the first-seen date of a status).
- A goal linked twice (``serves`` and ``tests``) is one question.
"""

from __future__ import annotations

from coflow.kernel.context import EvalTime
from coflow.kernel.ports.goal_directory import ENDED_GOAL_STATUSES, GoalDirectory
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.model import DecConfig, DecisionView, GoalChange, GoalLine

__all__ = ["ENDED", "GOAL_ROLES", "goal_changes_unanswered", "served_goals"]

ENDED = ENDED_GOAL_STATUSES
GOAL_ROLES = ("serves", "tests")


def _goal_refs(d: DecisionView) -> list[str]:
    refs: list[str] = []
    for link in _states.live_links(d, GOAL_ROLES):
        if link.target_ref not in refs:
            refs.append(link.target_ref)
    return refs


def goal_changes_unanswered(
    d: DecisionView, T: EvalTime, cfg: DecConfig, goals: GoalDirectory
) -> list[GoalChange]:
    """Served or tested goals that ended after the decided date and that no review since has
    answered (§3.13)."""
    out: list[GoalChange] = []
    decided = _states.decided_date(d, cfg) or _states.k_date(d, cfg)
    for ref in _goal_refs(d):
        st = goals.state(ref, as_of=T.instant)
        if st is None or st.status not in ENDED:
            continue
        changed = st.status_changed_date or st.first_seen_date
        if changed is None:
            continue
        if changed <= decided:
            continue  # already ended when decided: the owner knew
        if _states.reviewed_on_or_after(d, changed, T, cfg):
            continue  # a later review answers it
        out.append(GoalChange(ref=ref, title=st.title, status=st.status, changed=changed))
    return out


def served_goals(d: DecisionView, T: EvalTime, goals: GoalDirectory) -> list[GoalLine]:
    """Every served or tested goal as a card line: title, status and since when (§3.9)."""
    lines: list[GoalLine] = []
    for ref in _goal_refs(d):
        st = goals.state(ref, as_of=T.instant)
        if st is None:
            lines.append(GoalLine(ref=ref, title=None, status=None, since=None))
        else:
            since = st.status_changed_date or st.first_seen_date
            lines.append(GoalLine(ref=ref, title=st.title, status=st.status, since=since))
    return lines
