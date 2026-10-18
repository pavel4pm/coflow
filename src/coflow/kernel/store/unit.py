"""The unit of work behind ``api.unit_of_work``: the ``sys_tx_log`` row, ``tx`` and ``recorded_at``
stamping, events in the same transaction, idempotency keys in ``sys_command_keys`` (spec §2.1,
§2.3, AT-K5).

Owned by track K (kernel); increment I1, spec §12.2.

``Unit`` implements ``api.UnitOfWork``. Life of a unit (``run_unit``):

1. take the writer (units are serialised; they never nest), ``BEGIN IMMEDIATE``;
2. stamp one instant from the store's clock (``committed_at``) and write the ``sys_tx_log`` row
   (actor, channel, owner-channel flag, interaction id, source ref, approval ref, instance role,
   code version, owner module, command); its rowid is the unit's ``tx``;
3. look up the context's idempotency key (``prior_result``);
4. run the caller's block: every write goes through the unit, which checks the table registry
   before SQLite's authorizer and triggers check again;
5. commit; or roll back on any exception, or when the block wrote nothing at all (a unit that wrote
   nothing leaves no trace, not even its ``sys_tx_log`` row);
6. release the writer, then run the store's after-commit callbacks (event dispatch).

Extras beyond the protocol, for kernel services and later tracks:

- ``kernel_insert`` / ``kernel_update``: the kernel's own tables (tap, aliases, events, keys),
  written from inside any module's unit; module code never calls them.
- ``record_event`` / ``event_ids``: the events published in the unit (``events.publish``).
- ``prior_result`` / ``prior_tx`` / ``remember``: idempotency. A command opened with
  ``ctx.idempotency_key`` checks ``prior_result`` first and returns it (writing nothing); after
  its writes it calls ``remember(result_json)``. A key reused for another command is a
  ``ContractViolation``.
- ``declare_input_class``: the data classes of the unit's inputs (POL). A journal-class input in a
  module without journal-class tables is ``Refused(JOURNAL_CLASS_INPUT)``; a row is never stored in
  a table of a less restrictive class than the unit's inputs.
- ``erase``: POL's erasure (owner module ``pol`` only): blank declared erasable columns and stamp
  ``erased_tx``.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from coflow.kernel.context import CommandContext, format_instant
from coflow.kernel.errors import Conflict, ContractViolation, NotFound, RefusalCode, Refused
from coflow.kernel.store.api import SqlParams, SqlValue
from coflow.kernel.store.registry import (
    DATA_CLASSES,
    KERNEL_SERVICE_TABLES,
    STAMP_COLUMNS,
    TableDecl,
)
from coflow.kernel.store.txlog import insert_tx
from coflow.kernel.store.writer import Writer, warn_if_slow

if TYPE_CHECKING:
    from coflow.kernel.store.db import SqliteStore

__all__ = ["Unit", "class_rank", "run_unit"]


def class_rank(data_class: str) -> int:
    """0 for journal (most restrictive) ... 3 for system."""
    return DATA_CLASSES.index(data_class)


def _check_value(table: str, col: str, value: object) -> SqlValue:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    raise ContractViolation(
        f"{table}.{col}: stored values are str, int or None, not {type(value).__name__}"
        " (decimals and instants are text; floats never reach the store)"
    )


class Unit:
    """One open unit of work (see the module docstring)."""

    def __init__(
        self,
        store: SqliteStore,
        writer: Writer,
        *,
        owner_module: str,
        ctx: CommandContext,
        command: str | None,
        committed_at: datetime,
        tx: int,
        instance_id: str,
        instance_role: str,
    ) -> None:
        self._store = store
        self._writer = writer
        self._owner = owner_module
        self._ctx = ctx
        self._command = command
        self._committed_at = committed_at
        self._recorded_at = format_instant(committed_at)
        self._tx = tx
        self.instance_id = instance_id
        self.instance_role = instance_role
        self._events: list[str] = []
        self._writes = 0
        self._input_class = "system"
        self.prior_result: str | None = None
        self.prior_tx: int | None = None
        self._remembered = False
        self._closed = False

    # -- protocol properties ---------------------------------------------------------------------

    @property
    def tx(self) -> int:
        return self._tx

    @property
    def committed_at(self) -> datetime:
        return self._committed_at

    @property
    def recorded_at(self) -> str:
        """``committed_at`` as stored text: the ``recorded_at`` of every row of the unit."""
        return self._recorded_at

    @property
    def owner_module(self) -> str:
        return self._owner

    @property
    def ctx(self) -> CommandContext:
        return self._ctx

    @property
    def command(self) -> str | None:
        return self._command

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(self._events)

    @property
    def wrote(self) -> bool:
        return self._writes > 0

    @property
    def input_class(self) -> str:
        return self._input_class

    # -- helpers ---------------------------------------------------------------------------------

    def _alive(self) -> None:
        if self._closed:
            raise ContractViolation("the unit of work is closed")

    def _decl(self, table: str) -> TableDecl:
        decl = self._store.registry.get(table)
        if decl is None:
            raise ContractViolation(f"{table} is not a registered table")
        return decl

    def _own(self, table: str) -> TableDecl:
        decl = self._decl(table)
        if table in KERNEL_SERVICE_TABLES:
            raise ContractViolation(f"{table} is written only by kernel services")
        if decl.module != self._owner:
            raise ContractViolation(
                f"a unit of {self._owner!r} may not write {table} (owned by {decl.module!r})"
            )
        return decl

    def _class_allows(self, decl: TableDecl) -> None:
        # Only the protected classes taint: journal and financial input never lands in a less
        # restrictive table; work input may feed system bookkeeping (counts, hashes, reports).
        if decl.table in KERNEL_SERVICE_TABLES or self._input_class not in ("journal", "financial"):
            return
        if class_rank(self._input_class) < class_rank(decl.data_class):
            if self._input_class == "journal":
                raise Refused(
                    RefusalCode.JOURNAL_CLASS_INPUT,
                    f"journal-class input may not be stored in {decl.table}",
                )
            raise ContractViolation(
                f"{self._input_class}-class input may not be stored in {decl.table}"
                f" ({decl.data_class})"
            )

    def _exec(self, sql: str, params: SqlParams = ()) -> sqlite3.Cursor:
        auth = self._writer.authorizer
        auth.mode = "unit"
        auth.owner = self._owner
        return self._writer.run(sql, params)

    def _insert_row(self, decl: TableDecl, row: Mapping[str, SqlValue]) -> int:
        stamped = sorted(STAMP_COLUMNS & set(row))
        if stamped:
            raise ContractViolation(
                f"{decl.table}: {', '.join(stamped)} are stamped by the store, never by the caller"
            )
        values: dict[str, SqlValue] = {
            col: _check_value(decl.table, col, v) for col, v in row.items()
        }
        unknown = sorted(set(values) - set(decl.columns))
        if unknown:
            raise ContractViolation(f"{decl.table}: unknown columns {', '.join(unknown)}")
        if decl.has_tx:
            values["tx"] = self._tx
        if decl.has_recorded_at:
            values["recorded_at"] = self._recorded_at
        cols = ", ".join(f'"{c}"' for c in values)
        marks = ", ".join("?" for _ in values)
        cur = self._exec(
            f'INSERT INTO "{decl.table}" ({cols}) VALUES ({marks})', tuple(values.values())
        )
        self._writes += 1
        rowid = cur.lastrowid
        if rowid is None:
            raise ContractViolation(f"{decl.table}: the insert returned no rowid")
        return int(rowid)

    def _current(self, decl: TableDecl, id: int, cols: list[str]) -> sqlite3.Row:
        listed = ", ".join(f'"{c}"' for c in cols) or "1"
        row = self.fetch_one(
            f'SELECT {listed} FROM "{decl.table}" WHERE "{decl.key_column}" = ?', (id,)
        )
        if row is None:
            raise NotFound(f"{decl.table}#{id}")
        return row

    # -- the protocol ----------------------------------------------------------------------------

    def insert(self, table: str, row: Mapping[str, SqlValue]) -> int:
        self._alive()
        decl = self._own(table)
        self._class_allows(decl)
        return self._insert_row(decl, row)

    def set_once(self, table: str, id: int, /, **cols: SqlValue) -> None:
        self._alive()
        decl = self._own(table)
        self._class_allows(decl)
        if not cols:
            raise ContractViolation("set_once needs at least one column")
        bad = sorted(set(cols) - decl.set_once)
        if bad:
            raise ContractViolation(f"{table}: {', '.join(bad)} are not set-once columns")
        values = {c: _check_value(table, c, v) for c, v in cols.items()}
        if any(v is None for v in values.values()):
            raise ContractViolation(f"{table}: set_once sets a value, never NULL")
        current = self._current(decl, id, sorted(values))
        already = sorted(c for c in values if current[c] is not None)
        if already:
            raise ContractViolation(f"{table}#{id}: {', '.join(already)} already set")
        assign = ", ".join(f'"{c}" = ?' for c in values)
        self._exec(
            f'UPDATE "{table}" SET {assign} WHERE "{decl.key_column}" = ?',
            (*values.values(), id),
        )
        self._writes += 1

    def update_head(self, table: str, id: int, version: int, /, **cols: SqlValue) -> int:
        self._alive()
        decl = self._own(table)
        self._class_allows(decl)
        if not decl.versioned or decl.append_only:
            raise ContractViolation(f"{table} is not a versioned head (use update_mutable)")
        if "version" in cols:
            raise ContractViolation("update_head manages version itself")
        if not cols:
            raise ContractViolation("update_head needs at least one column")
        bad = sorted(set(cols) - decl.mutable)
        if bad:
            raise ContractViolation(f"{table}: {', '.join(bad)} are not mutable columns")
        values = {c: _check_value(table, c, v) for c, v in cols.items()}
        current = self._current(decl, id, ["version"])
        if int(current["version"]) != version:
            raise Conflict(int(current["version"]))
        assign = ", ".join(f'"{c}" = ?' for c in values)
        cur = self._exec(
            f'UPDATE "{table}" SET {assign}, "version" = "version" + 1'
            f' WHERE "{decl.key_column}" = ? AND "version" = ?',
            (*values.values(), id, version),
        )
        if cur.rowcount != 1:
            raise Conflict(int(self._current(decl, id, ["version"])["version"]))
        self._writes += 1
        return version + 1

    def update_mutable(self, table: str, key: Mapping[str, SqlValue], /, **cols: SqlValue) -> int:
        self._alive()
        decl = self._own(table)
        self._class_allows(decl)
        if decl.versioned:
            raise ContractViolation(f"{table} is a versioned head (use update_head)")
        if not key or not cols:
            raise ContractViolation("update_mutable needs a key and at least one column")
        bad = sorted(set(cols) - decl.mutable)
        if bad:
            raise ContractViolation(f"{table}: {', '.join(bad)} are not mutable columns")
        unknown = sorted(set(key) - set(decl.columns))
        if unknown:
            raise ContractViolation(f"{table}: unknown key columns {', '.join(unknown)}")
        values = {c: _check_value(table, c, v) for c, v in cols.items()}
        where = {c: _check_value(table, c, v) for c, v in key.items()}
        assign = ", ".join(f'"{c}" = ?' for c in values)
        cond = " AND ".join(f'"{c}" IS ?' for c in where)
        cur = self._exec(
            f'UPDATE "{table}" SET {assign} WHERE {cond}', (*values.values(), *where.values())
        )
        if cur.rowcount:
            self._writes += 1
        return int(cur.rowcount)

    def fetch_one(self, sql: str, params: SqlParams = ()) -> sqlite3.Row | None:
        self._alive()
        self._writer.authorizer.mode = "read"
        row: sqlite3.Row | None = self._writer.run(sql, params).fetchone()
        return row

    def fetch_all(self, sql: str, params: SqlParams = ()) -> list[sqlite3.Row]:
        self._alive()
        self._writer.authorizer.mode = "read"
        return list(self._writer.run(sql, params).fetchall())

    # -- kernel services -------------------------------------------------------------------------

    def kernel_insert(self, table: str, row: Mapping[str, SqlValue]) -> int:
        """Insert into a kernel-service table from inside any unit (kernel code only)."""
        self._alive()
        decl = self._decl(table)
        if table not in KERNEL_SERVICE_TABLES:
            raise ContractViolation(f"{table} is not a kernel-service table")
        auth = self._writer.authorizer
        auth.kernel_scope = True
        try:
            return self._insert_row(decl, row)
        finally:
            auth.kernel_scope = False

    def kernel_update(self, table: str, key: Mapping[str, SqlValue], /, **cols: SqlValue) -> int:
        """Update mutable columns of a kernel-service table (the tap's sequence, ...)."""
        self._alive()
        decl = self._decl(table)
        if table not in KERNEL_SERVICE_TABLES:
            raise ContractViolation(f"{table} is not a kernel-service table")
        bad = sorted(set(cols) - decl.mutable)
        if bad or not cols or not key:
            raise ContractViolation(f"{table}: {', '.join(bad) or 'nothing'} not mutable")
        values = {c: _check_value(table, c, v) for c, v in cols.items()}
        where = {c: _check_value(table, c, v) for c, v in key.items()}
        assign = ", ".join(f'"{c}" = ?' for c in values)
        cond = " AND ".join(f'"{c}" IS ?' for c in where)
        auth = self._writer.authorizer
        auth.kernel_scope = True
        try:
            cur = self._exec(
                f'UPDATE "{table}" SET {assign} WHERE {cond}',
                (*values.values(), *where.values()),
            )
        finally:
            auth.kernel_scope = False
        if cur.rowcount:
            self._writes += 1
        return int(cur.rowcount)

    def record_event(self, event_id: str) -> int:
        """Note an event published in this unit; returns its position (0, 1, ...)."""
        self._events.append(event_id)
        return len(self._events) - 1

    def next_event_position(self) -> int:
        return len(self._events)

    # -- idempotency -----------------------------------------------------------------------------

    def remember(self, result_json: str) -> None:
        """Store the command's result under the context's idempotency key (a retry returns it)."""
        key = self._ctx.idempotency_key
        if key is None:
            return
        if self._command is None:
            raise ContractViolation("an idempotent unit of work names its command")
        if self._remembered or self.prior_result is not None:
            raise ContractViolation(f"idempotency key {key!r} is already remembered")
        self.kernel_insert(
            "sys_command_keys", {"key": key, "command": self._command, "result_json": result_json}
        )
        self._remembered = True

    # -- data classes (POL) ----------------------------------------------------------------------

    def declare_input_class(self, data_class: str) -> None:
        """The unit's inputs include ``data_class``; journal input is refused outright (P-2)."""
        if data_class not in DATA_CLASSES:
            raise ContractViolation(f"unknown data class {data_class!r}")
        if data_class == "journal":
            own = [d for d in self._store.registry.values() if d.module == self._owner]
            if not any(d.data_class == "journal" for d in own):
                raise Refused(
                    RefusalCode.JOURNAL_CLASS_INPUT,
                    f"{self._owner!r} accepts no journal-class input",
                )
        if class_rank(data_class) < class_rank(self._input_class):
            self._input_class = data_class

    # -- erasure (POL) ---------------------------------------------------------------------------

    def erase(self, table: str, id: int, /, **cols: SqlValue) -> None:
        """Blank declared erasable columns of one row and stamp ``erased_tx`` (POL only)."""
        self._alive()
        if self._owner != "pol":
            raise ContractViolation("only POL's erasure unit erases")
        decl = self._decl(table)
        bad = sorted(set(cols) - decl.erasable)
        if bad or not cols:
            raise ContractViolation(f"{table}: {', '.join(bad) or 'nothing'} not erasable")
        values = {c: _check_value(table, c, v) for c, v in cols.items()}
        self._current(decl, id, [])
        assign = ", ".join(f'"{c}" = ?' for c in values)
        cur = self._exec(
            f'UPDATE "{table}" SET {assign}, "erased_tx" = ? WHERE "{decl.key_column}" = ?',
            (*values.values(), self._tx, id),
        )
        if cur.rowcount != 1:
            raise NotFound(f"{table}#{id}")
        self._writes += 1


@contextmanager
def run_unit(
    store: SqliteStore,
    writer: Writer,
    owner_module: str,
    ctx: CommandContext,
    *,
    command: str | None,
) -> Iterator[Unit]:
    """Open, run and close one unit of work on ``writer`` (see the module docstring)."""
    if not owner_module or not owner_module.isidentifier():
        raise ContractViolation(f"bad owner module {owner_module!r}")
    writer.acquire()
    started = time.monotonic()
    unit: Unit | None = None
    committed = False
    try:
        writer.system("BEGIN IMMEDIATE")
        try:
            committed_at = store.clock.now()
            instance = writer.system(
                "SELECT instance_id, role FROM sys_instance LIMIT 1"
            ).fetchone()
            instance_id = str(instance["instance_id"]) if instance else store.bootstrap_instance_id
            role = str(instance["role"]) if instance else store.bootstrap_role
            writer.authorizer.mode = "system"
            tx = insert_tx(
                writer.conn,
                ctx=ctx,
                committed_at=format_instant(committed_at),
                instance_role=role,
                code_version=store.code_version,
                owner_module=owner_module,
                command=command,
            )
            writer.authorizer.mode = "closed"
            unit = Unit(
                store,
                writer,
                owner_module=owner_module,
                ctx=ctx,
                command=command,
                committed_at=committed_at,
                tx=tx,
                instance_id=instance_id,
                instance_role=role,
            )
            if ctx.idempotency_key is not None:
                prior = writer.system(
                    "SELECT command, result_json, tx FROM sys_command_keys WHERE key = ?",
                    (ctx.idempotency_key,),
                ).fetchone()
                if prior is not None:
                    if command is not None and str(prior["command"]) != command:
                        raise ContractViolation(
                            f"idempotency key {ctx.idempotency_key!r} was used by"
                            f" {prior['command']!r}"
                        )
                    unit.prior_result = str(prior["result_json"])
                    unit.prior_tx = int(prior["tx"])
            yield unit
            if writer.statement_hook is not None:
                writer.statement_hook("COMMIT")
            if unit.wrote:
                writer.system("COMMIT")
                committed = True
            else:
                writer.system("ROLLBACK")
        except BaseException:
            if writer.conn.in_transaction:
                writer.system("ROLLBACK")
            raise
    finally:
        if unit is not None:
            unit._closed = True
        writer.authorizer.mode = "closed"
        writer.authorizer.owner = None
        writer.authorizer.kernel_scope = False
        writer.release()
        warn_if_slow(time.monotonic() - started, owner_module=owner_module, command=command)
    if committed and unit is not None:
        store.after_commit(unit.tx, unit.event_ids)
