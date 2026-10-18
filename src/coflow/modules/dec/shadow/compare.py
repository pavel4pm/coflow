"""The shadow report: v1's own computed output against v2's (spec §6.6).

Owned by track S (store, import, shadow); increment I1, spec §12.2 (AT-S5, AT-S6). ``shadow_report``
is fixed by ``dec.api`` and ``write_shadow_report`` by the importer; the track implements both.

v2's values come from track D's queries at the snapshot's ``as_of`` / ``as_of_date`` on the
knowledge axis (``queries.waiting(env, today=as_of_date, as_of=as_of)``, ``queries.health``,
``queries.assumption_due``), so the shadow compares exactly what the CLI and MCP show. The
comparison runs after the import commits, from read connections; one small unit then stores
``dec_shadow_items`` and ``dec_import_runs.v2_output_json`` (a record, never read back as an
answer). A ``partial`` run is ``blocked``.

What is compared, for the decisions the snapshot held (§6.6):

- ``due``: every assumption of an active decision that v1 computed a due date for, as
  ``(date, source)`` with v1's ``next_check`` read as ``explicit``; must be ``same``;
- ``waiting_membership`` and ``waiting_reasons``: v1's waiting list against v2's decision items;
  an extra v2 reason is ``expected`` under SR-7 to SR-10, a v2-only item under the rule of its
  first reason when every reason has one; anything v1 lists and v2 does not is ``unexpected``. A
  v1 reason without a date (v1 never dates ``violated``) matches v2's reason of the same kind and
  assumption on kind and assumption alone (``_as_v1_states``; integration spec note: found by
  importing the v1 exporter's output, whose ``violated`` reasons carry ``due: null``);
- ``order``: the relative order of the items both lists hold with identical reasons; must be
  ``same``;
- ``health``: v1's label against v2's label, mapped (§6.6), ``same`` or ``expected`` under SR-1 to
  SR-8;
- ``count``: the snapshot's declared counts against the mirrored rows v2 holds for its decisions;
  must be equal;
- ``basis_drift``: a ``source_changed`` edition sealed by this run, a ``finding``.

Spec notes:

- Run-level items (``count``) use ``decision_ref = '*'``; their ``subject_ref`` is the entity.
- The rule facts (status, review date, manual flag) are the head replayed to the snapshot's
  ``as_of`` from its versions (``store/versions.py``), so a report recomputed after later runs
  compares the same head.
- ``runs_since_last_unexpected`` counts consecutive written reports of the run's issuer, ending at
  this run, with no unexpected line (§6.6 shadow readiness).
- Found in review: health, due dates and the waiting list are evaluated at one ``T`` (the run's
  ``as_of`` and ``as_of_date``); ``v2_output_json.input_hash`` covers the effective ``DecConfig``
  and the algorithm version, not only the free-standing ``dec.config_version`` setting.
- ``shadow_report()`` without a run reads the issuer's latest run whatever its status, so a newer
  partial or failed import shows as ``blocked`` instead of an older clean report. A partial run
  that a later snapshot overtook stays ``partial`` (the status set has no "superseded"); the later
  runs' reports list it in their coverage. A source zone unlike the owner's is a coverage note.
"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from coflow.kernel.config.profile import load_profile
from coflow.kernel.config.settings import load_settings
from coflow.kernel.context import Answer, CommandContext, parse_instant
from coflow.kernel.errors import NotFound
from coflow.kernel.ids import codes
from coflow.kernel.ops.instance import load_instance
from coflow.kernel.ports.decision_directory import Reason, WaitingItem
from coflow.kernel.store.api import insert, read_connection, unit_of_work, update_mutable
from coflow.modules.dec import queries
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.domain.model import (
    DecConfig,
    DecEnv,
    DecisionView,
    ImportRunView,
    ShadowItem,
    ShadowReport,
)
from coflow.modules.dec.shadow import rules
from coflow.modules.dec.store import repo, versions

__all__ = ["ALGORITHM_VERSION", "compute_shadow", "shadow_report", "write_shadow_report"]

ALGORITHM_VERSION = "1"
ASPECT_ORDER = {
    "count": 0,
    "health": 1,
    "due": 2,
    "waiting_membership": 3,
    "waiting_reasons": 4,
    "order": 5,
    "basis_drift": 6,
}
CLASSES = ("same", "expected", "unexpected", "finding")
COUNTED = ("decisions", "assumptions", "facts", "reviews", "links", "versions")
RUN_LEVEL = "*"


# ==================================================================================================
# Small helpers


def _iso(value: date | None) -> str:
    return value.isoformat() if value else "-"


def _reason_key(kind: str, due: date | None, code: str | None) -> tuple[str, str, str]:
    return (kind, _iso(due), code or "")


def _reason_text(key: tuple[str, str, str]) -> str:
    kind, due, code = key
    return " ".join(p for p in (kind, due, code) if p)


def _known_at(v: Any) -> datetime:
    return v.origin_recorded_at or v.recorded_at


@dataclass(slots=True)
class _Items:
    rows: list[ShadowItem]

    def add(
        self,
        decision_ref: str,
        aspect: str,
        classification: str,
        *,
        subject_ref: str | None = None,
        v1: str | None = None,
        v2: str | None = None,
        rule_id: str | None = None,
    ) -> None:
        self.rows.append(
            ShadowItem(
                decision_ref=decision_ref,
                aspect=aspect,  # type: ignore[arg-type]
                subject_ref=subject_ref,
                v1_value=v1,
                v2_value=v2,
                classification=classification,  # type: ignore[arg-type]
                rule_id=rule_id,
            )
        )

    def sorted(self) -> tuple[ShadowItem, ...]:
        return tuple(
            sorted(
                self.rows,
                key=lambda i: (
                    i.decision_ref,
                    ASPECT_ORDER[i.aspect],
                    i.subject_ref or "",
                    i.v1_value or "",
                    i.v2_value or "",
                ),
            )
        )


# ==================================================================================================
# The comparison (reads only)


@dataclass(slots=True)
class _Context:
    run: ImportRunView
    source: Mapping[str, Any]
    cfg: DecConfig
    views: dict[str, DecisionView]  # replayed to the run's as_of
    assumption_refs: dict[str, str]  # v1 assumption id -> D-0907_A-01
    held_counts: dict[str, int]
    drift: list[tuple[str, str]]  # (decision ref, edition ref)


def _load_context(run: ImportRunView) -> _Context:
    with read_connection() as conn:
        row = conn.execute(
            "SELECT source_computed_json FROM dec_import_runs WHERE id = ?", (run.id,)
        ).fetchone()
        source = json.loads(row["source_computed_json"] or "{}") if row else {}
        profile = load_profile(conn)
        cfg = DecConfig.from_settings(load_settings(conn), timezone=profile.timezone)
        refs = [codes.render("D", int(n)) for n in source.get("decisions", [])]
        loaded = repo.load_decisions(conn, refs=refs)
        assumption_refs: dict[str, str] = {}
        for r in conn.execute(
            "SELECT ms.source_id AS source_id, d.public_id AS public_id, a.code_n AS code_n, "
            "a.id AS id FROM dec_mirror_state ms "
            "JOIN dec_assumptions a ON ms.local_table = 'dec_assumptions' AND ms.local_id = a.id "
            "JOIN dec_decisions d ON a.decision_id = d.id "
            "WHERE ms.issuer = ? AND ms.source_kind = 'assumption'",
            (run.source_issuer,),
        ):
            source_id = str(r["source_id"])
            row = _row_known_at(conn, run, source_id) or r
            assumption_refs[source_id] = codes.render_scoped(
                row["public_id"], "A", int(row["code_n"])
            )
        held = _held_counts(conn, run.source_issuer, [v.id for v in loaded])
        drift = [
            (str(r["public_id"]), codes.render_scoped(str(r["public_id"]), "E", int(r["n"])))
            for r in conn.execute(
                "SELECT d.public_id AS public_id, e.n AS n FROM dec_editions e "
                "JOIN dec_decisions d ON e.decision_id = d.id "
                "WHERE e.reason = 'source_changed' AND e.reason_text = ? ORDER BY d.number, e.n",
                (f"import run {run.id}",),
            )
        ]
    as_of = run.as_of
    views: dict[str, DecisionView] = {}
    for view in loaded:
        if as_of is not None:
            hidden = [v for v in view.versions if _known_at(v) > as_of]
            view = versions.replay_decision(view, hidden)
        views[view.public_id] = view
    return _Context(
        run=run,
        source=source,
        cfg=cfg,
        views=views,
        assumption_refs=assumption_refs,
        held_counts=held,
        drift=drift,
    )


def _row_known_at(conn: Any, run: ImportRunView, source_id: str) -> Any:
    """The local row of a source assumption as known at the run's ``as_of``: a later run may have
    replaced it with a successor (same ``origin_ref``) that the run's own report never saw."""
    if run.as_of is None:
        return None
    rows = conn.execute(
        "SELECT d.public_id AS public_id, a.code_n AS code_n, a.id AS id, "
        "coalesce(a.origin_recorded_at, a.recorded_at) AS k, d.mirror_of AS mirror_of "
        "FROM dec_assumptions a JOIN dec_decisions d ON a.decision_id = d.id "
        "WHERE a.origin_ref = ?",
        (codes.foreign_ref(run.source_issuer, source_id),),
    ).fetchall()
    prefix = f"{run.source_issuer}_"
    known = [
        r
        for r in rows
        if str(r["mirror_of"] or "").startswith(prefix) and parse_instant(r["k"]) <= run.as_of
    ]
    return max(known, key=lambda r: (parse_instant(r["k"]), r["id"])) if known else None


