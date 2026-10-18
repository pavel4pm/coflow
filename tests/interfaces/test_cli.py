"""The ``coflow`` command line of I1 (spec §5.6) over fake core services."""

from __future__ import annotations

import io
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.interfaces.admin import cli
from coflow.interfaces.admin.cli import main
from coflow.kernel.errors import RefusalCode, Refused
from coflow.kernel.ops.doctor import DoctorCheck, DoctorReport
from coflow.kernel.ops.instance import InstanceInfo
from tests.interfaces import fakes
from tests.interfaces.fakes import FakeDecService, FakeLauncher, MemoryClients, make_services


@pytest.fixture
def world(tmp_path: Path) -> tuple[Path, FakeDecService, FakeLauncher]:
    root = tmp_path / "coflow-data"
    root.mkdir()
    dec = FakeDecService()
    return root, dec, FakeLauncher(make_services(root, dec=dec))


def run(
    argv: list[str], launcher: FakeLauncher | None, capsys: pytest.CaptureFixture[str], **env: str
) -> tuple[int, str, str]:
    code = main(argv, launcher=launcher, environ=env)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_usage_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, _, err = run(["dec", "waiting"], None, capsys)
    assert code == 2
    assert "COFLOW_DATA_ROOT" in err
    assert run(["dec", "show"], None, capsys)[0] == 2
    assert (
        run(["dec", "waiting", "--date", "tomorrow", "--data-root", str(tmp_path)], None, capsys)[0]
        == 2
    )
    assert (
        run(["dec", "shadow", "--run", "first", "--data-root", str(tmp_path)], None, capsys)[0] == 2
    )
    assert run(["dec", "integrity", "--data-root", str(tmp_path)], None, capsys)[0] == 2
    code, out, _ = run(["--help"], None, capsys)
    assert code == 0
    assert "coflow" in out


