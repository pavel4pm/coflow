"""The shared views (``interfaces/views/card.py``): wire forms and the authority statement."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from coflow.interfaces.views import card
from coflow.kernel.context import CommandContext
from tests.interfaces.fakes import FakeDecService, FakeFacts, RecordingUsage, make_services


def test_wire_values() -> None:
    assert card.wire_value(datetime(2026, 11, 15, 9, 30, tzinfo=UTC)) == "2026-11-15T09:30:00.000Z"
    assert card.wire_value(date(2026, 11, 15)) == "2026-11-15"
    assert card.wire_value(Decimal("0.50")) == "0.50"
    assert card.wire_value(frozenset({"b", "a"})) == ["a", "b"]
    assert card.wire_value({"k": (1, None, True)}) == {"k": [1, None, True]}
    with pytest.raises(TypeError):
        card.wire_value(0.5)  # floats never travel (CFJ-1, §2.1)


def test_authority_in_words() -> None:
    assert card.authority_of(None)["system_of_record"] == "this instance"
    mirror = card.authority_of("V1_D907", mirror_scope="full")
    assert mirror == {
        "system_of_record": "V1",
        "mirror_of": "V1_D907",
        "writable_here": False,
        "text": "mirrored from V1; read-only here (V1 is the system of record)",
    }
    log = card.authority_of("CF2LOG_D-037", mirror_scope="basis_only")
    assert log["writable_here"] is True
    assert "monitoring is native here" in str(log["text"])
    assert card.authority_of(None, known=False)["system_of_record"] is None


def test_the_waiting_view_keeps_the_query_order_and_states_authority(tmp_path: Path) -> None:
    dec = FakeDecService()
    view = card.waiting_view(dec, FakeFacts(), today=date(2026, 11, 15))
    assert [i["ref"] for i in view["value"]["items"]] == [i.ref for i in dec.items]
    assert [i["position"] for i in view["value"]["items"]] == [1, 2, 3, 4]
    assert view["instance_role"] == "dev"
    assert view["timezone"] == "Europe/Berlin"
    assert view["value"]["today"] == "2026-11-15"
    assert "V1" in view["authority"]
    assert view["coverage"] == ["mirrored from V1, snapshot exported at 2026-11-14T06:00:00.000Z"]


def test_an_unlisted_decision_has_an_unknown_authority() -> None:
    dec = FakeDecService()
    dec.lines = [x for x in dec.lines if x.public_id not in ("D-0905", "D-0904")]
    view = card.waiting_view(dec, FakeFacts())
    first, second = view["value"]["items"][:2]
    # D-0905 is not listed now but its card names its mirror; D-0904 is found by neither
    assert first["ref"] == "D-0905"
    assert first["authority"]["system_of_record"] == "V1"
    assert second["ref"] == "D-0904"
    assert second["authority"]["system_of_record"] is None
    assert "authority of 1 decision in this answer is unknown" in view["authority"]


def test_views_record_pulls_only_when_asked(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    usage = services.usage
    assert isinstance(usage, RecordingUsage)
    card.waiting_view(services.dec, services.facts)
    assert usage.rows == []
    ctx = CommandContext(actor="owner", channel="cli", owner_channel=True, interaction_id="i")
    card.waiting_view(services.dec, services.facts, usage=(usage, ctx, "cli"))
    assert usage.rows == [("dec.waiting.pull", "cli", {"view": "cli"})]


def test_the_owner_card_shows_amounts_and_the_agent_card_withholds_them(tmp_path: Path) -> None:
    dec = FakeDecService()
    owner = card.context_view(dec, FakeFacts(), "D905", audience="owner")
    agent = card.context_view(dec, FakeFacts(), "D905", audience="agent")
    agent_money = card.context_view(dec, FakeFacts(), "D905", audience="agent", financial=True)
    assert owner["value"]["stakes"][0]["amount"] == "450"
    assert agent["value"]["stakes"][0]["amount"] is None
    assert agent_money["value"]["stakes"][0]["amount"] == "450"
    assert card.AMOUNTS_WITHHELD in agent["coverage"]
    fact = agent["value"]["monitoring_facts"][0]
    assert fact["bears_on"] == [{"assumption": "A-02", "bearing": "bears_on"}]


def test_an_empty_waiting_list_still_states_the_instance_authority() -> None:
    dec = FakeDecService(items=[])
    view = card.waiting_view(dec, FakeFacts())
    assert view["value"]["items"] == []
    assert "mirrored from V1" in view["authority"]
    assert "every decision in this answer is native" not in view["authority"]
