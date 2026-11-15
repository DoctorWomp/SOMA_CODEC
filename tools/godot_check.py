"""Run the Godot project's automated checks in headless mode (G1, D-34).

    uv run python tools/godot_check.py                  # import the project, run all Godot tests
    uv run python tools/godot_check.py --filter sb05    # only tests whose name contains "sb05"
    uv run python tools/godot_check.py --require        # fail (instead of skip) if Godot is missing

Godot is found from, in order: the GODOT_BIN environment variable, the copy installed by
tools/install_godot.py (.tools/godot/), or `godot` / `godot4` on the PATH. On Windows,
GODOT_BIN must point at the *_console.exe build so its output reaches this script.

Steps:
  1. Version: the binary must be Godot 4.7.2 stable (D-06).
  2. Import:  `--import` imports the project's resources, as opening the editor would.
  3. Compile: loads every .gd file (godot_app/tests/compile_all.gd). GDScript warnings are
              errors in this project (D-38), so a new warning fails here.
  4. Tests:   runs godot_app/tests/test_main.tscn at a fixed 60 frames per simulated second.
  5. Outputs: every journal line, observation packet and action result the tests wrote, and
              every message that crossed the Python link, is validated against contracts/ in
              Python (D-41). No message to the sidecar may carry an NPC's private goal or any
              evaluator-only value (T17).

For the link tests, two sidecars run on 127.0.0.1 with a fresh session token for the duration
of the Godot tests: a normal one (which drops the connection once, to test reconnecting) and a
deliberately slow one.

Any engine or script ERROR line fails the check, even if every test passed.
Exit code: 0 passed, 1 failed, 2 skipped (Godot not found and --require not given).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.install_godot import installed_binary  # noqa: E402

PROJECT_DIR = REPO / "godot_app"
EXPECTED_VERSION_PREFIX = "4.7.2.stable"
TEST_SCENE = "res://tests/test_main.tscn"
COMPILE_SCRIPT = "res://tests/compile_all.gd"

EXIT_PASSED, EXIT_FAILED, EXIT_SKIPPED = 0, 1, 2

_ERROR_LINE = re.compile(r"^\s*(SCRIPT ERROR|USER SCRIPT ERROR|ERROR|Parse Error|USER ERROR)\b")
_WARNING_LINE = re.compile(r"^\s*(WARNING|USER WARNING|SCRIPT WARNING)\b")
_SUMMARY_LINE = re.compile(r"^G1 TESTS DONE passed=(\d+) failed=(\d+)\s*$")
_COMPILE_LINE = re.compile(r"^COMPILE DONE scripts=(\d+) failed=(\d+)\s*$")


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


def compile_report(output: str) -> tuple[int, list[str]]:
    """Number of scripts compiled (-1 if the run did not finish) and the problems found."""
    scripts = -1
    problems: list[str] = []
    for line in output.splitlines():
        match = _COMPILE_LINE.match(line.strip())
        if match:
            scripts = int(match.group(1))
        elif line.startswith("COMPILE FAIL ") or _ERROR_LINE.match(line):
            problems.append(line.strip())
    return scripts, problems


# Files the full test run must leave behind (a filtered run may write fewer).
EXPECTED_ARTIFACTS = ("sampling.jsonl", "sampling.observations.json", "demo_a.jsonl", "demo_b.jsonl",
                      "gate.action_results.json", "sidecar/sidecar_received.jsonl", "sidecar/sidecar_sent.jsonl")

# The two sidecars started for the Godot link tests: name, extra arguments.
SIDECARS = {
    "RANGE_LINK_PORT": ["--agent", "robot_legged=probe", "--agent", "robot_quadruped=greeter", "--drop-after", "25"],
    "RANGE_LINK_PORT_SLOW": ["--agent", "robot_legged=greeter", "--delay-ms", "1500"],
}


def private_strings() -> list[str]:
    """Text that must never reach an agent: NPC private goals and scenario evaluator-only values."""
    from range_service.configs import load_and_check

    config_set, _ = load_and_check()
    found = []
    for persona in config_set.items["personas"].values():
        if persona.get("private_goal"):
            found.append(str(persona["private_goal"]))
    for scenario in config_set.items["scenarios"].values():
        for value in scenario.get("evaluator_only", {}).values():
            if isinstance(value, str) and " " in value and len(value) >= 12:   # sentences, not single ids
                found.append(value)
    return found


def validate_artifacts(folder: Path, require_all: bool = True) -> tuple[int, list[str]]:
    """Check Godot's journals (*.jsonl) and packet dumps (*.observations.json) against the
    contracts. Returns (number of records checked, problems)."""
    from range_service import contracts

    problems: list[str] = []
    checked = 0
    if require_all:
        for name in EXPECTED_ARTIFACTS:
            if not (folder / name).is_file():
                problems.append(f"{name} was not written by the Godot tests")
    for path in sorted(folder.glob("*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            checked += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name} line {number}: not JSON ({exc})")
                continue
            for p in contracts.problems("journal_entry", entry)[:3]:
                problems.append(f"{path.name} line {number}: {p}")
            if entry.get("seq") != number - 1:
                problems.append(f"{path.name} line {number}: seq is {entry.get('seq')}, expected {number - 1}")
    for path in sorted(folder.glob("*.observations.json")):
        for index, packet in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            checked += 1
            for p in contracts.problems("observation", packet)[:3]:
                problems.append(f"{path.name} packet {index}: {p}")
    for path in sorted(folder.glob("*.action_results.json")):
        for index, result in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            checked += 1
            for p in contracts.problems("action_result", result)[:3]:
                problems.append(f"{path.name} result {index}: {p}")
    secrets_list = private_strings()
    for path in sorted(folder.glob("sidecar*/sidecar_*.jsonl")):
        if "deliberately_invalid" in path.name:
            continue
        rel = f"{path.parent.name}/{path.name}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            checked += 1
            record = json.loads(line)
            if path.name == "sidecar_problems.jsonl":
                problems.append(f"{rel}: the sidecar refused something Godot sent: {record['problem']}")
                continue
            schema = "action_result" if path.name == "sidecar_results.jsonl" else "envelope"
            for p in contracts.problems(schema, record)[:3]:
                problems.append(f"{rel} line {number}: {p}")
            if path.name == "sidecar_received.jsonl":
                for secret in secrets_list:
                    if secret in line:
                        problems.append(f"{rel} line {number}: private text reached the sidecar (T17): {secret[:40]!r}")
    return checked, problems


def start_sidecars(record_root: Path, token: str) -> tuple[list[subprocess.Popen], dict[str, str]]:
    """Start the test sidecars; returns the processes and the environment for Godot."""
    procs, env = [], {}
    for env_name, extra in SIDECARS.items():
        folder = record_root / ("sidecar" if env_name == "RANGE_LINK_PORT" else "sidecar_slow")
        proc = subprocess.Popen([sys.executable, "-m", "range_service.link", "--record", str(folder), *extra],
                                cwd=REPO, env=dict(os.environ, RANGE_SESSION_TOKEN=token),
                                stdout=subprocess.PIPE, text=True)
        procs.append(proc)
        line = proc.stdout.readline().strip()
        if not line.startswith("LISTENING "):
            raise RuntimeError(f"the test sidecar did not start ({line!r})")
        env[env_name] = line.rsplit(":", 1)[1]
    return procs, env


def stop_sidecars(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


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


def _run(cmd: list[str], timeout: int, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=None if env is None else dict(os.environ, **env))
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

    code, out = _run([godot, "--headless", "--path", str(PROJECT_DIR), "--script", COMPILE_SCRIPT], timeout=300)
    scripts, problems = compile_report(out)
    if code != 0 or scripts < 0 or problems:
        print(f"  FAIL  compiling the GDScript files (exit code {code}); GDScript warnings count as errors (D-38)")
        for line in problems or out.strip().splitlines()[-20:]:
            print(f"        {line}")
        return EXIT_FAILED
    print(f"  {scripts} GDScript files compiled with no errors or warnings")

    artifacts = Path(tempfile.mkdtemp(prefix="godot_artifacts_"))
    cmd = [godot, "--headless", "--path", str(PROJECT_DIR), "--fixed-fps", "60", TEST_SCENE,
           "--", f"--artifacts-dir={artifacts.as_posix()}"]
    if test_filter:
        cmd.append(f"--filter={test_filter}")
    token = secrets.token_hex(24)
    try:
        sidecars, link_env = start_sidecars(artifacts, token)
    except RuntimeError as exc:
        print(f"  FAIL  {exc}")
        return EXIT_FAILED
    try:
        code, out = _run(cmd, timeout=900, env=dict(link_env, RANGE_SESSION_TOKEN=token))
    finally:
        stop_sidecars(sidecars)
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
        shutil.rmtree(artifacts, ignore_errors=True)
        return EXIT_FAILED
    print(f"  {len(report.passed)} Godot tests passed")

    checked, problems = validate_artifacts(artifacts, require_all=not test_filter)
    shutil.rmtree(artifacts, ignore_errors=True)
    if problems:
        print(f"  FAIL  {len(problems)} problem(s) in what Godot wrote (journals and observation packets):")
        for line in problems[:20]:
            print(f"        {line}")
        return EXIT_FAILED
    print(f"  {checked} journal lines, packets, action results and link messages match the contracts")
    return EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
