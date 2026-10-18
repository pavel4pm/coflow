"""Track S: a source zone unlike the owner's (found by the I1 review). The owner here keeps UTC
while the synthetic source writes its dates in Europe/Berlin, as a fresh ``coflow init`` would."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store.api import Store
from coflow.modules.dec import api as dec
from tests.modules.dec import snapshot_builder as sb
from tests.modules.dec.import_helpers import import_doc, one, rows

Doc = dict[str, Any]


@pytest.fixture
def owner_tz() -> str:
    return "UTC"


@pytest.fixture
def env(dev_store: Store) -> Any:
    return dec.default_env()


def _decision(doc: Doc, v1_id: int) -> Doc:
    return next(d for d in doc["decisions"] if d["v1_id"] == v1_id)


def _near_midnight(doc: Doc) -> None:
    """Exported at 00:30 in the source's zone: its day is already the 15th, UTC's still the 14th."""
    doc.update(
        exported_at="2026-11-14T23:30:12Z", as_of="2026-11-14T23:30:00Z", as_of_date="2026-11-15"
    )
    _decision(doc, 910)["review_due"] = "2026-11-14"
    _decision(doc, 906)["versions"].append(
        {
            "v1_id": 90631,
            "entity": "assumption",
            "entity_v1_id": 9063,
            "field": "state",
            "old_value": "NOT_YET_DUE",
            "new_value": "HOLDING",
            "source": "app",
            "changed_by": "owner",
            "changed_at": "2026-11-09T23:30:00Z",  # 10 November in the source's zone
        }
    )


def _import(env: Any, clock: FakeClock, ctx: CommandContext, tmp_path: Path) -> Any:
    doc = sb.planted(sb.s1, _near_midnight)
    at = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)
    return import_doc(env, doc, tmp_path / "s1-midnight.json", clock=clock, ctx=ctx, at=at).value


def test_a_zone_mismatch_is_a_finding_and_a_coverage_note(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    report = _import(env, clock, owner_ctx, tmp_path)
    assert any("Europe/Berlin is not the owner's zone UTC" in f for f in report.findings)
    shadow = dec.shadow_report(env, run_id=report.run_id)
    assert any("Europe/Berlin is not the owner's zone UTC" in n for n in shadow.coverage)


def test_health_due_and_waiting_share_the_snapshot_s_day(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    report = _import(env, clock, owner_ctx, tmp_path)
    output = json.loads(
        one("SELECT v2_output_json FROM dec_import_runs WHERE id = ?", (report.run_id,))
    )
    assert output["as_of_date"] == "2026-11-15"
    health = output["health"]["D-0910"]
    assert "REVIEW_OVERDUE" in health["timeliness"]  # the 14th is past on the 15th
    assert "DUE_TODAY" not in health["timeliness"]
    waiting = {i["ref"]: i["reasons"] for i in output["waiting"]}
    assert ["review_overdue", "2026-11-14", ""] in waiting["D-0910"]


def test_a_check_near_midnight_is_rebuilt_once(
    env: Any, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    _import(env, clock, owner_ctx, tmp_path)
    checks = rows(
        "SELECT c.observed_at, c.observed_precision FROM dec_checks c "
        "JOIN dec_assumptions a ON a.id = c.assumption_id "
        "JOIN dec_decisions d ON d.id = a.decision_id "
        "WHERE d.public_id = 'D-0906' AND a.code_n = 3"
    )
    # the version row's instant is on 10 November in the source's zone, the day v1 wrote as
    # last_checked_at: no second, day-precision assessment for the same check
    assert checks == [{"observed_at": "2026-11-09T23:30:00.000Z", "observed_precision": "instant"}]
