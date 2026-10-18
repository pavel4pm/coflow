"""``init``, ``doctor``, roles and the data root (AT-K9; DEP-23, OPS-1, OPS-4)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from coflow import contracts
from coflow.kernel.config.profile import load_profile
from coflow.kernel.config.settings import load_settings
from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import ContractViolation, RefusalCode, Refused
from coflow.kernel.ops.doctor import run_doctor
from coflow.kernel.ops.init import init_instance, migrate_instance
from coflow.kernel.ops.instance import (
    INSTANCE_ROLES,
    check_snapshot_import,
    load_instance,
    repository_working_tree,
)
from coflow.kernel.store import api, migrations
from coflow.kernel.store.db import (
    BACKUPS_DIR,
    DB_FILE,
    INBOX_DIR,
    VOLUME_FILE,
    InstanceExists,
    InstanceNotFound,
    SqliteStore,
    open_store,
)
from coflow.kernel.store.migrations import MigrationError, SchemaMismatch
from coflow.modules.dec import api as dec_api
from tests.kernel.conftest import ModuleDirs


def _checks(root: Path) -> dict[str, tuple[bool, str]]:
    return {c.name: (c.ok, c.detail) for c in run_doctor(root).checks}


def _working_tree(path: Path) -> Path:
    """Make ``path`` a repository working tree: ``git init`` when git exists, else a ``.git``."""
    path.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if git is not None:
        subprocess.run([git, "init", "-q", str(path)], check=True, capture_output=True)
    else:
        (path / ".git").mkdir()
    return path


# --------------------------------------------------------------------------------------------------
# AT-K9: the data root of a validation instance


def test_at_k9_init_refuses_a_validation_root_inside_a_working_tree(
    module_dirs: ModuleDirs, tmp_path: Path, clock: FakeClock
) -> None:
    tree = _working_tree(tmp_path / "repo")
    root = tree / "validation-data"
    with pytest.raises(Refused) as refused:
        init_instance(root, role="validation", clock=clock, timezone="Europe/Berlin")
    assert refused.value.code is RefusalCode.DATA_ROOT_IN_REPOSITORY
    assert refused.value.allowed == ("a data root outside any repository working tree",)
    assert not root.exists(), "nothing was created"
    assert repository_working_tree(root) == tree.resolve()


def test_at_k9_doctor_refuses_a_validation_root_inside_a_working_tree(
    module_dirs: ModuleDirs, tmp_path: Path, clock: FakeClock
) -> None:
    root = tmp_path / "outer" / "validation-data"
    init_instance(root, role="validation", clock=clock, timezone="Europe/Berlin")
    checks = _checks(root)
    assert checks["role"] == (True, checks["role"][1])
    assert checks["role"][1].startswith("role: validation")
    assert checks["data_root"][0]
    _working_tree(tmp_path / "outer")  # the root now lies inside a working tree
    report = run_doctor(root)
    checks = _checks(root)
    assert not report.ok
    assert not checks["data_root"][0]
    assert "DATA_ROOT_IN_REPOSITORY" in checks["data_root"][1]


def test_at_k9_a_dev_root_may_lie_anywhere(
    module_dirs: ModuleDirs, tmp_path: Path, clock: FakeClock
) -> None:
    root = _working_tree(tmp_path / "repo") / "dev-data"
    init_instance(root, role="dev", clock=clock, timezone="Europe/Berlin")
    ok, detail = _checks(root)["data_root"]
    assert ok
    assert "allowed for dev only" in detail


@pytest.mark.parametrize(
    ("role", "synthetic", "code"),
    [
        ("dev", False, RefusalCode.IMPORT_NOT_SYNTHETIC),
        ("dev", True, None),
        ("validation", True, None),
        ("validation", False, None),
        ("drill", True, RefusalCode.IMPORT_ROLE),
        ("staging", False, RefusalCode.IMPORT_ROLE),
        ("production", False, RefusalCode.IMPORT_ROLE),
    ],
)
def test_at_k9_snapshot_roles(role: str, synthetic: bool, code: RefusalCode | None) -> None:
    if code is None:
        check_snapshot_import(role, synthetic=synthetic)
        return
    with pytest.raises(Refused) as refused:
        check_snapshot_import(role, synthetic=synthetic)
    assert refused.value.code is code


def _cfj(obj: Any) -> bytes:
    def norm(x: Any) -> Any:
        if isinstance(x, str):
            return unicodedata.normalize("NFC", x)
        if isinstance(x, list):
            return [norm(v) for v in x]
        if isinstance(x, dict):
            return {str(k): norm(v) for k, v in x.items()}
        return x

    return json.dumps(
        norm(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _snapshot(directory: Path, *, synthetic: bool) -> Path:
    body = json.loads(contracts.load_example("import_decisions_v1.example.json"))
    body["synthetic"] = synthetic
    body.pop("content_hash", None)
    body["content_hash"] = "sha256:" + hashlib.sha256(_cfj(body)).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("s1.json" if synthetic else "s1-not-synthetic.json")
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def test_at_k9_end_to_end_import_into_dev(
    dev_store: SqliteStore, tmp_path: Path, owner_ctx: CommandContext
) -> None:
    """Through ``dec.api.import_snapshot`` once track S's importer exists."""
    env = dec_api.default_env()
    plain = _snapshot(tmp_path / "inbox", synthetic=False)
    try:
        with pytest.raises(Refused) as refused:
            dec_api.import_snapshot(env, plain, mode="shadow", ctx=owner_ctx)
    except NotImplementedError:
        pytest.skip("track S's importer is not implemented yet")
    assert refused.value.code is RefusalCode.IMPORT_NOT_SYNTHETIC
    result = dec_api.import_snapshot(
        env, _snapshot(tmp_path / "inbox", synthetic=True), mode="shadow", ctx=owner_ctx
    )
    assert result.tx is not None


