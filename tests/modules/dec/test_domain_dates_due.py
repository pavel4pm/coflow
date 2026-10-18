"""Check dates (spec §3.6): the v1 date table (AT-D1), due dates and the floor rule (AT-D1), and THE
``next_check_after`` (AT-D2)."""

from __future__ import annotations

from datetime import date

import pytest

from coflow.kernel.errors import RefusalCode, Refused
from coflow.modules.dec.domain.dates import DATE_PATTERNS, dates_in
from coflow.modules.dec.domain.due import (
    assessed_since,
    assumption_due,
    check_due,
    floor_date,
    next_check_after,
)
from coflow.modules.dec.domain.model import AssumptionView, DecisionView, DueResult, NextCheck
from tests.modules.dec.domain_builders import CFG, CK, A, D, T, at_day, days, noon

BASE = date(2026, 11, 2)

# --------------------------------------------------------------------------------------------------
# AT-D1: the date table, ported from v1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # ISO
        ("confirmed by 2026-11-20", [date(2026, 11, 20)]),
        ("2026-11-20", [date(2026, 11, 20)]),
        # day.month.year, one or two digits
        ("by 15.11.2026", [date(2026, 11, 15)]),
        ("by 5.11.2026", [date(2026, 11, 5)]),
        ("by 5.1.2027", [date(2027, 1, 5)]),
        # day.month: the year of the base
        ("by 15.11", [date(2026, 11, 15)]),
        # in order of appearance, whatever the pattern
        ("after 20.11 or by 2026-11-18", [date(2026, 11, 20), date(2026, 11, 18)]),
        ("10.11.2026 and then 12.11", [date(2026, 11, 10), date(2026, 11, 12)]),
        # never dates
        ("reach 1.5 points", []),
        ("a share of 0.80", []),
        ("growth of 12.5 %", []),
        ("12,15.11 units", []),
        ("115.11 and 15.112", []),
        # invalid calendar dates are skipped
        ("by 31.02", []),
        ("by 31.02.2027", []),
        ("by 2026-02-30", []),
        ("by 31.02 or 03.03", [date(2027, 3, 3)]),
        # a day.month inside a day.month.year is not taken twice
        ("on 10.11.2026", [date(2026, 11, 10)]),
        # HTML-escaped text, as v1 stored it
        ("by 15.11&nbsp;at the latest", [date(2026, 11, 15)]),
        ("&lt;10.11&gt;", [date(2026, 11, 10)]),
        ("by 15&#46;11", [date(2026, 11, 15)]),
        # year rollover: earlier than the base means next year; the base day itself stays
        ("by 05.01", [date(2027, 1, 5)]),
        ("by 02.11", [date(2026, 11, 2)]),
        ("by 01.11", [date(2027, 11, 1)]),
        # nothing
        ("", []),
        (None, []),
    ],
)
def test_dates_in(text: str | None, expected: list[date]) -> None:
    assert dates_in(text, BASE) == expected


def test_the_table_is_the_spec_table() -> None:
    assert DATE_PATTERNS == (
        r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)",
        r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(20\d{2})(?!\d)",
        r"(?<![\d.,])(\d{2})\.(\d{2})(?![\d.,])",
    )


def test_a_leap_day_is_taken_only_in_the_base_year_as_v1_does() -> None:
    assert dates_in("by 29.02", date(2028, 1, 10)) == [date(2028, 2, 29)]
    assert dates_in("by 29.02", date(2027, 1, 10)) == []  # 2027 has no 29 February
    assert dates_in("by 29.02", date(2028, 3, 1)) == []  # rolled into 2029, which has none


# --------------------------------------------------------------------------------------------------
# AT-D1: due dates and the floor rule


def _decision(
    *assumptions: AssumptionView, review: date | None = date(2026, 11, 30)
) -> DecisionView:
    return D(
        1001,
        decided=BASE,
        created=noon(BASE),
        review_due=review,
        assumptions=list(assumptions),
    )


def test_a_date_equal_to_the_creation_day_is_not_due() -> None:
    d = _decision(A(1, statement="Sealed on 02.11; confirm by 10.11", threshold_text=None))
    a = d.assumptions[0]
    assert floor_date(a, T, CFG) == BASE
    assert assumption_due(d, a, T, CFG) == DueResult(due=date(2026, 11, 10), source="text")


def test_after_a_check_on_day_seven_the_next_text_date_counts() -> None:
    text = "by 07.11 or after 11.11"
    before = _decision(A(1, threshold_text=text))
    a = before.assumptions[0]
    assert assumption_due(before, a, at_day(date(2026, 11, 5)), CFG).due == date(2026, 11, 7)

    after = _decision(A(1, threshold_text=text, checks=[CK(date(2026, 11, 7), "HOLDING")]))
    a = after.assumptions[0]
    assert floor_date(a, T, CFG) == date(2026, 11, 7)
    assert assumption_due(after, a, T, CFG) == DueResult(due=date(2026, 11, 11), source="text")


def test_threshold_text_comes_before_the_statement() -> None:
    d = _decision(A(1, threshold_text="by 12.11", statement="Holds until 09.11"))
    assert assumption_due(d, d.assumptions[0], T, CFG).due == date(2026, 11, 12)
    d = _decision(A(1, threshold_text="no date here", statement="Holds until 09.11"))
    assert assumption_due(d, d.assumptions[0], T, CFG).due == date(2026, 11, 9)


def test_by_date_beats_text_and_explicit_beats_both() -> None:
    d = _decision(A(1, threshold_text="by 10.11", by_date=date(2026, 11, 20)))
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 20), source="by_date"
    )
    d = _decision(
        A(
            1,
            threshold_text="by 10.11",
            by_date=date(2026, 11, 20),
            next_check_at=date(2026, 11, 25),
        )
    )
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 25), source="explicit"
    )


