"""``DecisionDirectory``: how spokes and same-tier modules reach decisions without importing DEC.

Skeleton file (spec §4.2, §12.1). Implemented by DEC (``modules/dec/directory.py``); used by CMT in
the slice and by SIG, PPL, CAL, WRK, MTG and RHY later. The waiting-list DTOs (``Reason``,
``QuestionContext``, ``WaitingItem``) live here because the waiting list is one list for the CLI,
MCP and, from stage 2, the plan and the bot (§3.8); DEC's domain model re-exports them.

Spec note: ``resolve`` and ``accepts_attachment`` return ``NotFound`` / ``Ambiguous`` / ``Refused``
instances as values, as §4.2 writes them, so a spoke decides in its prepare phase without exception
handling across the port.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from coflow.kernel.errors import Accept, Ambiguous, NotFound, Refused

__all__ = [
    "RESERVED_WAITING_KINDS",
    "WAITING_KINDS",
    "AskedPart",
    "DecisionDirectory",
    "DecisionInfo",
    "DecisionState",
    "EntryContext",
    "FactLine",
    "GoalLine",
    "Offer",
    "ProbeItem",
    "QuestionContext",
    "Reason",
    "Resolved",
    "SubjectKind",
    "WaitingItem",
    "WaitingKind",
]

WaitingKind = Literal[
    "violated",
    "review_overdue",
    "review_today",
    "goal_changed",
    "check_due",
    "incomplete",
    "fork_due",
    "proposal_waiting",
]
"""Waiting reasons of §3.8, in their rank order (``KIND_RANK``)."""

WAITING_KINDS: tuple[WaitingKind, ...] = (
    "violated",
    "review_overdue",
    "review_today",
    "goal_changed",
    "check_due",
    "incomplete",
    "fork_due",
    "proposal_waiting",
)
RESERVED_WAITING_KINDS: tuple[str, ...] = ("expectation_missed", "contradiction")  # [LATER 3]

SubjectKind = Literal["decision", "fork", "proposal"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Resolved:
    """A reference resolved to its canonical public id (``D-0907``) or scoped code."""

    ref: str
    via: Literal["canonical", "tolerant", "alias", "foreign"] = "canonical"


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionInfo:
    """What any module may know about a decision: no basis, no text beyond the title."""

    public_id: str
    title: str
    kind: str
    status: str
    mirror_of: str | None
    mirror_scope: str | None
    current_edition: int
    review_due: date | None
    closed_at: datetime | None = None
    successor_ref: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionState:
    """A decision's computed state at a time: the composite label with both axes and reasons
    (§3.7)."""

    ref: str
    label: str
    ground: str | None
    timeliness: frozenset[str]
    reasons: tuple[str, ...]
    share: Decimal | None
    review_due: date | None
    bet: bool = False
    badge: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Reason:
    """One waiting reason, in structure and in words (§3.8).

    ``due`` is the date the reason is about (the due date, the violation's observed date, the goal's
    change date); ``code`` is the assumption code (``A-02``) or the goal ref for ``goal_changed``;
    ``critical`` is set for ``violated`` and ``check_due``; ``due_source`` is the source of a
    check's due date (``explicit``, ``by_date``, ``text``); ``status`` is the goal's status for
    ``goal_changed``. ``text`` is the rendered sentence, e.g. "A-02: check due 15 Nov, from its
    threshold date".
    """

    kind: WaitingKind
    due: date | None
    code: str | None = None
    critical: bool | None = None
    due_source: str | None = None
    status: str | None = None
    text: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class FactLine:
    """The last fact shown on a question card: code, text cut to 120 characters, age, evidence."""

    ref: str
    text: str
    occurred_at: date | datetime | None
    age_days: int | None
    evidence: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalLine:
    """A served or tested goal as the card shows it."""

    ref: str
    title: str | None
    status: str | None
    since: date | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AskedPart:
    """What the question asks about: an assumption with its threshold and due date, or the
    review."""

    kind: Literal["assumption", "review", "goal", "fork", "proposal", "incomplete"]
    ref: str
    statement: str | None = None
    threshold_text: str | None = None
    due: date | None = None
    due_source: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionContext:
    """The rule-built context of a waiting item (§3.9): never a waiting item without it.

    ``share_line`` is always first for decisions. ``likely_actions`` are button labels whose dates
    come from the same functions the writes use (AT-N11). ``execution`` maps a probe kind to its
    counts.
    """

    one_line: str
    share_line: str | None
    health: DecisionState | None
    reasons: tuple[Reason, ...]
    last_fact: FactLine | None
    passed: tuple[tuple[str, date], ...]
    goals: tuple[GoalLine, ...]
    asked: AskedPart | None
    execution: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    postponements_since_review: int = 0
    likely_actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class WaitingItem:
    """One entry of the waiting list (§3.8); reasons are sorted by kind rank, due date, code."""

    subject_kind: SubjectKind
    ref: str
    number: int
    title: str
    health: DecisionState | None
    reasons: tuple[Reason, ...]
    question_context: QuestionContext | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EntryContext:
    """What a spoke knows when it offers a decision at entry time (§3.14)."""

    kind: str
    text: str = ""
    person_refs: tuple[str, ...] = ()
    company_refs: tuple[str, ...] = ()
    goal_ref: str | None = None
    occasion_time: datetime | None = None
    reply_to_decision: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Offer:
    """A likely decision offered at entry; ``preselected`` only for a decision named by label."""

    ref: str
    reason: str
    preselected: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeItem:
    """An assumption a meeting or a live app may probe (§7.4) [LATER 3]."""

    decision_ref: str
    assumption_ref: str
    statement: str
    metric: str | None
    threshold_text: str | None
    due: date | None
    due_source: str | None
    violation_text: str | None = None
    question: str | None = None


@runtime_checkable
class DecisionDirectory(Protocol):
    """Read decisions and check attachments without importing DEC (spec §4.2)."""

    def resolve(self, text_or_ref: str) -> Resolved | Ambiguous | NotFound:
        """``D42``, ``D-0042``, ``V1_D42`` and aliases resolve to the canonical id."""
        ...

    def info(self, ref: str) -> DecisionInfo | None: ...

    def state(self, ref: str, as_of: datetime | None = None) -> DecisionState: ...

    def accepts_attachment(self, ref: str, attachment_kind: str) -> Accept | Refused:
        """§3.14: refuses a missing, ended or V1-mirrored decision, naming what to do instead."""
        ...

    def open_for(
        self, subjects: Sequence[str], *, kinds: Sequence[str] | None = None, limit: int = 10
    ) -> list[DecisionInfo]: ...

    def likely_for_entry(self, ctx: EntryContext) -> list[Offer]:
        """§3.14: at most three offers; a decision named by label beats a guess [I3]."""
        ...

    def waiting(self, today: date | None = None) -> list[WaitingItem]:
        """§3.8, each item with its question context."""
        ...

    def projection(self, ref: str, audience: str) -> dict[str, object]:
        """§4.4: ``owner`` or ``agent`` in the slice."""
        ...

    def assumptions_to_probe(self, subjects: Sequence[str], *, limit: int = 5) -> list[ProbeItem]:
        """§7.4 [LATER 3]."""
        ...