# --------------------------------------------------------------------------------------------------
# init


def test_init_writes_the_instance_profile_settings_and_layout(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    info = init_instance(
        data_root, role="dev", clock=clock, timezone="Europe/Berlin", issuer="TS", locale="ru"
    )
    assert info.role == "dev"
    assert info.created_at == clock.now()
    assert info.instance_id.startswith("i-")
    assert len(info.volume_id) == 32
    assert (data_root / VOLUME_FILE).read_text(encoding="utf-8").strip() == info.volume_id
    assert (data_root / INBOX_DIR).is_dir()
    store = open_store(data_root, clock=clock, read_only=True)
    try:
        with store.read_connection() as conn:
            assert load_instance(conn) == info
            profile = load_profile(conn)
            settings = load_settings(conn)
            tx_rows = conn.execute("SELECT owner_module, command FROM sys_tx_log").fetchall()
    finally:
        store.close()
    assert (profile.display_name, profile.timezone, profile.locale) == (
        "Owner",
        "Europe/Berlin",
        "ru",
    )
    assert settings["ids.issuer"] == "TS"
    assert settings["ids.foreign_issuers"] == "V1,CF2LOG"
    assert settings["owner.timezone"] == "Europe/Berlin"
    assert [tuple(r) for r in tx_rows] == [("ops", "init"), ("cfg", "init")]
    config = dec_api.model.DecConfig.from_settings(settings, timezone=profile.timezone)
    assert config.issuer == "TS"
    assert config.foreign_issuers == ("V1", "CF2LOG")


def test_init_never_overwrites_an_instance(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone="UTC")
    with pytest.raises(InstanceExists):
        init_instance(data_root, role="validation", clock=clock, timezone="UTC")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "production"},
        {"role": "drill"},
        {"timezone": "Mars/Olympus"},
        {"issuer": "V1"},
        {"issuer": "D907"},
        {"issuer": "cf"},
        {"locale": "xx"},
        {"currency": "euro"},
        {"display_name": "  "},
    ],
)
def test_init_checks_its_arguments(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock, kwargs: dict[str, str]
) -> None:
    args: dict[str, Any] = {"role": "dev", "timezone": "Europe/Berlin", **kwargs}
    with pytest.raises(ContractViolation):
        init_instance(data_root, clock=clock, **args)
    assert not (data_root / DB_FILE).exists()


