"""``coflow run`` with the real composition root on a ``dev`` instance (track K's store): the
second core is refused by the lock, the CLI issues a client token through the admin API, a local
AI client lists the tools through the shim, every call lands in ``mcp_call_log``, and shutdown
revokes this run's admin tokens (AT-K7, AT-M1, MCP-1)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from coflow.app import composition
from coflow.app.supervisor import AppLauncher, serve
from coflow.interfaces.admin.api import read_endpoint
from coflow.interfaces.admin.cli import main
from coflow.interfaces.mcp.stdio_shim import run_shim
from coflow.kernel.context import FakeClock
from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store.api import read_connection
from coflow.kernel.store.lock import probe_lock
from tests.interfaces.fakes import FakeLauncher, make_services
from tests.interfaces.harness import running_core


def _session(url: str, token: str, *messages: dict[str, object]) -> list[dict[str, object]]:
    stdin = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    stdout = io.BytesIO()
    assert run_shim(url, token, stdin=stdin, stdout=stdout) == 0
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def test_a_real_core(
    data_root: Path, clock: FakeClock, owner_tz: str, capsys: pytest.CaptureFixture[str]
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    with composition.open_core(data_root, clock=clock):
        pass  # the instance opens and closes cleanly
    never = FakeLauncher(make_services(data_root), refuse=AssertionError("CLI opened the store"))
    root = ["--data-root", str(data_root)]

    with running_core(data_root, clock=clock) as core:
        assert serve(data_root, port=0, clock=clock) == 1, "a second core is refused"
        assert "INSTANCE_LOCKED" in capsys.readouterr().err
        code = main(
            ["mcp", "token", "new", "--client", "desk", "--scope", "read", "--json", *root],
            launcher=never,
            environ={},
        )
        assert code == 0
        token = json.loads(capsys.readouterr().out)["value"]["token"]
        endpoint = read_endpoint(data_root)
        assert endpoint is not None
        answers = _session(
            f"{endpoint.url}/mcp",
            token,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "dec_nothing", "arguments": {"x": 1}},
            },
        )
        tools = {t["name"] for t in answers[0]["result"]["tools"]}  # type: ignore[index]
        assert tools == {
            "dec_list",
            "dec_context",
            "dec_waiting",
            "dec_integrity",
            "dec_shadow_report",
        }
        unknown = answers[1]["result"]["structuredContent"]  # type: ignore[index]
        assert unknown["error"]["type"] == "not_found"
        assert unknown["instance_role"] == "dev"
        assert core.port > 0

    with composition.open_core(data_root, clock=clock), read_connection() as conn:
        clients = [tuple(r) for r in conn.execute("SELECT client, scopes FROM mcp_clients")]
        calls = [
            tuple(r) for r in conn.execute("SELECT client, tool, result_kind FROM mcp_call_log")
        ]
        admin = [
            tuple(r) for r in conn.execute("SELECT scope, revoked_at IS NOT NULL FROM adm_tokens")
        ]
        role = conn.execute("SELECT role FROM sys_instance").fetchone()[0]
    assert clients == [("desk", "read")]
    assert calls == [("desk", "dec_nothing", "unknown_tool")]
    assert sorted(admin) == [("admin", 1), ("import", 1)]
    assert role == "dev"


def test_the_ephemeral_core_issues_tokens_when_no_core_runs(
    data_root: Path, clock: FakeClock, owner_tz: str, capsys: pytest.CaptureFixture[str]
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    code = main(
        [
            "mcp",
            "token",
            "new",
            "--client",
            "desk",
            "--scope",
            "write",
            "--data-root",
            str(data_root),
        ],
        launcher=AppLauncher(clock=clock),
        environ={},
    )
    assert code == 0, capsys.readouterr().err
    assert "scope write" in capsys.readouterr().out
    with composition.open_core(data_root, clock=clock), read_connection() as conn:
        assert conn.execute("SELECT scopes FROM mcp_clients").fetchone()[0] == "read write"


def test_a_validation_root_moved_into_a_working_tree_does_not_open(
    tmp_path: Path, clock: FakeClock
) -> None:
    """Review finding: only init and doctor refused it; the core, the CLI's ephemeral core and
    the import open through ``open_core``."""
    outer = tmp_path / "outer"
    root = outer / "validation-data"
    init_instance(root, role="validation", clock=clock, timezone="Europe/Berlin")
    with composition.open_core(root, clock=clock):
        pass  # outside any working tree it opens
    (outer / ".git").mkdir()  # the root now lies inside a working tree
    with pytest.raises(Refused) as refused, composition.open_core(root, clock=clock):
        pytest.fail("the core opened")
    assert refused.value.code is RefusalCode.DATA_ROOT_IN_REPOSITORY
    assert probe_lock(root).free, "the store was closed on refusal"
