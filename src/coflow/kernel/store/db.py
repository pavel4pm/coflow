"""Opening an instance's database: WAL, ``STRICT`` tables, the writer and read connections.

Owned by track K; increment I1, spec §12.2. ``open_store`` is fixed by the skeleton (it is reached
through ``kernel.store.api.open_store``); the track implements it.

Layout of a data root (relative names only; the database never stores the root's own path):

- ``coflow.db`` (+ ``-wal`` / ``-shm``): the instance's one SQLite file;
- ``instance.lock`` and ``instance.holder.json``: the instance lock (``lock.py``);
- ``volume.id``: the random volume id written at ``init`` (DEP-2), checked by ``doctor``;
- ``inbox/snapshots/``: where snapshot files are dropped (§6.5);
- ``backups/``: the snapshot taken before a migration (OPS-4).

``open_store`` takes the instance lock (``Refused(INSTANCE_LOCKED)`` while another core holds it),
opens the single writer, refuses a schema that differs from the code's migrations
(``SchemaMismatch``) and returns a ``SqliteStore``. ``read_only=True`` opens no writer and takes no
lock: such a store only serves read connections.

Spec note: read connections open the file with ``mode=ro`` and ``query_only``, under an authorizer
that allows reads only, and each ``read_connection()`` block is one read transaction, so a query
that reads several tables sees one snapshot.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import coflow
from coflow.kernel.context import Clock, CommandContext, format_instant
from coflow.kernel.errors import CoflowError, ContractViolation, NotFound
from coflow.kernel.store import migrations as _migrations
from coflow.kernel.store.authorizer import Authorizer, read_only_authorizer
from coflow.kernel.store.lock import InstanceLock
from coflow.kernel.store.registry import TableDecl, load_registry
from coflow.kernel.store.unit import Unit, run_unit
from coflow.kernel.store.writer import BUSY_TIMEOUT_MS, StatementHook, Writer, connect_writer

__all__ = [
    "BACKUPS_DIR",
    "DB_FILE",
    "INBOX_DIR",
    "VOLUME_FILE",
    "AfterCommit",
    "InstanceExists",
    "InstanceNotFound",
    "SqliteStore",
    "create_store",
    "migrate_store",
    "open_read_connection",
    "open_store",
]

DB_FILE = "coflow.db"
VOLUME_FILE = "volume.id"
INBOX_DIR = "inbox/snapshots"
BACKUPS_DIR = "backups"

AfterCommit = Callable[[int, tuple[str, ...]], None]
"""Called after a unit commits, outside the writer, with its tx and event ids (EVT dispatch)."""

_log = logging.getLogger("coflow.kernel.store")


class InstanceNotFound(NotFound):
    """No CoFlow instance lives in the data root (``coflow init`` creates one)."""


class InstanceExists(CoflowError):
    """``init`` found an instance already in the data root; it never overwrites one."""

    type_name = "instance_exists"


def _code_version() -> str:
    return str(coflow.__version__)


def open_read_connection(db_path: Path) -> sqlite3.Connection:
    """A read-only connection to ``db_path`` (``mode=ro``, ``query_only``, read authorizer)."""
    conn = sqlite3.connect(
        Path(db_path).resolve().as_uri() + "?mode=ro",
        uri=True,
        isolation_level=None,
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_MS / 1000,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.set_authorizer(read_only_authorizer)
    return conn


class SqliteStore:
    """One instance's database: the single writer (unless read-only) plus read connections."""

    def __init__(
        self,
        data_root: Path,
        clock: Clock,
        *,
        writer: Writer | None,
        lock: InstanceLock | None,
        registry: dict[str, TableDecl],
        bootstrap_role: str = "dev",
        bootstrap_instance_id: str = "uninitialised",
    ) -> None:
        self._root = data_root
        self._clock = clock
        self._writer = writer
        self._lock = lock
        self._registry = registry
        self._after_commit: list[AfterCommit] = []
        self._closed = False
        self.bootstrap_role = bootstrap_role
        self.bootstrap_instance_id = bootstrap_instance_id
        self.code_version = _code_version()

    # -- Store protocol --------------------------------------------------------------------------

    @property
    def data_root(self) -> Path:
        return self._root

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def db_path(self) -> Path:
        return self._root / DB_FILE

    @property
    def read_only(self) -> bool:
        return self._writer is None

    @property
    def registry(self) -> dict[str, TableDecl]:
        return self._registry

    def unit_of_work(
        self, owner_module: str, ctx: CommandContext, *, command: str | None = None
    ) -> AbstractContextManager[Unit]:
        if self._closed:
            raise ContractViolation("the store is closed")
        if self._writer is None:
            raise ContractViolation("a read-only store has no writer")
        return run_unit(self, self._writer, owner_module, ctx, command=command)

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        if self._closed:
            raise ContractViolation("the store is closed")
        conn = open_read_connection(self.db_path)
        try:
            conn.execute("BEGIN")
            yield conn
        finally:
            try:
                if conn.in_transaction:
                    conn.execute("COMMIT")
            finally:
                conn.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._writer is not None:
                self._writer.close()
        finally:
            if self._lock is not None:
                self._lock.release()

    # -- extras ----------------------------------------------------------------------------------

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def statement_hook(self) -> StatementHook | None:
        return None if self._writer is None else self._writer.statement_hook

    @statement_hook.setter
    def statement_hook(self, hook: StatementHook | None) -> None:
        """Test seam: called after every statement of every unit (fault injection, AT-K5)."""
        if self._writer is None:
            raise ContractViolation("a read-only store has no writer")
        self._writer.statement_hook = hook

    def add_after_commit(self, callback: AfterCommit) -> None:
        self._after_commit.append(callback)

    def after_commit(self, tx: int, event_ids: tuple[str, ...]) -> None:
        for callback in tuple(self._after_commit):
            try:
                callback(tx, event_ids)
            except Exception:  # the unit has committed; a callback never undoes it
                _log.exception("after-commit callback failed for tx %s", tx)

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _root(data_root: Path) -> Path:
    return Path(data_root).expanduser().resolve()