def _held_counts(conn: Any, issuer: str, decision_ids: Sequence[int]) -> dict[str, int]:
    """The mirrored rows v2 holds for the run's decisions, per entity of the snapshot's counts."""
    held = {"decisions": len(decision_ids)}
    if not decision_ids:
        return dict.fromkeys(COUNTED, 0)
    marks = ",".join("?" for _ in decision_ids)
    live = {
        "assumptions": ("assumption", "dec_assumptions", "t.status = 'active'"),
        "facts": ("fact", "dec_facts", "t.voided_at IS NULL"),
        "reviews": ("review", "dec_reviews", "t.voided_at IS NULL"),
        "links": ("link", "dec_links", "t.removed_tx IS NULL"),
    }
    for entity, (kind, table, condition) in live.items():
        held[entity] = int(
            conn.execute(
                f"SELECT count(*) FROM dec_mirror_state ms JOIN {table} t "
                "ON ms.local_table = ? AND ms.local_id = t.id "
                f"WHERE ms.issuer = ? AND ms.source_kind = ? AND ms.absent_since_run_id IS NULL "
                f"AND {condition} AND t.decision_id IN ({marks})",
                (table, issuer, kind, *decision_ids),
            ).fetchone()[0]
        )
    via_versions = conn.execute(
        "SELECT count(*) FROM dec_mirror_state ms JOIN dec_versions v "
        "ON ms.local_table = 'dec_versions' AND ms.local_id = v.id "
        f"WHERE ms.issuer = ? AND ms.source_kind = 'version' AND ("
        f"(v.entity = 'decision' AND v.entity_id IN ({marks})) OR (v.entity = 'assumption' AND "
        f"v.entity_id IN (SELECT id FROM dec_assumptions WHERE decision_id IN ({marks}))))",
        (issuer, *decision_ids, *decision_ids),
    ).fetchone()[0]
    via_checks = conn.execute(
        "SELECT count(*) FROM dec_mirror_state ms JOIN dec_checks c "
        "ON ms.local_table = 'dec_checks' AND ms.local_id = c.id "
        f"WHERE ms.issuer = ? AND ms.source_kind = 'version' AND c.decision_id IN ({marks})",
        (issuer, *decision_ids),
    ).fetchone()[0]
    held["versions"] = int(via_versions) + int(via_checks)
    return held


