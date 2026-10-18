"""``coflow run`` on a real loopback socket (spec §4.5, AT-K7, AT-M1): the endpoint file, the CLI
through the admin API while the core runs, the stdio shim through the MCP endpoint, shutdown."""

from __future__ import annotations

import http.client
import io
import json
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from coflow.app.supervisor import serve
from coflow.interfaces.admin.api import Services, read_endpoint
from coflow.interfaces.admin.cli import main
from coflow.interfaces.mcp.stdio_shim import run_shim
from coflow.kernel.context import Clock
from coflow.kernel.errors import RefusalCode, Refused
from tests.interfaces.fakes import FakeLauncher, MemoryAdminTokens, RecordingUsage, make_services
from tests.interfaces.harness import fake_opener, running_core


def _get(port: int, path: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request("GET", path, headers=headers or {})
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def test_the_cli_and_the_shim_go_through_the_running_core(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "coflow-data"
    root.mkdir()
    services = make_services(root)
    never = FakeLauncher(
        services, refuse=AssertionError("the CLI opened the instance while the core runs")
    )

    with running_core(root, opener=fake_opener(services)) as core:
        endpoint = read_endpoint(root)
        assert endpoint is not None
        assert endpoint.url == f"http://127.0.0.1:{core.port}"
        assert _get(core.port, "/healthz") == (200, b"ok")
        assert _get(core.port, "/healthz", {"host": "decisions.example"})[0] == 421

        # the CLI: through the admin API, never through the store
        assert (
            main(["dec", "waiting", "--json", "--data-root", str(root)], launcher=never, environ={})
            == 0
        )
        over_cli = json.loads(capsys.readouterr().out)
        assert (
            main(
                [
                    "mcp",
                    "token",
                    "new",
                    "--client",
                    "desk",
                    "--scope",
                    "read",
                    "--json",
                    "--data-root",
                    str(root),
                ],
                launcher=never,
                environ={},
            )
            == 0
        )
        token = json.loads(capsys.readouterr().out)["value"]["token"]
        assert never.opened == 0

        # the shim: a local AI client's session over stdio
        lines = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "dec_waiting", "arguments": {}},
            },
        ]
        stdin = io.BytesIO(b"".join(json.dumps(x).encode() + b"\n" for x in lines))
        stdout = io.BytesIO()
        assert run_shim(f"{endpoint.url}/mcp", token, stdin=stdin, stdout=stdout) == 0
        answers = [json.loads(x) for x in stdout.getvalue().splitlines()]
        assert [a["id"] for a in answers] == [1, 2, 3]
        assert answers[0]["result"]["serverInfo"]["name"] == "coflow-v2"
        over_shim = answers[2]["result"]["structuredContent"]
        assert over_shim["value"]["items"] == over_cli["value"]["items"]

        # a wrong token over the shim is an answer, not a crash
        stdout = io.BytesIO()
        run_shim(
            f"{endpoint.url}/mcp",
            "cfm_wrong",
            stdin=io.BytesIO(json.dumps(lines[2]).encode() + b"\n"),
            stdout=stdout,
        )
        assert "coflow mcp token new" in json.loads(stdout.getvalue())["error"]["message"]

        # the admin API refuses a missing or a wrong-scope token
        conn = http.client.HTTPConnection("127.0.0.1", core.port, timeout=30)
        conn.request(
            "POST",
            "/admin/v1/dec.waiting",
            body=b"{}",
            headers={"content-type": "application/json"},
        )
        assert conn.getresponse().status == 401
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", core.port, timeout=30)
        conn.request(
            "POST",
            "/admin/v1/dec.waiting",
            body=b"{}",
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {endpoint.import_token}",
            },
        )
        assert conn.getresponse().status == 403
        conn.close()

    assert read_endpoint(root) is None, "the endpoint file is removed at shutdown"
    tokens = services.admin_tokens
    assert isinstance(tokens, MemoryAdminTokens)
    assert tokens.revoked
    usage = services.usage
    assert isinstance(usage, RecordingUsage)
    assert [(s, ch) for s, ch, _ in usage.rows] == [
        ("dec.waiting.pull", "cli"),
        ("dec.waiting.pull", "mcp"),
    ]


def test_a_stale_endpoint_file_falls_back_to_an_ephemeral_core(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "coflow-data"
    root.mkdir()
    services = make_services(root)
    with running_core(root, opener=fake_opener(services)):
        stale = (root / "run" / "core.json").read_text(encoding="utf-8")
    (root / "run" / "core.json").write_text(stale, encoding="utf-8")  # as a crash would leave it
    launcher = FakeLauncher(services)
    assert main(["dec", "list", "--data-root", str(root)], launcher=launcher, environ={}) == 0
    assert launcher.opened == 1
    assert "D-0905" in capsys.readouterr().out
    assert read_endpoint(root) is None, "the stale file is removed once the lock is held"


def test_a_second_core_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def locked(root: Path, *, clock: Clock | None = None) -> AbstractContextManager[Services]:
        raise Refused(RefusalCode.INSTANCE_LOCKED, "another core holds the instance lock")

    assert serve(tmp_path, port=0, opener=locked) == 1
    assert "INSTANCE_LOCKED" in capsys.readouterr().err
