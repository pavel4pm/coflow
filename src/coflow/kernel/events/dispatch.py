"""In-process dispatch after commit: one delivery per declared handler, tracked in
``sys_event_deliveries``, idempotent by (event id, handler) (ARCHITECTURE §6.2).

Owned by track K (kernel); increment I1, spec §12.2.

A ``Dispatcher`` holds the declared handlers (name, event types, data classes, function). Attached
to a store, it runs after every unit that published events has committed, outside the writer:

1. each event is read back from ``sys_events`` (ids and field names only);
2. every handler that declared the event's type and data class is called once, outside any unit
   (it may open its own units of work);
3. the outcome is recorded in an ``evt`` unit: ``delivered``, or ``failed`` with the error's type
   name (never its message, which could hold a value); after ``max_attempts`` failures the delivery
   is ``dead`` (the dead letter the status page shows from 0B).

``deliver_pending`` retries failed deliveries and catches up events committed while no dispatcher
was attached. A delivered (event, handler) pair is never delivered again.

Spec notes: only POL and OBS may declare the journal class (ARCHITECTURE §6.2). Back-off timing and
the 30-day pruning of delivered events arrive with the scheduler (0B); the slice declares no
consumers that exist yet, so the composition root attaches a dispatcher with no handlers.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from coflow.kernel.context import CommandContext, format_instant
from coflow.kernel.errors import ContractViolation
from coflow.kernel.events.publish import EVENT_TYPE
from coflow.kernel.store.db import SqliteStore
from coflow.kernel.store.registry import DATA_CLASSES

__all__ = ["DeliveryReport", "Dispatcher", "Event", "Handler", "load_events"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """A stored event as handlers see it: the envelope, with ``data`` split into its two members."""

    id: str
    type: str
    source: str
    subject: str
    time: str
    dataversion: int
    correlation_id: str
    causation_id: str | None
    actor: str
    data_class: str
    source_ref: str | None
    entity: str
    changed: tuple[str, ...]
    tx: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Handler:
    name: str  # "<mod>.<what>", e.g. "obs.count_imports"
    types: frozenset[str]  # exact types, or "coflow.dec.*"-style prefixes ending in "*"
    classes: frozenset[str]
    fn: Callable[[Event], None]

    def wants(self, event: Event) -> bool:
        if event.data_class not in self.classes:
            return False
        for pattern in self.types:
            if pattern.endswith("*") and event.type.startswith(pattern[:-1]):
                return True
            if pattern == event.type:
                return True
        return False


@dataclass(slots=True)
class DeliveryReport:
    delivered: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    dead: list[tuple[str, str]] = field(default_factory=list)


_COLUMNS = (
    "id, type, source, subject, time, dataversion, correlationid, causationid, actor, dataclass,"
    " sourceref, data, tx"
)


def _event(row: sqlite3.Row) -> Event:
    data = json.loads(str(row["data"]))
    return Event(
        id=str(row["id"]),
        type=str(row["type"]),
        source=str(row["source"]),
        subject=str(row["subject"]),
        time=str(row["time"]),
        dataversion=int(row["dataversion"]),
        correlation_id=str(row["correlationid"]),
        causation_id=None if row["causationid"] is None else str(row["causationid"]),
        actor=str(row["actor"]),
        data_class=str(row["dataclass"]),
        source_ref=None if row["sourceref"] is None else str(row["sourceref"]),
        entity=str(data["entity"]),
        changed=tuple(str(c) for c in data["changed"]),
        tx=int(row["tx"]),
    )


def load_events(conn: sqlite3.Connection, ids: Sequence[str] | None = None) -> list[Event]:
    """Events by id (in commit order), or every event when ``ids`` is None."""
    if ids is None:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM sys_events ORDER BY tx, id").fetchall()
    else:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM sys_events WHERE id IN ({marks}) ORDER BY tx, id", tuple(ids)
        ).fetchall()
    return [_event(r) for r in rows]


class Dispatcher:
    """The declared handlers of one process and their delivery bookkeeping."""

    def __init__(self, *, max_attempts: int = 3) -> None:
        self._handlers: dict[str, Handler] = {}
        self.max_attempts = max_attempts
        self._store: SqliteStore | None = None

    @property
    def handlers(self) -> tuple[Handler, ...]:
        return tuple(self._handlers.values())

    def register(
        self,
        name: str,
        *,
        types: Iterable[str],
        classes: Iterable[str],
        fn: Callable[[Event], None],
    ) -> Handler:
        if name in self._handlers:
            raise ContractViolation(f"handler {name!r} is already registered")
        declared = frozenset(classes)
        unknown = declared - set(DATA_CLASSES)
        if unknown or not declared:
            raise ContractViolation(f"handler {name!r} declares unknown classes {sorted(unknown)}")
        if "journal" in declared and name.split(".")[0] not in ("pol", "obs"):
            raise ContractViolation("only POL and OBS handlers receive journal-class events")
        wanted = frozenset(types)
        for pattern in wanted:
            if not (pattern.endswith("*") or EVENT_TYPE.match(pattern)):
                raise ContractViolation(f"handler {name!r}: bad event type {pattern!r}")
        handler = Handler(name=name, types=wanted, classes=declared, fn=fn)
        self._handlers[name] = handler
        return handler

    def attach(self, store: SqliteStore) -> None:
        """Deliver after every commit of ``store`` that published events."""
        self._store = store
        store.add_after_commit(self._after_commit)

    def _after_commit(self, tx: int, event_ids: tuple[str, ...]) -> None:
        if event_ids and self._store is not None:
            self.deliver(self._store, event_ids)

    def _ctx(self, event: Event) -> CommandContext:
        return CommandContext(
            actor="system",
            channel="system",
            owner_channel=False,
            interaction_id=f"dispatch-{event.id}",
        )

    def deliver(self, store: SqliteStore, event_ids: Sequence[str]) -> DeliveryReport:
        """Deliver the given events to every handler that declared them and is not done yet."""
        report = DeliveryReport()
        if not self._handlers:
            return report
        with store.read_connection() as conn:
            events = load_events(conn, list(event_ids))
            done = {
                (str(r["event_id"]), str(r["handler"])): (str(r["status"]), int(r["attempts"]))
                for r in conn.execute(
                    "SELECT event_id, handler, status, attempts FROM sys_event_deliveries"
                ).fetchall()
            }
        for event in events:
            for handler in self._handlers.values():
                if not handler.wants(event):
                    continue
                status, attempts = done.get((event.id, handler.name), ("", 0))
                if status in ("delivered", "dead"):
                    continue
                self._deliver_one(store, event, handler, attempts, report)
        return report

    def deliver_pending(self, store: SqliteStore) -> DeliveryReport:
        """Catch up: every stored event not yet delivered (or failed) to a declared handler."""
        with store.read_connection() as conn:
            ids = [str(r[0]) for r in conn.execute("SELECT id FROM sys_events ORDER BY tx, id")]
        return self.deliver(store, ids)

    def _deliver_one(
        self,
        store: SqliteStore,
        event: Event,
        handler: Handler,
        attempts: int,
        report: DeliveryReport,
    ) -> None:
        error: str | None = None
        try:
            handler.fn(event)
        except Exception as exc:
            error = type(exc).__name__
        attempts += 1
        if error is None:
            status = "delivered"
            report.delivered.append((event.id, handler.name))
        elif attempts >= self.max_attempts:
            status = "dead"
            report.dead.append((event.id, handler.name))
        else:
            status = "failed"
            report.failed.append((event.id, handler.name))
        with store.unit_of_work("evt", self._ctx(event), command="deliver") as unit:
            delivered_at = format_instant(unit.committed_at) if error is None else None
            key = {"event_id": event.id, "handler": handler.name}
            if attempts == 1:
                unit.insert(
                    "sys_event_deliveries",
                    {
                        **key,
                        "status": status,
                        "attempts": attempts,
                        "last_error": error,
                        "delivered_at": delivered_at,
                    },
                )
            else:
                unit.update_mutable(
                    "sys_event_deliveries",
                    key,
                    status=status,
                    attempts=attempts,
                    last_error=error,
                    delivered_at=delivered_at,
                )