def _facts(view: DecisionView, health: Any, cfg: DecConfig) -> rules.RuleFacts:
    return rules.RuleFacts(
        health=health,
        status=view.status,
        is_mirror=view.mirror_of is not None,
        review_due=view.review_due,
        manual_flag=view.manual_flag,
        share_limit=cfg.unverifiable_share_limit,
    )


def input_hash(run: ImportRunView, cfg: DecConfig) -> str:
    """What a report was computed from: the file, its ``as_of``, every value of the effective
    configuration (``DecConfig``, decimals as text) and the algorithm version."""
    return cfj.sha256_hex(
        cfj.cfj(
            {
                "file_hash": run.file_hash,
                "as_of": run.stored.get("as_of"),
                "config": dataclasses.asdict(cfg),
                "algorithm_version": ALGORITHM_VERSION,
            }
        )
    )


def compute_shadow(
    env: DecEnv, run: ImportRunView
) -> tuple[tuple[ShadowItem, ...], dict[str, object]]:
    """Every compared item of a fully applied run, and the record of what v2 computed."""
    ctx = _load_context(run)
    items = _Items(rows=[])
    as_of, as_of_date = run.as_of, run.as_of_date
    v1 = ctx.source.get("v1_computed", {})
    active = {ref for ref, view in ctx.views.items() if view.status == "active"}
    output: dict[str, object] = {
        "algorithm_version": ALGORITHM_VERSION,
        "input_hash": input_hash(run, ctx.cfg),
        "as_of": run.stored.get("as_of"),
        "as_of_date": _iso(as_of_date),
    }

    # counts -------------------------------------------------------------------------------------
    declared = ctx.source.get("counts", {})
    for entity in COUNTED:
        want, have = declared.get(entity), ctx.held_counts.get(entity, 0)
        items.add(
            RUN_LEVEL,
            "count",
            "same" if want == have else "unexpected",
            subject_ref=entity,
            v1=str(want),
            v2=str(have),
        )

    # health -------------------------------------------------------------------------------------
    healths: dict[str, Any] = {}
    facts: dict[str, rules.RuleFacts] = {}
    for ref, view in ctx.views.items():
        try:
            h = queries.health(env, ref, as_of=as_of, today=as_of_date).value
        except NotFound:  # not known at the snapshot's as_of: an exporter's record time is wrong
            items.add(ref, "health", "unexpected", v1="known", v2="not known at as_of")
            continue
        healths[ref] = h
        facts[ref] = _facts(view, h, ctx.cfg)
    output["health"] = {
        ref: {
            "label": h.label,
            "ground": h.ground,
            "timeliness": sorted(h.timeliness),
            "share": None if h.share is None else format(h.share, "f"),
        }
        for ref, h in sorted(healths.items())
    }
    for key, entry in sorted(v1.get("health", {}).items(), key=lambda kv: int(kv[0])):
        ref = codes.render("D", int(key))
        if ref not in healths:
            continue
        cls, rule = rules.classify_health(entry["label"], facts[ref])
        items.add(ref, "health", cls, v1=entry["label"], v2=healths[ref].label, rule_id=rule)

    # due dates ----------------------------------------------------------------------------------
    dues: dict[str, list[str | None]] = {}
    for key, entry in sorted(v1.get("assumption_due", {}).items(), key=lambda kv: int(kv[0])):
        aref = ctx.assumption_refs.get(str(key))
        if aref is None:
            continue
        dref = aref.split("_")[0]
        if dref not in active or dref not in healths:
            continue
        due = queries.assumption_due(env, aref, at=as_of, today=as_of_date).value.due
        v2_pair = (_iso(due.due), due.source or "-")
        source = "explicit" if entry.get("source") == "next_check" else entry.get("source")
        v1_pair = (entry.get("due") or "-", source or "-")
        dues[aref] = [due.due.isoformat() if due.due else None, due.source]
        items.add(
            dref,
            "due",
            "same" if v1_pair == v2_pair else "unexpected",
            subject_ref=aref,
            v1=" ".join(v1_pair),
            v2=" ".join(v2_pair),
        )
    output["due"] = dues

    # the waiting list ---------------------------------------------------------------------------
    v2_items: list[WaitingItem] = [
        i
        for i in queries.waiting(env, today=as_of_date, as_of=as_of).value
        if i.subject_kind == "decision" and i.ref in ctx.views
    ]
    output["waiting"] = [
        {"ref": i.ref, "reasons": [list(_reason_key(r.kind, r.due, r.code)) for r in i.reasons]}
        for i in v2_items
    ]
    _compare_waiting(ctx, v1.get("waiting", []), v2_items, facts, items)

    # basis drift --------------------------------------------------------------------------------
    for dref, eref in ctx.drift:
        items.add(dref, "basis_drift", "finding", subject_ref=eref, v2="source_changed")
    return items.sorted(), output


