"""A fake ``DecisionDirectory`` for spokes' suites (CMT in I3; WRK, MTG and others later)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from coflow.kernel.errors import Accept, Ambiguous, NotFound, RefusalCode, Refused
from coflow.kernel.ports.decision_directory import (
    DecisionInfo,
    DecisionState,
    EntryContext,
    Offer,
    ProbeItem,
    Resolved,
    WaitingItem,
)

ENDED = frozenset({"closed", "cancelled", "superseded", "withdrawn"})


@dataclass
class FakeDecisionDirectory:
    """Decisions by canonical id; ``aliases`` maps other input forms to canonical ids.

    ``accepts_attachment`` follows §3.14: a missing decision is ``NOT_FOUND``, a ``full`` mirror is
    ``MIRRORED``, an ended decision is ``DECISION_ENDED``; drafts and active decisions accept.
    """

    decisions: dict[str, DecisionInfo] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    states: dict[str, DecisionState] = field(default_factory=dict)
    waiting_items: list[WaitingItem] = field(default_factory=list)
    offers: list[Offer] = field(default_factory=list)
    probe_items: list[ProbeItem] = field(default_factory=list)
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def add(self, info: DecisionInfo, *aliases: str) -> None:
        self.decisions[info.public_id] = info
        for alias in aliases:
            self.aliases[alias] = info.public_id

    def resolve(self, text_or_ref: str) -> Resolved | Ambiguous | NotFound:
        self.calls.append(("resolve", (text_or_ref,)))
        if text_or_ref in self.decisions:
            return Resolved(ref=text_or_ref, via="canonical")
        if text_or_ref in self.aliases:
            return Resolved(ref=self.aliases[text_or_ref], via="alias")
        return NotFound(text_or_ref)

    def info(self, ref: str) -> DecisionInfo | None:
        self.calls.append(("info", (ref,)))
        return self.decisions.get(ref)

    def state(self, ref: str, as_of: datetime | None = None) -> DecisionState:
        self.calls.append(("state", (ref, as_of)))
        return self.states[ref]

    def accepts_attachment(self, ref: str, attachment_kind: str) -> Accept | Refused:
        self.calls.append(("accepts_attachment", (ref, attachment_kind)))
        d = self.decisions.get(ref)
        if d is None:
            return Refused(RefusalCode.NOT_FOUND, f"{ref} not found")
        if d.mirror_scope == "full":
            return Refused(
                RefusalCode.MIRRORED,
                "record it in the system of record of this decision until adoption",
            )
        if d.status in ENDED:
            hint = d.successor_ref or "another decision"
            return Refused(RefusalCode.DECISION_ENDED, f"link to {hint} or choose none")
        return Accept()

    def open_for(
        self, subjects: Sequence[str], *, kinds: Sequence[str] | None = None, limit: int = 10
    ) -> list[DecisionInfo]:
        self.calls.append(("open_for", (tuple(subjects), kinds, limit)))
        found = [d for d in self.decisions.values() if d.status == "active"]
        if kinds is not None:
            found = [d for d in found if d.kind in kinds]
        return found[:limit]

    def likely_for_entry(self, ctx: EntryContext) -> list[Offer]:
        self.calls.append(("likely_for_entry", (ctx,)))
        return self.offers[:3]

    def waiting(self, today: date | None = None) -> list[WaitingItem]:
        self.calls.append(("waiting", (today,)))
        return list(self.waiting_items)

    def projection(self, ref: str, audience: str) -> dict[str, object]:
        self.calls.append(("projection", (ref, audience)))
        d = self.decisions[ref]
        return {"public_id": d.public_id, "title": d.title, "status": d.status}

    def assumptions_to_probe(self, subjects: Sequence[str], *, limit: int = 5) -> list[ProbeItem]:
        self.calls.append(("assumptions_to_probe", (tuple(subjects), limit)))
        return self.probe_items[:limit]