def _open_writer(db_path: Path) -> Writer:
    conn = connect_writer(db_path)
    return Writer(conn, Authorizer())


def _sources() -> list[_migrations.MigrationSource]:
    return _migrations.discover_sources()


def open_store(data_root: Path, *, clock: Clock, read_only: bool = False) -> SqliteStore:
    """Open the instance in ``data_root`` under the instance lock (``INSTANCE_LOCKED`` when another
    core holds it) and return its ``Store``. ``read_only`` opens no writer."""
    root = _root(data_root)
    db_path = root / DB_FILE
    if not db_path.is_file():
        raise InstanceNotFound(str(root), "no CoFlow instance in this data root (coflow init)")
    if read_only:
        conn = open_read_connection(db_path)
        try:
            registry = load_registry(conn)
        finally:
            conn.close()
        return SqliteStore(root, clock, writer=None, lock=None, registry=registry)
    lock = InstanceLock(root).acquire("core", since=format_instant(clock.now()))
    writer: Writer | None = None
    try:
        writer = _open_writer(db_path)
        writer.authorizer.mode = "system"
        files = _migrations.code_migrations(_sources())
        status = _migrations.schema_status(writer.conn, files)
        if not status.ok:
            raise _migrations.SchemaMismatch(status)
        registry = load_registry(writer.conn)
        writer.authorizer.registry = registry
        writer.authorizer.mode = "closed"
        return SqliteStore(root, clock, writer=writer, lock=lock, registry=registry)
    except BaseException:
        if writer is not None:
            writer.conn.close()
        lock.release()
        raise


def create_store(
    data_root: Path,
    *,
    clock: Clock,
    role: str,
    instance_id: str,
    sources: Sequence[_migrations.MigrationSource] | None = None,
) -> SqliteStore:
    """Create the database of a new instance and apply every migration (``init`` only).

    The caller holds the instance lock; the returned store does not own it.
    """
    root = _root(data_root)
    db_path = root / DB_FILE
    if db_path.exists():
        raise InstanceExists(f"an instance already lives in {root.name}")
    writer = _open_writer(db_path)
    try:
        files = _migrations.code_migrations(sources if sources is not None else _sources())
        _migrations.apply_pending(
            writer.conn,
            writer.authorizer,
            files,
            applied_at=format_instant(clock.now()),
            code_version=_code_version(),
        )
        writer.authorizer.mode = "system"
        registry = load_registry(writer.conn)
        writer.authorizer.registry = registry
        writer.authorizer.mode = "closed"
    except BaseException:
        writer.conn.close()
        raise
    return SqliteStore(
        root,
        clock,
        writer=writer,
        lock=None,
        registry=registry,
        bootstrap_role=role,
        bootstrap_instance_id=instance_id,
    )


def migrate_store(data_root: Path, *, clock: Clock) -> list[str]:
    """Apply pending migrations to an existing instance under its lock, after a snapshot copy.

    Returns the applied files (empty when the schema is current). Refuses an applied file that
    changed or that the code does not know (``SchemaMismatch``).
    """
    root = _root(data_root)
    db_path = root / DB_FILE
    if not db_path.is_file():
        raise InstanceNotFound(str(root), "no CoFlow instance in this data root (coflow init)")
    now = clock.now()
    with InstanceLock(root).acquire("migrate", since=format_instant(now)):
        writer = _open_writer(db_path)
        try:
            writer.authorizer.mode = "system"
            files = _migrations.code_migrations(_sources())
            status = _migrations.schema_status(writer.conn, files)
            if status.unknown or status.changed:
                raise _migrations.SchemaMismatch(status)
            if not status.pending:
                return []
            backups = root / BACKUPS_DIR
            backups.mkdir(exist_ok=True)
            stamp = format_instant(now).replace(":", "").replace("-", "").replace(".", "")
            target = backups / f"pre-migrate-{stamp}.db"
            writer.conn.execute("VACUUM INTO ?", (str(target),))
            return _migrations.apply_pending(
                writer.conn,
                writer.authorizer,
                files,
                applied_at=format_instant(now),
                code_version=_code_version(),
            )
        finally:
            writer.authorizer.mode = "system"
            writer.conn.close()
