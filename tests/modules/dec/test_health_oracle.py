"""AT-D3, track S's part: the named vectors H1-H18 pin the independent oracle, and the oracle and
DEC's health agree on the whole enumerated space of §3.7.

DEC is reached two ways. Through its public query (``dec.api.health``) over an in-memory view: the
loader of ``store/repo.py`` (track S's own file) is replaced by one that returns the planted view,
so the query runs exactly as it does over the database (the named vectors and a sample of the
space). And, for the whole space, through the pure functions the query calls
(``states.view_at`` then ``health.health``), which avoids a store round trip per case; the sample
checks that both ways give the same result. The oracle itself never imports DEC's domain code
(``tests/architecture``); this test file is where the two meet.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from coflow.kernel.store.api import Store
from coflow.modules.dec import api as dec
from coflow.modules.dec.domain import health as dec_health
from coflow.modules.dec.domain import states as dec_states
from coflow.modules.dec.domain.model import DecConfig, DecisionView
from coflow.modules.dec.store import repo
from tests.modules.dec.oracle_views import REVIEWS, STATES, TZ, Plant, T, decision
from tests.oracle.health_oracle import dates_in, oracle_health

CFG = DecConfig(timezone=TZ)
SAMPLE_EVERY = 97  # every n-th case of the space also runs through the query


@pytest.fixture
def module_health(dev_store: Store, monkeypatch: pytest.MonkeyPatch) -> Any:
    """``health(view)`` as DEC computes it through ``dec.api.health`` at ``T``."""
    env = dec.default_env()
    planted: dict[str, DecisionView] = {}
    monkeypatch.setattr(repo, "load_decision", lambda conn, ref: planted.get(ref))

    def run(view: DecisionView) -> Any:
        planted[view.public_id] = view
        return dec.health(env, view.public_id, as_of=T.instant).value

    return run


def pure_health(view: DecisionView) -> Any:
    """The same computation without the store: the visibility filter, then health (§3.7)."""
    visible = dec_states.view_at(view, T, CFG)
    assert visible is not None
    return dec_health.health(visible, T, CFG)


def _cmp(result: Any) -> tuple[Any, ...]:
    return (
        result.label,
        result.ground,
        frozenset(result.timeliness),
        result.share,
        result.bet,
        dict(result.states),
        tuple(result.pool),
    )


# ==================================================================================================
# The named vectors (§3.7)


def P(state: str, critical: bool = True, **kw: Any) -> Plant:
    return Plant(critical=critical, state=state, **kw)


VECTORS: dict[str, tuple[DecisionView, str, str | None, Decimal | None, set[str]]] = {
    # name: (view, label, ground, share, timeliness kinds that must be present)
    "H1": (
        decision([], review_in=10, depth="full"),
        "INSUFFICIENT_DATA",
        "NO_ASSUMPTIONS",
        None,
        set(),
    ),
    "H2": (decision([], review_in=10, depth="light"), "ON_TRACK", "NOT_MONITORED", None, set()),
    "H3": (
        decision([P("VIOLATED"), P("HOLDING")], review="overdue"),
        "REVIEW_REQUIRED",
        "VIOLATED",
        Decimal(0),
        {"REVIEW_OVERDUE"},
    ),
    "H4": (
        decision([P("UNVERIFIABLE"), P("UNVERIFIABLE", via_source_none=True)], review="overdue"),
        "STALE",
        "INSUFFICIENT",
        Decimal(1),
        {"REVIEW_OVERDUE"},
    ),
    "H5": (
        decision([P("UNVERIFIABLE"), P("UNVERIFIABLE"), P("HOLDING")], review_in=5),
        "INSUFFICIENT_DATA",
        "INSUFFICIENT",
        Decimal(2) / 3,
        set(),
    ),
    "H6": (
        decision([P("UNVERIFIABLE"), P("HOLDING")], review_in=5, fresh=True),
        "ON_TRACK",
        "HOLDING",
        Decimal("0.5"),
        {"ON_SCHEDULE"},
    ),
    "H7": (
        decision([P("NOT_YET_DUE")] * 3, review_in=20, fresh=True),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        {"ON_SCHEDULE"},
    ),
    "H8": (
        decision(
            [P("UNCHECKED", threshold_text="confirmed by 14.11"), P("NOT_YET_DUE")], review_in=20
        ),
        "WATCH",
        "AWAITING",
        Decimal(0),
        {"CHECK_OVERDUE"},
    ),
    "H9": (
        decision(
            [P("HOLDING", frequency="weekly", check_age=10, next_check=T.date - timedelta(days=3))],
            review_in=20,
        ),
        "WATCH",
        "HOLDING",
        Decimal(0),
        {"CHECK_OVERDUE"},
    ),
    "H10": (
        decision(
            [P("HOLDING", frequency="ad_hoc"), P("HOLDING", frequency="ad_hoc")], review_in=60
        ),
        "WATCH",
        "HOLDING",
        Decimal(0),
        {"NO_DATA_SINCE"},
    ),
    "H11": (
        decision([P("DRIFTING"), P("HOLDING")], review="today"),
        "WATCH",
        "DRIFTING",
        Decimal(0),
        {"DUE_TODAY"},
    ),
    "H12": (
        decision([P("HOLDING"), P("HOLDING")], review_in=20, flag="ZOMBIE"),
        "ZOMBIE",
        "HOLDING",
        Decimal(0),
        set(),
    ),
    "H13": (
        decision([P("VIOLATED", critical=False), P("HOLDING")], review_in=20, fresh=True),
        "WATCH",
        "DRIFTING",
        Decimal(0),
        {"ON_SCHEDULE"},
    ),
    "H14": (
        decision([P("HOLDING")], review="none", fresh=True, mirror=True),
        "WATCH",
        "HOLDING",
        Decimal(0),
        {"NO_REVIEW_DATE"},
    ),
    "H15": (
        decision([], review="none", status="closed", outcome=("success", "reported")),
        "CLOSED",
        None,
        None,
        set(),
    ),
    "H16": (
        decision([P("UNKNOWN"), P("HOLDING")], review_in=20, fresh=True),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        {"ON_SCHEDULE"},
    ),
    "H17": (
        decision([P("VIOLATED", critical=False), P("HOLDING", critical=False)], review_in=20),
        "REVIEW_REQUIRED",
        "VIOLATED",
        Decimal(0),
        set(),
    ),
    "H18": (
        decision([P("NOT_YET_DUE"), P("NOT_YET_DUE")], review_in=20, fact_age=40),
        "AWAITING_CHECKS",
        "AWAITING",
        Decimal(0),
        {"NO_DATA_SINCE"},
    ),
}


@pytest.mark.parametrize("name", sorted(VECTORS, key=lambda n: int(n[1:])))
def test_the_oracle_reproduces_the_named_vectors(name: str) -> None:
    view, label, ground, share, kinds = VECTORS[name]
    got = oracle_health(view, T, CFG)
    assert got.label == label
    assert got.ground == ground
    assert got.share == share
    assert kinds <= got.timeliness


@pytest.mark.parametrize("name", sorted(VECTORS, key=lambda n: int(n[1:])))
def test_the_module_agrees_on_the_named_vectors(name: str, module_health: Any) -> None:
    view, label, *_ = VECTORS[name]
    got = module_health(view)
    assert got.label == label
    if view.status == "active":
        assert _cmp(got) == _cmp(oracle_health(view, T, CFG))


def test_the_oracles_date_table() -> None:
    base = T.date.replace(month=11, day=2)
    assert dates_in("by 2026-11-20 or 15.12.2026, else 03.01", base) == [
        base.replace(day=20),
        base.replace(month=12, day=15),
        base.replace(year=2027, month=1, day=3),
    ]
    assert dates_in("1.5 or 0.80 or 12.5 % or 31.02", base) == []
    assert dates_in("on 5.11.2026 and 15.11", base) == [base.replace(day=5), base.replace(day=15)]
    assert dates_in("&nbsp;10.11&lt;", base) == [base.replace(day=10)]
    assert dates_in(None, base) == []


# ==================================================================================================
# The enumerated space (§3.7): 0-3 assumptions, critical or not, 7 effective states each; the
# review none, future, today, overdue or reviewed after its due date; fresh or stale activity;
# depth light or full; a manual flag or none.


def _space() -> Iterator[tuple[str, DecisionView]]:
    kinds = [(c, s) for c in (True, False) for s in STATES]
    for n in range(4):
        for combo in itertools.combinations_with_replacement(kinds, n):
            plants = [
                Plant(critical=c, state=s, via_source_none=(s == "UNVERIFIABLE" and i % 2 == 0))
                for i, (c, s) in enumerate(combo)
            ]
            for review, fresh, flag in itertools.product(REVIEWS, (True, False), (None, "ZOMBIE")):
                for depth in ("light", "full") if n == 0 else ("full",):
                    name = f"{combo}|{review}|fresh={fresh}|{flag}|{depth}"
                    yield name, decision(plants, review=review, fresh=fresh, flag=flag, depth=depth)


def test_the_space_is_what_the_spec_enumerates() -> None:
    names = [name for name, _ in _space()]
    assert len(names) == len(set(names))
    # (1 + 14 + 105 + 560) assumption multisets x 5 reviews x 2 activities x 2 flags, and the
    # empty set once more for the second depth.
    assert len(names) == (1 + 14 + 105 + 560) * 20 + 20


def test_the_module_and_the_oracle_agree_on_the_whole_space(module_health: Any) -> None:
    disagreements = []
    for index, (name, view) in enumerate(_space()):
        mine = _cmp(oracle_health(view, T, CFG))
        theirs = _cmp(pure_health(view))
        if mine != theirs:
            disagreements.append(f"{name}\n  oracle {mine}\n  module {theirs}")
        if index % SAMPLE_EVERY == 0:
            assert _cmp(module_health(view)) == theirs, f"query and pure path differ: {name}"
    summary = "\n".join(disagreements[:20])
    assert not disagreements, f"{len(disagreements)} disagreements:\n{summary}"
