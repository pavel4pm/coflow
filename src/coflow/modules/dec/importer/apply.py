"""Applying an import plan (spec §6.5): new mirrors inserted and sealed E-01 (reason ``import``)
using the hash functions of ``domain/cfj.py``; changed heads versioned; changed bases sealed
E-(n+1) (reason ``source_changed``); children missing in the source voided, never deleted;
tombstones; foreign and burned numbers; foreign context.

Owned by track S (store, import, shadow); increment I1, spec §12.2.

Everything here runs inside the importer's unit of work (``snapshot.py`` opens it) and writes only
through ``kernel.store.api``. The field mapping is §6.3:

- a decision keeps its number (``D907`` becomes ``D-0907``, alias ``V1_D907``), is ``full`` depth
  (``depth_basis = 'import'``), ``reconstructed = 1``, ``mirror_of = 'V1_D907'``, ``mirror_scope =
  'full'``; its knowledge time is the source's ``created_at``;
- one chosen option from the statement plus one per alternative (``origin = 'import'``,
  ``recorded_before_choice = 'unknown'``);
- assumptions keep their codes (``A1`` becomes ``A-01``); the threshold is text, the data source
  kind is ``none`` for an empty source and ``manual`` otherwise; ``ad-hoc`` becomes ``ad_hoc``;
- facts keep their phase; a named session is ``foreign`` evidence ``V1_S...``;
- reviews are ``trigger = 'import'`` with the v1 label in ``legacy_health_at_review``;
- goal links are ``serves``, task and topic links ``foreign_attachment``; ``about_person`` and
  ``about_company`` are ``about`` links; all ``resolution = 'foreign'``;
- the outcome is a ``reported`` resolution by ``import``; the learning is ``legacy_text``;
- decision versions become ``dec_versions`` (``cause_kind = 'import'``, reconstructed); assumption
  state versions become reconstructed assessments (``rebuild_checks.py``).

Spec notes:

- **Knowledge time of what the source did not time-stamp.** A row the source gives no recording
  time for (the outcome, the learning, a change detected between two snapshots without a version
  row, a void of a changed or deleted child) takes the snapshot's ``as_of`` as its
  ``origin_recorded_at`` / ``voided_at``: the source knew it no later than that. So the shadow,
  computed on the knowledge axis at ``as_of``, sees exactly the snapshot. The same holds for every
  row that first appears in a later run of an existing mirror without a time of its own (found in
  review): an assumption successor, a new option, a new ``about`` link, a child that comes back
  after it was deleted, and a link removal (a ``dec_versions`` row of entity ``link``, so a view
  before the snapshot still shows the link). Views and recomputed reports of earlier instants
  therefore do not change when a later snapshot is applied.
- **Restored children.** A fact or review the source deleted is voided; when it comes back with
  the same content it is inserted again as a new row (voids are set once). A deleted assumption
  is dropped; when it comes back it gets a successor, as for a changed basis.
- **Head versions the source records.** ``review_due_initial`` is set when the mirror is inserted;
  later only the source's own earliest ``review_due`` version can correct it. A head change of a
  decision or an assumption that the run's new v1 version rows record is stored once, as that
  imported row.
- **Options are append-only and have no void column.** A changed statement keeps the chosen option
  first imported (its text is frozen at the choice, §2.9) and the new statement is sealed as a
  field; a new alternative text is a new option; a removed alternative stays and is reported.
- **A changed assumption basis** (statement, metric, threshold, source, frequency, criticality) is
  a successor row with the next free code (the predecessor keeps its code and its checks); a
  changed ``next_check_at`` is a versioned update; a deleted assumption is ``dropped``.
- **Outcomes and learnings** cannot be voided; a resolution or learning that changes in the source
  is a new row (the outcome supersedes the previous one), one that disappears is reported.
- A v1 review without an action is imported as ``keep``.
- A head change that the snapshot's own version rows record is stored once, as the imported v1
  version row; a change without one gets a version row of its own (reason "changed in V1 without
  a version row").
- A new mirror's first seal sets ``current_edition`` in the unit that creates it; counters and
  ``current_edition`` are bookkeeping and get no version row (``store/versions.py``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from coflow.kernel.context import format_instant, local_date, parse_instant
from coflow.kernel.events.publish import publish
from coflow.kernel.ids import aliases, codes, tap
from coflow.kernel.store.api import current_unit, insert, set_once, update_head, update_mutable
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.importer import rebuild_checks
from coflow.modules.dec.store import mirror, versions
from coflow.modules.dec.store.mirror import MirrorState
from coflow.modules.dec.store.repo import observed_sort_key

__all__ = [
    "CHILD_KEYS",
    "HEAD_COLUMNS",
    "RunContext",
    "apply_decision",
    "content_hash",
    "decision_head_columns",
    "decision_rows_estimate",
    "mark_decision_absent",
    "register_numbers",
    "seal_if_needed",
    "upsert_foreign_context",
]

CHILD_KEYS: tuple[str, ...] = ("assumptions", "facts", "reviews", "links", "versions")

HEAD_COLUMNS: tuple[str, ...] = (
    "title",
    "statement",
    "context",
    "kind",
    "decider",
    "decider_basis",
    "decider_ref",
    "depth",
    "depth_basis",
    "status",
    "manual_flag",
    "manual_flag_reason",
    "known",
    "would_help",
    "unknowns_json",
    "expected_text",
    "confidence",
    "review_due",
    "review_due_initial",
    "decided_at",
    "decided_precision",
    "decided_basis",
    "closed_at",
    "origin_kind",
    "origin_ref",
    "third_party_sensitive",
    "legacy_json",
)
"""The ``dec_decisions`` columns the source owns and the importer compares on every run."""

ASSUMPTION_BASIS: tuple[str, ...] = (
    "statement",
    "metric",
    "threshold_text",
    "data_source_kind",
    "data_source_text",
    "check_frequency",
    "is_critical",
)
ASSUMPTION_MUTABLE: tuple[str, ...] = ("next_check_at",)

# v1 field names of decision versions -> dec_decisions columns (§6.3).
DECISION_FIELD_MAP: Mapping[str, str] = {
    "context_known": "known",
    "context_unknown": "unknowns_json",
    "context_would_help": "would_help",
    "manual_health": "manual_flag",
    "expected_result": "expected_text",
    "investment": "legacy_json.investment",
}
DATE_FIELDS = frozenset({"review_due", "decided_at", "next_check_at"})
# v1 field names of assumption versions -> dec_assumptions columns.
ASSUMPTION_FIELD_MAP: Mapping[str, str] = {
    "threshold": "threshold_text",
    "data_source": "data_source_text",
}

LINK_ROLES: Mapping[str, tuple[str, str]] = {
    "goal": ("serves", "foreign_goal"),
    "task": ("foreign_attachment", "foreign_task"),
    "topic": ("foreign_attachment", "foreign_topic"),
}
CONTEXT_KINDS: Mapping[str, str] = {
    "goals": "goal",
    "tasks": "task",
    "topics": "topic",
    "sessions": "session",
    "people": "person",
    "companies": "company",
}
TERMINAL = frozenset({"closed", "cancelled", "superseded", "withdrawn"})


# ==================================================================================================
# The run context and small helpers


@dataclass(slots=True)
class RunContext:
    """What every apply step needs about the run; it collects events, findings and counts."""

    run_id: int
    issuer: str
    as_of: datetime
    timezone: str  # the owner's zone: local dates of instants
    source_timezone: str  # the source's zone: its dates
    sessions: Mapping[str, Mapping[str, Any]]
    states: dict[tuple[str, str], MirrorState]
    event_ids: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    sealed_source_changed: list[str] = field(default_factory=list)

    @property
    def as_of_text(self) -> str:
        return format_instant(self.as_of)

    @property
    def run_label(self) -> str:
        return f"import run {self.run_id}"

    def foreign(self, source_id: str) -> str:
        return codes.foreign_ref(self.issuer, source_id)

    def emit(self, type_: str, *, subject: str, entity: str, changed: Sequence[str]) -> None:
        data_class = "system" if entity == "import_run" else "work"
        self.event_ids.append(
            publish(type_, subject=subject, entity=entity, changed=changed, data_class=data_class)
        )


def content_hash(obj: object) -> str:
    """The content hash ``dec_mirror_state`` keeps for a source row (sha256 of its CFJ-1 form)."""
    return cfj.sha256_hex(cfj.cfj(obj))


def _date(value: object) -> str | None:
    """A source date (``YYYY-MM-DD``, optionally with a time) as a stored date."""
    if value is None or str(value).strip() == "":
        return None
    return str(value)[:10]


def _instant(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return format_instant(parse_instant(str(value)))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _cfj_text(obj: object) -> str:
    return cfj.cfj(obj).decode("utf-8")


def _head_source(src: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in src.items() if k not in CHILD_KEYS}


def _code_n(code: object) -> int | None:
    """``A3`` -> 3; ``None`` for a missing code."""
    if not isinstance(code, str) or not code[1:].isdigit():
        return None
    return int(code[1:])


def _frequency(value: object) -> str | None:
    if value is None:
        return None
    return "ad_hoc" if value in ("ad-hoc", "ad_hoc") else str(value)


def _data_source_kind(value: object) -> str:
    return "none" if _text(value) is None else "manual"


def _fetch(sql: str, params: Sequence[object] = ()) -> Any:
    return current_unit().fetch_one(sql, params)


def _fetch_all(sql: str, params: Sequence[object] = ()) -> list[Any]:
    return current_unit().fetch_all(sql, params)


# ==================================================================================================
# Source rows -> stored columns (§6.3)


def decision_head_columns(
    src: Mapping[str, Any], *, issuer: str, sessions: Mapping[str, Any]
) -> dict[str, Any]:
    """The importer-owned ``dec_decisions`` columns of a source decision."""
    mapping = src.get("decider_mapping")
    decider = mapping or "self"
    owner_person = _text(src.get("owner_person"))
    decider_ref = (
        codes.foreign_ref(issuer, owner_person) if decider != "self" and owner_person else None
    )
    unknown = _text(src.get("context_unknown"))
    session = _text(src.get("source_session"))
    origin_kind, origin_ref = "not_recorded", None
    if session is not None:
        kind = (sessions.get(session) or {}).get("communication_type")
        origin_kind = "chat" if kind == "chat" else "session"
        origin_ref = codes.foreign_ref(issuer, session)
    decided = _date(src.get("decided_at"))
    review_due = _date(src.get("review_due"))
    first_review = initial_review_from_versions(src) or review_due
    legacy = {
        "investment": src.get("investment"),
        "executor_person": src.get("executor_person"),
        "process_type": src.get("process_type"),
        "folder_path": src.get("folder_path"),
    }
    return {
        "title": src["title"],
        "statement": _text(src.get("statement")),
        "context": _text(src.get("context")),
        "kind": src.get("kind") or "choice",
        "decider": decider,
        "decider_basis": "mapped" if mapping else "assumed",
        "decider_ref": decider_ref,
        "depth": "full",
        "depth_basis": "import",
        "status": src["status"],
        "manual_flag": src.get("manual_health"),
        "manual_flag_reason": f"set in {issuer}" if src.get("manual_health") else None,
        "known": _text(src.get("context_known")),
        "would_help": _text(src.get("context_would_help")),
        "unknowns_json": _cfj_text([unknown] if unknown else []),
        "expected_text": _text(src.get("expected_result")),
        "confidence": src.get("confidence"),
        "review_due": review_due,
        "review_due_initial": first_review,
        "decided_at": decided,
        "decided_precision": "day" if decided else "unknown",
        "decided_basis": "import" if decided else "unknown",
        "closed_at": _instant(src.get("closed_at")),
        "origin_kind": origin_kind,
        "origin_ref": origin_ref,
        "third_party_sensitive": 1 if _text(src.get("about_person")) else 0,
        "legacy_json": _cfj_text(legacy),
    }


def initial_review_from_versions(src: Mapping[str, Any]) -> str | None:
    """The first review date the source's own version rows show: the ``old_value`` of its earliest
    ``review_due`` version, or ``None`` when there is none (§6.3)."""
    review_versions = sorted(
        (
            v
            for v in src.get("versions") or ()
            if v["entity"] == "decision"
            and v["entity_v1_id"] == src["v1_id"]
            and v["field"] == "review_due"
        ),
        key=lambda v: (v["changed_at"], v["v1_id"]),
    )
    if not review_versions:
        return None
    return _date(review_versions[0].get("old_value"))


def _assumption_columns(src: Mapping[str, Any], issuer: str) -> dict[str, Any]:
    return {
        "position": int(src.get("position") or 0),
        "statement": src["statement"],
        "metric": _text(src.get("metric")),
        "threshold_text": _text(src.get("threshold")),
        "data_source_kind": _data_source_kind(src.get("data_source")),
        "data_source_text": _text(src.get("data_source")),
        "check_frequency": _frequency(src.get("check_frequency")),
        "next_check_at": _date(src.get("next_check_at")),
        "is_critical": int(src.get("is_critical", 1)),
        "origin_recorded_at": _instant(src.get("created_at")),
        "origin_ref": codes.foreign_ref(issuer, str(src["v1_id"])),
    }


def _fact_columns(src: Mapping[str, Any], issuer: str) -> dict[str, Any]:
    occurred = _date(src.get("occurred_at"))
    session = _text(src.get("session"))
    return {
        "phase": "ground" if src.get("phase") == "grounding" else "monitoring",
        "kind": "observation",
        "text": src["fact"],
        "occurred_at": occurred,
        "occurred_precision": "day" if occurred else "unknown",
        "occurred_basis": "import" if occurred else "unknown",
        "evidence_kind": "foreign" if session else "none",
        "evidence_ref": codes.foreign_ref(issuer, session) if session else None,
        "source_text": _text(src.get("source")),
        "reported_by": "import",
        "reconstructed": 1,
        "origin_recorded_at": _instant(src.get("created_at")),
        "origin_ref": codes.foreign_ref(issuer, str(src["v1_id"])),
    }


def _review_columns(src: Mapping[str, Any], issuer: str) -> dict[str, Any]:
    occurred = _date(src.get("reviewed_at"))
    return {
        "action": src.get("action") or "keep",
        "verdict": _text(src.get("verdict")),
        "notes": _text(src.get("notes")),
        "trigger": "import",
        "occurred_at": occurred,
        "occurred_precision": "day" if occurred else "unknown",
        "occurred_basis": "import" if occurred else "unknown",
        "next_review_due": _date(src.get("next_review_due")),
        "legacy_health_at_review": _text(src.get("health_at_review")),
        "reconstructed": 1,
        "origin_recorded_at": _instant(src.get("created_at")),
        "origin_ref": codes.foreign_ref(issuer, str(src["v1_id"])),
    }


def _source_links(
    src: Mapping[str, Any], issuer: str
) -> list[tuple[str, str, dict[str, Any], str]]:
    """(state kind, state key, columns, content hash) of every link the source decision implies.

    A source link hashes its source object (as every child does); an ``about`` link, which comes
    from a head field, hashes its columns."""
    out: list[tuple[str, str, dict[str, Any], str]] = []
    v1 = src["v1_id"]
    for link in src.get("links") or ():
        role, target_kind = LINK_ROLES[link["kind"]]
        via = _text(link.get("source"))
        out.append(
            (
                "link",
                f"{v1}:{link['kind']}:{link['ref']}",
                {
                    "role": role,
                    "target_ref": codes.foreign_ref(issuer, link["ref"]),
                    "target_kind": target_kind,
                    "resolution": "foreign",
                    "note": f"linked in {issuer} via {via}" if via else f"linked in {issuer}",
                    "origin_recorded_at": _instant(link.get("created_at")),
                },
                content_hash(link),
            )
        )
    for field_name, target_kind in (("about_person", "person"), ("about_company", "company")):
        ref = _text(src.get(field_name))
        if ref:
            cols = {
                "role": "about",
                "target_ref": codes.foreign_ref(issuer, ref),
                "target_kind": target_kind,
                "resolution": "foreign",
                "note": None,
                "origin_recorded_at": _instant(src.get("created_at")),
            }
            out.append(("about_link", f"{v1}:{target_kind}:{ref}", cols, content_hash(cols)))
    return out


def _source_options(src: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(state key, columns) of the chosen statement option and one option per alternative."""
    v1 = src["v1_id"]
    out: list[tuple[str, dict[str, Any]]] = []
    statement = _text(src.get("statement"))
    if statement:
        out.append((f"{v1}:statement", {"text": statement, "chosen": 1, "why_rejected": None}))
    for alt in src.get("alternatives") or ():
        text = alt["option"]
        key = f"{v1}:alt:{content_hash(text)[:16]}"
        out.append(
            (key, {"text": text, "chosen": 0, "why_rejected": _text(alt.get("why_rejected"))})
        )
    return out


