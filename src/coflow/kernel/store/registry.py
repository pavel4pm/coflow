"""``sys_table_registry``: per table its owner module, data class and the ``append_only``,
``set_once_cols``, ``erasable_cols`` and ``mutable_cols`` declarations that the authorizer and
the trigger generator read (spec §2.1, §2.3).

Owned by track K (kernel); increment I1, spec §12.2.

A ``TableDecl`` joins a registry row with the table's real columns (``PRAGMA table_info``), so the
unit of work, the authorizer and the trigger generator all read one object. ``validate_decl`` is
the fitness check the migration runner applies after every file: an owner, a data class, a
``STRICT`` table, the owner's prefix, ``tx`` (and ``recorded_at`` for module tables), declared
columns that exist, and declarations that do not contradict each other.

Spec note: a table with a ``version`` column is a versioned head; ``version`` is changed only by
``update_head`` and is treated as mutable whether or not it is listed. ``append_only = 1`` means
"no mutable columns": every column is immutable except the declared set-once and erasable ones.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

__all__ = [
    "DATA_CLASSES",
    "KERNEL_OWNERS",
    "KERNEL_SERVICE_TABLES",
    "STAMP_COLUMNS",
    "TableDecl",
    "load_registry",
    "owner_prefixes",
    "validate_decl",
]

DATA_CLASSES: tuple[str, ...] = ("journal", "financial", "work", "system")

# Kernel "modules" that own kernel tables, with the table-name prefix each may create.
KERNEL_OWNERS: Mapping[str, str] = {
    "sto": "sys_",
    "ids": "sys_",
    "evt": "sys_",
    "ops": "sys_",
    "obs": "sys_",
    "pol": "sys_",
    "cfg": "cfg_",
    "mcp": "mcp_",
    "adm": "adm_",
}

# Tables written by kernel services inside any module's unit of work (the tap, aliases, events,
# idempotency keys, the transaction log). Module code never writes them directly.
KERNEL_SERVICE_TABLES: frozenset[str] = frozenset(
    {
        "sys_tx_log",
        "sys_command_keys",
        "sys_id_prefixes",
        "sys_id_sequence",
        "sys_id_burned",
        "sys_id_foreign",
        "sys_id_aliases",
        "sys_events",
    }
)

# Columns the store stamps; a caller never supplies or changes them (AT-K5).
STAMP_COLUMNS: frozenset[str] = frozenset({"tx", "recorded_at"})

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True, kw_only=True)
class TableDecl:
    """One registered table: its declarations and its real columns."""

    table: str
    module: str
    data_class: str
    append_only: bool
    set_once: frozenset[str]
    erasable: frozenset[str]
    mutable: frozenset[str]
    columns: tuple[str, ...]
    pk: str | None  # the INTEGER PRIMARY KEY column, if the table has one

    @property
    def has_tx(self) -> bool:
        return "tx" in self.columns

    @property
    def has_recorded_at(self) -> bool:
        return "recorded_at" in self.columns

    @property
    def versioned(self) -> bool:
        return "version" in self.columns

    @property
    def has_erased_tx(self) -> bool:
        return "erased_tx" in self.columns

    @property
    def changeable(self) -> frozenset[str]:
        """Columns ``update_head`` / ``update_mutable`` may change."""
        return self.mutable

    @property
    def key_column(self) -> str:
        """The column ``set_once`` and ``update_head`` address rows by."""
        return self.pk or "rowid"


def _json_list(raw: object, *, table: str, column: str) -> frozenset[str]:
    try:
        value = json.loads(str(raw)) if raw is not None else []
    except ValueError as exc:
        raise ValueError(f"{table}: {column} is not a JSON array") from exc
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{table}: {column} must be a JSON array of column names")
    return frozenset(value)


def _columns(conn: sqlite3.Connection, table: str) -> tuple[tuple[str, ...], str | None]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    names = tuple(str(r[1]) for r in rows)
    pks = [r for r in rows if int(r[5]) > 0]
    pk = None
    if len(pks) == 1 and str(pks[0][2]).upper() == "INTEGER":
        pk = str(pks[0][1])
    return names, pk


def load_registry(conn: sqlite3.Connection) -> dict[str, TableDecl]:
    """Every registered table, joined with its columns. Empty before the kernel migration."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'sys_table_registry'"
    ).fetchone()
    if exists is None:
        return {}
    out: dict[str, TableDecl] = {}
    rows = conn.execute(
        "SELECT table_name, module, data_class, append_only, set_once_cols, erasable_cols,"
        " mutable_cols FROM sys_table_registry ORDER BY table_name"
    ).fetchall()
    for name, module, data_class, append_only, so, er, mu in rows:
        table = str(name)
        columns, pk = _columns(conn, table)
        out[table] = TableDecl(
            table=table,
            module=str(module),
            data_class=str(data_class),
            append_only=bool(append_only),
            set_once=_json_list(so, table=table, column="set_once_cols"),
            erasable=_json_list(er, table=table, column="erasable_cols"),
            mutable=_json_list(mu, table=table, column="mutable_cols"),
            columns=columns,
            pk=pk,
        )
    return out


