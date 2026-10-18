"""Fakes for the interface layer (track X): a synthetic DEC read side and in-memory core services.

Everything here is invented for the fixture world of spec §9.1: the owner "Owner" in
``Europe/Berlin``, today 2026-11-15, V1 mirrors D-0903 to D-0910, the goal ``V1_G901`` "Cut fixed
costs" dropped on 2026-11-05, and one native decision from the reserved block (D-1001).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from coflow.interfaces.admin.api import Services
from coflow.interfaces.mcp.auth import (
    ClientIdentity,
    IssuedToken,
    TokenScope,
    hash_token,
    new_token,
    scopes_for,
)
from coflow.kernel.context import Answer, CommandContext, CommandResult, FakeClock
from coflow.kernel.errors import NotFound, RefusalCode, Refused
from coflow.kernel.ports.decision_directory import DecisionInfo
from coflow.modules.dec.api import model

NOW = datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
TODAY = date(2026, 11, 15)
TZ = "Europe/Berlin"
ROLE = "dev"
STAMP = {"tx": 1, "recorded_at": datetime(2026, 11, 14, 6, 0, tzinfo=UTC)}

# --------------------------------------------------------------------------------------------------
# Views


def decision(number: int, title: str, **overrides: Any) -> model.DecisionView:
    public_id = f"D-{number:04d}"
    mirror = number < 1001
    base: dict[str, Any] = {
        **STAMP,
        "id": number,
        "public_id": public_id,
        "number": number,
        "title": title,
        "question": None,
        "statement": f"{title}, as decided",
        "kind": "choice",
        "decider": "self",
        "decider_basis": "stated",
        "decider_ref": None,
        "depth": "full",
        "depth_basis": "import" if mirror else "owner",
        "reversibility": "unknown",
        "status": "active",
        "manual_flag": None,
        "manual_flag_reason": None,
        "context": None,
        "known": None,
        "would_help": None,
        "unknowns": (),
        "success_criterion": None,
        "expected_metric": None,
        "expected_target": None,
        "expected_unit": None,
        "expected_by": None,
        "expected_text": None,
        "confidence": None,
        "not_doing": None,
        "review_due": date(2026, 11, 10),
        "review_due_initial": date(2026, 11, 10),
        "decided_at": date(2026, 11, 2),
        "decided_precision": "day",
        "decided_basis": "import" if mirror else "stated",
        "activated_at": None,
        "closed_at": None,
        "current_edition": 1,
        "completion_pending": False,
        "origin_kind": "import" if mirror else "cli",
        "origin_quote": None,
        "publishability": "private",
        "third_party_sensitive": False,
        "reconstructed": mirror,
        "mirror_of": f"V1_D{number}" if mirror else None,
        "mirror_scope": "full" if mirror else None,
        "notes": None,
        "legacy_json": '{"secret":"never shown"}',
        "version": 1,
    }
    base.update(overrides)
    return model.DecisionView(**base)


def assumption(
    d: model.DecisionView, n: int, statement: str, **overrides: Any
) -> model.AssumptionView:
    code = f"A-{n:02d}"
    base: dict[str, Any] = {
        **STAMP,
        "id": d.id * 100 + n,
        "decision_id": d.id,
        "code_n": n,
        "code": code,
        "ref": f"{d.public_id}_{code}",
        "position": n,
        "statement": statement,
        "metric": "signed contracts",
        "comparator": ">=",
        "threshold_value": "3",
        "threshold_value2": None,
        "unit": "signed",
        "threshold_text": None,
        "by_date": date(2026, 11, 20),
        "judge_from": None,
        "drift_margin": None,
        "data_source_kind": "manual",
        "data_source_text": None,
        "data_source_ref": None,
        "check_frequency": "weekly",
        "next_check_at": None,
        "is_critical": True,
        "scope": None,
        "check_cost": None,
        "class_tag": "demand",
        "probability": None,
        "probability_by": None,
        "probability_recorded_at": None,
        "shareable": False,
        "status": "active",
        "superseded_by": None,
        "drop_reason": None,
        "added_in_edition": 1,
        "salt": "00" * 16,
        "version": 1,
    }
    base.update(overrides)
    return model.AssumptionView(**base)


def fact(d: model.DecisionView, n: int, text: str, **overrides: Any) -> model.FactView:
    code = f"FT-{n:03d}"
    base: dict[str, Any] = {
        **STAMP,
        "id": d.id * 1000 + n,
        "decision_id": d.id,
        "code_n": n,
        "code": code,
        "ref": f"{d.public_id}_{code}",
        "phase": "monitoring",
        "kind": "observation",
        "claimed_outcome": None,
        "text": text,
        "occurred_at": date(2026, 11, 12),
        "occurred_precision": "day",
        "occurred_basis": "import",
        "evidence_kind": "none",
        "evidence_ref": None,
        "evidence_quote": None,
        "quote_verified": None,
        "source_text": None,
        "reported_by": "owner",
        "added_in_edition": None,
        "corrects_fact_id": None,
        "salt": "11" * 16,
        "reconstructed": True,
    }
    base.update(overrides)
    return model.FactView(**base)


def stake(d: model.DecisionView, amount: str) -> model.StakeView:
    return model.StakeView(
        **STAMP,
        id=d.id,
        decision_id=d.id,
        type="money",
        amount=amount,
        currency="EUR",
        period="month",
        count_periods=6,
        direction="cost",
        note=None,
        planned=True,
        added_in_edition=1,
        salt="22" * 16,
    )


def state(ref: str, label: str, *reasons: str) -> model.DecisionState:
    return model.DecisionState(
        ref=ref,
        label=label,
        ground="HOLDING",
        timeliness=frozenset({"REVIEW_OVERDUE"}) if label == "REVIEW_REQUIRED" else frozenset(),
        reasons=reasons,
        share=Decimal("0.5"),
        review_due=date(2026, 11, 10),
    )


def reason(kind: model.WaitingKind, text: str, due: date | None, **kw: Any) -> model.Reason:
    return model.Reason(kind=kind, due=due, text=text, **kw)


def question(one_line: str, *actions: str, **kw: Any) -> model.QuestionContext:
    return model.QuestionContext(
        one_line=one_line,
        share_line=kw.pop("share_line", "1 of 2 assumptions cannot be checked (50 %)"),
        health=kw.pop("health", None),
        reasons=kw.pop("reasons", ()),
        last_fact=kw.pop("last_fact", None),
        passed=kw.pop("passed", ()),
        goals=kw.pop("goals", ()),
        asked=kw.pop("asked", None),
        likely_actions=actions,
        **kw,
    )


def waiting_item(
    number: int, title: str, label: str, *reasons: model.Reason, actions: tuple[str, ...] = ()
) -> model.WaitingItem:
    ref = f"D-{number:04d}"
    return model.WaitingItem(
        subject_kind="decision",
        ref=ref,
        number=number,
        title=title,
        health=state(ref, label, *(r.text for r in reasons)),
        reasons=reasons,
        question_context=question(f"{ref}: {title}", *actions, reasons=reasons),
    )


def standard_items() -> list[model.WaitingItem]:
    """The waiting list of the fixture world, in rank order (a violation first)."""
    return [
        waiting_item(
            905,
            "Rent a second workshop room",
            "OFF_TRACK",
            reason(
                "violated",
                "A-02 violated on 2026-11-12 (not critical)",
                date(2026, 11, 12),
                code="A-02",
                critical=False,
            ),
            actions=("review now", "add a fact"),
        ),
        waiting_item(
            904,
            "Move the bookkeeping to monthly",
            "REVIEW_REQUIRED",
            reason("review_overdue", "Review date passed on 2026-11-10", date(2026, 11, 10)),
            actions=("close", "cancel", "keep until 2026-12-15"),
        ),
        waiting_item(
            906,
            "Pause the newsletter",
            "WATCH",
            reason(
                "goal_changed",
                "Goal V1_G901 Cut fixed costs was dropped on 2026-11-05",
                date(2026, 11, 5),
                code="V1_G901",
                status="dropped",
            ),
            reason("review_today", "Review is due today", TODAY),
            actions=("review now",),
        ),
        waiting_item(
            1001,
            "Adopt a weekly release train",
            "AWAITING_CHECKS",
            reason(
                "check_due",
                "A-01: check due 2026-11-15, from its threshold date",
                TODAY,
                code="A-01",
                critical=True,
                due_source="by_date",
            ),
            actions=("check A-01: holding", "check A-01: violated", "postpone"),
        ),
    ]


def standard_lines() -> list[model.DecisionLine]:
    titles = {
        903: "Close the old storage unit",
        904: "Move the bookkeeping to monthly",
        905: "Rent a second workshop room",
        906: "Pause the newsletter",
        1001: "Adopt a weekly release train",
    }
    return [
        model.DecisionLine(
            public_id=f"D-{n:04d}",
            title=t,
            status="active",
            kind="choice",
            label="WATCH",
            share=Decimal("0.5"),
            review_due=date(2026, 11, 10),
            first_reason=None,
            mirror_of=f"V1_D{n}" if n < 1001 else None,
        )
        for n, t in titles.items()
    ]


def context_for(ref: str, *, audience: model.Audience) -> model.DecisionContext:
    number = int(ref.split("-")[1])
    d = decision(number, "Rent a second workshop room")
    a1 = assumption(d, 1, "Two workshops a month fill the room")
    a2 = assumption(d, 2, "The landlord keeps the price", data_source_kind="none")
    f1 = fact(
        d,
        1,
        "The landlord asked for one more week",
        bearings=(model.FactBearing(assumption_id=a2.id, bearing="bears_on"),),
    )
    d = replace(d, assumptions=(a1, a2), facts=(f1,), stakes=(stake(d, "450"),))
    health = model.HealthResult(
        label="OFF_TRACK",
        ground="VIOLATED",
        timeliness=frozenset({"REVIEW_OVERDUE"}),
        reasons=(
            model.HealthReason(
                axis="ground", kind="VIOLATED", text="A-02 is violated", code="A-02"
            ),
            model.HealthReason(
                axis="timeliness",
                kind="REVIEW_OVERDUE",
                text="Review date passed",
                day=date(2026, 11, 10),
                source="review",
            ),
        ),
        share=Decimal("0.5"),
        bet=False,
        states={"A-01": "HOLDING", "A-02": "VIOLATED"},
        pool=("A-01", "A-02"),
    )
    cards = (
        model.AssumptionCard(
            assumption=a1,
            state="HOLDING",
            due=model.DueResult(due=date(2026, 11, 20), source="by_date"),
            last_check=None,
        ),
        model.AssumptionCard(
            assumption=a2,
            state="VIOLATED",
            due=model.DueResult(due=None, source=None),
            last_check=None,
        ),
    )
    return model.DecisionContext(
        decision=d,
        integrity_line=None,
        share_line="1 of 2 assumptions cannot be checked (50 %)",
        health=health,
        waiting_reasons=standard_items()[0].reasons,
        question_context=standard_items()[0].question_context,
        assumptions=cards,
        ground_facts=(),
        monitoring_facts=(f1,),
        reviews=(),
        outcome=None,
        learnings=(),
        editions=(model.IntegrityLine(edition=1, status="ok", seal12="0123456789ab"),),
        links=(),
        mirror_line=(
            "mirrored from V1, snapshot exported at 2026-11-14T06:00:00.000Z; read-only here"
        ),
        detail="brief",
        audience=audience,
    )


# --------------------------------------------------------------------------------------------------
# The DEC read side


def _answer(value: Any, *, role: str, coverage: tuple[str, ...] = ()) -> Answer[Any]:
    return Answer(value=value, instance_role=role, as_of=NOW, coverage=coverage)


@dataclass
class FakeDecService:
    """A ``DecService`` over canned answers; records every call."""

    items: list[model.WaitingItem] = field(default_factory=standard_items)
    lines: list[model.DecisionLine] = field(default_factory=standard_lines)
    calls: list[tuple[str, Mapping[str, Any]]] = field(default_factory=list)
    import_report: model.ImportReport | None = None
    role: str = ROLE

    def waiting(self, *, today: date | None = None) -> Answer[list[model.WaitingItem]]:
        self.calls.append(("waiting", {"today": today}))
        return _answer(
            list(self.items),
            role=self.role,
            coverage=("mirrored from V1, snapshot exported at 2026-11-14T06:00:00.000Z",),
        )

    def decision_context(self, ref: str, **kw: Any) -> Answer[model.DecisionContext]:
        self.calls.append(("decision_context", {"ref": ref, **kw}))
        canonical = {"D905": "D-0905", "V1_D905": "D-0905", "D-0905": "D-0905"}.get(ref)
        if canonical is None:
            raise NotFound(ref)
        return _answer(context_for(canonical, audience=kw.get("audience", "owner")), role=self.role)

    def list_decisions(self, **kw: Any) -> Answer[list[model.DecisionLine]]:
        self.calls.append(("list_decisions", kw))
        lines = self.lines
        if kw.get("mirror"):
            lines = [x for x in lines if x.mirror_of and x.mirror_of.startswith(kw["mirror"] + "_")]
        return _answer(list(lines)[: kw.get("limit", 50)], role=self.role)

    def integrity(self, ref: str) -> Answer[list[model.IntegrityReport]]:
        self.calls.append(("integrity", {"ref": ref}))
        report = model.IntegrityReport(
            decision_ref="D-0905",
            lines=(
                model.IntegrityLine(edition=1, status="ok", seal12="0123456789ab"),
                model.IntegrityLine(edition="live", status="drift", items=("statement",)),
            ),
        )
        return _answer([report], role=self.role)

    def shadow_report(self, *, run_id: int | None = None) -> Answer[model.ShadowReport]:
        self.calls.append(("shadow_report", {"run_id": run_id}))
        unexpected = model.ShadowItem(
            decision_ref="D-0904",
            aspect="due",
            subject_ref="D-0904_A-01",
            v1_value="2026-11-20",
            v2_value="2026-11-18",
            classification="unexpected",
        )
        report = model.ShadowReport(
            run_id=run_id or 3,
            as_of_date=date(2026, 11, 14),
            report_status="written",
            totals={"same": 40, "expected": 3, "unexpected": 1, "finding": 0},
            by_rule={"SR-2": 2, "SR-5": 1},
            unexpected=(unexpected,),
            findings=(),
            items=(unexpected,),
            runs_since_last_unexpected=0,
        )
        return _answer(report, role=self.role)

    def decision_info(self, ref: str) -> DecisionInfo | None:
        self.calls.append(("decision_info", {"ref": ref}))
        if ref != "D-0905":
            return None
        return DecisionInfo(
            public_id="D-0905",
            title="Rent a second workshop room",
            kind="choice",
            status="active",
            mirror_of="V1_D905",
            mirror_scope="full",
            current_edition=1,
            review_due=date(2026, 11, 10),
        )

    def import_snapshot(
        self, file: Path, *, mode: model.ImportMode, ctx: CommandContext
    ) -> CommandResult[model.ImportReport]:
        self.calls.append(("import_snapshot", {"file": file, "mode": mode, "ctx": ctx}))
        if self.role == "dev" and "real" in file.name:
            raise Refused(
                RefusalCode.IMPORT_NOT_SYNTHETIC, "a dev instance imports synthetic files only"
            )
        report = self.import_report or model.ImportReport(
            run_id=1,
            status="applied",
            mode=mode,
            file_hash="sha256:" + "ab" * 32,
            source_issuer="V1",
            synthetic=True,
            exported_at=NOW,
            as_of=NOW,
            as_of_date=TODAY,
            counts={"decisions": model.EntityCounts(seen=8, new=8)},
        )
        return CommandResult(value=report, tx=7, event_ids=("e1", "e2"))


# --------------------------------------------------------------------------------------------------
# Core services


@dataclass
class FakeFacts:
    role_name: str = ROLE
    tz: str = TZ

    def role(self) -> str:
        return self.role_name

    def timezone(self) -> str:
        return self.tz


@dataclass
class RecordingUsage:
    rows: list[tuple[str, str, Mapping[str, str]]] = field(default_factory=list)

    def record(self, signal: str, *, ctx: CommandContext, detail: Mapping[str, str]) -> None:
        self.rows.append((signal, ctx.channel, dict(detail)))


@dataclass
class MemoryClients:
    clients: dict[str, tuple[str, frozenset[str], bool]] = field(default_factory=dict)
    contexts: list[CommandContext] = field(default_factory=list)

    def issue(
        self, client: str, *, scope: TokenScope, financial: bool, ctx: CommandContext
    ) -> IssuedToken:
        if not client or client.upper() == client:
            raise ValueError(f"client name {client!r}: use lower-case letters")
        self.contexts.append(ctx)
        token = new_token()
        replaced = client in self.clients
        self.clients[client] = (hash_token(token), scopes_for(scope), financial)
        return IssuedToken(
            client=client, scope=scope, financial=financial, token=token, replaced=replaced
        )

    def verify(self, token: str) -> ClientIdentity | None:
        digest = hash_token(token)
        for client, (stored, scopes, financial) in self.clients.items():
            if stored == digest:
                return ClientIdentity(client=client, scopes=scopes, financial=financial)
        return None


@dataclass
class MemoryCallLog:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def log(
        self,
        identity: ClientIdentity,
        *,
        tool: str,
        arguments: Mapping[str, object] | None,
        result_kind: str,
        interaction_id: str,
    ) -> None:
        self.rows.append(
            {
                "client": identity.client,
                "tool": tool,
                "arguments": dict(arguments or {}),
                "result_kind": result_kind,
                "interaction_id": interaction_id,
            }
        )


@dataclass
class MemoryAdminTokens:
    issued: dict[str, str] = field(default_factory=dict)
    revoked: bool = False

    def issue(self, scope: Any, *, ctx: CommandContext) -> str:
        token = new_token("cfa_")
        self.issued[hash_token(token)] = scope
        return token

    def verify(self, token: str) -> Any:
        return None if self.revoked else self.issued.get(hash_token(token))

    def revoke_issued(self, *, ctx: CommandContext) -> None:
        self.revoked = True


def make_services(
    data_root: Path, *, dec: FakeDecService | None = None, role: str = ROLE
) -> Services:
    return Services(
        dec=dec or FakeDecService(role=role),
        facts=FakeFacts(role_name=role),
        usage=RecordingUsage(),
        clients=MemoryClients(),
        call_log=MemoryCallLog(),
        admin_tokens=MemoryAdminTokens(),
        clock=FakeClock(NOW),
        data_root=data_root,
    )


@dataclass
class FakeLauncher:
    """A ``CoreLauncher`` over one ``Services``; ``refuse`` makes ``open`` raise it."""

    services: Services
    opened: int = 0
    served: list[tuple[Path, int]] = field(default_factory=list)
    refuse: Exception | None = None

    @contextmanager
    def open(self, data_root: Path) -> Iterator[Services]:
        if self.refuse is not None:
            raise self.refuse
        self.opened += 1
        yield self.services

    def serve(self, data_root: Path, *, port: int) -> int:
        self.served.append((data_root, port))
        return 0
