"""The instance (``sys_instance``, spec §2.3, §6.1): its id and role, shown in every answer.

Owned by track K; increment I1, spec §12.2. ``InstanceRole``, ``InstanceInfo`` and ``load_instance``
are fixed by the skeleton because the importer checks the role (``IMPORT_ROLE``,
``IMPORT_NOT_SYNTHETIC``) and every query answer states it; the track implements them.

Roles: ``dev`` (synthetic data only, anywhere including CI), ``validation`` (the owner's real
snapshot; the data root lies outside any repository working tree), ``drill`` (the case runner's
throw-away copies); later ``staging`` and ``production``.

Helpers for the other tracks:

- ``check_snapshot_import(role, synthetic=...)``: the role rule of §6.1 and §6.5 in one place. A
  ``dev`` instance accepts only snapshots marked ``"synthetic": true``
  (``IMPORT_NOT_SYNTHETIC``); only ``dev`` and ``validation`` take snapshot imports at all
  (``IMPORT_ROLE``). A ``validation`` instance accepts both; it is where the real snapshot lives.
- ``repository_working_tree(path)``: the working tree a path lies in (a ``.git`` directory or file
  in the path or a parent), which ``init`` and ``doctor`` refuse for every role but ``dev``.

Spec note: §6.1 and the pseudo-code of §6.5 refuse only a snapshot *not* marked synthetic in a
``dev`` instance; nothing refuses a synthetic snapshot in a ``validation`` instance (AT-K9 imports
the synthetic S1 into one), so ``validation`` accepts both. A ``drill`` copy takes no import
(``IMPORT_ROLE``); the case runner writes to it through commands, not through the importer.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from coflow.kernel.context import new_salt, parse_instant
from coflow.kernel.errors import NotFound, RefusalCode, Refused

__all__ = [
    "INIT_ROLES",
    "INSTANCE_ROLES",
    "SNAPSHOT_ROLES",
    "InstanceInfo",
    "InstanceRole",
    "check_snapshot_import",
    "load_instance",
    "new_instance_id",
    "new_volume_id",
    "repository_working_tree",
]

InstanceRole = Literal["dev", "validation", "drill", "staging", "production"]
INSTANCE_ROLES: tuple[InstanceRole, ...] = ("dev", "validation", "drill", "staging", "production")
INIT_ROLES: tuple[InstanceRole, ...] = ("dev", "validation")
"""The roles ``coflow init`` creates in the slice; ``drill`` copies are made by the case runner."""
SNAPSHOT_ROLES: tuple[InstanceRole, ...] = ("dev", "validation")


@dataclass(frozen=True, slots=True, kw_only=True)
class InstanceInfo:
    instance_id: str
    role: InstanceRole
    volume_id: str
    created_at: datetime


def load_instance(conn: sqlite3.Connection) -> InstanceInfo:
    row = conn.execute(
        "SELECT instance_id, role, volume_id, created_at FROM sys_instance LIMIT 1"
    ).fetchone()
    if row is None:
        raise NotFound("sys_instance", "this database has no instance row (coflow init)")
    role = str(row[1])
    if role not in INSTANCE_ROLES:
        raise NotFound("sys_instance", f"unknown instance role {role!r}")
    return InstanceInfo(
        instance_id=str(row[0]),
        role=role,  # type: ignore[arg-type]
        volume_id=str(row[2]),
        created_at=parse_instant(str(row[3])),
    )


def new_instance_id() -> str:
    """A random instance id, ``i-`` plus 16 hex digits (the event source names it)."""
    return "i-" + new_salt()[:16]


def new_volume_id() -> str:
    """A random volume id (DEP-2), written in the database and in the data root at ``init``."""
    return new_salt()


def repository_working_tree(path: Path) -> Path | None:
    """The repository working tree ``path`` lies in, or None.

    A working tree is any directory holding ``.git`` (a directory, or the file a worktree or a
    submodule uses). The data root itself counts, so does every parent.
    """
    resolved = Path(path).expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def check_snapshot_import(role: str, *, synthetic: bool) -> None:
    """Refuse a snapshot import the instance's role does not allow (§6.1, §6.5 order)."""
    if role == "dev" and not synthetic:
        raise Refused(
            RefusalCode.IMPORT_NOT_SYNTHETIC,
            'a dev instance accepts only snapshots marked "synthetic": true',
            allowed=["a snapshot marked synthetic", "a validation instance"],
        )
    if role not in SNAPSHOT_ROLES:
        raise Refused(
            RefusalCode.IMPORT_ROLE,
            f"a {role} instance takes no snapshot import",
            allowed=list(SNAPSHOT_ROLES),
        )
