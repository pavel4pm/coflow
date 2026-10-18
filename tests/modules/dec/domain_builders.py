"""Builders of DEC views for track D's domain tests (synthetic, in memory, no store).

A view is built from typed attributes, and its ``stored`` row is derived from them the way SQLite
would return it (booleans 0/1, instants as ``format_instant`` text, dates ISO, ``unknowns_json``),
so seals and integrity checks hash exactly what a loaded view would hash.

The world is the shared one of ``tests/conftest.py``: the owner's zone ``Europe/Berlin``, now
2026-11-15T09:30:00.000Z, today 2026-11-15. Times default to noon local time.

Usage::

    d = D(1001, review_due=days(10), assumptions=[A(1, checks=[CK(days(-2), "HOLDING")])])
    h = health(d, T, CFG)
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from coflow.kernel.context import EvalTime, format_instant, seeded_salts, zone
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.domain.model import (
    AssumptionView,
    CheckView,
    DecConfig,
    DecisionView,
    EditionView,
    FactView,
    ForkView,
    LinkView,
    OptionView,
    OutcomeView,
    ProposalView,
    ReadingView,
    ReviewView,
    StakeView,
    VersionView,
)

TZ = "Europe/Berlin"
CFG = DecConfig(timezone=TZ)
TODAY = date(2026, 11, 15)
NOW = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
T = EvalTime.at(NOW, TZ)

_UNSET = datetime(1970, 1, 1, tzinfo=UTC)
_ids = itertools.count(1)
_CHILDREN = frozenset(
    {
        "options",
        "assumptions",
        "facts",
        "reviews",
        "outcomes",
        "learnings",
        "stakes",
        "links",
        "editions",
        "versions",
        "checks",
        "readings",
        "bearings",
    }
)
_NOT_COLUMNS = frozenset({"stored", "code", "ref", "absent_since_run_id", "adopted_at"})


def days(n: int) -> date:
    """A date relative to today."""
    return TODAY + timedelta(days=n)


def noon(day: date) -> datetime:
    """Noon local time on ``day``, as a UTC instant."""
    return datetime.combine(day, time(12), tzinfo=zone(TZ)).astimezone(UTC)


def at_day(day: date) -> EvalTime:
    """``T`` at 10:30 local time on ``day``."""
    return EvalTime.at(datetime.combine(day, time(10, 30), tzinfo=zone(TZ)), TZ)


def _next_id() -> int:
    return next(_ids)


def _salt(n: int) -> str:
    return f"{n:032x}"


def _col(v: object) -> object:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, datetime):
        return format_instant(v)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    return v


def stored_of(view: Any) -> dict[str, object]:
    """The row as SQLite would return it, derived from the typed attributes."""
    out: dict[str, object] = {}
    for f in dataclasses.fields(view):
        if f.name in _CHILDREN or f.name in _NOT_COLUMNS:
            continue
        value = getattr(view, f.name)
        if f.name == "unknowns":
            out["unknowns_json"] = json.dumps(list(value), ensure_ascii=False)
        elif f.name == "evidence_refs":
            out["evidence_refs_json"] = json.dumps(list(value))
        else:
            out[f.name] = _col(value)
    return out


def finish[V](view: V) -> V:
    return dataclasses.replace(view, stored=stored_of(view))  # type: ignore[type-var]


def _precision(at: object) -> str:
    if at is None:
        return "unknown"
    return "instant" if isinstance(at, datetime) else "day"


def _recorded(at: date | datetime | None, recorded: datetime | None) -> datetime:
    if recorded is not None:
        return recorded
    if isinstance(at, datetime):
        return at
    if isinstance(at, date):
        return noon(at)
    return NOW - timedelta(days=1)


# ==================================================================================================
# Children (attached to their parents by ``A`` and ``D``)


def CK(
    observed: date | datetime | None,
    state: str | None = "HOLDING",
    *,
    kind: str = "assessment",
    recorded: datetime | None = None,
    voided_at: datetime | None = None,
    next_check_set: date | None = None,
    note: str | None = None,
    proposed_by: str = "owner",
    reconstructed: bool = False,
) -> CheckView:
    rec = _recorded(observed, recorded)
    return CheckView(
        tx=1,
        recorded_at=rec,
        id=_next_id(),
        assumption_id=0,
        decision_id=0,
        code_n=0,
        code="",
        ref="",
        kind=kind,  # type: ignore[arg-type]
        state=state if kind == "assessment" else None,  # type: ignore[arg-type]
        reading_id=None,
        observed_value=None,
        observed_text=None,
        observed_at=observed,
        observed_precision=_precision(observed),  # type: ignore[arg-type]
        observed_basis="live" if observed is not None else "unknown",
        due_answered=None,
        due_source_answered=None,
        next_check_set=next_check_set,
        next_check_rule="postpone" if kind == "postponement" else "none",
        evidence_kind=None,
        evidence_ref=None,
        evidence_quote=None,
        quote_verified=None,
        note=note,
        proposed_by=proposed_by,  # type: ignore[arg-type]
        reconstructed=reconstructed,
        voided_at=voided_at,
    )


def RD(
    observed: date | datetime | None, value: str | None = "1", *, unit: str | None = None
) -> ReadingView:
    return ReadingView(
        tx=1,
        recorded_at=_recorded(observed, None),
        id=_next_id(),
        assumption_id=0,
        decision_id=0,
        code_n=0,
        code="",
        ref="",
        value=value,
        unit=unit,
        value_text=None,
        observed_at=observed,
        observed_precision=_precision(observed),  # type: ignore[arg-type]
        observed_basis="stated",
        source_kind="owner_statement",
        source_ref=None,
        quote=None,
        proposed_state=None,
        no_proposal_reason="text_threshold",
        proposed_by="owner",
        accepted_by_check_id=None,
    )


def A(
    code_n: int,
    *,
    statement: str = "The assumption holds",
    critical: bool = True,
    source: str = "manual",
    frequency: str | None = None,
    next_check_at: date | None = None,
    by_date: date | None = None,
    threshold_text: str | None = "a threshold in words",
    comparator: str | None = None,
    value: str | None = None,
    value2: str | None = None,
    unit: str | None = None,
    metric: str | None = None,
    judge_from: date | None = None,
    status: str = "active",
    checks: Sequence[CheckView] = (),
    readings: Sequence[ReadingView] = (),
    created: datetime | None = None,
    position: int | None = None,
    class_tag: str | None = None,
    erased: bool = False,
    added_in_edition: int | None = None,
) -> AssumptionView:
    aid = _next_id()
    return AssumptionView(
        tx=1,
        recorded_at=created or _UNSET,
        id=aid,
        decision_id=0,
        code_n=code_n,
        code=f"A-{code_n:02d}",
        ref="",
        position=position if position is not None else code_n,
        statement=statement,
        metric=metric,
        comparator=comparator,  # type: ignore[arg-type]
        threshold_value=value,
        threshold_value2=value2,
        unit=unit,
        threshold_text=threshold_text,
        by_date=by_date,
        judge_from=judge_from,
        drift_margin=None,
        data_source_kind=source,  # type: ignore[arg-type]
        data_source_text=None if source == "none" else "a source",
        data_source_ref=None,
        check_frequency=frequency,  # type: ignore[arg-type]
        next_check_at=next_check_at,
        is_critical=critical,
        scope=None,
        check_cost=None,
        class_tag=class_tag,
        probability=None,
        probability_by=None,
        probability_recorded_at=None,
        shareable=False,
        status=status,  # type: ignore[arg-type]
        superseded_by=None,
        drop_reason=None,
        added_in_edition=added_in_edition,
        salt=_salt(aid),
        version=1,
        erased_tx=99 if erased else None,
        checks=tuple(checks),
        readings=tuple(readings),
    )


def F(
    occurred: date | datetime | None,
    text: str = "Something happened",
    *,
    phase: str = "monitoring",
    kind: str = "observation",
    evidence_kind: str = "none",
    evidence_ref: str | None = None,
    recorded: datetime | None = None,
    voided_at: datetime | None = None,
    added_in_edition: int | None = None,
    erased: bool = False,
) -> FactView:
    fid = _next_id()
    return FactView(
        tx=1,
        recorded_at=_recorded(occurred, recorded),
        id=fid,
        decision_id=0,
        code_n=0,
        code="",
        ref="",
        phase=phase,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
        claimed_outcome="done" if kind == "outcome_report" else None,
        text=text,
        occurred_at=occurred,
        occurred_precision=_precision(occurred),  # type: ignore[arg-type]
        occurred_basis="stated" if occurred is not None else "unknown",
        evidence_kind=evidence_kind,  # type: ignore[arg-type]
        evidence_ref=evidence_ref,
        evidence_quote=None,
        quote_verified=None,
        source_text=None,
        reported_by="owner",
        added_in_edition=added_in_edition,
        corrects_fact_id=None,
        salt=_salt(fid),
        reconstructed=False,
        voided_at=voided_at,
        erased_tx=99 if erased else None,
    )


def R(
    occurred: date | datetime | None,
    action: str = "keep",
    *,
    next_review_due: date | None = None,
    recorded: datetime | None = None,
    voided_at: datetime | None = None,
    successor_ref: str | None = None,
) -> ReviewView:
    return ReviewView(
        tx=1,
        recorded_at=_recorded(occurred, recorded),
        id=_next_id(),
        decision_id=0,
        code_n=0,
        code="",
        ref="",
        action=action,  # type: ignore[arg-type]
        verdict=None,
        notes=None,
        revise_basis=None,
        trigger="scheduled",
        trigger_ref=None,
        trigger_at=None,
        occurred_at=occurred,
        occurred_precision=_precision(occurred),  # type: ignore[arg-type]
        occurred_basis="live",
        next_review_due=next_review_due,
        status_before=None,
        review_due_before=None,
        edition_before=None,
        edition_after=None,
        health_before=None,
        ground_before=None,
        timeliness_before=None,
        unverifiable_before=None,
        unverifiable_after=None,
        reasons_answered_json=None,
        execution_summary_json=None,
        successor_ref=successor_ref,
        is_correction=False,
        legacy_health_at_review=None,
        reconstructed=False,
        voided_at=voided_at,
    )


def L(
    role: str,
    target_ref: str,
    *,
    target_kind: str = "foreign_goal",
    removed_tx: int | None = None,
    created: datetime | None = None,
) -> LinkView:
    return LinkView(
        tx=1,
        recorded_at=created or _UNSET,
        id=_next_id(),
        decision_id=0,
        role=role,  # type: ignore[arg-type]
        target_ref=target_ref,
        target_kind=target_kind,  # type: ignore[arg-type]
        resolution="foreign",
        note=None,
        removed_tx=removed_tx,
    )


def OP(text: str, *, chosen: bool = False, erased: bool = False) -> OptionView:
    oid = _next_id()
    return OptionView(
        tx=1,
        recorded_at=_UNSET,
        id=oid,
        decision_id=0,
        fork_id=None,
        code_n=0,
        code="",
        ref="",
        text=text,
        chosen=chosen,
        why_rejected=None if chosen else "another option won",
        recorded_before_choice="yes",
        added_in_edition=None,
        origin="owner",
        salt=_salt(oid),
        erased_tx=99 if erased else None,
    )


def OC(kind: str, basis: str, *, supersedes: int | None = None) -> OutcomeView:
    return OutcomeView(
        tx=1,
        recorded_at=NOW - timedelta(days=1),
        id=_next_id(),
        decision_id=0,
        review_id=None,
        kind=kind,  # type: ignore[arg-type]
        basis=basis,  # type: ignore[arg-type]
        evidence_refs=(),
        measured_value=None,
        expected_vs_actual=None,
        occurred_at=TODAY - timedelta(days=1),
        occurred_precision="day",
        occurred_basis="stated",
        resolved_by="owner",
        supersedes_outcome_id=supersedes,
        reconstructed=False,
    )


def ST(amount: str = "120", *, currency: str = "EUR") -> StakeView:
    sid = _next_id()
    return StakeView(
        tx=1,
        recorded_at=_UNSET,
        id=sid,
        decision_id=0,
        type="money",
        amount=amount,
        currency=currency,
        period="once",
        count_periods=None,
        direction="cost",
        note=None,
        planned=True,
        added_in_edition=None,
        salt=_salt(sid),
    )


def V(
    entity: str,
    entity_id: int,
    field: str,
    old: str | None,
    new: str | None,
    *,
    recorded: datetime,
) -> VersionView:
    return finish(
        VersionView(
            tx=1,
            recorded_at=recorded,
            id=_next_id(),
            entity=entity,  # type: ignore[arg-type]
            entity_id=entity_id,
            field=field,
            old_value=old,
            new_value=new,
            reason=None,
            cause_kind="command",
            cause_ref=None,
            reconstructed=False,
        )
    )


# ==================================================================================================
# The decision


def _stamp(view: Any, created: datetime, origin: datetime | None) -> Any:
    """Children without their own time take the decision's: recorded with it and, for an imported
    decision, known since its origin time."""
    if view.recorded_at == _UNSET:
        return dataclasses.replace(view, recorded_at=created, origin_recorded_at=origin)
    return view


def D(
    number: int = 1001,
    *,
    title: str = "Move the workshop to a smaller room",
    statement: str | None = "Rent the small room for one quarter",
    question: str | None = "Which room for the workshop?",
    status: str = "active",
    depth: str = "full",
    kind: str = "choice",
    review_due: date | None = None,
    decided: date | datetime | None = None,
    decided_basis: str | None = None,
    created: datetime | None = None,
    origin_recorded: datetime | None = None,
    activated: datetime | None = None,
    manual_flag: str | None = None,
    mirror_of: str | None = None,
    reconstructed: bool | None = None,
    absent_since_run_id: int | None = None,
    expected_by: date | None = None,
    unknowns: Iterable[str] = ("whether the room has enough power",),
    success_criterion: str | None = "rent down by a third",
    origin_kind: str = "cli",
    assumptions: Sequence[AssumptionView] = (),
    facts: Sequence[FactView] = (),
    reviews: Sequence[ReviewView] = (),
    links: Sequence[LinkView] = (),
    options: Sequence[OptionView] = (),
    outcomes: Sequence[OutcomeView] = (),
    stakes: Sequence[StakeView] = (),
    versions: Sequence[VersionView] = (),
) -> DecisionView:
    """A decision with its children attached (ids, codes, refs and stored rows filled in)."""
    created = created or noon(days(-20))
    pid = f"D-{number:04d}"
    did = number
    if decided is None and decided_basis != "unknown":
        decided = created.astimezone(zone(TZ)).date()
    is_mirror = mirror_of is not None
    if activated is None and status != "draft":
        activated = created

    def own(view: Any, **kw: Any) -> Any:
        stamped = _stamp(view, created, origin_recorded)
        return finish(dataclasses.replace(stamped, decision_id=did, **kw))

    asms = []
    for a in assumptions:
        a_ref = f"{pid}_{a.code}"
        checks = tuple(
            own(c, assumption_id=a.id, code_n=i, code=f"CK-{i:03d}", ref=f"{a_ref}_CK-{i:03d}")
            for i, c in enumerate(a.checks, start=1)
        )
        readings = tuple(
            own(r, assumption_id=a.id, code_n=i, code=f"RD-{i:03d}", ref=f"{a_ref}_RD-{i:03d}")
            for i, r in enumerate(a.readings, start=1)
        )
        asms.append(own(a, ref=a_ref, checks=checks, readings=readings))
    view = DecisionView(
        tx=1,
        recorded_at=created,
        origin_recorded_at=origin_recorded,
        id=did,
        public_id=pid,
        number=number,
        title=title,
        question=question,
        statement=statement,
        kind=kind,  # type: ignore[arg-type]
        decider="self",
        decider_basis="stated",
        decider_ref=None,
        depth=depth,  # type: ignore[arg-type]
        depth_basis="import" if is_mirror else "computed",
        reversibility="unknown",
        status=status,  # type: ignore[arg-type]
        manual_flag=manual_flag,  # type: ignore[arg-type]
        manual_flag_reason="the owner says so" if manual_flag else None,
        context=None,
        known=None,
        would_help=None,
        unknowns=tuple(unknowns),
        success_criterion=success_criterion,
        expected_metric=None,
        expected_target=None,
        expected_unit=None,
        expected_by=expected_by,
        expected_text=None,
        confidence=70,
        not_doing=None,
        review_due=review_due,
        review_due_initial=review_due,
        decided_at=decided,
        decided_precision=_precision(decided),  # type: ignore[arg-type]
        decided_basis=(decided_basis or ("import" if is_mirror else "stated")),  # type: ignore[arg-type]
        activated_at=activated,
        closed_at=noon(days(-1)) if status in ("closed", "cancelled", "superseded") else None,
        current_edition=0,
        completion_pending=False,
        origin_kind="import" if is_mirror else origin_kind,  # type: ignore[arg-type]
        origin_quote=None,
        publishability="private",
        third_party_sensitive=False,
        reconstructed=is_mirror if reconstructed is None else reconstructed,
        mirror_of=mirror_of,
        mirror_scope="full" if is_mirror else None,
        notes=None,
        legacy_json=None,
        version=1,
        absent_since_run_id=absent_since_run_id,
        options=tuple(
            own(o, code_n=i, code=f"O-{i:02d}", ref=f"{pid}_O-{i:02d}")
            for i, o in enumerate(options, start=1)
        ),
        assumptions=tuple(asms),
        facts=tuple(
            own(f, code_n=i, code=f"FT-{i:03d}", ref=f"{pid}_FT-{i:03d}")
            for i, f in enumerate(facts, start=1)
        ),
        reviews=tuple(
            own(r, code_n=i, code=f"R-{i:02d}", ref=f"{pid}_R-{i:02d}")
            for i, r in enumerate(reviews, start=1)
        ),
        outcomes=tuple(own(o) for o in outcomes),
        stakes=tuple(own(s) for s in stakes),
        links=tuple(own(link) for link in links),
        versions=tuple(versions),
    )
    return finish(view)


def sealed(
    d: DecisionView,
    *,
    reason: str = "activation",
    sealed_at: datetime | None = None,
    by: str = "owner",
) -> DecisionView:
    """``d`` with its next edition sealed by ``cfj.build_edition`` (deterministic salts)."""
    n = max((e.n for e in d.editions), default=0) + 1
    at = sealed_at or (d.activated_at or d.recorded_at)
    with seeded_salts(f"{d.public_id}-E{n}"):
        draft = cfj.build_edition(
            public_id=d.public_id,
            n=n,
            decision=d.stored,
            items=cfj.seal_items(d),
            sealed_at=format_instant(at),
            sealed_by=by,
        )
    edition = finish(
        EditionView(
            tx=1,
            recorded_at=at,
            decision_id=d.id,
            n=n,
            code=f"E-{n:02d}",
            ref=f"{d.public_id}_E-{n:02d}",
            reason=reason,  # type: ignore[arg-type]
            fields_json=draft.fields_json,
            field_salts_json=draft.field_salts_json,
            field_hashes_json=draft.field_hashes_json,
            items_json=draft.items_json,
            seal_hash=draft.seal_hash,
            canon_version=cfj.CANON_VERSION,
            sealed_at=at,
            sealed_by=by,
            review_id=None,
            reason_text=None,
            unverifiable_at_seal=None,
            reconstructed=d.reconstructed,
        )
    )
    return finish(dataclasses.replace(d, editions=(*d.editions, edition), current_edition=n))


def with_head(d: DecisionView, **changes: Any) -> DecisionView:
    """``d`` with head fields changed (and its stored row following them), as a write would."""
    return finish(dataclasses.replace(d, **changes))


def FK(number: int, *, deadline: date | None, status: str = "open") -> ForkView:
    return finish(
        ForkView(
            tx=1,
            recorded_at=noon(days(-5)),
            id=_next_id(),
            public_id=f"Q-{number:04d}",
            number=number,
            question="Which venue for the workshop?",
            trigger_text=None,
            trigger_ref=None,
            opened_at=days(-5),
            opened_precision="day",
            opened_basis="stated",
            decider="self",
            decider_ref=None,
            deadline=deadline,
            status=status,  # type: ignore[arg-type]
            outcome_not_heard=False,
            decision_id=None,
            closed_at=None,
            close_reason=None,
            delegated_to_ref=None,
            version=1,
        )
    )


def PR(pid: int, *, recorded: datetime, status: str = "proposed") -> ProposalView:
    return finish(
        ProposalView(
            tx=1,
            recorded_at=recorded,
            id=pid,
            ref=f"proposal {pid}",
            title="Adopt a weekly release train",
            type="decision_new",
            decision_id=None,
            payload_json="{}",
            payload_hash="0" * 64,
            origin_kind="agent_session",
            origin_quote=None,
            proposed_by="mcp_test-client",
            match_candidates_json="[]",
            status=status,  # type: ignore[arg-type]
            decided_tx=None,
            reject_class=None,
            reject_reason=None,
            result_ref=None,
        )
    )
