"""The read views the CLI and MCP share: the decision card and the other I1 answers as wire dicts.

Owned by track X (interfaces); increment I1, spec §12.2.

Both interfaces serve **the same view functions** over one service seam (``DecService``), so the
waiting list, the card and every other answer are identical item for item and in the same order
whether the owner asks over MCP, over the CLI or through the ``waiting`` query itself (AT-M1). A
view is plain JSON data (``str``, ``int``, ``bool``, ``None``, lists and dicts): MCP returns it as
structured content, the admin API returns it as the response body, and the CLI renders it as text
(``interfaces/admin/render.py``).

Every view is an envelope that states the server, the instance role, the as-of instant and axis,
the coverage notes, staleness and **the authority**: who is the system of record for each decision
in the answer ("mirrored from V1; read-only here") (spec §5.1, §5.5, AT-M1).

The card (``context_view``) follows the order of spec §5.3: the integrity line when not ``ok``, the
share line, health with both axes and every reason, the statement, why it waits, the question
context, assumptions, facts (ground, then monitoring), reviews, outcome, learnings, editions, links,
execution, the mirror status and the instance role. Projections (§4.4): ``owner`` (the CLI) and
``agent`` (MCP), which withholds money amounts unless the client token has ``financial = 1``. Salts
and raw stored rows never leave the instance.

Spec notes:

- ``WaitingItem`` and ``DecisionLine`` do not carry a mirror scope, and ``WaitingItem`` carries no
  mirror reference at all, while AT-M1 asks every answer to state the mirror authority. The views
  derive each decision's authority from ``list_decisions`` (``DecisionLine.mirror_of``): a decision
  with ``mirror_of = 'V1_D907'`` names ``V1`` as its system of record. ``list_decisions`` answers as
  of now, so a decision the answer shows and the list lacks is looked up with
  ``DecService.decision_info`` (DEC's ``DecisionDirectory`` port), which describes the stored
  record regardless of time (integration). A skeleton change that puts ``mirror_of`` and
  ``mirror_scope`` on ``WaitingItem`` (and ``mirror_scope`` on ``DecisionLine``) would remove both
  extra queries.
  ``list_decisions(limit=1_000_000)`` is expected to return every decision.
- Shadow items with ``decision_ref = '*'`` are run-level counts, not decisions.
- ``dec_waiting`` maps to ``waiting`` "(+ ``drafts_to_finish``)" (§5.5). Drafts exist only from I2
  (native writes); the I1 view serves the waiting list alone and I2 adds the drafts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, runtime_checkable

from coflow.kernel.config.profile import load_profile
from coflow.kernel.context import Answer, Axis, CommandContext, CommandResult, format_instant
from coflow.kernel.errors import CoflowError, error_payload
from coflow.kernel.obs.usage import record_usage
from coflow.kernel.ops.instance import load_instance
from coflow.kernel.ports.decision_directory import DecisionInfo
from coflow.kernel.store.api import read_connection
from coflow.modules.dec import api as dec_api
from coflow.modules.dec.api import model

__all__ = [
    "SERVER_NAME",
    "AuthorityMap",
    "DecApiService",
    "DecService",
    "InstanceFacts",
    "KernelUsageSink",
    "StoreInstanceFacts",
    "UsageSink",
    "Wire",
    "authority_of",
    "context_view",
    "envelope",
    "error_view",
    "import_view",
    "integrity_view",
    "list_view",
    "shadow_view",
    "waiting_view",
    "wire_value",
]

SERVER_NAME = "coflow-v2"
"""The name the v2 server advertises, distinct from v1's, so agents never confuse the two (§5.5)."""

Wire = dict[str, object]
"""A JSON object as the interfaces send it."""

WAITING_PULL = "dec.waiting.pull"
SHADOW_OPENED = "dec.shadow.opened"

# ==================================================================================================
# The seams the views read through


