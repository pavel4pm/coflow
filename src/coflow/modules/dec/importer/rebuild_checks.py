"""``rebuild_checks`` (spec §6.5): reconstructed assessments from v1's state versions and from
snapshot diffs where only ``last_checked_at`` moved; the state map of §6.3 (AT-S1, AT-S3).

Owned by track S (store, import, shadow); increment I1, spec §12.2.

v1 has no check log, so v2 builds one from what the snapshots show. Every row it writes is an
assessment with ``proposed_by = 'import'``, ``next_check_rule = 'import'`` and
``reconstructed = 1``:

1. **Explicit history.** Each v1 version row of an assumption's ``state`` that is not mirrored yet
   becomes one assessment observed at its ``changed_at`` (precision ``instant``), known from then.
2. **A snapshot diff.** When ``last_checked_at`` names a day on which the assumption has no
   assessment yet, one assessment of the snapshot's state is added, observed on that day
   (precision ``day``) and known from the end of that day in the source's zone, or from the
   snapshot's ``as_of`` if that is earlier.
3. **The first state of a new mirror** without ``last_checked_at``: HOLDING, DRIFTING, VIOLATED,
   or UNVERIFIABLE with a data source, is one assessment with an unknown observed time, known
   from the snapshot's ``as_of``. NOT_YET_DUE, and UNVERIFIABLE without a source (data source
   kind ``none``), add nothing.

The state map: v1's ``NOT_YET_DUE`` with a ``last_checked_at`` (a state reset in v1) is
``UNKNOWN``, noted "state reset in V1"; the other states are kept.

Spec notes:

- §6.5 compares ``last_checked_at`` with the previous snapshot's. The previous value is read back
  from the reconstructed log instead of being stored: an assessment already observed on that day
  means the date did not move. So the same file, or a newer one with the same date, adds nothing,
  and "checks between two snapshots that leave no version row and repeat the same date are
  invisible", as §6.5 states.
- "Known from the end of that day" is capped at the snapshot's ``as_of``, so a check made on the
  snapshot's own day is visible to the shadow computed at ``as_of`` on the knowledge axis.
- ``last_checked_at`` is a day in the source's zone, so "a day without an assessment" compares
  it with the source-zone days of the assessments (found in review: comparing owner-zone days of
  version instants added a duplicate near midnight when the zones differ).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from coflow.kernel.context import end_of_local_day, format_instant, local_date, parse_instant
from coflow.kernel.ids import codes
from coflow.kernel.store.api import current_unit, insert, update_head
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.store import mirror
from coflow.modules.dec.store.mirror import MirrorState

if TYPE_CHECKING:
    from coflow.modules.dec.importer.apply import RunContext

__all__ = ["map_snapshot_state", "map_version_state", "rebuild_checks"]

KEPT_STATES = frozenset({"HOLDING", "DRIFTING", "VIOLATED", "UNVERIFIABLE"})
RESET_NOTE = "state reset in {issuer}"


def map_version_state(value: object) -> tuple[str, bool] | None:
    """A v1 state value as a stored assessment state and whether it is a reset; ``None`` when the
    value is no v1 state."""
    if value in KEPT_STATES:
        return str(value), False
    if value == "NOT_YET_DUE":
        return "UNKNOWN", True
    return None


def map_snapshot_state(state: str, *, has_last_checked: bool, has_source: bool) -> str | None:
    """§6.3: the assessment a snapshot's assumption state stands for, or ``None`` for no row."""
    if state == "NOT_YET_DUE":
        return "UNKNOWN" if has_last_checked else None
    if state == "UNVERIFIABLE" and not has_last_checked and not has_source:
        return None
    return state if state in KEPT_STATES else None


def _observed_day(row: Mapping[str, Any], tz: str) -> date | None:
    if row["observed_precision"] == "unknown" or row["observed_at"] is None:
        return None
    text = str(row["observed_at"])
    if row["observed_precision"] == "instant":
        return local_date(parse_instant(text), tz)
    return date.fromisoformat(text[:10])


