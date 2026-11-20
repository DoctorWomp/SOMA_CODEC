"""docs/DECISIONS.md: the index table and the decision sections agree (G3g).

At G3f the index stopped at D-61 and still showed D-60 and D-61 as PROPOSED while their
sections said APPROVED. Every decision section needs one index row, every row a section, and
the status word (PROPOSED, APPROVED, REJECTED, SUPERSEDED) of a row must be its section's.
"""

from __future__ import annotations

import re
from pathlib import Path

DECISIONS = Path(__file__).resolve().parent.parent / "docs" / "DECISIONS.md"
STATUS_WORDS = ("PROPOSED", "APPROVED", "REJECTED", "SUPERSEDED")
ROW = re.compile(r"^\| (D-\d+) \| (.+?) \| (.+?) \|$")
HEADING = re.compile(r"^## (D-\d+) — ")
STATUS = re.compile(r"^\*\*Status:\*\* (.+)$")


def status_word(text: str) -> str | None:
    """The first status word of a status text ("APPROVED (owner, ...); proposed ..." -> APPROVED)."""
    found = [(text.find(w), w) for w in STATUS_WORDS if w in text]
    return min(found)[1] if found else None


def parse(text: str) -> tuple[dict[str, str], dict[str, str | None], list[str]]:
    rows: dict[str, str] = {}
    sections: dict[str, str | None] = {}
    problems: list[str] = []
    lines = text.splitlines()
    current = None
    for i, line in enumerate(lines):
        m = ROW.match(line)
        if m and current is None:
            if m.group(1) in rows:
                problems.append(f"{m.group(1)}: two index rows")
            rows[m.group(1)] = m.group(3)
            continue
        h = HEADING.match(line)
        if h:
            current = h.group(1)
            if current in sections:
                problems.append(f"{current}: two sections")
            sections[current] = None
            for follow in lines[i + 1:i + 4]:
                s = STATUS.match(follow)
                if s:
                    sections[current] = s.group(1)
                    break
    return rows, sections, problems


def index_problems(text: str) -> list[str]:
    rows, sections, problems = parse(text)
    for did, status in sections.items():
        if status is None:
            problems.append(f"{did}: its section has no **Status:** line")
            continue
        if did not in rows:
            problems.append(f"{did}: a section without an index row")
            continue
        if status_word(rows[did]) != status_word(status):
            problems.append(f"{did}: the index says {status_word(rows[did])}, its section {status_word(status)}")
    for did in rows:
        if did not in sections:
            problems.append(f"{did}: an index row without a section")
    return problems


def test_every_decision_has_one_index_row_with_its_status():
    problems = index_problems(DECISIONS.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_the_check_finds_a_stale_row_and_a_missing_one():
    text = ("| ID | Topic | Status |\n|---|---|---|\n| D-01 | One | PROPOSED (2026-11-17) |\n\n---\n\n"
            "## D-01 — One\n**Status:** APPROVED (owner, 2026-11-19); proposed 2026-11-17.\n\n"
            "## D-02 — Two\n**Status:** PROPOSED (2026-11-19).\n")
    problems = index_problems(text)
    assert "D-01: the index says PROPOSED, its section APPROVED" in problems
    assert "D-02: a section without an index row" in problems


def test_status_word_takes_the_first_word():
    assert status_word("APPROVED (owner, 2026-11-16); proposed 2026-11-16") == "APPROVED"
    assert status_word("REJECTED as the default (owner, 2026-11-20); kept as a condition, PROPOSED before") == "REJECTED"
    assert status_word("SUPERSEDED by D-36 (owner, 2026-11-14)") == "SUPERSEDED"
