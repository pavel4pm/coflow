"""Interaction context, clocks, time conventions and the one source of randomness.

Skeleton file (spec §12.1): every track codes against it; a change is a reviewed skeleton pull
request. It is the leaf of the kernel and imports only the standard library.

Conventions (spec §2.1, §12.5):

- An *instant* is a timezone-aware ``datetime`` in UTC. It is stored as ISO 8601 text with
  milliseconds and ``Z`` (``format_instant``), for example ``2026-11-15T09:30:00.000Z``.
- A *local date* is computed in the owner's IANA zone, never the host's (``local_date``).
- There is no wall-clock call outside a ``Clock`` and no randomness outside ``new_salt()``; ruff's
  banned-API rule (TID251) enforces both everywhere except this file.

Spec note: ``CommandContext`` carries ``approval_ref`` in addition to the seven fields of §12.1,
because ``sys_tx_log.approval_ref`` (§2.3) must come from the context and STO stamps it, never the
caller. ``new_salt`` lives here (not in the decision domain) so that every module and EVT draw
randomness from one function; ``modules/dec/domain/cfj.py`` re-exports it as in §3.3.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

__all__ = [
    "CHANNELS",
    "ID_SHAPE",
    "NON_OWNER_CHANNELS",
    "Answer",
    "Axis",
    "Channel",
    "Clock",
    "CommandContext",
    "CommandResult",
    "EvalTime",
    "FakeClock",
    "SystemClock",
    "derive_idempotency_key",
    "end_of_local_day",
    "format_instant",
    "local_date",
    "new_salt",
    "parse_instant",
    "seeded_salts",
    "start_of_local_day",
    "zone",
]

UTC = dt.UTC

Channel = Literal["cli", "mcp", "bot", "app", "import", "system"]
CHANNELS: tuple[Channel, ...] = ("cli", "mcp", "bot", "app", "import", "system")
ID_SHAPE = re.compile(r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$")
"""Letters, digits and single ``-`` / ``_`` separators: the shape of every id an envelope or the
transaction log may carry (``cli-0f3a...``, ``mcp_client-a``, ``import_v1``)."""
# Channels that can never be owner channels: a tool argument may have been written by a model (P-4).
NON_OWNER_CHANNELS: frozenset[str] = frozenset({"mcp", "app", "import", "system"})

Axis = Literal["knowledge", "instance", "occurrence"]
"""The as-of axes of §3.15: knowledge time K (default), instance time, occurrence time."""


# --------------------------------------------------------------------------------------------------
# The command context


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandContext:
    """Who is writing, through which channel, under which interaction (spec §5.1).

    ``owner_channel`` is set by the interface that received the call, never by the caller: the local
    CLI (and from stage 2 the bot) is an owner channel; MCP, apps and imports never are.
    ``idempotency_key`` is given by the client, or derived with ``derive_idempotency_key``.
    """

    actor: str
    channel: Channel
    owner_channel: bool
    interaction_id: str
    source_ref: str | None = None
    idempotency_key: str | None = None
    expected_version: int | None = None
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(f"unknown channel {self.channel!r}")
        if self.owner_channel and self.channel in NON_OWNER_CHANNELS:
            raise ValueError(f"channel {self.channel!r} is never an owner channel")
        if not self.actor or not self.interaction_id:
            raise ValueError("actor and interaction_id are required")
        for name, value in (("actor", self.actor), ("interaction_id", self.interaction_id)):
            if not ID_SHAPE.match(value) or len(value) > 120:
                raise ValueError(f"{name} must be id-shaped")  # free text never reaches the log

    def with_actor(self, actor: str, *, channel: Channel) -> CommandContext:
        """The same interaction under another actor, e.g. ``ctx.with_actor('import_v1',
        channel='import')``."""
        owner = self.owner_channel and channel not in NON_OWNER_CHANNELS
        return replace(self, actor=actor, channel=channel, owner_channel=owner)

    def with_expected_version(self, version: int | None) -> CommandContext:
        return replace(self, expected_version=version)

    def with_idempotency_key(self, key: str | None) -> CommandContext:
        return replace(self, idempotency_key=key)


def derive_idempotency_key(interaction_id: str, payload_hash: str) -> str:
    """The key a retry reuses when the client gave none: the interaction id plus the payload
    hash."""
    return f"{interaction_id}-{payload_hash}"


# --------------------------------------------------------------------------------------------------
# Results and answers


@dataclass(frozen=True)
class CommandResult[T]:
    """What every command returns: its value, the unit's ``tx`` and the ids of its events.

    ``tx`` is ``None`` when nothing was written (for example an import of a file already applied).
    ``replayed`` is true when a retry with the same idempotency key returned the first result.
    """

    value: T
    tx: int | None
    event_ids: tuple[str, ...] = ()
    replayed: bool = False


@dataclass(frozen=True)
class Answer[T]:
    """What every query returns (spec §5.1): the value plus as-of, coverage, staleness and role.

    ``instance_role`` is stated in every answer. ``coverage`` holds honest notes such as
    "amounts withheld (financial flag off)" or "mirrored from V1, snapshot exported at ...".
    """

    value: T
    instance_role: str
    as_of: dt.datetime
    axis: Axis = "knowledge"
    coverage: tuple[str, ...] = ()
    stale: bool = False


# --------------------------------------------------------------------------------------------------
# Clocks


@runtime_checkable
class Clock(Protocol):
    """The only way code learns the current time."""

    def now(self) -> dt.datetime:
        """The current instant: timezone-aware, in UTC."""
        ...


class SystemClock:
    """The wall clock. Used by the composition root only; tests use ``FakeClock``."""

    def now(self) -> dt.datetime:
        return dt.datetime.now(UTC)


class FakeClock:
    """A settable clock for tests. Frozen unless ``tick`` is given, which advances it after each
    read.

    The shared test world (``tests/conftest.py``) starts it at 2026-11-15T09:30:00.000Z, which is
    10:30 on 15 November 2026 in the owner's zone ``Europe/Berlin``.
    """

    def __init__(self, start: dt.datetime, *, tick: dt.timedelta | None = None) -> None:
        self._now = _require_aware(start).astimezone(UTC)
        self._tick = tick

    def now(self) -> dt.datetime:
        current = self._now
        if self._tick is not None:
            self._now = self._now + self._tick
        return current

    def set(self, instant: dt.datetime) -> None:
        self._now = _require_aware(instant).astimezone(UTC)

    def advance(
        self,
        *,
        days: float = 0,
        hours: float = 0,
        minutes: float = 0,
        seconds: float = 0,
        milliseconds: float = 0,
    ) -> dt.datetime:
        self._now = self._now + dt.timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
        )
        return self._now

    def set_local(self, day: dt.date, at: dt.time, tz: str | ZoneInfo) -> None:
        """Set the clock to a wall time in a zone, e.g. 09:00 in ``Europe/Berlin``."""
        self._now = dt.datetime.combine(day, at, tzinfo=zone(tz)).astimezone(UTC)


# --------------------------------------------------------------------------------------------------
# Time conventions


def zone(tz: str | ZoneInfo) -> ZoneInfo:
    """An IANA zone; the ``tzdata`` dependency makes this work on Windows too."""
    return tz if isinstance(tz, ZoneInfo) else ZoneInfo(tz)


def _require_aware(instant: dt.datetime) -> dt.datetime:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instants must be timezone-aware")
    return instant


def format_instant(instant: dt.datetime) -> str:
    """UTC ISO 8601 with milliseconds and ``Z``: the stored form of every instant (§2.1)."""
    utc = _require_aware(instant).astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def parse_instant(text: str) -> dt.datetime:
    """Parse a stored or received instant (``Z`` or an explicit offset) into aware UTC."""
    value = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _require_aware(value).astimezone(UTC)


def local_date(instant: dt.datetime, tz: str | ZoneInfo) -> dt.date:
    """The owner-zone date of an instant: "today" is always this, never the host's date."""
    return _require_aware(instant).astimezone(zone(tz)).date()


