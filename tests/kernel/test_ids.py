"""IDS: the numbering tap, the prefix registry, canonical codes, tolerant input and aliases.

AT-K1 (IDN-1, IDN-10), AT-K2 (IDN-2), AT-K3 (IDN-9).
"""

from __future__ import annotations

import json
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from coflow.kernel.context import FakeClock
from coflow.kernel.errors import Ambiguous, ContractViolation, NotFound, RefusalCode, Refused
from coflow.kernel.ids import aliases, codes, tap
from coflow.kernel.ids.registry import SLICE_PREFIXES, prefix_spec
from coflow.kernel.ops.init import init_instance
from coflow.kernel.store import api
from coflow.kernel.store.db import SqliteStore, open_store
from tests.kernel.conftest import ModuleDirs
from tests.kernel.helpers import ctx

# --------------------------------------------------------------------------------------------------
# AT-K1: the tap


def test_at_k1_concurrent_issues_skip_foreign_and_burned(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="register") as unit:
        for n in range(903, 911):
            tap.register_foreign("D", n, issuer="V1", source_id=f"D{n}")
        for n in (901, 902):
            tap.burn("D", n, reason="numbering_gap", issuer="V1")
        assert unit.tx > 0

    issued: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            for _ in range(125):
                with api.unit_of_work("tst", ctx(f"worker{i}"), command="issue"):
                    got = tap.issue("D")
                with lock:
                    issued.append(got.n)
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(issued) == 1000
    assert len(set(issued)) == 1000, "no duplicates"
    assert min(issued) == 1001, "the first native is D-1001"
    assert sorted(issued) == list(range(1001, 2001)), "no gaps, no reuse"
    assert not set(issued) & set(range(901, 911)), "no foreign or burned number"
    with api.read_connection() as conn:
        next_n = conn.execute("SELECT next_n FROM sys_id_sequence WHERE prefix = 'D'").fetchone()
        assert next_n[0] == 2001


def test_tap_skips_numbers_in_the_block_and_starts_other_prefixes_at_one(
    kstore: SqliteStore,
) -> None:
    with api.unit_of_work("tst", ctx(), command="burn"):
        tap.burn("D", 1001, reason="undo")
        tap.burn("D", 1002, reason="undo")
        tap.burn("D", 1004, reason="undo")
        first = tap.issue("D")
        second = tap.issue("D")
        fork = tap.issue("Q")
        commitment = tap.issue("F")
    assert (first.public_id, second.public_id) == ("D-1003", "D-1005")
    assert fork.public_id == "Q-0001"
    assert commitment.public_id == "F-10001"


def test_a_rolled_back_unit_gives_its_number_back_unseen(kstore: SqliteStore) -> None:
    def failing_create() -> None:
        with api.unit_of_work("tst", ctx(), command="issue"):
            assert tap.issue("D").n == 1001
            raise RuntimeError("the record that would carry the number failed")

    with pytest.raises(RuntimeError):
        failing_create()
    with api.unit_of_work("tst", ctx(), command="issue"):
        assert tap.issue("D").n == 1001


def test_tap_refuses_scoped_prefixes_and_runs_only_in_a_unit(kstore: SqliteStore) -> None:
    with pytest.raises(ContractViolation, match=r"outside|no unit"):
        tap.issue("D")
    with api.unit_of_work("tst", ctx(), command="issue"):
        with pytest.raises(ContractViolation, match="scoped"):
            tap.issue("A")
        with pytest.raises(Refused) as unknown:
            tap.issue("X")
        assert unknown.value.code is RefusalCode.PREFIX_UNKNOWN
        tap.issue("Q")


