"""Skeleton smoke test: the package imports, the shared contracts hold, the fakes fit the ports."""

from __future__ import annotations

import hashlib
import importlib
import json
import pkgutil
import unicodedata
from datetime import UTC, date, datetime, timedelta
from typing import Any

import jsonschema
import pytest

import coflow
from coflow import contracts
from coflow.kernel.context import (
    CommandContext,
    EvalTime,
    FakeClock,
    format_instant,
    local_date,
    new_salt,
    parse_instant,
    seeded_salts,
)
from coflow.kernel.errors import Ambiguous, RefusalCode, Refused, error_payload
from coflow.kernel.ids.registry import SLICE_PREFIXES
from coflow.kernel.ports.attachment_probe import DecisionAttachmentProbe
from coflow.kernel.ports.decision_directory import DecisionDirectory
from coflow.kernel.ports.evidence_resolver import EvidenceResolver, quote_in_text
from coflow.kernel.ports.goal_directory import GoalDirectory
from coflow.kernel.ports.undo import UndoHandler
from coflow.modules.dec import api as dec_api
from tests.fakes import (
    FakeAttachmentProbe,
    FakeDecisionDirectory,
    FakeEvidenceResolver,
    FakeGoalDirectory,
    FakeUndoHandler,
)

EXAMPLE = "import_decisions_v1.example.json"

# The refusal codes of spec §5.1, verbatim.
SPEC_CODES = [
    "ACTIVATION_GATE",
    "SEALED_USE_REVISE",
    "USE_A_REVIEW",
    "NATIVE_OTHER_DECIDER",
    "TERMINAL_DECISION",
    "DRAFT_ACTIVATE_FIRST",
    "MIRRORED",
    "DECISION_ENDED",
    "REVIEW_DATE_REQUIRED",
    "REVIEW_DATE_OUT_OF_RANGE",
    "REVISION_EMPTY",
    "REVISE_BASIS_REQUIRED",
    "TRIGGER_FACT_REQUIRED",
    "REASON_REQUIRED",
    "OUTCOME_REQUIRED",
    "OUTCOME_BASIS_REQUIRED",
    "OUTCOME_UNKNOWN_NEEDS_NOT_CONFIRMED",
    "RESOLVED_NEEDS_EVIDENCE",
    "REPORTED_NEEDS_A_REPORT",
    "LEARNING_REQUIRED",
    "SUCCESSOR_INVALID",
    "FOREIGN_ASSUMPTION",
    "FOREIGN_EVIDENCE",
    "GROUNDS_ARE_BASIS",
    "ASSUMPTION_NOT_ACTIVE",
    "STATE_NOT_ALLOWED",
    "NEXT_CHECK_OUT_OF_RANGE",
    "POSTPONE_OUT_OF_RANGE",
    "DATA_SOURCE_KIND_REQUIRED",
    "PROBABILITY_NOT_OWNER",
    "PROBABILITY_OUT_OF_RANGE",
    "EVENT_TIME_IN_FUTURE",
    "JOURNAL_CLASS_INPUT",
    "QUOTE_NOT_IN_SOURCE",
    "LINK_ROLE_UNKNOWN",
    "LINK_SELF",
    "LINK_CYCLE",
    "OWNER_CHANNEL_REQUIRED",
    "OWNER_QUOTE_REQUIRED",
    "PROPOSAL_REJECTED_BEFORE",
    "PROPOSAL_ORIGIN_SWITCHED_OFF",
    "NOT_PROPOSED",
    "PUBLISHABILITY_LOCKED",
    "UNDO_WINDOW_PASSED",
    "UNDO_HAS_LATER_WRITES",
    "NOT_UNDOABLE",
    "IMPORT_ROLE",
    "IMPORT_NOT_SYNTHETIC",
    "IMPORT_FORMAT_UNSUPPORTED",
    "IMPORT_SOURCE_CONFLICT",
    "IMPORT_HASH_MISMATCH",
    "IMPORT_ADOPTED",
    "ADOPTION_GATE",
    "DONE_NEEDS_TIME",
    "SHIFT_NEEDS_REASON",
    "EXPLICIT_NONE_NEEDS_REASON",
    "SUGGESTED_DONE_FROM_PROPOSAL_ONLY",
]


def test_every_module_imports() -> None:
    names = [m.name for m in pkgutil.walk_packages(coflow.__path__, prefix="coflow.")]
    assert "coflow.modules.dec.api" in names
    for name in names:
        importlib.import_module(name)
    assert coflow.__version__


