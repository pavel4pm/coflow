"""The rule-built question context and likely actions (spec §3.9).

The stale card is the shape of AT-N23 (review 31 days overdue, last fact 45 days old, a served goal
dropped 20 days ago, two commitments overdue through the fake probe): everything the owner needs
to answer is on the card. The check card shows the next date the write would store (AT-N11).
"""

from __future__ import annotations

from datetime import date

from coflow.kernel.ports.attachment_probe import AttachmentSummary
from coflow.kernel.ports.goal_directory import GoalState
from coflow.modules.dec.domain.context_card import (
    leading_kind,
    likely_actions,
    question_context,
    threshold_words,
    with_question_context,
)
from coflow.modules.dec.domain.due import next_check_after
from coflow.modules.dec.domain.waiting import decision_item, waiting
from tests.fakes import FakeAttachmentProbe, FakeGoalDirectory
from tests.modules.dec.domain_builders import (
    CFG,
    CK,
    FK,
    PR,
    A,
    D,
    F,
    L,
    R,
    T,
    days,
    noon,
)

GOALS = FakeGoalDirectory(
    states={
        "V1_G901": GoalState(
            ref="V1_G901",
            title="Cut fixed costs",
            status="dropped",
            status_changed_date=days(-20),
            first_seen_date=days(-19),
        )
    }
)
PROBE = FakeAttachmentProbe(
    summaries={
        "D-1003": AttachmentSummary(
            kind="commitment", total=2, open=2, overdue=2, refs=("F-10001", "F-10002")
        )
    }
)


def _stale():
    return D(
        1003,
        title="Rent a second storage unit",
        statement="Rent the unit near the workshop for six months",
        created=noon(days(-60)),
        decided=days(-60),
        review_due=days(-31),
        expected_by=days(-3),
        links=[L("serves", "V1_G901")],
        facts=[
            F(days(-50), "The landlord sent the contract", evidence_kind="owner_statement"),
            F(days(-45), "Moved the first boxes in", evidence_ref="V1_S90001"),
        ],
        assumptions=[A(1, source="none", threshold_text=None, by_date=days(-10))],
    )


def test_the_stale_card_shows_everything_needed_to_answer() -> None:
    d = _stale()
    item = decision_item(d, T, CFG, GOALS)
    assert item is not None
    assert [r.kind for r in item.reasons] == ["review_overdue", "goal_changed"]
    qc = question_context(item, d, T, CFG, goals=GOALS, probes=[PROBE])
    assert qc.one_line == (
        "D-1003 · Rent a second storage unit — Rent the unit near the workshop for six months"
    )
    assert qc.share_line == "1 of 1 assumptions it rests on cannot be checked"
    assert qc.health is not None
    assert qc.health.label == "STALE"
    assert qc.last_fact is not None
    assert (qc.last_fact.ref, qc.last_fact.age_days, qc.last_fact.evidence) == (
        "D-1003_FT-002",
        45,
        "V1_S90001",
    )
    assert ("review date", days(-31)) in qc.passed
    assert ("expected by", days(-3)) in qc.passed
    assert ("A-01 by-date", days(-10)) in qc.passed
    assert [(g.ref, g.title, g.status, g.since) for g in qc.goals] == [
        ("V1_G901", "Cut fixed costs", "dropped", days(-20))
    ]
    assert qc.execution == {
        "commitment": {
            "total": 2,
            "open": 2,
            "done": 0,
            "dropped": 0,
            "overdue": 2,
            "shifted": 0,
        }
    }
    assert qc.asked is not None
    assert (qc.asked.kind, qc.asked.due, qc.asked.due_source) == ("review", days(-31), "review")
    assert qc.likely_actions[:2] == ("close", "cancel")
    assert qc.likely_actions[2] == "keep (give a reason) · next review 2026-12-15"
    assert leading_kind(item) == "goal_changed"


def test_review_actions_carry_the_step_date() -> None:
    d = D(1004, review_due=days(-2), assumptions=[A(1, checks=[CK(days(-1), "HOLDING")])])
    item = decision_item(d, T, CFG, GOALS)
    assert item is not None
    assert likely_actions(item, d, T, CFG) == (
        "keep · next review 2026-12-15",
        "adjust · next review 2026-12-15",
        "close",
        "cancel",
        "supersede",
    )