def test_a_failed_init_leaves_nothing_behind(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    module_dirs.add("bad", "0001_bad.sql", "CREATE TABLE bad_items (id INTEGER PRIMARY KEY);")
    with pytest.raises(MigrationError, match=r"STRICT|registry"):
        init_instance(data_root, role="dev", clock=clock, timezone="UTC")
    assert not (data_root / DB_FILE).exists()
    assert not (data_root / VOLUME_FILE).exists()
    module_dirs.tiers.pop("bad")
    init_instance(data_root, role="dev", clock=clock, timezone="UTC")  # a retry simply works


def test_open_store_needs_an_instance(data_root: Path, clock: FakeClock) -> None:
    with pytest.raises(InstanceNotFound):
        open_store(data_root, clock=clock)
    checks = _checks(data_root)
    assert not checks["role"][0]
    assert "coflow init" in checks["role"][1]
    assert not checks["schema"][0]


# --------------------------------------------------------------------------------------------------
# doctor and the schema revision


def test_doctor_on_a_fresh_instance(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone="Europe/Berlin")
    report = run_doctor(data_root)
    assert report.ok, report.checks
    assert [c.name for c in report.checks] == ["role", "lock", "data_root", "schema", "volume"]
    assert _checks(data_root)["schema"][1].startswith("schema revision ")


def test_schema_drift_pending_changed_and_migrate(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone="UTC")
    path = module_dirs.add(
        "tst",
        "0002_more.sql",
        "CREATE TABLE tst_more (id INTEGER PRIMARY KEY, tx INTEGER NOT NULL,"
        " recorded_at TEXT NOT NULL) STRICT;\n"
        "INSERT INTO sys_table_registry (table_name, module, data_class, append_only)"
        " VALUES ('tst_more', 'tst', 'work', 1);\n",
    )
    ok, detail = _checks(data_root)["schema"]
    assert not ok
    assert "1 pending (tst/0002_more.sql)" in detail
    with pytest.raises(SchemaMismatch):
        open_store(data_root, clock=clock)

    assert migrate_instance(data_root, clock=clock) == ["tst/0002_more.sql"]
    assert list((data_root / BACKUPS_DIR).glob("pre-migrate-*.db")), "a snapshot came first"
    assert migrate_instance(data_root, clock=clock) == []
    assert run_doctor(data_root).ok
    store = open_store(data_root, clock=clock)
    try:
        assert "tst_more" in store.registry
        with store.read_connection() as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
            revision = conn.execute(
                "SELECT value FROM sys_meta WHERE key = 'schema_revision'"
            ).fetchone()[0]
            applied = migrations.applied_migrations(conn)
        assert revision == migrations.schema_revision(applied.items())
    finally:
        store.close()

    path.write_text(path.read_text(encoding="utf-8") + "-- edited after apply\n", encoding="utf-8")
    ok, detail = _checks(data_root)["schema"]
    assert not ok
    assert "changed after apply: tst/0002_more.sql" in detail
    with pytest.raises(SchemaMismatch):
        migrate_instance(data_root, clock=clock)
    path.unlink()
    ok, detail = _checks(data_root)["schema"]
    assert not ok
    assert "unknown to this code" in detail


def test_doctor_notices_a_database_from_another_volume(
    module_dirs: ModuleDirs, data_root: Path, clock: FakeClock
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone="UTC")
    (data_root / VOLUME_FILE).write_text("0" * 32, encoding="utf-8")
    assert not _checks(data_root)["volume"][0]
    (data_root / VOLUME_FILE).unlink()
    assert "missing" in _checks(data_root)["volume"][1]


def test_the_instance_role_is_in_every_tx_row(kstore: SqliteStore) -> None:
    with api.read_connection() as conn:
        roles = {r[0] for r in conn.execute("SELECT instance_role FROM sys_tx_log")}
        info = load_instance(conn)
    assert roles == {"dev"}
    assert info.role in INSTANCE_ROLES
