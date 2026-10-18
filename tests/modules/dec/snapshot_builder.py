"""The synthetic snapshot family S1, S1′ and S1″ (spec §9.1) and planted variants.

Everything here is invented: the decisions, titles, people ("Person A"), companies ("Supplier A",
"Example Landlord Ltd") and numbers. The JSON files in ``tests/fixtures/synthetic/snapshots/`` are
generated from these functions (``python -m tests.modules.dec.snapshot_builder``), and a test
checks that the committed files equal the builder's output byte for byte.

The content hash is computed by the exporter-side algorithm documented in
``coflow/contracts/README.md``, written out here independently of DEC's ``cfj``.

The world (as of 2026-11-15, owner zone Europe/Berlin; v1 numbers 903 to 910, 901 and 902 deleted):

| v1  | trait (AT-S1)                                    | v2 at S1                       | rule   |
|-----|--------------------------------------------------|--------------------------------|--------|
| 903 | closed, outcome success                          | CLOSED · success · reported    | same   |
| 904 | every assumption unverifiable, review overdue    | STALE (v1 INSUFFICIENT_DATA)   | SR-2   |
| 905 | no assumptions                                   | INSUFFICIENT_DATA              | same   |
| 906 | active without a review date (2 of 3 uncheckable)| INSUFFICIENT_DATA (v1 WATCH)   | SR-3/8 |
| 907 | serves V1_G901, dropped 11-05 after decided 11-02| STALE; goal_changed waits      | SR-9   |
| 908 | a non-critical violated assumption               | WATCH (v1 ON_TRACK)            | SR-7   |
| 909 | HOLDING with a weekly check overdue              | WATCH (v1 ON_TRACK)            | SR-5   |
| 910 | a state reset in v1 (UNKNOWN)                    | AWAITING_CHECKS (v1 WATCH)     | SR-1   |

S1′ (as of 11-16): the fact of 907 is reworded, 905 is removed, the statement of 908 changes
(without a version row), and the last check of 909 moves to 11-14 without a version row.

S1″ (as of 12-11, after S1′): 907 has a review dated 11-10 (recorded 12-05) and its assumption
checked HOLDING on 11-10 (SR-6: nothing recorded since); 910 is checked HOLDING (a v1 version
row), gains an uncheckable assumption and a later review date (SR-4); 908 is flagged ZOMBIE and its
critical assumption is violated (SR-10 next to SR-7).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "snapshots"

Doc = dict[str, Any]


# ------------------------------------------------------------------------------ the content hash


def _normalise(x: Any) -> Any:
    if isinstance(x, str):
        return unicodedata.normalize("NFC", x)
    if isinstance(x, float):
        raise TypeError("CFJ-1 refuses floats")
    if isinstance(x, list):
        return [_normalise(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _normalise(v) for k, v in x.items()}
    return x


def content_hash(document: Doc) -> str:
    body = {k: v for k, v in document.items() if k != "content_hash"}
    canonical = json.dumps(
        _normalise(body), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def finalize(doc: Doc) -> Doc:
    """Recompute ``counts`` from the rows and seal ``content_hash`` (call after every edit)."""
    decisions = doc["decisions"]
    doc["counts"] = {
        "decisions": len(decisions),
        "assumptions": sum(len(d["assumptions"]) for d in decisions),
        "facts": sum(len(d["facts"]) for d in decisions),
        "reviews": sum(len(d["reviews"]) for d in decisions),
        "links": sum(len(d["links"]) for d in decisions),
        "versions": sum(len(d["versions"]) for d in decisions),
    }
    doc["content_hash"] = content_hash(doc)
    return doc


def dumps(doc: Doc) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def write(doc: Doc, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(doc), encoding="utf-8", newline="\n")
    return path


# ------------------------------------------------------------------------------------ row helpers


def _decision(v1_id: int, title: str, **fields: Any) -> Doc:
    base: Doc = {
        "v1_id": v1_id,
        "v1_ref": f"D{v1_id}",
        "kind": "choice",
        "decider_mapping": "self",
        "title": title,
        "statement": None,
        "context": None,
        "alternatives": [],
        "investment": None,
        "expected_result": None,
        "confidence": None,
        "decided_at": None,
        "review_due": None,
        "owner_person": None,
        "executor_person": None,
        "about_person": None,
        "about_company": None,
        "context_known": None,
        "context_unknown": None,
        "context_would_help": None,
        "status": "active",
        "manual_health": None,
        "outcome": None,
        "learning": None,
        "process_type": None,
        "folder_path": None,
        "source_session": None,
        "created_at": None,
        "closed_at": None,
        "assumptions": [],
        "facts": [],
        "reviews": [],
        "links": [],
        "versions": [],
    }
    unknown = set(fields) - set(base)
    if unknown:
        raise KeyError(f"unknown decision fields {sorted(unknown)}")
    base.update(fields)
    return base


def _assumption(v1_id: int, code: str, statement: str, **fields: Any) -> Doc:
    base: Doc = {
        "v1_id": v1_id,
        "code": code,
        "statement": statement,
        "metric": None,
        "threshold": None,
        "data_source": None,
        "check_frequency": "ad-hoc",
        "is_critical": 1,
        "state": "NOT_YET_DUE",
        "next_check_at": None,
        "last_checked_at": None,
        "position": int(code[1:]),
        "notes": None,
        "created_at": None,
    }
    unknown = set(fields) - set(base)
    if unknown:
        raise KeyError(f"unknown assumption fields {sorted(unknown)}")
    base.update(fields)
    return base


def _fact(v1_id: int, text: str, **fields: Any) -> Doc:
    base: Doc = {
        "v1_id": v1_id,
        "assumption_v1_id": None,
        "phase": "monitoring",
        "occurred_at": None,
        "fact": text,
        "source": None,
        "session": None,
        "created_at": None,
    }
    base.update(fields)
    return base


def _link(kind: str, ref: str, source: str, created_at: str) -> Doc:
    return {"kind": kind, "ref": ref, "source": source, "created_at": created_at}


def _version(v1_id: int, entity: str, entity_v1_id: int, field: str, old: Any, new: Any, at: str):
    return {
        "v1_id": v1_id,
        "entity": entity,
        "entity_v1_id": entity_v1_id,
        "field": field,
        "old_value": old,
        "new_value": new,
        "source": "app",
        "changed_by": "owner",
        "changed_at": at,
    }


def _by_id(doc: Doc, v1_id: int) -> Doc:
    return next(d for d in doc["decisions"] if d["v1_id"] == v1_id)


def _assumption_of(decision: Doc, v1_id: int) -> Doc:
    return next(a for a in decision["assumptions"] if a["v1_id"] == v1_id)


# ------------------------------------------------------------------------------------------- S1


def _s1_decisions() -> list[Doc]:
    d903 = _decision(
        903,
        "Run the autumn workshop series as a pilot",
        statement="Run four evening sessions in October",
        context="Demand for evening sessions was unclear",
        alternatives=[{"option": "Skip the autumn series", "why_rejected": "loses the group"}],
        investment="about 10 hours",
        expected_result="at least 6 people per session",
        confidence=60,
        decided_at="2026-09-01",
        context_known="Last spring 5 people came per session",
        context_unknown="whether evenings suit the group",
        status="closed",
        outcome="success",
        learning="Evening sessions filled up; small groups worked better",
        process_type="operational",
        source_session="S90002",
        created_at="2026-09-01T18:00:00Z",
        closed_at="2026-10-30T17:00:00Z",
        assumptions=[
            _assumption(
                9031,
                "A1",
                "At least 6 people sign up per session",
                metric="sign-ups",
                threshold="6 per session",
                data_source="booking sheet",
                check_frequency="weekly",
                state="HOLDING",
                last_checked_at="2026-10-20",
                created_at="2026-09-01T18:05:00Z",
            )
        ],
        facts=[
            _fact(
                90301,
                "Spring sessions averaged 5 people",
                assumption_v1_id=9031,
                phase="grounding",
                occurred_at="2026-06-30",
                source="booking sheet",
                created_at="2026-09-01T18:06:00Z",
            )
        ],
        reviews=[
            {
                "v1_id": 903001,
                "reviewed_at": "2026-10-30",
                "verdict": "worked",
                "action": "close",
                "health_at_review": "ON_TRACK",
                "next_review_due": None,
                "notes": None,
                "created_at": "2026-10-30T17:00:00Z",
            }
        ],
        links=[_link("topic", "T901", "app", "2026-09-01T18:10:00Z")],
    )
    d904 = _decision(
        904,
        "Offer a monthly maintenance plan to existing customers",
        statement="Offer the plan at a fixed monthly price from October",
        context="Customers ask for repairs at short notice",
        alternatives=[{"option": "Keep billing repairs one by one", "why_rejected": "uneven"}],
        expected_result="five plans sold by January",
        confidence=50,
        decided_at="2026-10-01",
        review_due="2026-11-01",
        about_company="C-902",
        context_unknown="how many customers want a plan",
        created_at="2026-10-01T16:00:00Z",
        assumptions=[
            _assumption(
                9041,
                "A1",
                "Customers value predictable costs",
                threshold="most customers say yes",
                data_source=None,
                state="UNVERIFIABLE",
                created_at="2026-10-01T16:02:00Z",
            ),
            _assumption(
                9042,
                "A2",
                "The plan price covers the average repair cost",
                metric="margin",
                threshold="positive margin",
                data_source="rough estimate from last year",
                state="UNVERIFIABLE",
                last_checked_at="2026-10-20",
                created_at="2026-10-01T16:03:00Z",
            ),
        ],
        links=[_link("goal", "G902", "app", "2026-10-01T16:05:00Z")],
    )
    d905 = _decision(
        905,
        "Switch the newsletter to every second week",
        statement="Send it every second Thursday",
        decided_at="2026-11-05",
        review_due="2026-11-25",
        created_at="2026-11-05T12:00:00Z",
    )
    d906 = _decision(
        906,
        "Rent a second storage unit for the winter",
        statement="Rent a small unit from November to March",
        decided_at="2026-10-20",
        created_at="2026-10-20T10:00:00Z",
        assumptions=[
            _assumption(
                9061,
                "A1",
                "The extra stock sells before spring",
                threshold="sold out by March",
                state="UNVERIFIABLE",
                created_at="2026-10-20T10:01:00Z",
            ),
            _assumption(
                9062,
                "A2",
                "Storage prices stay flat",
                threshold="no increase",
                state="UNVERIFIABLE",
                created_at="2026-10-20T10:02:00Z",
            ),
            _assumption(
                9063,
                "A3",
                "The unit is reachable by van",
                threshold="access confirmed",
                data_source="site visit",
                state="HOLDING",
                last_checked_at="2026-11-10",
                created_at="2026-10-20T10:03:00Z",
            ),
        ],
    )
    d907 = _decision(
        907,
        "Move the shared workshop to a smaller room for one quarter",
        statement="Rent the small room from 1 Dec to 28 Feb; keep the equipment",
        context="The large room costs more than the workshop earns in winter",
        alternatives=[{"option": "Keep the large room", "why_rejected": "cost"}],
        investment="about 6 hours of moving",
        expected_result="rent down by a third",
        confidence=70,
        decided_at="2026-11-02",
        review_due="2026-11-12",
        about_company="C-901",
        context_known="The small room is free from December",
        context_unknown="whether the small room has enough power",
        context_would_help="A test run of the kiln in the small room",
        process_type="operational",
        created_at="2026-11-02T19:02:11Z",
        assumptions=[
            _assumption(
                9071,
                "A1",
                "The landlord confirms the small room by 10.11",
                metric="written confirmation",
                threshold="confirmation by 10.11",
                data_source="mail",
                created_at="2026-11-02T19:03:00Z",
            )
        ],
        facts=[
            _fact(
                90701,
                "The landlord asked for one more week",
                assumption_v1_id=9071,
                occurred_at="2026-11-09",
                source="chat",
                session="S90001",
                created_at="2026-11-09T10:00:00Z",
            )
        ],
        links=[
            _link("goal", "G901", "mcp", "2026-11-02T19:05:00Z"),
            _link("task", "K9001", "app", "2026-11-03T09:00:00Z"),
        ],
        versions=[
            _version(
                90711,
                "decision",
                907,
                "review_due",
                "2026-11-08",
                "2026-11-12",
                "2026-11-03T09:30:00Z",
            )
        ],
    )
    d908 = _decision(
        908,
        "Sell the old display cases through a local listing",
        statement="List all four cases at a fixed price",
        decided_at="2026-10-25",
        review_due="2026-11-30",
        about_person="P901",
        created_at="2026-10-25T09:00:00Z",
        assumptions=[
            _assumption(
                9081,
                "A1",
                "Each case sells for at least 100 EUR",
                metric="price",
                threshold="100 EUR per case",
                data_source="listing messages",
                state="HOLDING",
                last_checked_at="2026-11-08",
                created_at="2026-10-25T09:01:00Z",
            ),
            _assumption(
                9082,
                "A2",
                "A buyer collects the cases within a week",
                threshold="pickup within 7 days",
                data_source="messages",
                is_critical=0,
                state="VIOLATED",
                last_checked_at="2026-11-09",
                created_at="2026-10-25T09:02:00Z",
            ),
        ],
        links=[_link("goal", "G902", "mcp", "2026-10-25T09:05:00Z")],
    )
    d909 = _decision(
        909,
        "Hold a weekly check-in with the evening group",
        statement="Meet every Monday for 30 minutes",
        decided_at="2026-10-05",
        review_due="2026-12-01",
        created_at="2026-10-05T08:00:00Z",
        assumptions=[
            _assumption(
                9091,
                "A1",
                "Attendance stays at four or more",
                metric="attendance",
                threshold="4 or more",
                data_source="attendance list",
                check_frequency="weekly",
                state="HOLDING",
                next_check_at="2026-11-10",
                last_checked_at="2026-11-03",
                created_at="2026-10-05T08:01:00Z",
            )
        ],
    )
    d910 = _decision(
        910,
        "Try a new supplier for clay",
        statement="Order one trial batch from the new supplier",
        decided_at="2026-10-28",
        review_due="2026-12-10",
        about_company="C-902",
        created_at="2026-10-28T11:00:00Z",
        assumptions=[
            _assumption(
                9101,
                "A1",
                "The trial batch arrives in good condition",
                threshold="no broken bags",
                data_source="delivery note",
                state="NOT_YET_DUE",
                last_checked_at="2026-11-06",
                created_at="2026-10-28T11:01:00Z",
            )
        ],
        versions=[
            _version(
                91011,
                "assumption",
                9101,
                "state",
                "HOLDING",
                "NOT_YET_DUE",
                "2026-11-06T10:00:00Z",
            )
        ],
    )
    return [d903, d904, d905, d906, d907, d908, d909, d910]


def _reason(kind: str, due: str | None, assumption: int | None = None) -> Doc:
    out: Doc = {"kind": kind, "due": due}
    if assumption is not None:
        out["assumption_v1_id"] = assumption
    return out


def _due(due: str | None, source: str | None) -> Doc:
    return {"due": due, "source": source}


def s1() -> Doc:
    doc: Doc = {
        "format": "coflow.import.decisions",
        "format_version": 1,
        "synthetic": True,
        "exported_at": "2026-11-15T05:00:12Z",
        "as_of": "2026-11-15T05:00:00Z",
        "as_of_date": "2026-11-15",
        "source": {
            "issuer": "V1",
            "schema_revision": "synthetic-1",
            "exporter_version": "1.0.0",
            "timezone": "Europe/Berlin",
        },
        "id_space": {"decision": {"highest_issued": 910, "deleted_without_trace": [901, 902]}},
        "context": {
            "goals": [
                {
                    "ref": "G901",
                    "title": "Cut fixed costs",
                    "status": "dropped",
                    "status_changed_at": "2026-11-05",
                },
                {
                    "ref": "G902",
                    "title": "Grow the training line",
                    "status": "active",
                    "status_changed_at": None,
                },
            ],
            "tasks": [
                {"ref": "K9001", "title": "Measure the room", "status": "done"},
                {"ref": "K9002", "title": "Book the trial session", "status": "open"},
            ],
            "topics": [{"ref": "T901", "title": "Workshop", "status": "active"}],
            "sessions": [
                {
                    "ref": "S90001",
                    "communication_type": "chat",
                    "started_at": "2026-10-30T08:00:00Z",
                },
                {
                    "ref": "S90002",
                    "communication_type": "call",
                    "started_at": "2026-08-30T09:00:00Z",
                },
            ],
            "people": [
                {"ref": "P901", "display_name": "Person A", "is_self": False},
                {"ref": "P902", "display_name": "Person B", "is_self": False},
            ],
            "companies": [
                {"ref": "C-901", "name": "Example Landlord Ltd"},
                {"ref": "C-902", "name": "Supplier A"},
            ],
        },
        "decisions": _s1_decisions(),
        "v1_computed": {
            "today": "2026-11-15",
            "health": {
                "903": {"label": "CLOSED_SUCCESS", "reasons": ["closed with success"]},
                "904": {"label": "INSUFFICIENT_DATA", "reasons": ["2 of 2 unverifiable"]},
                "905": {"label": "INSUFFICIENT_DATA", "reasons": ["no assumptions"]},
                "906": {"label": "WATCH", "reasons": ["2 unverifiable, 0 not yet checked"]},
                "907": {"label": "STALE", "reasons": ["review overdue"]},
                "908": {"label": "ON_TRACK", "reasons": ["all critical assumptions hold"]},
                "909": {"label": "ON_TRACK", "reasons": ["all critical assumptions hold"]},
                "910": {"label": "WATCH", "reasons": ["1 assumption not yet checked"]},
            },
            "waiting": [
                {"v1_id": 904, "reasons": [_reason("review_overdue", "2026-11-01")]},
                {
                    "v1_id": 907,
                    "reasons": [
                        _reason("review_overdue", "2026-11-12"),
                        _reason("check_due", "2026-11-10", 9071),
                    ],
                },
                {"v1_id": 909, "reasons": [_reason("check_due", "2026-11-10", 9091)]},
            ],
            "assumption_due": {
                "9041": _due("2026-11-01", "review"),
                "9042": _due("2026-11-01", "review"),
                "9061": _due(None, None),
                "9062": _due(None, None),
                "9063": _due(None, None),
                "9071": _due("2026-11-10", "text"),
                "9081": _due("2026-11-30", "review"),
                "9082": _due("2026-11-30", "review"),
                "9091": _due("2026-11-10", "next_check"),
                "9101": _due("2026-12-10", "review"),
            },
        },
        "counts": {},
        "content_hash": "",
    }
    return finalize(doc)


# ------------------------------------------------------------------------------------------- S1′


def s1_prime() -> Doc:
    doc = copy.deepcopy(s1())
    doc["exported_at"] = "2026-11-16T05:00:09Z"
    doc["as_of"] = "2026-11-16T05:00:00Z"
    doc["as_of_date"] = "2026-11-16"
    doc["decisions"] = [d for d in doc["decisions"] if d["v1_id"] != 905]  # removed in v1
    _by_id(doc, 907)["facts"][0]["fact"] = "The landlord asked for two more weeks"
    _by_id(doc, 908)["statement"] = "List all four cases at a lower fixed price"
    _assumption_of(_by_id(doc, 909), 9091)["last_checked_at"] = "2026-11-14"
    v1 = doc["v1_computed"]
    v1["today"] = "2026-11-16"
    del v1["health"]["905"]
    v1["waiting"] = [w for w in v1["waiting"] if w["v1_id"] != 909]
    return finalize(doc)


# ------------------------------------------------------------------------------------------- S1″


def s1_double_prime() -> Doc:
    doc = copy.deepcopy(s1_prime())
    doc["exported_at"] = "2026-12-11T05:00:15Z"
    doc["as_of"] = "2026-12-11T05:00:00Z"
    doc["as_of_date"] = "2026-12-11"

    d907 = _by_id(doc, 907)
    d907["review_due"] = "2026-12-31"
    d907["reviews"] = [
        {
            "v1_id": 907001,
            "reviewed_at": "2026-11-10",
            "verdict": "Wait for the landlord",
            "action": "keep",
            "health_at_review": "WATCH",
            "next_review_due": "2026-12-31",
            "notes": None,
            "created_at": "2026-12-05T18:00:00Z",
        }
    ]
    a9071 = _assumption_of(d907, 9071)
    a9071["state"] = "HOLDING"
    a9071["last_checked_at"] = "2026-11-10"
    d907["versions"].append(
        _version(
            90712,
            "decision",
            907,
            "review_due",
            "2026-11-12",
            "2026-12-31",
            "2026-12-05T18:00:00Z",
        )
    )

    d908 = _by_id(doc, 908)
    d908["manual_health"] = "ZOMBIE"
    a9081 = _assumption_of(d908, 9081)
    a9081["state"] = "VIOLATED"
    a9081["last_checked_at"] = "2026-12-01"
    d908["versions"].append(
        _version(90811, "decision", 908, "manual_health", None, "ZOMBIE", "2026-12-01T10:00:00Z")
    )

    d910 = _by_id(doc, 910)
    d910["review_due"] = "2026-12-30"
    a9101 = _assumption_of(d910, 9101)
    a9101["state"] = "HOLDING"
    a9101["last_checked_at"] = "2026-11-12"
    d910["assumptions"].append(
        _assumption(
            9102,
            "A2",
            "The supplier keeps the trial price for a year",
            threshold="same price",
            state="UNVERIFIABLE",
            created_at="2026-12-01T09:00:00Z",
        )
    )
    d910["versions"] += [
        _version(
            91012, "assumption", 9101, "state", "NOT_YET_DUE", "HOLDING", "2026-11-12T08:00:00Z"
        ),
        _version(
            91013, "decision", 910, "review_due", "2026-12-10", "2026-12-30", "2026-12-01T09:00:00Z"
        ),
    ]

    doc["v1_computed"] = {
        "today": "2026-12-11",
        "health": {
            "903": {"label": "CLOSED_SUCCESS", "reasons": ["closed with success"]},
            "904": {"label": "INSUFFICIENT_DATA", "reasons": ["2 of 2 unverifiable"]},
            "906": {"label": "WATCH", "reasons": ["2 unverifiable, 0 not yet checked"]},
            "907": {"label": "ON_TRACK", "reasons": ["all critical assumptions hold"]},
            "908": {"label": "ZOMBIE", "reasons": ["set by the owner"]},
            "909": {"label": "STALE", "reasons": ["review overdue"]},
            "910": {"label": "WATCH", "reasons": ["1 unverifiable, 0 not yet checked"]},
        },
        "waiting": [
            {"v1_id": 904, "reasons": [_reason("review_overdue", "2026-11-01")]},
            {"v1_id": 908, "reasons": [_reason("review_overdue", "2026-11-30")]},
            {"v1_id": 909, "reasons": [_reason("review_overdue", "2026-12-01")]},
        ],
        "assumption_due": {
            "9041": _due("2026-11-01", "review"),
            "9042": _due("2026-11-01", "review"),
            "9061": _due(None, None),
            "9062": _due(None, None),
            "9063": _due(None, None),
            "9071": _due("2026-12-31", "review"),
            "9081": _due("2026-11-30", "review"),
            "9082": _due("2026-11-30", "review"),
            "9091": _due("2026-11-10", "next_check"),
            "9101": _due("2026-12-30", "review"),
            "9102": _due("2026-12-30", "review"),
        },
    }
    return finalize(doc)


# ---------------------------------------------------------------------------- planted variants


def planted(base: Callable[[], Doc], edit: Callable[[Doc], None]) -> Doc:
    """A copy of a family member with ``edit`` applied to it, re-sealed."""
    doc = copy.deepcopy(base())
    edit(doc)
    return finalize(doc)


FILES: dict[str, Callable[[], Doc]] = {
    "s1.json": s1,
    "s1_prime.json": s1_prime,
    "s1_double_prime.json": s1_double_prime,
}


def main(argv: list[str] | None = None) -> int:
    target = Path(argv[0]) if argv else SNAPSHOT_DIR
    for name, build in FILES.items():
        write(build(), target / name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
