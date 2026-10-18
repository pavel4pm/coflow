"""``publish``: write an event in the current unit of work (ARCHITECTURE §6.2, spec §4.6).

Owned by track K; increment I1, spec §12.2. The signature is fixed by the skeleton because track S
publishes ``coflow.dec.decision.imported``, ``coflow.dec.edition.sealed`` and
``coflow.dec.import.completed``; the track implements it.

The envelope is CloudEvents-compatible: ``id`` (UUIDv7, its random part from ``new_salt``),
``type`` (``coflow.<mod>.<entity>.<verb_past>``), ``source`` (``coflow://<instance_id>/<mod>``),
``subject`` (a plain public id or ``<ISSUER>_<id>``, never a ``coflow:`` form), ``time``,
``dataversion`` (1), ``correlationid`` (the interaction id), ``causationid``, ``actor``,
``dataclass``, ``sourceref`` and ``data`` = ``{"entity", "changed"}``: field names, never values.

What ``publish`` refuses (``ContractViolation``, AT-K6): a type of another module than the unit's
owner; a subject or source ref that is not id-shaped (letters, digits, ``-`` and ``_`` only: a
public id, an ``<ISSUER>_<id>`` ref or a run number); a ``changed`` entry that is not a field name
(``statement``, ``next_check_at``), which is how a value would leak into a payload; a
``correlationid`` (the interaction id) or ``actor`` that is not id-shaped (found in review: both
were copied from the context unchecked, and an interaction id can come from a client header).

Spec notes: ``time`` is the unit's instant (every event of a unit carries the same time, which is
also its rows' ``recorded_at``); ``sourceref`` defaults to the context's ``source_ref``; the
UUIDv7 ordering counter is the event's position inside its unit.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from coflow.kernel.context import ID_SHAPE, format_instant, new_salt
from coflow.kernel.errors import ContractViolation
from coflow.kernel.store.api import current_unit
from coflow.kernel.store.registry import DATA_CLASSES
from coflow.kernel.store.unit import Unit

__all__ = [
    "DATAVERSION",
    "ENVELOPE_FIELDS",
    "EVENT_TYPE",
    "envelope_problems",
    "event_data",
    "publish",
    "uuid7",
]

DATAVERSION = 1
EVENT_TYPE = re.compile(r"^coflow\.([a-z][a-z0-9]*)\.([a-z][a-z_]*)\.([a-z][a-z_]*)$")
FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ENVELOPE_FIELDS: tuple[str, ...] = (
    "id",
    "type",
    "source",
    "subject",
    "time",
    "dataversion",
    "correlationid",
    "causationid",
    "actor",
    "dataclass",
    "sourceref",
    "data",
)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def uuid7(at: datetime, counter: int) -> str:
    """A UUIDv7: 48 bits of Unix milliseconds, a 12-bit counter, 62 random bits (``new_salt``)."""
    ms = (at - _EPOCH) // timedelta(milliseconds=1)
    rand = int(new_salt(), 16) & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | (counter & 0xFFF) << 64 | 0b10 << 62 | rand
    return str(uuid.UUID(int=value))


def event_data(entity: str, changed: Sequence[str]) -> str:
    """The ``data`` member in CFJ-1 form: ``{"changed": [...], "entity": "..."}``."""
    if not FIELD_NAME.match(entity):
        raise ContractViolation(f"entity must be a type name, not {entity!r}")
    names: list[str] = []
    for name in changed:
        if not isinstance(name, str) or not FIELD_NAME.match(name):
            raise ContractViolation(
                f"changed holds field names only, not {name!r}: an event never carries a value"
            )
        if name not in names:
            names.append(name)
    body = {"changed": names, "entity": entity}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def envelope_problems(row: Mapping[str, Any]) -> list[str]:
    """Why a stored event row breaks the envelope schema (empty when it holds). The schema scan
    of AT-K6 runs this over every row of ``sys_events``."""
    problems: list[str] = []
    for key in ENVELOPE_FIELDS:
        if key not in row:
            problems.append(f"missing {key}")
    m = EVENT_TYPE.match(str(row.get("type", "")))
    if m is None:
        problems.append(f"type {row.get('type')!r}")
    source = str(row.get("source", ""))
    if m is not None and not re.match(rf"^coflow://[A-Za-z0-9-]+/{m.group(1)}$", source):
        problems.append(f"source {source!r}")
    if not ID_SHAPE.match(str(row.get("subject", ""))):
        problems.append("subject is not id-shaped")
    sourceref = row.get("sourceref")
    if sourceref is not None and not ID_SHAPE.match(str(sourceref)):
        problems.append("sourceref is not id-shaped")
    for key in ("correlationid", "actor"):
        if not ID_SHAPE.match(str(row.get(key, ""))):
            problems.append(f"{key} is not id-shaped")
    causation = row.get("causationid")
    if causation is not None and not ID_SHAPE.match(str(causation)):
        problems.append("causationid is not id-shaped")
    if row.get("dataclass") not in DATA_CLASSES:
        problems.append(f"dataclass {row.get('dataclass')!r}")
    try:
        data = json.loads(str(row.get("data", "")))
    except ValueError:
        problems.append("data is not JSON")
        return problems
    if not isinstance(data, dict) or set(data) != {"entity", "changed"}:
        problems.append("data holds keys other than entity and changed")
        return problems
    if not isinstance(data["entity"], str) or not FIELD_NAME.match(data["entity"]):
        problems.append("data.entity is not a type name")
    if not isinstance(data["changed"], list) or not all(
        isinstance(c, str) and FIELD_NAME.match(c) for c in data["changed"]
    ):
        problems.append("data.changed holds something other than field names")
    return problems


def publish(
    type: str,
    *,
    subject: str,
    entity: str,
    changed: Sequence[str],
    data_class: str = "work",
    source_ref: str | None = None,
    causation_id: str | None = None,
) -> str:
    """Store one event row in the current unit of work and return its id.

    It commits if and only if the unit commits. ``changed`` holds field names only; a value-shaped
    entry is a ``ContractViolation`` (AT-K6).
    """
    unit = current_unit()
    if not isinstance(unit, Unit):
        raise ContractViolation("events are published inside a kernel unit of work")
    m = EVENT_TYPE.match(type)
    if m is None:
        raise ContractViolation(f"event type {type!r} is not coflow.<mod>.<entity>.<verb_past>")
    module = m.group(1)
    if module != unit.owner_module:
        raise ContractViolation(f"a unit of {unit.owner_module!r} cannot publish {type}")
    if isinstance(changed, str):
        raise ContractViolation("changed is a sequence of field names, not one string")
    if not ID_SHAPE.match(subject) or len(subject) > 80:
        raise ContractViolation(f"subject must be a public id or <ISSUER>_<id>, not {subject!r}")
    ref = source_ref if source_ref is not None else unit.ctx.source_ref
    if ref is not None and (not ID_SHAPE.match(ref) or len(ref) > 120):
        raise ContractViolation(f"sourceref must be an id, not {ref!r}")
    if causation_id is not None and not ID_SHAPE.match(causation_id):
        raise ContractViolation(f"causationid must be an id, not {causation_id!r}")
    for name, value in (("correlationid", unit.ctx.interaction_id), ("actor", unit.ctx.actor)):
        if not ID_SHAPE.match(value) or len(value) > 120:
            raise ContractViolation(f"{name} must be id-shaped")  # the value is never echoed
    if data_class not in DATA_CLASSES:
        raise ContractViolation(f"unknown data class {data_class!r}")
    data = event_data(entity, changed)
    event_id = uuid7(unit.committed_at, unit.next_event_position())
    unit.kernel_insert(
        "sys_events",
        {
            "id": event_id,
            "type": type,
            "source": f"coflow://{unit.instance_id}/{module}",
            "subject": subject,
            "time": format_instant(unit.committed_at),
            "dataversion": DATAVERSION,
            "correlationid": unit.ctx.interaction_id,
            "causationid": causation_id,
            "actor": unit.ctx.actor,
            "dataclass": data_class,
            "sourceref": ref,
            "data": data,
        },
    )
    unit.record_event(event_id)
    return event_id
