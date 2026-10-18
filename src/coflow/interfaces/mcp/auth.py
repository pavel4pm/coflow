"""Per-client MCP tokens and the MCP call log (``mcp_clients``, ``mcp_call_log``; MCP-1, spec §2.3,
§5.5).

Owned by track X (interfaces); increment I1, spec §12.2.

- A token is shown once, when ``coflow mcp token new`` issues it; only its SHA-256 hash is stored.
  Its random part comes from ``kernel.context.new_salt()``, the one source of randomness.
- A client has a name (``claude-desktop``), a scope (``read``, or ``write`` which includes read) and
  the ``financial`` flag (money amounts are withheld from it otherwise). Its actor is
  ``mcp_<client>``. A new token for an existing client replaces the old one, which stops working
  at once (rotation).
- A read-only token sees only the R tools and cannot call a write tool (``READ_ONLY_TOKEN``).
- Every tool call is logged with its client, tool, a hash of its arguments (never the arguments),
  the kind of result and the interaction id.

Spec note: §2.3 lists ``mcp_clients(client PK, token_hash, scopes, financial, revoked_at)`` and
``mcp_call_log(at, client, tool, args_hash, result_kind, interaction_id)``; the tables belong to the
kernel migration (track K), which declares ``mcp_clients`` with the mutable columns ``token_hash``,
``scopes``, ``financial`` and ``revoked_at`` (rotation) and ``mcp_call_log`` as append-only. This
module writes them through the store API in units of work owned by module ``mcp``. ``scopes`` is
stored as space-separated words (``read`` or ``read write``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from coflow.kernel.context import Clock, CommandContext, format_instant, new_salt
from coflow.kernel.store.api import insert, read_connection, unit_of_work, update_mutable

__all__ = [
    "CLIENT_NAME",
    "CallLog",
    "ClientIdentity",
    "ClientRegistry",
    "IssuedToken",
    "SqlCallLog",
    "SqlClientRegistry",
    "TokenScope",
    "args_hash",
    "bearer_token",
    "hash_token",
    "new_token",
    "scopes_for",
]

TokenScope = Literal["read", "write"]
CLIENT_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
"""A client name: lower-case letters, digits and hyphens, at most 32 characters."""

_TOKEN_PREFIX = "cfm_"


def new_token(prefix: str = _TOKEN_PREFIX) -> str:
    """A fresh bearer token: 256 random bits as hex behind a recognisable prefix."""
    return prefix + new_salt() + new_salt()


def hash_token(token: str) -> str:
    """The stored form of a token: SHA-256 hex of its UTF-8 bytes."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(authorization: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, else ``None``."""
    if not authorization:
        return None
    scheme, _, value = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def scopes_for(scope: TokenScope) -> frozenset[str]:
    """``write`` includes ``read``."""
    return frozenset({"read", "write"}) if scope == "write" else frozenset({"read"})


def args_hash(arguments: Mapping[str, object] | None) -> str:
    """A hash of a call's arguments for the log: the arguments themselves are never stored."""
    text = json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ClientIdentity:
    """Who is calling over MCP, as the verified token says."""

    client: str
    scopes: frozenset[str]
    financial: bool = False

    @property
    def actor(self) -> str:
        return f"mcp_{self.client}"

    @property
    def can_write(self) -> bool:
        return "write" in self.scopes


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedToken:
    client: str
    scope: TokenScope
    financial: bool
    token: str
    replaced: bool


@runtime_checkable
class ClientRegistry(Protocol):
    def issue(
        self, client: str, *, scope: TokenScope, financial: bool, ctx: CommandContext
    ) -> IssuedToken: ...

    def verify(self, token: str) -> ClientIdentity | None: ...


@runtime_checkable
class CallLog(Protocol):
    def log(
        self,
        identity: ClientIdentity,
        *,
        tool: str,
        arguments: Mapping[str, object] | None,
        result_kind: str,
        interaction_id: str,
    ) -> None: ...


def _check_client(client: str) -> None:
    if not CLIENT_NAME.match(client):
        raise ValueError(f"client name {client!r}: use 1-32 lower-case letters, digits and hyphens")


class SqlClientRegistry:
    """``mcp_clients`` through the store API of the bound store."""

    TABLE = "mcp_clients"

    def issue(
        self, client: str, *, scope: TokenScope, financial: bool, ctx: CommandContext
    ) -> IssuedToken:
        _check_client(client)
        if scope not in ("read", "write"):
            raise ValueError(f"scope {scope!r}: read or write")
        token = new_token()
        scopes = " ".join(sorted(scopes_for(scope)))
        with unit_of_work("mcp", ctx, command="mcp_token_new") as uow:
            existing = uow.fetch_one(f"SELECT client FROM {self.TABLE} WHERE client = ?", (client,))
            cols: dict[str, str | int | None] = {
                "token_hash": hash_token(token),
                "scopes": scopes,
                "financial": int(financial),
            }
            if existing is None:
                insert(self.TABLE, {"client": client, **cols})
            else:
                update_mutable(self.TABLE, {"client": client}, **cols, revoked_at=None)
        return IssuedToken(
            client=client,
            scope=scope,
            financial=financial,
            token=token,
            replaced=existing is not None,
        )

    def verify(self, token: str) -> ClientIdentity | None:
        digest = hash_token(token)
        with read_connection() as conn:
            row = conn.execute(
                f"SELECT client, token_hash, scopes, financial FROM {self.TABLE} "
                "WHERE token_hash = ? AND revoked_at IS NULL",
                (digest,),
            ).fetchone()
        if row is None or not hmac.compare_digest(str(row["token_hash"]), digest):
            return None
        return ClientIdentity(
            client=str(row["client"]),
            scopes=frozenset(str(row["scopes"]).split()),
            financial=bool(row["financial"]),
        )


class SqlCallLog:
    """``mcp_call_log`` through the store API: one small unit per call (module ``mcp``)."""

    TABLE = "mcp_call_log"

    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def log(
        self,
        identity: ClientIdentity,
        *,
        tool: str,
        arguments: Mapping[str, object] | None,
        result_kind: str,
        interaction_id: str,
    ) -> None:
        ctx = CommandContext(
            actor=identity.actor, channel="mcp", owner_channel=False, interaction_id=interaction_id
        )
        with unit_of_work("mcp", ctx, command="mcp_call"):
            insert(
                self.TABLE,
                {
                    "at": format_instant(self.clock.now()),
                    "client": identity.client,
                    "tool": tool,
                    "args_hash": args_hash(arguments),
                    "result_kind": result_kind,
                    "interaction_id": interaction_id,
                },
            )
