"""The interfaces' own tables on a real ``dev`` instance (track K's store): ``mcp_clients``,
``mcp_call_log``, ``adm_tokens``, and the kernel services the views use (instance facts, usage)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from coflow.interfaces.admin.api import SqlAdminTokens
from coflow.interfaces.mcp.auth import SqlCallLog, SqlClientRegistry, args_hash, hash_token
from coflow.interfaces.views.card import KernelUsageSink, StoreInstanceFacts
from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store.api import Store, read_connection


@contextmanager
def tracks_landed() -> Iterator[None]:
    try:
        yield
    except NotImplementedError as exc:
        pytest.skip(f"waiting for {exc}")


@pytest.fixture
def store(request: pytest.FixtureRequest) -> Iterator[Store]:
    with tracks_landed():
        yield request.getfixturevalue("dev_store")


def test_client_tokens(store: Store, owner_ctx: CommandContext) -> None:
    clients = SqlClientRegistry()
    first = clients.issue("desk", scope="read", financial=False, ctx=owner_ctx)
    identity = clients.verify(first.token)
    assert identity is not None
    assert (identity.client, identity.scopes, identity.financial) == (
        "desk",
        frozenset({"read"}),
        False,
    )
    assert identity.actor == "mcp_desk"
    assert clients.verify("cfm_" + "0" * 64) is None

    second = clients.issue("desk", scope="write", financial=True, ctx=owner_ctx)
    assert second.replaced
    assert clients.verify(first.token) is None, "rotation: the old token stops working"
    rotated = clients.verify(second.token)
    assert rotated is not None
    assert rotated.can_write
    assert rotated.financial
    with read_connection() as conn:
        rows = conn.execute("SELECT client, token_hash, scopes FROM mcp_clients").fetchall()
    assert [tuple(r) for r in rows] == [("desk", hash_token(second.token), "read write")]
    assert second.token not in str([tuple(r) for r in rows]), "only the hash is stored"
    with pytest.raises(ValueError, match="client name"):
        clients.issue("Desk Top", scope="read", financial=False, ctx=owner_ctx)


def test_the_call_log(store: Store, clock: FakeClock, owner_ctx: CommandContext) -> None:
    clients = SqlClientRegistry()
    identity = clients.verify(
        clients.issue("desk", scope="read", financial=False, ctx=owner_ctx).token
    )
    assert identity is not None
    SqlCallLog(clock).log(
        identity,
        tool="dec_context",
        arguments={"ref": "D-0905"},
        result_kind="ok",
        interaction_id="mcp-1",
    )
    with read_connection() as conn:
        row = conn.execute(
            "SELECT at, client, tool, args_hash, result_kind, interaction_id FROM mcp_call_log"
        ).fetchone()
        tx = conn.execute(
            "SELECT actor, channel, owner_channel FROM sys_tx_log ORDER BY tx DESC LIMIT 1"
        ).fetchone()
    assert tuple(row) == (
        "2026-11-15T09:30:00.000Z",
        "desk",
        "dec_context",
        args_hash({"ref": "D-0905"}),
        "ok",
        "mcp-1",
    )
    assert "D-0905" not in str(tuple(row)), "the arguments are never stored"
    assert tuple(tx) == ("mcp_desk", "mcp", 0)


def test_admin_tokens_live_for_one_run(store: Store, clock: FakeClock) -> None:
    ctx = CommandContext(
        actor="core", channel="system", owner_channel=False, interaction_id="core-1"
    )
    tokens = SqlAdminTokens(clock)
    admin = tokens.issue("admin", ctx=ctx)
    imp = tokens.issue("import", ctx=ctx)
    assert tokens.verify(admin) == "admin"
    assert tokens.verify(imp) == "import"
    assert SqlAdminTokens(clock).verify(admin) is None, "another run never accepts this run's token"
    clock.advance(hours=2)
    tokens.revoke_issued(ctx=ctx)
    assert tokens.verify(admin) is None
    with read_connection() as conn:
        rows = conn.execute(
            "SELECT scope, created_at, revoked_at FROM adm_tokens ORDER BY scope"
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("admin", "2026-11-15T09:30:00.000Z", "2026-11-15T11:30:00.000Z"),
        ("import", "2026-11-15T09:30:00.000Z", "2026-11-15T11:30:00.000Z"),
    ]


def test_instance_facts_and_usage(
    store: Store, owner_ctx: CommandContext, mcp_ctx: CommandContext
) -> None:
    facts = StoreInstanceFacts()
    assert facts.role() == "dev"
    assert facts.timezone() == "Europe/Berlin"
    sink = KernelUsageSink()
    sink.record("dec.waiting.pull", ctx=owner_ctx, detail={"view": "cli"})
    sink.record("dec.waiting.pull", ctx=owner_ctx, detail={"view": "cli_brief"})
    sink.record("dec.waiting.pull", ctx=mcp_ctx, detail={"view": "mcp"})
    with read_connection() as conn:
        rows = conn.execute(
            "SELECT signal, day, channel, value FROM sys_usage_signals ORDER BY channel"
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("dec.waiting.pull", "2026-11-15", "cli", "2"),
        ("dec.waiting.pull", "2026-11-15", "mcp", "1"),
    ]