def _v1_reasons(
    entry: Mapping[str, Any], assumption_refs: Mapping[str, str]
) -> list[tuple[str, str, str]]:
    out = []
    for r in entry.get("reasons", []):
        code = None
        if r.get("assumption_v1_id") is not None:
            aref = assumption_refs.get(str(r["assumption_v1_id"]))
            code = aref.split("_", 1)[1] if aref else f"v1:{r['assumption_v1_id']}"
        due = date.fromisoformat(r["due"]) if r.get("due") else None
        out.append(_reason_key(r["kind"], due, code))
    return out


def _as_v1_states(
    v2_pairs: Sequence[tuple[tuple[str, str, str], Reason]], v1_count: Counter[tuple[str, str, str]]
) -> list[tuple[tuple[str, str, str], Reason]]:
    """v2's reason keys, with the date dropped where v1 lists the same reason without one.

    v1 dates no ``violated`` reason (its waiting list states only that the assumption is
    violated), while v2 dates it by the violation's observation (§3.8). A v1 reason whose ``due``
    is null therefore matches v2's reason of the same kind and assumption whatever v2's date: there
    is no v1 date to compare (§6.6 compares the due dates v1 states).
    """
    exact = Counter(v1_count)
    dateless = Counter({k: n for k, n in v1_count.items() if k[1] == "-"})
    out: list[tuple[tuple[str, str, str], Reason]] = []
    for key, reason in v2_pairs:
        if exact[key] > 0:
            exact[key] -= 1
            out.append((key, reason))
            continue
        bare = (key[0], "-", key[2])
        if key[1] != "-" and dateless[bare] > 0 and exact[bare] > 0:
            dateless[bare] -= 1
            exact[bare] -= 1
            out.append((bare, reason))
            continue
        out.append((key, reason))
    return out