def test_fake_clock_world(clock: FakeClock, owner_tz: str, today: date) -> None:
    now = clock.now()
    assert now == datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
    assert local_date(now, owner_tz) == today
    assert format_instant(now) == "2026-11-15T09:30:00.000Z"
    assert parse_instant("2026-11-15T09:30:00.000Z") == now
    t = EvalTime.end_of_day(today, owner_tz)
    assert t.date == today
    assert format_instant(t.instant) == "2026-11-15T22:59:59.999Z"
    clock.advance(days=1)
    assert EvalTime.at(clock.now(), owner_tz).date == today + timedelta(days=1)


def test_salts_are_hex_and_seedable() -> None:
    salt = new_salt()
    assert len(salt) == 32
    int(salt, 16)
    with seeded_salts("fixture"):
        first = [new_salt(), new_salt()]
    with seeded_salts("fixture"):
        assert [new_salt(), new_salt()] == first
    assert first[0] != first[1]


def test_contexts_and_errors(owner_ctx: CommandContext) -> None:
    with pytest.raises(ValueError, match="never an owner channel"):
        CommandContext(actor="mcp_x", channel="mcp", owner_channel=True, interaction_id="i")
    imported = owner_ctx.with_actor("import_v1", channel="import")
    assert imported.channel == "import"
    assert not imported.owner_channel

    assert set(SPEC_CODES) <= {c.value for c in RefusalCode}
    assert all(c.name == c.value for c in RefusalCode)
    with pytest.raises(ValueError, match="NO_SUCH_CODE"):
        Refused("NO_SUCH_CODE")
    payload = error_payload(Refused(RefusalCode.ACTIVATION_GATE, missing=["question"]))
    assert payload["error"]["code"] == "ACTIVATION_GATE"
    assert payload["error"]["missing"] == ["question"]
    assert error_payload(Ambiguous(["D-0907", "D-1001"]))["error"]["candidates"] == [
        "D-0907",
        "D-1001",
    ]


def test_fakes_fit_their_ports() -> None:
    assert isinstance(FakeDecisionDirectory(), DecisionDirectory)
    assert isinstance(FakeAttachmentProbe(), DecisionAttachmentProbe)
    assert isinstance(FakeEvidenceResolver(), EvidenceResolver)
    assert isinstance(FakeGoalDirectory(), GoalDirectory)
    assert isinstance(FakeUndoHandler(), UndoHandler)
    assert quote_in_text("one  more\nweek", "The landlord asked for one more week")


def test_prefix_table_follows_the_owner_answer() -> None:
    by_prefix = {p.prefix: p for p in SLICE_PREFIXES}
    assert (by_prefix["D"].width, by_prefix["D"].block_start) == (4, 1001)
    assert (by_prefix["F"].width, by_prefix["F"].block_start) == (5, 10001)
    assert by_prefix["Q"].entity == "fork"
    assert by_prefix["CK"].scoped_under == ("A",)


def test_facade_wires_a_default_environment() -> None:
    env = dec_api.default_env()
    assert isinstance(env.goal_directory, GoalDirectory)
    assert env.attachment_probes == ()


def _cfj(obj: Any) -> bytes:
    def normalise(x: Any) -> Any:
        if isinstance(x, str):
            return unicodedata.normalize("NFC", x)
        if isinstance(x, float):
            raise TypeError("CFJ-1 refuses floats")
        if isinstance(x, list):
            return [normalise(v) for v in x]
        if isinstance(x, dict):
            return {str(k): normalise(v) for k, v in x.items()}
        return x

    return json.dumps(
        normalise(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def test_snapshot_schema_and_example() -> None:
    schema = contracts.load_schema("coflow.import.decisions/1")
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    example = json.loads(contracts.load_example(EXAMPLE))
    validator.validate(example)

    body = {k: v for k, v in example.items() if k != "content_hash"}
    assert example["content_hash"] == "sha256:" + hashlib.sha256(_cfj(body)).hexdigest()

    unknown = json.loads(contracts.load_example(EXAMPLE))
    unknown["decisions"][0]["surprise"] = 1
    assert not validator.is_valid(unknown)
    missing = json.loads(contracts.load_example(EXAMPLE))
    del missing["synthetic"]
    assert not validator.is_valid(missing)
    fraction = json.loads(contracts.load_example(EXAMPLE))
    fraction["decisions"][0]["confidence"] = 70.5
    assert not validator.is_valid(fraction)
