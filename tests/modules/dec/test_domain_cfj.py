"""CFJ-1, salted hashes, the seal and the read side of integrity (spec §3.3; AT-K8).

AT-K8: ``cfj({"q1": 70, "q2": 20})`` is byte-identical to the forecast pilot's canonical form; the
pilot's ``sha256(salt + canonical)`` of a fixture seal verifies with ``unit_hash``; a float in a
basis raises ``TypeError``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from coflow.kernel.context import seeded_salts
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.domain.model import DecisionView
from tests.conftest import FixtureLoader
from tests.modules.dec.domain_builders import OP, ST, A, D, F, days, finish, sealed, with_head

# --------------------------------------------------------------------------------------------------
# AT-K8: byte identity with the forecast pilot


def test_cfj_is_byte_identical_to_the_pilot(fixtures: FixtureLoader) -> None:
    assert cfj.cfj({"q1": 70, "q2": 20}) == b'{"q1":70,"q2":20}'
    for rec in fixtures.json("domain/pilot_seals.json")["records"]:
        pilot = json.dumps(
            rec["record"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        assert cfj.cfj(rec["record"]) == pilot == rec["canonical"].encode("utf-8"), rec["name"]


def test_pilot_seals_verify_with_unit_hash(fixtures: FixtureLoader) -> None:
    for rec in fixtures.json("domain/pilot_seals.json")["records"]:
        assert cfj.unit_hash(rec["salt"], rec["record"]) == rec["sha256"], rec["name"]
        # the pilot's own shape: sha256(salt + canonical)
        raw = hashlib.sha256((rec["salt"] + rec["canonical"]).encode("utf-8")).hexdigest()
        assert raw == rec["sha256"]


@pytest.mark.parametrize("value", [1.5, 0.0, float("nan"), {"p": 0.7}, [1, 2.0]])
def test_a_float_is_refused(value: object) -> None:
    with pytest.raises(TypeError):
        cfj.cfj(value)


def test_a_float_in_a_basis_is_refused() -> None:
    d = D(1001, review_due=days(10))
    row = {**d.stored, "confidence": 0.7}
    with pytest.raises(TypeError):
        cfj.build_edition(
            public_id=d.public_id, n=1, decision=row, items=[], sealed_at="x", sealed_by="owner"
        )


# --------------------------------------------------------------------------------------------------
# CFJ-1 rules


def test_normalise_rules() -> None:
    assert cfj.normalise("é") == "é"  # NFC
    assert cfj.normalise(Decimal("150.50")) == "150.50"
    assert cfj.normalise(Decimal("1E+2")) == "100"
    assert cfj.normalise(date(2026, 11, 15)) == "2026-11-15"
    assert cfj.normalise(datetime(2026, 11, 15, 9, 30, tzinfo=UTC)) == "2026-11-15T09:30:00+00:00"
    assert cfj.normalise((1, "a", None, True)) == [1, "a", None, True]
    assert cfj.normalise({1: "x"}) == {"1": "x"}
    with pytest.raises(TypeError):
        cfj.normalise(Decimal("NaN"))
    with pytest.raises(TypeError):
        cfj.normalise(object())


def test_cfj_sorts_keys_keeps_unicode_and_has_no_spaces() -> None:
    assert cfj.cfj({"b": [1, {"z": 1, "y": "Grüße"}], "a": None}) == (
        '{"a":null,"b":[1,{"y":"Grüße","z":1}]}'.encode()
    )


def test_unit_hash_shape() -> None:
    salt = "ab" * 16
    expected = hashlib.sha256(salt.encode("ascii") + b'{"q1":70}').hexdigest()
    assert cfj.unit_hash(salt, {"q1": 70}) == expected


def test_basis_value_and_item_content_read_stored_rows() -> None:
    d = D(1001, review_due=days(10), unknowns=("one", "two"))
    assert cfj.basis_value(d.stored, "unknowns") == ["one", "two"]
    assert cfj.basis_value(d.stored, "reconstructed") == 0
    with pytest.raises(KeyError):
        cfj.basis_value(d.stored, "title")  # the naming layer is not basis
    row = {**finish(A(1)).stored, "is_critical": True}
    content = cfj.item_content("assumption", row, code="A-01")
    assert content["code"] == "A-01"
    assert content["is_critical"] == 1  # a boolean is hashed as SQLite stores it
    assert list(content) == list(cfj.ITEM_KEYS["assumption"])


# --------------------------------------------------------------------------------------------------
# The seal and integrity


def _decision() -> DecisionView:
    return D(
        1002,
        review_due=days(30),
        options=[OP("Rent the small room", chosen=True), OP("Keep the large room")],
        facts=[F(days(-21), "The landlord offered the small room", phase="ground")],
        assumptions=[A(1, statement="The landlord confirms by 10.11"), A(2)],
        stakes=[ST("120")],
    )


def test_build_edition_is_deterministic_under_seeded_salts() -> None:
    d = _decision()
    first = sealed(d)
    again = sealed(d)
    assert first.editions[0].seal_hash == again.editions[0].seal_hash
    e = first.editions[0]
    assert len(e.seal_hash) == 64
    items = json.loads(e.items_json)
    assert items == sorted(items)
    assert {i[0] for i in items} == {"option", "ground", "assumption", "stake"}
    assert list(json.loads(e.fields_json)) == sorted(cfj.BASIS_FIELDS)


def test_fresh_salts_differ_per_field() -> None:
    d = _decision()
    with seeded_salts("one"):
        e = cfj.build_edition(
            public_id="D-1002", n=1, decision=d.stored, items=[], sealed_at="t", sealed_by="o"
        )
    salts = json.loads(e.field_salts_json)
    assert len(set(salts.values())) == len(cfj.BASIS_FIELDS)


def test_a_sealed_edition_verifies() -> None:
    d = sealed(_decision())
    lines = cfj.integrity_lines(d)
    assert [(line.edition, line.status) for line in lines] == [(1, "ok")]
    assert lines[0].seal12 == d.editions[0].seal_hash[:12]
    assert cfj.integrity_report(d).ok


def test_a_basis_field_changed_outside_revise_is_live_drift() -> None:
    d = sealed(_decision())
    changed = with_head(d, statement="Rent the large room after all")
    lines = cfj.integrity_lines(changed)
    assert lines[0].edition == "live"
    assert lines[0].status == "drift"
    assert lines[0].items == ("statement",)
    assert any(line.edition == 1 and line.status == "ok" for line in lines)
    # the title is the naming layer, not basis: no drift
    assert all(line.status == "ok" for line in cfj.integrity_lines(with_head(d, title="Renamed")))


def test_an_edited_edition_is_changed() -> None:
    d = sealed(_decision())
    e = d.editions[0]
    fields = json.loads(e.fields_json)
    fields["statement"] = "something else"
    tampered = dataclasses.replace(e, fields_json=json.dumps(fields))
    lines = cfj.integrity_lines(dataclasses.replace(d, editions=(tampered,)))
    assert (lines[0].edition, lines[0].status, lines[0].items) == (1, "changed", ("statement",))

    reseal = dataclasses.replace(e, seal_hash="0" * 64)
    lines = cfj.integrity_lines(dataclasses.replace(d, editions=(reseal,)))
    assert (lines[0].status, lines[0].items) == ("changed", ("seal",))


def test_an_edited_item_is_changed_and_an_erased_one_is_ok_with_erasures() -> None:
    d = sealed(_decision())
    fact = d.facts[0]
    edited = dataclasses.replace(fact, stored={**fact.stored, "text": "rewritten"})
    lines = cfj.integrity_lines(dataclasses.replace(d, facts=(edited,)))
    assert (lines[0].status, lines[0].items) == ("changed", ("ground FT-001",))

    erased = dataclasses.replace(fact, erased_tx=7, salt="", stored={**fact.stored, "text": ""})
    lines = cfj.integrity_lines(dataclasses.replace(d, facts=(erased,)))
    assert [(line.edition, line.status) for line in lines] == [(1, "ok_with_erasures")]

    missing = cfj.integrity_lines(dataclasses.replace(d, stakes=()))
    assert missing[0].status == "changed"
    assert missing[0].items[0].startswith("stake ")


def test_an_erased_inline_field_keeps_the_seal_verifiable() -> None:
    d = sealed(_decision())
    e = d.editions[0]
    fields = json.loads(e.fields_json)
    salts = json.loads(e.field_salts_json)
    fields["statement"] = None
    salts["statement"] = ""
    erased = dataclasses.replace(
        e,
        fields_json=json.dumps(fields),
        field_salts_json=json.dumps(salts),
        erased_fields_json='["statement"]',
    )
    lines = cfj.integrity_lines(dataclasses.replace(d, editions=(erased,)))
    assert (lines[0].edition, lines[0].status) == (1, "ok_with_erasures")


def test_a_terminal_decision_has_no_drift_line() -> None:
    d = sealed(_decision())
    closed = with_head(d, status="closed", statement="changed after closing")
    assert [line.status for line in cfj.integrity_lines(closed)] == ["ok"]


def test_completion_pending_lists_what_waits_and_is_not_drift() -> None:
    d = sealed(D(1003, review_due=days(30), success_criterion=None))
    filled = with_head(d, completion_pending=True, success_criterion="counted by the owner")
    lines = cfj.integrity_lines(filled)
    assert [(line.edition, line.status) for line in lines] == [
        (1, "ok"),
        ("live", "completion_pending"),
    ]
    assert lines[1].items == ("success_criterion",)


# --------------------------------------------------------------------------------------------------
# A golden seal computed from the spec text alone (review finding: the envelope was only checked
# against the module itself, so a renamed key or a lost NFC step would have passed)


def _golden_spec_seal(g: dict[str, object]) -> dict[str, str]:
    """§3.3 ``seal`` re-done with json, hashlib and unicodedata only, from the fixture's inputs."""
    import unicodedata

    def norm(x: object) -> object:
        if isinstance(x, str):
            return unicodedata.normalize("NFC", x)
        if isinstance(x, list):
            return [norm(v) for v in x]
        if isinstance(x, dict):
            return {str(k): norm(v) for k, v in x.items()}
        return x

    def canon(x: object) -> bytes:
        return json.dumps(
            norm(x), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

    def uh(salt: str, content: object) -> str:
        return hashlib.sha256(salt.encode("ascii") + canon(content)).hexdigest()

    row: dict[str, object] = g["decision"]  # type: ignore[assignment]
    salts: dict[str, str] = g["field_salts"]  # type: ignore[assignment]
    fields = {
        k: json.loads(str(row["unknowns_json"])) if k == "unknowns" else row[k]
        for k in cfj.BASIS_FIELDS
    }
    hashes = {k: uh(salts[k], fields[k]) for k in cfj.BASIS_FIELDS}
    items = sorted(
        [
            i["kind"],
            i["code"],
            uh(i["salt"], {k: i["code"] if k == "code" else i["row"][k] for k in keys}),
        ]
        for i in g["items"]  # type: ignore[attr-defined]
        for keys in [cfj.ITEM_KEYS[i["kind"]]]
    )
    env = {
        "cv": 1,
        "decision": g["public_id"],
        "edition": g["n"],
        "field_hashes": hashes,
        "items": items,
        "sealed_at": g["sealed_at"],
        "sealed_by": g["sealed_by"],
    }
    return {
        "fields_json": canon(fields).decode("utf-8"),
        "field_salts_json": canon(salts).decode("utf-8"),
        "field_hashes_json": canon(hashes).decode("utf-8"),
        "items_json": canon(items).decode("utf-8"),
        "envelope": canon(env).decode("utf-8"),
        "seal_hash": hashlib.sha256(canon(env)).hexdigest(),
    }


COMBINING_ACUTE = "\u0301"


def test_the_golden_seal_fixture_follows_the_spec_text(fixtures: FixtureLoader) -> None:
    g = fixtures.json("domain/seal_golden.json")
    assert _golden_spec_seal(g) == g["expected"]
    assert COMBINING_ACUTE in g["decision"]["statement"]  # the input really is decomposed
    assert COMBINING_ACUTE not in g["expected"]["fields_json"]  # and the seal hashes its NFC form


def test_build_edition_reproduces_the_golden_seal_byte_for_byte(
    fixtures: FixtureLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    g = fixtures.json("domain/seal_golden.json")
    salts = iter(g["field_salts"][k] for k in cfj.BASIS_FIELDS)  # §3.3: one per field, in order
    monkeypatch.setattr(cfj, "new_salt", lambda: next(salts))
    items = [
        cfj.SealItem(kind=i["kind"], code=i["code"], row=i["row"], salt=i["salt"])
        for i in g["items"]
    ]
    draft = cfj.build_edition(
        public_id=g["public_id"],
        n=g["n"],
        decision=g["decision"],
        items=items,
        sealed_at=g["sealed_at"],
        sealed_by=g["sealed_by"],
    )
    want = g["expected"]
    assert draft.fields_json == want["fields_json"]
    assert draft.field_salts_json == want["field_salts_json"]
    assert draft.field_hashes_json == want["field_hashes_json"]
    assert draft.items_json == want["items_json"]
    assert draft.seal_hash == want["seal_hash"]
    envelope = cfj.seal_envelope(
        public_id=g["public_id"],
        n=g["n"],
        field_hashes=json.loads(draft.field_hashes_json),
        items=json.loads(draft.items_json),
        sealed_at=g["sealed_at"],
        sealed_by=g["sealed_by"],
    )
    assert cfj.cfj(envelope).decode("utf-8") == want["envelope"]