def _compare_waiting(
    ctx: _Context,
    v1_list: Sequence[Mapping[str, Any]],
    v2_items: Sequence[WaitingItem],
    facts: Mapping[str, rules.RuleFacts],
    items: _Items,
) -> None:
    v1_by_ref: dict[str, list[tuple[str, str, str]]] = {}
    v1_order: list[str] = []
    for entry in v1_list:
        ref = codes.render("D", int(entry["v1_id"]))
        if ref not in ctx.views:
            continue
        v1_by_ref[ref] = _v1_reasons(entry, ctx.assumption_refs)
        v1_order.append(ref)
    v2_by_ref: dict[str, list[Reason]] = {i.ref: list(i.reasons) for i in v2_items}
    v2_order = [i.ref for i in v2_items]

    identical: set[str] = set()
    for ref in sorted(set(v1_by_ref) | set(v2_by_ref)):
        v1_keys = v1_by_ref.get(ref)
        v2_reasons = v2_by_ref.get(ref)
        fact = facts.get(ref)
        if v1_keys is not None and v2_reasons is not None:
            items.add(ref, "waiting_membership", "same", v1="listed", v2="listed")
        elif v2_reasons is not None:
            explained = [rules.classify_extra_reason(r, fact) if fact else None for r in v2_reasons]
            if all(explained):
                items.add(
                    ref,
                    "waiting_membership",
                    "expected",
                    v1="absent",
                    v2="listed",
                    rule_id=explained[0],
                )
            else:
                items.add(ref, "waiting_membership", "unexpected", v1="absent", v2="listed")
        else:
            items.add(ref, "waiting_membership", "unexpected", v1="listed", v2="absent")

        v1_count = Counter(v1_keys or [])
        v2_pairs = _as_v1_states(
            [(_reason_key(r.kind, r.due, r.code), r) for r in v2_reasons or []], v1_count
        )
        v2_count = Counter(k for k, _ in v2_pairs)
        if v1_keys is not None and v2_reasons is not None and v1_count == v2_count:
            identical.add(ref)
            text = "; ".join(_reason_text(k) for k in sorted(v1_count.elements()))
            items.add(ref, "waiting_reasons", "same", v1=text, v2=text)
            continue
        remaining = Counter(v1_count)
        for key, reason in v2_pairs:
            if remaining[key] > 0:
                remaining[key] -= 1
                continue
            rule = rules.classify_extra_reason(reason, fact) if fact else None
            items.add(
                ref,
                "waiting_reasons",
                "expected" if rule else "unexpected",
                subject_ref=reason.code,
                v1=None,
                v2=_reason_text(key),
                rule_id=rule,
            )
        missing = v1_count - v2_count
        for key in sorted(missing.elements()):
            items.add(
                ref,
                "waiting_reasons",
                "unexpected",
                subject_ref=key[2] or None,
                v1=_reason_text(key),
                v2=None,
            )

    common_v1 = [r for r in v1_order if r in identical]
    common_v2 = [r for r in v2_order if r in identical]
    for ref in sorted(identical):
        p1, p2 = common_v1.index(ref) + 1, common_v2.index(ref) + 1
        items.add(ref, "order", "same" if p1 == p2 else "unexpected", v1=str(p1), v2=str(p2))


