"""Mirrors (spec §6.1): the authority map (``full`` for V1, ``basis_only`` for the project's
decision log), the guard every command calls (``MIRRORED``, naming the authority, AT-S4) and
``dec_mirror_state`` bookkeeping with tombstones.

Owned by track S (store, import, shadow); increment I1, spec §12.2.

- **The authority map.** A mirror's ``mirror_of`` is ``<ISSUER>_<source id>``. ``V1`` owns every
  field and every child row of its mirrors (``full``); the project's decision log ``CF2LOG`` owns
  ``title``, ``context``, ``statement``, the option texts and ``decided_at`` (``basis_only``), and
  v2 owns everything else. One writer per field, always.
- **The guard.** ``guard_mirror(decision, op=..., fields=...)`` is called by every DEC command
  before it writes (I2 commands; the importer never calls it, because it is the authority's own
  writer). It raises ``Refused(MIRRORED)`` with the authority named and what to do instead.
- **Bookkeeping.** ``dec_mirror_state`` keys each mirrored source row by ``(issuer, source_kind,
  source_id)`` with the local row, a content hash and the runs that saw it. A row missing from a
  later snapshot gets ``absent_since_run_id`` (a tombstone), never a delete; it is cleared when the
  row comes back.

Spec note: §6.1 names the log-owned fields as "the option texts from the Alternatives bullet"; the
guard models them as the pseudo-field ``option_text`` (any command that writes an option's text,
``add_option`` included, names it).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.store.api import insert, update_mutable
from coflow.modules.dec.domain.model import DecisionView

__all__ = [
    "AUTHORITIES",
    "DEC_WRITE_COMMANDS",
    "Authority",
    "MirrorState",
    "authority_of",
    "guard_mirror",
    "issuer_of",
    "load_mirror_states",
    "mark_absent",
    "mark_present",
    "mirror_line",
    "put_state",
]

OPTION_TEXT = "option_text"


@dataclass(frozen=True, slots=True, kw_only=True)
class Authority:
    """Who owns a mirror's fields (§6.1). ``owned`` is ``None`` when the source owns everything."""

    issuer: str
    scope: Literal["full", "basis_only"]
    name: str
    owned: frozenset[str] | None

    def owns(self, fields: Collection[str]) -> list[str]:
        if self.owned is None:
            return sorted(fields) or ["*"]
        return sorted(set(fields) & self.owned)


AUTHORITIES: Mapping[str, Authority] = {
    "V1": Authority(issuer="V1", scope="full", name="V1", owned=None),
    "CF2LOG": Authority(
        issuer="CF2LOG",
        scope="basis_only",
        name="the project's decision log",
        owned=frozenset(
            {
                "title",
                "context",
                "statement",
                "decided_at",
                "decided_precision",
                "decided_basis",
                OPTION_TEXT,
            }
        ),
    ),
}

DEC_WRITE_COMMANDS: tuple[str, ...] = (
    "update_decision",
    "activate_decision",
    "complete_decision",
    "add_option",
    "add_assumption",
    "supersede_assumption",
    "drop_assumption",
    "record_check",
    "record_reading",
    "postpone_check",
    "add_fact",
    "correct_fact",
    "review_decision",
    "set_manual_flag",
    "set_publishability",
    "link",
    "unlink",
    "undo",
)
"""Every DEC command of §5.2 that writes to an existing decision; each calls ``guard_mirror``."""


def issuer_of(mirror_of: str | None) -> str | None:
    """``'V1'`` for ``'V1_D907'``; ``None`` for a native or adopted record."""
    if not mirror_of:
        return None
    issuer, sep, _ = mirror_of.partition("_")
    return issuer if sep else None


def authority_of(mirror_of: str | None, mirror_scope: str | None = None) -> Authority | None:
    """The authority of a mirror; an unknown issuer is treated as owning everything."""
    issuer = issuer_of(mirror_of)
    if issuer is None:
        return None
    known = AUTHORITIES.get(issuer)
    if known is not None:
        return known
    scope: Literal["full", "basis_only"] = "basis_only" if mirror_scope == "basis_only" else "full"
    return Authority(issuer=issuer, scope=scope, name=issuer, owned=None)


def guard_mirror(
    decision: DecisionView | Mapping[str, object],
    *,
    op: str,
    fields: Collection[str] = (),
) -> None:
    """Refuse a command that would change a field the decision's authority owns (§3.1, §6.1).

    ``fields`` names the columns (or ``option_text``) the command would write. For a ``full``
    mirror every command is refused whatever it writes; for a ``basis_only`` mirror only commands
    that touch an owned field.
    """
    if isinstance(decision, DecisionView):
        mirror_of, scope, ref = decision.mirror_of, decision.mirror_scope, decision.public_id
    else:
        mirror_of = _opt_text(decision.get("mirror_of"))
        scope = _opt_text(decision.get("mirror_scope"))
        ref = _opt_text(decision.get("public_id"))
    authority = authority_of(mirror_of, scope)
    if authority is None:
        return
    if authority.scope == "full" or authority.owned is None:
        raise Refused(
            RefusalCode.MIRRORED,
            f"{ref} is mirrored from {authority.name}; {authority.name} is the system of record "
            f"until adoption, so {op} is refused here: record it in {authority.name}",
        )
    owned = authority.owns(fields)
    if owned:
        raise Refused(
            RefusalCode.MIRRORED,
            f"{', '.join(owned)} of {ref} belong to {authority.name} ({authority.issuer}); "
            f"change them there and re-import, so {op} is refused here",
            allowed=sorted(set(fields) - set(owned)),
        )


