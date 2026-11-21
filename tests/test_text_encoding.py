"""Every text file is read and written as UTF-8, on every platform.

Without ``encoding=``, Python uses the platform's default: UTF-8 on Linux and in CI, but the
ANSI code page (often cp1252) on Windows. Reports contain characters such as "–", so a report
written as UTF-8 and read back with the default came out as "â€“" on the owner's PC and failed
``test_report_leaves_out_void_rows_and_marks_pooled_ones`` there only (2026-11-21).
This test finds such calls before they reach Windows.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FOLDERS = ("range_service", "tools", "tests")


def _mode(call: ast.Call, position: int) -> str | None:
    """The mode of an open() call if it is a literal ("r" when absent), else None. ``position``:
    1 for the builtin open(file, mode), 0 for Path.open(mode)."""
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) else None
    if len(call.args) > position:
        arg = call.args[position]
        return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
    return "r"


def default_encoding_calls(source: str) -> list[int]:
    """Line numbers of read_text(), write_text() and text-mode open() calls without encoding=."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if any(k.arg == "encoding" or k.arg is None for k in node.keywords):   # encoding= or **kwargs
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
            found.append(node.lineno)
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = _mode(node, 1)
            if mode is not None and "b" not in mode:
                found.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == "open" and not isinstance(func.value, ast.Name):
            mode = _mode(node, 0)                                      # path.open(...), self.log_path.open(...)
            if mode is not None and "b" not in mode:
                found.append(node.lineno)
    return found


def test_the_scanner_catches_default_encodings():
    bad = 'p.read_text()\np.write_text("x")\nopen("f")\nopen("f", "w")\nself.p.open("a")\n'
    good = ('p.read_text(encoding="utf-8")\np.write_text("x", encoding="utf-8")\n'
            'open("f", "rb")\nopen("f", encoding="utf-8")\np.read_bytes()\nself.p.open("wb")\n')
    assert default_encoding_calls(bad) == [1, 2, 3, 4, 5]
    assert default_encoding_calls(good) == []


def test_no_text_io_relies_on_the_platform_encoding():
    problems = []
    for folder in FOLDERS:
        for path in sorted((REPO / folder).rglob("*.py")):
            for line in default_encoding_calls(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(REPO)}:{line}")
    assert not problems, "add encoding=\"utf-8\" (Windows defaults to its ANSI code page): " + ", ".join(problems)
