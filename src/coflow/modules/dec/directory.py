"""DEC's implementation of the ``DecisionDirectory`` port (spec §4.2, §3.14).

The read side (``resolve``, ``info``, ``state``, ``open_for``, ``waiting``, ``projection``) is
increment I1 ("implemented by DEC [0A-I1; offers in I3]", §4.2) and delegates to DEC's queries and
loaders. ``accepts_attachment`` and ``likely_for_entry`` are owned by track C (commitments, K's
agent); increment I3, spec §12.4. The class is fixed by the skeleton because ``dec.api.directory``
constructs it. No module consumes the port in I1 except the interfaces' authority lookup (``info``).

Spec notes (integration):

- ``info`` describes the stored record now (status, mirror authority, current edition): it is not
  cut to a time axis. Who owns a record is a fact about the record, so an answer evaluated at
  another time (``waiting --date``, a shadow run) still names its system of record.
- ``resolve`` returns ``Resolved`` only for a reference whose decision exists; a scoped code
  (``D-0907_A-01``) resolves when its decision exists (its own row is the caller's to check).
  ``via`` is ``canonical`` for canonical input, ``tolerant`` for a tolerant form, ``foreign`` for an
  ``<ISSUER>_<id>`` reference found through its alias, and ``alias`` for any other alias.
- ``open_for`` lists draft and active decisions with a live ``about``, ``serves`` or ``tests`` link
  to one of the subjects, by number (§4.3: PPL's dossier line, MTG's brief).
- ``projection`` is the port's compact form (§4.4) for a spoke: ids, title, statement, the share
  line, health with reasons, assumptions with due dates and sources, the authority and the instance
  role. It never carries stakes, so no money amount travels through the port; the full card of the
  CLI and MCP is assembled by ``interfaces/views/card.py`` from ``decision_context``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal, cast

from coflow.kernel.context import EvalTime, format_instant
from coflow.kernel.errors import (
    Accept,
    Ambiguous,
    CoflowError,
    ContractViolation,
    NotFound,
    Refused,
)
from coflow.kernel.ids import aliases as _aliases
from coflow.kernel.ids import codes as _codes
from coflow.kernel.ports.decision_directory import (
    DecisionInfo,
    DecisionState,
    EntryContext,
    Offer,
    ProbeItem,
    Resolved,
    WaitingItem,
)
from coflow.kernel.store import api as _store
from coflow.modules.dec import queries as _queries
from coflow.modules.dec.domain import health as _health
from coflow.modules.dec.domain import states as _states
from coflow.modules.dec.domain.model import Audience, DecEnv, DecisionView
from coflow.modules.dec.store import repo as _repo

__all__ = ["DecDirectory"]

_TODO = "track C: modules/dec/directory.py"
_OPEN = ("draft", "active")
_SUBJECT_ROLES = ("about", "serves", "tests")
_AUDIENCES = ("owner", "agent")

Via = Literal["canonical", "tolerant", "alias", "foreign"]


def _info(d: DecisionView, T: EvalTime) -> DecisionInfo:
    return DecisionInfo(
        public_id=d.public_id,
        title=d.title,
        kind=d.kind,
        status=d.status,
        mirror_of=d.mirror_of,
        mirror_scope=d.mirror_scope,
        current_edition=d.current_edition,
        review_due=d.review_due,
        closed_at=d.closed_at,
        successor_ref=_states.successor_ref(d, T),
    )


def _via(text: str, canonical: str) -> Via:
    t = text.strip()
    if t == canonical:
        return "canonical"
    try:
        tolerant = _codes.canonical(t)
    except CoflowError:
        return "alias"
    if tolerant == canonical:
        return "tolerant"
    try:
        return "foreign" if _codes.parse(tolerant).is_foreign else "alias"
    except CoflowError:
        return "alias"


class DecDirectory:
    """Implements ``kernel.ports.decision_directory.DecisionDirectory``."""

    def __init__(self, env: DecEnv) -> None:
        self.env = env

    def _now(self) -> datetime:
        return _store.current_store().clock.now()

    def resolve(self, text_or_ref: str) -> Resolved | Ambiguous | NotFound:
        with _store.read_connection() as conn:
            try:
                canonical = _aliases.resolve(conn, text_or_ref.strip())
            except (NotFound, Ambiguous) as exc:
                return exc
            except Refused as exc:
                return NotFound(text_or_ref, exc.detail)
            try:
                root = _codes.parse(canonical).root
            except CoflowError:
                return NotFound(text_or_ref, f"{canonical} is not a decision reference")
            exists = conn.execute(
                "SELECT 1 FROM dec_decisions WHERE public_id = ?", (root,)
            ).fetchone()
        if exists is None:
            return NotFound(text_or_ref, f"no decision {root} in this instance")
        return Resolved(ref=canonical, via=_via(text_or_ref, canonical))

    def _load(self, ref: str) -> DecisionView | None:
        with _store.read_connection() as conn:
            try:
                canonical = _aliases.resolve(conn, ref.strip())
                root = _codes.parse(canonical).root
            except CoflowError:
                return None
            return _repo.load_decision(conn, root)

    def info(self, ref: str) -> DecisionInfo | None:
        d = self._load(ref)
        if d is None:
            return None
        with _store.read_connection() as conn:
            cfg, _role = _queries._config(conn)
        return _info(d, EvalTime.at(self._now(), cfg.tz))

    def state(self, ref: str, as_of: datetime | None = None) -> DecisionState:
        answer = _queries.health(self.env, ref, as_of=as_of)
        d = self._load(ref)
        review_due = d.review_due if d is not None else None
        public_id = d.public_id if d is not None else ref
        return _health.to_state(public_id, answer.value, review_due)

    def accepts_attachment(self, ref: str, attachment_kind: str) -> Accept | Refused:
        raise NotImplementedError(_TODO)

    def open_for(
        self, subjects: Sequence[str], *, kinds: Sequence[str] | None = None, limit: int = 10
    ) -> list[DecisionInfo]:
        wanted = {s.strip() for s in subjects if s.strip()}
        if not wanted or limit < 1:
            return []
        with _store.read_connection() as conn:
            cfg, _role = _queries._config(conn)
            decisions = _repo.load_decisions(
                conn, statuses=_OPEN, kinds=list(kinds) if kinds is not None else None
            )
        T = EvalTime.at(self._now(), cfg.tz)
        out: list[DecisionInfo] = []
        for d in decisions:
            v = _states.view_at(d, T, cfg)
            if v is None:
                continue
            if any(link.target_ref in wanted for link in _states.live_links(v, _SUBJECT_ROLES)):
                out.append(_info(v, T))
                if len(out) >= limit:
                    break
        return out

    def likely_for_entry(self, ctx: EntryContext) -> list[Offer]:
        raise NotImplementedError(_TODO)

    def waiting(self, today: date | None = None) -> list[WaitingItem]:
        return _queries.waiting(self.env, today=today).value

    def projection(self, ref: str, audience: str) -> dict[str, object]:
        if audience not in _AUDIENCES:
            raise ContractViolation(f"no {audience!r} projection in the slice ({_AUDIENCES})")
        answer = _queries.decision_context(self.env, ref, audience=cast(Audience, audience))
        c = answer.value
        d = c.decision
        return {
            "audience": audience,
            "ref": d.public_id,
            "title": d.title,
            "kind": d.kind,
            "status": d.status,
            "question": d.question,
            "statement": d.statement,
            "review_due": d.review_due.isoformat() if d.review_due else None,
            "share_line": c.share_line,
            "health": {
                "label": c.health.label,
                "ground": c.health.ground,
                "timeliness": sorted(c.health.timeliness),
                "reasons": list(c.health.words),
            },
            "assumptions": [
                {
                    "code": card.assumption.code,
                    "statement": card.assumption.statement,
                    "state": card.state,
                    "due": card.due.due.isoformat() if card.due.due else None,
                    "due_source": card.due.source,
                }
                for card in c.assumptions
            ],
            "mirror_of": d.mirror_of,
            "mirror_scope": d.mirror_scope,
            "instance_role": answer.instance_role,
            "as_of": format_instant(answer.as_of),
            "coverage": list(answer.coverage),
        }

    def assumptions_to_probe(self, subjects: Sequence[str], *, limit: int = 5) -> list[ProbeItem]:
        raise NotImplementedError("LATER 3: assumptions_to_probe (§7.4)")
