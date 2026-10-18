"""``import_snapshot``: validate, plan and apply a ``coflow.import.decisions`` v1 snapshot (spec
§6.5).

Owned by track S (store, import, shadow); increment I1, spec §12.2 (AT-S1...S8, AT-K9). The
signature is fixed by ``dec.api``; the track implements it.

The order of checks is the spec's: the file hash (the same file twice is a no-op); the JSON Schema
``coflow/contracts/import_decisions_v1.schema.json`` (an unknown field or a float is
``IMPORT_FORMAT_UNSUPPORTED``); the ``content_hash`` (``IMPORT_HASH_MISMATCH``); the instance role
(``IMPORT_NOT_SYNTHETIC`` in ``dev`` for a snapshot without ``"synthetic": true``, ``IMPORT_ROLE``
outside ``dev`` and ``validation``); the id space (``IMPORT_SOURCE_CONFLICT`` when
``highest_issued`` reaches the native block); adopted records (``IMPORT_ADOPTED``). Then one unit of
work per snapshot (chunked only above ``dec.import_unit_max_rows``), and the shadow report after
commit (``shadow/compare.py``).

How a run moves (``dec_import_runs.status``):

- **one unit** (the usual case): the run row is inserted ``applied`` in the unit that applies the
  whole snapshot, so it exists only if everything was applied. A fault rolls everything back and a
  separate unit records the run as ``failed`` with the error; the same file may be imported again.
- **chunks** (more planned rows than ``dec.import_unit_max_rows``, split by decision): the first
  chunk inserts the run as ``partial`` with ``report_status = 'blocked'``; the last chunk sets it
  ``applied``. A fault in a later chunk leaves the run ``partial`` (the shadow report refuses to
  run on it), and importing the same file again resumes it: the content hashes skip what was
  applied, the remaining chunks complete it, and the report is written.

Spec notes:

- A refused import writes nothing, not even a run row, so the same file can be imported once the
  cause is fixed; the run status ``refused`` is reserved.
- ``dry_run`` validates and plans, and returns the planned counts without writing a run row.
  ``final`` behaves like ``shadow`` (the adoption procedure, §6.10, marks the last run with it).
- Semantic rules the schema cannot express are format errors (``IMPORT_FORMAT_UNSUPPORTED``):
  ``v1_ref`` must be ``D<v1_id>``; ids are unique; ``decider_mapping = 'other'`` needs kind
  ``advisee`` or ``forecast_container``; the issuer must be one of ``ids.foreign_issuers``.
- The snapshot's ``v1_computed`` block, its declared counts and its decision ids are kept with the
  run (``source_computed_json``), so ``shadow_report`` can recompute a report from the database.
- **Snapshots are applied in order** (found in review: an older file imported after a newer one
  voided rows "before" they were recorded). A snapshot whose ``as_of`` is earlier than that of an
  applied or partial run of the same issuer is ``IMPORT_SOURCE_CONFLICT``; one with the same
  ``as_of`` is accepted only when it was exported later (a re-export of the same instant). A
  partial run is resumed by its own file only while no later run has written; after that it stays
  partial, and ``shadow_report`` lists it as superseded.
- **Zones.** The importer reads the source's dates in ``source.timezone`` and computes in the
  owner's zone; when the two differ the run carries a finding, and the shadow report a coverage
  note, because v1's day and v2's day can then differ near midnight.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from coflow.contracts import load_schema
from coflow.kernel.config.profile import load_profile
from coflow.kernel.config.settings import load_settings
from coflow.kernel.context import CommandContext, CommandResult, format_instant, parse_instant
from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.ids import codes
from coflow.kernel.ids.registry import prefix_spec
from coflow.kernel.ops.instance import load_instance
from coflow.kernel.store.api import insert, read_connection, unit_of_work, update_mutable
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.domain.model import (
    DecConfig,
    DecEnv,
    EntityCounts,
    ImportMode,
    ImportReport,
)
from coflow.modules.dec.importer import apply
from coflow.modules.dec.shadow import compare
from coflow.modules.dec.store import mirror, repo
from coflow.modules.dec.store.mirror import MirrorState

__all__ = ["ENTITIES", "ImportPlan", "build_plan", "import_snapshot", "parse_snapshot"]

FORMAT = "coflow.import.decisions"
FORMAT_VERSION = 1
SCHEMA_NAME = f"{FORMAT}/{FORMAT_VERSION}"
ENTITIES: tuple[str, ...] = ("decisions", "assumptions", "facts", "reviews", "links", "versions")
_CHILD_KINDS: Mapping[str, str] = {
    "assumptions": "assumption",
    "facts": "fact",
    "reviews": "review",
    "links": "link",
}


def _refuse(code: RefusalCode, detail: str) -> Refused:
    return Refused(code, detail)


# ==================================================================================================
# Reading and validating


def _no_float(text: str) -> Any:
    raise Refused(
        RefusalCode.IMPORT_FORMAT_UNSUPPORTED,
        f"the number {text} has a fraction or an exponent: CFJ-1 refuses floats",
    )


def _no_constant(text: str) -> Any:
    raise Refused(RefusalCode.IMPORT_FORMAT_UNSUPPORTED, f"{text} is not JSON")


def parse_snapshot(raw: bytes) -> dict[str, Any]:
    """Parse, validate against the schema and check the content hash and the semantic rules."""
    try:
        doc = json.loads(raw.decode("utf-8"), parse_float=_no_float, parse_constant=_no_constant)
    except UnicodeDecodeError as exc:
        raise _refuse(RefusalCode.IMPORT_FORMAT_UNSUPPORTED, "the file is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise _refuse(
            RefusalCode.IMPORT_FORMAT_UNSUPPORTED, f"not JSON: {exc.msg} at line {exc.lineno}"
        ) from exc
    if not isinstance(doc, dict):
        raise _refuse(RefusalCode.IMPORT_FORMAT_UNSUPPORTED, "the snapshot is not a JSON object")
    if doc.get("format") != FORMAT or doc.get("format_version") != FORMAT_VERSION:
        raise _refuse(
            RefusalCode.IMPORT_FORMAT_UNSUPPORTED,
            f"format {doc.get('format')!r} version {doc.get('format_version')!r}; "
            f"this importer reads {FORMAT} version {FORMAT_VERSION}",
        )
    validator = jsonschema.Draft202012Validator(load_schema(SCHEMA_NAME))
    error = jsonschema.exceptions.best_match(validator.iter_errors(doc))
    if error is not None:
        where = "/".join(str(p) for p in error.absolute_path) or "(root)"
        raise _refuse(RefusalCode.IMPORT_FORMAT_UNSUPPORTED, f"{where}: {error.message}")
    _check_semantics(doc)
    body = {k: v for k, v in doc.items() if k != "content_hash"}
    expected = "sha256:" + cfj.sha256_hex(cfj.cfj(body))
    if doc["content_hash"] != expected:
        raise _refuse(
            RefusalCode.IMPORT_HASH_MISMATCH,
            "content_hash does not match the CFJ-1 form of the document; the file was changed "
            "after export or was not written by a conforming exporter",
        )
    return doc


def _check_semantics(doc: Mapping[str, Any]) -> None:
    bad = RefusalCode.IMPORT_FORMAT_UNSUPPORTED
    seen: dict[str, set[int]] = {"decision": set(), "assumption": set(), "fact": set()}
    seen.update(review=set(), version=set())
    for d in doc["decisions"]:
        if d["v1_ref"] != f"D{d['v1_id']}":
            raise _refuse(
                bad, f"decision {d['v1_id']}: v1_ref {d['v1_ref']!r} is not D{d['v1_id']}"
            )
        if d["decider_mapping"] == "other" and d["kind"] not in ("advisee", "forecast_container"):
            raise _refuse(
                bad,
                f"decision {d['v1_id']}: decider 'other' is allowed only for kinds advisee and "
                "forecast_container",
            )
        for kind, rows in (
            ("decision", [d]),
            ("assumption", d["assumptions"]),
            ("fact", d["facts"]),
            ("review", d["reviews"]),
            ("version", d["versions"]),
        ):
            for row in rows:
                if row["v1_id"] in seen[kind]:
                    raise _refuse(bad, f"{kind} {row['v1_id']} appears twice")
                seen[kind].add(row["v1_id"])
        own = {a["v1_id"] for a in d["assumptions"]}
        for v in d["versions"]:
            if v["entity"] == "decision" and v["entity_v1_id"] != d["v1_id"]:
                raise _refuse(bad, f"version {v['v1_id']} names another decision")
            if v["entity"] == "assumption" and v["entity_v1_id"] not in own:
                raise _refuse(bad, f"version {v['v1_id']} names an assumption of another decision")
        codes_seen: set[str] = set()
        for a in d["assumptions"]:
            code = a.get("code")
            if code is not None and code in codes_seen:
                raise _refuse(bad, f"decision {d['v1_id']}: assumption code {code} appears twice")
            if code is not None:
                codes_seen.add(code)
            if code is not None and int(code[1:]) > 99:
                raise _refuse(bad, f"decision {d['v1_id']}: assumption code {code} exceeds A99")


# ==================================================================================================
# The plan (reads only, before any unit of work)


@dataclass(slots=True)
class _DecisionPlan:
    src: Mapping[str, Any]
    status: str  # new | changed | unchanged | adopted
    rows: int


@dataclass(slots=True)
class ImportPlan:
    """What a snapshot changes against the mirror state, computed before any write (AP-4)."""

    decisions: list[_DecisionPlan]
    absent: list[MirrorState]
    counts: dict[str, EntityCounts]
    states: dict[tuple[str, str], MirrorState]
    touched_adopted: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return sum(p.rows for p in self.decisions) + len(self.absent)

    def chunks(self, max_rows: int) -> list[tuple[list[_DecisionPlan], list[MirrorState]]]:
        """One chunk when the plan fits the bound, else whole decisions per chunk (§6.5); the
        tombstones go with the last chunk."""
        applicable = [p for p in self.decisions if p.status != "adopted"]
        if self.row_count <= max_rows:
            return [(applicable, list(self.absent))]
        out: list[list[_DecisionPlan]] = [[]]
        size = 0
        for p in applicable:
            if out[-1] and size + p.rows > max_rows:
                out.append([])
                size = 0
            out[-1].append(p)
            size += p.rows
        chunks = [(c, []) for c in out]
        chunks[-1] = (chunks[-1][0], list(self.absent))
        return chunks


def _owner_index(conn: Any, issuer: str) -> dict[tuple[str, str], int]:
    """(source kind, source id) -> the local decision id of every mirrored child row."""
    index: dict[tuple[str, str], int] = {}
    for kind, table in (
        ("assumption", "dec_assumptions"),
        ("fact", "dec_facts"),
        ("review", "dec_reviews"),
        ("link", "dec_links"),
    ):
        for row in conn.execute(
            f"SELECT ms.source_id, t.decision_id FROM dec_mirror_state ms JOIN {table} t "
            "ON ms.local_table = ? AND ms.local_id = t.id "
            "WHERE ms.issuer = ? AND ms.source_kind = ? AND ms.absent_since_run_id IS NULL",
            (table, issuer, kind),
        ):
            index[(kind, str(row[0]))] = int(row[1])
    return index


def _child_keys(src: Mapping[str, Any], entity: str) -> list[tuple[str, Mapping[str, Any]]]:
    if entity == "links":
        return [(f"{src['v1_id']}:{x['kind']}:{x['ref']}", x) for x in src["links"]]
    return [(str(x["v1_id"]), x) for x in src[entity]]


def build_plan(
    doc: Mapping[str, Any],
    states: Mapping[tuple[str, str], MirrorState],
    owners: Mapping[tuple[str, str], int],
) -> ImportPlan:
    """Diff the snapshot against ``dec_mirror_state`` by content hash."""
    tallies = {
        e: {"seen": 0, "new": 0, "changed": 0, "unchanged": 0, "absent": 0} for e in ENTITIES
    }
    plans: list[_DecisionPlan] = []
    adopted: list[str] = []
    present: set[str] = set()
    children_of: dict[tuple[str, int], set[str]] = {}
    for (child_kind, child_key), owner in owners.items():
        children_of.setdefault((child_kind, owner), set()).add(child_key)
    for src in sorted(doc["decisions"], key=lambda d: d["v1_id"]):
        key = str(src["v1_id"])
        present.add(key)
        state = states.get(("decision", key))
        changed = state is None or state.content_hash != apply.content_hash(
            {k: v for k, v in src.items() if k not in apply.CHILD_KEYS}
        )
        local = state.local_id if state is not None else None
        for entity, kind in _CHILD_KINDS.items():
            keys = _child_keys(src, entity)
            tallies[entity]["seen"] += len(keys)
            seen_keys = set()
            for child_key, child in keys:
                seen_keys.add(child_key)
                child_state = states.get((kind, child_key))
                if child_state is None:
                    tallies[entity]["new"] += 1
                    changed = True
                elif (
                    child_state.content_hash != apply.content_hash(child)
                    or child_state.absent_since_run_id is not None  # deleted, now back
                ):
                    tallies[entity]["changed"] += 1
                    changed = True
                else:
                    tallies[entity]["unchanged"] += 1
            if local is not None:
                gone = children_of.get((kind, local), set()) - seen_keys
                tallies[entity]["absent"] += len(gone)
                changed = changed or bool(gone)
        new_versions = [v for v in src["versions"] if ("version", str(v["v1_id"])) not in states]
        tallies["versions"]["seen"] += len(src["versions"])
        tallies["versions"]["new"] += len(new_versions)
        tallies["versions"]["unchanged"] += len(src["versions"]) - len(new_versions)
        changed = changed or bool(new_versions)
        tallies["decisions"]["seen"] += 1
        if state is None:
            status = "new"
        elif state.adopted_at is not None:
            status = "adopted"
            if changed:
                adopted.append(codes.render("D", int(src["v1_id"])))
        elif changed or state.absent_since_run_id is not None:
            status = "changed"
        else:
            status = "unchanged"
        tallies["decisions"][status if status != "adopted" else "unchanged"] += 1
        plans.append(_DecisionPlan(src=src, status=status, rows=apply.decision_rows_estimate(src)))
    absent = [
        st
        for (kind, key), st in states.items()
        if kind == "decision"
        and key not in present
        and st.absent_since_run_id is None
        and st.adopted_at is None
    ]
    tallies["decisions"]["absent"] = len(absent)
    counts = {e: EntityCounts(**t) for e, t in tallies.items()}
    return ImportPlan(
        decisions=plans,
        absent=sorted(absent, key=lambda s: int(s.source_id)),
        counts=counts,
        states=dict(states),
        touched_adopted=adopted,
    )


def _counts_json(counts: Mapping[str, EntityCounts]) -> str:
    return cfj.cfj(
        {
            e: {
                "seen": c.seen,
                "new": c.new,
                "changed": c.changed,
                "unchanged": c.unchanged,
                "absent": c.absent,
            }
            for e, c in counts.items()
        }
    ).decode("utf-8")


def counts_from_json(text: str | None) -> dict[str, EntityCounts]:
    if not text:
        return {}
    raw = json.loads(text)
    return {e: EntityCounts(**v) for e, v in raw.items() if isinstance(v, dict)}


# ==================================================================================================
# The command


def _prepare(file: Path) -> tuple[bytes, str, Any]:
    raw = Path(file).read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    with read_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM dec_import_runs WHERE file_hash = ?", (file_hash,)
        ).fetchone()
    return raw, file_hash, existing


def _report(
    *,
    run_id: int | None,
    status: str,
    mode: str,
    file_hash: str,
    doc_or_row: Mapping[str, Any],
    counts: Mapping[str, EntityCounts],
    absent: Sequence[str] = (),
    findings: Sequence[str] = (),
    report_status: str = "pending",
    noop: bool = False,
) -> ImportReport:
    """The run report from the snapshot document, or from a stored ``dec_import_runs`` row."""
    data = dict(doc_or_row)  # a sqlite3.Row's ``in`` tests values, a dict's tests keys

    def instant(key: str) -> Any:
        value = data.get(key)
        return parse_instant(value) if value else None

    issuer = data["source_issuer"] if "source_issuer" in data else data["source"]["issuer"]
    return ImportReport(
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        file_hash=file_hash,
        source_issuer=issuer,
        synthetic=bool(data["synthetic"]),
        exported_at=instant("exported_at"),
        as_of=instant("as_of"),
        as_of_date=repo.opt_date(data.get("as_of_date")),
        counts=dict(counts),
        absent=tuple(absent),
        findings=tuple(findings),
        report_status=report_status,  # type: ignore[arg-type]
        noop=noop,
    )


def import_snapshot(
    env: DecEnv, file: Path, *, mode: ImportMode = "shadow", ctx: CommandContext
) -> CommandResult[ImportReport]:
    raw, file_hash, existing = _prepare(file)
    if existing is not None and existing["status"] in ("applied", "noop"):
        report = _report(
            run_id=existing["id"],
            status="noop",
            mode=existing["mode"],
            file_hash=file_hash,
            doc_or_row=existing,
            counts=counts_from_json(existing["counts_json"]),
            report_status=existing["report_status"],
            noop=True,
        )
        return CommandResult(value=report, tx=None)

    doc = parse_snapshot(raw)
    with read_connection() as conn:
        instance = load_instance(conn)
        profile = load_profile(conn)
        cfg = DecConfig.from_settings(load_settings(conn), timezone=profile.timezone)
    issuer = doc["source"]["issuer"]
    if instance.role == "dev" and doc["synthetic"] is not True:
        raise _refuse(
            RefusalCode.IMPORT_NOT_SYNTHETIC,
            'a dev instance accepts only snapshots marked "synthetic": true; import real '
            "snapshots into a validation instance whose data root lies outside any repository",
        )
    if instance.role not in ("dev", "validation"):
        raise _refuse(
            RefusalCode.IMPORT_ROLE,
            f"snapshots are imported into a validation instance (or a dev instance for synthetic "
            f"files); this instance is {instance.role}",
        )
    if issuer not in cfg.foreign_issuers:
        raise _refuse(
            RefusalCode.IMPORT_FORMAT_UNSUPPORTED,
            f"issuer {issuer} is not one of the configured foreign issuers "
            f"({', '.join(cfg.foreign_issuers)})",
        )
    block = prefix_spec("D").block_start or 0
    id_space = doc["id_space"]["decision"]
    numbers = [d["v1_id"] for d in doc["decisions"]] + list(id_space["deleted_without_trace"])
    if block and (id_space["highest_issued"] >= block or any(n >= block for n in numbers)):
        raise _refuse(
            RefusalCode.IMPORT_SOURCE_CONFLICT,
            f"the source issues decision numbers up to {id_space['highest_issued']}; numbers from "
            f"{block} are the instance's own block",
        )
    with read_connection() as conn:
        states = mirror.load_mirror_states(conn, issuer)
        owners = _owner_index(conn, issuer)
        mirrored_ids = {st.local_id for (k, _), st in states.items() if k == "decision"}
        clash = []
        for d in doc["decisions"]:
            row = conn.execute(
                "SELECT id FROM dec_decisions WHERE number = ?", (d["v1_id"],)
            ).fetchone()
            if row is not None and row[0] not in mirrored_ids:
                clash.append(codes.render("D", d["v1_id"]))
    if clash:
        raise _refuse(
            RefusalCode.IMPORT_SOURCE_CONFLICT,
            f"{', '.join(clash)} already exist here and are not mirrors of {issuer}",
        )
    _check_order(doc, issuer, existing)
    plan = build_plan(doc, states, owners)
    if plan.touched_adopted:
        raise _refuse(
            RefusalCode.IMPORT_ADOPTED,
            f"{', '.join(plan.touched_adopted)} were adopted: v2 is their system of record now",
        )
    if mode == "dry_run":
        report = _report(
            run_id=None,
            status="noop",
            mode=mode,
            file_hash=file_hash,
            doc_or_row=doc,
            counts=plan.counts,
            absent=[codes.render("D", int(s.source_id)) for s in plan.absent],
            noop=True,
        )
        return CommandResult(value=report, tx=None)
    return _apply_plan(env, doc, plan, file_hash, mode, existing, cfg, profile.timezone, ctx)


def zone_note(source_tz: str, owner_tz: str) -> str:
    """The warning for a source whose zone is not the owner's (see the module's spec note)."""
    return (
        f"the source's zone {source_tz} is not the owner's zone {owner_tz}: v1's and v2's day can "
        "differ near midnight; set the owner's zone to the source's during the shadow period"
    )


def _check_order(doc: Mapping[str, Any], issuer: str, existing: Any) -> None:
    """Refuse a snapshot older than what the issuer's runs already applied (see the spec note).

    Every applied or partial run of the issuer wrote rows known from its ``as_of``; applying an
    older snapshot on top would void and version rows back in time, and voids and editions are
    set once. The one exception is resuming the same partial run, while no later run wrote."""
    with read_connection() as conn:
        runs = conn.execute(
            "SELECT id, file_hash, as_of, exported_at, status FROM dec_import_runs "
            "WHERE source_issuer = ? AND status IN ('applied', 'partial') ORDER BY id",
            (issuer,),
        ).fetchall()
    if existing is not None and existing["status"] == "partial":
        later = [r for r in runs if r["id"] > existing["id"]]
        if later:
            r = later[-1]
            raise _refuse(
                RefusalCode.IMPORT_SOURCE_CONFLICT,
                f"run {existing['id']} cannot be resumed: run {r['id']} (as_of {r['as_of']}) was "
                "imported after it; import a newer snapshot instead",
            )
        return
    written = [r for r in runs if r["as_of"]]
    if not written:
        return
    newest = max(written, key=lambda r: (parse_instant(r["as_of"]), r["id"]))
    as_of = parse_instant(doc["as_of"])
    newest_as_of = parse_instant(newest["as_of"])
    exported = parse_instant(doc["exported_at"])
    newest_exported = (
        parse_instant(newest["exported_at"]) if newest["exported_at"] else newest_as_of
    )
    if as_of < newest_as_of or (as_of == newest_as_of and exported <= newest_exported):
        raise _refuse(
            RefusalCode.IMPORT_SOURCE_CONFLICT,
            f"snapshot as_of {format_instant(as_of)} is older than run {newest['id']} "
            f"(as_of {newest['as_of']}); snapshots of {issuer} are imported in order",
        )


def _stored_instant(text: str) -> str:
    return format_instant(parse_instant(text))


def _source_computed(doc: Mapping[str, Any]) -> str:
    return cfj.cfj(
        {
            "v1_computed": doc["v1_computed"],
            "counts": doc["counts"],
            "decisions": sorted(d["v1_id"] for d in doc["decisions"]),
            "source_timezone": doc["source"]["timezone"],
        }
    ).decode("utf-8")


def _apply_plan(
    env: DecEnv,
    doc: Mapping[str, Any],
    plan: ImportPlan,
    file_hash: str,
    mode: str,
    existing: Any,
    cfg: DecConfig,
    owner_tz: str,
    ctx: CommandContext,
) -> CommandResult[ImportReport]:
    issuer = doc["source"]["issuer"]
    # the file hash is the import's idempotency; its several units carry no command key
    ictx = ctx.with_actor(f"import_{issuer.lower()}", channel="import").with_idempotency_key(None)
    chunks = plan.chunks(cfg.import_unit_max_rows)
    pre_existing: int | None = existing["id"] if existing is not None else None
    run_id: int | None = pre_existing
    keep_counts = existing is not None and existing["status"] == "partial"
    counts_json = existing["counts_json"] if keep_counts else _counts_json(plan.counts)
    sessions = {s["ref"]: s for s in doc["context"]["sessions"]}
    event_ids: list[str] = []
    findings: list[str] = []
    if doc["source"]["timezone"] != owner_tz:
        findings.append(zone_note(doc["source"]["timezone"], owner_tz))
    absent_refs: list[str] = []
    committed = 0
    last_tx: int | None = None
    try:
        for i, (decisions, tombstones) in enumerate(chunks):
            last = i == len(chunks) - 1
            status = "applied" if last else "partial"
            report_status = "pending" if last else "blocked"
            with unit_of_work("dec", ictx, command="import_snapshot") as uow:
                if run_id is None:
                    run_id = insert(
                        "dec_import_runs",
                        {
                            "source_issuer": issuer,
                            "format": FORMAT,
                            "format_version": FORMAT_VERSION,
                            "synthetic": 1 if doc["synthetic"] else 0,
                            "file_hash": file_hash,
                            "exported_at": _stored_instant(doc["exported_at"]),
                            "as_of": _stored_instant(doc["as_of"]),
                            "as_of_date": doc["as_of_date"],
                            "mode": mode,
                            "status": status,
                            "counts_json": counts_json,
                            "report_status": report_status,
                            "source_computed_json": _source_computed(doc),
                        },
                    )
                elif i == 0 or last:
                    update_mutable(
                        "dec_import_runs",
                        {"id": run_id},
                        status=status,
                        report_status=report_status,
                        counts_json=counts_json,
                        error=None,
                        source_computed_json=_source_computed(doc),
                    )
                run = apply.RunContext(
                    run_id=run_id,
                    issuer=issuer,
                    as_of=parse_instant(doc["as_of"]),
                    timezone=owner_tz,
                    source_timezone=doc["source"]["timezone"],
                    sessions=sessions,
                    states=plan.states,
                )
                if i == 0:
                    apply.register_numbers(doc, issuer=issuer)
                    apply.upsert_foreign_context(doc["context"], run)
                for p in decisions:
                    apply.apply_decision(p.src, run)
                for state in tombstones:
                    ref = apply.mark_decision_absent(state, run)
                    if ref is not None:
                        absent_refs.append(ref)
                if last:
                    run.emit(
                        "coflow.dec.import.completed",
                        subject=f"{issuer}_run-{run_id}",
                        entity="import_run",
                        changed=[],
                    )
                last_tx = uow.tx
            committed += 1
            event_ids += run.event_ids
            findings += run.findings
    except Exception as exc:
        durable = pre_existing if pre_existing is not None else (run_id if committed else None)
        resumable = committed > 0 or (existing is not None and existing["status"] == "partial")
        _record_failure(doc, file_hash, mode, counts_json, durable, resumable, exc, ictx)
        raise
    assert run_id is not None
    shadow = compare.write_shadow_report(env, run_id, ctx=ictx)
    report = _report(
        run_id=run_id,
        status="applied",
        mode=mode,
        file_hash=file_hash,
        doc_or_row=doc,
        counts=counts_from_json(counts_json),
        absent=absent_refs,
        findings=findings,
        report_status=shadow.report_status,
    )
    return CommandResult(value=report, tx=last_tx, event_ids=tuple(event_ids))


def _record_failure(
    doc: Mapping[str, Any],
    file_hash: str,
    mode: str,
    counts_json: str,
    run_id: int | None,
    resumable: bool,
    exc: Exception,
    ctx: CommandContext,
) -> None:
    """Record a run that did not complete: ``failed`` when nothing of it was applied, else it stays
    ``partial`` (resumable by importing the same file again). The error keeps its type and
    message; the caller re-raises the original exception either way."""
    error = f"{type(exc).__name__}: {exc}"[:500]
    try:
        with unit_of_work("dec", ctx, command="import_snapshot"):
            if run_id is None:
                insert(
                    "dec_import_runs",
                    {
                        "source_issuer": doc["source"]["issuer"],
                        "format": FORMAT,
                        "format_version": FORMAT_VERSION,
                        "synthetic": 1 if doc["synthetic"] else 0,
                        "file_hash": file_hash,
                        "exported_at": _stored_instant(doc["exported_at"]),
                        "as_of": _stored_instant(doc["as_of"]),
                        "as_of_date": doc["as_of_date"],
                        "mode": mode,
                        "status": "failed",
                        "counts_json": counts_json,
                        "report_status": "blocked",
                        "error": error,
                        "source_computed_json": _source_computed(doc),
                    },
                )
            else:
                update_mutable(
                    "dec_import_runs",
                    {"id": run_id},
                    status="partial" if resumable else "failed",
                    report_status="blocked",
                    error=error,
                )
    except Exception:  # the original error matters more than this bookkeeping
        return
