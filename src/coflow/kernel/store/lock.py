"""The OS-level instance lock on the data root: the second ``core`` refuses (``INSTANCE_LOCKED``),
the CLI's ephemeral core takes the same lock (spec §4.5, AT-K7).

Owned by track K (kernel); increment I1, spec §12.2.

The lock is an exclusive, non-blocking OS lock on ``<data_root>/instance.lock``: ``flock`` on POSIX,
a one-byte ``msvcrt.locking`` region on Windows. Both are held per open file, so a second holder
in the same process is refused exactly like one in another process, and the operating system
releases the lock when the holder dies. The lock is the truth; ``instance.holder.json`` beside it
is only a note for ``doctor`` (process id, purpose, since when) and may be stale.

Spec note: §4.5 names one lock for ``core``, the CLI's ephemeral core, ``init`` and ``migrate``.
A read-only store takes no lock (it never writes), so ``doctor`` and read-only tools can run while
``core`` holds it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Literal

from coflow.kernel.errors import RefusalCode, Refused

__all__ = [
    "HOLDER_FILE",
    "LOCK_FILE",
    "InstanceLock",
    "LockHolder",
    "LockProbe",
    "LockPurpose",
    "probe_lock",
    "read_holder",
]

LOCK_FILE = "instance.lock"
HOLDER_FILE = "instance.holder.json"

LockPurpose = Literal["core", "ephemeral", "init", "migrate", "probe"]


@dataclass(frozen=True, slots=True, kw_only=True)
class LockHolder:
    """What the holder wrote beside the lock (informational; the lock itself is the truth)."""

    pid: int
    purpose: str
    since: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LockProbe:
    """The result of ``probe_lock``: whether the lock is free and, if not, who said they hold it."""

    free: bool
    holder: LockHolder | None = None


def _try_lock(fd: int) -> bool:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        with contextlib.suppress(OSError):
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


class InstanceLock:
    """An exclusive lock on one data root. Use ``acquire`` (or ``with InstanceLock(...)``)."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root)
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        return self.data_root / LOCK_FILE

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self, purpose: LockPurpose = "core", *, since: str | None = None) -> InstanceLock:
        """Take the lock or raise ``Refused(INSTANCE_LOCKED)`` at once (never waits)."""
        if self._fd is not None:
            return self
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        if not _try_lock(fd):
            os.close(fd)
            holder = read_holder(self.data_root)
            who = f" by process {holder.pid} ({holder.purpose})" if holder else ""
            raise Refused(
                RefusalCode.INSTANCE_LOCKED,
                f"the instance is locked{who}: another core runs on this data root",
                allowed=["the running core's admin API", "stop the running core first"],
            )
        self._fd = fd
        if purpose != "probe":
            _write_holder(self.data_root, LockHolder(pid=os.getpid(), purpose=purpose, since=since))
        return self

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            _unlock(fd)
        finally:
            os.close(fd)

    def __enter__(self) -> InstanceLock:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def _write_holder(data_root: Path, holder: LockHolder) -> None:
    body = {"pid": holder.pid, "purpose": holder.purpose, "since": holder.since}
    with contextlib.suppress(OSError):  # the note is informational; the lock already holds
        (data_root / HOLDER_FILE).write_text(json.dumps(body, sort_keys=True), encoding="utf-8")


def read_holder(data_root: Path) -> LockHolder | None:
    """The holder note beside the lock, if one is readable."""
    try:
        raw = json.loads((Path(data_root) / HOLDER_FILE).read_text(encoding="utf-8"))
        return LockHolder(pid=int(raw["pid"]), purpose=str(raw["purpose"]), since=raw.get("since"))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def probe_lock(data_root: Path) -> LockProbe:
    """Whether the instance lock is free, by taking and releasing it at once (``doctor``)."""
    lock = InstanceLock(data_root)
    try:
        lock.acquire("probe")
    except Refused:
        return LockProbe(free=False, holder=read_holder(data_root))
    lock.release()
    return LockProbe(free=True)
