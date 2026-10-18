"""The loopback admin API (``/admin``) with scoped tokens (``admin``, ``import``) in ``adm_tokens``
(spec §2.3, §5.6; ARCHITECTURE §6.8).

Owned by track X (interfaces); increment I1, spec §12.2.

The CLI is a thin client of this API. One operation table (``AdminService.dispatch``) serves both
paths the CLI can take, so they cannot drift apart:

- **core running** (``coflow run``): the CLI reads the endpoint file the core wrote in its data root
  (``run/core.json``: the loopback URL and this run's admin and import tokens) and posts
  ``/admin/v1/<operation>`` with a bearer token; it never opens the database;
- **core stopped**: the CLI starts an ephemeral core in process (``CoreLauncher.open``) under the
  same instance lock, and calls ``AdminService`` directly.

Either way the local CLI is an owner channel: the context is
``CommandContext(actor='owner', channel='cli', owner_channel=True)``.

Admin tokens are issued by the core at start, one per scope, shown only in the endpoint file, and
valid only for that run: their hashes are recorded in ``adm_tokens`` and revoked at shutdown.
``import`` operations need the ``import`` token; every other operation needs the ``admin`` token.

Operations of I1: ``ping``, ``dec.waiting``, ``dec.show``, ``dec.list``, ``dec.integrity``,
``dec.shadow``, ``dec.import.v1`` (scope ``import``) and ``mcp.token.new``.

Spec notes:

- ``adm_tokens`` belongs to the kernel migration (track K): append-only, ``revoked_at`` set once.
  This module writes it through the store API in units owned by module ``adm``; a revocation sets
  ``revoked_at`` on the row its insert returned (the table's key is its token hash, so the row is
  addressed by rowid).
- ``dec import v1 FILE`` sends the absolute path of the file, not its bytes: the admin API is
  loopback-only and the core runs on the same machine in stage 0A.
- The endpoint file lives under the data root (``run/core.json``); a token in it is as protected as
  the database next to it, and it is created with owner-only permissions where the OS supports it.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit

import anyio.to_thread
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from coflow.interfaces.mcp.auth import (
    CallLog,
    ClientRegistry,
    IssuedToken,
    bearer_token,
    hash_token,
    new_token,
)
from coflow.interfaces.views import card
from coflow.interfaces.views.card import (
    SERVER_NAME,
    DecService,
    InstanceFacts,
    UsageSink,
    Wire,
    error_view,
)
from coflow.kernel.context import (
    Axis,
    Clock,
    CommandContext,
    format_instant,
    new_salt,
    parse_instant,
)
from coflow.kernel.errors import (
    Ambiguous,
    CoflowError,
    Conflict,
    ContractViolation,
    NotFound,
    Refused,
)
from coflow.kernel.store.api import insert, set_once, unit_of_work
from coflow.modules.dec.api import model

__all__ = [
    "ENDPOINT_FILE",
    "OPERATIONS",
    "AdminClient",
    "AdminFailure",
    "AdminScope",
    "AdminService",
    "AdminTokens",
    "CoreEndpoint",
    "CoreLauncher",
    "HttpAdminClient",
    "LocalAdminClient",
    "Services",
    "SqlAdminTokens",
    "admin_routes",
    "owner_context",
    "read_endpoint",
    "remove_endpoint",
    "write_endpoint",
]

log = logging.getLogger("coflow.admin")

AdminScope = Literal["admin", "import"]
ENDPOINT_FILE = Path("run") / "core.json"

# ==================================================================================================
# Tokens of this core run


@dataclass(frozen=True, slots=True, kw_only=True)
class _Issued:
    token_hash: str
    scope: AdminScope
    rowid: int


class AdminTokens(Protocol):
    def issue(self, scope: AdminScope, *, ctx: CommandContext) -> str: ...

    def verify(self, token: str) -> AdminScope | None: ...

    def revoke_issued(self, *, ctx: CommandContext) -> None: ...


class SqlAdminTokens:
    """``adm_tokens`` rows for provenance; verification accepts only this run's tokens."""

    TABLE = "adm_tokens"

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self._issued: dict[str, _Issued] = {}

    def issue(self, scope: AdminScope, *, ctx: CommandContext) -> str:
        token = new_token("cfa_")
        digest = hash_token(token)
        with unit_of_work("adm", ctx, command="adm_token_issue"):
            rowid = insert(
                self.TABLE,
                {
                    "token_hash": digest,
                    "scope": scope,
                    "created_at": format_instant(self.clock.now()),
                },
            )
        self._issued[digest] = _Issued(token_hash=digest, scope=scope, rowid=rowid)
        return token

    def verify(self, token: str) -> AdminScope | None:
        issued = self._issued.get(hash_token(token))
        return None if issued is None else issued.scope

    def revoke_issued(self, *, ctx: CommandContext) -> None:
        if not self._issued:
            return
        at = format_instant(self.clock.now())
        with unit_of_work("adm", ctx, command="adm_token_revoke"):
            for digest in sorted(self._issued):
                set_once(self.TABLE, self._issued[digest].rowid, revoked_at=at)
        self._issued.clear()