class _Log:
    """The check log of one assumption inside the unit: its assessments and its counter."""

    def __init__(self, assumption_id: int, decision_id: int, origin_ref: str) -> None:
        self.assumption_id = assumption_id
        self.decision_id = decision_id
        self.origin_ref = origin_ref
        unit = current_unit()
        self.rows = unit.fetch_all(
            "SELECT observed_at, observed_precision FROM dec_checks "
            "WHERE assumption_id = ? AND kind = 'assessment' AND voided_at IS NULL",
            (assumption_id,),
        )
        head = unit.fetch_one(
            "SELECT ck_seq, status FROM dec_assumptions WHERE id = ?", (assumption_id,)
        )
        self.ck_seq = int(head["ck_seq"]) if head else 0
        self.active = bool(head) and head["status"] == "active"
        self.days: set[date] = set()
        self.added = 0

    def known_days(self, tz: str) -> set[date]:
        days = {d for d in (_observed_day(r, tz) for r in self.rows) if d is not None}
        return days | self.days

    @property
    def empty(self) -> bool:
        return not self.rows and not self.added

    def append(
        self,
        *,
        state: str,
        observed_at: str | None,
        precision: str,
        known_at: str,
        note: str | None,
        day: date | None,
    ) -> int:
        self.ck_seq += 1
        check_id = insert(
            "dec_checks",
            {
                "assumption_id": self.assumption_id,
                "decision_id": self.decision_id,
                "code_n": self.ck_seq,
                "kind": "assessment",
                "state": state,
                "observed_at": observed_at,
                "observed_precision": precision,
                "observed_basis": "import" if observed_at else "unknown",
                "next_check_rule": "import",
                "note": note,
                "proposed_by": "import",
                "reconstructed": 1,
                "origin_recorded_at": known_at,
                "origin_ref": self.origin_ref,
            },
        )
        self.added += 1
        if day is not None:
            self.days.add(day)
        return check_id

    def flush(self) -> None:
        if not self.added:
            return
        row = current_unit().fetch_one(
            "SELECT version FROM dec_assumptions WHERE id = ?", (self.assumption_id,)
        )
        update_head("dec_assumptions", self.assumption_id, int(row["version"]), ck_seq=self.ck_seq)


def _remember(run: RunContext, key: str, check_id: int, digest: str) -> None:
    existing = run.states.get(("version", key))
    mirror.put_state(
        issuer=run.issuer,
        source_kind="version",
        source_id=key,
        local_table="dec_checks",
        local_id=check_id,
        content_hash=digest,
        run_id=run.run_id,
        existing=existing,
    )
    run.states[("version", key)] = MirrorState(
        issuer=run.issuer,
        source_kind="version",
        source_id=key,
        local_table="dec_checks",
        local_id=check_id,
        content_hash=digest,
        first_run_id=existing.first_run_id if existing else run.run_id,
        last_run_id=run.run_id,
        absent_since_run_id=None,
        adopted_at=None,
    )


def _source_day(value: object) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    return date.fromisoformat(str(value)[:10])


def rebuild_checks(
    *,
    decision_id: int,
    assumptions: Sequence[tuple[Mapping[str, Any], int]],
    versions: Sequence[Mapping[str, Any]],
    run: RunContext,
) -> int:
    """Append the reconstructed assessments of one decision's assumptions; returns how many.

    ``assumptions`` pairs each source assumption with its current local row (a successor when the
    source changed its basis). Runs inside the importer's unit of work.
    """
    added = 0
    by_assumption: dict[int, list[Mapping[str, Any]]] = {}
    for v in versions:
        if v["entity"] == "assumption" and v["field"] == "state":
            by_assumption.setdefault(int(v["entity_v1_id"]), []).append(v)
    issuer_note = RESET_NOTE.format(issuer=run.issuer)
    for src, local_id in assumptions:
        log = _Log(local_id, decision_id, codes.foreign_ref(run.issuer, str(src["v1_id"])))
        if not log.active:
            continue
        # 1. explicit history
        for v in sorted(
            by_assumption.get(int(src["v1_id"]), ()), key=lambda v: (v["changed_at"], v["v1_id"])
        ):
            key = str(v["v1_id"])
            if ("version", key) in run.states:
                continue
            mapped = map_version_state(v.get("new_value"))
            if mapped is None:
                run.findings.append(
                    f"a state version of assumption {src['v1_id']} holds no v1 state; skipped"
                )
                continue
            state, reset = mapped
            changed_at = parse_instant(str(v["changed_at"]))
            text = format_instant(changed_at)
            check_id = log.append(
                state=state,
                observed_at=text,
                precision="instant",
                known_at=text,
                note=issuer_note if reset else None,
                day=local_date(changed_at, run.source_timezone),
            )
            _remember(run, key, check_id, cfj.sha256_hex(cfj.cfj(v)))
        # 2. a snapshot diff: last_checked_at names a day without an assessment
        day = _source_day(src.get("last_checked_at"))
        has_source = bool((src.get("data_source") or "").strip())
        if day is not None and day not in log.known_days(run.source_timezone):
            state = map_snapshot_state(src["state"], has_last_checked=True, has_source=has_source)
            if state is not None:
                known: datetime = min(end_of_local_day(day, run.source_timezone), run.as_of)
                log.append(
                    state=state,
                    observed_at=day.isoformat(),
                    precision="day",
                    known_at=format_instant(known),
                    note=issuer_note if src["state"] == "NOT_YET_DUE" else None,
                    day=day,
                )
        # 3. the first state of a new mirror without last_checked_at
        elif day is None and log.empty:
            state = map_snapshot_state(src["state"], has_last_checked=False, has_source=has_source)
            if state is not None:
                log.append(
                    state=state,
                    observed_at=None,
                    precision="unknown",
                    known_at=run.as_of_text,
                    note=None,
                    day=None,
                )
        log.flush()
        added += log.added
    return added
