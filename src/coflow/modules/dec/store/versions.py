"""``dec_versions``: one row per changed field of a mutable head, in the same unit of work (spec
§2.4 table 17); the replay that ``as_of`` uses.

Owned by track S (store, import, shadow); increment I1, spec §12.2.

- ``record_version`` writes one row in the current unit of work. Values are stored as text
  (``value_text``): integers as their digits, ``None`` as NULL, everything else as stored.
- ``replay_decision`` undoes versions on a loaded ``DecisionView`` (newest first): each hidden row
  sets its field back to ``old_value``. ``as_of(T)`` passes the versions not visible at ``T``
  (§3.15 ``replay_head``); the view's ``stored`` rows are updated too, so hashing at ``T`` sees
  the replayed values.

Spec note: sequence counters (``a_seq``, ``ck_seq``, ...) and ``current_edition`` are bookkeeping
and are never versioned (the edition rows are the history of ``current_edition``). A version row
whose field is not a column of its entity's table (v1 field names the importer could not map) is
kept as history and skipped by the replay.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from typing import Any

from coflow.kernel.store.api import SqlValue, insert
from coflow.modules.dec.domain.model import AssumptionView, DecisionView, LinkView, VersionView
from coflow.modules.dec.store import repo

__all__ = [
    "INTEGER_COLUMNS",
    "record_version",
    "replay_decision",
    "typed_value",
    "value_text",
]

INTEGER_COLUMNS: frozenset[str] = frozenset(
    {
        # dec_decisions
        "number",
        "confidence",
        "current_edition",
        "completion_pending",
        "third_party_sensitive",
        "reconstructed",
        "a_seq",
        "o_seq",
        "r_seq",
        "l_seq",
        "ft_seq",
        "version",
        "erased_tx",
        # dec_assumptions
        "code_n",
        "position",
        "is_critical",
        "probability",
        "shareable",
        "superseded_by",
        "added_in_edition",
        "ck_seq",
        "rd_seq",
        # dec_links
        "removed_tx",
        # dec_forks
        "outcome_not_heard",
        "decision_id",
    }
)


def value_text(value: SqlValue | bool) -> str | None:
    """A stored value as ``dec_versions`` keeps it."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def typed_value(column: str, text: str | None) -> SqlValue:
    """The stored (SQLite) value of a version's text for ``column``."""
    if text is None:
        return None
    if column in INTEGER_COLUMNS:
        return int(text)
    return text


def record_version(
    entity: str,
    entity_id: int,
    field: str,
    old: SqlValue | bool,
    new: SqlValue | bool,
    *,
    cause_kind: str,
    cause_ref: str | None = None,
    reason: str | None = None,
    reconstructed: bool = False,
    origin_recorded_at: str | None = None,
    origin_ref: str | None = None,
) -> int:
    """Write one ``dec_versions`` row in the current unit of work; returns its id."""
    return insert(
        "dec_versions",
        {
            "entity": entity,
            "entity_id": entity_id,
            "field": field,
            "old_value": value_text(old),
            "new_value": value_text(new),
            "reason": reason,
            "cause_kind": cause_kind,
            "cause_ref": cause_ref,
            "reconstructed": 1 if reconstructed else 0,
            "origin_recorded_at": origin_recorded_at,
            "origin_ref": origin_ref,
        },
    )


def _restore(stored: Mapping[str, Any], changes: Iterable[VersionView]) -> dict[str, Any] | None:
    row = dict(stored)
    touched = False
    for v in changes:
        if v.field in row and v.field not in ("id", "tx", "recorded_at"):
            row[v.field] = typed_value(v.field, v.old_value)
            touched = True
    return row if touched else None


def replay_decision(view: DecisionView, hidden: Iterable[VersionView]) -> DecisionView:
    """``view`` with the field changes of ``hidden`` undone, newest first (§3.15)."""
    newest_first = sorted(hidden, key=lambda v: v.id, reverse=True)
    if not newest_first:
        return view
    by_entity: dict[tuple[str, int], list[VersionView]] = {}
    for v in newest_first:
        by_entity.setdefault((v.entity, v.entity_id), []).append(v)

    head = view
    changes = by_entity.get(("decision", view.id))
    if changes:
        row = _restore(view.stored, changes)
        if row is not None:
            head = dataclasses.replace(view, **repo.decision_head_fields(row))

    assumptions: list[AssumptionView] = []
    for a in head.assumptions:
        changes = by_entity.get(("assumption", a.id))
        row = _restore(a.stored, changes) if changes else None
        if row is None:
            assumptions.append(a)
            continue
        rebuilt = repo.assumption_from_row(row, view.public_id)
        assumptions.append(dataclasses.replace(rebuilt, checks=a.checks, readings=a.readings))

    links: list[LinkView] = []
    for link in head.links:
        changes = by_entity.get(("link", link.id))
        row = _restore(link.stored, changes) if changes else None
        links.append(repo.link_from_row(row) if row is not None else link)

    return dataclasses.replace(head, assumptions=tuple(assumptions), links=tuple(links))
