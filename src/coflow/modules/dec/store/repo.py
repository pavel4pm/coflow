"""Loading DEC rows into the frozen views of ``domain/model.py``.

Owned by track S (store, import, shadow); increment I1, spec §12.2. The loaders below are fixed by
the skeleton because track D's ``queries.py`` reads through them; the track implements them.

Rules: a loader returns **every** row of a decision (voided rows, removed links, later versions
included; visibility at ``T`` is track D's filter); children are ordered by code (assumptions by
``position``, checks by observed time then K); ``stored`` carries the row as SQLite returned it;
``code`` and ``ref`` are rendered with ``kernel.ids.codes``. ``ref`` arguments are canonical public
ids (callers resolve user input with ``kernel.ids.aliases.resolve`` first).

Spec notes:

- Event times are converted by precision (``model.py``): ``instant`` to an aware UTC datetime,
  ``day`` to a date (the first ten characters), ``month`` to the first day of that month,
  ``unknown`` to ``None``.
- Tables without origin columns (forks, proposals, editions, import runs, fact bearings) get
  ``origin_recorded_at = origin_ref = None``, so ``K(row)`` is their ``recorded_at``.
- ``DecisionView.absent_since_run_id`` and ``adopted_at`` come from ``dec_mirror_state`` by the
  local row (``local_table = 'dec_decisions'``), so they survive adoption, which clears
  ``mirror_of``.
- A proposal's ``title`` is its payload's ``title``, else ``statement``, else ``question``, else
  ``"proposal <id>"``.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from coflow.kernel.context import parse_instant
from coflow.kernel.ids import codes
from coflow.modules.dec.domain.model import (
    AssumptionView,
    CheckView,
    DecisionView,
    EditionView,
    EventAt,
    FactBearing,
    FactView,
    ForkView,
    ImportRunView,
    LearningView,
    LinkView,
    OptionView,
    OutcomeView,
    ProposalView,
    ReadingView,
    ReviewView,
    StakeView,
    VersionView,
)

__all__ = [
    "assumption_from_row",
    "decision_head_fields",
    "event_at",
    "import_run_view",
    "link_from_row",
    "load_assumption",
    "load_decision",
    "load_decisions",
    "load_forks",
    "load_import_run",
    "load_proposals",
    "observed_sort_key",
    "opt_bool",
    "opt_date",
    "opt_instant",
]

Row = Mapping[str, Any]

_CHUNK = 500  # ids per IN (...) list, well below SQLite's parameter limit


# ==================================================================================================
# Stored value conversions (shared with versions.py)


def opt_date(value: object) -> date | None:
    """A stored ``YYYY-MM-DD`` (or a longer text whose first ten characters are one) as a date."""
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)[:10])


def opt_instant(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return parse_instant(str(value))


def opt_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def event_at(value: object, precision: object) -> EventAt:
    """The typed value of an event-time column by its precision (see the module docstring)."""
    if value is None or value == "" or precision == "unknown":
        return None
    text = str(value)
    if precision == "instant":
        return parse_instant(text)
    if precision == "month":
        return date(int(text[0:4]), int(text[5:7]), 1)
    return date.fromisoformat(text[:10])


def _stamp(row: Row) -> dict[str, Any]:
    keys = row.keys() if hasattr(row, "keys") else row
    has_origin = "origin_recorded_at" in keys
    return {
        "tx": row["tx"],
        "recorded_at": parse_instant(row["recorded_at"]),
        "origin_recorded_at": opt_instant(row["origin_recorded_at"]) if has_origin else None,
        "origin_ref": row["origin_ref"] if "origin_ref" in keys else None,
        "stored": dict(row),
    }


# ==================================================================================================
# Row to view


def _option(row: Row, parent_ref: str) -> OptionView:
    return OptionView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        fork_id=row["fork_id"],
        code_n=row["code_n"],
        code=codes.render("O", row["code_n"]),
        ref=codes.render_scoped(parent_ref, "O", row["code_n"]),
        text=row["text"],
        chosen=opt_bool(row["chosen"]),
        why_rejected=row["why_rejected"],
        recorded_before_choice=row["recorded_before_choice"],
        added_in_edition=row["added_in_edition"],
        origin=row["origin"],
        salt=row["salt"],
        erased_tx=row["erased_tx"],
    )


def _check(row: Row, assumption_ref: str) -> CheckView:
    return CheckView(
        **_stamp(row),
        id=row["id"],
        assumption_id=row["assumption_id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("CK", row["code_n"]),
        ref=codes.render_scoped(assumption_ref, "CK", row["code_n"]),
        kind=row["kind"],
        state=row["state"],
        reading_id=row["reading_id"],
        observed_value=row["observed_value"],
        observed_text=row["observed_text"],
        observed_at=event_at(row["observed_at"], row["observed_precision"]),
        observed_precision=row["observed_precision"],
        observed_basis=row["observed_basis"],
        due_answered=opt_date(row["due_answered"]),
        due_source_answered=row["due_source_answered"],
        next_check_set=opt_date(row["next_check_set"]),
        next_check_rule=row["next_check_rule"],
        evidence_kind=row["evidence_kind"],
        evidence_ref=row["evidence_ref"],
        evidence_quote=row["evidence_quote"],
        quote_verified=opt_bool(row["quote_verified"]),
        note=row["note"],
        proposed_by=row["proposed_by"],
        reconstructed=bool(row["reconstructed"]),
        voided_at=opt_instant(row["voided_at"]),
        voided_reason=row["voided_reason"],
        erased_tx=row["erased_tx"],
    )


def _reading(row: Row, assumption_ref: str) -> ReadingView:
    return ReadingView(
        **_stamp(row),
        id=row["id"],
        assumption_id=row["assumption_id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("RD", row["code_n"]),
        ref=codes.render_scoped(assumption_ref, "RD", row["code_n"]),
        value=row["value"],
        unit=row["unit"],
        value_text=row["value_text"],
        observed_at=event_at(row["observed_at"], row["observed_precision"]),
        observed_precision=row["observed_precision"],
        observed_basis=row["observed_basis"],
        source_kind=row["source_kind"],
        source_ref=row["source_ref"],
        quote=row["quote"],
        proposed_state=row["proposed_state"],
        no_proposal_reason=row["no_proposal_reason"],
        proposed_by=row["proposed_by"],
        accepted_by_check_id=row["accepted_by_check_id"],
        voided_at=opt_instant(row["voided_at"]),
        voided_reason=row["voided_reason"],
    )


def observed_sort_key(row: Row) -> tuple[str, str, int]:
    """Checks and readings in observed order, then K, then id (§3.4 ``latest_assessment``).

    A stored date sorts before every instant of the same day, which matches "a check observed on
    a day, at an unknown time"; an unknown observed time sorts at its knowledge time.
    """
    known = row["origin_recorded_at"] or row["recorded_at"]
    observed = row["observed_at"] if row["observed_precision"] != "unknown" else None
    return (str(observed or known), str(known), int(row["id"]))


def _assumption(
    row: Row, decision_ref: str, checks: Sequence[Row], readings: Sequence[Row]
) -> AssumptionView:
    ref = codes.render_scoped(decision_ref, "A", row["code_n"])
    return AssumptionView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("A", row["code_n"]),
        ref=ref,
        position=row["position"],
        statement=row["statement"],
        metric=row["metric"],
        comparator=row["comparator"],
        threshold_value=row["threshold_value"],
        threshold_value2=row["threshold_value2"],
        unit=row["unit"],
        threshold_text=row["threshold_text"],
        by_date=opt_date(row["by_date"]),
        judge_from=opt_date(row["judge_from"]),
        drift_margin=row["drift_margin"],
        data_source_kind=row["data_source_kind"],
        data_source_text=row["data_source_text"],
        data_source_ref=row["data_source_ref"],
        check_frequency=row["check_frequency"],
        next_check_at=opt_date(row["next_check_at"]),
        is_critical=bool(row["is_critical"]),
        scope=row["scope"],
        check_cost=row["check_cost"],
        class_tag=row["class_tag"],
        probability=row["probability"],
        probability_by=row["probability_by"],
        probability_recorded_at=opt_instant(row["probability_recorded_at"]),
        shareable=bool(row["shareable"]),
        status=row["status"],
        superseded_by=row["superseded_by"],
        drop_reason=row["drop_reason"],
        added_in_edition=row["added_in_edition"],
        salt=row["salt"],
        version=row["version"],
        erased_tx=row["erased_tx"],
        checks=tuple(_check(c, ref) for c in sorted(checks, key=observed_sort_key)),
        readings=tuple(_reading(r, ref) for r in sorted(readings, key=observed_sort_key)),
    )


def _fact(row: Row, decision_ref: str, bearings: Sequence[Row]) -> FactView:
    return FactView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("FT", row["code_n"]),
        ref=codes.render_scoped(decision_ref, "FT", row["code_n"]),
        phase=row["phase"],
        kind=row["kind"],
        claimed_outcome=row["claimed_outcome"],
        text=row["text"],
        occurred_at=event_at(row["occurred_at"], row["occurred_precision"]),
        occurred_precision=row["occurred_precision"],
        occurred_basis=row["occurred_basis"],
        evidence_kind=row["evidence_kind"],
        evidence_ref=row["evidence_ref"],
        evidence_quote=row["evidence_quote"],
        quote_verified=opt_bool(row["quote_verified"]),
        source_text=row["source_text"],
        reported_by=row["reported_by"],
        added_in_edition=row["added_in_edition"],
        corrects_fact_id=row["corrects_fact_id"],
        salt=row["salt"],
        reconstructed=bool(row["reconstructed"]),
        bearings=tuple(
            FactBearing(assumption_id=b["assumption_id"], bearing=b["bearing"])
            for b in sorted(bearings, key=lambda b: b["assumption_id"])
        ),
        voided_at=opt_instant(row["voided_at"]),
        voided_reason=row["voided_reason"],
        erased_tx=row["erased_tx"],
    )


def _review(row: Row, decision_ref: str) -> ReviewView:
    return ReviewView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("R", row["code_n"]),
        ref=codes.render_scoped(decision_ref, "R", row["code_n"]),
        action=row["action"],
        verdict=row["verdict"],
        notes=row["notes"],
        revise_basis=row["revise_basis"],
        trigger=row["trigger"],
        trigger_ref=row["trigger_ref"],
        trigger_at=_trigger_at(row["trigger_at"]),
        occurred_at=event_at(row["occurred_at"], row["occurred_precision"]),
        occurred_precision=row["occurred_precision"],
        occurred_basis=row["occurred_basis"],
        next_review_due=opt_date(row["next_review_due"]),
        status_before=row["status_before"],
        review_due_before=opt_date(row["review_due_before"]),
        edition_before=row["edition_before"],
        edition_after=row["edition_after"],
        health_before=row["health_before"],
        ground_before=row["ground_before"],
        timeliness_before=row["timeliness_before"],
        unverifiable_before=row["unverifiable_before"],
        unverifiable_after=row["unverifiable_after"],
        reasons_answered_json=row["reasons_answered_json"],
        execution_summary_json=row["execution_summary_json"],
        successor_ref=row["successor_ref"],
        is_correction=bool(row["is_correction"]),
        legacy_health_at_review=row["legacy_health_at_review"],
        reconstructed=bool(row["reconstructed"]),
        voided_at=opt_instant(row["voided_at"]),
        voided_reason=row["voided_reason"],
        erased_tx=row["erased_tx"],
    )


def _trigger_at(value: object) -> EventAt:
    """``trigger_at`` has no precision column: an instant when it has a time, else a date."""
    if value is None or value == "":
        return None
    text = str(value)
    return parse_instant(text) if "T" in text else date.fromisoformat(text[:10])


def _outcome(row: Row) -> OutcomeView:
    return OutcomeView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        review_id=row["review_id"],
        kind=row["kind"],
        basis=row["basis"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"] or "[]")),
        measured_value=row["measured_value"],
        expected_vs_actual=row["expected_vs_actual"],
        occurred_at=event_at(row["occurred_at"], row["occurred_precision"]),
        occurred_precision=row["occurred_precision"],
        occurred_basis=row["occurred_basis"],
        resolved_by=row["resolved_by"],
        supersedes_outcome_id=row["supersedes_outcome_id"],
        reconstructed=bool(row["reconstructed"]),
    )


def _learning(row: Row, decision_ref: str) -> LearningView:
    return LearningView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        code_n=row["code_n"],
        code=codes.render("L", row["code_n"]),
        ref=codes.render_scoped(decision_ref, "L", row["code_n"]),
        edition=row["edition"],
        review_id=row["review_id"],
        outcome_id=row["outcome_id"],
        confirmed=row["confirmed"],
        refuted=row["refuted"],
        limits=row["limits"],
        next_step=row["next_step"],
        same_again=row["same_again"],
        legacy_text=row["legacy_text"],
        salt=row["salt"],
        reconstructed=bool(row["reconstructed"]),
        erased_tx=row["erased_tx"],
    )


def _stake(row: Row) -> StakeView:
    return StakeView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        type=row["type"],
        amount=row["amount"],
        currency=row["currency"],
        period=row["period"],
        count_periods=row["count_periods"],
        direction=row["direction"],
        note=row["note"],
        planned=bool(row["planned"]),
        added_in_edition=row["added_in_edition"],
        salt=row["salt"],
    )


def _link(row: Row) -> LinkView:
    return LinkView(
        **_stamp(row),
        id=row["id"],
        decision_id=row["decision_id"],
        role=row["role"],
        target_ref=row["target_ref"],
        target_kind=row["target_kind"],
        resolution=row["resolution"],
        note=row["note"],
        removed_tx=row["removed_tx"],
        removed_reason=row["removed_reason"],
    )


def _edition(row: Row, decision_ref: str) -> EditionView:
    return EditionView(
        **_stamp(row),
        decision_id=row["decision_id"],
        n=row["n"],
        code=codes.render("E", row["n"]),
        ref=codes.render_scoped(decision_ref, "E", row["n"]),
        reason=row["reason"],
        fields_json=row["fields_json"],
        field_salts_json=row["field_salts_json"],
        field_hashes_json=row["field_hashes_json"],
        items_json=row["items_json"],
        seal_hash=row["seal_hash"],
        canon_version=row["canon_version"],
        sealed_at=parse_instant(row["sealed_at"]),
        sealed_by=row["sealed_by"],
        review_id=row["review_id"],
        reason_text=row["reason_text"],
        unverifiable_at_seal=row["unverifiable_at_seal"],
        reconstructed=bool(row["reconstructed"]),
        erased_fields_json=row["erased_fields_json"],
        erased_tx=row["erased_tx"],
    )


def _version(row: Row) -> VersionView:
    return VersionView(
        **_stamp(row),
        id=row["id"],
        entity=row["entity"],
        entity_id=row["entity_id"],
        field=row["field"],
        old_value=row["old_value"],
        new_value=row["new_value"],
        reason=row["reason"],
        cause_kind=row["cause_kind"],
        cause_ref=row["cause_ref"],
        reconstructed=bool(row["reconstructed"]),
    )


def decision_head_fields(row: Row) -> dict[str, Any]:
    """The typed head fields of a ``dec_decisions`` row (no children, no mirror bookkeeping)."""
    return {
        **_stamp(row),
        "id": row["id"],
        "public_id": row["public_id"],
        "number": row["number"],
        "title": row["title"],
        "question": row["question"],
        "statement": row["statement"],
        "kind": row["kind"],
        "decider": row["decider"],
        "decider_basis": row["decider_basis"],
        "decider_ref": row["decider_ref"],
        "depth": row["depth"],
        "depth_basis": row["depth_basis"],
        "reversibility": row["reversibility"],
        "status": row["status"],
        "manual_flag": row["manual_flag"],
        "manual_flag_reason": row["manual_flag_reason"],
        "context": row["context"],
        "known": row["known"],
        "would_help": row["would_help"],
        "unknowns": tuple(json.loads(row["unknowns_json"] or "[]")),
        "success_criterion": row["success_criterion"],
        "expected_metric": row["expected_metric"],
        "expected_target": row["expected_target"],
        "expected_unit": row["expected_unit"],
        "expected_by": opt_date(row["expected_by"]),
        "expected_text": row["expected_text"],
        "confidence": row["confidence"],
        "not_doing": row["not_doing"],
        "review_due": opt_date(row["review_due"]),
        "review_due_initial": opt_date(row["review_due_initial"]),
        "decided_at": event_at(row["decided_at"], row["decided_precision"]),
        "decided_precision": row["decided_precision"],
        "decided_basis": row["decided_basis"],
        "activated_at": opt_instant(row["activated_at"]),
        "closed_at": opt_instant(row["closed_at"]),
        "current_edition": row["current_edition"],
        "completion_pending": bool(row["completion_pending"]),
        "origin_kind": row["origin_kind"],
        "origin_quote": row["origin_quote"],
        "publishability": row["publishability"],
        "third_party_sensitive": bool(row["third_party_sensitive"]),
        "reconstructed": bool(row["reconstructed"]),
        "mirror_of": row["mirror_of"],
        "mirror_scope": row["mirror_scope"],
        "notes": row["notes"],
        "legacy_json": row["legacy_json"],
        "version": row["version"],
        "erased_tx": row["erased_tx"],
    }


def assumption_from_row(row: Row, decision_ref: str) -> AssumptionView:
    """An ``AssumptionView`` from a stored row, without its checks and readings."""
    return _assumption(row, decision_ref, [], [])


def link_from_row(row: Row) -> LinkView:
    return _link(row)


# ==================================================================================================
# Batch loading


def _in_chunks(
    conn: sqlite3.Connection, sql: str, ids: Sequence[int], extra: Sequence[object] = ()
) -> list[sqlite3.Row]:
    """Run ``sql`` (with one ``{ids}`` placeholder list) over ``ids`` in chunks."""
    out: list[sqlite3.Row] = []
    for start in range(0, len(ids), _CHUNK):
        part = list(ids[start : start + _CHUNK])
        marks = ",".join("?" for _ in part)
        out.extend(conn.execute(sql.format(ids=marks), [*part, *extra]).fetchall())
    return out


def _group(rows: Iterable[Row], key: str) -> dict[int, list[Row]]:
    groups: dict[int, list[Row]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


def _assemble(conn: sqlite3.Connection, heads: Sequence[Row]) -> list[DecisionView]:
    if not heads:
        return []
    ids = [h["id"] for h in heads]

    def by_decision(table: str) -> dict[int, list[Row]]:
        sql = f"SELECT * FROM {table} WHERE decision_id IN ({{ids}})"
        return _group(_in_chunks(conn, sql, ids), "decision_id")

    options = by_decision("dec_options")
    assumptions = by_decision("dec_assumptions")
    checks = by_decision("dec_checks")
    readings = by_decision("dec_readings")
    facts = by_decision("dec_facts")
    reviews = by_decision("dec_reviews")
    outcomes = by_decision("dec_outcomes")
    learnings = by_decision("dec_learnings")
    stakes = by_decision("dec_stakes")
    links = by_decision("dec_links")
    editions = by_decision("dec_editions")

    fact_ids = [f["id"] for rows in facts.values() for f in rows]
    bearings = _group(
        _in_chunks(conn, "SELECT * FROM dec_fact_assumptions WHERE fact_id IN ({ids})", fact_ids),
        "fact_id",
    )
    assumption_ids = [a["id"] for rows in assumptions.values() for a in rows]
    link_ids = [x["id"] for rows in links.values() for x in rows]
    version_rows = _in_chunks(
        conn, "SELECT * FROM dec_versions WHERE entity = 'decision' AND entity_id IN ({ids})", ids
    )
    version_rows += _in_chunks(
        conn,
        "SELECT * FROM dec_versions WHERE entity = 'assumption' AND entity_id IN ({ids})",
        assumption_ids,
    )
    version_rows += _in_chunks(
        conn, "SELECT * FROM dec_versions WHERE entity = 'link' AND entity_id IN ({ids})", link_ids
    )
    owner_of_assumption = {a["id"]: a["decision_id"] for rows in assumptions.values() for a in rows}
    owner_of_link = {x["id"]: x["decision_id"] for rows in links.values() for x in rows}
    versions: dict[int, list[Row]] = defaultdict(list)
    for v in version_rows:
        if v["entity"] == "decision":
            versions[v["entity_id"]].append(v)
        elif v["entity"] == "assumption":
            versions[owner_of_assumption[v["entity_id"]]].append(v)
        else:
            versions[owner_of_link[v["entity_id"]]].append(v)

    mirror = {
        m["local_id"]: m
        for m in _in_chunks(
            conn,
            "SELECT local_id, absent_since_run_id, adopted_at FROM dec_mirror_state "
            "WHERE local_table = 'dec_decisions' AND local_id IN ({ids})",
            ids,
        )
    }

    views = []
    for head in heads:
        did, ref = head["id"], head["public_id"]
        checks_of = _group(checks.get(did, []), "assumption_id")
        readings_of = _group(readings.get(did, []), "assumption_id")
        m = mirror.get(did)
        views.append(
            DecisionView(
                **decision_head_fields(head),
                absent_since_run_id=m["absent_since_run_id"] if m else None,
                adopted_at=opt_instant(m["adopted_at"]) if m else None,
                options=tuple(
                    _option(o, ref) for o in sorted(options.get(did, []), key=lambda o: o["code_n"])
                ),
                assumptions=tuple(
                    _assumption(a, ref, checks_of.get(a["id"], []), readings_of.get(a["id"], []))
                    for a in sorted(
                        assumptions.get(did, []), key=lambda a: (a["position"], a["code_n"])
                    )
                ),
                facts=tuple(
                    _fact(f, ref, bearings.get(f["id"], []))
                    for f in sorted(facts.get(did, []), key=lambda f: f["code_n"])
                ),
                reviews=tuple(
                    _review(r, ref) for r in sorted(reviews.get(did, []), key=lambda r: r["code_n"])
                ),
                outcomes=tuple(
                    _outcome(o) for o in sorted(outcomes.get(did, []), key=lambda o: o["id"])
                ),
                learnings=tuple(
                    _learning(x, ref)
                    for x in sorted(learnings.get(did, []), key=lambda x: x["code_n"])
                ),
                stakes=tuple(_stake(s) for s in sorted(stakes.get(did, []), key=lambda s: s["id"])),
                links=tuple(_link(x) for x in sorted(links.get(did, []), key=lambda x: x["id"])),
                editions=tuple(
                    _edition(e, ref) for e in sorted(editions.get(did, []), key=lambda e: e["n"])
                ),
                versions=tuple(
                    _version(v) for v in sorted(versions.get(did, []), key=lambda v: v["id"])
                ),
            )
        )
    return views


# ==================================================================================================
# The loaders


def load_decision(conn: sqlite3.Connection, ref: str) -> DecisionView | None:
    """The decision ``ref`` (``D-0907``) with every child row, or ``None``."""
    head = conn.execute("SELECT * FROM dec_decisions WHERE public_id = ?", (ref,)).fetchone()
    if head is None:
        return None
    return _assemble(conn, [head])[0]


def load_decisions(
    conn: sqlite3.Connection,
    *,
    statuses: Collection[str] | None = None,
    kinds: Collection[str] | None = None,
    mirror_issuer: str | None = None,
    refs: Collection[str] | None = None,
) -> list[DecisionView]:
    """Decisions with every child row, ordered by number; filters combine with AND."""
    where: list[str] = []
    params: list[object] = []
    for column, values in (("status", statuses), ("kind", kinds), ("public_id", refs)):
        if values is not None:
            values = list(values)
            if not values:
                return []
            where.append(f"{column} IN ({','.join('?' for _ in values)})")
            params.extend(values)
    if mirror_issuer is not None:
        where.append("substr(mirror_of, 1, ?) = ?")
        params.extend([len(mirror_issuer) + 1, f"{mirror_issuer}_"])
    sql = "SELECT * FROM dec_decisions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    heads = conn.execute(sql + " ORDER BY number", params).fetchall()
    return _assemble(conn, heads)


def load_assumption(
    conn: sqlite3.Connection, assumption_ref: str
) -> tuple[DecisionView, AssumptionView] | None:
    """The decision and the assumption ``D-0907_A-01``, or ``None``."""
    parsed = codes.parse(assumption_ref)
    if len(parsed.parts) != 2 or parsed.parts[1][0] != "A":
        return None
    (d_prefix, d_n), (_, a_n) = parsed.parts
    decision = load_decision(conn, codes.render(d_prefix, d_n))
    if decision is None:
        return None
    for assumption in decision.assumptions:
        if assumption.code_n == a_n:
            return decision, assumption
    return None


def load_forks(
    conn: sqlite3.Connection, *, statuses: Collection[str] | None = None
) -> list[ForkView]:
    sql, params = "SELECT * FROM dec_forks", []
    if statuses is not None:
        values = list(statuses)
        if not values:
            return []
        sql += f" WHERE status IN ({','.join('?' for _ in values)})"
        params = values
    heads = conn.execute(sql + " ORDER BY id", params).fetchall()
    if not heads:
        return []
    options = _group(
        _in_chunks(
            conn, "SELECT * FROM dec_options WHERE fork_id IN ({ids})", [h["id"] for h in heads]
        ),
        "fork_id",
    )
    forks = []
    for h in heads:
        parsed = codes.parse(h["public_id"])
        forks.append(
            ForkView(
                **_stamp(h),
                id=h["id"],
                public_id=h["public_id"],
                number=parsed.parts[0][1],
                question=h["question"],
                trigger_text=h["trigger_text"],
                trigger_ref=h["trigger_ref"],
                opened_at=event_at(h["opened_at"], h["opened_precision"]),
                opened_precision=h["opened_precision"],
                opened_basis=h["opened_basis"],
                decider=h["decider"],
                decider_ref=h["decider_ref"],
                deadline=opt_date(h["deadline"]),
                status=h["status"],
                outcome_not_heard=bool(h["outcome_not_heard"]),
                decision_id=h["decision_id"],
                closed_at=opt_instant(h["closed_at"]),
                close_reason=h["close_reason"],
                delegated_to_ref=h["delegated_to_ref"],
                version=h["version"],
                options=tuple(
                    _option(o, h["public_id"])
                    for o in sorted(options.get(h["id"], []), key=lambda o: o["code_n"])
                ),
            )
        )
    return forks


def _proposal_title(row: Row) -> str:
    try:
        payload = json.loads(row["payload_json"])
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        for key in ("title", "statement", "question"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return f"proposal {row['id']}"


def load_proposals(
    conn: sqlite3.Connection, *, statuses: Collection[str] | None = None
) -> list[ProposalView]:
    sql, params = "SELECT * FROM dec_proposals", []
    if statuses is not None:
        values = list(statuses)
        if not values:
            return []
        sql += f" WHERE status IN ({','.join('?' for _ in values)})"
        params = values
    rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    return [
        ProposalView(
            **_stamp(r),
            id=r["id"],
            ref=f"proposal {r['id']}",
            title=_proposal_title(r),
            type=r["type"],
            decision_id=r["decision_id"],
            payload_json=r["payload_json"],
            payload_hash=r["payload_hash"],
            origin_kind=r["origin_kind"],
            origin_quote=r["origin_quote"],
            proposed_by=r["proposed_by"],
            match_candidates_json=r["match_candidates_json"],
            status=r["status"],
            decided_tx=r["decided_tx"],
            reject_class=r["reject_class"],
            reject_reason=r["reject_reason"],
            result_ref=r["result_ref"],
        )
        for r in rows
    ]


def import_run_view(row: Row) -> ImportRunView:
    return ImportRunView(
        **_stamp(row),
        id=row["id"],
        source_issuer=row["source_issuer"],
        format=row["format"],
        format_version=row["format_version"],
        synthetic=bool(row["synthetic"]),
        file_hash=row["file_hash"],
        exported_at=opt_instant(row["exported_at"]),
        as_of=opt_instant(row["as_of"]),
        as_of_date=opt_date(row["as_of_date"]),
        mode=row["mode"],
        status=row["status"],
        counts_json=row["counts_json"],
        v2_output_json=row["v2_output_json"],
        report_status=row["report_status"],
        error=row["error"],
    )


def load_import_run(
    conn: sqlite3.Connection,
    run_id: int | None = None,
    *,
    issuer: str = "V1",
    any_status: bool = False,
) -> ImportRunView | None:
    """The run ``run_id``, or the latest run of ``issuer`` whose status is ``applied`` (with
    ``any_status``: the latest run of ``issuer`` whatever its status)."""
    if run_id is not None:
        row = conn.execute("SELECT * FROM dec_import_runs WHERE id = ?", (run_id,)).fetchone()
    elif any_status:
        row = conn.execute(
            "SELECT * FROM dec_import_runs WHERE source_issuer = ? ORDER BY id DESC LIMIT 1",
            (issuer,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM dec_import_runs WHERE source_issuer = ? AND status = 'applied' "
            "ORDER BY id DESC LIMIT 1",
            (issuer,),
        ).fetchone()
    return import_run_view(row) if row is not None else None
