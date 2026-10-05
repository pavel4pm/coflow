"""Consistency check for the CoFlow 2.0 documents.

Checks that relative links resolve, every referenced requirement ID exists as a table row in
docs/REQUIREMENTS.md, every referenced decision ID exists in docs/DECISIONS.md, no ID is defined twice,
every non-"Later" requirement appears in docs/ROADMAP.md, no R2/Later item sits in stages 0-5, and no
gendered pronouns describe the owner. Exits non-zero on any problem.

Run from the repository root:  python tools/check_docs.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREFIXES = "CFG|IDN|PPL|SIG|DEC|CMT|MTG|WRK|RHY|LRN|BOT|MCP|UI|SRC|PRV|OPS|EXT|NFR|FIN|ALN|TML|REL|GOL|DEP|P"
RETIRED = {"OPS-9", "ALN-1", "WRK-7"}  # explained in REQUIREMENTS.md, never reissued
ROW_ID = re.compile(r"^\| ((?:[A-Z]{2,3})-\d+|P-\d+) \|", re.M)
ROW_PRIORITY = re.compile(r"^\| ((?:[A-Z]{2,3})-\d+) \| .*?\| (R1|R2|Plugin|Later) \|", re.M)
PRONOUNS = re.compile(r"\b(he|his|him|she|her)\b", re.I)


def refs(text: str) -> set[str]:
    found = set(re.findall(rf"\b((?:{PREFIXES})-\d+)\b", text))
    for prefix, first, last in re.findall(r"\b([A-Z]{1,3})-(\d+)…(\d+)", text):
        found |= {f"{prefix}-{i}" for i in range(int(first), int(last) + 1)}
    return found


def main() -> int:
    problems: list[str] = []
    req = (ROOT / "docs/REQUIREMENTS.md").read_text(encoding="utf-8")
    road = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    dec = (ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")
    defined = ROW_ID.findall(req)
    ids = set(defined)
    decisions = set(re.findall(r"^## (D-\d+)", dec, re.M))

    for dup in sorted({i for i in defined if defined.count(i) > 1}):
        problems.append(f"duplicate requirement ID {dup}")

    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for match in re.finditer(r"\]\(([^)#]+)(#[^)]*)?\)", text):
            target = match.group(1)
            if not target.startswith("http") and not (path.parent / target).exists():
                problems.append(f"{rel}: broken link {target}")
        for missing in sorted(refs(text) - ids - RETIRED):
            problems.append(f"{rel}: undefined requirement {missing}")
        for missing in sorted(set(re.findall(r"\bD-\d{3}\b", text)) - decisions):
            problems.append(f"{rel}: undefined decision {missing}")
        if PRONOUNS.search(text):
            problems.append(f"{rel}: gendered pronoun (use they/them for the owner)")

    priorities = dict(ROW_PRIORITY.findall(req))
    covered = refs(road)
    for rid, pri in priorities.items():
        if pri != "Later" and not rid.startswith("NFR") and rid not in covered:
            problems.append(f"ROADMAP: {rid} ({pri}) is not placed in any stage")
    early = road.split("### Stage 6")[0]
    for rid in sorted(refs(early)):
        if priorities.get(rid) in ("R2", "Later"):
            problems.append(f"ROADMAP: {rid} ({priorities[rid]}) appears in stages 0-5")

    for problem in problems:
        print(problem)
    print(f"{len(ids)} requirement IDs, {len(decisions)} decisions, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