def test_register_foreign_is_idempotent_and_refuses_conflicts(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="register"):
        tap.register_foreign("D", 907, issuer="V1", source_id="D907")
        tap.register_foreign("D", 907, issuer="V1", source_id="D907")
        tap.burn("D", 901, reason="numbering_gap", issuer="V1")
        tap.burn("D", 901, reason="numbering_gap", issuer="V1")
        with pytest.raises(Refused) as other:
            tap.register_foreign("D", 907, issuer="CF2LOG", source_id="D-907")
        assert other.value.code is RefusalCode.IMPORT_SOURCE_CONFLICT
        issued = tap.issue("D")
        with pytest.raises(Refused) as ours:
            tap.register_foreign("D", issued.n, issuer="V1", source_id="D1001")
        assert ours.value.code is RefusalCode.IMPORT_SOURCE_CONFLICT
        with pytest.raises(ContractViolation):
            tap.register_foreign("D", 10000, issuer="V1", source_id="D10000")
        with pytest.raises(ContractViolation):
            tap.burn("D", 5, reason="lost")  # type: ignore[arg-type]
    with api.read_connection() as conn:
        assert conn.execute("SELECT count(*) FROM sys_id_foreign").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM sys_id_burned").fetchone()[0] == 1


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    burned=st.sets(st.integers(min_value=1001, max_value=1060), max_size=25),
    foreign=st.sets(st.integers(min_value=1, max_value=1000), max_size=25),
    count=st.integers(min_value=1, max_value=30),
)
def test_property_the_tap_never_issues_a_foreign_or_burned_number(
    module_dirs: ModuleDirs, burned: set[int], foreign: set[int], count: int
) -> None:
    clock = FakeClock(datetime(2026, 11, 15, 9, 30, tzinfo=UTC))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp) / "data"
        init_instance(root, role="dev", clock=clock, timezone="Europe/Berlin")
        store = open_store(root, clock=clock)
        try:
            with api.use_store(store):
                with api.unit_of_work("tst", ctx(), command="seed"):
                    for n in sorted(foreign):
                        tap.register_foreign("D", n, issuer="V1", source_id=f"D{n}")
                    for n in sorted(burned):
                        tap.burn("D", n, reason="undo")
                got = []
                for _ in range(count):
                    with api.unit_of_work("tst", ctx(), command="issue"):
                        got.append(tap.issue("D").n)
        finally:
            store.close()
    assert got == sorted(got)
    assert len(set(got)) == len(got)
    assert all(n >= 1001 for n in got)
    assert not set(got) & (burned | foreign)
    expected = [n for n in range(1001, 2000) if n not in burned][:count]
    assert got == expected


def test_seeded_registry_agrees_with_the_slice_prefixes(kstore: SqliteStore) -> None:
    with api.read_connection() as conn:
        rows = {
            r["prefix"]: r
            for r in conn.execute(
                "SELECT prefix, entity, width, owner_module, block_start, scoped_under"
                " FROM sys_id_prefixes"
            ).fetchall()
        }
        sequences = dict(conn.execute("SELECT prefix, next_n FROM sys_id_sequence").fetchall())
    assert set(rows) == {p.prefix for p in SLICE_PREFIXES}
    for spec in SLICE_PREFIXES:
        row = rows[spec.prefix]
        assert (row["entity"], row["width"], row["owner_module"], row["block_start"]) == (
            spec.entity,
            spec.width,
            spec.owner_module,
            spec.block_start,
        )
        scoped = json.loads(row["scoped_under"]) if row["scoped_under"] else []
        assert tuple(scoped) == spec.scoped_under
    assert sequences == {"D": 1001, "Q": 1, "F": 10001}


# --------------------------------------------------------------------------------------------------
# AT-K2: render and parse

_CHAINS: list[tuple[tuple[str, int], ...]] = [
    (("D", 42),),
    (("Q", 7),),
    (("F", 42),),
    (("D", 42), ("A", 3)),
    (("D", 42), ("O", 2)),
    (("Q", 7), ("O", 1)),
    (("D", 42), ("E", 2)),
    (("D", 42), ("R", 4)),
    (("D", 42), ("L", 1)),
    (("D", 42), ("FT", 7)),
    (("D", 42), ("A", 3), ("CK", 2)),
    (("D", 42), ("A", 3), ("RD", 1)),
]


def _render_chain(chain: tuple[tuple[str, int], ...]) -> str:
    ref = codes.render(*chain[0])
    for prefix, n in chain[1:]:
        ref = codes.render_scoped(ref, prefix, n)
    return ref


