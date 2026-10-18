"""``coflow run`` as its own process, stopped the way a service manager or a terminal stops it
(spec §4.5; integration): SIGTERM on Linux, Ctrl+Break on Windows. The core exits 0 after its
cleanup, so the endpoint file is gone and this run's admin tokens are revoked.

uvicorn shuts down gracefully on these signals and then raises them again; without the core's own
handler their default action would end the process before that cleanup.
"""

from __future__ import annotations

import http.client
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from coflow.app import composition
from coflow.kernel.context import FakeClock
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store.api import read_connection


def _root_args(data_root: Path) -> tuple[str, str]:
    return ("--data-root", str(data_root))


def _healthy(url: str) -> bool:
    host, _, port = url.removeprefix("http://").partition(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.request("GET", "/healthz")
        return conn.getresponse().status == 200
    except OSError:
        return False
    finally:
        conn.close()


def test_a_stopped_core_process_cleans_up(data_root: Path, clock: FakeClock, owner_tz: str) -> None:
    init_instance(data_root, role="dev", clock=clock, timezone=owner_tz)
    endpoint = data_root / "run" / "core.json"
    windows = sys.platform == "win32"
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coflow.app.supervisor",
            "run",
            *("--port", "0"),
            *_root_args(data_root),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if windows else 0,  # type: ignore[attr-defined]
    ) as core:
        try:
            deadline = time.monotonic() + 60
            url = None
            while time.monotonic() < deadline and core.poll() is None:
                if endpoint.exists():
                    url = json.loads(endpoint.read_text(encoding="utf-8"))["url"]
                    if _healthy(url):
                        break
                time.sleep(0.1)
            if url is None or not _healthy(url):
                core.kill()
                pytest.fail(f"the core did not start: {core.communicate()[1]}")
            core.send_signal(signal.CTRL_BREAK_EVENT if windows else signal.SIGTERM)  # type: ignore[attr-defined]
            code = core.wait(timeout=60)
        finally:
            if core.poll() is None:
                core.kill()
                core.wait(timeout=30)
    assert code == 0
    assert not endpoint.exists()
    with composition.open_core(data_root, clock=clock), read_connection() as conn:
        tokens = [
            tuple(r) for r in conn.execute("SELECT scope, revoked_at IS NOT NULL FROM adm_tokens")
        ]
    assert sorted(tokens) == [("admin", 1), ("import", 1)]
