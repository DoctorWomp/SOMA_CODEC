"""Run the Godot project's automated checks in headless mode (G1, D-34).

    uv run python tools/godot_check.py                  # import the project, run all Godot tests
    uv run python tools/godot_check.py --filter sb05    # only tests whose name contains "sb05"
    uv run python tools/godot_check.py --require        # fail (instead of skip) if Godot is missing

Godot is found from, in order: the GODOT_BIN environment variable, the copy installed by
tools/install_godot.py (.tools/godot/), or `godot` / `godot4` on the PATH. On Windows,
GODOT_BIN must point at the *_console.exe build so its output reaches this script.

Steps:
  1. Version: the binary must be Godot 4.7.2 stable (D-06).
  2. Import: `--import` loads every script and resource, as opening the editor would.
  3. Tests:  runs godot_app/tests/test_main.tscn at a fixed 60 frames per simulated second.

Any engine or script ERROR line fails the check, even if every test passed.
Exit code: 0 passed, 1 failed, 2 skipped (Godot not found and --require not given).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.install_godot import installed_binary  # noqa: E402

PROJECT_DIR = REPO / "godot_app"
EXPECTED_VERSION_PREFIX = "4.7.2.stable"
TEST_SCENE = "res://tests/test_main.tscn"

EXIT_PASSED, EXIT_FAILED, EXIT_SKIPPED = 0, 1, 2

_ERROR_LINE = re.compile(r"^\s*(SCRIPT ERROR|USER SCRIPT ERROR|ERROR|Parse Error|USER ERROR)\b")
_WARNING_LINE = re.compile(r"^\s*(WARNING|USER WARNING|SCRIPT WARNING)\b")
_SUMMARY_LINE = re.compile(r"^G1 TESTS DONE passed=(\d+) failed=(\d+)\s*$")


@dataclass
class RunReport:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: tuple[int, int] | None = None

    @property
    def ok(self) -> bool:
        return (
            self.summary is not None
            and not self.failed
            and not self.errors
            and self.summary == (len(self.passed), 0)
            and len(self.passed) > 0
        )


def analyze(output: str) -> RunReport:
    """Read Godot's output: test results, the summary line, and any error or warning lines."""
    report = RunReport()
    for line in output.splitlines():
        if line.startswith("PASS "):
            report.passed.append(line[5:].split(" (")[0].strip())
        elif line.startswith("FAIL "):
            report.failed.append(line[5:].strip())
        elif _ERROR_LINE.match(line):
            report.errors.append(line.strip())
        elif _WARNING_LINE.match(line):
            report.warnings.append(line.strip())
        else:
            match = _SUMMARY_LINE.match(line.strip())
            if match:
                report.summary = (int(match.group(1)), int(match.group(2)))
    return report


def find_godot() -> str | None:
    env = os.environ.get("GODOT_BIN", "").strip().strip('"')
    if env:
        return env
    installed = installed_binary()
    if installed is not None:
        return str(installed)
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run(cmd: list[str], timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return -1, out + f"\nTIMEOUT after {timeout} s"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    require = "--require" in args
    test_filter = ""
    if "--filter" in args:
        i = args.index("--filter")
        test_filter = args[i + 1] if i + 1 < len(args) else ""

    godot = find_godot()
    if godot is None:
        print("  Godot not found. Set GODOT_BIN to the Godot 4.7.2 (console) executable,")
        print("  or run: uv run python tools/install_godot.py   (see docs/BUILD_AND_RUN.md)")
        return EXIT_FAILED if require else EXIT_SKIPPED
    if not Path(godot).is_file() and shutil.which(godot) is None:
        # Someone pointed GODOT_BIN somewhere on purpose; a wrong path is an error, not a skip.
        print(f"  FAIL  GODOT_BIN is set to {godot!r}, but no such file exists")
        return EXIT_FAILED

    code, out = _run([godot, "--headless", "--version"], timeout=60)
    version = out.strip().splitlines()[-1] if out.strip() else ""
    if code != 0 or not version.startswith(EXPECTED_VERSION_PREFIX):
        print(f"  FAIL  {godot} reports version {version!r}; this project needs {EXPECTED_VERSION_PREFIX} (D-06)")
        return EXIT_FAILED
    print(f"  Godot {version} at {godot}")

    code, out = _run([godot, "--headless", "--path", str(PROJECT_DIR), "--import"], timeout=600)
    import_report = analyze(out)
    if code != 0 or import_report.errors:
        print(f"  FAIL  project import (exit code {code})")
        for line in import_report.errors or out.strip().splitlines()[-20:]:
            print(f"        {line}")
        return EXIT_FAILED
    print("  project imported with no errors")

    cmd = [godot, "--headless", "--path", str(PROJECT_DIR), "--fixed-fps", "60", TEST_SCENE]
    if test_filter:
        cmd += ["--", f"--filter={test_filter}"]
    code, out = _run(cmd, timeout=900)
    report = analyze(out)
    for name in report.passed:
        print(f"  PASS  {name}")
    for item in report.failed:
        print(f"  FAIL  {item}")
    for line in report.errors:
        print(f"  ERROR {line}")
    for line in sorted(set(report.warnings)):
        print(f"  note  {line}")
    if report.summary is None:
        print(f"  FAIL  the test run did not finish (exit code {code}); last output:")
        for line in out.strip().splitlines()[-20:]:
            print(f"        {line}")
        return EXIT_FAILED
    if code != 0 or not report.ok:
        print(f"  {len(report.passed)} passed, {len(report.failed)} failed, {len(report.errors)} error line(s)")
        return EXIT_FAILED
    print(f"  {len(report.passed)} Godot tests passed")
    return EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
