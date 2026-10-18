"""``coflow mcp-stdio`` (spec §4.5, AT-K7, MCP-1): a forwarder that knows a URL and a token, never
a data root."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping

import grimp
import pytest

from coflow.interfaces.mcp.stdio_shim import (
    DEFAULT_URL,
    Forwarder,
    PostResult,
    check_loopback_url,
    run_shim,
)

SHIM = "coflow.interfaces.mcp.stdio_shim"


class FakePost:
    def __init__(self, *answers: PostResult | Exception) -> None:
        self.answers = list(answers)
        self.sent: list[tuple[dict[str, object] | list[object], dict[str, str]]] = []

    def __call__(self, body: bytes, headers: Mapping[str, str]) -> PostResult:
        self.sent.append((json.loads(body), dict(headers)))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _json(status: int, payload: object, **headers: str) -> PostResult:
    return PostResult(status, "application/json", json.dumps(payload).encode(), headers)


def _line(payload: object) -> bytes:
    return json.dumps(payload).encode() + b"\n"


def test_the_shim_imports_nothing_that_can_find_an_instance() -> None:
    graph = grimp.build_graph("coflow")
    upstream = graph.find_upstream_modules(SHIM)
    assert upstream == set(), f"the shim imports {sorted(upstream)}"


def test_only_loopback_urls() -> None:
    assert check_loopback_url(DEFAULT_URL) == ("127.0.0.1", 8741, "/mcp")
    assert check_loopback_url("http://localhost:9000/mcp")[1] == 9000
    for url in (
        "https://127.0.0.1:8741/mcp",
        "http://198.51.100.7:8741/mcp",
        "http://decisions.example/mcp",
    ):
        with pytest.raises(ValueError, match="loopback"):
            check_loopback_url(url)
    with pytest.raises(ValueError, match="COFLOW_MCP_TOKEN"):
        Forwarder(DEFAULT_URL, "")


def test_forwarding_keeps_the_negotiated_version() -> None:
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25"},
    }
    post = FakePost(
        _json(200, {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25"}}),
        PostResult(202, "", b""),
        _json(200, {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}),
    )
    fwd = Forwarder(DEFAULT_URL, "cfm_t", post=post)
    assert fwd.forward(_line(init)) == [
        b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25"}}'
    ]
    assert fwd.forward(_line({"jsonrpc": "2.0", "method": "notifications/initialized"})) == []
    out = fwd.forward(_line({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
    assert json.loads(out[0])["result"] == {"tools": []}
    first, later = post.sent[0][1], post.sent[2][1]
    assert first["authorization"] == "Bearer cfm_t"
    assert "mcp-protocol-version" not in first
    assert later["mcp-protocol-version"] == "2025-11-25"
    assert fwd.forward(b"   \n") == []


def test_event_streams_and_batches() -> None:
    sse = (
        b'event: message\ndata: {"jsonrpc":"2.0","id":3,\ndata: "result":{}}\n\n'
        b'data: {"jsonrpc":"2.0","method":"note"}\n\n'
    )
    post = FakePost(PostResult(200, "text/event-stream", sse))
    out = Forwarder(DEFAULT_URL, "cfm_t", post=post).forward(
        _line({"jsonrpc": "2.0", "id": 3, "method": "ping"})
    )
    assert [json.loads(x) for x in out] == [
        {"jsonrpc": "2.0", "id": 3, "result": {}},
        {"jsonrpc": "2.0", "method": "note"},
    ]
    assert all(b"\n" not in x for x in out)


def test_failures_become_json_rpc_errors() -> None:
    down = FakePost(ConnectionRefusedError("refused"), ConnectionRefusedError("refused"))
    fwd = Forwarder(DEFAULT_URL, "cfm_t", post=down)
    out = fwd.forward(_line({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}))
    error = json.loads(out[0])
    assert error["id"] == 7
    assert "coflow run" in error["error"]["message"]
    assert fwd.forward(_line({"jsonrpc": "2.0", "method": "notifications/initialized"})) == []

    refused = FakePost(_json(401, {"error": {"type": "http", "status": 401}}))
    out = Forwarder(DEFAULT_URL, "cfm_bad", post=refused).forward(
        _line({"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
    )
    assert "coflow mcp token new" in json.loads(out[0])["error"]["message"]

    rpc_error = {"jsonrpc": "2.0", "id": 9, "error": {"code": -32602, "message": "bad params"}}
    passed = FakePost(_json(400, rpc_error))
    out = Forwarder(DEFAULT_URL, "cfm_t", post=passed).forward(
        _line({"jsonrpc": "2.0", "id": 9, "method": "x"})
    )
    assert json.loads(out[0]) == rpc_error

    garbage = Forwarder(DEFAULT_URL, "cfm_t", post=FakePost()).forward(b"{not json\n")
    assert json.loads(garbage[0])["error"]["code"] == -32700


def test_run_shim_writes_one_message_per_line() -> None:
    post = FakePost(
        _json(200, {"jsonrpc": "2.0", "id": 1, "result": {"a": "line\nbreak"}}),
        _json(200, {"jsonrpc": "2.0", "id": 2, "result": {}}),
    )
    stdin = io.BytesIO(
        _line({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        + _line({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    )
    stdout = io.BytesIO()
    assert run_shim(DEFAULT_URL, "cfm_t", stdin=stdin, stdout=stdout, post=post) == 0
    lines = stdout.getvalue().splitlines()
    assert [json.loads(x)["id"] for x in lines] == [1, 2]
    assert json.loads(lines[0])["result"]["a"] == "line\nbreak"
    err = io.StringIO()
    assert (
        run_shim(
            "http://decisions.example/mcp",
            "cfm_t",
            stdin=io.BytesIO(),
            stdout=io.BytesIO(),
            stderr=err,
        )
        == 2
    )
    assert "loopback" in err.getvalue()