# ==================================================================================================
# Storing and reading reports


def _build_report(
    run: ImportRunView,
    report_status: str,
    items: Iterable[ShadowItem],
    runs_since: int | None,
) -> ShadowReport:
    items = tuple(items)
    totals = Counter(i.classification for i in items)
    by_rule = Counter(i.rule_id for i in items if i.classification == "expected" and i.rule_id)
    return ShadowReport(
        run_id=run.id,
        as_of_date=run.as_of_date,
        report_status=report_status,  # type: ignore[arg-type]
        totals={c: totals.get(c, 0) for c in CLASSES},
        by_rule={r: by_rule[r] for r in rules.RULE_IDS if by_rule.get(r)},
        unexpected=tuple(i for i in items if i.classification == "unexpected"),
        findings=tuple(i for i in items if i.classification == "finding"),
        items=items,
        runs_since_last_unexpected=runs_since,
    )


def _stored_items(conn: Any, run_id: int) -> tuple[ShadowItem, ...]:
    rows = conn.execute(
        "SELECT * FROM dec_shadow_items WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    return tuple(
        ShadowItem(
            decision_ref=r["decision_ref"],
            aspect=r["aspect"],
            subject_ref=r["subject_ref"],
            v1_value=r["v1_value"],
            v2_value=r["v2_value"],
            classification=r["classification"],
            rule_id=r["rule_id"],
        )
        for r in rows
    )


def _runs_since_last_unexpected(conn: Any, run: ImportRunView, unexpected_now: int) -> int:
    """Consecutive written reports of the run's issuer, ending at this run, with no unexpected
    line; 0 when this run has one."""
    if unexpected_now:
        return 0
    count = 1
    for r in conn.execute(
        "SELECT r.id AS id, (SELECT count(*) FROM dec_shadow_items s WHERE s.run_id = r.id "
        "AND s.classification = 'unexpected') AS unexpected FROM dec_import_runs r "
        "WHERE r.source_issuer = ? AND r.report_status = 'written' AND r.id < ? "
        "ORDER BY r.id DESC",
        (run.source_issuer, run.id),
    ):
        if r["unexpected"]:
            break
        count += 1
    return count


