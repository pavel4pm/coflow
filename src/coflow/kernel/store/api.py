"""The storage contract every track codes against (spec §12.1, §2.1, §2.3).

Skeleton file. Track K implements ``Store`` and ``UnitOfWork`` (``db.py``, ``unit.py``,
``writer.py``, ``registry.py``, ``triggers.py``, ``authorizer.py``, ``txlog.py``, ``lock.py``,
``migrations.py``); everyone else uses only the functions below. A signature change is a reviewed
skeleton pull request.

Usage::

    from coflow.kernel.store.api import insert, read_connection, set_once, unit_of_work, update_head

    with unit_of_work("dec", ctx, command="import_snapshot") as uow:
        run_id = insert("dec_import_runs", {...})          # tx and recorded_at are stamped here
        set_once("dec_readings", reading_id, accepted_by_check_id=check_id)
        version = update_head("dec_decisions", decision_id, expected, review_due="2026-12-01")

    with read_connection() as conn:                         # WAL read connection, query_only
        rows = conn.execute("SELECT ... FROM dec_decisions").fetchall()

The rules (STO, spec §2.1, §2.3, §2.9):

- **One process-wide store.** The composition root (or a test fixture) binds the instance's store
  with ``bind_store`` / ``use_store``; the free functions use it. There is never a second writer.
- **One unit of work per command.** ``unit_of_work(owner_module, ctx)`` commits on success and rolls
  back on any exception, together with every event published inside it. It writes exactly one
  ``sys_tx_log`` row (actor, channel, owner-channel flag, interaction id, approval ref, instance
  role, code version, command). Units do not nest; writes outside a unit raise
  ``ContractViolation``.
- **Ownership.** A unit may write only the tables its ``owner_module`` registered (the SQLite
  authorizer reads ``sys_table_registry``). Cross-module workflows are orchestrated by interfaces,
  each step its owner's own unit (ARCHITECTURE §6.1).
- **The store stamps time.** ``insert`` sets ``tx`` (the unit's id) and ``recorded_at`` (the unit's
  ``committed_at``, from the store's ``Clock``) on every table that has those columns. A row that
  supplies either raises ``ContractViolation`` (a programming error, AT-K5).
- **Values are stored values.** Rows are mappings of column name to ``str | int | None`` (SQLite
  ``STRICT`` tables): instants as ``format_instant`` text, dates as ``YYYY-MM-DD``, decimals as
  decimal strings, booleans as 0/1, JSON as CFJ-1 text. Floats are refused.
- **Append-only by declaration.** No registered table accepts DELETE. ``set_once`` changes columns
  declared in ``set_once_cols`` from NULL to a value exactly once. Erasable columns are blanked only
  by POL's erasure unit. ``update_head`` changes ``mutable_cols`` of a versioned head (a table with
  a ``version`` column) under optimistic concurrency; ``update_mutable`` changes ``mutable_cols`` of
  an unversioned system table. Field history is the owner module's job (``dec_versions``,
  ``cmt_history``), written in the same unit. ``update_*`` never change ``tx`` or ``recorded_at``.

Migrations (the contract between K's runner and every module's ``.sql`` files):

- Files are named ``NNNN_<name>.sql``: kernel files in ``coflow/migrations/kernel/``, module files
  in ``coflow/modules/<mod>/migrations/``. They are applied forward-only, kernel first, then modules
  in tier order (lowest tier first), each file once, with its checksum recorded in
  ``sys_migrations``.
- A module file creates only tables with its own prefix (``dec_``, ``cmt_``) as ``STRICT`` tables,
  and inserts one ``sys_table_registry`` row per table: ``table_name``, ``module``, ``data_class``
  (``work``, ``financial``, ``system``; never ``journal`` in the slice), ``append_only`` (0/1),
  ``set_once_cols``, ``erasable_cols``, ``mutable_cols`` (each a JSON array of column names, ``[]``
  when empty). After the file runs, the runner generates the ``BEFORE UPDATE`` / ``BEFORE DELETE``
  triggers of those tables from their registry rows.
- Every domain table has ``tx INTEGER NOT NULL`` and ``recorded_at TEXT NOT NULL``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from coflow.kernel.context import Clock, CommandContext
from coflow.kernel.errors import ContractViolation

__all__ = [
    "SqlParams",
    "SqlValue",
    "Store",
    "UnitOfWork",
    "bind_store",
    "current_store",
    "current_unit",
    "insert",
    "open_store",
    "read_connection",
    "set_once",
    "unbind_store",
    "unit_of_work",
    "update_head",
    "update_mutable",
    "use_store",
]

SqlValue = str | int | None
"""A stored value: booleans are 0/1, decimals and instants are text; floats never reach it."""

SqlParams = Sequence[SqlValue] | Mapping[str, SqlValue]


@runtime_checkable
class UnitOfWork(Protocol):
    """An open unit of work: one transaction, one ``sys_tx_log`` row, its events."""

    @property
    def tx(self) -> int:
        """The unit's ``sys_tx_log.tx``; every row it inserts carries it."""
        ...

    @property
    def committed_at(self) -> datetime:
        """The unit's instant (UTC, from the store's clock): ``recorded_at`` of its new rows."""
        ...

    @property
    def owner_module(self) -> str: ...

    @property
    def ctx(self) -> CommandContext: ...

    def insert(self, table: str, row: Mapping[str, SqlValue]) -> int:
        """Insert one row, stamping ``tx`` and ``recorded_at``; returns the new rowid."""
        ...

    def set_once(self, table: str, id: int, /, **cols: SqlValue) -> None:
        """Set declared set-once columns of row ``id`` (its INTEGER PRIMARY KEY) from NULL, once."""
        ...

    def update_head(self, table: str, id: int, version: int, /, **cols: SqlValue) -> int:
        """Change mutable columns of a versioned head row if its version is ``version``.

        Increments the version and returns the new one; raises ``Conflict(current_version)`` on a
        mismatch and ``NotFound`` for a missing row.
        """
        ...

    def update_mutable(self, table: str, key: Mapping[str, SqlValue], /, **cols: SqlValue) -> int:
        """Change mutable columns of the unversioned rows matching ``key``; returns their count."""
        ...

    def fetch_one(self, sql: str, params: SqlParams = ()) -> sqlite3.Row | None:
        """Read inside the unit (sees its own writes). Prefer reads before the unit (AP-4)."""
        ...

    def fetch_all(self, sql: str, params: SqlParams = ()) -> list[sqlite3.Row]: ...