def decision_rows_estimate(src: Mapping[str, Any]) -> int:
    """How many rows applying a decision may write (for chunking, §6.5)."""
    assumptions = len(src.get("assumptions") or ())
    return (
        2  # the head and its edition
        + len(_source_options(src))
        + 3 * assumptions  # the row and up to two rebuilt checks
        + len(src.get("facts") or ())
        + len(src.get("reviews") or ())
        + len(_source_links(src, "V1"))
        + len(src.get("versions") or ())
        + (1 if src.get("outcome") else 0)
        + (1 if src.get("learning") else 0)
    )


# ==================================================================================================
# Run-wide steps


def register_numbers(snapshot: Mapping[str, Any], *, issuer: str) -> None:
    """Every number the source holds becomes foreign; every number it deleted is burned (§6.4)."""
    for src in snapshot["decisions"]:
        tap.register_foreign("D", int(src["v1_id"]), issuer=issuer, source_id=src["v1_ref"])
        aliases.add_alias(
            codes.foreign_ref(issuer, src["v1_ref"]),
            codes.render("D", int(src["v1_id"])),
            issuer=issuer,
            kind="foreign",
        )
    for n in snapshot["id_space"]["decision"]["deleted_without_trace"]:
        tap.burn("D", int(n), reason="numbering_gap", issuer=issuer)


