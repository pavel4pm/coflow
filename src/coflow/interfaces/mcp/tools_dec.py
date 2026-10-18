"""The ``dec_`` tools; in I1 the read tools ``dec_list``, ``dec_context`` (audience ``agent``),
``dec_waiting`` (records a pull usage signal), ``dec_integrity`` and ``dec_shadow_report`` (spec
§5.5).

Owned by track X (interfaces); increment I1, spec §12.2.

Each handler takes the server's dependencies and one validated call, and returns the same view the
admin API serves the CLI (``interfaces/views/card.py``), so an agent and the owner see identical
items in identical order (AT-M1). Arguments have already passed the tool's JSON Schema; dates are
``YYYY-MM-DD`` and instants ISO 8601 with ``Z`` or an offset, never free text (§5.1).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, cast

from coflow.interfaces.mcp.auth import ClientIdentity
from coflow.interfaces.views import card
from coflow.interfaces.views.card import DecService, InstanceFacts, UsageSink, Wire
from coflow.kernel.context import Axis, CommandContext, parse_instant
from coflow.modules.dec.api import model

__all__ = ["HANDLERS", "ArgumentError", "McpDeps", "ToolCall", "ToolHandler"]


class ArgumentError(ValueError):
    """An argument that passed the schema but is still unusable (``2026-02-31``)."""


class McpDeps(Protocol):
    """What the tools need from the core (``interfaces.admin.api.Services`` provides it)."""

    @property
    def dec(self) -> DecService: ...

    @property
    def facts(self) -> InstanceFacts: ...

    @property
    def usage(self) -> UsageSink: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    """One validated tool call: who calls, under which context, with which arguments."""

    identity: ClientIdentity
    ctx: CommandContext
    arguments: Mapping[str, object]

    def text(self, key: str) -> str | None:
        value = self.arguments.get(key)
        return None if value is None else str(value)

    def day(self, key: str) -> date | None:
        value = self.text(key)
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ArgumentError(f"{key}: {value!r} is not a date YYYY-MM-DD") from None

    def instant(self, key: str) -> datetime | None:
        value = self.text(key)
        if value is None:
            return None
        try:
            return parse_instant(value)
        except ValueError:
            raise ArgumentError(f"{key}: {value!r} is not an ISO 8601 instant") from None

    def integer(self, key: str) -> int | None:
        value = self.arguments.get(key)
        return None if value is None else int(cast(int, value))


ToolHandler = Callable[[McpDeps, ToolCall], Wire]


def dec_waiting(deps: McpDeps, call: ToolCall) -> Wire:
    return card.waiting_view(
        deps.dec,
        deps.facts,
        today=call.day("date"),
        usage=(deps.usage, call.ctx, "mcp"),
    )


def dec_context(deps: McpDeps, call: ToolCall) -> Wire:
    return card.context_view(
        deps.dec,
        deps.facts,
        str(call.arguments["ref"]),
        detail=cast(model.Detail, call.text("detail") or "brief"),
        as_of=call.instant("as_of"),
        axis=cast(Axis, call.text("axis") or "knowledge"),
        audience="agent",
        financial=call.identity.financial,
    )


def dec_list(deps: McpDeps, call: ToolCall) -> Wire:
    return card.list_view(
        deps.dec,
        deps.facts,
        status=call.text("status"),
        kind=call.text("kind"),
        health=call.text("health"),
        linked_to=call.text("linked_to"),
        mirror=call.text("mirror"),
        limit=call.integer("limit") or 50,
    )


def dec_integrity(deps: McpDeps, call: ToolCall) -> Wire:
    return card.integrity_view(deps.dec, deps.facts, str(call.arguments["ref"]))


def dec_shadow_report(deps: McpDeps, call: ToolCall) -> Wire:
    return card.shadow_view(
        deps.dec,
        deps.facts,
        run_id=call.integer("run_id"),
        usage=(deps.usage, call.ctx, "mcp"),
    )


HANDLERS: Mapping[str, ToolHandler] = {
    "dec_waiting": dec_waiting,
    "dec_context": dec_context,
    "dec_list": dec_list,
    "dec_integrity": dec_integrity,
    "dec_shadow_report": dec_shadow_report,
}
"""Tool name -> handler; ``server.py`` refuses to start when a catalogue entry has none."""
