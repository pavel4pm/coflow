"""Numbered, forward-only migrations (OPS-4): kernel files first, then module files in tier order;
checksums in ``sys_migrations``; triggers generated after each file (see ``api.py`` for the file
contract).

Owned by track K (kernel); increment I1, spec §12.2.

- **Discovery.** Kernel files live in ``coflow/migrations/kernel/``, module files in
  ``coflow/modules/<mod>/migrations/``, named ``NNNN_<name>.sql``. They are found on the file
  system, so the kernel never imports a module. Order: kernel, then modules by tier (the tiers of
  ARCHITECTURE §5.1 and ``.importlinter``) and name, then by number.
- **One transaction per file.** The file's statements run under the authorizer in ``migrate`` mode
  for its module (DDL only on the module's own prefix). Then the runner checks the contract
  (``registry.validate_decl``: owner, data class, ``STRICT``, prefix, ``tx`` / ``recorded_at``,
  declared columns), regenerates the triggers of every registered table, records the file and its
  checksum in ``sys_migrations``, and sets ``sys_meta.schema_revision`` and ``PRAGMA
  user_version``. Any problem rolls the whole file back.
- **Forward-only.** An applied file never changes: its checksum (SHA-256 of the file with LF line
  endings) is compared on every open, and ``open_store`` refuses a database whose applied files
  differ from the code's (``SchemaMismatch``). Migrations run at ``init`` and by
  ``ops.init.migrate_instance`` (a deploy step, with a snapshot first), never on service start.

Spec note: OPS-4 says migrations "run once as a deploy step ... never on service start", so a core
started on a database that lacks a file refuses with ``SchemaMismatch`` instead of migrating.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from coflow.kernel.errors import CoflowError
from coflow.kernel.store.authorizer import Authorizer
from coflow.kernel.store.registry import KERNEL_OWNERS, load_registry, owner_prefixes, validate_decl
from coflow.kernel.store.triggers import regenerate_triggers

__all__ = [
    "KERNEL_DIR",
    "MODULES_DIR",
    "MODULE_TIERS",
    "MigrationError",
    "MigrationFile",
    "MigrationSource",
    "SchemaMismatch",
    "SchemaStatus",
    "applied_migrations",
    "apply_pending",
    "code_migrations",
    "discover_sources",
    "schema_revision",
    "schema_status",
    "split_statements",
]

_PACKAGE = Path(__file__).resolve().parents[2]  # .../coflow
KERNEL_DIR = _PACKAGE / "migrations" / "kernel"
MODULES_DIR = _PACKAGE / "modules"

# The domain tiers of ARCHITECTURE §5.1 (and the ``domain`` contract in ``.importlinter``).
MODULE_TIERS: Mapping[str, int] = {
    "ppl": 1,
    "jrn": 1,
    "cal": 1,
    "sig": 2,
    "dec": 2,
    "cmt": 3,
    "fin": 3,
    "wrk": 4,
    "tax": 4,
    "mtg": 5,
    "rhy": 6,
    "src": 6,
    "tml": 6,
    "lrn": 6,
    "gol": 7,
    "aln": 8,
}

_FILE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


class MigrationError(CoflowError):
    """A migration file broke the file contract; nothing of it was applied."""

    type_name = "migration_error"

    def __init__(self, file: str, problems: Sequence[str]) -> None:
        self.file = file
        self.problems = tuple(problems)
        self.detail = f"{file}: " + "; ".join(self.problems)
        super().__init__(self.detail)


class SchemaMismatch(CoflowError):
    """The database's applied migrations differ from the code's (pending, unknown or changed)."""

    type_name = "schema_mismatch"

    def __init__(self, status: SchemaStatus) -> None:
        self.status = status
        self.detail = status.summary()
        super().__init__(self.detail)


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrationSource:
    """One directory of migration files and the module that owns them (``kernel`` for STO's)."""

    module: str
    tier: int
    directory: Path

    @property
    def is_kernel(self) -> bool:
        return self.module == "kernel"

    @property
    def owners(self) -> tuple[str, ...]:
        """The registry modules this source may register tables for."""
        return tuple(KERNEL_OWNERS) if self.is_kernel else (self.module,)

    @property
    def prefixes(self) -> tuple[str, ...]:
        return tuple(sorted({p for owner in self.owners for p in owner_prefixes(owner)}))


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrationFile:
    source: MigrationSource
    number: int
    name: str  # "0001_kernel.sql"
    sql: str  # LF line endings
    checksum: str

    @property
    def key(self) -> str:
        """The ``sys_migrations.file`` value: ``kernel/0001_kernel.sql``, ``dec/0001_dec.sql``."""
        return f"{self.source.module}/{self.name}"


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemaStatus:
    """The code's migrations against the database's ``sys_migrations``."""

    code_revision: str
    db_revision: str
    applied: int
    pending: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not (self.pending or self.unknown or self.changed)

    def summary(self) -> str:
        if self.ok:
            return f"schema revision {self.db_revision[:12]} ({self.applied} migrations)"
        parts = []
        if self.pending:
            parts.append(f"{len(self.pending)} pending ({', '.join(self.pending)}): run migrate")
        if self.unknown:
            parts.append(f"applied but unknown to this code: {', '.join(self.unknown)}")
        if self.changed:
            parts.append(f"changed after apply: {', '.join(self.changed)}")
        return "; ".join(parts)


def discover_sources() -> list[MigrationSource]:
    """The kernel's migration directory and every module's, in apply order."""
    sources = [MigrationSource(module="kernel", tier=0, directory=KERNEL_DIR)]
    modules: list[MigrationSource] = []
    if MODULES_DIR.is_dir():
        for child in sorted(MODULES_DIR.iterdir()):
            mig = child / "migrations"
            if not child.is_dir() or not mig.is_dir() or not any(mig.glob("*.sql")):
                continue
            if child.name not in MODULE_TIERS:
                raise MigrationError(str(mig), [f"module {child.name!r} has no tier"])
            modules.append(
                MigrationSource(module=child.name, tier=MODULE_TIERS[child.name], directory=mig)
            )
    modules.sort(key=lambda s: (s.tier, s.module))
    return sources + modules


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def code_migrations(sources: Iterable[MigrationSource]) -> list[MigrationFile]:
    """Every migration file of ``sources``, in apply order (kernel first, then tiers)."""
    files: list[MigrationFile] = []
    ordered = sorted(sources, key=lambda s: (0 if s.is_kernel else 1, s.tier, s.module))
    for source in ordered:
        seen: dict[int, str] = {}
        found: list[MigrationFile] = []
        for path in sorted(source.directory.glob("*.sql")):
            m = _FILE.match(path.name)
            if m is None:
                raise MigrationError(str(path), ["migration files are named NNNN_<name>.sql"])
            number = int(m.group(1))
            if number in seen:
                raise MigrationError(path.name, [f"number {number} is also {seen[number]}"])
            seen[number] = path.name
            sql = _read(path)
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            found.append(
                MigrationFile(
                    source=source, number=number, name=path.name, sql=sql, checksum=checksum
                )
            )
        files.extend(sorted(found, key=lambda f: f.number))
    return files


def schema_revision(pairs: Iterable[tuple[str, str]]) -> str:
    """One hash over (file, checksum) pairs: equal for the same set of applied files."""
    body = "\n".join(sorted(f"{key}:{checksum}" for key, checksum in pairs))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def applied_migrations(conn: sqlite3.Connection) -> dict[str, str]:
    """``file -> checksum`` from ``sys_migrations`` (empty before the kernel migration)."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'sys_migrations'"
    ).fetchone()
    if exists is None:
        return {}
    return {
        str(f): str(c)
        for f, c in conn.execute("SELECT file, checksum FROM sys_migrations ORDER BY rowid")
    }


def schema_status(conn: sqlite3.Connection, files: Sequence[MigrationFile]) -> SchemaStatus:
    applied = applied_migrations(conn)
    code = {f.key: f.checksum for f in files}
    return SchemaStatus(
        code_revision=schema_revision(code.items()),
        db_revision=schema_revision(applied.items()),
        applied=len(applied),
        pending=tuple(k for k in code if k not in applied),
        unknown=tuple(k for k in applied if k not in code),
        changed=tuple(k for k in code if k in applied and applied[k] != code[k]),
    )


def _has_code(chunk: str) -> bool:
    text = re.sub(r"/\*.*?\*/", "", chunk, flags=re.S)
    text = re.sub(r"--[^\n]*", "", text)
    return bool(text.strip(" \t\r\n;"))


def split_statements(sql: str) -> list[str]:
    """Split a file into complete statements (strings, comments and trigger bodies respected)."""
    out: list[str] = []
    start = 0
    for i, ch in enumerate(sql):
        if ch != ";":
            continue
        candidate = sql[start : i + 1]
        if sqlite3.complete_statement(candidate):
            if _has_code(candidate):
                out.append(candidate.strip())
            start = i + 1
    if _has_code(sql[start:]):
        raise ValueError("the file ends inside an unterminated statement")
    return out


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(r[0])
        for r in conn.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _registry_rows(conn: sqlite3.Connection) -> dict[str, tuple[object, ...]]:
    if "sys_table_registry" not in _tables(conn):
        return {}
    return {
        str(r[0]): tuple(r[1:])
        for r in conn.execute(
            "SELECT table_name, module, data_class, append_only, set_once_cols, erasable_cols,"
            " mutable_cols FROM sys_table_registry"
        )
    }


def apply_pending(
    conn: sqlite3.Connection,
    authorizer: Authorizer,
    files: Sequence[MigrationFile],
    *,
    applied_at: str,
    code_version: str,
) -> list[str]:
    """Apply every file of ``files`` that is not applied yet; returns the applied keys.

    Refuses (``SchemaMismatch``) when an applied file changed or is unknown to the code: the
    schema only moves forward along the code's own files.
    """
    status = schema_status(conn, files)
    if status.unknown or status.changed:
        raise SchemaMismatch(status)
    applied = applied_migrations(conn)
    done: list[str] = []
    for file in files:
        if file.key in applied:
            continue
        _apply_one(conn, authorizer, file, applied_at=applied_at, code_version=code_version)
        applied[file.key] = file.checksum
        done.append(file.key)
    return done


def _apply_one(
    conn: sqlite3.Connection,
    authorizer: Authorizer,
    file: MigrationFile,
    *,
    applied_at: str,
    code_version: str,
) -> None:
    try:
        statements = split_statements(file.sql)
    except ValueError as exc:
        raise MigrationError(file.key, [str(exc)]) from exc
    authorizer.mode = "system"
    conn.execute("BEGIN IMMEDIATE")
    try:
        tables_before = _tables(conn)
        registry_before = set(load_registry(conn))
        rows_before = _registry_rows(conn)
        authorizer.mode = "migrate"
        authorizer.migrate_prefixes = file.source.prefixes
        for stmt in statements:
            try:
                conn.execute(stmt)
            except sqlite3.DatabaseError as exc:
                head = " ".join(stmt.split())[:80]
                raise MigrationError(file.key, [f"{exc} in: {head}"]) from exc
        authorizer.mode = "system"
        authorizer.migrate_prefixes = ()
        registry = load_registry(conn)
        problems: list[str] = []
        for table in sorted(_tables(conn) - tables_before):
            if table not in registry:
                problems.append(f"{table}: no sys_table_registry row")
        owners = set(file.source.owners)
        for name in sorted(set(registry) - registry_before):
            if registry[name].module not in owners:
                problems.append(f"{name}: registered for {registry[name].module!r}")
        rows_after = _registry_rows(conn)
        for name, row in sorted(rows_before.items()):
            if row[0] not in owners and rows_after.get(name) != row:
                problems.append(f"{name}: another module's registry row changed")
        for decl in registry.values():
            if decl.module in owners:
                problems.extend(validate_decl(conn, decl, allowed_modules=owners))
        if problems:
            raise MigrationError(file.key, problems)
        regenerate_triggers(conn, registry.values())
        conn.execute(
            "INSERT INTO sys_migrations (file, module, checksum, applied_at) VALUES (?, ?, ?, ?)",
            (file.key, file.source.module, file.checksum, applied_at),
        )
        applied = applied_migrations(conn)
        for key, value in (
            ("schema_revision", schema_revision(applied.items())),
            ("code_version", code_version),
        ):
            conn.execute(
                "INSERT INTO sys_meta (key, value) VALUES (?, ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        conn.execute(f"PRAGMA user_version = {len(applied)}")
        conn.execute("COMMIT")
    except BaseException:
        authorizer.mode = "system"
        conn.execute("ROLLBACK")
        raise
    finally:
        authorizer.mode = "closed"
        authorizer.migrate_prefixes = ()