def upsert_foreign_context(context: Mapping[str, Any], run: RunContext) -> None:
    """Goals with status and change dates, tasks, topics, sessions, people, companies (§6.5)."""
    for section, kind in CONTEXT_KINDS.items():
        for item in context.get(section) or ():
            ref = item["ref"]
            title = item.get("title") or item.get("display_name") or item.get("name")
            status = item.get("status") if section in ("goals", "tasks", "topics") else None
            changed_at = _date(item.get("status_changed_at")) if section == "goals" else None
            row = _fetch(
                "SELECT title, status, status_changed_at, last_run_id FROM dec_foreign_context "
                "WHERE issuer = ? AND kind = ? AND foreign_ref = ?",
                (run.issuer, kind, ref),
            )
            if row is None:
                insert(
                    "dec_foreign_context",
                    {
                        "issuer": run.issuer,
                        "kind": kind,
                        "foreign_ref": ref,
                        "title": title,
                        "status": status,
                        "status_changed_at": changed_at,
                        "status_changed_precision": "day" if changed_at else "unknown",
                        "first_seen_status_run_id": run.run_id,
                        "last_run_id": run.run_id,
                    },
                )
                continue
            changes: dict[str, str | int | None] = {}
            if row["title"] != title:
                changes["title"] = title
            if row["status"] != status:
                changes.update(
                    status=status,
                    status_changed_at=changed_at,
                    status_changed_precision="day" if changed_at else "unknown",
                    first_seen_status_run_id=run.run_id,
                )
            elif row["status_changed_at"] != changed_at:
                changes.update(
                    status_changed_at=changed_at,
                    status_changed_precision="day" if changed_at else "unknown",
                )
            if row["last_run_id"] != run.run_id:
                changes["last_run_id"] = run.run_id
            if changes:
                update_mutable(
                    "dec_foreign_context",
                    {"issuer": run.issuer, "kind": kind, "foreign_ref": ref},
                    **changes,
                )