# ==================================================================================================
# What the core gives the interfaces


@dataclass(frozen=True, slots=True, kw_only=True)
class Services:
    """Everything the admin API and the MCP listener need from one open instance.

    Built by the composition root (``coflow.app.composition``) over the bound store; tests build it
    from fakes. It satisfies ``interfaces.mcp.tools_dec.McpDeps``.
    """

    dec: DecService
    facts: InstanceFacts
    usage: UsageSink
    clients: ClientRegistry
    call_log: CallLog
    admin_tokens: AdminTokens
    clock: Clock
    data_root: Path


class CoreLauncher(Protocol):
    """How the CLI reaches the composition root without importing it (``coflow.app`` sits above
    ``coflow.interfaces`` in the import contract)."""

    def open(self, data_root: Path) -> AbstractContextManager[Services]:
        """An ephemeral core: the store opened under the instance lock, bound, and its services."""
        ...

    def serve(self, data_root: Path, *, port: int) -> int:
        """``coflow run``: serve MCP and the admin API on loopback until stopped; an exit code."""
        ...


def owner_context(interaction_id: str) -> CommandContext:
    """The local CLI: an owner channel (§5.1)."""
    return CommandContext(
        actor="owner", channel="cli", owner_channel=True, interaction_id=interaction_id
    )


# ==================================================================================================
# The operation table


class AdminFailure(Exception):
    """An operation that did not succeed, with the error view to show and an HTTP status."""

    def __init__(self, payload: Wire, status: int) -> None:
        self.payload = payload
        self.status = status
        error = payload.get("error")
        detail = error.get("detail") if isinstance(error, dict) else None
        super().__init__(str(detail or payload))


class _Invalid(ValueError):
    """An argument the operation cannot use (HTTP 400)."""


def _invalid_view(detail: str, role: str | None) -> Wire:
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


class _Args:
    def __init__(self, raw: Mapping[str, object]) -> None:
        self.raw = raw

    def text(self, key: str, *, required: bool = False) -> str | None:
        value = self.raw.get(key)
        if value is None:
            if required:
                raise _Invalid(f"{key} is required")
            return None
        if not isinstance(value, str):
            raise _Invalid(f"{key} must be text")
        return value

    def choice(self, key: str, allowed: tuple[str, ...], default: str) -> str:
        value = self.text(key) or default
        if value not in allowed:
            raise _Invalid(f"{key} must be one of {', '.join(allowed)}")
        return value

    def flag(self, key: str) -> bool:
        value = self.raw.get(key, False)
        if not isinstance(value, bool):
            raise _Invalid(f"{key} must be true or false")
        return value

    def integer(self, key: str, *, minimum: int = 1, maximum: int | None = None) -> int | None:
        value = self.raw.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise _Invalid(f"{key} must be an integer")
        if value < minimum or (maximum is not None and value > maximum):
            raise _Invalid(f"{key} is out of range")
        return value

    def day(self, key: str) -> date | None:
        value = self.text(key)
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise _Invalid(f"{key} must be a date YYYY-MM-DD") from None


Operation = Callable[["AdminService", _Args, CommandContext], Wire]


