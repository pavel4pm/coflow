"""Wiring: open the store under the instance lock (``kernel.store.api.open_store``,
``bind_store``), build ``dec.api.default_env()`` (and from I3 the CMT environment with
``dec.api.directory``), register probes and resolvers.

Owned by track X (interfaces); increment I1, spec §12.2.

- ``build_services`` wires the interfaces' ``Services`` over the store that is already bound (the
  core, the CLI's ephemeral core, or a test's ``dev_store``).
- ``open_core`` is the whole composition for one process: it opens the instance under its lock,
  binds it as the one store of the process, yields the services and closes everything on exit. A
  second ``open_core`` on the same data root, in this process or another, is refused by the lock
  (``INSTANCE_LOCKED``): there is never a second writer (§4.5). Like ``init`` and ``doctor`` it
  refuses a non-dev data root inside a repository working tree (``DATA_ROOT_IN_REPOSITORY``, found
  in review: a validation root copied into a repository later would otherwise still import, run
  and write its reports and endpoint file into the tree).

In I1 DEC's environment is ``dec.api.default_env()``: the shadow goal directory over mirrored goal
context, no attachment probes (CMT arrives in I3) and no evidence resolvers (I2).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from coflow.interfaces.admin.api import Services, SqlAdminTokens
from coflow.interfaces.mcp.auth import SqlCallLog, SqlClientRegistry
from coflow.interfaces.views.card import DecApiService, KernelUsageSink, StoreInstanceFacts
from coflow.kernel.context import Clock, SystemClock
from coflow.kernel.ops.init import refuse_repository_root
from coflow.kernel.ops.instance import load_instance
from coflow.kernel.store.api import bind_store, open_store, unbind_store
from coflow.modules.dec import api as dec_api
from coflow.modules.dec.api import DecEnv

__all__ = ["build_services", "dec_env", "open_core"]


def dec_env() -> DecEnv:
    """DEC's environment for the slice (ports wired here as their modules arrive)."""
    return dec_api.default_env()


def build_services(*, clock: Clock, data_root: Path, env: DecEnv | None = None) -> Services:
    """The interfaces' services over the bound store."""
    return Services(
        dec=DecApiService(env or dec_env()),
        facts=StoreInstanceFacts(),
        usage=KernelUsageSink(),
        clients=SqlClientRegistry(),
        call_log=SqlCallLog(clock),
        admin_tokens=SqlAdminTokens(clock),
        clock=clock,
        data_root=data_root,
    )


@contextmanager
def open_core(data_root: Path, *, clock: Clock | None = None) -> Iterator[Services]:
    """Open the instance in ``data_root`` under its lock, bind it, and yield its services."""
    clock = clock or SystemClock()
    store = open_store(data_root, clock=clock)
    try:
        with store.read_connection() as conn:
            role = load_instance(conn).role
        refuse_repository_root(Path(data_root), role)
        bind_store(store)
        try:
            yield build_services(clock=clock, data_root=data_root)
        finally:
            unbind_store()
    finally:
        store.close()