def mark_decision_absent(state: MirrorState, run: RunContext) -> str | None:
    """Tombstone a decision missing from the snapshot (never a delete); its ref, if newly absent."""
    if not mirror.mark_absent(state, run.run_id):
        return None
    row = _fetch("SELECT public_id FROM dec_decisions WHERE id = ?", (state.local_id,))
    ref = row["public_id"] if row else codes.render("D", int(state.source_id))
    run.emit(
        "coflow.dec.decision.imported",
        subject=ref,
        entity="decision",
        changed=["absent_since_run_id"],
    )
    return str(ref)


# ==================================================================================================
# One decision


@dataclass(slots=True)
class _Counters:
    a_seq: int = 0
    o_seq: int = 0
    r_seq: int = 0
    l_seq: int = 0
    ft_seq: int = 0

    def as_columns(self) -> dict[str, int]:
        return {
            "a_seq": self.a_seq,
            "o_seq": self.o_seq,
            "r_seq": self.r_seq,
            "l_seq": self.l_seq,
            "ft_seq": self.ft_seq,
        }


def _put(run: RunContext, kind: str, key: str, table: str, local_id: int, digest: str) -> None:
    existing = run.states.get((kind, key))
    mirror.put_state(
        issuer=run.issuer,
        source_kind=kind,
        source_id=key,
        local_table=table,
        local_id=local_id,
        content_hash=digest,
        run_id=run.run_id,
        existing=existing,
    )
    run.states[(kind, key)] = MirrorState(
        issuer=run.issuer,
        source_kind=kind,
        source_id=key,
        local_table=table,
        local_id=local_id,
        content_hash=digest,
        first_run_id=existing.first_run_id if existing else run.run_id,
        last_run_id=run.run_id,
        absent_since_run_id=None,
        adopted_at=existing.adopted_at if existing else None,
    )


def _head_version(decision_id: int) -> int:
    return int(_fetch("SELECT version FROM dec_decisions WHERE id = ?", (decision_id,))["version"])


def _version_field(src_field: str) -> str:
    return DECISION_FIELD_MAP.get(src_field, src_field)


def apply_decision(src: Mapping[str, Any], run: RunContext) -> tuple[str, list[str]]:
    """Insert or update one mirrored decision with every child; returns its ref and what changed.

    The caller decides whether the decision changed at all (the content hashes); this function is
    idempotent anyway: unchanged rows are only refreshed in ``dec_mirror_state``.
    """
    key = str(src["v1_id"])
    public_id = codes.render("D", int(src["v1_id"]))
    head = decision_head_columns(src, issuer=run.issuer, sessions=run.sessions)
    state = run.states.get(("decision", key))
    changed: list[str] = []

    if state is None:
        decision_id = insert(
            "dec_decisions",
            {
                "public_id": public_id,
                "number": int(src["v1_id"]),
                **head,
                "reconstructed": 1,
                "mirror_of": codes.foreign_ref(run.issuer, src["v1_ref"]),
                "mirror_scope": "full",
                "origin_recorded_at": _instant(src.get("created_at")),
            },
        )
        counters = _Counters()
        changed += ["status", "kind"]
        new_decision = True
    else:
        decision_id = state.local_id
        row = _fetch("SELECT * FROM dec_decisions WHERE id = ?", (decision_id,))
        counters = _Counters(
            a_seq=row["a_seq"],
            o_seq=row["o_seq"],
            r_seq=row["r_seq"],
            l_seq=row["l_seq"],
            ft_seq=row["ft_seq"],
        )
        changed += _update_head(src, decision_id, row, head, run)
        new_decision = False

    changed += _apply_options(src, decision_id, counters, run, new_decision=new_decision)
    assumption_ids = _apply_assumptions(src, decision_id, public_id, counters, run)
    changed += assumption_ids.changed
    changed += _apply_facts(src, decision_id, counters, assumption_ids.by_v1, run)
    changed += _apply_reviews(src, decision_id, counters, run)
    changed += _apply_links(src, decision_id, run, new_decision=new_decision)
    outcome_id = _apply_outcome(src, decision_id, run)
    changed += ["outcome"] if outcome_id is not None else []
    if _apply_learning(src, decision_id, counters, outcome_id, run):
        changed.append("learning")
    changed += _apply_versions(src, decision_id, assumption_ids.by_v1, run)
    rebuilt = rebuild_checks.rebuild_checks(
        decision_id=decision_id,
        assumptions=[(a, assumption_ids.by_v1[a["v1_id"]]) for a in src.get("assumptions") or ()],
        versions=src.get("versions") or (),
        run=run,
    )
    if rebuilt:
        changed.append("checks")

    seqs = counters.as_columns()
    current = _fetch(
        "SELECT a_seq, o_seq, r_seq, l_seq, ft_seq FROM dec_decisions WHERE id = ?", (decision_id,)
    )
    seq_changes = {k: v for k, v in seqs.items() if current[k] != v}
    if seq_changes:
        update_head("dec_decisions", decision_id, _head_version(decision_id), **seq_changes)

    sealed = seal_if_needed(decision_id, run)
    if sealed is not None:
        changed.append("current_edition")
    _put(run, "decision", key, "dec_decisions", decision_id, content_hash(_head_source(src)))
    if new_decision or changed:
        names = sorted(set(changed))
        run.emit(
            "coflow.dec.decision.imported", subject=public_id, entity="decision", changed=names
        )
    return public_id, sorted(set(changed))


def _update_head(
    src: Mapping[str, Any],
    decision_id: int,
    row: Mapping[str, Any],
    head: Mapping[str, Any],
    run: RunContext,
) -> list[str]:
    diff = {col: head[col] for col in HEAD_COLUMNS if row[col] != head[col]}
    # review_due_initial is set when the mirror is inserted; later only the source's own earliest
    # review_due version may correct it (a v1 change without a version row, e.g. a close that
    # clears review_due, must not rewrite a basis field and seal a source_changed edition)
    if "review_due_initial" in diff and initial_review_from_versions(src) is None:
        del diff["review_due_initial"]
    if not diff:
        return []
    recorded_by_source = {
        _version_field(v["field"])
        for v in src.get("versions") or ()
        if v["entity"] == "decision"
        and v["entity_v1_id"] == src["v1_id"]
        and ("version", str(v["v1_id"])) not in run.states
    }
    update_head("dec_decisions", decision_id, int(row["version"]), **diff)
    for col, new in diff.items():
        if col in recorded_by_source:
            continue  # the imported v1 version row records this change
        versions.record_version(
            "decision",
            decision_id,
            col,
            row[col],
            new,
            cause_kind="import",
            cause_ref=run.run_label,
            reason=f"changed in {run.issuer} without a version row",
            reconstructed=True,
            origin_recorded_at=run.as_of_text,
        )
    return sorted(diff)


