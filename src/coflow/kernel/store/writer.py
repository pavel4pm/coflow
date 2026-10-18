"""The single writer: one write connection, units of work serialised on it (AP-1, OPS-3, spec
§4.5).

Owned by track K (kernel); increment I1, spec §12.2.

``Writer`` owns the instance's only write connection. A unit of work holds the writer for its whole
duration, so units are serialised: a second unit from another thread waits for the first; a second
unit from the same thread is a ``ContractViolation`` (units do not nest). The connection runs in
WAL mode with ``synchronous = NORMAL``, foreign keys and recursive triggers on, SQLite's defensive
mode on and the statement cache off (the authorizer must see every statement, see
``authorizer.py``).

Spec note: §4.5 speaks of a "writer thread". With units written as ``with`` blocks, the caller's
thread runs the block while it holds the writer, which gives the same guarantee (one connection,
one unit at a time, nothing else writing) without moving closures between threads. A unit that
holds the writer longer than ``SLOW_UNIT_SECONDS`` is logged (OPS-3's watchdog, minimal form).
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

from coflow.kernel.errors import ContractViolation
from coflow.kernel.store.api import SqlParams
from coflow.kernel.store.authorizer import Authorizer

__all__ = ["SLOW_UNIT_SECONDS", "StatementHook", "Writer", "connect_writer", "translate"]

SLOW_UNIT_SECONDS = 10.0
BUSY_TIMEOUT_MS = 30_000

_log = logging.getLogger("coflow.kernel.store")

StatementHook = Callable[[str], None]
"""Called after every statement a unit executes (a test seam for fault injection, AT-K5)."""


def connect_writer(db_path: Path) -> sqlite3.Connection:
    """Open the write connection with the store's pragmas (no authorizer yet)."""
    conn = sqlite3.connect(
        str(db_path),
        isolation_level=None,
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_MS / 1000,
        cached_statements=0,
    )
    conn.row_factory = sqlite3.Row
    mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()
    if mode is None or str(mode[0]).lower() != "wal":
        conn.close()
        raise ContractViolation(f"{db_path.name}: WAL mode is required (got {mode!r})")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    return conn


def translate(exc: sqlite3.DatabaseError, sql: str) -> Exception:
    """A kernel error for SQLite's refusals: generated triggers and the authorizer."""
    message = str(exc)
    if message.startswith("coflow:"):
        return ContractViolation(message)
    if "not authorized" in message:
        head = " ".join(sql.split())[:60]
        return ContractViolation(f"not authorized in this unit of work: {head}")
    return exc


class Writer:
    """The one write connection of a store and the lock that serialises units on it."""

    def __init__(self, conn: sqlite3.Connection, authorizer: Authorizer) -> None:
        self.conn = conn
        self.authorizer = authorizer
        self._lock = threading.Lock()
        self._owner: int | None = None
        self.statement_hook: StatementHook | None = None
        conn.set_authorizer(authorizer)

    @property
    def busy(self) -> bool:
        return self._owner is not None

    def acquire(self) -> None:
        me = threading.get_ident()
        if self._owner == me:
            raise ContractViolation("units of work do not nest")
        self._lock.acquire()
        self._owner = me

    def release(self) -> None:
        self._owner = None
        self._lock.release()

    def system(self, sql: str, params: SqlParams = ()) -> sqlite3.Cursor:
        """Run one of the store's own statements (BEGIN, COMMIT, the tx row) in ``system`` mode."""
        previous = self.authorizer.mode
        self.authorizer.mode = "system"
        try:
            return self.conn.execute(sql, params)
        finally:
            self.authorizer.mode = previous

    def run(self, sql: str, params: SqlParams = ()) -> sqlite3.Cursor:
        """Run a statement under the current mode; refusals become ``ContractViolation``."""
        try:
            cur = self.conn.execute(sql, params)
        except sqlite3.DatabaseError as exc:
            raise translate(exc, sql) from exc
        if self.statement_hook is not None:
            self.statement_hook(sql)
        return cur

    def close(self) -> None:
        self.authorizer.mode = "system"
        with contextlib.suppress(sqlite3.DatabaseError):
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.conn.close()


def warn_if_slow(seconds: float, *, owner_module: str, command: str | None) -> None:
    if seconds > SLOW_UNIT_SECONDS:
        _log.warning(
            "unit of work %s/%s held the writer for %.1f s", owner_module, command, seconds
        )
