"""The loopback MCP listener: tokens, Host and Origin checks, the read-only list, the call log
(MCP-1, spec §5.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from coflow.interfaces.mcp.catalogue import CATALOGUE, ToolSpec
from coflow.interfaces.mcp.server import build_mcp_server
from coflow.interfaces.mcp.tools_dec import HANDLERS, McpDeps, ToolCall
from coflow.interfaces.views.card import Wire
from tests.interfaces.fakes import FakeDecService, MemoryCallLog, RecordingUsage, make_services
from tests.interfaces.harness import PORT, call_tool, issue, listener, rpc

READ_TOOLS = {"dec_list", "dec_context", "dec_waiting", "dec_integrity", "dec_shadow_report"}


def test_no_token_is_401(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with listener(services) as client:
        response = rpc(client, "tools/list", token=None)
        assert response.status_code == 401
        assert response.headers["www-authenticate"].startswith("Bearer")
        assert rpc(client, "tools/list", token="cfm_" + "0" * 64).status_code == 401
        assert (
            rpc(client, "tools/list", token=None, headers={"authorization": "Basic x"}).status_code
            == 401
        )


def test_foreign_host_and_origin_are_refused(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        foreign = rpc(client, "tools/list", token=token, headers={"host": "decisions.example:8741"})
        assert foreign.status_code == 421
        other_port = rpc(client, "tools/list", token=token, headers={"host": "127.0.0.1:9999"})
        assert other_port.status_code == 421
        origin = rpc(client, "tools/list", token=token, headers={"origin": "http://example.com"})
        assert origin.status_code == 403
        local_page = rpc(
            client, "tools/list", token=token, headers={"origin": "http://localhost:3000"}
        )
        assert local_page.status_code == 403
        same = rpc(
            client, "tools/list", token=token, headers={"origin": f"http://127.0.0.1:{PORT}"}
        )
        assert same.status_code == 200
        assert (
            rpc(
                client, "tools/list", token=token, headers={"host": f"localhost:{PORT}"}
            ).status_code
            == 200
        )
        # the host check guards every route, not only /mcp
        assert client.get("/healthz", headers={"host": "decisions.example"}).status_code == 421
        assert client.get("/healthz").text == "ok"


def test_initialize_names_the_v2_server(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    params = {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "1"},
    }
    with listener(services) as client:
        result = rpc(client, "initialize", params, token=token).json()["result"]
    assert result["serverInfo"]["name"] == "coflow-v2"
    assert "read-only here" in result["instructions"]


def test_read_token_lists_the_read_tools(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        tools = rpc(client, "tools/list", token=token).json()["result"]["tools"]
    assert {t["name"] for t in tools} == READ_TOOLS
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
    assert all(t["name"].startswith("dec_") for t in tools)


def _echo_write(deps: McpDeps, call: ToolCall) -> Wire:
    return {
        "server": "coflow-v2",
        "view": "echo",
        "instance_role": deps.facts.role(),
        "value": dict(call.arguments),
    }


WRITE_TOOL = ToolSpec(
    name="dec_test_write",
    maps_to="test_write",
    description="A synthetic write tool for the scope test.",
    input_schema={
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "additionalProperties": False,
    },
    undo="not_undoable",
)


def test_read_only_token_cannot_call_a_write_tool(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    reader = issue(services, "reader", "read")
    writer = issue(services, "writer", "write")
    catalogue = (*CATALOGUE, WRITE_TOOL)
    handlers = {**HANDLERS, "dec_test_write": _echo_write}
    with listener(services, catalogue=catalogue, handlers=handlers) as client:
        listed = {
            t["name"] for t in rpc(client, "tools/list", token=reader).json()["result"]["tools"]
        }
        assert "dec_test_write" not in listed
        refused = call_tool(client, "dec_test_write", {"x": 1}, token=reader)
        assert refused["_is_error"]
        assert refused["error"]["code"] == "READ_ONLY_TOKEN"
        assert set(refused["error"]["allowed"]) == READ_TOOLS
        assert refused["instance_role"] == "dev"
        listed_w = {
            t["name"] for t in rpc(client, "tools/list", token=writer).json()["result"]["tools"]
        }
        assert "dec_test_write" in listed_w
        done = call_tool(client, "dec_test_write", {"x": 1}, token=writer)
        assert not done["_is_error"]
        assert done["value"] == {"x": 1}
    log = services.call_log
    assert isinstance(log, MemoryCallLog)
    kinds = [(r["client"], r["tool"], r["result_kind"]) for r in log.rows]
    assert kinds == [
        ("reader", "dec_test_write", "refused:READ_ONLY_TOKEN"),
        ("writer", "dec_test_write", "ok"),
    ]


def test_every_call_is_logged_with_its_client(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        call_tool(client, "dec_list", {"limit": 3}, token=token)
        call_tool(client, "dec_context", {"ref": "D-0999"}, token=token)
        call_tool(client, "dec_list", {"limit": 0}, token=token)
        call_tool(client, "dec_nothing", {}, token=token)
    log = services.call_log
    assert isinstance(log, MemoryCallLog)
    assert [(r["tool"], r["result_kind"]) for r in log.rows] == [
        ("dec_list", "ok"),
        ("dec_context", "not_found"),
        ("dec_list", "invalid_arguments"),
        ("dec_nothing", "unknown_tool"),
    ]
    assert {r["client"] for r in log.rows} == {"desk"}
    ids = [r["interaction_id"] for r in log.rows]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("mcp-") for i in ids)


def test_errors_state_the_role_and_name_what_is_wrong(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        missing = call_tool(client, "dec_context", {}, token=token)
        bad_date = call_tool(client, "dec_waiting", {"date": "2026-02-31"}, token=token)
        free_text = call_tool(client, "dec_waiting", {"date": "next monday"}, token=token)
        not_found = call_tool(client, "dec_context", {"ref": "D-0999"}, token=token)
    for payload in (missing, bad_date, free_text, not_found):
        assert payload["_is_error"]
        assert payload["instance_role"] == "dev"
        assert payload["server"] == "coflow-v2"
    assert missing["error"]["type"] == "invalid_arguments"
    assert "ref" in missing["error"]["detail"]
    assert bad_date["error"]["type"] == "invalid_arguments"
    assert free_text["error"]["type"] == "invalid_arguments"
    assert not_found["error"] == {
        "type": "not_found",
        "code": "NOT_FOUND",
        "detail": "D-0999 not found",
        "missing": [],
        "allowed": [],
        "candidates": [],
    }


def test_money_is_withheld_unless_the_client_is_financial(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    plain = issue(services, "plain")
    money = issue(services, "money", financial=True)
    with listener(services) as client:
        withheld = call_tool(client, "dec_context", {"ref": "D905"}, token=plain)
        shown = call_tool(client, "dec_context", {"ref": "V1_D905"}, token=money)
    assert withheld["value"]["stakes"][0]["amount"] is None
    assert withheld["value"]["stakes"][0]["amount_withheld"] is True
    assert "amounts withheld (financial flag off)" in withheld["coverage"]
    assert "450" not in str(withheld)
    assert shown["value"]["stakes"][0]["amount"] == "450"
    assert "amounts withheld (financial flag off)" not in shown["coverage"]
    assert withheld["value"]["audience"] == "agent"
    assert shown["value"]["audience"] == "agent"
    # DEC's agent audience always withholds amounts, so a financial agent's card is read from the
    # owner audience (integration)
    dec = services.dec
    assert isinstance(dec, FakeDecService)
    audiences = [kw["audience"] for name, kw in dec.calls if name == "decision_context"]
    assert audiences == ["agent", "owner"]


def test_the_card_never_carries_salts_or_raw_rows(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        card = call_tool(client, "dec_context", {"ref": "D-0905", "detail": "full"}, token=token)
    text = str(card)
    assert "salt" not in text
    assert "00" * 16 not in text
    assert "never shown" not in text  # legacy_json stays inside the instance


def test_shadow_report_and_integrity(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    token = issue(services, "desk")
    with listener(services) as client:
        shadow = call_tool(client, "dec_shadow_report", {"run_id": 3}, token=token)
        integrity = call_tool(client, "dec_integrity", {"ref": "all"}, token=token)
    assert shadow["value"]["totals"] == {"expected": 3, "finding": 0, "same": 40, "unexpected": 1}
    assert shadow["value"]["unexpected"][0]["v1_value"] == "2026-11-20"
    assert shadow["value"]["unexpected"][0]["v2_value"] == "2026-11-18"
    assert "V1" in shadow["authority"]
    report = integrity["value"]["reports"][0]
    assert report["ok"] is False
    assert report["lines"][1] == {
        "edition": "live",
        "status": "drift",
        "items": ["statement"],
        "seal12": None,
    }
    assert report["authority"]["system_of_record"] == "V1"
    usage = services.usage
    assert isinstance(usage, RecordingUsage)
    assert usage.rows == [("dec.shadow.opened", "mcp", {"view": "mcp"})]


def test_a_catalogue_entry_needs_a_handler(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with pytest.raises(ValueError, match="dec_test_write"):
        build_mcp_server(services, call_log=services.call_log, catalogue=(*CATALOGUE, WRITE_TOOL))


class BrokenDec(FakeDecService):
    def waiting(self, *, today: object = None) -> Any:
        raise NotImplementedError("track D: modules/dec/queries.py")


def test_an_internal_failure_is_answered_and_logged(tmp_path: Path) -> None:
    services = make_services(tmp_path, dec=BrokenDec())
    token = issue(services, "desk")
    with listener(services) as client:
        failed = call_tool(client, "dec_waiting", {}, token=token)
    assert failed["_is_error"]
    assert failed["error"]["type"] == "internal"
    assert "track D" not in str(failed), "internals stay in the core's log"
    log = services.call_log
    assert isinstance(log, MemoryCallLog)
    assert [(r["tool"], r["result_kind"]) for r in log.rows] == [("dec_waiting", "error")]
    usage = services.usage
    assert isinstance(usage, RecordingUsage)
    assert usage.rows == [], "a failed call is no pull"