def _apply_options(
    src: Mapping[str, Any],
    decision_id: int,
    counters: _Counters,
    run: RunContext,
    *,
    new_decision: bool,
) -> list[str]:
    changed: list[str] = []
    # an option of a new mirror is known from the decision's creation; one a later snapshot adds
    # is known from that snapshot (the source does not time-stamp alternatives)
    known = _instant(src.get("created_at")) if new_decision else run.as_of_text
    has_chosen = (
        _fetch(
            "SELECT 1 AS x FROM dec_options WHERE decision_id = ? AND chosen = 1", (decision_id,)
        )
        is not None
    )
    wanted = _source_options(src)
    for key, cols in wanted:
        digest = content_hash(cols)
        state = run.states.get(("option", key))
        if state is not None:
            _put(run, "option", key, "dec_options", state.local_id, state.content_hash)
            continue
        if cols["chosen"] == 1 and has_chosen:
            run.findings.append(
                f"{codes.render('D', int(src['v1_id']))}: the statement changed in {run.issuer}; "
                "the chosen option keeps the text it was imported with (options are append-only)"
            )
            continue
        counters.o_seq += 1
        option_id = insert(
            "dec_options",
            {
                "decision_id": decision_id,
                "code_n": counters.o_seq,
                **cols,
                "recorded_before_choice": "unknown",
                "origin": "import",
                "salt": cfj.new_salt(),
                "origin_recorded_at": known,
            },
        )
        has_chosen = has_chosen or cols["chosen"] == 1
        _put(run, "option", key, "dec_options", option_id, digest)
        changed.append("options")
    wanted_keys = {k for k, _ in wanted}
    prefix = f"{src['v1_id']}:alt:"
    for (kind, key), _state in list(run.states.items()):
        if kind == "option" and key.startswith(prefix) and key not in wanted_keys:
            run.findings.append(
                f"{codes.render('D', int(src['v1_id']))}: an alternative was removed in "
                f"{run.issuer}; the option stays (options are append-only)"
            )
    return changed


@dataclass(slots=True)
class _AssumptionResult:
    by_v1: dict[int, int] = field(default_factory=dict)  # v1 id -> current local id
    changed: list[str] = field(default_factory=list)


def _free_code(decision_id: int, wanted: int | None, counters: _Counters) -> int:
    if wanted is not None:
        taken = _fetch(
            "SELECT 1 AS x FROM dec_assumptions WHERE decision_id = ? AND code_n = ?",
            (decision_id, wanted),
        )
        if taken is None:
            counters.a_seq = max(counters.a_seq, wanted)
            return wanted
    counters.a_seq += 1
    while _fetch(
        "SELECT 1 AS x FROM dec_assumptions WHERE decision_id = ? AND code_n = ?",
        (decision_id, counters.a_seq),
    ):
        counters.a_seq += 1
    return counters.a_seq


def _insert_assumption(decision_id: int, code_n: int, cols: Mapping[str, Any]) -> int:
    return insert(
        "dec_assumptions",
        {
            "decision_id": decision_id,
            "code_n": code_n,
            **cols,
            "status": "active",
            "salt": cfj.new_salt(),
        },
    )


def _set_assumption(
    assumption_id: int,
    changes: Mapping[str, Any],
    *,
    reason: str,
    run: RunContext,
    recorded_by_source: frozenset[str] = frozenset(),
) -> None:
    row = _fetch("SELECT * FROM dec_assumptions WHERE id = ?", (assumption_id,))
    update_head("dec_assumptions", assumption_id, int(row["version"]), **changes)
    for col, new in changes.items():
        if col in recorded_by_source:
            continue  # the imported v1 version row records this change
        versions.record_version(
            "assumption",
            assumption_id,
            col,
            row[col],
            new,
            cause_kind="import",
            cause_ref=run.run_label,
            reason=reason,
            reconstructed=True,
            origin_recorded_at=run.as_of_text,
        )


def _apply_assumptions(
    src: Mapping[str, Any],
    decision_id: int,
    public_id: str,
    counters: _Counters,
    run: RunContext,
) -> _AssumptionResult:
    result = _AssumptionResult()
    ordered = sorted(
        src.get("assumptions") or (), key=lambda a: (int(a.get("position") or 0), a["v1_id"])
    )
    for a in ordered:
        key = str(a["v1_id"])
        cols = _assumption_columns(a, run.issuer)
        digest = content_hash(a)
        state = run.states.get(("assumption", key))
        if state is None:
            code_n = _free_code(decision_id, _code_n(a.get("code")), counters)
            local = _insert_assumption(decision_id, code_n, cols)
            _put(run, "assumption", key, "dec_assumptions", local, digest)
            result.by_v1[a["v1_id"]] = local
            result.changed.append("assumptions")
            continue
        local = state.local_id
        returned = _returned(state)
        if state.content_hash != digest or returned:
            row = _fetch("SELECT * FROM dec_assumptions WHERE id = ?", (local,))
            basis_changed = [c for c in ASSUMPTION_BASIS if row[c] != cols[c]]
            if row["status"] != "active":
                basis_changed = basis_changed or ["status"]
            if basis_changed:
                code_n = _free_code(decision_id, None, counters)
                # the successor first exists in this snapshot, so it is known from its as_of; the
                # floor of its due date keeps the source row's creation (``due.floor_date``)
                successor = _insert_assumption(
                    decision_id, code_n, {**cols, "origin_recorded_at": run.as_of_text}
                )
                if row["status"] == "active":
                    _set_assumption(
                        local,
                        {"status": "superseded", "superseded_by": successor},
                        reason=f"changed in {run.issuer}: {', '.join(basis_changed)}",
                        run=run,
                    )
                old_ref = codes.render_scoped(public_id, "A", int(row["code_n"]))
                new_ref = codes.render_scoped(public_id, "A", code_n)
                if returned and basis_changed == ["status"]:
                    run.findings.append(
                        f"{old_ref} is back in {run.issuer} after it was deleted: added again "
                        f"as {new_ref}"
                    )
                else:
                    run.findings.append(
                        f"{old_ref} changed in {run.issuer} ({', '.join(basis_changed)}): "
                        f"superseded by {new_ref}"
                    )
                local = successor
                result.changed.append("assumptions")
            else:
                mutable = {c: cols[c] for c in ASSUMPTION_MUTABLE if row[c] != cols[c]}
                if mutable:
                    _set_assumption(
                        local,
                        mutable,
                        reason=f"changed in {run.issuer}",
                        run=run,
                        recorded_by_source=_versioned_by_source(src, a["v1_id"], run),
                    )
                    result.changed.append("assumptions")
        _put(run, "assumption", key, "dec_assumptions", local, digest)
        result.by_v1[a["v1_id"]] = local
    present = {str(a["v1_id"]) for a in ordered}
    for row in _fetch_all(
        "SELECT ms.source_id AS source_id, a.id AS id, a.status AS status FROM dec_mirror_state ms "
        "JOIN dec_assumptions a ON ms.local_table = 'dec_assumptions' AND ms.local_id = a.id "
        "WHERE ms.issuer = ? AND ms.source_kind = 'assumption' AND a.decision_id = ?",
        (run.issuer, decision_id),
    ):
        if row["source_id"] in present:
            continue
        state = run.states[("assumption", row["source_id"])]
        if mirror.mark_absent(state, run.run_id) and row["status"] == "active":
            _set_assumption(
                row["id"],
                {"status": "dropped", "drop_reason": f"deleted in {run.issuer}"},
                reason=f"deleted in {run.issuer}",
                run=run,
            )
            result.changed.append("assumptions")
    return result


