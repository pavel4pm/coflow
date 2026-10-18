"""The instance lock: one core per data root, the CLI's ephemeral core under the same lock (AT-K7;
OPS-3).

The kernel's part of AT-K7: a second core refuses (``INSTANCE_LOCKED``), in this process and in
another one; once the running core stops, an ephemeral core takes the same lock; a read-only store
needs no lock. The admin-API path and the stdio shim are track X's half of AT-K7.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from coflow.kernel.context import FakeClock
from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.ops.doctor import run_doctor
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store import api, migrations
from coflow.kernel.store.db import open_store
from coflow.kernel.store.lock import InstanceLock, probe_lock, read_holder
from tests.kernel.conftest import ModuleDirs
from tests.kernel.helpers import ctx


@pytest.fixture
def instance(module_dirs: ModuleDirs, data_root: Path, clock: FakeClock, owner_tz: str) -> Path:
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    return data_root


def _doctor_lock(root: Path) -> str:
    return next(c.detail for c in run_doctor(root).checks if c.name == "lock")


def test_at_k7_the_second_core_refuses(instance: Path, clock: FakeClock) -> None:
    core = open_store(instance, clock=clock)
    try:
        with pytest.raises(Refused) as refused:
            open_store(instance, clock=clock)
        assert refused.value.code is RefusalCode.INSTANCE_LOCKED
        assert "admin API" in " ".join(refused.value.allowed)
        holder = read_holder(instance)
        assert holder is not None
        assert holder.purpose == "core"
        assert _doctor_lock(instance).startswith("held by a running core")
        with pytest.raises(Refused):
            InstanceLock(instance).acquire("ephemeral")
    finally:
        core.close()
    assert probe_lock(instance).free
    assert _doctor_lock(instance).startswith("free")


def test_at_k7_an_ephemeral_core_runs_once_the_core_stops(instance: Path, clock: FakeClock) -> None:
    core = open_store(instance, clock=clock)
    core.close()
    ephemeral = open_store(instance, clock=clock)
    try:
        assert not probe_lock(instance).free  # it holds the same lock
        with api.use_store(ephemeral), api.unit_of_work("tst", ctx(), command="cli_write"):
            api.insert("tst_items", {"title": "Written by the CLI's ephemeral core"})
    finally:
        ephemeral.close()
    assert probe_lock(instance).free

    # the write is durable in the same store: committed once, with its transaction-log row
    reader = open_store(instance, clock=clock, read_only=True)
    try:
        with reader.read_connection() as conn:
            written = conn.execute(
                "SELECT count(*) FROM tst_items WHERE title = ?",
                ("Written by the CLI's ephemeral core",),
            ).fetchone()[0]
            logged = conn.execute(
                "SELECT count(*) FROM sys_tx_log WHERE command = 'cli_write'"
            ).fetchone()[0]
    finally:
        reader.close()
    assert written == 1
    assert logged == 1


def test_at_k7_a_read_only_store_takes_no_lock(instance: Path, clock: FakeClock) -> None:
    core = open_store(instance, clock=clock)
    try:
        reader = open_store(instance, clock=clock, read_only=True)
        with reader.read_connection() as conn:
            assert conn.execute("SELECT role FROM sys_instance").fetchone()[0] == "dev"
        reader.close()
    finally:
        core.close()


_HOLDER = textwrap.dedent(
    """
    import sys
    from datetime import UTC, datetime
    from pathlib import Path
    from coflow.kernel.context import FakeClock
    from coflow.kernel.store import migrations
    from coflow.kernel.store.db import open_store

    kernel = migrations.MigrationSource(module="kernel", tier=0, directory=migrations.KERNEL_DIR)
    migrations.discover_sources = lambda: [kernel]
    store = open_store(Path(sys.argv[1]), clock=FakeClock(datetime(2026, 11, 15, tzinfo=UTC)))
    print("ready", flush=True)
    sys.stdin.readline()
    store.close()
    print("closed", flush=True)
    """
)


def test_at_k7_a_core_in_another_process_holds_the_lock(
    data_root: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = migrations.MigrationSource(module="kernel", tier=0, directory=migrations.KERNEL_DIR)
    monkeypatch.setattr(migrations, "discover_sources", lambda: [kernel])
    init_instance(data_root, role="dev", clock=clock, timezone="Europe/Berlin")

    with subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(data_root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as proc:
        assert proc.stdout is not None
        assert proc.stdin is not None
        try:
            line = proc.stdout.readline().strip()
            if line != "ready":
                proc.kill()
                pytest.fail(f"the holder process did not start: {proc.communicate()[1]}")
            with pytest.raises(Refused) as refused:
                open_store(data_root, clock=clock)
            assert refused.value.code is RefusalCode.INSTANCE_LOCKED
            holder = read_holder(data_root)
            # The pid is the interpreter's; a launcher on Windows may have started it as a child.
            assert holder is not None
            assert holder.purpose == "core"
            assert holder.pid != os.getpid()
            assert not probe_lock(data_root).free
            proc.stdin.write("stop\n")
            proc.stdin.flush()
            assert proc.stdout.readline().strip() == "closed"
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)
    store = open_store(data_root, clock=clock)  # the ephemeral core, once the other one stopped
    store.close()