@pytest.mark.parametrize("chain", _CHAINS, ids=lambda c: "_".join(p for p, _ in c))
def test_at_k2_parse_render_round_trip(chain: tuple[tuple[str, int], ...]) -> None:
    ref = _render_chain(chain)
    parsed = codes.parse(ref)
    assert parsed.parts == chain
    assert parsed.canonical == ref
    assert not parsed.is_foreign


def test_at_k2_examples_of_the_spec() -> None:
    assert codes.render("D", 907) == "D-0907"
    assert codes.render("F", 42) == "F-00042"
    assert codes.render_scoped("D-0042", "A", 3) == "D-0042_A-03"
    assert codes.render_scoped("D-0042_A-03", "CK", 2) == "D-0042_A-03_CK-002"
    assert codes.render_scoped("Q-0007", "O", 1) == "Q-0007_O-01"
    assert codes.foreign_ref("V1", "D907") == "V1_D907"
    parsed = codes.parse("D-0042_A-03_CK-002")
    assert (parsed.root, parsed.parent, parsed.leaf) == ("D-0042", "D-0042_A-03", ("CK", 2))


@given(
    prefix=st.sampled_from([p.prefix for p in SLICE_PREFIXES if not p.scoped_under]),
    data=st.data(),
)
def test_at_k2_round_trip_for_every_number(prefix: str, data: st.DataObject) -> None:
    width = prefix_spec(prefix).width
    n = data.draw(st.integers(min_value=1, max_value=10**width - 1))
    assert codes.parse(codes.render(prefix, n)).parts == ((prefix, n),)


def test_at_k2_unregistered_prefix_is_refused() -> None:
    for call in (
        lambda: codes.render("X", 1),
        lambda: codes.parse("X-0001"),
        lambda: codes.canonical("X907"),
        lambda: prefix_spec("ZZ"),
    ):
        with pytest.raises(Refused) as refused:
            call()
        assert refused.value.code is RefusalCode.PREFIX_UNKNOWN


@pytest.mark.parametrize(
    "text",
    [
        "Q-0007_A-01",
        "A-01",
        "D-907",
        "D-00907",
        "D-0000",
        "D-0042_CK-001",
        "D-0042:A-01",
        " D-0042",
    ],
)
def test_parse_refuses_what_is_not_canonical(text: str) -> None:
    with pytest.raises(NotFound):
        codes.parse(text)


def test_render_refuses_numbers_outside_the_width() -> None:
    for n in (0, -1, 10000, True):
        with pytest.raises(ContractViolation):
            codes.render("D", n)
    with pytest.raises(ContractViolation):
        codes.render_scoped("Q-0007", "A", 1)
    with pytest.raises(ContractViolation):
        codes.render_scoped("V1_D907", "A", 1)


# --------------------------------------------------------------------------------------------------
# AT-K3: tolerant input, canonical output


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("D907", "D-0907"),
        ("d907", "D-0907"),
        ("D 907", "D-0907"),
        ("d-907", "D-0907"),
        ("D0907", "D-0907"),
        ("D-0907", "D-0907"),
        ("Д907", "D-0907"),  # the Cyrillic letter De, from the ru pack
        ("д-907", "D-0907"),
        ("D907 A1", "D-0907_A-01"),
        ("D907_A1", "D-0907_A-01"),
        ("D907/A1", "D-0907_A-01"),
        ("D-0907_A01", "D-0907_A-01"),
        ("d907 a2", "D-0907_A-02"),
        ("D907 А 2", "D-0907_A-02"),  # a Cyrillic A
        ("D 42 A 3 CK 2", "D-0042_A-03_CK-002"),
        ("q7 o1", "Q-0007_O-01"),
        ("f42", "F-00042"),
        ("ф 10001", "F-10001"),  # the Cyrillic letter ef
        ("D４２", "D-0042"),  # full-width digits
    ],
)
def test_at_k3_tolerant_forms(text: str, expected: str) -> None:
    assert codes.canonical(text) == expected


def test_at_k3_output_is_always_canonical() -> None:
    for text in ("D907", "d 907", "D-0907_A01", "Д907 А1"):
        out = codes.canonical(text)
        assert codes.parse(out).canonical == out
        assert codes.canonical(out) == out


