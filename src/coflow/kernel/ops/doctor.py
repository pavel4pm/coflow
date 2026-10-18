"""``coflow doctor`` (basic): the role, the lock, the data root and the schema revision.

Owned by track K; increment I1, spec §12.2. ``DoctorCheck``, ``DoctorReport`` and ``run_doctor`` are
fixed by the skeleton because track X renders them; the track implements them.

Checks: the instance role; the instance lock (free, or held by the running core); a data root
outside any repository working tree (refused for ``validation``, AT-K9); the schema revision
against the code's migrations.

Every check reads only: the database through a read-only connection (no writer, no lock held), the
lock by taking and releasing it at once. In order:

- ``role``: an instance lives here and its role is known (``role: validation``);
- ``lock``: free, or held by a running core (its process id from the holder note);
- ``data_root``: outside any repository working tree; inside one is refused for every role but
  ``dev`` (DEP-23);
- ``schema``: the applied migrations equal the code's (none pending, unknown or changed);
- ``volume``: ``volume.id`` in the data root matches the database's volume id (DEP-2), so a
  database copied into another data root is noticed.

Spec note: the ``volume`` check is the DEP-2 part that is cheap today; the full ``doctor``
(filesystems, model checksums, host checks) arrives in 0B.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from coflow.kernel.errors import CoflowError
from coflow.kernel.ops.instance import InstanceInfo, load_instance, repository_working_tree
from coflow.kernel.store import migrations as _migrations
from coflow.kernel.store.db import DB_FILE, VOLUME_FILE, open_read_connection
from coflow.kernel.store.lock import probe_lock

__all__ = ["DoctorCheck", "DoctorReport", "run_doctor"]


@dataclass(frozen=True, slots=True, kw_only=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class DoctorReport:
    data_root: Path
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def _read_instance(
    db_path: Path,
) -> tuple[InstanceInfo | None, _migrations.SchemaStatus | None, str | None]:
    try:
        conn = open_read_connection(db_path)
    except sqlite3.DatabaseError as exc:
        return None, None, f"the database cannot be opened: {type(exc).__name__}"
    try:
        info: InstanceInfo | None
        try:
            info = load_instance(conn)
        except (CoflowError, sqlite3.DatabaseError):
            info = None
        try:
            files = _migrations.code_migrations(_migrations.discover_sources())
            status = _migrations.schema_status(conn, files)
        except (CoflowError, sqlite3.DatabaseError) as exc:
            return info, None, f"the schema cannot be read: {exc}"
        return info, status, None
    finally:
        conn.close()


def run_doctor(data_root: Path) -> DoctorReport:
    root = Path(data_root).expanduser().resolve()
    db_path = root / DB_FILE
    checks: list[DoctorCheck] = []
    info: InstanceInfo | None = None
    status: _migrations.SchemaStatus | None = None
    error: str | None = None

    if db_path.is_file():
        info, status, error = _read_instance(db_path)
    if info is not None:
        checks.append(
            DoctorCheck(name="role", ok=True, detail=f"role: {info.role} ({info.instance_id})")
        )
    else:
        reason = error or "no CoFlow instance in this data root (coflow init)"
        checks.append(DoctorCheck(name="role", ok=False, detail=reason))

    if not root.is_dir():
        checks.append(DoctorCheck(name="lock", ok=False, detail="the data root does not exist"))
    else:
        try:
            probe = probe_lock(root)
        except OSError as exc:
            checks.append(
                DoctorCheck(name="lock", ok=False, detail=f"cannot probe: {type(exc).__name__}")
            )
        else:
            if probe.free:
                detail = "free (no core is running)"
            elif probe.holder is not None:
                detail = f"held by a running core (process {probe.holder.pid}"
                detail += f", since {probe.holder.since})" if probe.holder.since else ")"
            else:
                detail = "held by a running core"
            checks.append(DoctorCheck(name="lock", ok=True, detail=detail))

    tree = repository_working_tree(root)
    role = info.role if info is not None else None
    if tree is None:
        checks.append(
            DoctorCheck(name="data_root", ok=True, detail="outside any repository working tree")
        )
    elif role == "dev":
        checks.append(
            DoctorCheck(
                name="data_root",
                ok=True,
                detail=f"inside the working tree {tree} (allowed for dev only)",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="data_root",
                ok=False,
                detail=f"inside the repository working tree {tree}: refused for a"
                f" {role or 'non-dev'} instance (DATA_ROOT_IN_REPOSITORY)",
            )
        )

    if status is not None:
        checks.append(DoctorCheck(name="schema", ok=status.ok, detail=status.summary()))
    else:
        checks.append(DoctorCheck(name="schema", ok=False, detail=error or "no schema to compare"))

    if info is not None:
        try:
            volume = (root / VOLUME_FILE).read_text(encoding="utf-8").strip()
        except OSError:
            volume = None
        if volume is None:
            checks.append(DoctorCheck(name="volume", ok=False, detail=f"{VOLUME_FILE} is missing"))
        elif volume != info.volume_id:
            checks.append(
                DoctorCheck(
                    name="volume",
                    ok=False,
                    detail="the database belongs to another volume (copied into this root?)",
                )
            )
        else:
            checks.append(DoctorCheck(name="volume", ok=True, detail="matches the database"))

    return DoctorReport(data_root=root, checks=tuple(checks))
