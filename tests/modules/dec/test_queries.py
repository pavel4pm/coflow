"""DEC queries over a fake store (spec §5.3): assembling views into answers.

The store, the identity resolver, the configuration loaders and track S's row loaders are replaced
by in-memory fakes, so these tests pin what ``queries.py`` itself does: the evaluation time, the
as-of cut, the answer's role, coverage and staleness, and the card's assembly. The real store path
is exercised end to end by ``test_queries_store.py``.
"""

from __future__ import annotations

import contextlib
import dataclasses
import sqlite3
from collections.abc import Collection, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from coflow.kernel.config import profile as cfg_profile
from coflow.kernel.config import settings as cfg_settings
from coflow.kernel.context import FakeClock, end_of_local_day
from coflow.kernel.errors import NotFound
from coflow.kernel.ids import aliases
from coflow.kernel.ops import instance as ops_instance
from coflow.kernel.ports.attachment_probe import AttachmentSummary
from coflow.kernel.ports.goal_directory import GoalState
from coflow.kernel.store import api as store_api
from coflow.modules.dec import queries
from coflow.modules.dec.domain.model import (
    AssumptionView,
    DecEnv,
    DecisionView,
    ImportRunView,
)
from coflow.modules.dec.store import repo
from tests.fakes import FakeAttachmentProbe, FakeGoalDirectory
from tests.modules.dec.domain_builders import (
    CK,
    NOW,
    OP,
    ST,
    TZ,
    A,
    D,
    F,
    L,
    R,
    days,
    noon,
    sealed,
    with_head,
)