def test_the_data_root_comes_from_the_environment(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    code, out, _ = run(["dec", "list"], launcher, capsys, COFLOW_DATA_ROOT=str(root))
    assert code == 0
    assert "D-0903" in out
    assert launcher.opened == 1


def test_init_and_doctor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def fake_init(data_root: Path, **kw: Any) -> InstanceInfo:
        seen.update(kw, data_root=data_root)
        return InstanceInfo(
            instance_id="inst-1",
            role=kw["role"],
            volume_id="vol-1",
            created_at=datetime(2026, 11, 15, tzinfo=UTC),
        )

    monkeypatch.setattr(cli, "init_instance", fake_init)
    root = tmp_path / "new-root"
    code, out, _ = run(
        ["init", "--role", "validation", "--timezone", "Europe/Berlin", "--data-root", str(root)],
        None,
        capsys,
    )
    assert code == 0
    assert seen["role"] == "validation"
    assert seen["timezone"] == "Europe/Berlin"
    assert seen["issuer"] == "CF"
    assert seen["data_root"] == root.resolve()
    assert "validation instance inst-1" in out

    code, out, _ = run(["init", "--role", "dev", "--data-root", str(root)], None, capsys)
    assert code == 0
    assert seen["timezone"] == "UTC"
    assert "no --timezone" in out
    assert (
        run(
            ["init", "--role", "dev", "--timezone", "Mars/Olympus", "--data-root", str(root)],
            None,
            capsys,
        )[0]
        == 2
    )
    assert run(["init", "--role", "staging", "--data-root", str(root)], None, capsys)[0] == 2

    def refuse(data_root: Path, **kw: Any) -> InstanceInfo:
        raise Refused(
            RefusalCode.DATA_ROOT_IN_REPOSITORY, "the data root lies inside a git working tree"
        )

    monkeypatch.setattr(cli, "init_instance", refuse)
    code, _, err = run(
        ["init", "--role", "validation", "--timezone", "UTC", "--data-root", str(root)],
        None,
        capsys,
    )
    assert code == 1
    assert "DATA_ROOT_IN_REPOSITORY" in err

    report = DoctorReport(
        data_root=root,
        checks=(
            DoctorCheck(name="role", ok=True, detail="dev"),
            DoctorCheck(name="lock", ok=False, detail="held"),
        ),
    )
    monkeypatch.setattr(cli, "run_doctor", lambda data_root: report)
    code, out, _ = run(["doctor", "--data-root", str(root)], None, capsys)
    assert code == 1
    assert "[FAIL] lock: held" in out
    monkeypatch.setattr(
        cli, "run_doctor", lambda data_root: replace(report, checks=report.checks[:1])
    )
    assert run(["doctor", "--data-root", str(root)], None, capsys)[0] == 0


def test_run_hands_over_to_the_launcher(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    assert run(["run", "--port", "8800", "--data-root", str(root)], launcher, capsys)[0] == 0
    assert launcher.served == [(root.resolve(), 8800)]


def test_token_new(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    code, out, _ = run(
        ["mcp", "token", "new", "--client", "desk", "--scope", "read", "--data-root", str(root)],
        launcher,
        capsys,
    )
    assert code == 0
    token = next(line.strip() for line in out.splitlines() if line.strip().startswith("cfm_"))
    clients = launcher.services.clients
    assert isinstance(clients, MemoryClients)
    identity = clients.verify(token)
    assert identity is not None
    assert identity.scopes == frozenset({"read"})
    assert clients.contexts[0].owner_channel
    assert clients.contexts[0].channel == "cli"
    assert "shown once" in out

    code, out, _ = run(
        [
            "mcp",
            "token",
            "new",
            "--client",
            "desk",
            "--scope",
            "write",
            "--financial",
            "--json",
            "--data-root",
            str(root),
        ],
        launcher,
        capsys,
    )
    value = json.loads(out)["value"]
    assert value["replaced"] is True
    assert value["financial"] is True
    assert clients.verify(token) is None, "the old token stops working"
    code, _, err = run(
        ["mcp", "token", "new", "--client", "DESK", "--scope", "read", "--data-root", str(root)],
        launcher,
        capsys,
    )
    assert code == 1
    assert "invalid_arguments" in err


def test_import(
    world: tuple[Path, FakeDecService, FakeLauncher],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    root, dec, launcher = world
    snapshot = tmp_path / "inbox" / "snapshot-s1.json"
    snapshot.parent.mkdir()
    snapshot.write_text("{}", encoding="utf-8")
    code, out, _ = run(
        ["dec", "import", "v1", str(snapshot), "--data-root", str(root)], launcher, capsys
    )
    assert code == 0
    assert "Import run 1: applied (mode shadow, from V1, synthetic)" in out
    assert "decisions: seen 8, new 8" in out
    name, args = dec.calls[-1]
    assert name == "import_snapshot"
    assert args["file"] == snapshot.resolve()
    assert args["ctx"].owner_channel
    run(
        ["dec", "import", "v1", str(snapshot), "--final", "--data-root", str(root)],
        launcher,
        capsys,
    )
    assert dec.calls[-1][1]["mode"] == "final"
    run(
        ["dec", "import", "v1", str(snapshot), "--dry-run", "--data-root", str(root)],
        launcher,
        capsys,
    )
    assert dec.calls[-1][1]["mode"] == "dry_run"
    assert (
        run(
            [
                "dec",
                "import",
                "v1",
                str(snapshot),
                "--final",
                "--dry-run",
                "--data-root",
                str(root),
            ],
            launcher,
            capsys,
        )[0]
        == 2
    )
    assert (
        run(
            ["dec", "import", "v1", str(tmp_path / "missing.json"), "--data-root", str(root)],
            launcher,
            capsys,
        )[0]
        == 2
    )

    real = tmp_path / "inbox" / "real.json"
    real.write_text("{}", encoding="utf-8")
    code, _, err = run(
        ["dec", "import", "v1", str(real), "--data-root", str(root)], launcher, capsys
    )
    assert code == 1
    assert "refused IMPORT_NOT_SYNTHETIC: a dev instance imports synthetic files only" in err
    assert "instance: dev" in err


def test_show_list_integrity_shadow(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, dec, launcher = world
    data = ["--data-root", str(root)]
    code, out, _ = run(
        [
            "dec",
            "show",
            "D905",
            "--full",
            "--as-of",
            "2026-11-01T12:00Z",
            "--axis",
            "instance",
            *data,
        ],
        launcher,
        capsys,
    )
    assert code == 0
    _, args = dec.calls[-1]
    assert args["detail"] == "full"
    assert args["as_of"] == datetime(2026, 11, 1, 12, tzinfo=UTC)
    assert args["axis"] == "instance"
    assert args["audience"] == "owner"
    assert "A-02 [VIOLATED] The landlord keeps the price" in out
    assert "450 EUR" in out, "the owner's card shows amounts"
    assert "mirror: mirrored from V1" in out

    code, _, err = run(["dec", "show", "D-0999", *data], launcher, capsys)
    assert code == 1
    assert "not_found NOT_FOUND: D-0999 not found" in err
    code, out, _ = run(["dec", "show", "D-0999", "--json", *data], launcher, capsys)
    assert code == 1
    assert json.loads(out)["error"]["code"] == "NOT_FOUND"

    run(
        [
            "dec",
            "list",
            "--status",
            "active",
            "--kind",
            "test",
            "--mirror",
            "V1",
            "--health",
            "WATCH",
            "--limit",
            "5",
            *data,
        ],
        launcher,
        capsys,
    )
    _, args = next(
        c for c in reversed(dec.calls) if c[0] == "list_decisions" and c[1].get("limit") == 5
    )
    assert args == {
        "status": "active",
        "kind": "test",
        "health": "WATCH",
        "linked_to": None,
        "mirror": "V1",
        "limit": 5,
    }

    code, out, _ = run(["dec", "integrity", "--all", *data], launcher, capsys)
    assert code == 0
    assert (
        dec.calls[0] == ("integrity", {"ref": "all"}) or ("integrity", {"ref": "all"}) in dec.calls
    )
    assert "D-0905: NOT OK" in out
    assert "live: drift (statement)" in out
    run(["dec", "integrity", "D-0905", *data], launcher, capsys)
    assert ("integrity", {"ref": "D-0905"}) in dec.calls

    code, out, _ = run(["dec", "shadow", *data], launcher, capsys)
    assert code == 0
    assert ("shadow_report", {"run_id": None}) in dec.calls
    assert "totals: same 40, expected 3, unexpected 1, finding 0" in out
    assert "D-0904 D-0904_A-01 due: V1 2026-11-20 | v2 2026-11-18" in out
    run(["dec", "shadow", "--run", "2", *data], launcher, capsys)
    assert ("shadow_report", {"run_id": 2}) in dec.calls


def test_waiting_brief_has_at_most_eight_lines(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, dec, launcher = world
    base = fakes.standard_items()
    dec.items = [
        fakes.waiting_item(
            910 + i, f"Synthetic item {i}", "WATCH", *base[i % 4].reasons, actions=("review now",)
        )
        for i in range(10)
    ]
    dec.lines = [*dec.lines]
    code, out, _ = run(["dec", "waiting", "--brief", "--data-root", str(root)], launcher, capsys)
    assert code == 0
    items = [ln for ln in out.splitlines() if ln[:1].isdigit()]
    assert len(items) == 8
    assert all(" -> review now" in ln for ln in items)
    assert "... 2 more: coflow dec waiting" in out
    assert out.splitlines()[0] == "Waiting on 2026-11-15 (10 items)"
    again = run(["dec", "waiting", "--brief", "--data-root", str(root)], launcher, capsys)[1]
    assert again == out, "the brief list is deterministic"
    goal_line = next(ln for ln in items if "V1_G901" in ln)
    assert "(+1)" in goal_line, "a second reason is counted"


def test_waiting_full_shows_reasons_and_likely_actions(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    code, out, _ = run(
        ["dec", "waiting", "--data-root", str(root), "--date", "2026-11-15"], launcher, capsys
    )
    assert code == 0
    assert "Review date passed on 2026-11-10" in out
    assert "likely: close | cancel | keep until 2026-12-15" in out
    assert "1 of 2 assumptions cannot be checked (50 %)" in out
    assert "as of 2026-11-15 10:30 (Europe/Berlin)" in out
    # §3.9: a decision item without any fact says so instead of dropping the line.
    assert out.count("   last fact: no fact recorded") == 4


def test_recipe(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, out, _ = run(["dec", "waiting", "--recipe"], None, capsys)
    assert code == 0
    assert "coflow dec waiting --brief" in out
    assert "dec_waiting" in out
    assert "<DATA_ROOT>" in out
    _, out, _ = run(["dec", "waiting", "--recipe", "--data-root", str(tmp_path)], None, capsys)
    assert str(tmp_path) in out
    assert "<DATA_ROOT>" not in out
    _, out, _ = run(["dec", "waiting", "--help"], None, capsys)
    assert "morning pull" in out


def test_an_ephemeral_core_refused_by_the_lock(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    launcher.refuse = Refused(RefusalCode.INSTANCE_LOCKED, "another core holds the instance lock")
    code, _, err = run(["dec", "waiting", "--data-root", str(root)], launcher, capsys)
    assert code == 1
    assert "INSTANCE_LOCKED" in err


def test_mcp_stdio_never_resolves_a_data_root(
    world: tuple[Path, FakeDecService, FakeLauncher],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, launcher = world
    launcher.refuse = AssertionError("the shim opened the instance")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"")))
    code, _, err = run(["mcp-stdio"], launcher, capsys, COFLOW_DATA_ROOT=str(root))
    assert code == 2
    assert "COFLOW_MCP_TOKEN" in err
    code, _, _ = run(
        ["mcp-stdio"], launcher, capsys, COFLOW_DATA_ROOT=str(root), COFLOW_MCP_TOKEN="cfm_x"
    )
    assert code == 0
    code, _, err = run(
        ["mcp-stdio", "--url", "http://198.51.100.7:8741/mcp"],
        launcher,
        capsys,
        COFLOW_MCP_TOKEN="cfm_x",
    )
    assert code == 2
    assert "loopback" in err
    assert launcher.opened == 0


def test_an_internal_failure_names_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    class BrokenDec(FakeDecService):
        def waiting(self, *, today: object = None) -> Any:
            raise NotImplementedError("track D: modules/dec/queries.py")

    launcher = FakeLauncher(make_services(tmp_path, dec=BrokenDec()))
    code, _, err = run(["dec", "waiting", "--data-root", str(tmp_path)], launcher, capsys)
    assert code == 1
    assert "internal: internal error: NotImplementedError: track D" in err


def test_an_endpoint_file_naming_another_host_is_refused(
    world: tuple[Path, FakeDecService, FakeLauncher], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _, launcher = world
    (root / "run").mkdir()
    (root / "run" / "core.json").write_text(
        json.dumps(
            {
                "url": "http://decisions.example:8741",
                "pid": 1,
                "started_at": "2026-11-15T09:30:00.000Z",
                "admin_token": "cfa_x",
                "import_token": "cfa_y",
            }
        ),
        encoding="utf-8",
    )
    code, _, err = run(["dec", "list", "--data-root", str(root)], launcher, capsys)
    assert code == 2
    assert "loopback" in err
    assert launcher.opened == 0