def start_of_local_day(day: dt.date, tz: str | ZoneInfo) -> dt.datetime:
    """The first instant (UTC) of ``day`` in the zone."""
    return dt.datetime.combine(day, dt.time.min, tzinfo=zone(tz)).astimezone(UTC)


def end_of_local_day(day: dt.date, tz: str | ZoneInfo) -> dt.datetime:
    """The last millisecond (UTC) of ``day`` in the zone."""
    nxt = start_of_local_day(day + dt.timedelta(days=1), tz)
    return nxt - dt.timedelta(milliseconds=1)


@dataclass(frozen=True, slots=True)
class EvalTime:
    """``T`` of spec §3: the evaluation instant (UTC) and ``T.date``, its date in the owner's zone.

    Every computed function takes an ``EvalTime`` and the configuration explicitly (§12.5).
    """

    instant: dt.datetime
    date: dt.date

    def __post_init__(self) -> None:
        _require_aware(self.instant)

    @classmethod
    def at(cls, instant: dt.datetime, tz: str | ZoneInfo) -> EvalTime:
        """T at an instant; ``T.date`` is that instant's owner-zone date."""
        utc = _require_aware(instant).astimezone(UTC)
        return cls(utc, local_date(utc, tz))

    @classmethod
    def end_of_day(cls, day: dt.date, tz: str | ZoneInfo) -> EvalTime:
        """T for "as of the day": the last millisecond of ``day`` in the owner's zone."""
        return cls(end_of_local_day(day, tz), day)


# --------------------------------------------------------------------------------------------------
# Randomness


def _secure_salt() -> str:
    return secrets.token_hex(16)


@dataclass
class _SaltSource:
    draw: Callable[[], str] = field(default=_secure_salt)


_SALTS = _SaltSource()


def new_salt() -> str:
    """16 random bytes as hex: the only source of randomness in CoFlow (spec §3.3, §12.5).

    Salts protect sealed content (§3.3); EVT may also draw the random part of UUIDv7 event ids
    from it. Tests that need reproducible salts wrap the code in ``seeded_salts``.
    """
    return _SALTS.draw()


@contextmanager
def seeded_salts(seed: str) -> Iterator[None]:
    """Deterministic salts for tests and golden fixtures: sha256(seed + counter), 32 hex chars."""
    counter = 0

    def draw() -> str:
        nonlocal counter
        counter += 1
        return hashlib.sha256(f"{seed}-{counter}".encode()).hexdigest()[:32]

    previous = _SALTS.draw
    _SALTS.draw = draw
    try:
        yield
    finally:
        _SALTS.draw = previous