class FakeStore:
    """Enough of ``Store`` for queries: a clock and read connections; queries never write."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.data_root = Path("unused")
        self.reads = 0

    @contextlib.contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        self.reads += 1
        yield None  # type: ignore[misc]

    def unit_of_work(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("queries never write")

    def close(self) -> None:
        pass


@dataclasses.dataclass
class World:
    decisions: dict[str, DecisionView] = dataclasses.field(default_factory=dict)
    runs: dict[str, ImportRunView] = dataclasses.field(default_factory=dict)
    aliases: dict[str, str] = dataclasses.field(default_factory=dict)
    settings: dict[str, str] = dataclasses.field(default_factory=dict)
    role: str = "dev"

    def add(self, *ds: DecisionView) -> None:
        for d in ds:
            self.decisions[d.public_id] = d


def _run(issuer: str = "V1", *, as_of_date: date = date(2026, 11, 15)) -> ImportRunView:
    return ImportRunView(
        tx=3,
        recorded_at=datetime(2026, 11, 15, 6, 0, tzinfo=UTC),
        id=1,
        source_issuer=issuer,
        format="coflow.import.decisions",
        format_version=1,
        synthetic=True,
        file_hash="0" * 64,
        exported_at=datetime(2026, 11, 15, 5, 0, 12, tzinfo=UTC),
        as_of=datetime(2026, 11, 15, 5, 0, tzinfo=UTC),
        as_of_date=as_of_date,
        mode="shadow",
        status="applied",
        counts_json="{}",
        v2_output_json=None,
        report_status="written",
        error=None,
    )


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    w = World()
    store = FakeStore(FakeClock(NOW))

    def resolve(conn: object, text: str) -> str:
        t = text.strip()
        if t in w.aliases:
            return w.aliases[t]
        if t in w.decisions or any(t == a.ref for d in w.decisions.values() for a in d.assumptions):
            return t
        raise NotFound(t)

    def load_decision(conn: object, ref: str) -> DecisionView | None:
        return w.decisions.get(ref)

    def load_decisions(
        conn: object,
        *,
        statuses: Collection[str] | None = None,
        kinds: Collection[str] | None = None,
        mirror_issuer: str | None = None,
        refs: Collection[str] | None = None,
    ) -> list[DecisionView]:
        out = [
            d
            for d in w.decisions.values()
            if (statuses is None or d.status in statuses)
            and (kinds is None or d.kind in kinds)
            and (mirror_issuer is None or (d.mirror_of or "").startswith(mirror_issuer + "_"))
            and (refs is None or d.public_id in refs)
        ]
        return sorted(out, key=lambda d: d.number)

    def load_assumption(conn: object, ref: str) -> tuple[DecisionView, AssumptionView] | None:
        for d in w.decisions.values():
            for a in d.assumptions:
                if a.ref == ref:
                    return d, a
        return None

    def load_import_run(
        conn: object, run_id: int | None = None, *, issuer: str = "V1"
    ) -> ImportRunView | None:
        return w.runs.get(issuer)

    monkeypatch.setattr(aliases, "resolve", resolve)
    monkeypatch.setattr(repo, "load_decision", load_decision)
    monkeypatch.setattr(repo, "load_decisions", load_decisions)
    monkeypatch.setattr(repo, "load_assumption", load_assumption)
    monkeypatch.setattr(repo, "load_import_run", load_import_run)
    monkeypatch.setattr(cfg_settings, "load_settings", lambda conn: dict(w.settings))
    monkeypatch.setattr(
        cfg_profile,
        "load_profile",
        lambda conn: cfg_profile.OwnerProfile(
            display_name="Owner", timezone=TZ, locale="en", currency="EUR"
        ),
    )
    monkeypatch.setattr(
        ops_instance,
        "load_instance",
        lambda conn: ops_instance.InstanceInfo(
            instance_id="instance-1", role=w.role, volume_id="volume-1", created_at=NOW
        ),
    )
    with store_api.use_store(store):  # type: ignore[arg-type]
        yield w


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
PROBE = FakeAttachmentProbe(
    summaries={"D-1001": AttachmentSummary(kind="commitment", total=2, open=2, overdue=2)}
)
ENV = DecEnv(goal_directory=GOALS, attachment_probes=(PROBE,))


def _mirror() -> DecisionView:
    return D(
        907,
        mirror_of="V1_D907",
        decided=date(2026, 11, 2),
        created=datetime(2026, 11, 15, 6, 0, tzinfo=UTC),  # imported this morning
        origin_recorded=noon(date(2026, 11, 2)),
        review_due=date(2026, 11, 12),
        links=[L("serves", "V1_G901")],
        assumptions=[
            A(1, threshold_text="confirmation by 10.11", statement="The landlord confirms")
        ],
        facts=[F(date(2026, 11, 9), "The landlord asked for one more week")],
    )


def _native() -> DecisionView:
    return sealed(
        D(
            1001,
            review_due=days(-3),
            options=[OP("Rent the small room", chosen=True), OP("Keep the large room")],
            assumptions=[A(1, checks=[CK(days(-2), "VIOLATED")]), A(2, source="none")],
            stakes=[ST("450")],
        )
    )


# --------------------------------------------------------------------------------------------------
# waiting


def test_waiting_lists_items_in_order_with_their_context(world: World) -> None:
    world.add(_mirror(), _native(), D(1002, status="closed"), D(1003, review_due=days(9)))
    world.runs["V1"] = _run()
    answer = queries.waiting(ENV)
    assert [i.ref for i in answer.value] == ["D-1001", "D-0907"]
    first, mirror = answer.value
    assert first.reasons[0].kind == "violated"
    assert [r.kind for r in mirror.reasons] == ["review_overdue", "goal_changed", "check_due"]
    for item in answer.value:
        assert item.question_context is not None
        assert item.question_context.share_line
    assert first.question_context.execution["commitment"]["overdue"] == 2  # type: ignore[union-attr]
    assert answer.instance_role == "dev"
    assert answer.as_of == NOW
    assert answer.axis == "knowledge"
    assert answer.coverage == (
        "mirrored from V1, snapshot exported at 2026-11-15T05:00:12.000Z; read-only here",
    )
    assert not answer.stale


def test_waiting_is_stale_when_the_daily_snapshot_was_missed(world: World) -> None:
    world.add(_mirror())
    world.runs["V1"] = _run(as_of_date=date(2026, 11, 13))
    assert queries.waiting(ENV).stale
    world.runs.pop("V1")
    assert queries.waiting(ENV).stale


def test_waiting_on_another_day_and_at_an_instant(world: World) -> None:
    world.add(D(1004, review_due=date(2026, 11, 20), assumptions=[A(1, threshold_text="by 18.11")]))
    answer = queries.waiting(ENV, today=date(2026, 11, 20))
    assert answer.as_of == end_of_local_day(date(2026, 11, 20), TZ)
    (item,) = answer.value
    assert [(r.kind, r.due) for r in item.reasons] == [
        ("review_today", date(2026, 11, 20)),
        ("check_due", date(2026, 11, 18)),
    ]
    at = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)
    answer = queries.waiting(ENV, today=date(2026, 11, 18), as_of=at)
    assert answer.as_of == at
    assert [r.kind for r in answer.value[0].reasons] == ["check_due"]
    only_instant = queries.waiting(ENV, as_of=datetime(2026, 11, 19, 23, 30, tzinfo=UTC))
    assert only_instant.value[0].reasons[0].kind == "review_today"  # 20 Nov in Berlin


def test_waiting_cuts_to_what_was_known_at_t(world: World) -> None:
    late = D(
        1005,
        review_due=days(20),
        assumptions=[A(1, checks=[CK(days(-1), "VIOLATED")])],
    )
    world.add(late)
    assert [i.ref for i in queries.waiting(ENV).value] == ["D-1005"]
    assert queries.waiting(ENV, today=days(-3)).value == []


# --------------------------------------------------------------------------------------------------
# decision_context


def test_the_brief_card(world: World) -> None:
    world.add(_mirror())
    world.runs["V1"] = _run()
    world.aliases["V1_D907"] = "D-0907"
    answer = queries.decision_context(ENV, "V1_D907")
    card = answer.value
    assert card.decision.public_id == "D-0907"
    assert card.integrity_line is None  # never sealed in this world: nothing to verify
    assert card.share_line == "0 of 1 assumptions it rests on cannot be checked"
    assert card.health.label == "STALE"
    assert [r.kind for r in card.waiting_reasons] == ["review_overdue", "goal_changed", "check_due"]
    assert card.question_context is not None
    assert [a.assumption.code for a in card.assumptions] == ["A-01"]
    assert (card.assumptions[0].state, card.assumptions[0].due.source) == ("UNCHECKED", "text")
    assert card.ground_facts == card.monitoring_facts == card.reviews == card.links == ()
    assert card.mirror_line == (
        "mirrored from V1, snapshot exported at 2026-11-15T05:00:12.000Z; read-only here"
    )
    assert card.execution == {"commitment": AttachmentSummary(kind="commitment")}
    assert answer.coverage == (card.mirror_line,)


def test_the_full_card_for_an_agent_withholds_money(world: World) -> None:
    world.add(_native())
    answer = queries.decision_context(ENV, "D-1001", detail="full", audience="agent")
    card = answer.value
    assert card.detail == "full"
    assert card.audience == "agent"
    assert card.health.label == "REVIEW_REQUIRED"
    assert [e.status for e in card.editions] == ["ok"]
    assert card.integrity_line is None
    assert [s.amount for s in card.decision.stakes] == [None]
    assert card.decision.stakes[0].stored["amount"] is None
    assert "amounts withheld (financial flag off)" in answer.coverage
    owner = queries.decision_context(ENV, "D-1001", detail="full").value
    assert [s.amount for s in owner.decision.stakes] == ["450"]


def test_the_card_puts_a_broken_integrity_first(world: World) -> None:
    d = _native()
    world.add(with_head(d, statement="Rent the large room after all"))
    card = queries.decision_context(ENV, "D-1001").value
    assert card.integrity_line == "integrity: live drift (statement)"


def test_the_full_card_splits_facts_and_lists_reviews_and_links(world: World) -> None:
    d = D(
        1006,
        review_due=days(10),
        facts=[F(days(-12), "ground fact", phase="ground"), F(days(-2), "monitoring fact")],
        reviews=[R(days(-5), "keep", next_review_due=days(10))],
        links=[L("serves", "V1_G902"), L("about", "V1_P901", target_kind="person", removed_tx=4)],
    )
    world.add(d)
    card = queries.decision_context(ENV, "D-1006", detail="full").value
    assert [f.text for f in card.ground_facts] == ["ground fact"]
    assert [f.text for f in card.monitoring_facts] == ["monitoring fact"]
    assert [r.action for r in card.reviews] == ["keep"]
    assert [link.target_ref for link in card.links] == ["V1_G902"]


def test_unknown_refs_and_refs_not_known_at_t_are_not_found(world: World) -> None:
    world.add(_mirror())
    with pytest.raises(NotFound):
        queries.decision_context(ENV, "D-0999")
    with pytest.raises(NotFound):
        queries.decision_context(ENV, "D-0907", as_of=datetime(2026, 10, 1, tzinfo=UTC))


# --------------------------------------------------------------------------------------------------
# list_decisions, health, assumption_due, integrity, as_of, drafts


def test_list_decisions_filters_and_first_reason(world: World) -> None:
    world.add(
        _mirror(),
        _native(),
        D(1002, status="closed"),
        D(1003, review_due=days(9), links=[L("serves", "V1_G902")]),
        D(1007, status="draft", created=noon(days(-9))),
    )
    lines = queries.list_decisions(ENV).value
    assert [line.public_id for line in lines] == ["D-0907", "D-1001", "D-1002", "D-1003", "D-1007"]
    by_id = {line.public_id: line for line in lines}
    assert by_id["D-1001"].first_reason == "A-01 violated: The assumption holds"
    assert by_id["D-0907"].first_reason == "review was due 2026-11-12, 3 days ago"
    assert [x.public_id for x in queries.list_decisions(ENV, status="active").value] == [
        "D-0907",
        "D-1001",
        "D-1003",
    ]
    assert [x.public_id for x in queries.list_decisions(ENV, mirror="V1").value] == ["D-0907"]
    native = queries.list_decisions(ENV, mirror="native", status="active").value
    assert [x.public_id for x in native] == ["D-1001", "D-1003"]
    assert [x.public_id for x in queries.list_decisions(ENV, health="stale").value] == ["D-0907"]
    linked = queries.list_decisions(ENV, linked_to="V1_G902").value
    assert [x.public_id for x in linked] == ["D-1003"]
    assert len(queries.list_decisions(ENV, limit=2).value) == 2


def test_health_and_assumption_due(world: World) -> None:
    world.add(_mirror())
    h = queries.health(ENV, "D-0907").value
    assert (h.label, h.ground) == ("STALE", "AWAITING")
    earlier = queries.health(ENV, "D-0907", as_of=datetime(2026, 11, 8, 12, 0, tzinfo=UTC)).value
    assert earlier.label == "AWAITING_CHECKS"
    due = queries.assumption_due(ENV, "D-0907_A-01").value
    assert (due.assumption_ref, due.due.due, due.due.source) == (
        "D-0907_A-01",
        date(2026, 11, 10),
        "text",
    )
    assert due.last_assessment is None
    with pytest.raises(NotFound):
        queries.assumption_due(ENV, "D-0907_A-09")


def test_integrity_of_one_and_of_all(world: World) -> None:
    world.add(_native(), D(1002, review_due=days(5)))
    (one,) = queries.integrity(ENV, "D-1001").value
    assert one.ok
    reports = queries.integrity(ENV, "all").value
    assert [r.decision_ref for r in reports] == ["D-1001"]  # only sealed decisions


def test_as_of_on_the_knowledge_and_instance_axes(world: World) -> None:
    """AT-S8's shape through the query: created in v1 on day 2, imported on day 30."""
    imported = D(
        903,
        mirror_of="V1_D903",
        created=noon(date(2026, 11, 30)),
        origin_recorded=noon(date(2026, 11, 2)),
        review_due=date(2026, 12, 1),
        assumptions=[A(1, created=noon(date(2026, 11, 2)))],
    )
    world.add(imported)
    world.runs["V1"] = _run()
    t = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    answer = queries.as_of(ENV, "D-0903", t)
    assert answer.value.decision.public_id == "D-0903"
    assert answer.value.dues["A-01"].source == "review"
    assert any("before this instance first imported it" in n for n in answer.value.coverage)
    with pytest.raises(NotFound):
        queries.as_of(ENV, "D-0903", t, axis="instance")


