"""The real core over real sockets rejects what it must (MCP-1, spec §4.5; added from the I1
review, which checked each case by hand): loopback only; no token, an empty bearer, a rotated
token, a token of the other surface and a previous run's admin token get 401; a foreign or
other-port ``Host`` gets 421 and a duplicated one is refused; a foreign, ``null``, other-port or
``https`` ``Origin`` gets 403 on ``/mcp`` and ``/admin``; a websocket to ``/mcp`` is not served."""

from __future__ import annotations

import http.client
import json
import socket
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from coflow.app.supervisor import build_http_app
from coflow.interfaces.admin.api import read_endpoint
from coflow.interfaces.admin.cli import main
from coflow.kernel.context import FakeClock
from coflow.kernel.ops.init import init_instance
from tests.interfaces.fakes import FakeLauncher, make_services
from tests.interfaces.harness import PORT, issue, running_core

BODY = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
ORIGINS = ("http://evil.example", "null", "http://127.0.0.1:1", "https://127.0.0.1")
# Taken before the offline guard (an autouse fixture) replaces it: the probe below connects only
# to this machine's own non-loopback addresses, which is still this machine, never the network.
_OWN_ADDRESS_CONNECT = socket.socket.connect


def _post(port: int, path: str, body: bytes, headers: dict[str, object]) -> int:
    """POST with exactly ``headers`` (no implicit Host; a list value repeats the header)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.putrequest("POST", path, skip_host=True, skip_accept_encoding=True)
        for key, value in headers.items():
            for one in value if isinstance(value, list) else [value]:
                conn.putheader(key, str(one))
        conn.putheader("content-length", str(len(body)))
        conn.endheaders(body)
        return conn.getresponse().status
    finally:
        conn.close()


def _rpc(token: str | None, port: int, **extra: object) -> dict[str, object]:
    headers: dict[str, object] = {
        "host": f"127.0.0.1:{port}",
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2025-11-25",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    headers.update(extra)
    return headers


def _reaches(addr: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        _OWN_ADDRESS_CONNECT(s, (addr, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _non_loopback_addresses() -> set[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return set()
    return {str(ai[4][0]) for ai in infos if not str(ai[4][0]).startswith("127.")}


def _new_token(root: list[str], never: FakeLauncher, capsys: pytest.CaptureFixture[str]) -> str:
    args = ["mcp", "token", "new", "--client", "desk", "--scope", "read", "--json", *root]
    assert main(args, launcher=never, environ={}) == 0
    return str(json.loads(capsys.readouterr().out)["value"]["token"])


def test_the_real_core_rejects_what_it_must(
    data_root: Path, clock: FakeClock, owner_tz: str, capsys: pytest.CaptureFixture[str]
) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    never = FakeLauncher(make_services(data_root), refuse=AssertionError("CLI opened the store"))
    root = ["--data-root", str(data_root)]
    with running_core(data_root, clock=clock) as core:
        port = core.port
        # bound to loopback only
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            assert s.getpeername()[0] == "127.0.0.1"
        assert core.endpoint.url.startswith("http://127.0.0.1:")
        for addr in _non_loopback_addresses():
            assert not _reaches(addr, port), "the core answers on a non-loopback address"

        # tokens: rotation stops the old one at once; each surface takes only its own tokens
        first = _new_token(root, never, capsys)
        assert _post(port, "/mcp", BODY, _rpc(first, port)) == 200
        second = _new_token(root, never, capsys)
        assert _post(port, "/mcp", BODY, _rpc(first, port)) == 401
        assert _post(port, "/mcp", BODY, _rpc(second, port)) == 200
        endpoint = read_endpoint(data_root)
        assert endpoint is not None
        assert _post(port, "/mcp", BODY, _rpc(endpoint.admin_token, port)) == 401
        admin_with_mcp = {
            "host": f"127.0.0.1:{port}",
            "content-type": "application/json",
            "authorization": f"Bearer {second}",
        }
        assert _post(port, "/admin/v1/ping", b"{}", admin_with_mcp) == 401
        assert _post(port, "/mcp", BODY, _rpc(None, port)) == 401
        assert _post(port, "/mcp", BODY, _rpc(None, port, authorization="Bearer ")) == 401

        # Host: missing, foreign, another port, duplicated
        no_host = _rpc(second, port)
        del no_host["host"]
        assert _post(port, "/mcp", BODY, no_host) in (400, 421)
        assert _post(port, "/mcp", BODY, _rpc(second, port, host="evil.example")) == 421
        assert _post(port, "/mcp", BODY, _rpc(second, port, host="127.0.0.1:1")) == 421
        duplicated = _rpc(second, port, host=[f"127.0.0.1:{port}", "evil.example"])
        try:
            status = _post(port, "/mcp", BODY, duplicated)
        except ConnectionError:
            status = 400  # the HTTP layer drops the connection: refused either way
        assert status in (400, 421)

        # Origin, on both surfaces
        admin = {**admin_with_mcp, "authorization": f"Bearer {endpoint.admin_token}"}
        for origin in ORIGINS:
            assert _post(port, "/mcp", BODY, _rpc(second, port, origin=origin)) == 403
            assert _post(port, "/admin/v1/ping", b"{}", {**admin, "origin": origin}) == 403
        assert _post(port, "/admin/v1/ping", b"{}", admin) == 200
        assert _post(port, "/admin/v1/ping", b"{}", {**admin, "host": "evil.example"}) == 421

    # a previous run's admin token is dead after a restart
    with running_core(data_root, clock=clock) as again:
        stale = {
            "host": f"127.0.0.1:{again.port}",
            "content-type": "application/json",
            "authorization": f"Bearer {endpoint.admin_token}",
        }
        assert _post(again.port, "/admin/v1/ping", b"{}", stale) == 401


def test_a_websocket_to_mcp_is_not_served(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    issue(services, "desk")
    app = build_http_app(services, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as client:
        refused = pytest.raises(Exception)  # noqa: PT011 - any refusal of the upgrade will do
        with refused:
            _talk_over_websocket(client)


def _talk_over_websocket(client: TestClient) -> None:
    with client.websocket_connect("/mcp", headers={"host": "evil.example"}) as ws:
        ws.send_text("{}")
        ws.receive_text()