class AdminService:
    """The admin operations over one instance's ``Services``."""

    def __init__(self, services: Services) -> None:
        self.services = services

    # -- operations ---------------------------------------------------------------------------

    def ping(self, args: _Args, ctx: CommandContext) -> Wire:
        facts = self.services.facts
        return {
            "server": SERVER_NAME,
            "view": "ping",
            "instance_role": facts.role(),
            "timezone": facts.timezone(),
        }

    def dec_waiting(self, args: _Args, ctx: CommandContext) -> Wire:
        brief = args.flag("brief")
        return card.waiting_view(
            self.services.dec,
            self.services.facts,
            today=args.day("date"),
            usage=(self.services.usage, ctx, "cli_brief" if brief else "cli"),
        )

    def dec_show(self, args: _Args, ctx: CommandContext) -> Wire:
        as_of = args.text("as_of")
        try:
            instant = None if as_of is None else parse_instant(as_of)
        except ValueError:
            raise _Invalid("as_of must be an ISO 8601 instant, e.g. 2026-11-01T12:00Z") from None
        return card.context_view(
            self.services.dec,
            self.services.facts,
            cast(str, args.text("ref", required=True)),
            detail="full" if args.flag("full") else "brief",
            as_of=instant,
            axis=cast(
                Axis, args.choice("axis", ("knowledge", "instance", "occurrence"), "knowledge")
            ),
            audience="owner",
        )

    def dec_list(self, args: _Args, ctx: CommandContext) -> Wire:
        return card.list_view(
            self.services.dec,
            self.services.facts,
            status=args.text("status"),
            kind=args.text("kind"),
            health=args.text("health"),
            linked_to=args.text("linked_to"),
            mirror=args.text("mirror"),
            limit=args.integer("limit", maximum=10_000) or 50,
        )

    def dec_integrity(self, args: _Args, ctx: CommandContext) -> Wire:
        ref = cast(str, args.text("ref", required=True))
        return card.integrity_view(self.services.dec, self.services.facts, ref)

    def dec_shadow(self, args: _Args, ctx: CommandContext) -> Wire:
        return card.shadow_view(
            self.services.dec,
            self.services.facts,
            run_id=args.integer("run_id"),
            usage=(self.services.usage, ctx, "cli"),
        )

    def dec_import_v1(self, args: _Args, ctx: CommandContext) -> Wire:
        path = Path(cast(str, args.text("path", required=True)))
        if not path.is_absolute():
            raise _Invalid("path must be absolute")
        if not path.is_file():
            raise _Invalid(f"no snapshot file at {path}")
        mode = args.choice("mode", ("shadow", "final", "dry_run"), "shadow")
        result = self.services.dec.import_snapshot(path, mode=cast(model.ImportMode, mode), ctx=ctx)
        facts = self.services.facts
        return card.import_view(result, instance_role=facts.role(), timezone=facts.timezone())

    def mcp_token_new(self, args: _Args, ctx: CommandContext) -> Wire:
        client = cast(str, args.text("client", required=True))
        scope = args.choice("scope", ("read", "write"), "read")
        try:
            issued = self.services.clients.issue(
                client,
                scope=cast(Literal["read", "write"], scope),
                financial=args.flag("financial"),
                ctx=ctx,
            )
        except ValueError as exc:
            raise _Invalid(str(exc)) from None
        return _token_view(issued, self.services.facts.role())

    # -- dispatch ----------------------------------------------------------------------------

    def dispatch(
        self,
        op: str,
        args: Mapping[str, object],
        *,
        interaction_id: str,
        scope: AdminScope | Literal["local"],
    ) -> Wire:
        """Run ``op``; raises ``AdminFailure`` with the error view on any refusal."""
        entry = OPERATIONS.get(op)
        if entry is None:
            raise AdminFailure(_invalid_view(f"no admin operation {op}", self._role()), 404)
        method, needed = entry
        if scope != "local" and scope != needed:
            detail = f"{op} needs the {needed} token"
            raise AdminFailure(_invalid_view(detail, self._role()), 403)
        ctx = owner_context(interaction_id)
        try:
            return method(self, _Args(args), ctx)
        except _Invalid as exc:
            raise AdminFailure(_invalid_view(str(exc), self._role()), 400) from None
        except CoflowError as err:
            raise AdminFailure(error_view(err, instance_role=self._role()), _status(err)) from err
        except (
            Exception
        ) as exc:  # the owner's own terminal: name the failure, keep the trace in the log
            log.exception("admin operation %s failed", op)
            payload = _invalid_view(f"internal error: {type(exc).__name__}: {exc}", self._role())
            cast(dict[str, object], payload["error"])["type"] = "internal"
            raise AdminFailure(payload, 500) from exc

    def _role(self) -> str | None:
        try:
            return self.services.facts.role()
        except Exception:  # an error answer still goes out without the role
            log.exception("could not read the instance role")
            return None


def _status(err: CoflowError) -> int:
    if isinstance(err, NotFound):
        return 404
    if isinstance(err, Refused | Ambiguous | Conflict):
        return 409
    if isinstance(err, ContractViolation):
        return 500
    return 400


def _token_view(issued: IssuedToken, role: str) -> Wire:
    return {
        "server": SERVER_NAME,
        "view": "mcp_token",
        "instance_role": role,
        "value": {
            "client": issued.client,
            "actor": f"mcp_{issued.client}",
            "scope": issued.scope,
            "financial": issued.financial,
            "replaced": issued.replaced,
            "token": issued.token,
        },
    }


OPERATIONS: Mapping[str, tuple[Operation, AdminScope]] = {
    "ping": (AdminService.ping, "admin"),
    "dec.waiting": (AdminService.dec_waiting, "admin"),
    "dec.show": (AdminService.dec_show, "admin"),
    "dec.list": (AdminService.dec_list, "admin"),
    "dec.integrity": (AdminService.dec_integrity, "admin"),
    "dec.shadow": (AdminService.dec_shadow, "admin"),
    "dec.import.v1": (AdminService.dec_import_v1, "import"),
    "mcp.token.new": (AdminService.mcp_token_new, "admin"),
}
"""Operation -> (method, the token scope it needs)."""

