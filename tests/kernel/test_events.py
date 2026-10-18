"""Events: the envelope schema, ids and field names only, the canary, dispatch (AT-K6; P-14)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from coflow.kernel.context import CommandContext, seeded_salts
from coflow.kernel.errors import ContractViolation
from coflow.kernel.events.dispatch import Dispatcher, Event, load_events
from coflow.kernel.events.publish import ENVELOPE_FIELDS, envelope_problems, publish, uuid7
from coflow.kernel.policy.canary import make_canary, scan_database
from coflow.kernel.store import api
from coflow.kernel.store.db import SqliteStore
from tests.kernel.helpers import ctx

# Every DEC and CMT event type of spec §4.6 (the slice and later), with an example `changed`.
CATALOGUE: list[tuple[str, str, list[str]]] = [
    ("coflow.dec.decision.created", "decision", ["status", "kind"]),
    ("coflow.dec.decision.updated", "decision", ["title"]),
    ("coflow.dec.decision.activated", "decision", ["status", "current_edition"]),
    ("coflow.dec.decision.reviewed", "decision", ["review_due"]),
    ("coflow.dec.decision.closed", "decision", ["status"]),
    ("coflow.dec.decision.cancelled", "decision", ["status"]),
    ("coflow.dec.decision.superseded", "decision", ["status"]),
    ("coflow.dec.decision.withdrawn", "decision", ["status"]),
    ("coflow.dec.decision.imported", "decision", ["statement", "review_due"]),
    ("coflow.dec.decision.adopted", "decision", ["mirror_of"]),
    ("coflow.dec.edition.sealed", "edition", ["current_edition"]),
    ("coflow.dec.assumption.added", "assumption", ["statement"]),
    ("coflow.dec.assumption.superseded", "assumption", ["superseded_by"]),
    ("coflow.dec.assumption.dropped", "assumption", ["status"]),
    ("coflow.dec.assumption.checked", "assumption", ["state", "next_check_at"]),
    ("coflow.dec.assumption.state_changed", "assumption", ["state"]),
    ("coflow.dec.assumption.postponed", "assumption", ["next_check_at"]),
    ("coflow.dec.reading.recorded", "reading", ["proposed_state"]),
    ("coflow.dec.fact.added", "fact", ["phase", "kind"]),
    ("coflow.dec.fact.voided", "fact", ["voided_at"]),
    ("coflow.dec.link.added", "link", ["role"]),
    ("coflow.dec.link.removed", "link", ["role"]),
    ("coflow.dec.fork.opened", "fork", ["status"]),
    ("coflow.dec.fork.decided", "fork", ["status"]),
    ("coflow.dec.fork.dissolved", "fork", ["status"]),
    ("coflow.dec.fork.delegated", "fork", ["status"]),
    ("coflow.dec.proposal.proposed", "proposal", ["status"]),
    ("coflow.dec.proposal.approved", "proposal", ["status"]),
    ("coflow.dec.proposal.rejected", "proposal", ["status"]),
    ("coflow.dec.import.completed", "import_run", []),
    ("coflow.dec.integrity.mismatch", "edition", ["edition"]),
    ("coflow.dec.assumption.check_due", "assumption", []),
    ("coflow.cmt.commitment.created", "commitment", ["status"]),
    ("coflow.cmt.commitment.status_changed", "commitment", ["status"]),
    ("coflow.cmt.commitment.due_shifted", "commitment", ["due_date"]),
    ("coflow.cmt.commitment.linked", "commitment", ["decision_ref"]),
]

CANARY = make_canary("decision-statement")


def _rows(store: SqliteStore) -> list[dict[str, object]]:
    with store.read_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM sys_events ORDER BY tx, id")]


def test_at_k6_every_catalogue_event_holds_only_ids_entity_and_names(kstore: SqliteStore) -> None:
    for module in ("dec", "cmt"):
        with api.unit_of_work(module, ctx(), command="publish_all"):
            for event_type, entity, changed in CATALOGUE:
                if event_type.split(".")[1] != module:
                    continue
                subject = "7" if entity == "import_run" else "D-0907"
                publish(event_type, subject=subject, entity=entity, changed=changed)
    rows = _rows(kstore)
    assert len(rows) == len(CATALOGUE)
    for row in rows:
        assert envelope_problems(row) == [], row
        assert set(json.loads(str(row["data"]))) == {"entity", "changed"}
        assert set(row) - {"tx"} == set(ENVELOPE_FIELDS)
        assert row["dataversion"] == 1
        scheme, _, rest = str(row["source"]).partition("://")
        assert scheme == "coflow"
        host, module = rest.split("/")
        assert host.startswith("i-")
        assert module == row["type"].split(".")[1]  # type: ignore[union-attr]


def test_at_k6_a_canary_in_a_record_never_reaches_the_event_tables(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="add_item"):
        item = api.insert("tst_items", {"title": CANARY, "note": f"the statement says {CANARY}"})
        publish("coflow.tst.item.added", subject=f"D-{item:04d}", entity="item", changed=["title"])
    with kstore.read_connection() as conn:
        assert scan_database(conn, CANARY, tables=["tst_items"]), "the canary is in its record"
        leaks = scan_database(conn, CANARY, exclude=["tst_items"])
    assert leaks == []


@pytest.mark.parametrize(
    "changed",
    [
        ["statement=Rent the small room"],
        ["Rent the small room"],
        [CANARY],
        ["state", "HOLDING"],
        "statement",
    ],
)
def test_at_k6_a_value_in_changed_is_refused(kstore: SqliteStore, changed: object) -> None:
    with api.unit_of_work("tst", ctx(), command="bad"), pytest.raises(ContractViolation):
        publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=changed)  # type: ignore[arg-type]
    assert _rows(kstore) == []


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"type": "coflow.oth.item.added"}, "cannot publish"),
        ({"type": "tst.item.added"}, "is not coflow"),
        ({"subject": "Rent the small room"}, "subject"),
        ({"subject": "coflow:D-0907"}, "subject"),
        ({"source_ref": "a message text"}, "sourceref"),
        ({"entity": "Item Name"}, "entity"),
        ({"data_class": "secret"}, "data class"),
    ],
)
def test_publish_refuses_malformed_envelopes(
    kstore: SqliteStore, kwargs: dict[str, str], match: str
) -> None:
    args: dict[str, object] = {
        "type": "coflow.tst.item.added",
        "subject": "D-0907",
        "entity": "item",
        "changed": ["title"],
    }
    args.update(kwargs)
    with (
        api.unit_of_work("tst", ctx(), command="bad"),
        pytest.raises(ContractViolation, match=match),
    ):
        publish(**args)  # type: ignore[arg-type]


def test_events_commit_and_roll_back_with_their_unit(kstore: SqliteStore) -> None:
    def failing_change() -> None:
        with api.unit_of_work("tst", ctx(), command="fail"):
            api.insert("tst_items", {"title": "Rolled back"})
            publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=["title"])
            raise RuntimeError("the change failed")

    with pytest.raises(RuntimeError):
        failing_change()
    assert _rows(kstore) == []
    with api.unit_of_work("tst", ctx(), command="ok") as unit:
        event_id = publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=[])
        assert unit.event_ids == (event_id,)  # type: ignore[attr-defined]
    rows = _rows(kstore)
    assert [r["id"] for r in rows] == [event_id]
    assert rows[0]["correlationid"] == "int-owner"
    assert rows[0]["time"] == "2026-11-15T09:30:00.000Z"


def test_uuid7_carries_the_time_and_version() -> None:
    at = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
    with seeded_salts("events"):
        a, b = uuid7(at, 0), uuid7(at, 1)
    ua, ub = uuid.UUID(a), uuid.UUID(b)
    assert ua.version == 7
    assert ub.version == 7
    assert ua.int >> 80 == int(at.timestamp() * 1000)
    assert a < b, "the in-unit counter orders events of one instant"


def test_dispatch_after_commit_once_per_handler(kstore: SqliteStore) -> None:
    seen: list[Event] = []
    calls = {"flaky": 0}

    def flaky(event: Event) -> None:
        calls["flaky"] += 1
        raise ValueError("the handler failed with a value inside")

    dispatcher = Dispatcher(max_attempts=2)
    dispatcher.register("obs.count", types=["coflow.tst.*"], classes=["work"], fn=seen.append)
    dispatcher.register("tst.flaky", types=["coflow.tst.item.added"], classes=["work"], fn=flaky)
    dispatcher.register("tst.money", types=["coflow.tst.*"], classes=["financial"], fn=seen.append)
    dispatcher.attach(kstore)

    with api.unit_of_work("tst", ctx(), command="add"):
        publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=["title"])
    assert [e.type for e in seen] == ["coflow.tst.item.added"]
    assert seen[0].changed == ("title",)
    assert seen[0].subject == "D-0907"

    report = dispatcher.deliver_pending(kstore)
    assert report.delivered == []
    assert len(report.dead) == 1, "the retry exhausts the attempts"
    assert calls["flaky"] == 2
    again = dispatcher.deliver_pending(kstore)
    assert again.delivered == again.failed == again.dead == []
    with kstore.read_connection() as conn:
        rows = conn.execute(
            "SELECT handler, status, attempts, last_error FROM sys_event_deliveries"
            " ORDER BY handler"
        ).fetchall()
        assert len(load_events(conn)) == 1
    assert [tuple(r) for r in rows] == [
        ("obs.count", "delivered", 1, None),
        ("tst.flaky", "dead", 2, "ValueError"),
    ]


def test_only_pol_and_obs_declare_the_journal_class() -> None:
    dispatcher = Dispatcher()
    with pytest.raises(ContractViolation, match="journal"):
        dispatcher.register("tst.reader", types=["coflow.tst.*"], classes=["journal"], fn=print)
    dispatcher.register("pol.journal", types=["coflow.jrn.*"], classes=["journal"], fn=print)
    with pytest.raises(ContractViolation):
        dispatcher.register("pol.journal", types=["coflow.jrn.*"], classes=["journal"], fn=print)
    with pytest.raises(ContractViolation):
        dispatcher.register("obs.bad", types=["not.a.type"], classes=["work"], fn=print)


def test_events_are_published_only_inside_a_unit(kstore: SqliteStore) -> None:
    mcp = CommandContext(actor="mcp_x", channel="mcp", owner_channel=False, interaction_id="m")
    with pytest.raises(ContractViolation):
        publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=[])
    with api.unit_of_work("tst", mcp, command="ok"):
        publish("coflow.tst.item.added", subject="V1_D907", entity="item", changed=["title"])
    assert _rows(kstore)[0]["actor"] == "mcp_x"


# Review finding: the interaction id and the actor were copied into the envelope unchecked, and an
# interaction id can come from a client header.


@pytest.mark.parametrize("field", ["interaction_id", "actor"])
def test_free_text_never_becomes_an_interaction_id_or_actor(field: str) -> None:
    good = {"actor": "owner", "channel": "cli", "owner_channel": True, "interaction_id": "t-1"}
    with pytest.raises(ValueError, match="id-shaped") as excinfo:
        CommandContext(**{**good, field: f"note {CANARY} 1200 EUR"})  # type: ignore[arg-type]
    assert CANARY not in str(excinfo.value)


@pytest.mark.parametrize("field", ["correlationid", "actor"])
def test_publish_refuses_a_context_whose_ids_are_not_id_shaped(
    kstore: SqliteStore, field: str
) -> None:
    bad = ctx()
    name = "interaction_id" if field == "correlationid" else "actor"
    object.__setattr__(bad, name, f"note {CANARY}")  # past the context's own check
    with (
        api.unit_of_work("tst", bad, command="bad"),
        pytest.raises(ContractViolation, match=f"{field} must be id-shaped") as excinfo,
    ):
        publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=["title"])
    assert CANARY not in str(excinfo.value)
    assert _rows(kstore) == []


@pytest.mark.parametrize("field", ["correlationid", "actor", "causationid"])
def test_the_envelope_scan_flags_free_text_ids(kstore: SqliteStore, field: str) -> None:
    with api.unit_of_work("tst", ctx(), command="ok"):
        publish("coflow.tst.item.added", subject="D-0907", entity="item", changed=["title"])
    row = _rows(kstore)[0]
    assert envelope_problems(row) == []
    assert envelope_problems({**row, field: f"note {CANARY}"}) == [f"{field} is not id-shaped"]
