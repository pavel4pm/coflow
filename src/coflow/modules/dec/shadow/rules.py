"""The expected-difference rules SR-1 to SR-10 of spec §6.6 and the v1 → v2 label mapping, each
rule with its own test (AT-S5). A rule's condition is evaluated on v2's own computed values
(``model.HealthResult`` carries the per-assumption states and the pool for that).

Owned by track S (store, import, shadow); increment I1, spec §12.2.

A difference is classified by the **first** rule, in table order, whose condition holds; anything
else is ``unexpected``. Health differences are checked against SR-1 to SR-8 (each names the v1 and
v2 labels it explains); an extra v2 waiting reason against SR-7 to SR-10; a reason v1 lists and
v2 does not is always unexpected.

Spec notes:

- "Timeliness clean" (SR-4) means no timeliness kind but ``ON_SCHEDULE`` and ``DUE_TODAY``: a
  review due today does not keep a holding decision from ``ON_TRACK`` (§3.7 step 6).
- SR-7 and SR-8 say "WATCH unless a higher label applies". A higher label (STALE, INSUFFICIENT_DATA,
  REVIEW_REQUIRED, a flag) is explained by its own cause, not by these rules, so their health form
  is ``ON_TRACK`` → ``WATCH`` only (v1 ``WATCH`` against v2 ``WATCH`` is simply ``same``).
- A non-critical violation exists only when critical assumptions exist (otherwise the pool is
  every assumption, §3.7), so SR-7's "critical ones present" holds whenever a violated reason is
  marked non-critical, or an assumption outside the pool is VIOLATED.
- SR-9's condition is the ``goal_changed`` reason itself: v2 produces it exactly when a served or
  tested goal ended after the decided date and after the last review (§3.13).
- SR-10 explains a violated reason of a decision with a manual flag, when SR-7 does not (a
  critical violation).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coflow.kernel.ports.decision_directory import Reason
from coflow.modules.dec.domain.model import HealthResult

__all__ = [
    "HEALTH_RULES",
    "REASON_RULES",
    "RULE_IDS",
    "RuleFacts",
    "classify_extra_reason",
    "classify_health",
    "map_v1_label",
]

RULE_IDS: tuple[str, ...] = tuple(f"SR-{n}" for n in range(1, 11))
CLEAN_TIMELINESS = frozenset({"ON_SCHEDULE", "DUE_TODAY"})


@dataclass(frozen=True, slots=True, kw_only=True)
class RuleFacts:
    """v2's own values for one decision at the snapshot's as-of: its health and its head."""

    health: HealthResult
    status: str
    is_mirror: bool
    review_due: date | None
    manual_flag: str | None
    share_limit: Decimal

    def pool_states(self) -> list[str]:
        return [self.health.states.get(code, "") for code in self.health.pool]

    def non_critical_violated(self) -> bool:
        pool = set(self.health.pool)
        return any(s == "VIOLATED" and c not in pool for c, s in self.health.states.items())


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthRule:
    rule_id: str
    v1: frozenset[str]
    v2: frozenset[str]
    condition: Callable[[RuleFacts], bool]
    why: str


def _sr1(f: RuleFacts) -> bool:
    t = f.health.timeliness
    return f.health.ground == "AWAITING" and not (t & {"NO_REVIEW_DATE", "CHECK_OVERDUE"})


def _sr2(f: RuleFacts) -> bool:
    if "REVIEW_OVERDUE" not in f.health.timeliness:
        return False
    if f.health.ground == "NO_ASSUMPTIONS":
        return True
    states = f.pool_states()
    return bool(states) and all(s == "UNVERIFIABLE" for s in states)


def _sr3(f: RuleFacts) -> bool:
    share = f.health.share
    return (
        f.health.ground == "INSUFFICIENT"
        and share is not None
        and f.share_limit < share < 1
        and "REVIEW_OVERDUE" not in f.health.timeliness
    )


def _sr4(f: RuleFacts) -> bool:
    share = f.health.share
    return (
        f.health.ground == "HOLDING"
        and "UNVERIFIABLE" in f.pool_states()
        and share is not None
        and share <= f.share_limit
        and f.health.timeliness <= CLEAN_TIMELINESS
    )


def _sr5(f: RuleFacts) -> bool:
    return f.health.ground == "HOLDING" and "CHECK_OVERDUE" in f.health.timeliness


def _sr6(f: RuleFacts) -> bool:
    return f.health.ground == "HOLDING" and "NO_DATA_SINCE" in f.health.timeliness


def _sr7(f: RuleFacts) -> bool:
    return f.non_critical_violated()


def _sr8(f: RuleFacts) -> bool:
    return f.is_mirror and f.status == "active" and f.review_due is None


def _labels(*names: str) -> frozenset[str]:
    return frozenset(names)


HEALTH_RULES: tuple[HealthRule, ...] = (
    HealthRule(
        rule_id="SR-1",
        v1=_labels("WATCH"),
        v2=_labels("AWAITING_CHECKS"),
        condition=_sr1,
        why="v1's 'not yet checked' WATCH carried no signal",
    ),
    HealthRule(
        rule_id="SR-2",
        v1=_labels("INSUFFICIENT_DATA"),
        v2=_labels("STALE"),
        condition=_sr2,
        why="v1 masked an overdue review",
    ),
    HealthRule(
        rule_id="SR-3",
        v1=_labels("WATCH"),
        v2=_labels("INSUFFICIENT_DATA"),
        condition=_sr3,
        why="a mostly uncheckable ground is fog, not 'watch'",
    ),
    HealthRule(
        rule_id="SR-4",
        v1=_labels("WATCH"),
        v2=_labels("ON_TRACK"),
        condition=_sr4,
        why="v1 called holding + unverifiable '0 not yet checked'",
    ),
    HealthRule(
        rule_id="SR-5",
        v1=_labels("ON_TRACK"),
        v2=_labels("WATCH"),
        condition=_sr5,
        why="a holding state with an overdue check is not on track",
    ),
    HealthRule(
        rule_id="SR-6",
        v1=_labels("ON_TRACK"),
        v2=_labels("WATCH"),
        condition=_sr6,
        why="stale 'holding' is not on track (P-9)",
    ),
    HealthRule(
        rule_id="SR-7",
        v1=_labels("ON_TRACK"),
        v2=_labels("WATCH"),
        condition=_sr7,
        why="health and waiting agree in v2; v1 ignored non-critical violations",
    ),
    HealthRule(
        rule_id="SR-8",
        v1=_labels("ON_TRACK"),
        v2=_labels("WATCH"),
        condition=_sr8,
        why="an active record without a review date waits in v2",
    ),
)

REASON_RULES: Mapping[str, str] = {
    "SR-7": "a non-critical violated assumption waits in v2",
    "SR-8": "an active mirror without a review date waits as 'incomplete'",
    "SR-9": "a served or tested goal ended after the decision and after its last review",
    "SR-10": "a violation under a manual flag waits in v2; v1 listed violations only under "
    "REVIEW_REQUIRED, which the flag hides",
}


def map_v1_label(label: str) -> tuple[str, str | None]:
    """v1's label as v2's, with the outcome of a closed decision: ``CLOSED_SUCCESS`` →
    ``('CLOSED', 'success')``; the other labels are the same names (§6.6)."""
    if label.startswith("CLOSED_"):
        return "CLOSED", label[len("CLOSED_") :].lower()
    return label, None


def _badge_outcome(badge: str | None) -> str | None:
    if not badge:
        return None
    return badge.split("·")[0].strip().split(" ")[0].lower() or None


def health_same(v1_label: str, v2: HealthResult) -> bool:
    label, outcome = map_v1_label(v1_label)
    if label != v2.label:
        return False
    if label == "CLOSED" and outcome is not None:
        badge = _badge_outcome(v2.badge)
        return badge is None or badge == outcome
    return True


def classify_health(v1_label: str, facts: RuleFacts) -> tuple[str, str | None]:
    """``('same', None)``, ``('expected', 'SR-n')`` or ``('unexpected', None)``."""
    if health_same(v1_label, facts.health):
        return "same", None
    label, _ = map_v1_label(v1_label)
    for rule in HEALTH_RULES:
        if label in rule.v1 and facts.health.label in rule.v2 and rule.condition(facts):
            return "expected", rule.rule_id
    return "unexpected", None


def classify_extra_reason(reason: Reason, facts: RuleFacts) -> str | None:
    """The rule that explains a reason v2 lists and v1 does not, or ``None`` (unexpected)."""
    if reason.kind == "violated" and reason.critical is False:
        return "SR-7"
    if reason.kind == "incomplete" and _sr8(facts):
        return "SR-8"
    if reason.kind == "goal_changed":
        return "SR-9"
    if reason.kind == "violated" and facts.manual_flag is not None:
        return "SR-10"
    return None