def test_as_of_on_the_occurrence_axis_counts_unknown_times(world: World) -> None:
    world.add(D(1008, review_due=days(9), facts=[F(None, "when?"), F(days(-3), "known")]))
    answer = queries.as_of(ENV, "D-1008", NOW, axis="occurrence")
    assert [f.text for f in answer.value.decision.facts] == ["known"]
    assert "1 row with unknown event time excluded" in answer.coverage
    assert answer.axis == "occurrence"


def test_drafts_to_finish(world: World) -> None:
    world.add(
        D(1007, status="draft", created=noon(days(-9))),
        D(1008, status="draft", created=noon(days(-3))),
    )
    (item,) = queries.drafts_to_finish(ENV).value
    assert (item.decision_ref, item.age_days) == ("D-1007", 9)


def test_queries_read_once_and_never_write(world: World) -> None:
    world.add(_native())
    store = store_api.current_store()
    before = store.reads  # type: ignore[attr-defined]
    queries.decision_context(ENV, "D-1001", detail="full")
    assert store.reads == before + 1  # type: ignore[attr-defined]


def test_the_instance_role_is_stated(world: World) -> None:
    world.role = "validation"
    world.add(D(1009, review_due=days(-1)))
    assert queries.waiting(ENV).instance_role == "validation"
    assert queries.health(ENV, "D-1009").instance_role == "validation"
