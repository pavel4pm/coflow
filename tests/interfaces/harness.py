"""Test harness for the interface layer: the core's listener in process, JSON-RPC over it."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from coflow.app.supervisor import RunningCore, build_http_app, serve
from coflow.interfaces.admin.api import Services
from coflow.interfaces.mcp.catalogue import CATALOGUE, ToolSpec
from coflow.interfaces.mcp.tools_dec import HANDLERS, ToolHandler
from coflow.kernel.context import Clock, CommandContext

PORT = 8741
BASE = f"http://127.0.0.1:{PORT}"
PROTOCOL = "2025-11-25"

OWNER_CTX = CommandContext(actor="owner", channel="cli", owner_channel=True, interaction_id="t-1")


def issue(services: Services, client: str, scope: str = "read", *, financial: bool = False) -> str:
    return services.clients.issue(client, scope=scope, financial=financial, ctx=OWNER_CTX).token  # type: ignore[arg-type]


@contextmanager
def listener(
    services: Services,
    *,
    catalogue: Sequence[ToolSpec] = CATALOGUE,
    handlers: Mapping[str, ToolHandler] | None = None,
) -> Iterator[TestClient]:
    app = build_http_app(
        services, port=PORT, catalogue=catalogue, handlers=dict(handlers or HANDLERS)
    )
    with TestClient(app, base_url=BASE) as client:
        yield client


def rpc(
    client: TestClient,
    method: str,
    params: Mapping[str, Any] | None = None,
    *,
    token: str | None,
    headers: Mapping[str, str] | None = None,
    request_id: int = 1,
) -> Any:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = dict(params)
    sent = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL,
    }
    if token is not None:
        sent["authorization"] = f"Bearer {token}"
    sent.update(headers or {})
    return client.post("/mcp", headers=sent, content=json.dumps(body))


def call_tool(
    client: TestClient, name: str, arguments: Mapping[str, Any] | None = None, *, token: str
) -> dict[str, Any]:
    """The structured result of a tool call, plus ``_is_error``."""
    response = rpc(
        client, "tools/call", {"name": name, "arguments": dict(arguments or {})}, token=token
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    payload = dict(result["structuredContent"])
    assert json.loads(result["content"][0]["text"]) == payload
    payload["_is_error"] = result["isError"]
    return payload


Opener = Callable[..., AbstractContextManager[Services]]


def fake_opener(services: Services) -> Opener:
    """An opener for ``serve`` that hands out ``services`` instead of opening a store."""

    @contextmanager
    def opener(root: Path, *, clock: Clock | None = None) -> Iterator[Services]:
        yield services

    return opener


@contextmanager
def running_core(
    data_root: Path, *, opener: Opener | None = None, clock: Clock | None = None
) -> Iterator[RunningCore]:
    """``coflow run`` in a background thread on a free loopback port, stopped on exit."""
    ready = threading.Event()
    box: dict[str, Any] = {}

    def on_ready(core: RunningCore) -> None:
        box["core"] = core
        ready.set()

    def target() -> None:
        try:
            box["code"] = serve(data_root, port=0, clock=clock, opener=opener, on_ready=on_ready)
        finally:
            ready.set()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    assert ready.wait(30), "the core did not start"
    assert "core" in box, f"the core refused to start (exit {box.get('code')})"
    core: RunningCore = box["core"]
    try:
        yield core
    finally:
        core.stop()
        thread.join(30)
        assert not thread.is_alive(), "the core did not stop"
        assert box["code"] == 0
