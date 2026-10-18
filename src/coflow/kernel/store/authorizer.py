"""The SQLite authorizer: a unit of work writes only the tables its owner module registered
(ARCHITECTURE §5.3).

Owned by track K (kernel); increment I1, spec §12.2.

The authorizer is the backstop behind the unit of work's own checks; it sees every statement the
writer prepares. The writer connection runs with the statement cache off, because SQLite consults
the authorizer only when a statement is prepared and a cached statement would skip it.

Modes (one at a time, set by the writer):

- ``closed``: no unit is open; nothing but reads.
- ``system``: the store's own statements (``BEGIN``, ``COMMIT``, the transaction-log row, the
  migration runner's bookkeeping and trigger generation); everything is allowed.
- ``migrate``: a migration file of one module: DDL only on tables with the module's prefixes
  (``migrate_prefixes``: ``dec_`` for DEC; ``sys_``, ``cfg_``, ``mcp_``, ``adm_`` for the kernel),
  ``INSERT`` into ``sys_table_registry``, data in the module's own tables; no ``ATTACH``, no
  transaction control, no pragma writes, no ``coflow_`` triggers (the runner generates those).
- ``unit``: a unit of work of one owner module: ``INSERT`` / ``UPDATE`` on that module's tables;
  ``UPDATE`` of an erasable column that is not also mutable, and of ``erased_tx``, only for POL's
  erasure unit (which may update any table, but only its erasable columns); kernel-service tables
  only inside a kernel service call (``kernel_scope``); never ``DELETE``, DDL, ``ATTACH``,
  transaction control or pragma writes.

Spec note (integration): a head's text column may be both mutable and erasable (``dec_decisions``,
``dec_forks``, §2.4 "[E]"). Its owner changes it through its commands; POL blanks it with a new
``erased_tx``. Denying the owner every erasable column made those declarations impossible.
- ``read``: a read inside a unit (``fetch_one`` / ``fetch_all``): reads only.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from coflow.kernel.store.registry import KERNEL_SERVICE_TABLES, TableDecl

__all__ = ["READ_PRAGMAS", "VALUE_PRAGMAS", "AuthMode", "Authorizer", "read_only_authorizer"]

AuthMode = Literal["closed", "system", "migrate", "unit", "read"]

OK = sqlite3.SQLITE_OK
DENY = sqlite3.SQLITE_DENY

READ_ACTIONS = frozenset(
    {sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
)
TXN_ACTIONS = frozenset({sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT})
READ_PRAGMAS = frozenset(
    {
        "table_info",
        "table_xinfo",
        "table_list",
        "index_list",
        "index_info",
        "index_xinfo",
        "foreign_key_list",
        "foreign_key_check",
        "data_version",
        "quick_check",  # ALTER TABLE ... ADD COLUMN checks the table with it
        "integrity_check",
    }
)
# DDL action -> which argument names the table it acts on.
_DDL_TABLE_ARG: Mapping[int, int] = {
    sqlite3.SQLITE_CREATE_TABLE: 1,
    sqlite3.SQLITE_DROP_TABLE: 1,
    sqlite3.SQLITE_CREATE_INDEX: 2,
    sqlite3.SQLITE_DROP_INDEX: 2,
    sqlite3.SQLITE_CREATE_TRIGGER: 2,
    sqlite3.SQLITE_DROP_TRIGGER: 2,
    sqlite3.SQLITE_CREATE_VIEW: 1,
    sqlite3.SQLITE_DROP_VIEW: 1,
    sqlite3.SQLITE_ALTER_TABLE: 2,
}
_SCHEMA_TABLES = frozenset({"sqlite_master", "sqlite_schema", "sqlite_temp_master"})
_INTERNAL_TABLES = frozenset({"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"})


# Pragmas that are reads only when they carry no value (``PRAGMA user_version``, never
# ``PRAGMA user_version = 5``).
VALUE_PRAGMAS = frozenset(
    {
        "user_version",
        "schema_version",
        "application_id",
        "journal_mode",
        "foreign_keys",
        "page_count",
        "page_size",
        "freelist_count",
        "query_only",
        "compile_options",
    }
)


def _read_pragma(name: str | None, arg: str | None = None) -> bool:
    lowered = (name or "").lower()
    return lowered in READ_PRAGMAS or (lowered in VALUE_PRAGMAS and arg is None)


@dataclass
class Authorizer:
    """The writer connection's authorizer; the writer flips its mode."""

    registry: dict[str, TableDecl] = field(default_factory=dict)
    mode: AuthMode = "closed"
    owner: str | None = None
    kernel_scope: bool = False
    migrate_prefixes: tuple[str, ...] = ()
    denied: list[str] = field(default_factory=list)

    def __call__(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        db_name: str | None,
        source: str | None,
    ) -> int:
        verdict = self._decide(action, arg1, arg2)
        if verdict != OK:
            self.denied.append(f"{self.mode}:{self.owner}:{action}:{arg1}:{arg2}")
            del self.denied[:-20]
        return verdict

    def _decide(self, action: int, arg1: str | None, arg2: str | None) -> int:
        if action in READ_ACTIONS:
            return OK
        if action == sqlite3.SQLITE_PRAGMA:
            return OK if self.mode == "system" or _read_pragma(arg1, arg2) else DENY
        if self.mode == "system":
            return OK
        if action in TXN_ACTIONS or action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return DENY
        if self.mode == "migrate":
            return self._migrate(action, arg1, arg2)
        if self.mode == "unit":
            return self._unit(action, arg1, arg2)
        return DENY  # closed, read

    def _migrate(self, action: int, arg1: str | None, arg2: str | None) -> int:
        prefixes = self.migrate_prefixes
        if action == sqlite3.SQLITE_REINDEX:
            return OK  # part of CREATE INDEX; it changes no data
        if action in _DDL_TABLE_ARG:
            target = arg1 if _DDL_TABLE_ARG[action] == 1 else arg2
            if action == sqlite3.SQLITE_CREATE_TRIGGER and (arg1 or "").startswith("coflow_"):
                return DENY
            return OK if target and target.startswith(prefixes) else DENY
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            table = arg1 or ""
            if table in _SCHEMA_TABLES or table in _INTERNAL_TABLES:
                return OK
            if table == "sys_table_registry" and action != sqlite3.SQLITE_DELETE:
                return OK  # the runner checks afterwards that only the module's own rows changed
            return OK if table.startswith(prefixes) else DENY
        return DENY

    def _unit(self, action: int, arg1: str | None, arg2: str | None) -> int:
        table = arg1 or ""
        if table in _INTERNAL_TABLES:
            return OK
        if action == sqlite3.SQLITE_DELETE:
            return DENY
        if self.kernel_scope:
            if table in KERNEL_SERVICE_TABLES and action in (
                sqlite3.SQLITE_INSERT,
                sqlite3.SQLITE_UPDATE,
            ):
                return OK
            return DENY
        decl = self.registry.get(table)
        if decl is None or table in KERNEL_SERVICE_TABLES:
            return DENY
        if action == sqlite3.SQLITE_INSERT:
            return OK if decl.module == self.owner else DENY
        if action == sqlite3.SQLITE_UPDATE:
            erasure_column = arg2 in decl.erasable or arg2 == "erased_tx"
            if self.owner == "pol":
                return OK if erasure_column else DENY
            if decl.module != self.owner:
                return DENY
            if arg2 == "erased_tx":
                return DENY  # only POL's erasure unit stamps an erasure
            # An erasable column that is also mutable (a head's text, changed by its commands
            # with version rows) is the owner's to change; one that is not mutable changes only
            # by erasure (the generated triggers hold the same rule for any client).
            return DENY if arg2 in decl.erasable and arg2 not in decl.mutable else OK
        return DENY


def read_only_authorizer(
    action: int, arg1: str | None, arg2: str | None, db_name: str | None, source: str | None
) -> int:
    """The authorizer of read connections: reads, read pragmas and the snapshot's BEGIN/COMMIT."""
    if action in READ_ACTIONS or action == sqlite3.SQLITE_TRANSACTION:
        return OK
    if action == sqlite3.SQLITE_PRAGMA:
        return OK if _read_pragma(arg1, arg2) else DENY
    return DENY
