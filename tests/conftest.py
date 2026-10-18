"""Shared fixtures (spec §12.1, §9.1): the fixture world every track's tests use.

- ``clock``: a ``FakeClock`` at 2026-11-15T09:30:00.000Z, i.e. 10:30 on 15 November 2026 in the
  owner's zone ``Europe/Berlin`` (``owner_tz``); ``today`` is that date.
- ``data_root``: a fresh temp data root, guaranteed outside any repository working tree.
- ``fixtures``: the loader for ``tests/fixtures/synthetic/``.
- ``dev_store``: a ``dev`` instance initialised in ``data_root`` and bound as the process store
  (needs track K's ``init_instance`` and ``open_store``).
- ``owner_ctx`` / ``mcp_ctx``: command contexts of the owner's CLI and of an MCP client.
- ``fake_*``: the port fakes of ``tests/fakes``.

Every test runs offline: a guard refuses socket connections to anything but loopback.
"""

from __future__ import annotations

import json
import shutil
import socket
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store import api as store_api
from coflow.kernel.store.api import Store
from tests.fakes import (
    FakeAttachmentProbe,
    FakeDecisionDirectory,
    FakeEvidenceResolver,
    FakeGoalDirectory,
    FakeUndoHandler,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "synthetic"

OWNER_TZ = "Europe/Berlin"
TEST_NOW = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
TEST_TODAY = date(2026, 11, 15)

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


# --------------------------------------------------------------------------------------------------
# Offline guard and store hygiene


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse any socket connection that is not loopback: tests never touch the network."""
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def _host(address: object) -> str:
        if isinstance(address, tuple) and address:
            return str(address[0])
        return str(address)  # AF_UNIX paths and other families stay local

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if self.family in (socket.AF_INET, socket.AF_INET6) and _host(address) not in _LOOPBACK:
            raise RuntimeError(f"tests are offline: refused connection to {address!r}")
        return real_connect(self, address)

    def guarded_create(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        if _host(address) not in _LOOPBACK:
            raise RuntimeError(f"tests are offline: refused connection to {address!r}")
        return real_create(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create)


@pytest.fixture(autouse=True)
def _no_store_leak() -> Iterator[None]:
    """No test leaves a store bound for the next one."""
    yield
    store_api.unbind_store()


# --------------------------------------------------------------------------------------------------
# The fixture world


@pytest.fixture
def owner_tz() -> str:
    return OWNER_TZ


@pytest.fixture
def today() -> date:
    return TEST_TODAY


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(TEST_NOW)


def _inside_working_tree(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return None


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """A fresh data root outside any repository working tree (``doctor`` refuses one inside)."""
    root = tmp_path / "coflow-data"
    root.mkdir()
    tree = _inside_working_tree(root)
    if tree is not None:
        pytest.fail(
            f"the temp data root {root} lies inside the working tree {tree}; set --basetemp"
        )
    return root


class FixtureLoader:
    """Reads ``tests/fixtures/synthetic/``; ``copy_to`` puts a fixture into a temp directory (an
    import reads a file the way the owner's inbox would hold it)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"{rel} is outside the synthetic fixtures")
        if not p.exists():
            raise FileNotFoundError(p)
        return p

    def bytes(self, rel: str) -> bytes:
        return self.path(rel).read_bytes()

    def text(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def json(self, rel: str) -> Any:
        return json.loads(self.text(rel))

    def copy_to(self, rel: str, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / Path(rel).name
        shutil.copyfile(self.path(rel), target)
        return target


@pytest.fixture
def fixtures() -> FixtureLoader:
    return FixtureLoader(FIXTURES_ROOT)


@pytest.fixture
def dev_store(data_root: Path, clock: FakeClock, owner_tz: str) -> Iterator[Store]:
    """A ``dev`` instance in ``data_root``, bound as the process store for the test."""
    from coflow.kernel.ops.init import init_instance

    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    store = store_api.open_store(data_root, clock=clock)
    try:
        with store_api.use_store(store):
            yield store
    finally:
        store.close()


# --------------------------------------------------------------------------------------------------
# Contexts


@pytest.fixture
def owner_ctx() -> CommandContext:
    """The owner at the local CLI: an owner channel."""
    return CommandContext(actor="owner", channel="cli", owner_channel=True, interaction_id="int-1")


@pytest.fixture
def mcp_ctx() -> CommandContext:
    """An AI client over MCP: never an owner channel."""
    return CommandContext(
        actor="mcp_test-client", channel="mcp", owner_channel=False, interaction_id="int-2"
    )


# --------------------------------------------------------------------------------------------------
# Fake ports


@pytest.fixture
def fake_goals() -> FakeGoalDirectory:
    return FakeGoalDirectory()


@pytest.fixture
def fake_probe() -> FakeAttachmentProbe:
    return FakeAttachmentProbe()


@pytest.fixture
def fake_resolver() -> FakeEvidenceResolver:
    return FakeEvidenceResolver()


@pytest.fixture
def fake_directory() -> FakeDecisionDirectory:
    return FakeDecisionDirectory()


@pytest.fixture
def fake_undo() -> FakeUndoHandler:
    return FakeUndoHandler()
