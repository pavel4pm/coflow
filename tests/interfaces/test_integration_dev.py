"""AT-M1 end to end on a real ``dev`` instance: the kernel (track K), the DEC queries (track D) and
the importer (track S) under the interfaces of track X.

Every track has landed (integration): a step that reaches an unfinished file fails instead of
skipping. The snapshot is the format's own synthetic example (``src/coflow/contracts/examples/``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coflow import contracts
from coflow.app import composition
from coflow.app.supervisor import AppLauncher
from coflow.interfaces.admin.cli import main
from coflow.kernel.context import FakeClock
from coflow.kernel.ops.init import init_instance
from coflow.modules.dec import api as dec_api
from tests.interfaces.harness import call_tool, issue, listener, rpc

EXAMPLE = "import_decisions_v1.example.json"


def _cli(
    argv: list[str], launcher: AppLauncher, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = main(argv, launcher=launcher, environ={})
    captured = capsys.readouterr()
    assert "NotImplementedError" not in captured.err, captured.err
    return code, captured.out, captured.err


def test_at_m1_on_a_dev_instance(
    data_root: Path,
    clock: FakeClock,
    owner_tz: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launcher = AppLauncher(clock=clock)
    snapshot = tmp_path / "inbox" / EXAMPLE
    snapshot.parent.mkdir()
    snapshot.write_bytes(contracts.load_example(EXAMPLE))
    root = ["--data-root", str(data_root)]

    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    code, out, err = _cli(["dec", "import", "v1", str(snapshot), *root], launcher, capsys)
    assert code == 0, err
    assert "applied" in out or "noop" in out
    code, out, err = _cli(["dec", "waiting", "--json", *root], launcher, capsys)
    assert code == 0, err
    over_cli = json.loads(out)
    assert over_cli["instance_role"] == "dev"

    with composition.open_core(data_root, clock=clock) as services:
        query = dec_api.waiting(dec_api.default_env())
        token = issue(services, "desk")
        with listener(services) as client:
            assert rpc(client, "tools/list", token=None).status_code == 401
            over_mcp = call_tool(client, "dec_waiting", {}, token=token)
        assert not over_mcp["_is_error"], over_mcp
        assert over_mcp["value"]["items"] == over_cli["value"]["items"]
        assert [i["ref"] for i in over_mcp["value"]["items"]] == [i.ref for i in query.value]
        refs = [i["ref"] for i in over_mcp["value"]["items"] if i["subject_kind"] == "decision"]
        for ref in refs[:1]:
            with listener(services) as client:
                card = call_tool(client, "dec_context", {"ref": ref}, token=token)
            assert card["instance_role"] == "dev"
            assert card["value"]["authority"]["system_of_record"] in ("V1", "this instance")
