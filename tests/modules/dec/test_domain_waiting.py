"""The waiting list (spec §3.8; AT-D4) and goal propagation (spec §3.13).

AT-D4: a synthetic month of due checks across 6 decisions. Each check due appears on its due day
and only then (the owner answers it that day); review-sourced dates never duplicate the review
reason; an overdue review appears even when the ground is INSUFFICIENT; the order is a critical
violation first, then the oldest due date, then the number.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

from coflow.kernel.ports.goal_directory import GoalState
from coflow.modules.dec.domain.due import next_check_after
from coflow.modules.dec.domain.goals import goal_changes_unanswered, served_goals
from coflow.modules.dec.domain.health import health
from coflow.modules.dec.domain.model import DecisionView
from coflow.modules.dec.domain.waiting import (
    KIND_RANK,
    decision_reasons,
    drafts_to_finish,
    urgency,
    waiting,
)
from tests.fakes import FakeGoalDirectory
from tests.modules.dec.domain_builders import (
    CFG,
    CK,
    FK,
    PR,
    A,
    D,
    L,
    R,
    T,
    at_day,
    days,
    finish,
    noon,
    with_head,
)

NOV = [date(2026, 11, n) for n in range(1, 31)]
CREATED = noon(date(2026, 10, 25))
NO_GOALS = FakeGoalDirectory()


def _month() -> list[DecisionView]:
    plain = "a threshold in words"
    return [
        D(
            1001,
            created=CREATED,
            review_due=date(2026, 12, 15),
            assumptions=[A(1, frequency="weekly", next_check_at=date(2026, 11, 3))],
        ),
        D(
            1002,
            created=CREATED,
            review_due=date(2026, 11, 25),
            assumptions=[
                A(1, by_date=date(2026, 11, 12), threshold_text=None),
                A(2, threshold_text="at least two answers by 20.11"),
            ],
        ),
        D(
            1003,
            created=CREATED,
            review_due=date(2026, 12, 20),
            assumptions=[
                A(1, frequency="monthly", next_check_at=date(2026, 11, 5)),
                A(2, frequency="ad_hoc", threshold_text="the quote arrives by 18.11"),
            ],
        ),
        D(
            1004,
            created=CREATED,
            review_due=date(2026, 11, 8),
            assumptions=[A(1, source="none"), A(2, source="none")],
        ),
        D(
            1005,
            created=CREATED,
            review_due=date(2026, 11, 16),
            assumptions=[A(1, threshold_text=plain, statement="No date in it")],
        ),
        D(
            1006,
            created=CREATED,
            review_due=date(2026, 12, 31),
            assumptions=[
                A(1, frequency="quarterly", next_check_at=date(2026, 11, 22)),
                A(2, critical=False, threshold_text="signed by 27.11"),
            ],
        ),
    ]


EXPECTED_CHECKS: dict[date, set[tuple[str, str]]] = {
    date(2026, 11, 3): {("D-1001", "A-01")},
    date(2026, 11, 5): {("D-1003", "A-01")},
    date(2026, 11, 10): {("D-1001", "A-01")},
    date(2026, 11, 12): {("D-1002", "A-01")},
    date(2026, 11, 17): {("D-1001", "A-01")},
    date(2026, 11, 18): {("D-1003", "A-02")},
    date(2026, 11, 20): {("D-1002", "A-02")},
    date(2026, 11, 22): {("D-1006", "A-01")},
    date(2026, 11, 24): {("D-1001", "A-01")},
    date(2026, 11, 27): {("D-1006", "A-02")},
}
EXPECTED_REVIEWS: dict[date, set[tuple[str, str]]] = {
    date(2026, 11, 8): {("D-1004", "review_today")},
    date(2026, 11, 16): {("D-1005", "review_today")},
    date(2026, 11, 25): {("D-1002", "review_today")},
}


def _answer_check(d: DecisionView, code: str, day: date) -> DecisionView:
    """The owner checks ``code`` as HOLDING on ``day``; the next date comes from THE function."""
    asms = []
    for a in d.assumptions:
        if a.code == code:
            nxt = next_check_after(a, day).next
            check = finish(
                dataclasses.replace(
                    CK(day, "HOLDING"),
                    assumption_id=a.id,
                    decision_id=d.id,
                    code_n=len(a.checks) + 1,
                    code=f"CK-{len(a.checks) + 1:03d}",
                    ref=f"{a.ref}_CK-{len(a.checks) + 1:03d}",
                )
            )
            a = finish(dataclasses.replace(a, checks=(*a.checks, check), next_check_at=nxt))
        asms.append(a)
    return dataclasses.replace(d, assumptions=tuple(asms))


def _keep(d: DecisionView, day: date) -> DecisionView:
    nxt = day + timedelta(days=30)
    review = finish(
        dataclasses.replace(
            R(day, "keep", next_review_due=nxt),
            decision_id=d.id,
            code=f"R-{len(d.reviews) + 1:02d}",
            ref=f"{d.public_id}_R-{len(d.reviews) + 1:02d}",
        )
    )
    return with_head(dataclasses.replace(d, reviews=(*d.reviews, review)), review_due=nxt)


def test_a_month_of_due_checks_across_six_decisions() -> None:
    world = {d.public_id: d for d in _month()}
    seen_checks: dict[date, set[tuple[str, str]]] = {}
    for day in NOV:
        T_ = at_day(day)
        items = waiting(world.values(), T_, CFG, goals=NO_GOALS)
        checks = {(i.ref, r.code or "") for i in items for r in i.reasons if r.kind == "check_due"}
        if checks:
            seen_checks[day] = checks
        for i in items:
            for r in i.reasons:
                if r.kind == "check_due":
                    assert r.due == day, (day, i.ref, r)  # on its due day, never later
                    assert r.due_source in ("explicit", "by_date", "text")  # never the review
        reviews_today = {
            (i.ref, r.kind) for i in items for r in i.reasons if r.kind == "review_today"
        }
        assert reviews_today == EXPECTED_REVIEWS.get(day, set()), day
        # an overdue review appears even when the ground is INSUFFICIENT
        d1004 = next(i for i in items if i.ref == "D-1004") if day >= date(2026, 11, 8) else None
        if d1004 is not None:
            assert d1004.health is not None
            assert d1004.health.ground == "INSUFFICIENT"
            assert d1004.reasons[0].kind == (
                "review_today" if day == date(2026, 11, 8) else "review_overdue"
            )
            assert d1004.health.label == (
                "INSUFFICIENT_DATA" if day == date(2026, 11, 8) else "STALE"
            )
        # review-sourced dates never duplicate the review reason
        for i in items:
            kinds = [r.kind for r in i.reasons]
            assert kinds == sorted(kinds, key=KIND_RANK.index)
            if "review_today" in kinds or "review_overdue" in kinds:
                assert all(r.due_source != "review" for r in i.reasons if r.kind == "check_due")
        # the order: no critical violation this month, so the oldest due date, then the number
        keys = [urgency(i) for i in items]
        assert keys == sorted(keys)
        # the owner answers what is due today
        for i in items:
            for r in i.reasons:
                if r.kind == "check_due" and r.code:
                    world[i.ref] = _answer_check(world[i.ref], r.code, day)
                if r.kind == "review_today" and i.ref in ("D-1002", "D-1005"):
                    world[i.ref] = _keep(world[i.ref], day)
    assert seen_checks == EXPECTED_CHECKS


def test_order_critical_violation_first_then_oldest_due_then_number() -> None:
    crit = D(
        1007,
        review_due=days(20),
        assumptions=[A(1, checks=[CK(days(-1), "VIOLATED")])],
    )
    overdue = D(1004, review_due=days(-7), assumptions=[A(1, source="none")])
    non_crit = D(
        1008,
        review_due=days(20),
        assumptions=[
            A(1, critical=False, checks=[CK(days(-14), "VIOLATED")]),
            A(2, checks=[CK(days(-2), "HOLDING")]),
        ],
    )
    same_a = D(1010, review_due=days(-5))
    same_b = D(1009, review_due=days(-5))
    fork = FK(7, deadline=days(-5))
    old_proposal = PR(3, recorded=noon(days(-30)))
    items = waiting(
        [same_a, overdue, non_crit, crit, same_b],
        T,
        CFG,
        goals=NO_GOALS,
        forks=[fork, FK(8, deadline=days(2)), FK(9, deadline=days(-9), status="decided")],
        proposals=[old_proposal, PR(4, recorded=noon(days(-1)), status="rejected")],
    )
    assert [i.ref for i in items] == [
        "D-1007",  # a critical violation, though its date is the newest
        "D-1008",  # non-critical violation observed 14 days ago
        "D-1004",  # review overdue for 7 days
        "D-1009",  # same due date: by number
        "D-1010",
        "Q-0007",  # a fork after decisions of the same date
        "proposal 3",  # proposals always last, however old
    ]
    assert items[1].reasons[0].critical is False
    assert items[-2].reasons[0].kind == "fork_due"
    assert items[-1].reasons[0].kind == "proposal_waiting"


def test_reasons_are_sorted_and_worded() -> None:
    d = D(
        1011,
        mirror_of=None,
        review_due=days(-2),
        assumptions=[
            A(1, threshold_text="by 10.11"),
            A(2, checks=[CK(days(-3), "VIOLATED")]),
        ],
    )
    reasons = decision_reasons(d, T, CFG, NO_GOALS)
    assert [(r.kind, r.code) for r in reasons] == [
        ("violated", "A-02"),
        ("review_overdue", None),
        ("check_due", "A-01"),
    ]
    assert reasons[0].text == "A-02 violated (critical), checked 2026-11-12: The assumption holds"
    assert reasons[1].text == "review was due 2026-11-13, 2 days ago"
    assert reasons[2].text == "A-01: check due 2026-11-10, from a date in its text (5 days ago)"
    assert (reasons[2].due_source, reasons[2].critical) == ("text", True)


def test_who_never_waits() -> None:
    overdue = {"review_due": days(-3)}
    assert decision_reasons(D(1, status="closed", **overdue), T, CFG, NO_GOALS) == []
    assert decision_reasons(D(2, status="draft", **overdue), T, CFG, NO_GOALS) == []
    tomb = D(3, mirror_of="V1_D903", absent_since_run_id=2, **overdue)
    assert decision_reasons(tomb, T, CFG, NO_GOALS) == []
    assert decision_reasons(D(4, review_due=days(3)), T, CFG, NO_GOALS) == []


def test_an_active_mirror_without_a_review_date_is_incomplete() -> None:
    d = D(905, mirror_of="V1_D905", review_due=None, created=noon(days(-9)))
    (r,) = decision_reasons(d, T, CFG, NO_GOALS)
    assert (r.kind, r.due) == ("incomplete", days(-9))
    native = D(1012, review_due=None)
    assert decision_reasons(native, T, CFG, NO_GOALS) == []


def test_unverifiable_and_violated_never_ask_for_a_check() -> None:
    d = D(
        1013,
        review_due=days(20),
        assumptions=[
            A(1, source="none", threshold_text="by 10.11"),
            A(2, threshold_text="by 10.11", checks=[CK(days(-9), "VIOLATED")]),
        ],
    )
    assert [r.kind for r in decision_reasons(d, T, CFG, NO_GOALS)] == ["violated"]


def test_an_unknown_check_still_asks_on_its_date() -> None:
    d = D(
        1014,
        review_due=days(20),
        assumptions=[A(1, next_check_at=days(0), checks=[CK(days(-6), "UNKNOWN")])],
    )
    (r,) = decision_reasons(d, T, CFG, NO_GOALS)
    assert (r.kind, r.due, r.due_source) == ("check_due", days(0), "explicit")


# --------------------------------------------------------------------------------------------------
# Goal propagation (§3.13)

DROPPED = GoalState(
    ref="V1_G901",
    title="Cut fixed costs",
    status="dropped",
    status_changed_date=date(2026, 11, 5),
    first_seen_date=date(2026, 11, 15),
)
ACTIVE = GoalState(
    ref="V1_G902",
    title="Grow the training line",
    status="active",
    status_changed_date=None,
    first_seen_date=date(2026, 11, 1),
)


def _serving(*, decided: date = date(2026, 11, 2), **kw: object) -> DecisionView:
    return D(
        907,
        mirror_of="V1_D907",
        decided=decided,
        review_due=days(20),
        links=[L("serves", "V1_G901"), L("serves", "V1_G902"), L("foreign_attachment", "V1_K9001")],
        **kw,  # type: ignore[arg-type]
    )


def _goals(*states: GoalState) -> FakeGoalDirectory:
    return FakeGoalDirectory(states={s.ref: s for s in states})


def test_a_dropped_goal_asks_once_until_a_review_answers_it() -> None:
    goals = _goals(DROPPED, ACTIVE)
    d = _serving()
    (change,) = goal_changes_unanswered(d, T, CFG, goals)
    assert (change.ref, change.status, change.changed, change.title) == (
        "V1_G901",
        "dropped",
        date(2026, 11, 5),
        "Cut fixed costs",
    )
    reasons = decision_reasons(d, T, CFG, goals)
    assert [(r.kind, r.due, r.code, r.status) for r in reasons] == [
        ("goal_changed", date(2026, 11, 5), "V1_G901", "dropped")
    ]
    assert reasons[0].text == "goal V1_G901 (Cut fixed costs) dropped on 2026-11-05"
    reviewed = _serving(reviews=[R(date(2026, 11, 10), "keep")])
    assert goal_changes_unanswered(reviewed, T, CFG, goals) == []
    before = _serving(reviews=[R(date(2026, 11, 4), "keep")])
    assert len(goal_changes_unanswered(before, T, CFG, goals)) == 1


def test_a_goal_already_ended_when_decided_asks_nothing() -> None:
    goals = _goals(DROPPED)
    assert goal_changes_unanswered(_serving(decided=date(2026, 11, 5)), T, CFG, goals) == []
    assert len(goal_changes_unanswered(_serving(decided=date(2026, 11, 4)), T, CFG, goals)) == 1


def test_an_unknown_change_date_falls_back_to_the_first_run_that_saw_it() -> None:
    undated = dataclasses.replace(DROPPED, status_changed_date=None)
    (change,) = goal_changes_unanswered(_serving(), T, CFG, _goals(undated))
    assert change.changed == date(2026, 11, 15)
    neither = dataclasses.replace(DROPPED, status_changed_date=None, first_seen_date=None)
    assert goal_changes_unanswered(_serving(), T, CFG, _goals(neither)) == []


def test_unknown_and_active_goals_ask_nothing_and_removed_links_do_not_count() -> None:
    assert goal_changes_unanswered(_serving(), T, CFG, _goals(ACTIVE)) == []
    removed = D(
        908,
        decided=date(2026, 11, 2),
        review_due=days(20),
        links=[L("serves", "V1_G901", removed_tx=5)],
    )
    assert goal_changes_unanswered(removed, T, CFG, _goals(DROPPED)) == []


def test_a_tested_goal_counts_once_and_the_goal_is_asked_as_of_t() -> None:
    goals = _goals(DROPPED)
    d = D(
        909,
        kind="test",
        decided=date(2026, 11, 2),
        review_due=days(20),
        links=[L("serves", "V1_G901"), L("tests", "V1_G901")],
    )
    assert len(goal_changes_unanswered(d, T, CFG, goals)) == 1
    assert ("state", ("V1_G901", T.instant)) in goals.calls


def test_served_goals_lines() -> None:
    lines = served_goals(_serving(), T, _goals(DROPPED))
    assert [(g.ref, g.status, g.since) for g in lines] == [
        ("V1_G901", "dropped", date(2026, 11, 5)),
        ("V1_G902", None, None),
    ]


def test_goal_change_is_a_question_not_a_state_change() -> None:
    d = _serving()
    h = health(d, T, CFG)
    assert h.label == "INSUFFICIENT_DATA"  # no assumptions; the goal does not change the label
    assert d.status == "active"


# --------------------------------------------------------------------------------------------------
# Drafts to finish (§3.8)


def test_drafts_to_finish() -> None:
    old = D(1020, status="draft", created=noon(days(-8)), review_due=days(20), question=None)
    young = D(1021, status="draft", created=noon(days(-6)))
    proposed = D(1022, status="draft", created=noon(days(-30)), origin_kind="proposal")
    active = D(1023, created=noon(days(-30)))
    (item,) = drafts_to_finish([young, proposed, active, old], T, CFG)
    assert (item.decision_ref, item.age_days) == ("D-1020", 8)
    assert "question" in item.missing
