"""Typed errors and the refusal-code catalogue (ARCHITECTURE §6.1, spec §5.1).

Skeleton file (spec §12.1): a new code is a reviewed skeleton pull request, so the catalogue stays
closed and every interface renders the same codes.

- ``NotFound(ref)``, ``Ambiguous(candidates)``, ``Refused(code, detail, missing, allowed)`` and
  ``Conflict(current_version)`` are what commands and queries raise. Over MCP they are rendered by
  ``error_payload`` as ``{"error": {"type", "code", "detail", "missing", "allowed",
  "candidates"}}``.
- Ports return refusals as values instead of raising (``Accept | Refused``, §4.2), so a spoke can
  decide in its prepare phase; the same classes serve both uses.
- ``ContractViolation`` is a programming error (for example a caller passing ``tx`` or
  ``recorded_at`` to the store, §2.1). It is never shown to the owner as a refusal; tests assert it.

Spec note: §5.1 lists the codes of the slice. The skeleton adds codes where the spec says "refused"
without naming one, marked ``# skeleton`` below: ``NOT_FOUND`` (the ``accepts_attachment`` value of
§3.14), ``PREFIX_UNKNOWN`` (AT-K2), ``NOT_ACTIVE`` (``set_manual_flag``), ``COMPLETION_NOT_PENDING``
(``complete_decision``), ``FORK_NOT_OPEN`` (``decide_fork``), ``CASE_ROLE`` (``run_case``),
``DATA_ROOT_IN_REPOSITORY`` (AT-K9), ``INSTANCE_LOCKED`` (AT-K7) and ``READ_ONLY_TOKEN`` (AT-M1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "Accept",
    "Ambiguous",
    "CoflowError",
    "Conflict",
    "ContractViolation",
    "NotFound",
    "RefusalCode",
    "Refused",
    "error_payload",
]


class RefusalCode(StrEnum):
    """Every refusal code of the slice (spec §5.1). Values equal names."""

    # activation and seal
    ACTIVATION_GATE = "ACTIVATION_GATE"
    SEALED_USE_REVISE = "SEALED_USE_REVISE"
    USE_A_REVIEW = "USE_A_REVIEW"
    NATIVE_OTHER_DECIDER = "NATIVE_OTHER_DECIDER"
    # lifecycle
    TERMINAL_DECISION = "TERMINAL_DECISION"
    DRAFT_ACTIVATE_FIRST = "DRAFT_ACTIVATE_FIRST"
    MIRRORED = "MIRRORED"
    DECISION_ENDED = "DECISION_ENDED"
    # review dates
    REVIEW_DATE_REQUIRED = "REVIEW_DATE_REQUIRED"
    REVIEW_DATE_OUT_OF_RANGE = "REVIEW_DATE_OUT_OF_RANGE"
    # revise
    REVISION_EMPTY = "REVISION_EMPTY"
    REVISE_BASIS_REQUIRED = "REVISE_BASIS_REQUIRED"
    TRIGGER_FACT_REQUIRED = "TRIGGER_FACT_REQUIRED"
    # closing and outcomes
    REASON_REQUIRED = "REASON_REQUIRED"
    OUTCOME_REQUIRED = "OUTCOME_REQUIRED"
    OUTCOME_BASIS_REQUIRED = "OUTCOME_BASIS_REQUIRED"
    OUTCOME_UNKNOWN_NEEDS_NOT_CONFIRMED = "OUTCOME_UNKNOWN_NEEDS_NOT_CONFIRMED"
    RESOLVED_NEEDS_EVIDENCE = "RESOLVED_NEEDS_EVIDENCE"
    REPORTED_NEEDS_A_REPORT = "REPORTED_NEEDS_A_REPORT"
    LEARNING_REQUIRED = "LEARNING_REQUIRED"
    SUCCESSOR_INVALID = "SUCCESSOR_INVALID"
    # assumptions and checks
    FOREIGN_ASSUMPTION = "FOREIGN_ASSUMPTION"
    FOREIGN_EVIDENCE = "FOREIGN_EVIDENCE"
    GROUNDS_ARE_BASIS = "GROUNDS_ARE_BASIS"
    ASSUMPTION_NOT_ACTIVE = "ASSUMPTION_NOT_ACTIVE"
    STATE_NOT_ALLOWED = "STATE_NOT_ALLOWED"
    NEXT_CHECK_OUT_OF_RANGE = "NEXT_CHECK_OUT_OF_RANGE"
    POSTPONE_OUT_OF_RANGE = "POSTPONE_OUT_OF_RANGE"
    DATA_SOURCE_KIND_REQUIRED = "DATA_SOURCE_KIND_REQUIRED"
    PROBABILITY_NOT_OWNER = "PROBABILITY_NOT_OWNER"
    PROBABILITY_OUT_OF_RANGE = "PROBABILITY_OUT_OF_RANGE"
    EVENT_TIME_IN_FUTURE = "EVENT_TIME_IN_FUTURE"
    # evidence
    JOURNAL_CLASS_INPUT = "JOURNAL_CLASS_INPUT"
    QUOTE_NOT_IN_SOURCE = "QUOTE_NOT_IN_SOURCE"
    # links
    LINK_ROLE_UNKNOWN = "LINK_ROLE_UNKNOWN"
    LINK_SELF = "LINK_SELF"
    LINK_CYCLE = "LINK_CYCLE"
    # proposals and MCP-origin writes
    OWNER_CHANNEL_REQUIRED = "OWNER_CHANNEL_REQUIRED"
    OWNER_QUOTE_REQUIRED = "OWNER_QUOTE_REQUIRED"
    PROPOSAL_REJECTED_BEFORE = "PROPOSAL_REJECTED_BEFORE"
    PROPOSAL_ORIGIN_SWITCHED_OFF = "PROPOSAL_ORIGIN_SWITCHED_OFF"
    NOT_PROPOSED = "NOT_PROPOSED"
    # publishability
    PUBLISHABILITY_LOCKED = "PUBLISHABILITY_LOCKED"
    # undo
    UNDO_WINDOW_PASSED = "UNDO_WINDOW_PASSED"
    UNDO_HAS_LATER_WRITES = "UNDO_HAS_LATER_WRITES"
    NOT_UNDOABLE = "NOT_UNDOABLE"
    # import
    IMPORT_ROLE = "IMPORT_ROLE"
    IMPORT_NOT_SYNTHETIC = "IMPORT_NOT_SYNTHETIC"
    IMPORT_FORMAT_UNSUPPORTED = "IMPORT_FORMAT_UNSUPPORTED"
    IMPORT_SOURCE_CONFLICT = "IMPORT_SOURCE_CONFLICT"
    IMPORT_HASH_MISMATCH = "IMPORT_HASH_MISMATCH"
    IMPORT_ADOPTED = "IMPORT_ADOPTED"
    # adoption
    ADOPTION_GATE = "ADOPTION_GATE"
    # commitments
    DONE_NEEDS_TIME = "DONE_NEEDS_TIME"
    SHIFT_NEEDS_REASON = "SHIFT_NEEDS_REASON"
    EXPLICIT_NONE_NEEDS_REASON = "EXPLICIT_NONE_NEEDS_REASON"
    SUGGESTED_DONE_FROM_PROPOSAL_ONLY = "SUGGESTED_DONE_FROM_PROPOSAL_ONLY"
    # added by the skeleton where the spec says "refused" without a code (see the module docstring)
    NOT_FOUND = "NOT_FOUND"  # skeleton
    PREFIX_UNKNOWN = "PREFIX_UNKNOWN"  # skeleton
    NOT_ACTIVE = "NOT_ACTIVE"  # skeleton
    COMPLETION_NOT_PENDING = "COMPLETION_NOT_PENDING"  # skeleton
    FORK_NOT_OPEN = "FORK_NOT_OPEN"  # skeleton
    CASE_ROLE = "CASE_ROLE"  # skeleton
    DATA_ROOT_IN_REPOSITORY = "DATA_ROOT_IN_REPOSITORY"  # skeleton
    INSTANCE_LOCKED = "INSTANCE_LOCKED"  # skeleton
    READ_ONLY_TOKEN = "READ_ONLY_TOKEN"  # skeleton


class CoflowError(Exception):
    """Base of every typed error."""

    type_name = "error"


class NotFound(CoflowError):
    """Nothing answers to ``ref``."""

    type_name = "not_found"

    def __init__(self, ref: str, detail: str = "") -> None:
        self.ref = ref
        self.detail = detail or f"{ref} not found"
        super().__init__(self.detail)


class Ambiguous(CoflowError):
    """Several records answer to the input; ``candidates`` are their canonical refs, best first."""

    type_name = "ambiguous"

    def __init__(self, candidates: Iterable[str], detail: str = "") -> None:
        self.candidates: tuple[str, ...] = tuple(candidates)
        self.detail = detail or f"ambiguous: {', '.join(self.candidates)}"
        super().__init__(self.detail)


class Refused(CoflowError):
    """A rule refused the call. Every refusal names what would make the call valid (§5.1).

    ``missing`` lists what is missing (``ACTIVATION_GATE(missing=[...])``); ``allowed`` lists what
    is allowed instead (``TERMINAL_DECISION(allowed=['close'])``).
    """

    type_name = "refused"

    def __init__(
        self,
        code: RefusalCode | str,
        detail: str = "",
        *,
        missing: Iterable[str] = (),
        allowed: Iterable[str] = (),
    ) -> None:
        self.code = RefusalCode(code)  # an unknown code is a ValueError: the catalogue is closed
        self.detail = detail
        self.missing: tuple[str, ...] = tuple(missing)
        self.allowed: tuple[str, ...] = tuple(allowed)
        super().__init__(f"{self.code}: {detail}" if detail else str(self.code))


class Conflict(CoflowError):
    """Optimistic concurrency: the caller's ``expected_version`` is not the current one (§2.1)."""

    type_name = "conflict"

    def __init__(self, current_version: int, detail: str = "") -> None:
        self.current_version = current_version
        self.detail = detail or f"current version is {current_version}"
        super().__init__(self.detail)


class ContractViolation(CoflowError):
    """A caller broke a kernel contract: a programming error, never an answer to the owner."""

    type_name = "contract_violation"


@dataclass(frozen=True, slots=True)
class Accept:
    """The positive answer of a port check such as ``DecisionDirectory.accepts_attachment``."""

    note: str = ""


def error_payload(err: CoflowError) -> dict[str, object]:
    """The wire form of a typed error (spec §5.1), identical for MCP and the admin API."""
    body: dict[str, object] = {
        "type": err.type_name,
        "code": None,
        "detail": getattr(err, "detail", str(err)),
        "missing": [],
        "allowed": [],
        "candidates": [],
    }
    if isinstance(err, Refused):
        body.update(code=str(err.code), missing=list(err.missing), allowed=list(err.allowed))
    elif isinstance(err, Ambiguous):
        body["candidates"] = list(err.candidates)
    elif isinstance(err, NotFound):
        body["code"] = str(RefusalCode.NOT_FOUND)
    elif isinstance(err, Conflict):
        body["current_version"] = err.current_version
    return {"error": body}