def owner_prefixes(module: str) -> tuple[str, ...]:
    """The table-name prefixes ``module`` may create: ``dec_`` for DEC, ``sys_`` for STO, ..."""
    if module in KERNEL_OWNERS:
        return (KERNEL_OWNERS[module],)
    return (f"{module}_",)


def _is_strict(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT strict FROM pragma_table_list WHERE name = ?", (table,)).fetchone()
    return bool(row and row[0])


def validate_decl(
    conn: sqlite3.Connection, decl: TableDecl, *, allowed_modules: Iterable[str]
) -> list[str]:
    """The problems with one registered table (empty when it follows the contract)."""
    problems: list[str] = []
    t = decl.table
    allowed = set(allowed_modules)
    if decl.module not in allowed:
        problems.append(f"{t}: module {decl.module!r} may not be registered by this migration")
    if not _NAME.match(t):
        problems.append(f"{t}: table names are lower-case snake_case")
    if not any(t.startswith(p) for p in owner_prefixes(decl.module)):
        problems.append(f"{t}: tables of {decl.module!r} start with {owner_prefixes(decl.module)}")
    if decl.data_class not in DATA_CLASSES:
        problems.append(f"{t}: unknown data class {decl.data_class!r}")
    if not decl.columns:
        problems.append(f"{t}: registered but the table does not exist")
        return problems
    if not _is_strict(conn, t):
        problems.append(f"{t}: tables are STRICT")
    for col in decl.columns:
        if not _NAME.match(col):
            problems.append(f"{t}.{col}: column names are lower-case snake_case")
    is_module = decl.module not in KERNEL_OWNERS
    if is_module and not decl.has_tx:
        problems.append(f"{t}: every domain table has tx INTEGER NOT NULL")
    if is_module and not decl.has_recorded_at:
        problems.append(f"{t}: every domain table has recorded_at TEXT NOT NULL")
    declared = decl.set_once | decl.erasable | decl.mutable
    for col in sorted(declared - set(decl.columns)):
        problems.append(f"{t}: declared column {col!r} does not exist")
    for col in sorted(declared & STAMP_COLUMNS):
        problems.append(f"{t}: {col} is stamped by the store and never declared changeable")
    if decl.append_only and decl.mutable:
        problems.append(f"{t}: an append-only table has no mutable columns")
    if decl.mutable & decl.set_once:
        problems.append(f"{t}: a column is either mutable or set-once")
    if decl.erasable and not decl.has_erased_tx:
        problems.append(f"{t}: erasable columns need an erased_tx column")
    if decl.versioned and decl.append_only:
        problems.append(f"{t}: a versioned head is not append-only")
    return problems
