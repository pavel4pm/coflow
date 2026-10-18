"""DEC queries: assembling views into computed results (spec §5.3).

Owned by track D (decision domain); increment I1, spec §12.2 (and the I2 queries later). The
functions below are the targets of ``dec.api``; their signatures are fixed by the facade.

How every query runs:

1. One read connection (``kernel.store.api.read_connection``): the owner profile, the settings and
   the instance are read (``DecConfig``, the instance role), user input is resolved to a canonical
   id (``kernel.ids.aliases.resolve``), and rows are loaded through track S's ``store/repo.py``.
   The connection is closed before anything else runs, so the goal directory and the attachment
   probes read with their own connections.
2. ``T`` comes from the arguments or the bound store's clock (never the host's clock); ``T.date`` is
   in the owner's zone.
3. Each decision is cut to what is visible at ``T`` on the axis (``states.view_at``, §3.15).
4. The pure functions of ``domain/`` compute the answer. Queries never write; the waiting-list pull
   signal is recorded by the interface.

Every answer states the instance role, ``as_of`` and the axis, and its coverage notes: for a mirror
"mirrored from V1, snapshot exported at ...; read-only here", and for the ``agent`` audience
"amounts withheld (financial flag off)" when money amounts were removed.

Spec notes:

- ``health`` and ``assumption_due`` take the same optional ``today`` as ``waiting``, so the shadow
  report evaluates all three at one ``T`` (the snapshot's ``as_of`` and ``as_of_date``, found in
  review: with the owner's zone unlike the source's, the dates differed near midnight).
- ``waiting``: ``T.date`` is ``today``, else the owner-zone date of ``as_of``, else of now;
  ``T.instant`` is ``as_of``, else the end of ``today`` when ``today`` is given, else now. In I1
  the list holds decisions only (§12.2); forks and proposals join it in I2 and I3 through the same
  domain function.
- ``stale`` is set when an answer shows a mirror and the issuer's latest applied snapshot is older
  than the day before ``T.date`` (a daily snapshot was missed, P-9).
- ``decision_context`` with ``detail='brief'`` keeps the share line, health, the waiting reasons,
  the question context, the active assumptions, the outcome and the integrity line; the facts,
  reviews, learnings, editions and links are filled for ``detail='full'``.
- The ``agent`` audience withholds every money amount: the client token's financial flag is not
  known to a query in the slice (the MCP layer may re-add amounts for a ``financial`` token).
- ``as_of`` refuses with ``NotFound`` when the decision itself was not visible at ``t`` on the axis
  (AT-S8: created in V1 on day 2, imported on day 30, asked at day 5 on the instance axis).
- ``list_decisions(mirror=...)`` takes an issuer (``V1``), or ``native`` / ``none`` for records
  that mirror nothing.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

from coflow.kernel.config import profile as _profile
from coflow.kernel.config import settings as _settings
from coflow.kernel.context import (
    Answer,
    Axis,
    EvalTime,
    end_of_local_day,
    format_instant,
    local_date,
)
from coflow.kernel.errors import NotFound
from coflow.kernel.ids import aliases as _aliases
from coflow.kernel.ops import instance as _instance
from coflow.kernel.ports.decision_directory import WaitingItem
from coflow.kernel.store import api as _store
from coflow.modules.dec.domain import cfj as _cfj
from coflow.modules.dec.domain import context_card as _card
from coflow.modules.dec.domain import due as _due
from coflow.modules.dec.domain import health as _health
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain import waiting as _waiting
from coflow.modules.dec.domain.inputs import DraftItem, ForkLine, RelatedLearning
from coflow.modules.dec.domain.model import (
    AsOfView,
    AssumptionCard,
    AssumptionDue,
    Audience,
    DecConfig,
    DecEnv,
    DecisionContext,
    DecisionLine,
    DecisionView,
    Detail,
    HealthResult,
    ImportRunView,
    IntegrityLine,
    IntegrityReport,
    LinkRole,
)
from coflow.modules.dec.store import repo as _repo

__all__ = [
    "as_of",
    "assumption_due",
    "decision_context",
    "drafts_to_finish",
    "forks",
    "health",
    "integrity",
    "list_decisions",
    "related_learnings",
    "waiting",
]

ALL_LINK_ROLES: tuple[LinkRole, ...] = (
    "follows",
    "supersedes",
    "depends_on",
    "part_of",
    "contradicts",
    "tests",
    "serves",
    "about",
    "informed_by",
    "foreign_attachment",
)
WITHHELD = "amounts withheld (financial flag off)"
NATIVE = frozenset({"native", "none"})


# ==================================================================================================
# What every query reads first


@dataclasses.dataclass(frozen=True, slots=True)
class _World:
    cfg: DecConfig
    role: str
    runs: dict[str, ImportRunView | None]


def _config(conn: sqlite3.Connection) -> tuple[DecConfig, str]:
    stored = _settings.load_settings(conn)
    owner = _profile.load_profile(conn)
    instance = _instance.load_instance(conn)
    cfg = DecConfig.from_settings(stored, timezone=owner.timezone)
    cfg = dataclasses.replace(
        cfg,
        currency=stored.get("owner.currency", owner.currency),
        locale=stored.get("owner.locale", owner.locale),
    )
    return cfg, instance.role


def _issuer(d: DecisionView) -> str | None:
    return d.mirror_of.split("_", 1)[0] if d.mirror_of else None


def _world(conn: sqlite3.Connection, decisions: Iterable[DecisionView]) -> _World:
    cfg, role = _config(conn)
    issuers = sorted({i for d in decisions if (i := _issuer(d))})
    runs = {i: _repo.load_import_run(conn, None, issuer=i) for i in issuers}
    return _World(cfg=cfg, role=role, runs=runs)


def _now() -> datetime:
    return _store.current_store().clock.now()


def _resolve(conn: sqlite3.Connection, text: str) -> str:
    return _aliases.resolve(conn, text.strip())


def _load_decision(conn: sqlite3.Connection, ref: str) -> DecisionView:
    canonical = _resolve(conn, ref)
    d = _repo.load_decision(conn, canonical)
    if d is None:
        raise NotFound(ref)
    return d


def _at(d: DecisionView, T: EvalTime, cfg: DecConfig, axis: Axis = "knowledge") -> DecisionView:
    v = _states.view_at(d, T, cfg, axis=axis)
    if v is None:
        raise NotFound(
            d.public_id,
            f"{d.public_id} was not known at {format_instant(T.instant)} on the {axis} axis",
        )
    return v


# ==================================================================================================
# Coverage notes


def _mirror_line(d: DecisionView, world: _World) -> str | None:
    issuer = _issuer(d)
    if issuer is None:
        return None
    if d.mirror_scope == "basis_only":
        return (
            f"text mirrored from {issuer} (title, context, statement, options, decided date); "
            "everything else is recorded here"
        )
    run = world.runs.get(issuer)
    exported = (
        format_instant(run.exported_at)
        if run is not None and run.exported_at
        else "an unknown time"
    )
    return f"mirrored from {issuer}, snapshot exported at {exported}; read-only here"


def _coverage(decisions: Iterable[DecisionView], world: _World) -> list[str]:
    notes: list[str] = []
    for d in decisions:
        line = _mirror_line(d, world)
        if line is not None and line not in notes:
            notes.append(line)
    return notes


def _stale(decisions: Iterable[DecisionView], world: _World, T: EvalTime) -> bool:
    for d in decisions:
        issuer = _issuer(d)
        if issuer is None or d.mirror_scope != "full":
            continue
        run = world.runs.get(issuer)
        if run is None or run.as_of_date is None:
            return True
        if run.as_of_date < T.date - timedelta(days=1):
            return True
    return False


def _answer[V](
    value: V,
    world: _World,
    T: EvalTime,
    *,
    axis: Axis = "knowledge",
    shown: Iterable[DecisionView] = (),
    extra: Sequence[str] = (),
) -> Answer[V]:
    shown = list(shown)
    coverage = [*_coverage(shown, world), *extra]
    return Answer(
        value=value,
        instance_role=world.role,
        as_of=T.instant,
        axis=axis,
        coverage=tuple(dict.fromkeys(coverage)),
        stale=_stale(shown, world, T),
    )


def _withhold_money(d: DecisionView) -> tuple[DecisionView, bool]:
    """The ``agent`` projection: money amounts removed (§4.4)."""
    withheld = False
    stakes = []
    for s in d.stakes:
        if s.type == "money" and s.amount is not None:
            withheld = True
            stored = {**s.stored, "amount": None}
            stakes.append(dataclasses.replace(s, amount=None, stored=stored))
        else:
            stakes.append(s)
    return dataclasses.replace(d, stakes=tuple(stakes)), withheld


def _integrity_text(lines: Sequence[IntegrityLine]) -> str | None:
    bad = [line for line in lines if line.status not in ("ok", "ok_with_erasures")]
    if not bad:
        return None
    parts = []
    for line in bad:
        label = "live" if line.edition == "live" else f"E-{line.edition:02d}"
        items = f" ({', '.join(line.items)})" if line.items else ""
        parts.append(f"{label} {line.status}{items}")
    return "integrity: " + "; ".join(parts)


# ==================================================================================================
# I1 queries


def decision_context(
    env: DecEnv,
    ref: str,
    *,
    detail: Detail = "brief",
    as_of: datetime | None = None,
    axis: Axis = "knowledge",
    audience: Audience = "owner",
) -> Answer[DecisionContext]:
    """The card (§5.3), in the spec's order; see the module's spec notes for ``detail`` and
    ``audience``."""
    with _store.read_connection() as conn:
        d = _load_decision(conn, ref)
        world = _world(conn, [d])
    cfg = world.cfg
    T = EvalTime.at(as_of or _now(), cfg.tz)
    v = _at(d, T, cfg, axis)
    # before any projection (the seal covers the amounts); the editions visible at T, their items
    # looked up among every loaded row, so a row voided since its seal is not a changed seal
    lines = _cfj.integrity_lines(v, rows=d)
    extra: list[str] = []
    if audience == "agent":
        v, withheld = _withhold_money(v)
        if withheld:
            extra.append(WITHHELD)
    goals = env.goal_directory
    h = _health.health(v, T, cfg)
    item = _waiting.decision_item(v, T, cfg, goals)
    qc = (
        _card.question_context(item, v, T, cfg, goals=goals, probes=env.attachment_probes)
        if item is not None
        else None
    )
    shown = v.assumptions if detail == "full" else tuple(_states.active_assumptions(v))
    cards = tuple(
        AssumptionCard(
            assumption=a,
            state=_states.effective_state(v, a, T, cfg),
            due=_due.assumption_due(v, a, T, cfg),
            last_check=_states.latest_assessment(a, T, cfg),
            readings=tuple(r for r in a.readings if not _states.voided_by(r, T)),
        )
        for a in shown
    )
    full = detail == "full"
    facts = sorted(
        (f for f in v.facts if not _states.voided_by(f, T)),
        key=lambda f: (_states.occurred_date(f, cfg), f.known_at, f.id),
    )
    reviews = sorted(
        _states.live_reviews(v, T),
        key=lambda r: (_states.occurred_date(r, cfg), r.known_at, r.id),
    )
    context = DecisionContext(
        decision=v,
        integrity_line=_integrity_text(lines),
        share_line=_health.share_line(v, T, cfg),
        health=h,
        waiting_reasons=item.reasons if item is not None else (),
        question_context=qc,
        assumptions=cards,
        ground_facts=tuple(f for f in facts if f.phase == "ground") if full else (),
        monitoring_facts=tuple(f for f in facts if f.phase == "monitoring") if full else (),
        reviews=tuple(reviews) if full else (),
        outcome=_states.current_outcome(v),
        learnings=v.learnings if full else (),
        editions=tuple(line for line in lines if line.edition != "live") if full else (),
        links=tuple(_states.live_links(v, ALL_LINK_ROLES)) if full else (),
        execution={p.kind: p.summary(v.public_id, as_of=T.instant) for p in env.attachment_probes},
        mirror_line=_mirror_line(v, world),
        detail=detail,
        audience=audience,
    )
    return _answer(context, world, T, axis=axis, shown=[v], extra=extra)


def list_decisions(
    env: DecEnv,
    *,
    status: str | None = None,
    kind: str | None = None,
    health: str | None = None,
    linked_to: str | None = None,
    mirror: str | None = None,
    limit: int = 50,
) -> Answer[list[DecisionLine]]:
    """One line per decision, by number: id, title, label, share, review date and the reason that
    decides the label (§5.3)."""
    issuer = mirror if mirror and mirror.lower() not in NATIVE else None
    with _store.read_connection() as conn:
        decisions = _repo.load_decisions(
            conn,
            statuses=[status] if status else None,
            kinds=[kind] if kind else None,
            mirror_issuer=issuer,
        )
        world = _world(conn, decisions)
        target = None
        if linked_to:
            try:
                target = _resolve(conn, linked_to)
            except NotFound:
                target = linked_to.strip()
    cfg = world.cfg
    T = EvalTime.at(_now(), cfg.tz)
    wanted_label = health.upper() if health else None
    lines: list[DecisionLine] = []
    shown: list[DecisionView] = []
    for d in sorted(decisions, key=lambda d: d.number):
        v = _states.view_at(d, T, cfg)
        if v is None:
            continue
        if mirror and mirror.lower() in NATIVE and v.mirror_of:
            continue
        if target and not any(
            link.target_ref in (target, linked_to) for link in _states.live_links(v, ALL_LINK_ROLES)
        ):
            continue
        h = _health.health(v, T, cfg)
        if wanted_label and h.label != wanted_label:
            continue
        first = _health.label_reason(h)
        lines.append(
            DecisionLine(
                public_id=v.public_id,
                title=v.title,
                status=v.status,
                kind=v.kind,
                label=h.label,
                share=h.share,
                review_due=v.review_due,
                first_reason=first.text if first else None,
                mirror_of=v.mirror_of,
            )
        )
        shown.append(v)
        if len(lines) >= limit:
            break
    return _answer(lines, world, T, shown=shown)


def _waiting_time(cfg: DecConfig, today: date | None, as_of: datetime | None) -> EvalTime:
    now = _now()
    day = today or local_date(as_of or now, cfg.tz)
    if as_of is not None:
        instant = as_of
    elif today is not None:
        instant = end_of_local_day(today, cfg.tz)
    else:
        instant = now
    return EvalTime(instant, day)


def waiting(
    env: DecEnv, *, today: date | None = None, as_of: datetime | None = None
) -> Answer[list[WaitingItem]]:
    """The waiting list (§3.8), each item with its question context (§3.9); decisions only in
    I1."""
    with _store.read_connection() as conn:
        decisions = _repo.load_decisions(conn)
        world = _world(conn, decisions)
    cfg = world.cfg
    T = _waiting_time(cfg, today, as_of)
    views = [v for d in decisions if (v := _states.view_at(d, T, cfg)) is not None]
    goals = env.goal_directory
    items = _waiting.waiting(views, T, cfg, goals=goals)
    by_ref = {v.public_id: v for v in views}
    items = [
        _card.with_question_context(
            i, by_ref.get(i.ref), T, cfg, goals=goals, probes=env.attachment_probes
        )
        for i in items
    ]
    shown = [by_ref[i.ref] for i in items if i.ref in by_ref]
    return _answer(items, world, T, shown=shown)


def _eval_time(cfg: DecConfig, instant: datetime | None, today: date | None) -> EvalTime:
    """``T`` at ``instant`` (default now); ``T.date`` is ``today`` when given, else the owner-zone
    date of the instant (see the module's spec note on ``today``)."""
    at = instant or _now()
    return EvalTime(at, today) if today is not None else EvalTime.at(at, cfg.tz)


def assumption_due(
    env: DecEnv,
    assumption_ref: str,
    *,
    at: datetime | None = None,
    today: date | None = None,
) -> Answer[AssumptionDue]:
    """``(date, source)`` and the last assessment of one assumption (§3.6)."""
    with _store.read_connection() as conn:
        canonical = _resolve(conn, assumption_ref)
        found = _repo.load_assumption(conn, canonical)
        if found is None:
            raise NotFound(assumption_ref)
        world = _world(conn, [found[0]])
    cfg = world.cfg
    T = _eval_time(cfg, at, today)
    d, a = found
    v = _at(d, T, cfg)
    av = next((x for x in v.assumptions if x.id == a.id), None)
    if av is None:
        raise NotFound(a.ref, f"{a.ref} was not known at {format_instant(T.instant)}")
    value = AssumptionDue(
        assumption_ref=av.ref,
        due=_due.assumption_due(v, av, T, cfg),
        last_assessment=_states.latest_assessment(av, T, cfg),
    )
    return _answer(value, world, T, shown=[v])


def health(
    env: DecEnv, ref: str, *, as_of: datetime | None = None, today: date | None = None
) -> Answer[HealthResult]:
    """Label, ground, timeliness, reasons, share and the ``bet`` badge (§3.7)."""
    with _store.read_connection() as conn:
        d = _load_decision(conn, ref)
        world = _world(conn, [d])
    cfg = world.cfg
    T = _eval_time(cfg, as_of, today)
    v = _at(d, T, cfg)
    return _answer(_health.health(v, T, cfg), world, T, shown=[v])


def integrity(env: DecEnv, ref: str) -> Answer[list[IntegrityReport]]:
    """Per edition ``ok`` / ``ok_with_erasures`` / ``changed``; live drift; completion pending
    (§3.3). ``ref`` is a decision ref or ``'all'`` (every decision with an edition)."""
    with _store.read_connection() as conn:
        if ref.strip().lower() == "all":
            decisions = [d for d in _repo.load_decisions(conn) if d.editions]
        else:
            decisions = [_load_decision(conn, ref)]
        world = _world(conn, decisions)
    T = EvalTime.at(_now(), world.cfg.tz)
    reports = [_cfj.integrity_report(d) for d in sorted(decisions, key=lambda d: d.number)]
    return _answer(reports, world, T, shown=decisions)


def as_of(env: DecEnv, ref: str, t: datetime, *, axis: Axis = "knowledge") -> Answer[AsOfView]:
    """The record as known at ``t`` on an axis, with what v2 computes at ``t`` (§3.15)."""
    with _store.read_connection() as conn:
        d = _load_decision(conn, ref)
        world = _world(conn, [d])
    cfg = world.cfg
    T = EvalTime.at(t, cfg.tz)
    v = _at(d, T, cfg, axis)
    notes: list[str] = []
    if d.mirror_of and T.instant < d.recorded_at:
        notes.append(
            f"before this instance first imported it ({format_instant(d.recorded_at)}), only "
            f"{_issuer(d)}'s state at that snapshot is known"
        )
    if axis == "occurrence":
        unknown = _states.unknown_event_rows(d)
        if unknown:
            rows = "row" if unknown == 1 else "rows"
            notes.append(f"{unknown} {rows} with unknown event time excluded")
    view = AsOfView(
        decision=v,
        health=_health.health(v, T, cfg),
        dues={a.code: _due.assumption_due(v, a, T, cfg) for a in _states.active_assumptions(v)},
        waiting_reasons=tuple(_waiting.decision_reasons(v, T, cfg, env.goal_directory)),
        coverage=tuple(notes),
    )
    return _answer(view, world, T, axis=axis, shown=[v], extra=notes)


# ==================================================================================================
# I2 queries


def drafts_to_finish(env: DecEnv, *, today: date | None = None) -> Answer[list[DraftItem]]:
    """Drafts left for ``dec.drafts_stale_days`` or longer, with what they miss (§3.8); the
    ``dec_waiting`` tool and ``coflow dec waiting --drafts`` show it beside the waiting list."""
    with _store.read_connection() as conn:
        decisions = _repo.load_decisions(conn, statuses=["draft"])
        world = _world(conn, decisions)
    cfg = world.cfg
    T = _waiting_time(cfg, today, None)
    views = [v for d in decisions if (v := _states.view_at(d, T, cfg)) is not None]
    return _answer(_waiting.drafts_to_finish(views, T, cfg), world, T, shown=views)


def related_learnings(
    env: DecEnv,
    *,
    kind: str | None = None,
    subjects: Sequence[str] = (),
    class_tags: Sequence[str] = (),
) -> Answer[list[RelatedLearning]]:
    raise NotImplementedError("track D, increment I2: related_learnings (§3.11)")


def forks(env: DecEnv, *, status: str | None = None) -> Answer[list[ForkLine]]:
    raise NotImplementedError("track D, increment I2: forks (§5.3)")