# ==================================================================================================
# HTTP


INTERACTION_HEADER = "x-coflow-interaction"
CLI_INTERACTION = re.compile(r"cli-[0-9a-f]{16}")


def admin_routes(service: AdminService, tokens: AdminTokens) -> list[Route]:
    """``POST /admin/v1/<operation>`` with a bearer token; the body is the arguments object."""

    async def endpoint(request: Request) -> JSONResponse:
        token = bearer_token(request.headers.get("authorization"))
        scope = None if token is None else tokens.verify(token)
        if scope is None:
            return JSONResponse(
                {"error": {"type": "http", "status": 401, "detail": "an admin token is required"}},
                status_code=401,
                headers={"www-authenticate": f'Bearer realm="{SERVER_NAME}-admin"'},
            )
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                _invalid_view("the body must be a JSON object", None), status_code=400
            )
        op = request.path_params["op"]
        raw = request.headers.get(INTERACTION_HEADER, "")
        # the header is the client's word: only the CLI's own id shape is kept, never free text
        interaction_id = raw if CLI_INTERACTION.fullmatch(raw) else "cli-" + new_salt()[:16]
        try:
            view = await anyio.to_thread.run_sync(
                lambda: service.dispatch(op, body, interaction_id=interaction_id, scope=scope)
            )
        except AdminFailure as failure:
            return JSONResponse(failure.payload, status_code=failure.status)
        return JSONResponse(view)

    return [Route("/admin/v1/{op}", endpoint, methods=["POST"])]


# ==================================================================================================
# Clients the CLI uses


class AdminClient(Protocol):
    def call(self, op: str, args: Mapping[str, object]) -> Wire:
        """The operation's view; raises ``AdminFailure`` with the error view otherwise."""
        ...


class LocalAdminClient:
    """The ephemeral core: ``AdminService`` in process, with every scope."""

    def __init__(self, service: AdminService, *, interaction_id: str) -> None:
        self.service = service
        self.interaction_id = interaction_id

    def call(self, op: str, args: Mapping[str, object]) -> Wire:
        return self.service.dispatch(op, args, interaction_id=self.interaction_id, scope="local")


@dataclass(frozen=True, slots=True, kw_only=True)
class CoreEndpoint:
    """What a running core tells the local CLI (``<data root>/run/core.json``)."""

    url: str  # http://127.0.0.1:<port>
    pid: int
    started_at: str
    admin_token: str
    import_token: str

    def token_for(self, scope: AdminScope) -> str:
        return self.import_token if scope == "import" else self.admin_token


def write_endpoint(data_root: Path, endpoint: CoreEndpoint) -> Path:
    path = data_root / ENDPOINT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(tmp, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(asdict(endpoint), fh, indent=2)
    os.replace(tmp, path)
    return path


def read_endpoint(data_root: Path) -> CoreEndpoint | None:
    path = data_root / ENDPOINT_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CoreEndpoint(**data)
    except (OSError, ValueError, TypeError):
        return None


def remove_endpoint(data_root: Path) -> None:
    (data_root / ENDPOINT_FILE).unlink(missing_ok=True)


class HttpAdminClient:
    """The admin API of a running core over loopback HTTP (standard library only)."""

    def __init__(
        self, endpoint: CoreEndpoint, *, interaction_id: str, timeout: float = 600.0
    ) -> None:
        parts = urlsplit(endpoint.url)
        if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(f"the admin API is loopback-only, not {endpoint.url}")
        self.endpoint = endpoint
        self.host = parts.hostname
        self.port = parts.port or 80
        self.interaction_id = interaction_id
        self.timeout = timeout

    def call(self, op: str, args: Mapping[str, object]) -> Wire:
        needed = OPERATIONS[op][1] if op in OPERATIONS else "admin"
        body = json.dumps(dict(args)).encode("utf-8")
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request(
                "POST",
                f"/admin/v1/{op}",
                body=body,
                headers={
                    "content-type": "application/json",
                    "authorization": f"Bearer {self.endpoint.token_for(needed)}",
                    INTERACTION_HEADER: self.interaction_id,
                },
            )
            response = conn.getresponse()
            raw = response.read()
            status = response.status
        finally:
            conn.close()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = {
                "error": {
                    "type": "http",
                    "status": status,
                    "detail": raw[:200].decode("utf-8", "replace"),
                }
            }
        if status != 200 or not isinstance(payload, dict):
            raise AdminFailure(payload if isinstance(payload, dict) else {"error": payload}, status)
        return payload
