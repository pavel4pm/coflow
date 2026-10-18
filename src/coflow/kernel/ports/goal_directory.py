"""``GoalDirectory``: the state of goals a decision serves or tests, without importing WRK or GOL.

Skeleton file (ARCHITECTURE §5.1, spec §4.2, §12.1). In the slice it is implemented by DEC's shadow
adapter over the goal context mirrored from V1 (``modules/dec/goals_shadow.py``, track S); WRK
implements it at stage 1 and GOL at 8.2.

Spec note: the slice uses ``state`` only. ``likely_goals`` (WRK-8) is declared for stage 1 so the
protocol does not change then; the shadow adapter may raise ``NotImplementedError`` for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

__all__ = ["ENDED_GOAL_STATUSES", "GoalDirectory", "GoalOffer", "GoalState"]

ENDED_GOAL_STATUSES: frozenset[str] = frozenset(
    {"dropped", "paused", "achieved", "abandoned", "superseded", "closed"}
)
"""``ENDED`` of §3.13: a served goal in one of these states asks ``goal_changed`` once."""


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalState:
    """A goal's status at a time. ``first_seen_date`` is the as-of date of the first snapshot run
    that saw the current status; it stands in when the change date is unknown (§3.13)."""

    ref: str
    title: str | None
    status: str
    status_changed_date: date | None
    first_seen_date: date | None


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalOffer:
    """A likely goal offered when a decision is created [stage 1]."""

    ref: str
    title: str | None
    reason: str


@runtime_checkable
class GoalDirectory(Protocol):
    def state(self, ref: str, as_of: datetime | None = None) -> GoalState | None:
        """The goal's state as known at ``as_of`` (knowledge axis); ``None`` when unknown."""
        ...

    def likely_goals(
        self, text: str, *, subjects: Sequence[str] = (), limit: int = 3
    ) -> list[GoalOffer]:
        """[stage 1, WRK-8]."""
        ...