def test_violated_actions_lead_with_revise() -> None:
    d = D(1005, review_due=days(20), assumptions=[A(1, checks=[CK(days(-1), "VIOLATED")])])
    item = decision_item(d, T, CFG, GOALS)
    assert item is not None
    assert likely_actions(item, d, T, CFG)[0] == "revise"
    qc = question_context(item, d, T, CFG, goals=GOALS)
    assert qc.asked is not None
    assert (qc.asked.kind, qc.asked.ref) == ("assumption", "D-1005_A-01")


def test_the_check_card_shows_the_date_the_write_would_store() -> None:
    weekly = A(
        2,
        frequency="weekly",
        next_check_at=days(0),
        metric="signed",
        comparator=">=",
        value="3",
        unit="contracts",
        by_date=date(2026, 11, 20),
        threshold_text=None,
        checks=[CK(days(-7), "HOLDING")],
    )
    adhoc = A(4, frequency="ad_hoc", threshold_text="the quote arrives by 15.11")
    d = D(1006, review_due=days(30), assumptions=[weekly, adhoc])
    items = waiting([d], T, CFG, goals=GOALS)
    (item,) = items
    assert [(r.kind, r.code) for r in item.reasons] == [
        ("check_due", "A-02"),
        ("check_due", "A-04"),
    ]
    actions = likely_actions(item, d, T, CFG)
    expected = next_check_after(d.assumptions[0], T.date).next
    assert expected == date(2026, 11, 22)
    assert actions[0] == f"holding · next check {expected}"
    assert actions[-1] == "postpone to 2026-11-22"
    assert actions[1:5] == (
        "drifting",
        "violated",
        "can't judge this time",
        "nothing to check with",
    )
    qc = question_context(item, d, T, CFG, goals=GOALS)
    assert qc.asked is not None
    assert qc.asked.threshold_text == "signed >= 3 contracts by 2026-11-20"
    assert (qc.asked.due, qc.asked.due_source) == (days(0), "explicit")


def test_an_ad_hoc_check_falls_back() -> None:
    d = D(
        1007, review_due=days(30), assumptions=[A(4, frequency="ad_hoc", threshold_text="by 15.11")]
    )
    (item,) = waiting([d], T, CFG, goals=GOALS)
    assert likely_actions(item, d, T, CFG)[0] == "holding · next check none (falls back)"


def test_postponements_since_the_last_review_are_counted() -> None:
    a = A(
        1,
        threshold_text="by 10.11",
        checks=[
            CK(days(-20), None, kind="postponement", next_check_set=days(-12)),
            CK(days(-8), None, kind="postponement", next_check_set=days(-5)),
            CK(days(-4), None, kind="postponement", next_check_set=days(0)),
        ],
    )
    d = D(1008, review_due=days(30), reviews=[R(days(-10), "keep")], assumptions=[a])
    (item,) = waiting([d], T, CFG, goals=GOALS)
    assert question_context(item, d, T, CFG, goals=GOALS).postponements_since_review == 2


def test_forks_and_proposals_have_a_context_without_a_decision() -> None:
    items = waiting(
        [],
        T,
        CFG,
        goals=GOALS,
        forks=[FK(7, deadline=days(-1))],
        proposals=[PR(3, recorded=noon(days(-2)))],
    )
    fork, proposal = (with_question_context(i, None, T, CFG, goals=GOALS) for i in items)
    assert fork.question_context is not None
    assert fork.question_context.one_line == "Which venue for the workshop?"
    assert fork.question_context.likely_actions[0] == "decide (pick an option)"
    assert fork.question_context.share_line is None
    assert proposal.question_context is not None
    assert proposal.question_context.likely_actions[0] == "approve (owner channel)"


def test_incomplete_mirror_actions() -> None:
    d = D(905, mirror_of="V1_D905", review_due=None)
    item = decision_item(d, T, CFG, GOALS)
    assert item is not None
    assert likely_actions(item, d, T, CFG) == (
        "set a review date (keep)",
        "complete fields",
        "cancel",
    )


def test_no_fact_and_no_statement() -> None:
    d = D(1009, statement=None, question=None, review_due=days(-1))
    item = decision_item(d, T, CFG, GOALS)
    assert item is not None
    qc = question_context(item, d, T, CFG, goals=GOALS)
    assert qc.one_line == "D-1009 · Move the workshop to a smaller room"
    assert qc.last_fact is None
    assert qc.execution == {}


def test_threshold_words() -> None:
    assert threshold_words(A(1, threshold_text="by 10.11")) == "by 10.11"
    band = A(1, metric="hours", comparator="between", value="10", value2="16", unit="h")
    assert threshold_words(band) == "hours between 10 and 16 h"
    assert threshold_words(A(1, comparator="<=", value="16", threshold_text=None)) == "value <= 16"
