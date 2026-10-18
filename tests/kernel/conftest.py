"""Fixtures of the kernel suite (track K).

Kernel tests run on instances whose migrations are the kernel's own plus two synthetic test
modules, ``tst`` and ``oth``, so they exercise every store rule (append-only, set-once, erasure,
versioned heads, data classes, ownership) without depending on the DEC schema that another track
writes in parallel. Tests about the real module tables use the shared ``dev_store`` instead.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store import api as store_api
from coflow.kernel.store import migrations
from coflow.kernel.store.db import DB_FILE, SqliteStore, open_store

TST_SQL = """\
-- A synthetic module for the kernel suite: every kind of table the registry can declare.
CREATE TABLE tst_items (
  id                 INTEGER PRIMARY KEY,
  title              TEXT NOT NULL,
  note               TEXT,
  origin_recorded_at TEXT,
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL
) STRICT;

CREATE TABLE tst_heads (
  id          INTEGER PRIMARY KEY,
  public_id   TEXT NOT NULL UNIQUE,
  title       TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft',
  review_due  TEXT,
  version     INTEGER NOT NULL DEFAULT 1,
  tx          INTEGER NOT NULL,
  recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE tst_checks (
  id            INTEGER PRIMARY KEY,
  item_id       INTEGER NOT NULL REFERENCES tst_items(id),
  state         TEXT NOT NULL CHECK (state IN
                  ('HOLDING','DRIFTING','VIOLATED','UNVERIFIABLE','UNKNOWN')),
  note          TEXT,                     -- erasable; ';' inside a comment is fine
  voided_at     TEXT,
  voided_reason TEXT,
  erased_tx     INTEGER,
  tx            INTEGER NOT NULL,
  recorded_at   TEXT NOT NULL
) STRICT;

CREATE TABLE tst_stakes (
  id          INTEGER PRIMARY KEY,
  amount      TEXT NOT NULL,
  tx          INTEGER NOT NULL,
  recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE tst_counters (
  key         TEXT PRIMARY KEY,
  value       INTEGER NOT NULL,
  tx          INTEGER NOT NULL,
  recorded_at TEXT NOT NULL
) STRICT;

CREATE INDEX tst_checks_item ON tst_checks (item_id);

INSERT INTO sys_table_registry
  (table_name, module, data_class, append_only, set_once_cols, erasable_cols, mutable_cols)
VALUES
  ('tst_items',    'tst', 'work',      1, '[]', '[]', '[]'),
  ('tst_heads',    'tst', 'work',      0, '[]', '[]', '["title","status","review_due"]'),
  ('tst_checks',   'tst', 'work',      1, '["voided_at","voided_reason"]', '["note"]', '[]'),
  ('tst_stakes',   'tst', 'financial', 1, '[]', '[]', '[]'),
  ('tst_counters', 'tst', 'system',    0, '[]', '[]', '["value"]');
"""

OTH_SQL = """\
CREATE TABLE oth_items (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  tx          INTEGER NOT NULL,
  recorded_at TEXT NOT NULL
) STRICT;
INSERT INTO sys_table_registry (table_name, module, data_class, append_only)
VALUES ('oth_items', 'oth', 'work', 1);
"""


class ModuleDirs:
    """Synthetic migration sources: ``add(module, file, sql)`` writes a migration file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.tiers: dict[str, int] = {}

    def add(self, module: str, name: str, sql: str, *, tier: int = 2) -> Path:
        directory = self.root / module
        directory.mkdir(parents=True, exist_ok=True)
        self.tiers[module] = tier
        path = directory / name
        path.write_text(sql, encoding="utf-8", newline="\n")
        return path

    def sources(self) -> list[migrations.MigrationSource]:
        kernel = migrations.MigrationSource(
            module="kernel", tier=0, directory=migrations.KERNEL_DIR
        )
        extra = [
            migrations.MigrationSource(module=m, tier=t, directory=self.root / m)
            for m, t in sorted(self.tiers.items(), key=lambda kv: (kv[1], kv[0]))
        ]
        return [kernel, *extra]


@pytest.fixture
def module_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleDirs:
    """Kernel migrations plus the synthetic ``tst`` and ``oth`` modules, for this test only."""
    dirs = ModuleDirs(tmp_path / "migrations")
    dirs.add("tst", "0001_tst.sql", TST_SQL, tier=2)
    dirs.add("oth", "0001_oth.sql", OTH_SQL, tier=3)
    monkeypatch.setattr(migrations, "discover_sources", dirs.sources)
    return dirs


@pytest.fixture
def kstore(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock, owner_tz: str
) -> Iterator[SqliteStore]:
    """A ``dev`` instance with the kernel and the synthetic modules, bound as the process store."""
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    store = open_store(data_root, clock=clock)
    try:
        with store_api.use_store(store):
            yield store
    finally:
        store.close()


@pytest.fixture
def raw(data_root: Path) -> Iterator[Callable[[], sqlite3.Connection]]:
    """A direct SQLite connection to the instance, as any other client would open one."""
    opened: list[sqlite3.Connection] = []

    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(data_root / DB_FILE, isolation_level=None)
        conn.row_factory = sqlite3.Row
        opened.append(conn)
        return conn

    yield connect
    for conn in opened:
        conn.close()


@pytest.fixture
def system_ctx() -> CommandContext:
    return CommandContext(actor="system", channel="system", owner_channel=False, interaction_id="s")