def write_shadow_report(env: DecEnv, run_id: int, *, ctx: CommandContext) -> ShadowReport:
    """Compute and store the report of a fully applied run (called by the importer after commit)."""
    with read_connection() as conn:
        run = repo.load_import_run(conn, run_id)
        if run is None:
            raise NotFound(f"import run {run_id}")
        if run.report_status == "written":
            stored = _stored_items(conn, run_id)
            unexpected = sum(i.classification == "unexpected" for i in stored)
            since = _runs_since_last_unexpected(conn, run, unexpected)
            return _build_report(run, "written", stored, since)
    if run.status != "applied":
        if run.report_status != "blocked":
            with unit_of_work("dec", ctx, command="write_shadow_report"):
                update_mutable("dec_import_runs", {"id": run_id}, report_status="blocked")
        return _build_report(run, "blocked", (), None)
    items, output = compute_shadow(env, run)
    with unit_of_work("dec", ctx, command="write_shadow_report"):
        for item in items:
            insert(
                "dec_shadow_items",
                {
                    "run_id": run_id,
                    "decision_ref": item.decision_ref,
                    "aspect": item.aspect,
                    "subject_ref": item.subject_ref,
                    "v1_value": item.v1_value,
                    "v2_value": item.v2_value,
                    "classification": item.classification,
                    "rule_id": item.rule_id,
                },
            )
        update_mutable(
            "dec_import_runs",
            {"id": run_id},
            v2_output_json=cfj.cfj(output).decode("utf-8"),
            report_status="written",
        )
    unexpected = sum(i.classification == "unexpected" for i in items)
    with read_connection() as conn:
        since = _runs_since_last_unexpected(conn, run, unexpected)
    return _build_report(run, "written", items, since)


def _coverage_notes(conn: Any, run: ImportRunView) -> list[str]:
    """The zone and overtaken-partial-run notes of a report (see the module's spec notes)."""
    notes: list[str] = []
    row = conn.execute(
        "SELECT source_computed_json FROM dec_import_runs WHERE id = ?", (run.id,)
    ).fetchone()
    source = json.loads(row["source_computed_json"] or "{}") if row else {}
    source_tz = source.get("source_timezone")
    owner_tz = load_profile(conn).timezone
    if source_tz and source_tz != owner_tz:
        notes.append(
            f"the source's zone {source_tz} is not the owner's zone {owner_tz}: days near "
            "midnight can differ from v1's"
        )
    overtaken = [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM dec_import_runs WHERE source_issuer = ? AND status = 'partial' "
            "AND id < ? ORDER BY id",
            (run.source_issuer, run.id),
        )
    ]
    if overtaken and run.status == "applied":
        runs = ", ".join(str(n) for n in overtaken)
        notes.append(
            f"run{'s' if len(overtaken) > 1 else ''} {runs} stayed partial: a newer snapshot was "
            "imported instead, and their applied chunks are part of this state"
        )
    return notes


def shadow_report(env: DecEnv, *, run_id: int | None = None) -> Answer[ShadowReport]:
    """The report of run ``run_id`` (default: the issuer's latest run, whatever its status: a
    newer partial or failed run is ``blocked``), recomputed from reads when it was never stored
    (``coflow dec shadow --run N``)."""
    with read_connection() as conn:
        run = repo.load_import_run(conn, run_id, any_status=True)
        role = load_instance(conn).role
        if run is None:
            raise NotFound(f"import run {run_id}" if run_id is not None else "an import run")
        stored = _stored_items(conn, run.id) if run.report_status == "written" else ()
        coverage = [
            "computed on the knowledge axis at the snapshot's as_of",
            f"mirrored from {run.source_issuer}; the report stays in this instance's data root",
            *_coverage_notes(conn, run),
        ]
        if run.report_status == "written":
            unexpected = sum(i.classification == "unexpected" for i in stored)
            since = _runs_since_last_unexpected(conn, run, unexpected)
            report = _build_report(run, "written", stored, since)
    if run.report_status != "written":
        if run.status != "applied":
            report = _build_report(run, "blocked", (), None)
            coverage.append(
                f"run {run.id} is {run.status}: import the same file again to finish it, or a "
                "newer snapshot"
            )
        else:
            items, _ = compute_shadow(env, run)
            unexpected = sum(i.classification == "unexpected" for i in items)
            with read_connection() as conn:
                since = _runs_since_last_unexpected(conn, run, unexpected)
            report = _build_report(run, "pending", items, since)
            coverage.append("recomputed from the database; not stored")
    as_of = run.as_of or run.recorded_at
    return Answer(value=report, instance_role=role, as_of=as_of, coverage=tuple(coverage))
