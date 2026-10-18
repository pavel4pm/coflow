"""In-memory ``DecisionView`` builders for the health agreement test (AT-D3, track S).

Each assumption is planted in one effective state at ``T`` (2026-11-15 in Europe/Berlin):

- an assessed state (HOLDING, DRIFTING, VIOLATED, UNVERIFIABLE, UNKNOWN): one assessment observed
  ``check_age`` days before ``T`` (45 by default), with no next check date and no date in its text,
  so its due date falls back to the review;
- UNVERIFIABLE without a check: data source kind ``none``;
- NOT_YET_DUE: no check, an explicit next check 10 days after ``T``;
- UNCHECKED: no check, an explicit next check 3 days before ``T`` (so a check is overdue).

The decision was decided and activated on 2026-09-01. "Fresh" adds a monitoring fact two days
before ``T``; "stale" adds nothing, so the last activity is the oldest of the assessments, the
review and the activation, all more than 30 days back.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from coflow.kernel.context import EvalTime, start_of_local_day
from coflow.modules.dec.domain.model import (
    AssumptionView,
    CheckView,
    DecisionView,
    FactView,
    OutcomeView,
    ReviewView,
)

TZ = "Europe/Berlin"
T = EvalTime.at(datetime(2026, 11, 15, 9, 30, tzinfo=UTC), TZ)
DECIDED = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
ASSESSED = ("HOLDING", "DRIFTING", "VIOLATED", "UNVERIFIABLE", "UNKNOWN")
STATES = (*ASSESSED, "NOT_YET_DUE", "UNCHECKED")
REVIEWS = ("none", "future", "today", "overdue", "reviewed")


@dataclass(frozen=True, slots=True)
class Plant:
    critical: bool
    state: str
    via_source_none: bool = False  # UNVERIFIABLE by data source kind none, without a check
    check_age: int = 45
    frequency: str | None = None
    next_check: date | None = None
    threshold_text: str | None = None


def _at(day: date, hour: int = 10) -> datetime:
    return start_of_local_day(day, TZ) + timedelta(hours=hour)


def _check(a_id: int, n: int, ref: str, state: str, day: date) -> CheckView:
    return CheckView(
        tx=1,
        recorded_at=_at(day),
        id=a_id * 100 + n,
        assumption_id=a_id,
        decision_id=1,
        code_n=n,
        code=f"CK-{n:03d}",
        ref=f"{ref}_CK-{n:03d}",
        kind="assessment",
        state=state,  # type: ignore[arg-type]
        reading_id=None,
        observed_value=None,
        observed_text=None,
        observed_at=day,
        observed_precision="day",
        observed_basis="stated",
        due_answered=None,
        due_source_answered=None,
        next_check_set=None,
        next_check_rule="none",
        evidence_kind=None,
        evidence_ref=None,
        evidence_quote=None,
        quote_verified=None,
        note=None,
        proposed_by="owner",
        reconstructed=False,
    )


def assumption(index: int, plant: Plant, decision_ref: str = "D-0042") -> AssumptionView:
    n = index + 1
    a_id = 10 + n
    ref = f"{decision_ref}_A-{n:02d}"
    checks: tuple[CheckView, ...] = ()
    kind = "manual"
    next_check = plant.next_check
    if plant.state in ASSESSED and not plant.via_source_none:
        checks = (_check(a_id, 1, ref, plant.state, T.date - timedelta(days=plant.check_age)),)
    elif plant.state == "UNVERIFIABLE":
        kind = "none"
    elif plant.state == "NOT_YET_DUE" and next_check is None and not plant.threshold_text:
        next_check = T.date + timedelta(days=10)
    elif plant.state == "UNCHECKED" and next_check is None and not plant.threshold_text:
        next_check = T.date - timedelta(days=3)
    return AssumptionView(
        tx=1,
        recorded_at=DECIDED,
        id=a_id,
        decision_id=1,
        code_n=n,
        code=f"A-{n:02d}",
        ref=ref,
        position=n,
        statement=f"Assumption number {n} holds",
        metric=None,
        comparator=None,
        threshold_value=None,
        threshold_value2=None,
        unit=None,
        threshold_text=plant.threshold_text,
        by_date=None,
        judge_from=None,
        drift_margin=None,
        data_source_kind=kind,  # type: ignore[arg-type]
        data_source_text=None,
        data_source_ref=None,
        check_frequency=plant.frequency,  # type: ignore[arg-type]
        next_check_at=next_check,
        is_critical=plant.critical,
        scope=None,
        check_cost=None,
        class_tag=None,
        probability=None,
        probability_by=None,
        probability_recorded_at=None,
        shareable=False,
        status="active",
        superseded_by=None,
        drop_reason=None,
        added_in_edition=1,
        salt="0" * 32,
        version=1,
        checks=checks,
    )


def _fact(day: date) -> FactView:
    return FactView(
        tx=1,
        recorded_at=_at(day),
        id=501,
        decision_id=1,
        code_n=1,
        code="FT-001",
        ref="D-0042_FT-001",
        phase="monitoring",
        kind="observation",
        claimed_outcome=None,
        text="Something happened",
        occurred_at=day,
        occurred_precision="day",
        occurred_basis="stated",
        evidence_kind="owner_statement",
        evidence_ref=None,
        evidence_quote=None,
        quote_verified=None,
        source_text=None,
        reported_by="owner",
        added_in_edition=None,
        corrects_fact_id=None,
        salt="1" * 32,
        reconstructed=False,
    )


def _review(day: date, next_due: date | None) -> ReviewView:
    return ReviewView(
        tx=1,
        recorded_at=_at(day),
        id=601,
        decision_id=1,
        code_n=1,
        code="R-01",
        ref="D-0042_R-01",
        action="keep",
        verdict="still fine",
        notes=None,
        revise_basis=None,
        trigger="scheduled",
        trigger_ref=None,
        trigger_at=None,
        occurred_at=day,
        occurred_precision="day",
        occurred_basis="live",
        next_review_due=next_due,
        status_before="active",
        review_due_before=None,
        edition_before=1,
        edition_after=1,
        health_before=None,
        ground_before=None,
        timeliness_before=None,
        unverifiable_before=None,
        unverifiable_after=None,
        reasons_answered_json=None,
        execution_summary_json=None,
        successor_ref=None,
        is_correction=False,
        legacy_health_at_review=None,
        reconstructed=False,
    )


def decision(
    plants: Sequence[Plant],
    *,
    review: str = "future",
    review_in: int = 10,
    fresh: bool = False,
    fact_age: int | None = None,
    depth: str = "full",
    flag: str | None = None,
    mirror: bool = False,
    status: str = "active",
    outcome: tuple[str, str] | None = None,
) -> DecisionView:
    """One decision at ``T``: ``review`` is none, future (``review_in`` days), today, overdue (5
    days) or reviewed (due 50 days back, reviewed 40 days back)."""
    reviews: tuple[ReviewView, ...] = ()
    if review == "none":
        review_due = None
    elif review == "future":
        review_due = T.date + timedelta(days=review_in)
    elif review == "today":
        review_due = T.date
    elif review == "overdue":
        review_due = T.date - timedelta(days=5)
    elif review == "reviewed":
        review_due = T.date - timedelta(days=50)
        reviews = (_review(T.date - timedelta(days=40), None),)
    else:
        raise ValueError(review)
    facts: tuple[FactView, ...] = ()
    if fresh:
        facts = (_fact(T.date - timedelta(days=2)),)
    elif fact_age is not None:
        facts = (_fact(T.date - timedelta(days=fact_age)),)
    outcomes: tuple[OutcomeView, ...] = ()
    if outcome is not None:
        outcomes = (
            OutcomeView(
                tx=1,
                recorded_at=_at(T.date - timedelta(days=1)),
                id=701,
                decision_id=1,
                review_id=None,
                kind=outcome[0],  # type: ignore[arg-type]
                basis=outcome[1],  # type: ignore[arg-type]
                evidence_refs=(),
                measured_value=None,
                expected_vs_actual=None,
                occurred_at=None,
                occurred_precision="unknown",
                occurred_basis="unknown",
                resolved_by="owner",
                supersedes_outcome_id=None,
                reconstructed=False,
            ),
        )
    return DecisionView(
        tx=1,
        recorded_at=DECIDED,
        id=1,
        public_id="D-0042",
        number=42,
        title="A planted decision",
        question="Which way?",
        statement="This way",
        kind="choice",
        decider="self",
        decider_basis="stated",
        decider_ref=None,
        depth=depth,  # type: ignore[arg-type]
        depth_basis="owner",
        reversibility="unknown",
        status=status,  # type: ignore[arg-type]
        manual_flag=flag,  # type: ignore[arg-type]
        manual_flag_reason="set by the owner" if flag else None,
        context=None,
        known=None,
        would_help=None,
        unknowns=("one unknown",),
        success_criterion=None,
        expected_metric=None,
        expected_target=None,
        expected_unit=None,
        expected_by=None,
        expected_text=None,
        confidence=None,
        not_doing=None,
        review_due=review_due,
        review_due_initial=review_due,
        decided_at=DECIDED.date(),
        decided_precision="day",
        decided_basis="stated",
        activated_at=DECIDED,
        closed_at=_at(T.date - timedelta(days=1)) if status == "closed" else None,
        current_edition=1,
        completion_pending=False,
        origin_kind="cli",
        origin_quote=None,
        publishability="private",
        third_party_sensitive=False,
        reconstructed=mirror,
        mirror_of="V1_D42" if mirror else None,
        mirror_scope="full" if mirror else None,
        notes=None,
        legacy_json=None,
        version=1,
        assumptions=tuple(assumption(i, p) for i, p in enumerate(plants)),
        facts=facts,
        reviews=reviews,
        outcomes=outcomes,
    )