def mirror_line(mirror_of: str | None, exported_at: str | None) -> str | None:
    """The authority line of a mirror's answers (§5.1)."""
    authority = authority_of(mirror_of)
    if authority is None:
        return None
    when = f", snapshot exported at {exported_at}" if exported_at else ""
    return f"mirrored from {authority.issuer}{when}; read-only here"


# ==================================================================================================
# dec_mirror_state


@dataclass(frozen=True, slots=True, kw_only=True)
class MirrorState:
    issuer: str
    source_kind: str
    source_id: str
    local_table: str
    local_id: int
    content_hash: str
    first_run_id: int
    last_run_id: int
    absent_since_run_id: int | None
    adopted_at: str | None


def _opt_text(value: object) -> str | None:
    return None if value is None else str(value)


def _state(row: Any) -> MirrorState:
    return MirrorState(
        issuer=str(row["issuer"]),
        source_kind=str(row["source_kind"]),
        source_id=str(row["source_id"]),
        local_table=str(row["local_table"]),
        local_id=int(row["local_id"]),
        content_hash=str(row["content_hash"]),
        first_run_id=int(row["first_run_id"]),
        last_run_id=int(row["last_run_id"]),
        absent_since_run_id=row["absent_since_run_id"],
        adopted_at=row["adopted_at"],
    )


def load_mirror_states(
    conn: Any, issuer: str, *, kinds: Collection[str] | None = None
) -> dict[tuple[str, str], MirrorState]:
    """Every state row of ``issuer`` keyed by ``(source_kind, source_id)``.

    ``conn`` is a read connection (``sqlite3.Connection``), or a unit of work (anything with
    ``fetch_all``).
    """
    sql = "SELECT * FROM dec_mirror_state WHERE issuer = ?"
    params: list[object] = [issuer]
    if kinds is not None:
        values = list(kinds)
        sql += f" AND source_kind IN ({','.join('?' for _ in values)})"
        params.extend(values)
    if hasattr(conn, "fetch_all"):
        rows = conn.fetch_all(sql, params)
    else:
        rows = conn.execute(sql, params).fetchall()
    return {(r["source_kind"], r["source_id"]): _state(r) for r in rows}


def put_state(
    *,
    issuer: str,
    source_kind: str,
    source_id: str,
    local_table: str,
    local_id: int,
    content_hash: str,
    run_id: int,
    existing: MirrorState | None,
) -> None:
    """Insert or refresh a state row in the current unit of work (clears a tombstone)."""
    if existing is None:
        insert(
            "dec_mirror_state",
            {
                "issuer": issuer,
                "source_kind": source_kind,
                "source_id": source_id,
                "local_table": local_table,
                "local_id": local_id,
                "content_hash": content_hash,
                "first_run_id": run_id,
                "last_run_id": run_id,
                "absent_since_run_id": None,
                "adopted_at": None,
            },
        )
        return
    changes: dict[str, str | int | None] = {}
    if existing.local_table != local_table or existing.local_id != local_id:
        changes.update(local_table=local_table, local_id=local_id)
    if existing.content_hash != content_hash:
        changes["content_hash"] = content_hash
    if existing.last_run_id != run_id:
        changes["last_run_id"] = run_id
    if existing.absent_since_run_id is not None:
        changes["absent_since_run_id"] = None
    if changes:
        update_mutable(
            "dec_mirror_state",
            {"issuer": issuer, "source_kind": source_kind, "source_id": source_id},
            **changes,
        )


def mark_absent(state: MirrorState, run_id: int) -> bool:
    """Tombstone a state row missing from the snapshot; ``False`` when it already was one."""
    if state.absent_since_run_id is not None:
        return False
    update_mutable(
        "dec_mirror_state",
        {"issuer": state.issuer, "source_kind": state.source_kind, "source_id": state.source_id},
        absent_since_run_id=run_id,
    )
    return True


def mark_present(state: MirrorState, run_id: int) -> None:
    """Refresh ``last_run_id`` of an unchanged row seen again (and clear a tombstone)."""
    put_state(
        issuer=state.issuer,
        source_kind=state.source_kind,
        source_id=state.source_id,
        local_table=state.local_table,
        local_id=state.local_id,
        content_hash=state.content_hash,
        run_id=run_id,
        existing=state,
    )