def _versioned_by_source(src: Mapping[str, Any], v1_id: int, run: RunContext) -> frozenset[str]:
    """The ``dec_assumptions`` columns that new v1 version rows of assumption ``v1_id`` record in
    this run (``_apply_versions`` stores them; the head update must not add a second row)."""
    return frozenset(
        ASSUMPTION_FIELD_MAP.get(v["field"], v["field"])
        for v in src.get("versions") or ()
        if v["entity"] == "assumption"
        and v["entity_v1_id"] == v1_id
        and v["field"] != "state"
        and ("version", str(v["v1_id"])) not in run.states
    )


def _returned(state: MirrorState) -> bool:
    """A child the source deleted (tombstoned; a fact or review voided, an assumption dropped) that
    is in the snapshot again. Voids are set once, so it comes back as a new row known from this
    snapshot."""
    return state.absent_since_run_id is not None


def _void(table: str, local_id: int, reason: str, run: RunContext) -> bool:
    row = _fetch(f"SELECT voided_at FROM {table} WHERE id = ?", (local_id,))
    if row is None or row["voided_at"] is not None:
        return False
    set_once(table, local_id, voided_at=run.as_of_text, voided_reason=reason)
    return True


def _apply_facts(
    src: Mapping[str, Any],
    decision_id: int,
    counters: _Counters,
    assumptions: Mapping[int, int],
    run: RunContext,
) -> list[str]:
    changed: list[str] = []
    present: set[str] = set()
    for f in src.get("facts") or ():
        key = str(f["v1_id"])
        present.add(key)
        digest = content_hash(f)
        state = run.states.get(("fact", key))
        if state is not None and state.content_hash == digest and not _returned(state):
            _put(run, "fact", key, "dec_facts", state.local_id, digest)
            continue
        cols = _fact_columns(f, run.issuer)
        corrects = None
        if state is not None:  # changed, or deleted in the source and back (already voided)
            _void("dec_facts", state.local_id, f"changed in {run.issuer}", run)
            corrects = state.local_id
            cols["origin_recorded_at"] = run.as_of_text
        counters.ft_seq += 1
        fact_id = insert(
            "dec_facts",
            {
                "decision_id": decision_id,
                "code_n": counters.ft_seq,
                **cols,
                "corrects_fact_id": corrects,
                "salt": cfj.new_salt(),
            },
        )
        target = f.get("assumption_v1_id")
        if target is not None:
            if target in assumptions:
                insert(
                    "dec_fact_assumptions",
                    {
                        "fact_id": fact_id,
                        "assumption_id": assumptions[target],
                        "bearing": "bears_on",
                    },
                )
            else:
                run.findings.append(
                    f"{codes.render('D', int(src['v1_id']))}: a fact names an assumption of "
                    "another decision; the bearing is not imported"
                )
        _put(run, "fact", key, "dec_facts", fact_id, digest)
        changed.append("facts")
    changed += _void_absent(
        "fact", "dec_facts", decision_id, present, f"deleted in {run.issuer}", run
    )
    return changed


def _void_absent(
    kind: str, table: str, decision_id: int, present: set[str], reason: str, run: RunContext
) -> list[str]:
    changed: list[str] = []
    for row in _fetch_all(
        f"SELECT ms.source_id AS source_id, t.id AS id FROM dec_mirror_state ms "
        f"JOIN {table} t ON ms.local_table = ? AND ms.local_id = t.id "
        "WHERE ms.issuer = ? AND ms.source_kind = ? AND t.decision_id = ?",
        (table, run.issuer, kind, decision_id),
    ):
        if row["source_id"] in present:
            continue
        state = run.states[(kind, row["source_id"])]
        mirror.mark_absent(state, run.run_id)
        if _void(table, row["id"], reason, run):
            changed.append(f"{kind}s")
    return changed


def _apply_reviews(
    src: Mapping[str, Any], decision_id: int, counters: _Counters, run: RunContext
) -> list[str]:
    changed: list[str] = []
    present: set[str] = set()
    ordered = sorted(
        src.get("reviews") or (),
        key=lambda r: (str(r.get("reviewed_at") or ""), str(r.get("created_at")), r["v1_id"]),
    )
    for r in ordered:
        key = str(r["v1_id"])
        present.add(key)
        digest = content_hash(r)
        state = run.states.get(("review", key))
        if state is not None and state.content_hash == digest and not _returned(state):
            _put(run, "review", key, "dec_reviews", state.local_id, digest)
            continue
        cols = _review_columns(r, run.issuer)
        if state is not None:  # changed, or deleted in the source and back (already voided)
            _void("dec_reviews", state.local_id, f"changed in {run.issuer}", run)
            cols["origin_recorded_at"] = run.as_of_text
        counters.r_seq += 1
        review_id = insert(
            "dec_reviews", {"decision_id": decision_id, "code_n": counters.r_seq, **cols}
        )
        _put(run, "review", key, "dec_reviews", review_id, digest)
        changed.append("reviews")
    changed += _void_absent(
        "review", "dec_reviews", decision_id, present, f"deleted in {run.issuer}", run
    )
    return changed


