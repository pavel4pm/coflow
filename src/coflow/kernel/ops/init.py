"""``coflow init``: create an instance in a data root (OPS-1 minimum, spec §5.6, §6.1).

Owned by track K; increment I1, spec §12.2. ``init_instance`` is fixed by the skeleton because the
shared test fixture (``tests/conftest.py``) and track X's CLI call it; the track implements it.

It refuses a data root inside any repository working tree for the ``validation`` role
(``DATA_ROOT_IN_REPOSITORY``, AT-K9), applies every migration, seeds the prefix registry from
``kernel.ids.registry.SLICE_PREFIXES``, writes the owner profile and the instance row.

Steps, all under the instance lock (``INSTANCE_LOCKED`` if a core holds it):

1. check the arguments: a role of ``INIT_ROLES`` (``dev``, ``validation``), an IANA zone, a locale
   of the R1 packs, an ISO 4217 currency, an issuer code that is not a foreign issuer;
2. refuse a ``validation`` data root inside a repository working tree; refuse a data root that
   already holds an instance (``InstanceExists``; ``init`` never overwrites);
3. create the database and apply every migration (kernel, then modules by tier);
4. one ``ops`` unit: the ``sys_instance`` row (random instance and volume ids), the prefix registry
   and the sequences (``D`` from 1001, ``F`` from 10001, the rest from 1);
5. one ``cfg`` unit: the owner profile and the initial settings;
6. write ``volume.id`` and create ``inbox/snapshots/``.

If any step fails, the files it created are removed, so a failed ``init`` can simply be repeated.

``migrate_instance`` is the forward-only migration step for an existing instance (OPS-4): under the
lock, a snapshot copy in ``backups/`` first, then the pending files.

Spec note: ``dev`` data roots may lie anywhere, including inside a working tree (§6.1: "anywhere,
including CI"); only the other roles are refused there.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from coflow.kernel.config.profile import OwnerProfile, profile_row, validate_profile
from coflow.kernel.config.settings import initial_settings
from coflow.kernel.context import Clock, CommandContext, format_instant
from coflow.kernel.errors import ContractViolation, RefusalCode, Refused
from coflow.kernel.ids.codes import is_issuer_code
from coflow.kernel.ids.registry import SLICE_PREFIXES, registry_row
from coflow.kernel.ops.instance import (
    INIT_ROLES,
    InstanceInfo,
    InstanceRole,
    new_instance_id,
    new_volume_id,
    repository_working_tree,
)
from coflow.kernel.store.db import (
    DB_FILE,
    INBOX_DIR,
    VOLUME_FILE,
    InstanceExists,
    SqliteStore,
    create_store,
    migrate_store,
)
from coflow.kernel.store.lock import InstanceLock

__all__ = ["init_instance", "migrate_instance", "refuse_repository_root"]

_FOREIGN_ISSUERS = ("V1", "CF2LOG")


def refuse_repository_root(data_root: Path, role: str) -> None:
    """``DATA_ROOT_IN_REPOSITORY`` for a non-dev data root inside a repository working tree."""
    if role == "dev":
        return
    tree = repository_working_tree(data_root)
    if tree is not None:
        raise Refused(
            RefusalCode.DATA_ROOT_IN_REPOSITORY,
            f"the data root of a {role} instance lies inside the repository working tree {tree}",
            allowed=["a data root outside any repository working tree"],
        )


def _check_arguments(
    role: str, *, timezone: str, issuer: str, locale: str, currency: str, display_name: str
) -> None:
    problems: list[str] = []
    if role not in INIT_ROLES:
        problems.append(f"init creates the roles {', '.join(INIT_ROLES)}, not {role!r}")
    if not is_issuer_code(issuer) or issuer in _FOREIGN_ISSUERS:
        problems.append(f"{issuer!r} is not a free issuer code (letters and digits, not V1)")
    problems += validate_profile(
        OwnerProfile(display_name=display_name, timezone=timezone, locale=locale, currency=currency)
    )
    if problems:
        raise ContractViolation("; ".join(problems))


def _remove_created(root: Path) -> None:
    for name in (DB_FILE, f"{DB_FILE}-wal", f"{DB_FILE}-shm", VOLUME_FILE):
        with contextlib.suppress(OSError):
            (root / name).unlink(missing_ok=True)


def _seed(
    store: SqliteStore,
    *,
    instance_id: str,
    volume_id: str,
    role: str,
    timezone: str,
    issuer: str,
    locale: str,
    currency: str,
    display_name: str,
) -> InstanceInfo:
    ctx = CommandContext(
        actor="system", channel="system", owner_channel=False, interaction_id=f"init-{instance_id}"
    )
    with store.unit_of_work("ops", ctx, command="init") as unit:
        created_at = unit.committed_at
        unit.insert(
            "sys_instance",
            {
                "instance_id": instance_id,
                "role": role,
                "volume_id": volume_id,
                "created_at": format_instant(created_at),
            },
        )
        for spec in SLICE_PREFIXES:
            unit.kernel_insert("sys_id_prefixes", registry_row(spec))
            if not spec.scoped_under:
                unit.kernel_insert(
                    "sys_id_sequence", {"prefix": spec.prefix, "next_n": spec.block_start or 1}
                )
    with store.unit_of_work("cfg", ctx, command="init") as unit:
        profile = OwnerProfile(
            display_name=display_name, timezone=timezone, locale=locale, currency=currency
        )
        unit.insert("cfg_profile", profile_row(profile))
        settings = initial_settings(
            timezone=timezone, locale=locale, currency=currency, issuer=issuer
        )
        for key, value in settings.items():
            unit.insert("cfg_settings", {"key": key, "value": value})
    return InstanceInfo(
        instance_id=instance_id,
        role=role,  # type: ignore[arg-type]
        volume_id=volume_id,
        created_at=created_at,
    )


def init_instance(
    data_root: Path,
    *,
    role: InstanceRole,
    clock: Clock,
    timezone: str,
    issuer: str = "CF",
    locale: str = "en",
    currency: str = "EUR",
    display_name: str = "Owner",
) -> InstanceInfo:
    _check_arguments(
        role,
        timezone=timezone,
        issuer=issuer,
        locale=locale,
        currency=currency,
        display_name=display_name,
    )
    root = Path(data_root).expanduser().resolve()
    refuse_repository_root(root, role)
    root.mkdir(parents=True, exist_ok=True)
    if (root / DB_FILE).exists():
        raise InstanceExists(f"an instance already lives in {root}; init never overwrites it")
    with InstanceLock(root).acquire("init", since=format_instant(clock.now())):
        if (root / DB_FILE).exists():
            raise InstanceExists(f"an instance already lives in {root}; init never overwrites it")
        instance_id = new_instance_id()
        volume_id = new_volume_id()
        store: SqliteStore | None = None
        try:
            store = create_store(root, clock=clock, role=role, instance_id=instance_id)
            info = _seed(
                store,
                instance_id=instance_id,
                volume_id=volume_id,
                role=role,
                timezone=timezone,
                issuer=issuer,
                locale=locale,
                currency=currency,
                display_name=display_name,
            )
            store.close()
            store = None
            (root / VOLUME_FILE).write_text(volume_id + "\n", encoding="utf-8")
            (root / INBOX_DIR).mkdir(parents=True, exist_ok=True)
        except BaseException:
            if store is not None:
                store.close()
            _remove_created(root)
            raise
    return info


def migrate_instance(data_root: Path, *, clock: Clock) -> list[str]:
    """Apply the code's pending migrations to an existing instance (a deploy step, OPS-4)."""
    return migrate_store(data_root, clock=clock)