@runtime_checkable
class DecService(Protocol):
    """DEC's I1 read side and its import command, as the interfaces use them.

    ``DecApiService`` delegates to ``coflow.modules.dec.api``; tests substitute a fake, so the
    interface layer is tested before the domain tracks land.
    """

    def waiting(self, *, today: date | None = None) -> Answer[list[model.WaitingItem]]: ...

    def decision_context(
        self,
        ref: str,
        *,
        detail: model.Detail = "brief",
        as_of: datetime | None = None,
        axis: Axis = "knowledge",
        audience: model.Audience = "owner",
    ) -> Answer[model.DecisionContext]: ...

    def list_decisions(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        health: str | None = None,
        linked_to: str | None = None,
        mirror: str | None = None,
        limit: int = 50,
    ) -> Answer[list[model.DecisionLine]]: ...

    def integrity(self, ref: str) -> Answer[list[model.IntegrityReport]]: ...

    def shadow_report(self, *, run_id: int | None = None) -> Answer[model.ShadowReport]: ...

    def decision_info(self, ref: str) -> DecisionInfo | None:
        """The stored record's identity and authority now (the ``DecisionDirectory`` port's
        ``info``)."""
        ...

    def import_snapshot(
        self, file: Path, *, mode: model.ImportMode, ctx: CommandContext
    ) -> CommandResult[model.ImportReport]: ...


class DecApiService:
    """``DecService`` over ``coflow.modules.dec.api`` with one environment."""

    def __init__(self, env: model.DecEnv) -> None:
        self.env = env

    def waiting(self, *, today: date | None = None) -> Answer[list[model.WaitingItem]]:
        return dec_api.waiting(self.env, today=today)

    def decision_context(
        self,
        ref: str,
        *,
        detail: model.Detail = "brief",
        as_of: datetime | None = None,
        axis: Axis = "knowledge",
        audience: model.Audience = "owner",
    ) -> Answer[model.DecisionContext]:
        return dec_api.decision_context(
            self.env, ref, detail=detail, as_of=as_of, axis=axis, audience=audience
        )

    def list_decisions(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        health: str | None = None,
        linked_to: str | None = None,
        mirror: str | None = None,
        limit: int = 50,
    ) -> Answer[list[model.DecisionLine]]:
        return dec_api.list_decisions(
            self.env,
            status=status,
            kind=kind,
            health=health,
            linked_to=linked_to,
            mirror=mirror,
            limit=limit,
        )

    def integrity(self, ref: str) -> Answer[list[model.IntegrityReport]]:
        return dec_api.integrity(self.env, ref)

    def shadow_report(self, *, run_id: int | None = None) -> Answer[model.ShadowReport]:
        return dec_api.shadow_report(self.env, run_id=run_id)

    def decision_info(self, ref: str) -> DecisionInfo | None:
        return dec_api.directory(self.env).info(ref)

    def import_snapshot(
        self, file: Path, *, mode: model.ImportMode, ctx: CommandContext
    ) -> CommandResult[model.ImportReport]:
        return dec_api.import_snapshot(self.env, file, mode=mode, ctx=ctx)


@runtime_checkable
class InstanceFacts(Protocol):
    """The instance role (stated in every answer) and the owner's zone (for local times)."""

    def role(self) -> str: ...

    def timezone(self) -> str: ...


class StoreInstanceFacts:
    """``InstanceFacts`` from ``sys_instance`` and ``cfg_profile`` of the bound store, read once."""

    def __init__(self) -> None:
        self._role: str | None = None
        self._tz: str | None = None

    def _load(self) -> None:
        with read_connection() as conn:
            self._role = load_instance(conn).role
            self._tz = load_profile(conn).timezone

    def role(self) -> str:
        if self._role is None:
            self._load()
        assert self._role is not None
        return self._role

    def timezone(self) -> str:
        if self._tz is None:
            self._load()
        assert self._tz is not None
        return self._tz


@runtime_checkable
class UsageSink(Protocol):
    """Where the interfaces record usage signals (P-13, spec §9.3): one row per signal, day and
    channel, written in its own unit of work."""

    def record(self, signal: str, *, ctx: CommandContext, detail: Mapping[str, str]) -> None: ...


class KernelUsageSink:
    """``UsageSink`` over ``kernel.obs.usage.record_usage`` (track K)."""

    def record(self, signal: str, *, ctx: CommandContext, detail: Mapping[str, str]) -> None:
        record_usage(signal, ctx=ctx, detail=dict(detail))


# ==================================================================================================
# Wire helpers