def _apply_links(
    src: Mapping[str, Any], decision_id: int, run: RunContext, *, new_decision: bool
) -> list[str]:
    changed: list[str] = []
    present: dict[str, set[str]] = {"link": set(), "about_link": set()}
    for kind, key, cols, digest in _source_links(src, run.issuer):
        present[kind].add(key)
        if not new_decision and (kind == "about_link" or cols["origin_recorded_at"] is None):
            # a link a later snapshot adds without its own time (an ``about`` link comes from a
            # head field) is known from that snapshot, not from the decision's creation
            cols = {**cols, "origin_recorded_at": run.as_of_text}
        state = run.states.get((kind, key))
        if state is not None:
            row = _fetch("SELECT removed_tx FROM dec_links WHERE id = ?", (state.local_id,))
            if row is not None and row["removed_tx"] is None:
                _put(run, kind, key, "dec_links", state.local_id, digest)
                continue
        live = _fetch(
            "SELECT id FROM dec_links WHERE decision_id = ? AND role = ? AND target_ref = ? "
            "AND removed_tx IS NULL",
            (decision_id, cols["role"], cols["target_ref"]),
        )
        if live is not None:  # the same target linked twice in the source (e.g. task and topic)
            _put(run, kind, key, "dec_links", int(live["id"]), digest)
            continue
        link_id = insert("dec_links", {"decision_id": decision_id, **cols})
        _put(run, kind, key, "dec_links", link_id, digest)
        changed.append("links")
    for kind in ("link", "about_link"):
        for row in _fetch_all(
            "SELECT ms.source_id AS source_id, l.id AS id, l.removed_tx AS removed_tx "
            "FROM dec_mirror_state ms JOIN dec_links l "
            "ON ms.local_table = 'dec_links' AND ms.local_id = l.id "
            "WHERE ms.issuer = ? AND ms.source_kind = ? AND l.decision_id = ?",
            (run.issuer, kind, decision_id),
        ):
            if row["source_id"] in present[kind]:
                continue
            mirror.mark_absent(run.states[(kind, row["source_id"])], run.run_id)
            if row["removed_tx"] is None:
                tx = current_unit().tx
                set_once(
                    "dec_links",
                    int(row["id"]),
                    removed_tx=tx,
                    removed_reason=f"removed in {run.issuer}",
                )
                # when the removal became known: a view before this snapshot still shows the link
                versions.record_version(
                    "link",
                    int(row["id"]),
                    "removed_tx",
                    None,
                    tx,
                    cause_kind="import",
                    cause_ref=run.run_label,
                    reason=f"removed in {run.issuer}",
                    reconstructed=True,
                    origin_recorded_at=run.as_of_text,
                )
                changed.append("links")
    return changed


def _apply_outcome(src: Mapping[str, Any], decision_id: int, run: RunContext) -> int | None:
    """A new ``reported`` resolution when the source's outcome appeared or changed; its id."""
    key = str(src["v1_id"])
    outcome = src.get("outcome")
    state = run.states.get(("outcome", key))
    digest = content_hash(outcome)
    if state is not None and state.content_hash == digest:
        _put(run, "outcome", key, "dec_outcomes", state.local_id, digest)
        return None
    if outcome is None:
        if state is not None:
            run.findings.append(
                f"{codes.render('D', int(src['v1_id']))}: the outcome was cleared in {run.issuer};"
                " resolutions are append-only, the imported one stays"
            )
            _put(run, "outcome", key, "dec_outcomes", state.local_id, digest)
        return None
    closed = _instant(src.get("closed_at"))
    outcome_id = insert(
        "dec_outcomes",
        {
            "decision_id": decision_id,
            "kind": outcome,
            "basis": "reported",
            "evidence_refs_json": "[]",
            "occurred_at": closed,
            "occurred_precision": "instant" if closed else "unknown",
            "occurred_basis": "import" if closed else "unknown",
            "resolved_by": "import",
            "supersedes_outcome_id": state.local_id if state is not None else None,
            "reconstructed": 1,
            "origin_recorded_at": closed if state is None and closed else run.as_of_text,
        },
    )
    _put(run, "outcome", key, "dec_outcomes", outcome_id, digest)
    return outcome_id


def _apply_learning(
    src: Mapping[str, Any],
    decision_id: int,
    counters: _Counters,
    outcome_id: int | None,
    run: RunContext,
) -> bool:
    key = str(src["v1_id"])
    text = _text(src.get("learning"))
    state = run.states.get(("learning", key))
    digest = content_hash(text)
    if state is not None and state.content_hash == digest:
        _put(run, "learning", key, "dec_learnings", state.local_id, digest)
        return False
    if text is None:
        if state is not None:
            run.findings.append(
                f"{codes.render('D', int(src['v1_id']))}: the learning was cleared in "
                f"{run.issuer}; learnings are append-only, the imported one stays"
            )
            _put(run, "learning", key, "dec_learnings", state.local_id, digest)
        return False
    if outcome_id is None:
        latest = _fetch(
            "SELECT id FROM dec_outcomes WHERE decision_id = ? ORDER BY id DESC LIMIT 1",
            (decision_id,),
        )
        outcome_id = int(latest["id"]) if latest else None
    closed = _instant(src.get("closed_at"))
    counters.l_seq += 1
    learning_id = insert(
        "dec_learnings",
        {
            "decision_id": decision_id,
            "code_n": counters.l_seq,
            "edition": 0,
            "outcome_id": outcome_id,
            "legacy_text": text,
            "salt": cfj.new_salt(),
            "reconstructed": 1,
            "origin_recorded_at": closed if state is None and closed else run.as_of_text,
        },
    )
    _put(run, "learning", key, "dec_learnings", learning_id, digest)
    return True


def _version_value(column: str, value: object) -> str | None:
    if value is None:
        return None
    if column == "unknowns_json":
        text = _text(value)
        return _cfj_text([text] if text else [])
    if column in DATE_FIELDS:
        return _date(value)
    if column == "check_frequency":
        return _frequency(value)
    return str(value)


def _apply_versions(
    src: Mapping[str, Any], decision_id: int, assumptions: Mapping[int, int], run: RunContext
) -> list[str]:
    """v1's field history: decision and non-state assumption rows become ``dec_versions``; state
    rows are rebuilt as assessments by ``rebuild_checks`` (which also records their state)."""
    changed: list[str] = []
    for v in sorted(src.get("versions") or (), key=lambda v: (v["changed_at"], v["v1_id"])):
        key = str(v["v1_id"])
        state = run.states.get(("version", key))
        if state is not None:
            _put(run, "version", key, state.local_table, state.local_id, state.content_hash)
            continue
        if v["entity"] == "assumption" and v["field"] == "state":
            continue  # rebuild_checks turns it into a reconstructed assessment
        if v["entity"] == "decision":
            entity, entity_id = "decision", decision_id
            column = _version_field(v["field"])
        else:
            local = assumptions.get(v["entity_v1_id"])
            if local is None:
                run.findings.append(
                    f"{codes.render('D', int(src['v1_id']))}: a version row names an assumption "
                    "that is not in the snapshot; it is not imported"
                )
                continue
            entity, entity_id = "assumption", local
            column = ASSUMPTION_FIELD_MAP.get(v["field"], v["field"])
        version_id = versions.record_version(
            entity,
            entity_id,
            column,
            _version_value(column, v.get("old_value")),
            _version_value(column, v.get("new_value")),
            cause_kind="import",
            cause_ref=f"{run.issuer} version {v['v1_id']}",
            reason=_text(v.get("source")),
            reconstructed=True,
            origin_recorded_at=_instant(v["changed_at"]),
            origin_ref=codes.foreign_ref(run.issuer, key),
        )
        _put(run, "version", key, "dec_versions", version_id, content_hash(v))
        changed.append("versions")
    return changed


