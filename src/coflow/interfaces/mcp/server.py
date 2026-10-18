"""The Streamable HTTP MCP listener on loopback: per-client tokens, Host and Origin checks, a token
on every request (no token → 401), every call logged in ``mcp_call_log``, every answer stating
the instance role and, for mirrors, the authority (MCP-1, AT-M1).

Owned by track X (interfaces); increment I1, spec §12.2.

Built on the official ``mcp`` SDK's low-level ``Server`` and its ``StreamableHTTPSessionManager``,
in **stateless JSON mode**: every request is authenticated on its own and answered with one JSON
body, so no session can be carried over from one token to another and the stdio shim stays a plain
request forwarder. Layers, outermost first:

1. ``LoopbackGuard`` (every route of the core's listener): the ``Host`` header must name the
   loopback listener with its port (else 421), and an ``Origin``, when present, must be the same
   loopback origin (else 403): DNS-rebinding protection is always on. The SDK's own transport
   check repeats the same allow-list.
2. ``BearerAuth`` (the ``/mcp`` route): ``Authorization: Bearer <token>`` must verify against
   ``mcp_clients`` (else 401 with ``WWW-Authenticate``); the verified ``ClientIdentity`` travels
   in the ASGI scope to the tool handlers.
3. The tool handlers: a read-only token sees only the R tools and cannot call a write tool
   (``READ_ONLY_TOKEN``); arguments are checked against the tool's schema; the answer is the view
   of ``interfaces/views/card.py``; the call is logged with its client.

Spec note: the listener binds 127.0.0.1 only (§4.5); ``localhost`` and ``[::1]`` with the same
port are accepted in the Host header because local clients send them for the same socket.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

import anyio.to_thread
import jsonschema
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

import coflow
from coflow.interfaces.mcp.auth import CallLog, ClientIdentity, ClientRegistry, bearer_token
from coflow.interfaces.mcp.catalogue import (
    CATALOGUE,
    SERVER_INSTRUCTIONS,
    ToolSpec,
    tool,
    visible_tools,
)
from coflow.interfaces.mcp.tools_dec import (
    HANDLERS,
    ArgumentError,
    McpDeps,
    ToolCall,
    ToolHandler,
)
from coflow.interfaces.views.card import SERVER_NAME, Wire, error_view
from coflow.kernel.context import CommandContext, new_salt
from coflow.kernel.errors import CoflowError, NotFound, RefusalCode, Refused

__all__ = [
    "IDENTITY_KEY",
    "LOOPBACK",
    "BearerAuth",
    "LoopbackGuard",
    "McpEndpoint",
    "build_mcp_server",
    "loopback_hosts",
    "loopback_origins",
    "mcp_endpoint",
]

log = logging.getLogger("coflow.mcp")

LOOPBACK = "127.0.0.1"
IDENTITY_KEY = "coflow.mcp.client"
"""The ASGI scope key that carries the verified ``ClientIdentity`` to the handlers."""


def loopback_hosts(port: int) -> frozenset[str]:
    return frozenset({f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"})


def loopback_origins(port: int) -> frozenset[str]:
    return frozenset(f"http://{host}" for host in loopback_hosts(port))


async def _plain(
    send: Send, status: int, text: str, headers: Iterable[tuple[bytes, bytes]] = ()
) -> None:
    body = json.dumps({"error": {"type": "http", "status": status, "detail": text}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    values = [v for k, v in scope.get("headers", ()) if k.lower() == name]
    if len(values) != 1:
        return None if not values else "\x00ambiguous"
    return values[0].decode("latin-1")


class LoopbackGuard:
    """Host and Origin allow-list for every route of the loopback listener (DNS rebinding)."""

    def __init__(self, app: ASGIApp, *, port: int) -> None:
        self.app = app
        self.hosts = loopback_hosts(port)
        self.origins = loopback_origins(port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        host = _header(scope, b"host")
        if host is None or host not in self.hosts:
            await _plain(send, 421, "the Host header does not name this loopback listener")
            return
        origin = _header(scope, b"origin")
        if origin is not None and origin not in self.origins:
            await _plain(send, 403, "the Origin is not allowed")
            return
        await self.app(scope, receive, send)


class BearerAuth:
    """A client token on every MCP request: no token or an unknown one gives 401."""

    def __init__(self, app: ASGIApp, *, clients: ClientRegistry) -> None:
        self.app = app
        self.clients = clients

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = bearer_token(_header(scope, b"authorization"))
        identity = None
        if token is not None:
            identity = await anyio.to_thread.run_sync(self.clients.verify, token)
        if identity is None:
            challenge = f'Bearer realm="{SERVER_NAME}"'.encode()
            await _plain(
                send,
                401,
                "a client token is required: coflow mcp token new --client NAME --scope read",
                [(b"www-authenticate", challenge)],
            )
            return
        scope[IDENTITY_KEY] = identity
        await self.app(scope, receive, send)


# --------------------------------------------------------------------------------------------------
# The tools


@dataclass(frozen=True, slots=True)
class _Outcome:
    payload: Wire
    kind: str  # the result_kind of mcp_call_log


def _invalid(detail: str, role: str | None) -> Wire:
    return {
        "server": SERVER_NAME,
        "view": "error",
        "instance_role": role,
        "error": {
            "type": "invalid_arguments",
            "code": None,
            "detail": detail,
            "missing": [],
            "allowed": [],
            "candidates": [],
        },
    }


def _internal(role: str | None) -> Wire:
    payload = _invalid("internal error; the core's log has the details", role)
    error = cast(dict[str, object], payload["error"])
    error["type"] = "internal"
    return payload


def _result_kind(err: CoflowError) -> str:
    if isinstance(err, Refused):
        return f"refused:{err.code}"
    return err.type_name


def _role(deps: McpDeps) -> str | None:
    try:
        return deps.facts.role()
    except Exception:  # the role is stated when it can be read; an error answer still goes out
        log.exception("could not read the instance role")
        return None


def _run_tool(
    deps: McpDeps,
    spec: ToolSpec | None,
    handler: ToolHandler | None,
    name: str,
    identity: ClientIdentity,
    ctx: CommandContext,
    arguments: Mapping[str, object],
    read_tools: list[str],
) -> _Outcome:
    if spec is None or handler is None:
        err = NotFound(name, f"no tool named {name}")
        return _Outcome(error_view(err, instance_role=_role(deps)), "unknown_tool")
    if not spec.read_only and not identity.can_write:
        err = Refused(
            RefusalCode.READ_ONLY_TOKEN,
            f"{name} writes, and this client's token is read-only; the owner can issue a write "
            "token with: coflow mcp token new --client NAME --scope write",
            allowed=read_tools,
        )
        return _Outcome(error_view(err, instance_role=_role(deps)), _result_kind(err))
    try:
        jsonschema.validate(dict(arguments), dict(spec.input_schema))
    except jsonschema.ValidationError as exc:
        return _Outcome(_invalid(exc.message, _role(deps)), "invalid_arguments")
    call = ToolCall(identity=identity, ctx=ctx, arguments=arguments)
    try:
        return _Outcome(handler(deps, call), "ok")
    except CoflowError as err:
        return _Outcome(error_view(err, instance_role=_role(deps)), _result_kind(err))
    except ArgumentError as exc:
        return _Outcome(_invalid(str(exc), _role(deps)), "invalid_arguments")
    except Exception:  # every call is answered and logged; the details stay in the core's log
        log.exception("tool %s failed", name)
        return _Outcome(_internal(_role(deps)), "error")


def _identity(ctx: Any) -> ClientIdentity:
    request = getattr(ctx, "request", None)
    identity = None if request is None else request.scope.get(IDENTITY_KEY)
    if not isinstance(identity, ClientIdentity):
        # Only reachable when the server is served without BearerAuth: refuse rather than guess.
        raise PermissionError("unauthenticated MCP request")
    return identity


def _tool_model(spec: ToolSpec) -> types.Tool:
    return types.Tool(
        name=spec.name,
        description=spec.description,
        input_schema=dict(spec.input_schema),
        annotations=types.ToolAnnotations(
            read_only_hint=spec.read_only,
            destructive_hint=False if spec.read_only else None,
            open_world_hint=False,
        ),
    )


def build_mcp_server(
    deps: McpDeps,
    *,
    call_log: CallLog,
    catalogue: Iterable[ToolSpec] = CATALOGUE,
    handlers: Mapping[str, ToolHandler] = HANDLERS,
    interaction_ids: Callable[[], str] | None = None,
) -> Server[Any]:
    """The ``coflow-v2`` MCP server over ``deps``. Every catalogue entry must have a handler."""
    tools = tuple(catalogue)
    missing = [t.name for t in tools if t.name not in handlers]
    if missing:
        raise ValueError(f"catalogue entries without a handler: {', '.join(missing)}")
    read_tools = [t.name for t in tools if t.read_only]
    next_id = interaction_ids or (lambda: "mcp-" + new_salt()[:16])

    async def list_tools(
        ctx: Any, params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        identity = _identity(ctx)
        return types.ListToolsResult(
            tools=[_tool_model(t) for t in visible_tools(identity.scopes, tools)]
        )

    async def call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        identity = _identity(ctx)
        arguments: Mapping[str, object] = params.arguments or {}
        interaction_id = next_id()
        command_ctx = CommandContext(
            actor=identity.actor, channel="mcp", owner_channel=False, interaction_id=interaction_id
        )
        spec = tool(params.name, tools)
        handler = handlers.get(params.name) if spec is not None else None
        outcome = await anyio.to_thread.run_sync(
            partial(
                _run_tool,
                deps,
                spec,
                handler,
                params.name,
                identity,
                command_ctx,
                arguments,
                read_tools,
            )
        )
        await anyio.to_thread.run_sync(
            partial(
                call_log.log,
                identity,
                tool=params.name,
                arguments=arguments,
                result_kind=outcome.kind,
                interaction_id=interaction_id,
            )
        )
        text = json.dumps(outcome.payload, ensure_ascii=False, separators=(",", ":"))
        return types.CallToolResult(
            content=[types.TextContent(text=text)],
            structured_content=outcome.payload,
            is_error=outcome.kind != "ok",
        )

    return Server(
        SERVER_NAME,
        version=coflow.__version__,
        title="CoFlow 2.0",
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


@dataclass(frozen=True, slots=True)
class McpEndpoint:
    """The ``/mcp`` ASGI app and the session manager whose ``run()`` the listener's lifespan
    enters."""

    asgi: ASGIApp
    manager: StreamableHTTPSessionManager
    server: Server[Any]


def mcp_endpoint(
    deps: McpDeps,
    *,
    clients: ClientRegistry,
    call_log: CallLog,
    port: int,
    catalogue: Iterable[ToolSpec] = CATALOGUE,
    handlers: Mapping[str, ToolHandler] = HANDLERS,
) -> McpEndpoint:
    """The authenticated Streamable HTTP endpoint (stateless, JSON responses)."""
    server = build_mcp_server(deps, call_log=call_log, catalogue=catalogue, handlers=handlers)
    manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=sorted(loopback_hosts(port)),
            allowed_origins=sorted(loopback_origins(port)),
        ),
    )
    asgi = BearerAuth(StreamableHTTPASGIApp(manager), clients=clients)
    return McpEndpoint(asgi=asgi, manager=manager, server=server)
