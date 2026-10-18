"""The literal gate finds every category and leaves the repository's legitimate literals alone.

Planted literals are invented and assembled at run time, so this file itself never contains one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

GATE_PATH = Path(__file__).resolve().parents[2] / "tools" / "literal_gate.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("literal_gate", GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["literal_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = _load()
AT = "@"
DOT = "."
BS = "\\"


def categories(line: str, **kwargs: object) -> set[str]:
    return {category for category, _ in gate.scan_line(line, **kwargs)}


@pytest.mark.parametrize(
    ("line", "category"),
    [
        (f"write to someone{AT}mailhost{DOT}de", "email"),
        ("call +" + "1 202 " + "555 0143", "phone"),
        ("tel:+" + "1202" + "5550143", "phone"),
        ("555" + "-123-4567", "phone"),
        (f"https://files{DOT}acme-widgets{DOT}io/x", "domain"),
        (f"open files{DOT}acme-widgets{DOT}io today", "domain"),
        ("10" + ".1.2.3", "ipv4"),
        ("http://" + "nas7:8080/", "private-host"),
        (f"laptop{DOT}local", "private-host"),
        (f"box{DOT}tail1234{DOT}ts{DOT}net", "private-host"),
        ("DESKTOP-" + "AB12CD3", "private-host"),
        (BS * 2 + "fileserver" + BS + "share", "private-host"),
        (f"ssh owner{AT}" + "nas7", "private-host"),
        ("C:" + BS + "Users" + BS + "Zander" + BS + "AppData", "home-path"),
        ("/home/" + "zander/data", "home-path"),
    ],
)
def test_planted_literals_are_found(line: str, category: str) -> None:
    assert category in categories(line)


@pytest.mark.parametrize(
    "line",
    [
        f"you{AT}example.com and 12345+user{AT}users.noreply.github.com",
        f"git{AT}github.com:org/repo.git",
        "https://docs.astral.sh/uv/ and https://github.com/org/repo",
        "http://127.0.0.1:8000/mcp, 0.0.0.0, 192.0.2.10, 203.0.113.7",
        "coflow://<instance_id>/dec",
        "coflow.app, .claude/settings.local.json, pyproject.toml, README.md, datetime.date",
        "2026-11-15 D-0907_A-03_CK-002 version 2.32.3 sha256:00ff",
        "image: ghcr.io/<org>/coflow@sha256:<release-digest>",
        "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        f"ssh -i <mcp-key> coflow-mcp{AT}coflow-host",
        '"timezone": "Europe/Berlin", "+1 day"',
        "C:" + BS + "Users" + BS + "<user>" + BS + "AppData and /home/runner/work",
        "pinned at v1.2.3.4",
    ],
)
def test_legitimate_literals_pass(line: str) -> None:
    assert categories(line) == set()


def test_names_are_checked_in_fixtures_only() -> None:
    names = frozenset({"Example Landlord Ltd"})
    fixture = "tests/fixtures/synthetic/snapshots/s1.json"
    planted = '{"title": "' + "Quill" + " Zander" + '"}'
    assert [f.category for f in gate.scan_text(fixture, planted, names)] == ["name"]
    cyrillic = '{"who": "' + "Пример" + '"}'
    assert [f.category for f in gate.scan_text(fixture, cyrillic, names)] == ["name"]
    clean = '{"title": "Cut fixed costs", "who": "Person A", "c": "Example Landlord Ltd"}'
    assert gate.scan_text(fixture, clean, names) == []
    assert gate.scan_text("docs/notes.md", planted, names) == []


def test_findings_are_masked() -> None:
    literal = f"someone{AT}mailhost{DOT}de"
    finding = gate.Finding("a.txt", 3, "email", literal)
    assert finding.render() == "a.txt:3: email: som" + "*" * (len(literal) - 3)


# --------------------------------------------------------------------------------------------------
# The owner's deny-list (P-12; review finding: it was described but did not exist)


def _deny_file(tmp_path: Path, phrases: list[str]) -> Path:
    key_file = tmp_path / "keys" / "deny.key"
    key_file.parent.mkdir()
    key_file.write_bytes(b"synthetic-test-key")
    deny = gate.DenyList(key=b"synthetic-test-key", digests=frozenset())
    digests = sorted({deny.digest(g) for p in phrases for g in [gate.deny_normalise(p)]})
    path = tmp_path / "deny.json"
    path.write_text(
        gate.json.dumps({"key_file": str(key_file), "digests": digests}), encoding="utf-8"
    )
    return path


def test_a_denied_phrase_is_found_in_any_file_and_masked(tmp_path: Path) -> None:
    phrase = "Quill" + "wort " + "Larch" + "mere"  # invented, assembled at run time
    deny = gate.load_deny_list(_deny_file(tmp_path, [phrase, "zz" + "qq" + "xx"]))
    assert len(deny.digests) == 2
    text = f'x = 1\n    """moving to the  {phrase.upper()} studio"""\n'
    findings = gate.scan_text("src/coflow/anything.py", text, deny=deny)
    assert [(f.line, f.category) for f in findings] == [(2, "deny")]
    assert findings[0].render() == "src/coflow/anything.py:2: deny: qui" + "*" * (len(phrase) - 3)
    assert gate.scan_text("docs/notes.md", "zz" + "qq" + "xx", deny=deny)[0].category == "deny"
    assert gate.scan_text("docs/notes.md", "nothing to see", deny=deny) == []


def test_grams_are_one_to_four_tokens_of_six_characters_or_more() -> None:
    grams = list(gate.deny_grams("Ab cd, EFGHIJ kl mn op qr"))
    assert "efghij" in grams
    assert "ab cd efghij" in grams
    assert "ab cd efghij kl" in grams
    assert "ab cd" not in grams  # five characters
    assert not any(len(g.split()) > 4 for g in grams)
    decomposed = "cafe" + chr(0x0301) + " corner"
    assert gate.deny_normalise(decomposed) == gate.deny_normalise("caf" + chr(0xE9) + " CORNER")


def test_the_deny_list_is_skipped_unless_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(gate.DENY_ENV, raising=False)
    assert gate.main([]) == 0
    assert "deny-list" not in capsys.readouterr().out
    path = _deny_file(tmp_path, ["zz" + "qq" + "xx"])
    monkeypatch.setenv(gate.DENY_ENV, str(path))
    assert gate.main([]) == 0
    assert "deny-list of 1 digests" in capsys.readouterr().out


def test_a_key_inside_the_repository_is_refused(tmp_path: Path) -> None:
    inside = gate.ROOT / "tests" / "fixtures" / "synthetic" / "allowed_names.txt"
    path = tmp_path / "deny.json"
    path.write_text(gate.json.dumps({"key_file": str(inside), "digests": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="inside the repository"):
        gate.load_deny_list(path)
