"""``coflow run``: the core process (writer, in-process dispatch, the MCP listener and the admin
API); from 0B also the daily snapshot import and usage-signal job (spec §4.5).

Owned by track X (interfaces); increment I1, spec §12.2.

``serve`` opens the instance with ``composition.open_core`` (the instance lock makes a second core
refuse with ``INSTANCE_LOCKED``), binds one HTTP listener on **127.0.0.1 only**, and serves on it:

- ``/mcp``: the Streamable HTTP MCP endpoint (per-client tokens, read tools in I1);
- ``/admin/v1/<operation>``: the admin API the CLI uses, with this run's admin and import tokens;
- ``/healthz``: ``ok`` and nothing else.

Every route sits behind the Host and Origin allow-list (DNS-rebinding protection). At start the
core issues this run's admin tokens and writes the endpoint file (``<data root>/run/core.json``)
that the local CLI reads; on shutdown it removes the file and revokes the tokens.

``LAUNCHER`` is the ``CoreLauncher`` the CLI uses (ephemeral cores and ``coflow run``), and
``main`` is the entry point that passes it explicitly (see the spec note in
``interfaces/admin/cli.py``).
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import socket
import sys
import threading
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from coflow.app import composition
from coflow.interfaces.admin import cli
from coflow.interfaces.admin.api import (
    AdminService,
    CoreEndpoint,
    Services,
    admin_routes,
    remove_endpoint,
    write_endpoint,
)
from coflow.interfaces.admin.render import render_error
from coflow.interfaces.mcp.catalogue import CATALOGUE, ToolSpec
from coflow.interfaces.mcp.server import LOOPBACK, LoopbackGuard, mcp_endpoint
from coflow.interfaces.mcp.stdio_shim import DEFAULT_PORT
from coflow.interfaces.mcp.tools_dec import HANDLERS, ToolHandler
from coflow.interfaces.views.card import error_view
from coflow.kernel.context import Clock, CommandContext, format_instant, new_salt
from coflow.kernel.errors import CoflowError, Refused

__all__ = ["LAUNCHER", "AppLauncher", "RunningCore", "build_http_app", "main", "serve"]

log = logging.getLogger("coflow.core")

Opener = Callable[..., AbstractContextManager[Services]]


def build_http_app(
    services: Services,
    *,
    port: int,
    catalogue: Sequence[ToolSpec] = CATALOGUE,
    handlers: dict[str, ToolHandler] | None = None,
) -> Starlette:
    """The core's one loopback listener: ``/mcp``, ``/admin/v1/...`` and ``/healthz``."""
    endpoint = mcp_endpoint(
        services,
        clients=services.clients,
        call_log=services.call_log,
        port=port,
        catalogue=catalogue,
        handlers=handlers or HANDLERS,
    )

    async def healthz(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with endpoint.manager.run():
            yield

    app = Starlette(
        routes=[
            Route("/mcp", endpoint=endpoint.asgi, methods=["GET", "POST", "DELETE"]),
            *admin_routes(AdminService(services), services.admin_tokens),
            Route("/healthz", healthz, methods=["GET"]),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(LoopbackGuard, port=port)
    return app


@dataclass(frozen=True, slots=True)
class RunningCore:
    """Handed to ``serve``'s ``on_ready`` callback: where the core listens and how to stop it."""

    endpoint: CoreEndpoint
    port: int
    stop: Callable[[], None]


def _system_ctx() -> CommandContext:
    return CommandContext(
        actor="core",
        channel="system",
        owner_channel=False,
        interaction_id="core-" + new_salt()[:16],
    )


class _Stopped(Exception):
    """A stop signal (SIGTERM, Ctrl+Break) that reached the core after uvicorn's shutdown."""


def _stop_signal(signum: int, frame: FrameType | None) -> None:
    raise _Stopped(signum)


@contextlib.contextmanager
def _clean_stop() -> Iterator[None]:
    """Let a stop signal end ``serve`` through its cleanup (endpoint file, admin tokens).

    uvicorn catches SIGINT, SIGTERM and (on Windows) SIGBREAK, shuts down gracefully, restores the
    previous handlers and raises the signal again. With the default handlers SIGTERM and SIGBREAK
    would then end the process at once, before the core removes its endpoint file and revokes
    this run's admin tokens; this handler turns them into an exception instead (integration).
    Signals are only handled in the main thread; elsewhere (tests) nothing changes.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    wanted = [getattr(signal, n) for n in ("SIGTERM", "SIGBREAK") if hasattr(signal, n)]
    previous = {sig: signal.signal(sig, _stop_signal) for sig in wanted}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _bind(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((LOOPBACK, port))
        sock.listen(128)
    except OSError:
        sock.close()
        raise
    return sock


def serve(
    data_root: Path,
    *,
    port: int = DEFAULT_PORT,
    clock: Clock | None = None,
    opener: Opener | None = None,
    on_ready: Callable[[RunningCore], None] | None = None,
    log_level: str = "warning",
) -> int:
    """Serve the instance on 127.0.0.1 until stopped; the exit code (1 when refused)."""
    open_services = opener or composition.open_core
    try:
        with open_services(data_root, clock=clock) as services:
            return _serve_open(
                services, data_root, port=port, on_ready=on_ready, log_level=log_level
            )
    except CoflowError as err:
        print(render_error(error_view(err, instance_role=None)), file=sys.stderr)
        if isinstance(err, Refused) and err.code == "INSTANCE_LOCKED":
            print("another core already serves this data root", file=sys.stderr)
        return 1


def _serve_open(
    services: Services,
    data_root: Path,
    *,
    port: int,
    on_ready: Callable[[RunningCore], None] | None,
    log_level: str,
) -> int:
    try:
        sock = _bind(port)
    except OSError as exc:
        print(f"coflow run: cannot listen on {LOOPBACK}:{port}: {exc}", file=sys.stderr)
        return 1
    actual = sock.getsockname()[1]
    ctx = _system_ctx()
    tokens = services.admin_tokens
    endpoint = CoreEndpoint(
        url=f"http://{LOOPBACK}:{actual}",
        pid=os.getpid(),
        started_at=format_instant(services.clock.now()),
        admin_token=tokens.issue("admin", ctx=ctx),
        import_token=tokens.issue("import", ctx=ctx),
    )
    app = build_http_app(services, port=actual)
    server = uvicorn.Server(
        uvicorn.Config(app, log_level=log_level, access_log=False, lifespan="on")
    )
    write_endpoint(data_root, endpoint)
    try:
        with _clean_stop(), contextlib.suppress(_Stopped, KeyboardInterrupt):
            print(
                f"coflow core: MCP at {endpoint.url}/mcp, admin API at {endpoint.url}/admin "
                f"(data root {data_root}); Ctrl+C stops it",
                file=sys.stderr,
            )
            if on_ready is not None:
                on_ready(RunningCore(endpoint=endpoint, port=actual, stop=lambda: _stop(server)))
            server.run(sockets=[sock])
    finally:
        remove_endpoint(data_root)
        with contextlib.suppress(CoflowError):
            tokens.revoke_issued(ctx=ctx)
        sock.close()
    return 0


def _stop(server: uvicorn.Server) -> None:
    server.should_exit = True


class AppLauncher:
    """The ``CoreLauncher`` of the composition root."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self.clock = clock

    def open(self, data_root: Path) -> AbstractContextManager[Services]:
        return composition.open_core(data_root, clock=self.clock)

    def serve(self, data_root: Path, *, port: int) -> int:
        return serve(data_root, port=port, clock=self.clock)


LAUNCHER = AppLauncher()


def main(argv: Sequence[str] | None = None) -> int:
    """The ``coflow`` entry point with the composition root passed explicitly."""
    return cli.main(argv, launcher=LAUNCHER)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