@runtime_checkable
class Store(Protocol):
    """One instance's database: the single writer plus WAL read connections."""

    @property
    def data_root(self) -> Path: ...

    @property
    def clock(self) -> Clock:
        """The clock that stamps every unit; queries read "now" from it too."""
        ...

    def unit_of_work(
        self, owner_module: str, ctx: CommandContext, *, command: str | None = None
    ) -> AbstractContextManager[UnitOfWork]: ...

    def read_connection(self) -> AbstractContextManager[sqlite3.Connection]:
        """A read-only WAL connection (``row_factory = sqlite3.Row``, ``query_only = ON``)."""
        ...

    def close(self) -> None: ...


# --------------------------------------------------------------------------------------------------
# The process-wide binding


class _Binding:
    store: Store | None = None


_BINDING = _Binding()
_UNIT: ContextVar[UnitOfWork | None] = ContextVar("coflow_unit_of_work", default=None)


def bind_store(store: Store) -> None:
    """Bind the instance's store for this process (the composition root does this once)."""
    if _BINDING.store is not None and _BINDING.store is not store:
        raise ContractViolation("a store is already bound: there is never a second writer")
    _BINDING.store = store


def unbind_store() -> None:
    _BINDING.store = None


@contextmanager
def use_store(store: Store) -> Iterator[Store]:
    """Bind ``store`` for the duration of a block (tests, the CLI's ephemeral core)."""
    previous = _BINDING.store
    _BINDING.store = store
    try:
        yield store
    finally:
        _BINDING.store = previous


def current_store() -> Store:
    store = _BINDING.store
    if store is None:
        raise ContractViolation("no store is bound (bind_store / use_store)")
    return store


def current_unit() -> UnitOfWork:
    unit = _UNIT.get()
    if unit is None:
        raise ContractViolation("no unit of work is open: writes happen only inside unit_of_work()")
    return unit


def open_store(data_root: Path, *, clock: Clock, read_only: bool = False) -> Store:
    """Open an initialised instance under its instance lock (track K implements it in ``db.py``)."""
    from coflow.kernel.store import db

    return db.open_store(data_root, clock=clock, read_only=read_only)


# --------------------------------------------------------------------------------------------------
# The functions every track uses


@contextmanager
def unit_of_work(
    owner_module: str, ctx: CommandContext, *, command: str | None = None
) -> Iterator[UnitOfWork]:
    """Run a block as one unit of work owned by ``owner_module`` ('dec', 'cmt', 'obs', ...)."""
    if _UNIT.get() is not None:
        raise ContractViolation("units of work do not nest")
    with current_store().unit_of_work(owner_module, ctx, command=command) as unit:
        token = _UNIT.set(unit)
        try:
            yield unit
        finally:
            _UNIT.reset(token)


def read_connection() -> AbstractContextManager[sqlite3.Connection]:
    """A read-only connection of the bound store; queries never write."""
    return current_store().read_connection()


def insert(table: str, row: Mapping[str, SqlValue]) -> int:
    return current_unit().insert(table, row)


def set_once(table: str, id: int, /, **cols: SqlValue) -> None:
    current_unit().set_once(table, id, **cols)


def update_head(table: str, id: int, version: int, /, **cols: SqlValue) -> int:
    return current_unit().update_head(table, id, version, **cols)


def update_mutable(table: str, key: Mapping[str, SqlValue], /, **cols: SqlValue) -> int:
    return current_unit().update_mutable(table, key, **cols)
