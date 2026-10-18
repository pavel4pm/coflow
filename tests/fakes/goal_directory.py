"""A fake ``GoalDirectory``: goal states by ref, optionally different before a cut-over instant."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from coflow.kernel.ports.goal_directory import GoalOffer, GoalState


@dataclass
class FakeGoalDirectory:
    """``states`` hold the current state; ``earlier`` holds (cut-over instant, state) for refs whose
    state at an ``as_of`` before the cut-over was different (for as-of tests)."""

    states: dict[str, GoalState] = field(default_factory=dict)
    earlier: dict[str, tuple[datetime, GoalState | None]] = field(default_factory=dict)
    offers: list[GoalOffer] = field(default_factory=list)
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def state(self, ref: str, as_of: datetime | None = None) -> GoalState | None:
        self.calls.append(("state", (ref, as_of)))
        if as_of is not None and ref in self.earlier:
            cut, before = self.earlier[ref]
            if as_of < cut:
                return before
        return self.states.get(ref)

    def likely_goals(
        self, text: str, *, subjects: Sequence[str] = (), limit: int = 3
    ) -> list[GoalOffer]:
        self.calls.append(("likely_goals", (text, tuple(subjects), limit)))
        return self.offers[:limit]