def test_look_alikes_follow_the_given_pack() -> None:
    with pytest.raises(NotFound):
        codes.canonical("Д907", look_alikes={})
    assert codes.canonical("Д907", look_alikes={"Д": "D"}) == "D-0907"


@pytest.mark.parametrize(
    "text", ["", "   ", "D", "907A", "D907 x", "D9 07", "hello", "D-0907:A-01"]
)
def test_tolerant_input_that_names_no_id(text: str) -> None:
    with pytest.raises((NotFound, Refused)):
        codes.canonical(text)


def test_too_many_digits_and_bad_scopes_name_no_id() -> None:
    with pytest.raises(NotFound):
        codes.canonical("D10907")
    with pytest.raises(NotFound):
        codes.canonical("Q7 A1")


def test_a_bare_number_is_ambiguous() -> None:
    with pytest.raises(Ambiguous) as amb:
        codes.canonical("907")
    assert amb.value.candidates == ("D-0907", "Q-0907", "F-00907")


def test_foreign_references() -> None:
    parsed = codes.parse("V1_D907")
    assert parsed.is_foreign
    assert (parsed.issuer, parsed.source_id) == ("V1", "D907")
    assert codes.parse("CF2LOG_D-037").canonical == "CF2LOG_D-037"
    assert codes.canonical("v1_d907") == "V1_D907"
    assert codes.canonical("V1 D907") == "V1_D907"
    assert codes.is_issuer_code("V1")
    assert codes.is_issuer_code("CF2LOG")
    assert not codes.is_issuer_code("D907")
    assert not codes.is_issuer_code("v1")
    with pytest.raises(ContractViolation):
        codes.foreign_ref("D907", "x")
    with pytest.raises(ContractViolation):
        codes.foreign_ref("V1", "D 907")


# --------------------------------------------------------------------------------------------------
# Aliases and resolve (IDN-9)


def test_aliases_resolve_in_the_documented_order(kstore: SqliteStore) -> None:
    with api.unit_of_work("tst", ctx(), command="alias"):
        aliases.add_alias("V1_D907", "D-0907", issuer="V1", kind="foreign")
        aliases.add_alias("V1_D907", "D-0907", issuer="V1", kind="foreign")  # idempotent
        aliases.add_alias("CF2LOG_D-037", "D-1004", issuer="CF2LOG", kind="foreign")
        with pytest.raises(ContractViolation, match="already points"):
            aliases.add_alias("v1 d907", "D-0908", issuer="V1", kind="foreign")
        with pytest.raises(ContractViolation):
            aliases.add_alias("V1_D909", "D907", issuer="V1", kind="foreign")
    with api.read_connection() as conn:
        assert aliases.resolve(conn, "D-0907") == "D-0907"
        assert aliases.resolve(conn, "d907 a1") == "D-0907_A-01"
        assert aliases.resolve(conn, "V1_D907") == "D-0907"
        assert aliases.resolve(conn, "v1/d907") == "D-0907"
        assert aliases.resolve(conn, "CF2LOG_D-037") == "D-1004"
        assert aliases.aliases_of(conn, "D-0907") == ["V1_D907"]
        with pytest.raises(NotFound):
            aliases.resolve(conn, "V1_D999")
        with pytest.raises(NotFound):
            aliases.resolve(conn, "not an id")
        with pytest.raises(Ambiguous):
            aliases.resolve(conn, "42")
        with pytest.raises(Refused):
            aliases.resolve(conn, "X42")
        assert conn.execute("SELECT count(*) FROM sys_id_aliases").fetchone()[0] == 2


def test_aliases_are_written_only_inside_a_unit(kstore: SqliteStore) -> None:
    with pytest.raises(ContractViolation):
        aliases.add_alias("V1_D907", "D-0907", issuer="V1", kind="foreign")
    with api.unit_of_work("tst", ctx(), command="alias"), pytest.raises(ContractViolation):
        aliases.add_alias("V1_D907", "D-0907", issuer="V1", kind="nickname")  # type: ignore[arg-type]
