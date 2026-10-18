"""The migration runner and the table-registry contract (OPS-4, NFR-13, ARCHITECTURE §5.3)."""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from coflow.kernel.context import FakeClock
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store import migrations
from coflow.kernel.store.db import DB_FILE, SqliteStore
from coflow.kernel.store.migrations import MigrationError, split_statements
from tests.kernel.conftest import ModuleDirs

REPO = Path(__file__).resolve().parents[2]

_GOOD_TABLE = (
    "CREATE TABLE {t} (id INTEGER PRIMARY KEY, title TEXT, tx INTEGER NOT NULL,"
    " recorded_at TEXT NOT NULL) STRICT;\n"
)


def _registry(table: str, module: str = "bad", extra: str = "1, '[]', '[]', '[]'") -> str:
    return (
        "INSERT INTO sys_table_registry (table_name, module, data_class, append_only,"
        f" set_once_cols, erasable_cols, mutable_cols) VALUES ('{table}', '{module}', 'work',"
        f" {extra});\n"
    )


def _init(root: Path, clock: FakeClock) -> None:
    init_instance(root, role="dev", clock=clock, timezone="UTC")


def test_split_statements_respects_strings_comments_and_trigger_bodies() -> None:
    sql = (
        "-- a comment; with a semicolon\n"
        "CREATE TABLE x (a TEXT DEFAULT 'one;two') STRICT; INSERT INTO x VALUES ('a;b');\n"
        "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1; SELECT 2; END;\n"
        "/* block; comment */\n"
    )
    out = split_statements(sql)
    assert len(out) == 3
    assert out[2].startswith("CREATE TRIGGER")
    assert out[2].endswith("END;")
    with pytest.raises(ValueError, match="unterminated"):
        split_statements("CREATE TABLE y (a TEXT)")
    assert split_statements("-- only comments\n") == []


def test_kernel_runs_first_then_modules_by_tier(module_dirs: ModuleDirs) -> None:
    module_dirs.add("aaa", "0001_aaa.sql", "", tier=5)
    module_dirs.add("zzz", "0001_zzz.sql", "", tier=1)
    files = migrations.code_migrations(module_dirs.sources())
    assert [f.key for f in files] == [
        "kernel/0001_kernel.sql",
        "zzz/0001_zzz.sql",
        "tst/0001_tst.sql",
        "oth/0001_oth.sql",
        "aaa/0001_aaa.sql",
    ]


def test_file_names_and_numbers_are_checked(module_dirs: ModuleDirs) -> None:
    module_dirs.add("tst", "0001_again.sql", "")
    with pytest.raises(MigrationError, match="number 1"):
        migrations.code_migrations(module_dirs.sources())
    module_dirs.add("odd", "first.sql", "")
    with pytest.raises(MigrationError, match="NNNN_"):
        migrations.code_migrations(module_dirs.sources())


def test_checksums_ignore_line_endings(tmp_path: Path) -> None:
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    for directory, text in ((lf, "SELECT 1;\n"), (crlf, "SELECT 1;\r\n")):
        directory.mkdir()
        (directory / "0001_x.sql").write_bytes(text.encode())
    sums = [
        migrations.code_migrations([migrations.MigrationSource(module="x", tier=1, directory=d)])[
            0
        ].checksum
        for d in (lf, crlf)
    ]
    assert sums[0] == sums[1]


def test_module_tiers_agree_with_the_import_contract() -> None:
    parser = configparser.ConfigParser()
    parser.read(REPO / ".importlinter", encoding="utf-8")
    layers = parser["importlinter:contract:domain"]["layers"].split("\n")
    tiers: dict[str, int] = {}
    for tier, line in enumerate(reversed([ln for ln in layers if ln.strip()]), start=1):
        for name in line.split("|"):
            tiers[name.strip().strip("()")] = tier
    assert tiers == dict(migrations.MODULE_TIERS)


def test_the_real_sources_are_discovered() -> None:
    sources = migrations.discover_sources()
    assert sources[0].module == "kernel"
    for source in sources[1:]:
        assert migrations.MODULE_TIERS[source.module] == source.tier
    assert [s.tier for s in sources[1:]] == sorted(s.tier for s in sources[1:])


