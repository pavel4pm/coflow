"""DEC queries end to end through a real ``dev`` instance (spec §5.3, §12.2).

Rows are written straight into the DEC tables in one owner unit of work (the I2 commands do not
exist yet), sealed with ``cfj.build_edition`` from the rows exactly as the store returns them, and
read back through ``dec.api``: resolution of any input form, track S's loaders, the as-of cut and
the pure domain functions.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from coflow.kernel.context import CommandContext, FakeClock, format_instant, new_salt
from coflow.kernel.errors import NotFound
from coflow.kernel.ports.goal_directory import GoalState
from coflow.kernel.store.api import Store, insert, read_connection, unit_of_work
from coflow.modules.dec import api
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.store import repo
from tests.fakes import FakeGoalDirectory

GOALS = FakeGoalDirectory(
    states={
        "V1_G901": GoalState(
            ref="V1_G901",
            title="Cut fixed costs",
            status="dropped",
            status_changed_date=date(2026, 11, 5),
            first_seen_date=date(2026, 11, 15),
        )
    }
)


def _seed(ctx: CommandContext) -> int:
    with unit_of_work("dec", ctx, command="test_seed"):
        did = insert(
            "dec_decisions",
            {
                "public_id": "D-1001",
                "number": 1001,
                "title": "Move the workshop to a smaller room",
                "question": "Which room for the workshop?",
                "statement": "Rent the small room for one quarter",
                "kind": "choice",
                "depth": "full",
                "status": "active",
                "review_due": "2026-11-12",
                "review_due_initial": "2026-11-12",
                "decided_at": "2026-11-02",
                "decided_precision": "day",
                "decided_basis": "stated",
                "activated_at": "2026-11-02T10:00:00.000Z",
                "unknowns_json": '["whether the room has enough power"]',
                "success_criterion": "rent down by a third",
                "origin_kind": "cli",
            },
        )
        for n, text, chosen in ((1, "Rent the small room", 1), (2, "Keep the large room", 0)):
            insert(
                "dec_options",
                {
                    "decision_id": did,
                    "code_n": n,
                    "text": text,
                    "chosen": chosen,
                    "recorded_before_choice": "yes",
                    "origin": "owner",
                    "salt": new_salt(),
                },
            )
        insert(
            "dec_assumptions",
            {
                "decision_id": did,
                "code_n": 1,
                "position": 1,
                "statement": "The landlord confirms the small room",
                "threshold_text": "confirmation by 10.11",
                "data_source_kind": "manual",
                "data_source_text": "mail",
                "is_critical": 1,
                "salt": new_salt(),
            },
        )
        insert(
            "dec_assumptions",
            {
                "decision_id": did,
                "code_n": 2,
                "position": 2,
                "statement": "The room has enough power",
                "data_source_kind": "none",
                "is_critical": 1,
                "salt": new_salt(),
            },
        )
        insert(
            "dec_facts",
            {
                "decision_id": did,
                "code_n": 1,
                "phase": "ground",
                "kind": "observation",
                "text": "The landlord offered the small room",
                "occurred_at": "2026-11-01",
                "occurred_precision": "day",
                "occurred_basis": "stated",
                "evidence_kind": "owner_statement",
                "salt": new_salt(),
            },
        )
        insert(
            "dec_links",
            {
                "decision_id": did,
                "role": "serves",
                "target_ref": "V1_G901",
                "target_kind": "foreign_goal",
                "resolution": "foreign",
            },
        )
    return did


def _seal(did: int, clock: FakeClock, ctx: CommandContext) -> None:
    with read_connection() as conn:
        d = repo.load_decision(conn, "D-1001")
    assert d is not None
    draft = cfj.build_edition(
        public_id=d.public_id,
        n=1,
        decision=d.stored,
        items=cfj.seal_items(d),
        sealed_at=format_instant(clock.now()),
        sealed_by=ctx.actor,
    )
    with unit_of_work("dec", ctx, command="test_seal"):
        insert(
            "dec_editions",
            {
                "decision_id": did,
                "n": 1,
                "reason": "activation",
                "fields_json": draft.fields_json,
                "field_salts_json": draft.field_salts_json,
                "field_hashes_json": draft.field_hashes_json,
                "items_json": draft.items_json,
                "seal_hash": draft.seal_hash,
                "sealed_at": draft.sealed_at,
                "sealed_by": draft.sealed_by,
                "reconstructed": 0,
            },
        )


RECORDED = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)  # the owner recorded it when deciding


@pytest.fixture
def seeded(dev_store: Store, clock: FakeClock, owner_ctx: CommandContext) -> Store:
    now = clock.now()
    clock.set(RECORDED)
    did = _seed(owner_ctx)
    _seal(did, clock, owner_ctx)
    clock.set(now)
    return dev_store


ENV = api.default_env(goal_directory=GOALS)


def test_waiting_through_the_store(seeded: Store) -> None:
    answer = api.waiting(ENV)
    (item,) = answer.value
    assert item.ref == "D-1001"
    assert [(r.kind, r.due) for r in item.reasons] == [
        ("review_overdue", date(2026, 11, 12)),
        ("goal_changed", date(2026, 11, 5)),
        ("check_due", date(2026, 11, 10)),
    ]
    assert item.question_context is not None
    assert item.question_context.share_line == "1 of 2 assumptions it rests on cannot be checked"
    assert answer.instance_role == "dev"
    assert answer.as_of == datetime(2026, 11, 15, 9, 30, tzinfo=UTC)


def test_the_card_resolves_any_input_form_and_its_seal_verifies(seeded: Store) -> None:
    answer = api.decision_context(ENV, "d1001", detail="full")
    card = answer.value
    assert card.decision.public_id == "D-1001"
    assert card.integrity_line is None
    assert [(e.edition, e.status) for e in card.editions] == [(1, "ok")]
    assert card.health.label == "STALE"
    assert card.health.ground == "AWAITING"
    assert [f.code for f in card.ground_facts] == ["FT-001"]
    assert [link.target_ref for link in card.links] == ["V1_G901"]
    (report,) = api.integrity(ENV, "all").value
    assert report.ok


def test_health_due_list_and_as_of_through_the_store(seeded: Store) -> None:
    assert api.health(ENV, "D-1001").value.label == "STALE"
    due = api.assumption_due(ENV, "D-1001_A-01").value
    assert (due.due.due, due.due.source) == (date(2026, 11, 10), "text")
    (line,) = api.list_decisions(ENV).value
    assert (line.public_id, line.label) == ("D-1001", "STALE")
    view = api.as_of(ENV, "D-1001", datetime(2026, 11, 15, 9, 30, tzinfo=UTC)).value
    assert view.dues["A-02"].source == "review"
    with pytest.raises(NotFound):  # recorded at 10:00 that day
        api.as_of(ENV, "D-1001", datetime(2026, 11, 2, 9, 0, tzinfo=UTC), axis="instance")
