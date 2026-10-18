"""The ``GoalDirectory`` shadow adapter: goal states from the mirrored V1 goal context (spec §4.2).

Owned by track S (store, import, shadow); increment I1, spec §12.2 (AT-S7). The class is fixed by
the skeleton because ``dec.api.default_env`` constructs it; the track implements it.

It reads ``dec_foreign_context`` (kind ``goal``) through ``kernel.store.api.read_connection``:
status, ``status_changed_at`` (its date) and ``first_seen_status_run_id`` (the as-of date of that
run is ``first_seen_date``), as known at ``as_of`` on the knowledge axis. Refs are foreign refs as
DEC links store them (``V1_G901``). WRK replaces it at stage 1.

Spec note: ``dec_foreign_context`` keeps a goal's current state only, so "as known at ``as_of``"
is answered for that state: it is known from the end of its change date in the owner's zone, or,
when the change date is unknown, from the ``as_of`` of the first snapshot that showed it, and never
later than that snapshot. Before then the adapter answers ``None`` (the earlier state is not kept),
which asks no ``goal_changed`` question, as §3.13 wants for an ``as_of`` before the change was
known.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from coflow.kernel.config.profile import load_profile
from coflow.kernel.context import end_of_local_day, parse_instant
from coflow.kernel.ports.goal_directory import GoalOffer, GoalState
from coflow.kernel.store.api import read_connection

__all__ = ["ShadowGoalDirectory"]


def _date(value: object) -> date | None:
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)[:10])


class ShadowGoalDirectory:
    """Implements ``kernel.ports.goal_directory.GoalDirectory`` over ``dec_foreign_context``."""

    def state(self, ref: str, as_of: datetime | None = None) -> GoalState | None:
        issuer, sep, source_ref = ref.partition("_")
        if not sep or not issuer or not source_ref:
            return None
        with read_connection() as conn:
            row = conn.execute(
                "SELECT title, status, status_changed_at, first_seen_status_run_id "
                "FROM dec_foreign_context WHERE issuer = ? AND kind = 'goal' AND foreign_ref = ?",
                (issuer, source_ref),
            ).fetchone()
            if row is None or row["status"] is None:
                return None
            run = None
            if row["first_seen_status_run_id"] is not None:
                run = conn.execute(
                    "SELECT as_of, as_of_date FROM dec_import_runs WHERE id = ?",
                    (row["first_seen_status_run_id"],),
                ).fetchone()
            timezone = load_profile(conn).timezone if as_of is not None else None
        changed = _date(row["status_changed_at"])
        seen_at = parse_instant(run["as_of"]) if run is not None and run["as_of"] else None
        if as_of is not None:
            known_at = end_of_local_day(changed, timezone) if changed and timezone else seen_at
            if seen_at is not None and known_at is not None:
                known_at = min(known_at, seen_at)
            if known_at is not None and as_of < known_at:
                return None
        return GoalState(
            ref=ref,
            title=row["title"],
            status=str(row["status"]),
            status_changed_date=changed,
            first_seen_date=_date(run["as_of_date"]) if run is not None else None,
        )

    def likely_goals(
        self, text: str, *, subjects: Sequence[str] = (), limit: int = 3
    ) -> list[GoalOffer]:
        raise NotImplementedError("stage 1: WRK implements likely_goals (WRK-8)")
