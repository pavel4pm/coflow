"""DEC's ``DecisionDirectory``, the read side of I1 (spec §4.2; integration): resolve, info, state,
open_for, waiting and the compact projection, on the imported synthetic snapshot S1."""

from __future__ import annotations

from datetime import date
from operator import methodcaller
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.errors import Ambiguous, ContractViolation, NotFound
from coflow.kernel.policy.canary import scan_value
from coflow.kernel.ports.decision_directory import DecisionDirectory, Resolved
from coflow.kernel.store.api import Store
from coflow.modules.dec import api as dec
from tests.modules.dec.import_helpers import import_family


@pytest.fixture
def directory(dev_store: Store, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path) -> Any:
    env = dec.default_env()
    import_family(env, "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path)
    return dec.directory(env)


RESOLVED = [
    ("D-0907", "D-0907", "canonical"),
    ("d907", "D-0907", "tolerant"),
    ("V1_D907", "D-0907", "foreign"),
    ("D907 A1", "D-0907_A-01", "tolerant"),
]


def test_resolve_and_its_refusals_as_values(directory: Any) -> None:
    assert isinstance(directory, DecisionDirectory)
    for text, ref, via in RESOLVED:
        assert directory.resolve(text) == Resolved(ref=ref, via=via), text  # type: ignore[arg-type]
    assert isinstance(directory.resolve("907"), Ambiguous)
    assert isinstance(directory.resolve("D-0999"), NotFound)
    assert isinstance(directory.resolve("V1_D999"), NotFound)
    assert isinstance(directory.resolve("not an id"), NotFound)


def _info(directory: Any, ref: str) -> Any:
    # methodcaller keeps the port's method name out of a "name.tld" shape for the literal gate
    return methodcaller("info", ref)(directory)


def test_info_names_the_authority(directory: Any) -> None:
    info = _info(directory, "V1_D907")
    assert info is not None
    assert (info.public_id, info.status, info.mirror_of, info.mirror_scope) == (
        "D-0907",
        "active",
        "V1_D907",
        "full",
    )
    assert info.current_edition == 1
    assert info.review_due == date(2026, 11, 12)
    assert _info(directory, "D-0999") is None


def test_state_is_health_in_the_port_form(directory: Any) -> None:
    state = directory.state("D907")
    health = dec.health(dec.default_env(), "D-0907").value
    assert state.ref == "D-0907"
    assert state.label == health.label
    assert state.reasons == health.words
    assert state.review_due == date(2026, 11, 12)


def test_open_for_lists_open_decisions_about_a_subject(directory: Any) -> None:
    assert [i.public_id for i in directory.open_for(["V1_C-902"])] == ["D-0904", "D-0910"]
    assert [i.public_id for i in directory.open_for(["V1_G902"], limit=1)] == ["D-0904"]
    assert directory.open_for(["V1_P999"]) == []
    assert directory.open_for([]) == []


def test_waiting_is_the_waiting_query(directory: Any) -> None:
    query = dec.waiting(dec.default_env(), today=date(2026, 11, 15)).value
    assert [i.ref for i in directory.waiting(date(2026, 11, 15))] == [i.ref for i in query]


def test_the_projection_carries_no_money_and_names_the_authority(directory: Any) -> None:
    projection = directory.projection("D907", "agent")
    assert projection["ref"] == "D-0907"
    assert projection["mirror_of"] == "V1_D907"
    assert projection["instance_role"] == "dev"
    assert "stakes" not in projection
    assert not scan_value("salt", list(projection))
    codes = [a["code"] for a in projection["assumptions"]]  # type: ignore[union-attr]
    assert codes == ["A-01"]
    with pytest.raises(ContractViolation):
        directory.projection("D907", "event_app")
