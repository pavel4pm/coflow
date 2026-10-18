"""Increment I1 as one system (spec §12.2: "I1 is done when the owner can import a snapshot, see
equal counts, and ask what is waiting and why over MCP and the CLI with the shadow report beside
it").

Every step runs through the real composition root (``coflow.app``), the kernel's store, DEC's
importer, queries and shadow, and the interfaces, on synthetic snapshots in a temp data root:

- the CLI flow of §5.6: ``init``, ``doctor``, ``dec import v1`` (S1, S1 again, S1′), ``dec list``,
  ``dec waiting --brief``, ``dec show``, ``dec shadow``, ``dec integrity``;
- the running core: CLI writes through the admin API (AT-K7), a token issued there, and a local AI
  client's MCP session through the real ``coflow mcp-stdio`` shim process, driven by the official
  SDK's stdio client (AT-M1), with every pull recorded by channel;
- a canary written into imported decisions never reaches events, the transaction log or any other
  kernel table (AT-K6 through DEC's own writes).

The clock is the fixture world's ``FakeClock``; it is set to each snapshot's import instant
(``IMPORT_AT``), as the daily job would run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from coflow.app import composition
from coflow.app.supervisor import AppLauncher
from coflow.interfaces.admin.cli import main
from coflow.kernel.context import FakeClock
from coflow.kernel.policy.canary import make_canary, scan_database
from coflow.kernel.store.api import read_connection
from tests.interfaces.fakes import FakeLauncher, make_services
from tests.interfaces.harness import running_core
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import IMPORT_AT

SNAPSHOTS = sb.SNAPSHOT_DIR
READ_TOOLS = ["dec_context", "dec_integrity", "dec_list", "dec_shadow_report", "dec_waiting"]


def _cli(
    argv: list[str], launcher: Any, capsys: pytest.CaptureFixture[str], root: Path
) -> tuple[int, str, str]:
    code = main([*argv, "--data-root", str(root)], launcher=launcher, environ={})
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _json(argv: list[str], launcher: Any, capsys: pytest.CaptureFixture[str], root: Path) -> Any:
    code, out, err = _cli([*argv, "--json"], launcher, capsys, root)
    assert code == 0, err or out
    return json.loads(out)


def _import(
    name: str,
    launcher: Any,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
    root: Path,
) -> str:
    clock.set(IMPORT_AT[name])
    code, out, err = _cli(["dec", "import", "v1", str(SNAPSHOTS / name)], launcher, capsys, root)
    assert code == 0, err or out
    return out


# ==================================================================================================
# The CLI flow


def test_the_i1_cli_flow_on_the_synthetic_family(
    data_root: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    launcher = AppLauncher(clock=clock)
    run = (launcher, capsys, data_root)

    code, out, err = _cli(["init", "--role", "dev", "--timezone", "Europe/Berlin"], *run)
    assert code == 0, err
    assert "dev instance" in out
    code, out, _ = _cli(["doctor"], *run)
    assert code == 0
    assert "all checks passed" in out

    out = _import("s1.json", *run[:1], clock, capsys, data_root)
    assert "Import run 1: applied" in out
    assert "decisions: seen 8, new 8" in out
    out = _import("s1.json", *run[:1], clock, capsys, data_root)
    assert "Import run 1: noop" in out  # AT-S2 over the CLI
    # The counts under a no-op are the applying run's, and the text says so.
    assert "already applied by run 1: nothing changed. The counts below are that run's." in out
    out = _import("s1_prime.json", *run[:1], clock, capsys, data_root)
    assert "Import run 2: applied" in out
    assert "absent since this run: D-0905" in out  # AT-S3
    assert "D-0908_E-02 (source_changed)" in out
    dry = SNAPSHOTS / "s1_double_prime.json"
    code, out, err = _cli(["dec", "import", "v1", str(dry), "--dry-run"], *run)
    assert code == 0, err or out
    assert out.startswith("Dry run (mode dry_run, from V1, synthetic): nothing was written")
    assert "already applied" not in out

    listed = _json(["dec", "list"], *run)
    lines = listed["value"]["lines"]
    assert [line["public_id"] for line in lines] == [f"D-{n:04d}" for n in range(903, 911)]
    assert all(line["authority"]["system_of_record"] == "V1" for line in lines)
    assert listed["instance_role"] == "dev"

    code, out, _ = _cli(["dec", "waiting", "--brief"], *run)
    assert code == 0
    items = [line for line in out.splitlines() if line[:1].isdigit()]
    assert 1 <= len(items) <= 8
    assert not any("D-0905" in line for line in items)  # tombstoned mirrors never wait
    waiting = _json(["dec", "waiting"], *run)
    assert [i["ref"] for i in waiting["value"]["items"]] == [line.split()[1] for line in items]

    code, out, _ = _cli(["dec", "show", "D907"], *run)
    assert code == 0
    assert "D-0907" in out
    assert "V1_G901" in out  # the goal_changed reason (AT-S7)
    assert "read-only here" in out

    shadow = _json(["dec", "shadow"], *run)
    report = shadow["value"]
    assert report["run_id"] == 2
    assert report["report_status"] == "written"
    assert report["totals"]["unexpected"] == 0
    assert report["totals"]["finding"] == 1
    code, out, _ = _cli(["dec", "shadow", "--run", "1"], *run)
    assert code == 0
    assert "unexpected 0" in out

    integrity = _json(["dec", "integrity", "--all"], *run)
    reports = integrity["value"]["reports"]
    assert len(reports) == 8
    assert all(r["ok"] for r in reports)
    assert all(r["authority"]["system_of_record"] == "V1" for r in reports)


# ==================================================================================================
# The running core: the admin API and an MCP session through the stdio shim


async def _stdio_session(url: str, token: str) -> dict[str, Any]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coflow.app.supervisor", "mcp-stdio", "--url", url],
        env={"COFLOW_MCP_TOKEN": token},
    )
    with anyio.fail_after(120):
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            waiting = await session.call_tool("dec_waiting", {})
            first = waiting.structured_content["value"]["items"][0]["ref"]  # type: ignore[index]
            card = await session.call_tool("dec_context", {"ref": first})
    return {
        "server": init.server_info.name,
        "tools": sorted(t.name for t in tools.tools),
        "waiting": waiting,
        "card": card,
    }


def test_the_core_serves_the_cli_and_an_mcp_client_through_the_shim(
    data_root: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    launcher = AppLauncher(clock=clock)
    assert (
        _cli(["init", "--role", "dev", "--timezone", "Europe/Berlin"], launcher, capsys, data_root)[
            0
        ]
        == 0
    )
    _import("s1.json", launcher, clock, capsys, data_root)  # an ephemeral core: no core runs
    never = FakeLauncher(
        make_services(data_root),
        refuse=AssertionError("the CLI opened the store while a core runs"),
    )

    with running_core(data_root, clock=clock) as core:
        # a CLI write while the core runs goes through the admin API (AT-K7)
        out = _import("s1_prime.json", never, clock, capsys, data_root)
        assert "Import run 2: applied" in out
        issued = _json(
            ["mcp", "token", "new", "--client", "desk", "--scope", "read"], never, capsys, data_root
        )
        token = issued["value"]["token"]
        over_cli = _json(["dec", "waiting"], never, capsys, data_root)
        assert never.opened == 0

        answer = anyio.run(_stdio_session, f"{core.endpoint.url}/mcp", token)

    assert answer["server"] == "coflow-v2"
    assert answer["tools"] == READ_TOOLS
    waiting = answer["waiting"]
    assert not waiting.is_error
    over_mcp = waiting.structured_content
    assert over_mcp["value"]["items"] == over_cli["value"]["items"]  # AT-M1: identical
    assert over_mcp["instance_role"] == "dev"
    assert "V1" in over_mcp["authority"]
    card = answer["card"].structured_content
    assert card["instance_role"] == "dev"
    assert card["value"]["authority"]["system_of_record"] == "V1"

    # the core is gone: the next CLI command runs an ephemeral core under the same lock
    shadow = _json(["dec", "shadow"], launcher, capsys, data_root)
    assert shadow["value"]["totals"]["unexpected"] == 0

    with composition.open_core(data_root, clock=clock), read_connection() as conn:
        calls = [
            tuple(r)
            for r in conn.execute(
                "SELECT client, tool, result_kind FROM mcp_call_log ORDER BY rowid"
            )
        ]
        pulls = {
            str(r[0])
            for r in conn.execute(
                "SELECT channel FROM sys_usage_signals WHERE signal = 'dec.waiting.pull'"
            )
        }
    assert [(c, t) for c, t, _ in calls] == [("desk", "dec_waiting"), ("desk", "dec_context")]
    assert pulls == {"cli", "mcp"}


# ==================================================================================================
# AT-K6 through DEC's own writes


def test_a_canary_in_imported_decisions_stays_in_the_decision_tables(
    data_root: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    canary = make_canary("decision-statement")

    def plant(doc: dict[str, Any]) -> None:
        d907 = next(d for d in doc["decisions"] if d["v1_id"] == 907)
        d907["statement"] = f"Rent the small room ({canary})"
        d907["facts"][0]["fact"] = f"The landlord said {canary}"
        d907["assumptions"][0]["notes"] = canary

    doc = sb.planted(sb.s1, plant)
    snapshot = sb.write(doc, tmp_path / "inbox" / "s1_canary.json")
    launcher = AppLauncher(clock=clock)
    assert (
        _cli(["init", "--role", "dev", "--timezone", "Europe/Berlin"], launcher, capsys, data_root)[
            0
        ]
        == 0
    )
    clock.set(IMPORT_AT["s1.json"])
    code, out, err = _cli(["dec", "import", "v1", str(snapshot)], launcher, capsys, data_root)
    assert code == 0, err or out
    card = _json(["dec", "show", "D-0907", "--full"], launcher, capsys, data_root)
    assert canary in json.dumps(card), "the owner's own card shows the record"

    with composition.open_core(data_root, clock=clock), read_connection() as conn:
        dec_tables = [
            str(r[0])
            for r in conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")
            if str(r[0]).startswith("dec_")
        ]
        held = {h.table for h in scan_database(conn, canary, tables=dec_tables)}
        leaks = scan_database(conn, canary, exclude=dec_tables)
        events = int(conn.execute("SELECT count(*) FROM sys_events").fetchone()[0])
    assert {"dec_decisions", "dec_facts"} <= held
    assert events > 0
    assert leaks == []