# ==================================================================================================
# The seal at import (§3.3, §6.5)


def _items(decision_id: int) -> list[cfj.SealItem]:
    items: list[cfj.SealItem] = []
    for o in _fetch_all(
        "SELECT * FROM dec_options WHERE decision_id = ? ORDER BY code_n", (decision_id,)
    ):
        items.append(
            cfj.SealItem(
                kind="option", code=codes.render("O", o["code_n"]), row=dict(o), salt=o["salt"]
            )
        )
    for f in _fetch_all(
        "SELECT * FROM dec_facts WHERE decision_id = ? AND phase = 'ground' AND voided_at IS NULL "
        "ORDER BY code_n",
        (decision_id,),
    ):
        items.append(
            cfj.SealItem(
                kind="ground", code=codes.render("FT", f["code_n"]), row=dict(f), salt=f["salt"]
            )
        )
    for a in _fetch_all(
        "SELECT * FROM dec_assumptions WHERE decision_id = ? AND status = 'active' "
        "ORDER BY position, code_n",
        (decision_id,),
    ):
        items.append(
            cfj.SealItem(
                kind="assumption", code=codes.render("A", a["code_n"]), row=dict(a), salt=a["salt"]
            )
        )
    for s in _fetch_all(
        "SELECT * FROM dec_stakes WHERE decision_id = ? AND planned = 1 ORDER BY id", (decision_id,)
    ):
        items.append(cfj.SealItem(kind="stake", code=str(s["id"]), row=dict(s), salt=s["salt"]))
    return items


def _item_hashes(items: Iterable[cfj.SealItem]) -> list[list[str]]:
    return sorted(
        [i.kind, i.code, cfj.unit_hash(i.salt, cfj.item_content(i.kind, i.row, code=i.code))]
        for i in items
    )


def _observed_local(row: Mapping[str, Any], tz: str) -> date | None:
    if row["observed_precision"] == "unknown" or row["observed_at"] is None:
        return None
    text = str(row["observed_at"])
    if row["observed_precision"] == "instant":
        return local_date(parse_instant(text), tz)
    return date.fromisoformat(text[:10])


def unverifiable_share_text(decision_id: int) -> str | None:
    """The unverifiable share at seal (§3.7 ``unverifiable_share`` at the seal instant).

    An assumption of the pool counts when its latest non-voided assessment is UNVERIFIABLE, or when
    it has none and its data source kind is ``none``. The share is stored as a decimal text rounded
    to four places (``0.5``, ``0.6667``, ``1``); ``None`` without a pool.
    """
    active = _fetch_all(
        "SELECT id, is_critical, data_source_kind FROM dec_assumptions "
        "WHERE decision_id = ? AND status = 'active'",
        (decision_id,),
    )
    critical = [a for a in active if a["is_critical"]]
    pool = critical or active
    if not pool:
        return None
    count = 0
    for a in pool:
        checks = _fetch_all(
            "SELECT state, observed_at, observed_precision, recorded_at, origin_recorded_at, id "
            "FROM dec_checks WHERE assumption_id = ? AND kind = 'assessment' AND voided_at IS NULL",
            (a["id"],),
        )
        if checks:
            latest = max(checks, key=observed_sort_key)
            count += latest["state"] == "UNVERIFIABLE"
        else:
            count += a["data_source_kind"] == "none"
    share = (Decimal(count) / Decimal(len(pool))).quantize(Decimal("0.0001")).normalize()
    return format(share, "f")


def seal_if_needed(decision_id: int, run: RunContext) -> int | None:
    """Seal E-01 (``import``) for a new active or terminal mirror, or E-(n+1) (``source_changed``)
    when the basis differs from the current edition; returns the new edition number."""
    row = dict(_fetch("SELECT * FROM dec_decisions WHERE id = ?", (decision_id,)))
    items = _items(decision_id)
    current = int(row["current_edition"])
    if current == 0:
        if row["status"] == "draft":
            return None
        reason = "import"
    else:
        edition = _fetch(
            "SELECT fields_json, items_json FROM dec_editions WHERE decision_id = ? AND n = ?",
            (decision_id, current),
        )
        fields = {k: cfj.basis_value(row, k) for k in cfj.BASIS_FIELDS}
        same_fields = json.loads(edition["fields_json"]) == json.loads(_cfj_text(fields))
        same_items = json.loads(edition["items_json"]) == _item_hashes(items)
        if same_fields and same_items:
            return None
        reason = "source_changed"
    n = current + 1
    unit = current_unit()
    draft = cfj.build_edition(
        public_id=row["public_id"],
        n=n,
        decision=row,
        items=items,
        sealed_at=format_instant(unit.committed_at),
        sealed_by=unit.ctx.actor,
    )
    insert(
        "dec_editions",
        {
            "decision_id": decision_id,
            "n": n,
            "reason": reason,
            "fields_json": draft.fields_json,
            "field_salts_json": draft.field_salts_json,
            "field_hashes_json": draft.field_hashes_json,
            "items_json": draft.items_json,
            "seal_hash": draft.seal_hash,
            "canon_version": cfj.CANON_VERSION,
            "sealed_at": draft.sealed_at,
            "sealed_by": draft.sealed_by,
            "review_id": None,
            "reason_text": run.run_label,
            "unverifiable_at_seal": unverifiable_share_text(decision_id),
            "reconstructed": int(row["reconstructed"]),
            "erased_fields_json": "[]",
        },
    )
    tables = {"option": "dec_options", "ground": "dec_facts", "assumption": "dec_assumptions"}
    for item in items:
        table = tables.get(item.kind, "dec_stakes")
        if item.row.get("added_in_edition") is None:
            set_once(table, int(item.row["id"]), added_in_edition=n)
    update_head(
        "dec_decisions",
        decision_id,
        int(row["version"]),
        current_edition=n,
        completion_pending=0,
    )
    run.emit(
        "coflow.dec.edition.sealed",
        subject=str(row["public_id"]),
        entity="edition",
        changed=["current_edition"],
    )
    if reason == "source_changed":
        run.sealed_source_changed.append(str(row["public_id"]))
        run.findings.append(
            f"{row['public_id']}: the basis changed in {run.issuer}; sealed "
            f"{codes.render_scoped(str(row['public_id']), 'E', n)} (source_changed)"
        )
    return n
