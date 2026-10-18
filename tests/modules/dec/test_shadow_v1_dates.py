"""The shadow comparison of reasons v1 lists without a date (spec §6.6, §3.8; integration).

v1's waiting list never dates a ``violated`` reason, while v2 dates it by the violation's observed
day. The v1 exporter writes such reasons with ``due: null``; the comparison then matches on kind and
assumption alone, and still compares every date v1 does state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store.api import Store
from coflow.modules.dec import api as dec
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import import_doc, planted

S1_AT = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


def _critical_violation(v1_due: str | None) -> Any:
    """S1 with 908's critical assumption violated, listed first by v1 as v1 lists it."""

    def edit(d: dict[str, Any]) -> None:
        d908 = next(x for x in d["decisions"] if x["v1_id"] == 908)
        a1, a2 = d908["assumptions"]
        a1["state"] = "VIOLATED"
        a2["state"] = "HOLDING"
        d["v1_computed"]["health"]["908"] = {
            "label": "REVIEW_REQUIRED",
            "reasons": ["a critical assumption is violated"],
        }
        reason = {"kind": "violated", "due": v1_due, "assumption_v1_id": 9081, "critical": True}
        d["v1_computed"]["waiting"].insert(0, {"v1_id": 908, "reasons": [reason]})

    return planted(sb.s1, edit)


def test_a_dateless_v1_violation_matches_v2s_dated_one(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    doc = _critical_violation(None)
    result = import_doc(env, doc, tmp_path / "v.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    report = dec.shadow_report(env, run_id=result.value.run_id).value
    assert report.unexpected == (), [str(i) for i in report.unexpected]
    reasons = [
        (i.classification, i.v1_value, i.v2_value)
        for i in report.items
        if i.decision_ref == "D-0908" and i.aspect == "waiting_reasons"
    ]
    assert reasons == [("same", "violated - A-01", "violated - A-01")]
    order = {i.decision_ref: i.classification for i in report.items if i.aspect == "order"}
    assert order["D-0908"] == "same"


def test_a_violation_date_v1_does_state_is_still_compared(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    doc = _critical_violation("2026-11-01")
    result = import_doc(env, doc, tmp_path / "v.json", clock=clock, ctx=owner_ctx, at=S1_AT)
    report = dec.shadow_report(env, run_id=result.value.run_id).value
    got = {(i.decision_ref, i.aspect, i.v1_value, i.v2_value) for i in report.unexpected}
    assert ("D-0908", "waiting_reasons", "violated 2026-11-01 A-01", None) in got