def wire_value(value: object) -> object:
    """A scalar as it travels: instants as stored text, dates as ``YYYY-MM-DD``, decimals as
    strings, sets sorted. Containers are converted element by element."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, datetime):
        return format_instant(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, frozenset | set):
        return sorted(str(v) for v in value)
    if isinstance(value, Mapping):
        return {str(k): wire_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [wire_value(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"no wire form for {type(value).__name__}")


def _when(at: object, precision: str, basis: str) -> Wire:
    return {"at": wire_value(at), "precision": precision, "basis": basis}


# ==================================================================================================
# Authority: who is the system of record for each decision (AT-M1)


@dataclass(frozen=True, slots=True)
class AuthorityMap:
    """Decision ref -> ``mirror_of`` (``None`` for natives) and ``mirror_scope``.

    ``list_decisions`` answers as of now on the knowledge axis; a decision an answer shows that the
    list does not hold (``waiting --date``, a shadow run's snapshot time, ``integrity`` over every
    stored edition, a mirror whose source recorded it after the instance's now) is looked up once
    with ``DecService.decision_info``, which describes the stored record regardless of time: who
    owns a record is a fact about the record. A decision found by neither stays unknown.
    """

    mirrors: Mapping[str, str | None]
    scopes: Mapping[str, str | None] = field(default_factory=dict)

    @classmethod
    def load(
        cls, dec: DecService, refs: Iterable[str] = (), *, as_of: datetime | None = None
    ) -> AuthorityMap:
        lines = dec.list_decisions(limit=1_000_000).value
        mirrors: dict[str, str | None] = {line.public_id: line.mirror_of for line in lines}
        scopes: dict[str, str | None] = {}
        for ref in dict.fromkeys(refs):
            if ref in mirrors:
                continue
            found = dec.decision_info(ref)
            if found is None:
                continue
            mirrors[ref] = found.mirror_of
            scopes[ref] = found.mirror_scope
        return cls(mirrors, scopes)

    def of(self, ref: str, *, mirror_scope: str | None = None) -> Wire:
        if ref not in self.mirrors:
            return authority_of(None, known=False)
        return authority_of(self.mirrors[ref], mirror_scope=mirror_scope or self.scopes.get(ref))

    def issuers(self, refs: Iterable[str]) -> list[str]:
        found = {_issuer(self.mirrors.get(r)) for r in refs if self.mirrors.get(r)}
        return sorted(i for i in found if i)

    def unknown(self, refs: Iterable[str]) -> int:
        """How many of ``refs`` this instance does not list (their authority is unknown)."""
        return len({r for r in refs if r not in self.mirrors})


def _issuer(mirror_of: str | None) -> str | None:
    if not mirror_of:
        return None
    head, sep, _ = mirror_of.partition("_")
    return head if sep else None


def authority_of(
    mirror_of: str | None, *, mirror_scope: str | None = None, known: bool = True
) -> Wire:
    """The authority of one decision in words and structure."""
    if not known:
        return {
            "system_of_record": None,
            "mirror_of": None,
            "writable_here": None,
            "text": "authority unknown: the decision is not listed in this instance",
        }
    issuer = _issuer(mirror_of)
    if issuer is None:
        return {
            "system_of_record": "this instance",
            "mirror_of": None,
            "writable_here": True,
            "text": "native to this instance",
        }
    if mirror_scope == "basis_only":
        return {
            "system_of_record": issuer,
            "mirror_of": mirror_of,
            "writable_here": True,
            "text": f"text owned by {issuer}; monitoring is native here",
        }
    return {
        "system_of_record": issuer,
        "mirror_of": mirror_of,
        "writable_here": False,
        "text": f"mirrored from {issuer}; read-only here ({issuer} is the system of record)",
    }


def _authority_summary(issuers: Sequence[str], unknown: int = 0) -> str:
    gap = (
        f" The authority of {unknown} decision{'s' if unknown != 1 else ''} in this answer is "
        "unknown: not listed in this instance."
        if unknown
        else ""
    )
    if not issuers:
        if unknown:
            return "no decision in this answer is listed as a mirror." + gap
        return "every decision in this answer is native to this instance"
    names = ", ".join(issuers)
    return (
        f"decisions mirrored from {names} are read-only here; {names} stays their system of "
        "record. Native decisions are owned by this instance." + gap
    )


# ==================================================================================================
# The envelope


def envelope(
    view: str,
    answer: Answer[object],
    value: object,
    *,
    timezone: str,
    issuers: Sequence[str] = (),
    unknown: int = 0,
    coverage: Sequence[str] = (),
) -> Wire:
    """Every answer: the server, the instance role, as-of, coverage, staleness and authority."""
    return {
        "server": SERVER_NAME,
        "view": view,
        "instance_role": answer.instance_role,
        "as_of": format_instant(answer.as_of),
        "axis": answer.axis,
        "timezone": timezone,
        "coverage": [*answer.coverage, *coverage],
        "stale": answer.stale,
        "authority": _authority_summary(issuers, unknown),
        "value": value,
    }


def error_view(err: CoflowError, *, instance_role: str | None) -> Wire:
    """A typed error (spec §5.1) inside the same envelope keys: errors state the role too."""
    return {"server": SERVER_NAME, "view": "error", "instance_role": instance_role} | (
        error_payload(err)
    )


# ==================================================================================================
# Waiting list (§3.8, §3.9)


def _state_view(state: model.DecisionState | None) -> Wire | None:
    if state is None:
        return None
    return {
        "ref": state.ref,
        "label": state.label,
        "ground": state.ground,
        "timeliness": wire_value(state.timeliness),
        "reasons": list(state.reasons),
        "share": wire_value(state.share),
        "review_due": wire_value(state.review_due),
        "bet": state.bet,
        "badge": state.badge,
    }


def _reason_view(reason: model.Reason) -> Wire:
    return {
        "kind": reason.kind,
        "due": wire_value(reason.due),
        "code": reason.code,
        "critical": reason.critical,
        "due_source": reason.due_source,
        "status": reason.status,
        "text": reason.text,
    }


def _question_context_view(qc: model.QuestionContext | None) -> Wire | None:
    if qc is None:
        return None
    last = qc.last_fact
    asked = qc.asked
    return {
        "one_line": qc.one_line,
        "share_line": qc.share_line,
        "health": _state_view(qc.health),
        "reasons": [_reason_view(r) for r in qc.reasons],
        "last_fact": None
        if last is None
        else {
            "ref": last.ref,
            "text": last.text,
            "occurred_at": wire_value(last.occurred_at),
            "age_days": last.age_days,
            "evidence": last.evidence,
        },
        "passed": [{"what": what, "date": wire_value(day)} for what, day in qc.passed],
        "goals": [
            {
                "ref": g.ref,
                "title": g.title,
                "status": g.status,
                "since": wire_value(g.since),
            }
            for g in qc.goals
        ],
        "asked": None
        if asked is None
        else {
            "kind": asked.kind,
            "ref": asked.ref,
            "statement": asked.statement,
            "threshold_text": asked.threshold_text,
            "due": wire_value(asked.due),
            "due_source": asked.due_source,
        },
        "execution": wire_value(qc.execution),
        "postponements_since_review": qc.postponements_since_review,
        "likely_actions": list(qc.likely_actions),
    }


def waiting_view(
    dec: DecService,
    facts: InstanceFacts,
    *,
    today: date | None = None,
    usage: tuple[UsageSink, CommandContext, str] | None = None,
) -> Wire:
    """``waiting`` with every item's question context and authority, in the query's order.

    ``usage`` = (sink, ctx, view name) records the pull by ``ctx.channel`` (spec §5.6, §9.3).
    """
    answer = dec.waiting(today=today)
    decision_refs = [i.ref for i in answer.value if i.subject_kind == "decision"]
    authority = AuthorityMap.load(dec, decision_refs, as_of=answer.as_of)
    items = []
    for position, item in enumerate(answer.value, start=1):
        is_decision = item.subject_kind == "decision"
        items.append(
            {
                "position": position,
                "subject_kind": item.subject_kind,
                "ref": item.ref,
                "number": item.number,
                "title": item.title,
                "health": _state_view(item.health),
                "reasons": [_reason_view(r) for r in item.reasons],
                "question_context": _question_context_view(item.question_context),
                "authority": authority.of(item.ref) if is_decision else authority_of(None),
            }
        )
    refs = decision_refs
    # An empty list still states the instance's authority (the issuers of every decision it
    # holds), never a vacuous "every decision in this answer is native" (integration).
    view = envelope(
        "waiting",
        answer,
        {"today": wire_value(today), "count": len(items), "items": items},
        timezone=facts.timezone(),
        issuers=authority.issuers(refs or list(authority.mirrors)),
        unknown=authority.unknown(refs),
    )
    if usage is not None:
        sink, ctx, name = usage
        sink.record(WAITING_PULL, ctx=ctx, detail={"view": name})
    return view


# ==================================================================================================
# The card (§5.3)


def _health_view(health: model.HealthResult) -> Wire:
    return {
        "label": health.label,
        "ground": health.ground,
        "timeliness": wire_value(health.timeliness),
        "reasons": [
            {
                "axis": r.axis,
                "kind": r.kind,
                "text": r.text,
                "code": r.code,
                "day": wire_value(r.day),
                "source": r.source,
            }
            for r in health.reasons
        ],
        "share": wire_value(health.share),
        "bet": health.bet,
        "states": {code: health.states[code] for code in sorted(health.states)},
        "pool": list(health.pool),
        "badge": health.badge,
        "badge_green": health.badge_green,
    }


def _check_view(check: model.CheckView | None) -> Wire | None:
    if check is None:
        return None
    return {
        "code": check.code,
        "ref": check.ref,
        "kind": check.kind,
        "state": check.state,
        "observed_value": check.observed_value,
        "observed_text": check.observed_text,
        "observed": _when(check.observed_at, check.observed_precision, check.observed_basis),
        "next_check_set": wire_value(check.next_check_set),
        "note": check.note,
        "evidence": {
            "kind": check.evidence_kind,
            "ref": check.evidence_ref,
            "quote": check.evidence_quote,
        },
        "proposed_by": check.proposed_by,
        "reconstructed": check.reconstructed,
        "voided_at": wire_value(check.voided_at),
    }


def _reading_view(reading: model.ReadingView) -> Wire:
    return {
        "code": reading.code,
        "ref": reading.ref,
        "value": reading.value,
        "unit": reading.unit,
        "value_text": reading.value_text,
        "observed": _when(reading.observed_at, reading.observed_precision, reading.observed_basis),
        "source": {"kind": reading.source_kind, "ref": reading.source_ref, "quote": reading.quote},
        "proposed_state": reading.proposed_state,
        "no_proposal_reason": reading.no_proposal_reason,
        "accepted": reading.accepted_by_check_id is not None,
        "voided_at": wire_value(reading.voided_at),
    }


def _assumption_view(card: model.AssumptionCard) -> Wire:
    a = card.assumption
    return {
        "code": a.code,
        "ref": a.ref,
        "position": a.position,
        "statement": a.statement,
        "metric": a.metric,
        "threshold": {
            "comparator": a.comparator,
            "value": a.threshold_value,
            "value2": a.threshold_value2,
            "unit": a.unit,
            "text": a.threshold_text,
            "by_date": wire_value(a.by_date),
        },
        "judge_from": wire_value(a.judge_from),
        "data_source": {
            "kind": a.data_source_kind,
            "text": a.data_source_text,
            "ref": a.data_source_ref,
        },
        "frequency": a.check_frequency,
        "critical": a.is_critical,
        "class_tag": a.class_tag,
        "probability": a.probability,
        "status": a.status,
        "added_in_edition": a.added_in_edition,
        "state": card.state,
        "due": {"date": wire_value(card.due.due), "source": card.due.source},
        "last_check": _check_view(card.last_check),
        "readings": [_reading_view(r) for r in card.readings],
    }


def _fact_view(fact: model.FactView, codes: Mapping[int, str]) -> Wire:
    return {
        "code": fact.code,
        "ref": fact.ref,
        "phase": fact.phase,
        "kind": fact.kind,
        "claimed_outcome": fact.claimed_outcome,
        "text": fact.text,
        "occurred": _when(fact.occurred_at, fact.occurred_precision, fact.occurred_basis),
        "evidence": {
            "kind": fact.evidence_kind,
            "ref": fact.evidence_ref,
            "quote": fact.evidence_quote,
            "quote_verified": fact.quote_verified,
        },
        "reported_by": fact.reported_by,
        "bears_on": [
            {"assumption": codes.get(b.assumption_id), "bearing": b.bearing} for b in fact.bearings
        ],
        "reconstructed": fact.reconstructed,
        "voided_at": wire_value(fact.voided_at),
    }


def _review_view(review: model.ReviewView) -> Wire:
    return {
        "code": review.code,
        "ref": review.ref,
        "action": review.action,
        "verdict": review.verdict,
        "notes": review.notes,
        "revise_basis": review.revise_basis,
        "trigger": review.trigger,
        "trigger_ref": review.trigger_ref,
        "occurred": _when(review.occurred_at, review.occurred_precision, review.occurred_basis),
        "next_review_due": wire_value(review.next_review_due),
        "successor_ref": review.successor_ref,
        "is_correction": review.is_correction,
        "reconstructed": review.reconstructed,
        "voided_at": wire_value(review.voided_at),
    }


def _outcome_view(outcome: model.OutcomeView | None) -> Wire | None:
    if outcome is None:
        return None
    return {
        "kind": outcome.kind,
        "basis": outcome.basis,
        "evidence_refs": list(outcome.evidence_refs),
        "measured_value": outcome.measured_value,
        "expected_vs_actual": outcome.expected_vs_actual,
        "occurred": _when(outcome.occurred_at, outcome.occurred_precision, outcome.occurred_basis),
        "resolved_by": outcome.resolved_by,
        "reconstructed": outcome.reconstructed,
    }


def _learning_view(learning: model.LearningView) -> Wire:
    return {
        "code": learning.code,
        "ref": learning.ref,
        "edition": learning.edition,
        "confirmed": learning.confirmed,
        "refuted": learning.refuted,
        "limits": learning.limits,
        "next_step": learning.next_step,
        "same_again": learning.same_again,
        "legacy_text": learning.legacy_text,
        "reconstructed": learning.reconstructed,
    }


def _stake_view(stake: model.StakeView, *, show_amounts: bool) -> Wire:
    withheld = stake.type == "money" and not show_amounts
    return {
        "type": stake.type,
        "amount": None if withheld else stake.amount,
        "amount_withheld": withheld,
        "currency": stake.currency,
        "period": stake.period,
        "count_periods": stake.count_periods,
        "direction": stake.direction,
        "note": stake.note,
        "planned": stake.planned,
    }


def _link_view(link: model.LinkView) -> Wire:
    return {
        "id": link.id,
        "role": link.role,
        "target_ref": link.target_ref,
        "target_kind": link.target_kind,
        "resolution": link.resolution,
        "note": link.note,
        "removed": link.removed_tx is not None,
    }


def _edition_view(line: model.IntegrityLine) -> Wire:
    return {
        "edition": line.edition,
        "status": line.status,
        "items": list(line.items),
        "seal12": line.seal12,
    }


def _decision_header(d: model.DecisionView) -> Wire:
    return {
        "public_id": d.public_id,
        "number": d.number,
        "title": d.title,
        "question": d.question,
        "statement": d.statement,
        "kind": d.kind,
        "status": d.status,
        "decider": d.decider,
        "decider_ref": d.decider_ref,
        "depth": d.depth,
        "reversibility": d.reversibility,
        "manual_flag": d.manual_flag,
        "manual_flag_reason": d.manual_flag_reason,
        "context": d.context,
        "known": d.known,
        "would_help": d.would_help,
        "unknowns": list(d.unknowns),
        "success_criterion": d.success_criterion,
        "expected": {
            "metric": d.expected_metric,
            "target": d.expected_target,
            "unit": d.expected_unit,
            "by": wire_value(d.expected_by),
            "text": d.expected_text,
        },
        "confidence": d.confidence,
        "not_doing": d.not_doing,
        "review_due": wire_value(d.review_due),
        "decided": _when(d.decided_at, d.decided_precision, d.decided_basis),
        "activated_at": wire_value(d.activated_at),
        "closed_at": wire_value(d.closed_at),
        "current_edition": d.current_edition,
        "completion_pending": d.completion_pending,
        "origin_kind": d.origin_kind,
        "origin_quote": d.origin_quote,
        "publishability": d.publishability,
        "third_party_sensitive": d.third_party_sensitive,
        "reconstructed": d.reconstructed,
        "mirror_of": d.mirror_of,
        "mirror_scope": d.mirror_scope,
        "absent_since_run_id": d.absent_since_run_id,
        "adopted_at": wire_value(d.adopted_at),
        "version": d.version,
    }


AMOUNTS_WITHHELD = "amounts withheld (financial flag off)"


def context_view(
    dec: DecService,
    facts: InstanceFacts,
    ref: str,
    *,
    detail: model.Detail = "brief",
    as_of: datetime | None = None,
    axis: Axis = "knowledge",
    audience: model.Audience = "owner",
    financial: bool = False,
) -> Wire:
    """The card of one decision in the order of spec §5.3, for the ``owner`` or ``agent``
    projection. The agent projection withholds money amounts unless ``financial``.

    DEC's ``agent`` audience always withholds amounts (a query cannot see the token), so a
    ``financial`` agent's card is assembled from DEC's ``owner`` audience, whose only difference is
    the amounts (integration; ``dec/queries.py`` spec note), and is still labelled ``agent``.
    """
    query_audience: model.Audience = "owner" if audience == "agent" and financial else audience
    answer = dec.decision_context(
        ref, detail=detail, as_of=as_of, axis=axis, audience=query_audience
    )
    card = answer.value
    d = card.decision
    show_amounts = audience == "owner" or financial
    codes = {a.id: a.code for a in d.assumptions}
    stakes = [_stake_view(s, show_amounts=show_amounts) for s in d.stakes]
    withheld = any(s["amount_withheld"] for s in stakes)
    authority = authority_of(d.mirror_of, mirror_scope=d.mirror_scope)
    issuer = authority["system_of_record"]
    value = {
        "integrity_line": card.integrity_line,
        "share_line": card.share_line,
        "health": _health_view(card.health),
        "decision": _decision_header(d),
        "waiting_reasons": [_reason_view(r) for r in card.waiting_reasons],
        "question_context": _question_context_view(card.question_context),
        "assumptions": [_assumption_view(a) for a in card.assumptions],
        "ground_facts": [_fact_view(f, codes) for f in card.ground_facts],
        "monitoring_facts": [_fact_view(f, codes) for f in card.monitoring_facts],
        "reviews": [_review_view(r) for r in card.reviews],
        "outcome": _outcome_view(card.outcome),
        "learnings": [_learning_view(lr) for lr in card.learnings],
        "stakes": stakes,
        "editions": [_edition_view(e) for e in card.editions],
        "links": [_link_view(lk) for lk in card.links],
        "execution": {kind: _execution(s) for kind, s in sorted(card.execution.items())},
        "mirror_line": card.mirror_line,
        "authority": authority,
        "detail": card.detail,
        "audience": audience,
    }
    return envelope(
        "decision_context",
        answer,
        value,
        timezone=facts.timezone(),
        issuers=[issuer] if d.mirror_of and isinstance(issuer, str) else [],
        coverage=[AMOUNTS_WITHHELD] if withheld else [],
    )


def _execution(summary: model.AttachmentSummary) -> Wire:
    return {
        **summary.counts(),
        "last_activity_at": wire_value(summary.last_activity_at),
        "refs": list(summary.refs),
    }


# ==================================================================================================
# List, integrity, shadow, import


def list_view(
    dec: DecService,
    facts: InstanceFacts,
    *,
    status: str | None = None,
    kind: str | None = None,
    health: str | None = None,
    linked_to: str | None = None,
    mirror: str | None = None,
    limit: int = 50,
) -> Wire:
    """``list_decisions``: one line each, with its authority."""
    answer = dec.list_decisions(
        status=status, kind=kind, health=health, linked_to=linked_to, mirror=mirror, limit=limit
    )
    lines = [
        {
            "public_id": line.public_id,
            "title": line.title,
            "status": line.status,
            "kind": line.kind,
            "label": line.label,
            "share": wire_value(line.share),
            "review_due": wire_value(line.review_due),
            "first_reason": line.first_reason,
            "mirror_of": line.mirror_of,
            "authority": authority_of(line.mirror_of),
        }
        for line in answer.value
    ]
    issuers = sorted({i for line in answer.value if (i := _issuer(line.mirror_of))})
    return envelope(
        "decision_list",
        answer,
        {"count": len(lines), "lines": lines},
        timezone=facts.timezone(),
        issuers=issuers,
    )


def integrity_view(dec: DecService, facts: InstanceFacts, ref: str) -> Wire:
    """``integrity`` for a ref or ``'all'``: per edition status, live drift, completion pending."""
    answer = dec.integrity(ref)
    authority = AuthorityMap.load(dec, [r.decision_ref for r in answer.value], as_of=answer.as_of)
    reports = [
        {
            "decision_ref": report.decision_ref,
            "ok": report.ok,
            "lines": [_edition_view(line) for line in report.lines],
            "authority": authority.of(report.decision_ref),
        }
        for report in answer.value
    ]
    return envelope(
        "integrity",
        answer,
        {"ref": ref, "count": len(reports), "reports": reports},
        timezone=facts.timezone(),
        issuers=authority.issuers(r.decision_ref for r in answer.value),
        unknown=authority.unknown(r.decision_ref for r in answer.value),
    )


def _shadow_item(item: model.ShadowItem) -> Wire:
    return {
        "decision_ref": item.decision_ref,
        "aspect": item.aspect,
        "subject_ref": item.subject_ref,
        "v1_value": item.v1_value,
        "v2_value": item.v2_value,
        "classification": item.classification,
        "rule_id": item.rule_id,
    }


def shadow_view(
    dec: DecService,
    facts: InstanceFacts,
    *,
    run_id: int | None = None,
    usage: tuple[UsageSink, CommandContext, str] | None = None,
) -> Wire:
    """``shadow_report`` (§6.6): totals per class, counts per rule, every unexpected line with both
    values, the findings. ``usage`` records that the report was opened (§9.3)."""
    answer = dec.shadow_report(run_id=run_id)
    report = answer.value
    every = (*report.unexpected, *report.findings, *report.items)
    refs = [i.decision_ref for i in every if i.decision_ref != "*"]  # '*': run-level counts
    authority = AuthorityMap.load(dec, refs, as_of=answer.as_of)
    value = {
        "run_id": report.run_id,
        "as_of_date": wire_value(report.as_of_date),
        "report_status": report.report_status,
        "totals": {k: report.totals[k] for k in sorted(report.totals)},
        "by_rule": {k: report.by_rule[k] for k in sorted(report.by_rule)},
        "unexpected": [_shadow_item(i) for i in report.unexpected],
        "findings": [_shadow_item(i) for i in report.findings],
        "runs_since_last_unexpected": report.runs_since_last_unexpected,
    }
    view = envelope(
        "shadow_report",
        answer,
        value,
        timezone=facts.timezone(),
        issuers=authority.issuers(refs),
        unknown=authority.unknown(refs),
    )
    if usage is not None:
        sink, ctx, name = usage
        sink.record(SHADOW_OPENED, ctx=ctx, detail={"view": name})
    return view


def import_view(
    result: CommandResult[model.ImportReport], *, instance_role: str, timezone: str
) -> Wire:
    """The run report of ``import_snapshot`` (§6.5)."""
    report = result.value
    counts = {
        entity: {
            "seen": c.seen,
            "new": c.new,
            "changed": c.changed,
            "unchanged": c.unchanged,
            "absent": c.absent,
        }
        for entity, c in sorted(report.counts.items())
    }
    issuer = report.source_issuer
    return {
        "server": SERVER_NAME,
        "view": "import_report",
        "instance_role": instance_role,
        "timezone": timezone,
        "authority": _authority_summary([issuer] if issuer else []),
        "value": {
            "run_id": report.run_id,
            "status": report.status,
            "mode": report.mode,
            "noop": report.noop,
            "file_hash": report.file_hash,
            "source_issuer": issuer,
            "synthetic": report.synthetic,
            "exported_at": wire_value(report.exported_at),
            "as_of": wire_value(report.as_of),
            "as_of_date": wire_value(report.as_of_date),
            "counts": counts,
            "absent": list(report.absent),
            "findings": list(report.findings),
            "report_status": report.report_status,
            "tx": result.tx,
            "event_count": len(result.event_ids),
        },
    }
