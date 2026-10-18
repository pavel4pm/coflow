"""AT-M1 (spec §9.1, MCP-1, DEC-6): ``dec_waiting`` and ``dec_context`` over MCP, ``coflow dec
waiting`` and ``show`` on the CLI, and the ``waiting`` query give identical items in one order;
every answer states the instance role and the mirror authority; no token → 401; a foreign Host
header is refused; a read-only token cannot call a write tool; every pull is recorded as a usage
signal.

The DEC read side is the synthetic fake of ``tests/interfaces/fakes.py`` (tracks D and S land in
parallel); ``test_integration_dev.py`` repeats the comparison on a real dev instance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from coflow.interfaces.admin.cli import main
from coflow.interfaces.mcp.catalogue import CATALOGUE, ToolSpec
from coflow.interfaces.mcp.tools_dec import HANDLERS
from tests.interfaces.fakes import FakeDecService, FakeLauncher, RecordingUsage, make_services
from tests.interfaces.harness import call_tool, issue, listener, rpc


def _items(view: dict[str, Any]) -> list[tuple[str, list[str]]]:
    return [(i["ref"], [r["text"] for r in i["reasons"]]) for i in view["value"]["items"]]


def _cli(
    argv: list[str], launcher: FakeLauncher, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    code = main(argv, launcher=launcher, environ={})
    out = capsys.readouterr().out
    return code, out


def test_waiting_is_identical_over_mcp_the_cli_and_the_query(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dec = FakeDecService()
    services = make_services(tmp_path, dec=dec)
    launcher = FakeLauncher(services)
    token = issue(services, "desk")

    with listener(services) as client:
        over_mcp = call_tool(client, "dec_waiting", {}, token=token)
    code, out = _cli(["dec", "waiting", "--json", "--data-root", str(tmp_path)], launcher, capsys)
    assert code == 0
    over_cli = json.loads(out)
    query = [(i.ref, [r.text for r in i.reasons]) for i in dec.waiting().value]

    assert _items(over_mcp) == _items(over_cli) == query
    # the whole item, question context included, is the same data on both channels
    assert over_mcp["value"]["items"] == over_cli["value"]["items"]

    code, text = _cli(["dec", "waiting", "--data-root", str(tmp_path)], launcher, capsys)
    assert code == 0
    positions = [text.index(ref) for ref, _ in query]
    assert positions == sorted(positions), "the text keeps the query's order"
    code, brief = _cli(
        ["dec", "waiting", "--brief", "--data-root", str(tmp_path)], launcher, capsys
    )
    lines = [ln for ln in brief.splitlines() if ln[:1].isdigit()]
    assert [ln.split()[1] for ln in lines] == [ref for ref, _ in query]


def test_context_is_identical_over_mcp_and_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    services = make_services(tmp_path)
    launcher = FakeLauncher(services)
    token = issue(services, "desk", financial=True)
    with listener(services) as client:
        over_mcp = call_tool(client, "dec_context", {"ref": "D905"}, token=token)
    code, out = _cli(
        ["dec", "show", "D905", "--json", "--data-root", str(tmp_path)], launcher, capsys
    )
    assert code == 0
    over_cli = json.loads(out)
    # the two projections differ only in their audience
    assert over_mcp["value"].pop("audience") == "agent"
    assert over_cli["value"].pop("audience") == "owner"
    over_mcp.pop("_is_error")
    assert over_mcp == over_cli

    code, text = _cli(["dec", "show", "D905", "--data-root", str(tmp_path)], launcher, capsys)
    first, second = text.splitlines()[:2]
    assert first == "1 of 2 assumptions cannot be checked (50 %)", "the share line comes first"
    assert second.startswith("D-0905")


def test_every_answer_states_the_role_and_the_mirror_authority(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    services = make_services(tmp_path, role="validation")
    launcher = FakeLauncher(services)
    token = issue(services, "desk")
    answers = []
    with listener(services) as client:
        for name, args in (
            ("dec_waiting", {}),
            ("dec_context", {"ref": "D-0905"}),
            ("dec_list", {}),
            ("dec_integrity", {"ref": "all"}),
            ("dec_shadow_report", {}),
        ):
            answers.append(call_tool(client, name, args, token=token))
    for answer in answers:
        assert answer["instance_role"] == "validation"
        assert answer["server"] == "coflow-v2"
        assert "V1" in answer["authority"]
    waiting = answers[0]["value"]["items"]
    by_ref = {i["ref"]: i["authority"] for i in waiting}
    assert by_ref["D-0905"]["system_of_record"] == "V1"
    assert by_ref["D-0905"]["writable_here"] is False
    assert "read-only here" in by_ref["D-0905"]["text"]
    assert by_ref["D-1001"]["system_of_record"] == "this instance"
    card = answers[1]["value"]
    assert card["authority"]["system_of_record"] == "V1"
    assert card["mirror_line"].startswith("mirrored from V1")
    lines = {
        x["public_id"]: x["authority"]["system_of_record"] for x in answers[2]["value"]["lines"]
    }
    assert lines["D-0903"] == "V1"
    assert lines["D-1001"] == "this instance"

    for argv in (["dec", "waiting"], ["dec", "show", "D-0905"], ["dec", "list"]):
        code, text = _cli([*argv, "--data-root", str(tmp_path)], launcher, capsys)
        assert code == 0
        assert "instance: validation" in text
        assert "read-only here" in text
    code, text = _cli(["dec", "waiting", "--brief", "--data-root", str(tmp_path)], launcher, capsys)
    assert "instance: validation" in text
    assert "read-only here" in text


def test_tokens_hosts_and_the_read_only_list(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    reader = issue(services, "reader")
    write_tool = ToolSpec(
        name="dec_test_write",
        maps_to="test_write",
        description="A synthetic write tool.",
        input_schema={"type": "object", "properties": {}},
        undo="not_undoable",
    )
    handlers = {**HANDLERS, "dec_test_write": HANDLERS["dec_list"]}
    with listener(services, catalogue=(*CATALOGUE, write_tool), handlers=handlers) as client:
        assert rpc(client, "tools/list", token=None).status_code == 401
        assert (
            rpc(client, "tools/list", token=reader, headers={"host": "evil.example"}).status_code
            == 421
        )
        refused = call_tool(client, "dec_test_write", {}, token=reader)
    assert refused["_is_error"]
    assert refused["error"]["code"] == "READ_ONLY_TOKEN"


def test_every_pull_is_a_usage_signal_by_channel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    services = make_services(tmp_path)
    launcher = FakeLauncher(services)
    token = issue(services, "desk")
    with listener(services) as client:
        call_tool(client, "dec_waiting", {}, token=token)
        call_tool(client, "dec_waiting", {"date": "2026-11-16"}, token=token)
        call_tool(client, "dec_context", {"ref": "D-0905"}, token=token)  # not a pull
    _cli(["dec", "waiting", "--data-root", str(tmp_path)], launcher, capsys)
    _cli(["dec", "waiting", "--brief", "--data-root", str(tmp_path)], launcher, capsys)
    usage = services.usage
    assert isinstance(usage, RecordingUsage)
    pulls = [(signal, channel, detail["view"]) for signal, channel, detail in usage.rows]
    assert pulls == [
        ("dec.waiting.pull", "mcp", "mcp"),
        ("dec.waiting.pull", "mcp", "mcp"),
        ("dec.waiting.pull", "cli", "cli"),
        ("dec.waiting.pull", "cli", "cli_brief"),
    ]
    dec = services.dec
    assert isinstance(dec, FakeDecService)
    days = [c[1]["today"] for c in dec.calls if c[0] == "waiting"]
    assert [str(d) if d else None for d in days] == [None, "2026-11-16", None, None]