@pytest.mark.parametrize(
    ("sql", "match"),
    [
        (
            "CREATE TABLE bad_x (id INTEGER PRIMARY KEY, tx INTEGER NOT NULL,"
            " recorded_at TEXT NOT NULL);\n" + _registry("bad_x"),
            "STRICT",
        ),
        (_GOOD_TABLE.format(t="bad_x"), "no sys_table_registry row"),
        (_GOOD_TABLE.format(t="tst_x") + _registry("tst_x", "tst"), "not authorized"),
        (_GOOD_TABLE.format(t="bad_x") + _registry("bad_x", "tst"), "registered for 'tst'"),
        (
            "CREATE TABLE bad_x (id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL) STRICT;\n"
            + _registry("bad_x"),
            "tx INTEGER NOT NULL",
        ),
        (
            "CREATE TABLE bad_x (id INTEGER PRIMARY KEY, tx INTEGER NOT NULL) STRICT;\n"
            + _registry("bad_x"),
            "recorded_at",
        ),
        (
            _GOOD_TABLE.format(t="bad_x") + _registry("bad_x", extra="1, '[\"gone\"]', '[]', '[]'"),
            "'gone' does not exist",
        ),
        (
            _GOOD_TABLE.format(t="bad_x")
            + _registry("bad_x", extra="1, '[]', '[\"title\"]', '[]'"),
            "erased_tx",
        ),
        (
            _GOOD_TABLE.format(t="bad_x")
            + _registry("bad_x", extra="1, '[]', '[]', '[\"title\"]'"),
            "append-only table has no mutable",
        ),
        (
            _GOOD_TABLE.format(t="bad_x") + _registry("bad_x", extra="0, '[]', '[]', '[\"tx\"]'"),
            "stamped by the store",
        ),
        (
            _GOOD_TABLE.format(t="bad_x") + _registry("bad_x", extra="0, '[]', '[]', 'title'"),
            "JSON",
        ),
        ("ATTACH DATABASE ':memory:' AS other;\n", "not authorized"),
        ("PRAGMA foreign_keys = OFF;\n", "not authorized"),
        ("BEGIN; COMMIT;\n", "not authorized"),
        ("DELETE FROM sys_table_registry WHERE table_name = 'tst_items';\n", "not authorized"),
        (
            "UPDATE sys_table_registry SET append_only = 0 WHERE table_name = 'tst_items';\n",
            "another module's registry row",
        ),
        ("UPDATE sys_meta SET value = 'x';\n", "not authorized"),
        (
            _GOOD_TABLE.format(t="bad_x")
            + _registry("bad_x")
            + "CREATE TRIGGER coflow_bad_x__title BEFORE UPDATE ON bad_x BEGIN SELECT 1; END;\n",
            "not authorized",
        ),
        ("CREATE TABLE bad_x (id INTEGER PRIMARY KEY) STRICT", "unterminated"),
    ],
)
def test_the_file_contract_is_enforced(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock, sql: str, match: str
) -> None:
    module_dirs.add("bad", "0001_bad.sql", sql, tier=4)
    with pytest.raises((MigrationError, ValueError), match=match):
        _init(data_root, clock)
    assert not (data_root / DB_FILE).exists()


def test_a_later_file_may_extend_its_own_registry_row(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock, raw: object
) -> None:
    module_dirs.add(
        "tst",
        "0002_note.sql",
        "ALTER TABLE tst_items ADD COLUMN extra TEXT;\n"
        "UPDATE sys_table_registry SET set_once_cols = '[\"extra\"]'"
        " WHERE table_name = 'tst_items';\n",
    )
    _init(data_root, clock)
    import sqlite3

    conn = sqlite3.connect(data_root / DB_FILE)
    try:
        conn.execute("INSERT INTO tst_items (title, tx, recorded_at) VALUES ('x', 1, '2026-11-15')")
        conn.execute("UPDATE tst_items SET extra = 'once'")
        with pytest.raises(sqlite3.IntegrityError, match="extra is set once"):
            conn.execute("UPDATE tst_items SET extra = 'twice'")
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
    finally:
        conn.close()


def test_every_table_of_a_dev_instance_follows_the_contract(dev_store: SqliteStore) -> None:
    """Fitness over the real migrations: every table has an owner, a class and STRICT."""
    from coflow.kernel.store.registry import KERNEL_OWNERS, validate_decl

    with dev_store.read_connection() as conn:
        tables = {
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        registry = dev_store.registry
        assert tables == set(registry), "every table is registered and every row has a table"
        for decl in registry.values():
            owners = list(KERNEL_OWNERS) if decl.module in KERNEL_OWNERS else [decl.module]
            assert validate_decl(conn, decl, allowed_modules=owners) == []
    kernel = {t for t, d in registry.items() if d.module in KERNEL_OWNERS}
    assert {
        "sys_meta",
        "sys_migrations",
        "sys_table_registry",
        "sys_tx_log",
        "sys_id_prefixes",
        "sys_id_sequence",
        "sys_id_burned",
        "sys_id_foreign",
        "sys_id_aliases",
        "sys_events",
        "sys_event_deliveries",
        "sys_command_keys",
        "sys_instance",
        "cfg_profile",
        "cfg_settings",
        "sys_usage_signals",
        "mcp_clients",
        "mcp_call_log",
        "adm_tokens",
    } == kernel
    assert all(d.data_class != "journal" for d in registry.values())
