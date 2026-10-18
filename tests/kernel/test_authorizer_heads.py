"""The authorizer on heads whose text columns are both mutable and erasable (integration; spec
§2.1, §2.4 "[E]" on ``dec_decisions`` and ``dec_forks``).

The owner module changes such a column through its commands (with version rows); POL's erasure unit
blanks it with a new ``erased_tx``. An erasable column that is not mutable changes only by erasure,
and only POL stamps ``erased_tx``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store import api
from coflow.kernel.store.authorizer import Authorizer
from coflow.kernel.store.db import SqliteStore
from coflow.kernel.store.registry import TableDecl
from coflow.modules.dec import api as dec
from tests.modules.dec.import_helpers import import_family

OK, DENY = sqlite3.SQLITE_OK, sqlite3.SQLITE_DENY

HEAD = TableDecl(
    table="tst_heads",
    module="tst",
    data_class="work",
    append_only=False,
    set_once=frozenset(),
    erasable=frozenset({"title", "note"}),
    mutable=frozenset({"title", "status"}),
    columns=("id", "title", "note", "status", "version", "erased_tx", "tx", "recorded_at"),
    pk="id",
)


def _update(owner: str, column: str) -> int:
    auth = Authorizer(registry={"tst_heads": HEAD}, mode="unit", owner=owner)
    return auth(sqlite3.SQLITE_UPDATE, "tst_heads", column, "main", None)


@pytest.mark.parametrize(
    ("owner", "column", "verdict"),
    [
        ("tst", "title", OK),  # mutable and erasable: the owner's commands change it
        ("tst", "status", OK),  # mutable only
        ("tst", "note", DENY),  # erasable only: changes by erasure alone
        ("tst", "erased_tx", DENY),  # only POL stamps an erasure
        ("pol", "title", OK),
        ("pol", "note", OK),
        ("pol", "erased_tx", OK),
        ("pol", "status", DENY),  # POL touches erasable columns only
        ("oth", "title", DENY),  # never another module's table
    ],
)
def test_the_owner_may_change_a_mutable_erasable_column(
    owner: str, column: str, verdict: int
) -> None:
    assert _update(owner, column) == verdict


def test_a_decision_head_text_is_mutable_and_erasable(
    dev_store: SqliteStore, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    import_family(dec.default_env(), "s1.json", clock=clock, ctx=owner_ctx, directory=tmp_path)
    with api.read_connection() as conn:
        row = conn.execute(
            "SELECT id, version FROM dec_decisions WHERE public_id = 'D-0907'"
        ).fetchone()
        decl = conn.execute(
            "SELECT erasable_cols FROM sys_table_registry WHERE table_name = 'dec_decisions'"
        ).fetchone()
    assert "statement" in str(decl[0])
    with api.unit_of_work("dec", owner_ctx, command="update_decision"):
        api.update_head("dec_decisions", int(row["id"]), int(row["version"]), statement="Changed")
    erasure = CommandContext(actor="owner", channel="cli", owner_channel=True, interaction_id="e")
    with api.unit_of_work("pol", erasure, command="erase") as unit:
        unit.erase("dec_decisions", int(row["id"]), statement=None)  # type: ignore[attr-defined]
        erased_by = unit.tx
    with api.read_connection() as conn:
        after = conn.execute(
            "SELECT statement, erased_tx FROM dec_decisions WHERE id = ?", (int(row["id"]),)
        ).fetchone()
    assert (after["statement"], after["erased_tx"]) == (None, erased_by)