def test_a_by_date_on_or_before_the_floor_falls_back_to_text() -> None:
    a = A(
        1,
        by_date=date(2026, 11, 6),
        threshold_text="by 06.11, then again 20.11",
        checks=[CK(date(2026, 11, 6), "HOLDING")],
    )
    d = _decision(a)
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 20), source="text"
    )


def test_the_review_date_is_the_last_resort() -> None:
    d = _decision(A(1, threshold_text="no date", statement="no date either"))
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 30), source="review"
    )
    d = _decision(A(1, threshold_text=None), review=None)
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(due=None, source=None)


def test_an_inactive_assumption_has_no_due_date() -> None:
    d = _decision(A(1, status="dropped", next_check_at=date(2026, 11, 20)))
    assert assumption_due(d, d.assumptions[0], T, CFG) == DueResult(due=None, source=None)


def test_a_day_month_takes_the_decided_year_else_the_k_year() -> None:
    a = A(1, threshold_text="by 05.01", created=noon(date(2026, 12, 20)))
    d = D(
        1001,
        decided=date(2026, 12, 20),
        created=noon(date(2026, 12, 20)),
        assumptions=[a],
        review_due=date(2027, 3, 1),
    )
    assert assumption_due(d, d.assumptions[0], at_day(date(2027, 1, 2)), CFG).due == date(
        2027, 1, 5
    )
    unknown = D(
        1002,
        decided_basis="unknown",
        created=noon(date(2026, 12, 20)),
        assumptions=[a],
        review_due=date(2027, 3, 1),
    )
    assert unknown.decided_at is None
    assert assumption_due(unknown, unknown.assumptions[0], at_day(date(2027, 1, 2)), CFG).due == (
        date(2027, 1, 5)
    )


# --------------------------------------------------------------------------------------------------
# check_due


def test_check_due_needs_a_checkable_state_a_dated_source_and_no_answer() -> None:
    due_text = A(1, threshold_text="by 10.11")
    d = _decision(due_text)
    assert check_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 10), source="text"
    )
    answered = _decision(A(1, threshold_text="by 10.11", checks=[CK(date(2026, 11, 10))]))
    a = answered.assumptions[0]
    assert assessed_since(a, date(2026, 11, 10), T, CFG)
    assert check_due(answered, a, T, CFG) is None
    future = _decision(A(1, threshold_text="by 20.11"))
    assert check_due(future, future.assumptions[0], T, CFG) is None
    review = _decision(A(1, threshold_text=None), review=date(2026, 11, 10))
    assert check_due(review, review.assumptions[0], T, CFG) is None
    violated = _decision(
        A(1, threshold_text="by 10.11", checks=[CK(date(2026, 11, 3), "VIOLATED")])
    )
    assert check_due(violated, violated.assumptions[0], T, CFG) is None
    nothing = _decision(A(1, threshold_text="by 10.11", source="none"))
    assert check_due(nothing, nothing.assumptions[0], T, CFG) is None


def test_a_postponement_answers_no_due_date() -> None:
    a = A(
        1,
        threshold_text="by 10.11",
        checks=[CK(date(2026, 11, 10), None, kind="postponement", next_check_set=days(5))],
    )
    d = _decision(a)
    assert not assessed_since(d.assumptions[0], date(2026, 11, 10), T, CFG)


def test_a_voided_check_does_not_count() -> None:
    a = A(1, threshold_text="by 10.11", checks=[CK(date(2026, 11, 10), voided_at=noon(days(-2)))])
    d = _decision(a)
    assert check_due(d, d.assumptions[0], T, CFG) == DueResult(
        due=date(2026, 11, 10), source="text"
    )


# --------------------------------------------------------------------------------------------------
# AT-D2: next_check_after after a check on 2026-11-01

CHECKED = date(2026, 11, 1)
NOV_10 = date(2026, 11, 10)
NOV_20 = date(2026, 11, 20)


@pytest.mark.parametrize(
    ("assumption", "explicit", "expected"),
    [
        (A(1, frequency="weekly"), None, NextCheck(next=date(2026, 11, 8), rule="frequency")),
        (A(1, frequency="monthly"), None, NextCheck(next=date(2026, 12, 1), rule="frequency")),
        (A(1, frequency="quarterly"), None, NextCheck(next=date(2027, 1, 30), rule="frequency")),
        (A(1, frequency="ad_hoc"), None, NextCheck(next=None, rule="ad_hoc_clear")),
        (A(1, frequency="weekly"), NOV_20, NextCheck(next=NOV_20, rule="explicit")),
        (A(1, next_check_at=NOV_10), None, NextCheck(next=NOV_10, rule="kept")),
        (A(1, next_check_at=date(2026, 10, 25)), None, NextCheck(next=None, rule="dropped")),
        (A(1, next_check_at=CHECKED), None, NextCheck(next=None, rule="dropped")),
        (A(1), None, NextCheck(next=None, rule="none")),
    ],
)  # fmt: skip
def test_next_check_after(
    assumption: AssumptionView, explicit: date | None, expected: NextCheck
) -> None:
    assert next_check_after(assumption, CHECKED, explicit) == expected


@pytest.mark.parametrize("explicit", [CHECKED, date(2026, 10, 30), date(2028, 11, 1)])
def test_an_explicit_next_check_out_of_range_is_refused(explicit: date) -> None:
    with pytest.raises(Refused) as err:
        next_check_after(A(1), CHECKED, explicit)
    assert err.value.code == RefusalCode.NEXT_CHECK_OUT_OF_RANGE


def test_an_explicit_next_check_730_days_ahead_is_allowed() -> None:
    assert next_check_after(A(1), CHECKED, date(2028, 10, 31)).next == date(2028, 10, 31)
