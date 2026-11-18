"""Run the Godot project's automated checks in headless mode (G1, D-34).

    uv run python tools/godot_check.py                  # import the project, run all Godot tests
    uv run python tools/godot_check.py --filter sb05    # only tests whose name contains "sb05"
    uv run python tools/godot_check.py --require        # fail (instead of skip) if Godot is missing
    uv run python tools/godot_check.py --filter determinis --repeat 5 --cpu-load 4
        # run the determinism tests 5 times while 4 busy processes load the CPU (D-47)

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
              Python (D-41). No message to the sidecar and no agent context may carry an NPC's
              private goal or any evaluator-only value (T17).
  6. Scenarios (G3a, D-48): SB-04 and SB-05 run end to end from their files through
              tools/run_scenario.py's runner, in stepped mode. SB-04 runs three times: the
              second time with random delays in the sidecar, the third with posing off
              (--no-pose, D-54), and all three must write the same journal bytes.
              G3c-1 (D-59): SB-04 three more times with NPCs model-driven by the fake model
              (one with random sidecar delays), then replayed from its decision records: all
              four journals the same. The canary runs SB-04 and SB-05 with a unique marker in
              every private goal and evaluator label: an NPC's own marker only in its own
              labelled prompt line, no marker anywhere else; every agent's contexts only mention
              tracks from its own observation packets.
              G3c-2 (D-61): the pulse scenarios SB-06 (long wait), SB-07 (empty hall) and SB-08
              (peripheral speaker) three times each (one with random sidecar delays): one journal
              per scenario; SB-06 again with the fake model and replayed. Their pulse metrics
              must show the expected behavior (FN-1, FN-2, few calls while waiting, no pacing).
              Runs with --filter only if the filter is part of "scenario_determinism".

For the link tests, two sidecars run on 127.0.0.1 with a fresh session token for the duration
of the Godot tests: a normal one (which drops the connection once, to test reconnecting) and a
deliberately slow one.

`--repeat N` runs step 4 (and 5) N times; `--cpu-load K` keeps K busy processes running
meanwhile. CI uses both on the determinism tests: a run that depends on thread timing only
differs now and then, and mostly under load (D-47).

Any engine or script ERROR line fails the check, even if every test passed.
Exit code: 0 passed, 1 failed, 2 skipped (Godot not found and --require not given).
"""

from __future__ import annotations

import json
import multiprocessing
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
EXPECTED_ARTIFACTS = ("sampling.jsonl", "sampling.observations.json", "demo_a.jsonl", "demo_b.jsonl", "demo_c.jsonl",
                      "gate.action_results.json", "sidecar/sidecar_received.jsonl", "sidecar/sidecar_sent.jsonl")

# The two sidecars started for the Godot link tests: name, extra arguments.
SIDECARS = {
    "RANGE_LINK_PORT": ["--agent", "robot_legged=probe", "--agent", "robot_quadruped=greeter", "--drop-after", "25"],
    "RANGE_LINK_PORT_SLOW": ["--agent", "robot_legged=greeter", "--delay-ms", "7000"],   # past the 6.5 s stale window
    # G3a/G3b: agent runtimes for SB-04 whose model takes 1.5 s per call (T25, T27), through the real
    # llama-server provider code path: the stand-in server (range_service/agents/standin.py) plays a
    # slow llama-server; {standin} is replaced with its port.
    "RANGE_LINK_PORT_MODEL": ["--scenario", "SB04_POLITE_BID", "--model", "llama-attach:{standin}"],
}
SIDECAR_FOLDERS = {"RANGE_LINK_PORT": "sidecar", "RANGE_LINK_PORT_SLOW": "sidecar_slow",
                   "RANGE_LINK_PORT_MODEL": "sidecar_model"}


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


OWN_GOAL_LABEL = "Your own private goal (known only to you): "


def own_goal_owners() -> dict[str, str]:
    """private goal -> the display name of the persona it belongs to (D-51: it may appear in that
    persona's own prompt, labelled, and nowhere else)."""
    from range_service.configs import load_and_check

    config_set, _ = load_and_check()
    return {str(p["private_goal"]): p["display_name"] for p in config_set.items["personas"].values()
            if p.get("private_goal")}


def is_own_goal(prompt: str, secret: str, owners: dict[str, str]) -> bool:
    """True when ``secret`` is a private goal that appears in ``prompt`` only on its owner's own
    labelled line, and the prompt is that owner's (D-51, G3c-1)."""
    owner = owners.get(secret)
    if owner is None or f"You are {owner} (" not in prompt.split("## IDENTITY", 1)[-1][:200]:
        return False
    return prompt.count(secret) == prompt.count(OWN_GOAL_LABEL + secret) == 1


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
    c, found = check_agent_records(folder)
    checked += c
    problems += found
    # G3b: the slow-model run (T25, T27) must really have gone through the llama-server provider.
    model_records = folder / "sidecar_model" / "decision_records.jsonl"
    if model_records.is_file():
        providers = {call["provider"] for line in model_records.read_text(encoding="utf-8").splitlines()
                     for call in json.loads(line).get("model_calls", [])}
        if providers != {"LLAMA_SERVER"}:
            problems.append(f"sidecar_model: model calls went through {sorted(providers) or 'no provider'}, "
                            "expected only LLAMA_SERVER (the stand-in server played by tools/godot_check.py)")
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


def check_agent_records(folder: Path) -> tuple[int, list[str]]:
    """Decision records match their contract; no assembled context carries private text (T17)."""
    from range_service import contracts

    checked, problems = 0, []
    secrets_list = private_strings()
    owners = own_goal_owners()
    for path in sorted(folder.glob("**/decision_records.jsonl")):
        rel = path.relative_to(folder).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            checked += 1
            for p in contracts.problems("decision_record", json.loads(line))[:3]:
                problems.append(f"{rel} line {number}: {p}")
    for path in sorted(folder.glob("**/prompts.jsonl")):
        rel = path.relative_to(folder).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            checked += 1
            prompt = json.loads(line)["prompt"]
            for secret in secrets_list:
                if secret in prompt and not is_own_goal(prompt, secret, owners):
                    problems.append(f"{rel} line {number}: private text in an agent's context (T17): {secret[:40]!r}")
    return checked, problems


def start_sidecars(record_root: Path, token: str) -> tuple[list[subprocess.Popen], dict[str, str]]:
    """Start the test sidecars (and the slow stand-in model server they use); returns the processes
    and the environment for Godot."""
    procs, env = [], {}
    model_key = secrets.token_urlsafe(32)
    standin = subprocess.Popen([sys.executable, "-m", "range_service.agents.standin", "--mode", "slow", "--delay-ms", "1500"],
                               cwd=REPO, env=dict(os.environ, RANGE_STANDIN_API_KEY=model_key),
                               stdout=subprocess.PIPE, text=True)
    procs.append(standin)
    line = standin.stdout.readline().strip()
    if not line.startswith("LISTENING "):
        raise RuntimeError(f"the stand-in model server did not start ({line!r})")
    standin_port = line.rsplit(":", 1)[1]
    for env_name, extra in SIDECARS.items():
        folder = record_root / SIDECAR_FOLDERS[env_name]
        args = [a.replace("{standin}", standin_port) for a in extra]
        proc = subprocess.Popen([sys.executable, "-m", "range_service.link", "--record", str(folder), *args],
                                cwd=REPO, env=dict(os.environ, RANGE_SESSION_TOKEN=token, RANGE_LLAMA_API_KEY=model_key),
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

    repeat = _int_option(args, "--repeat", 1)
    load_procs = _start_cpu_load(_int_option(args, "--cpu-load", 0))
    try:
        for attempt in range(1, repeat + 1):
            if repeat > 1:
                print(f"  run {attempt} of {repeat}" + (f" with {len(load_procs)} busy processes" if load_procs else ""))
            result = run_tests(godot, test_filter)
            if result != EXIT_PASSED:
                return result
            if not test_filter or test_filter in "scenario_determinism":
                result = scenario_checks(godot)
                if result != EXIT_PASSED:
                    return result
    finally:
        _stop_cpu_load(load_procs)
    return EXIT_PASSED


def _int_option(args: list[str], name: str, default: int) -> int:
    if name not in args:
        return default
    i = args.index(name)
    try:
        return max(0, int(args[i + 1]))
    except (IndexError, ValueError):
        raise SystemExit(f"{name} needs a whole number")


def _busy() -> None:
    while True:
        pass


def _start_cpu_load(count: int) -> list[multiprocessing.Process]:
    procs = [multiprocessing.Process(target=_busy, daemon=True) for _ in range(count)]
    for proc in procs:
        proc.start()
    return procs


def _stop_cpu_load(procs: list[multiprocessing.Process]) -> None:
    for proc in procs:
        proc.terminate()
    for proc in procs:
        proc.join(timeout=10)


def _scenario_run(godot: str, scenario_id: str, out: Path, jitter_ms: int = 0, posing: bool = True,
                  model: str = "none", configs=None):
    import asyncio

    from range_service.eval.runner import RunOptions, run_scenario
    return asyncio.run(run_scenario(RunOptions(scenario_id, godot, out_dir=out, jitter_ms=jitter_ms, timeout_s=600,
                                               posing=posing, model=model, configs=configs)))


def _sent(run_dir: Path, agent: str) -> list[dict]:
    out = []
    for line in (run_dir / "sidecar" / "sidecar_sent.jsonl").read_text(encoding="utf-8").splitlines():
        env = json.loads(line)
        if env["type"] == "agent.action_request" and env["payload"]["agent_id"] == agent:
            out.append(dict(env["payload"], tick=env["tick_id"]))
    return out


def pulse_checks(godot: str, root: Path) -> tuple[list[str], str]:
    """G3c-2: the pulse scenarios are deterministic and show what PULSE_PROTOCOL §10 asks for."""
    problems: list[str] = []
    notes = []
    for scenario_id in ("SB06_LONG_WAIT", "SB07_EMPTY_HALL", "SB08_PERIPHERAL_SPEAKER"):
        runs = [_scenario_run(godot, scenario_id, root / f"{scenario_id}_{k}", jitter) for k, jitter in enumerate((0, 25, 0))]
        hashes = {r.journal_sha256 for r in runs}
        if len(hashes) != 1:
            problems.append(f"{scenario_id} is not deterministic with the pulse on: {sorted(h[:12] for h in hashes if h)}")
        r = runs[0]
        s = r.summary
        if r.exit_code != 0 or r.godot_errors or s["sidecar_problems"] or s["step_timeouts"] or s["tape"]["refused"]:
            problems.append(f"{scenario_id}: exit {r.exit_code}, errors {r.godot_errors[:2]}, sidecar {s['sidecar_problems'][:2]}, "
                            f"refused tape {s['tape']['refused'][:1]}")
        _, found = check_agent_records(r.run_dir)
        problems += [f"{scenario_id}: {p}" for p in found]
        m = s.get("pulse", {}).get("robot_r")
        if m is None:
            problems.append(f"{scenario_id}: no pulse metrics (is the pulse on?)")
            continue
        if m["fn1_violations"]:
            problems.append(f"{scenario_id}: Robot R left an open conversation without closing it (FN-1)")
        if m["zombie"]["ms"] > 0:
            problems.append(f"{scenario_id}: zombie time {m['zombie']['ms']} ms (something relevant got no response)")
        speech = [a for a in _sent(r.run_dir, "robot_r") if a["action"] == "SPEAK"]
        if scenario_id == "SB06_LONG_WAIT":
            waiting = [a for a in speech if 6 * 10 * 6 < a["tick"] < 1840 * 6]      # after the promise, before Y returns
            if s["agents"]["robot_r"]["open_commitments"] != 0 or len(speech) < 2:
                problems.append("SB-06: Robot R should promise to wait and then help Y")
            if waiting:
                problems.append(f"SB-06: Robot R interrupted Y while Y was busy: {waiting[0]['args'].get('text')!r}")
            if m["decisions"] > 10 or m["continues"] < 3 or m["glances"] < 3:
                problems.append(f"SB-06: expected few decisions, quiet CONTINUEs and glances while waiting: {m}")
        if scenario_id == "SB07_EMPTY_HALL":
            moves = [json.loads(line) for line in (r.run_dir / "pulse.jsonl").read_text(encoding="utf-8").splitlines()]
            cells = [(e["at_ms"], (e["destination"]["x"], e["destination"]["z"])) for e in moves if e["event"] == "SURVEY"]
            paced = [c for i, (t0, c) in enumerate(cells) for t1, c2 in cells[:i] if c2 == c and t0 - t1 < 90_000]
            if m["survey_moves"] < 5 or m["returns_to_post"] < 1 or paced or speech:
                problems.append(f"SB-07: expected a survey without pacing, a return to post and no speech "
                                f"(moves {m['survey_moves']}, returns {m['returns_to_post']}, paced {paced[:2]})")
        if scenario_id == "SB08_PERIPHERAL_SPEAKER":
            lat = m["glance_latency_ms"]["max"]
            answered = [a for a in speech if a["tick"] >= 660 * 6]
            if lat is None or lat > 500 or m["glances"] < 1:
                problems.append(f"SB-08: a glance toward a new speaker should follow within 0.5 s (max {lat})")
            if not answered:
                problems.append("SB-08: Robot R should answer the question addressed to it")
            if [a for a in speech if a["tick"] < 660 * 6]:
                problems.append("SB-08: Robot R spoke before it was addressed (talk between visitors is not for it)")
        notes.append(f"{scenario_id} {r.journal_sha256[:12]}")
    fake = [_scenario_run(godot, "SB06_LONG_WAIT", root / f"SB06_fake_{k}", jitter, model="fake") for k, jitter in enumerate((0, 25))]
    records = root / "SB06_fake_0" / "sidecar" / "decision_records.jsonl"
    fake.append(_scenario_run(godot, "SB06_LONG_WAIT", root / "SB06_fake_replay", model=f"replay:{records}"))
    if len({r.journal_sha256 for r in fake}) != 1:
        problems.append("SB-06 with the fake model and the pulse is not deterministic or not replayable: "
                        f"{[(r.journal_sha256 or '')[:12] for r in fake]}")
    for r in fake:
        _, found = check_agent_records(r.run_dir)
        problems += [f"SB06 fake: {p}" for p in found]
    return problems, "; ".join(notes) + f"; SB06 fake model {(fake[0].journal_sha256 or '')[:12]} x2 and replayed"


def npc_model_checks(godot: str, root: Path) -> tuple[list[str], str]:
    """G3c-1: NPCs model-driven (fake model) are deterministic and replayable; the canary finds
    no private goal or evaluator label outside an NPC's own labelled prompt line."""
    from range_service import contracts
    from range_service.configs import load_and_check
    from range_service.eval import canary
    from range_service.eval.runner import read_journal

    problems: list[str] = []
    runs = {}
    for name, jitter in (("SB04_npc_a", 0), ("SB04_npc_b", 25), ("SB04_npc_c", 0)):
        runs[name] = _scenario_run(godot, "SB04_POLITE_BID", root / name, jitter, model="fake")
    records = root / "SB04_npc_a" / "sidecar" / "decision_records.jsonl"
    runs["SB04_npc_replay"] = _scenario_run(godot, "SB04_POLITE_BID", root / "SB04_npc_replay", model=f"replay:{records}")
    hashes = {name: r.journal_sha256 for name, r in runs.items()}
    if len(set(hashes.values())) != 1:
        problems.append(f"SB-04 with model-driven NPCs is not deterministic or not replayable: "
                        f"{ {k: (v or '')[:12] for k, v in hashes.items()} }")
    for name, r in runs.items():
        s = r.summary
        if r.exit_code != 0 or r.godot_errors or s["sidecar_problems"] or s["step_timeouts"]:
            problems.append(f"{name}: exit {r.exit_code}, errors {r.godot_errors[:2]}, sidecar {s['sidecar_problems'][:2]}")
        if any(st["fallbacks"] for st in s["agents"].values()):
            problems.append(f"{name}: model fallbacks {[(a, st['fallbacks']) for a, st in s['agents'].items()]}")
        fn1 = (s.get("pulse") or {}).get("robot_r", {}).get("fn1_violations")
        if fn1:
            problems.append(f"{name}: Robot R left an open conversation without a closing line {fn1} time(s) (FN-1)")
        _, found = check_agent_records(r.run_dir)
        problems += [f"{name}: {p}" for p in found]
        for number, entry in enumerate(read_journal(r.run_dir / "journal.jsonl"), start=1):
            for p in contracts.problems("journal_entry", entry)[:1]:
                problems.append(f"{name} journal line {number}: {p}")
    npc_calls = sum(len(json.loads(line)["model_calls"]) for line in records.read_text(encoding="utf-8").splitlines()
                    if json.loads(line)["agent_id"] != "robot_r")
    if not npc_calls:
        problems.append("SB-04 with --model fake: no NPC made a model call (NPCs are not model-driven)")
    cs, _ = load_and_check()
    marked, goals, labels = canary.marked_configs(cs)
    for scenario_id in ("SB04_POLITE_BID", "SB05_RAMP_VS_STAIRS"):
        out = root / f"canary_{scenario_id}"
        _scenario_run(godot, scenario_id, out, model="fake", configs=marked)
        cast = marked.items["scenarios"][scenario_id]["cast"]
        npcs = {a for a, e in cast.items() if not (e["persona"] == "robot_r" or e["controller"] == "LLM_AGENT")}
        found = canary.scan_run(out, {a: e["persona"] for a, e in cast.items()}, goals, labels, npcs)
        found += canary.observer_filter_problems(out, list(cast))
        problems += [f"canary {scenario_id}: {p}" for p in found]
    return problems, f"{npc_calls} NPC model calls, journal {(hashes['SB04_npc_a'] or '')[:12]} x3 and replayed"


def scenario_checks(godot: str) -> int:
    """Step 6: SB-04 and SB-05 end to end; SB-04 three times (random sidecar delays, then posing off)."""
    from range_service import contracts
    from range_service.eval.runner import RunError, read_journal

    root = Path(tempfile.mkdtemp(prefix="scenario_runs_"))
    problems: list[str] = []
    try:
        runs = {"SB04_a": ("SB04_POLITE_BID", 0, True), "SB04_b": ("SB04_POLITE_BID", 25, True),
                "SB04_no_pose": ("SB04_POLITE_BID", 0, False), "SB05": ("SB05_RAMP_VS_STAIRS", 0, True)}
        results = {}
        for name, (scenario_id, jitter, posing) in runs.items():
            try:
                results[name] = _scenario_run(godot, scenario_id, root / name, jitter, posing)
            except RunError as exc:
                print(f"  FAIL  scenario {scenario_id}: {exc}")
                return EXIT_FAILED
        for name, r in results.items():
            s = r.summary
            if r.exit_code != 0 or r.godot_errors or s["sidecar_problems"] or s["step_timeouts"]:
                problems.append(f"{name}: exit {r.exit_code}, errors {r.godot_errors[:2]}, sidecar {s['sidecar_problems'][:2]}, "
                                f"step timeouts {s['step_timeouts']}")
            if s["tape"]["refused"]:
                problems.append(f"{name}: tape events refused: {s['tape']['refused'][:2]}")
            journal = read_journal(r.run_dir / "journal.jsonl")
            for number, entry in enumerate(journal, start=1):
                for p in contracts.problems("journal_entry", entry)[:2]:
                    problems.append(f"{name} journal line {number}: {p}")
            manifest = json.loads((r.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            problems += [f"{name} run manifest: {p}" for p in contracts.problems("run_manifest", manifest)[:2]]
            _, found = check_agent_records(r.run_dir)
            problems += [f"{name}: {p}" for p in found]
        a, b = results["SB04_a"], results["SB04_b"]
        if a.journal_sha256 != b.journal_sha256:
            problems.append(f"SB-04 is not deterministic: same seed, different journals ({a.journal_sha256[:12]} vs "
                            f"{b.journal_sha256[:12]}) with random sidecar delays in the second run (D-48)")
        off = results["SB04_no_pose"]
        if a.journal_sha256 != off.journal_sha256:
            problems.append(f"SB-04 journal changed with posing off ({a.journal_sha256[:12]} vs {off.journal_sha256[:12]}): "
                            f"pose is presentation and must never change the world (D-54)")
        sb04 = a.summary
        if sb04["actions_by_agent"].get("robot_r", {}).keys() - {"OK"}:
            problems.append(f"SB-04: Robot R had refused actions: {sb04['actions_by_agent']['robot_r']}")
        if sb04["agents"]["robot_r"]["open_commitments"] != 0 or not sb04["expressions_shown"]:
            problems.append("SB-04: Robot R should keep its promise to Y and show expressions")
        states = {st["avatar_id"]: st for st in results["SB05"].summary["final_states"]}
        for robot in ("robot_legged", "robot_quadruped", "robot_wheeled"):
            if states.get(robot, {}).get("y", 0) < 0.5:
                problems.append(f"SB-05: {robot} did not reach the platform ({states.get(robot)})")
        if "platform_stairs" in states.get("robot_wheeled", {}).get("links_used", ["platform_stairs"]):
            problems.append("SB-05: the wheeled humanoid used the stairs")
        try:
            npc_problems, npc_note = npc_model_checks(godot, root)
        except RunError as exc:
            npc_problems, npc_note = [f"model-driven NPC runs: {exc}"], ""
        problems += npc_problems
        try:
            pulse_problems, pulse_note = pulse_checks(godot, root)
        except RunError as exc:
            pulse_problems, pulse_note = [f"pulse scenario runs: {exc}"], ""
        problems += pulse_problems
        if problems:
            print(f"  FAIL  {len(problems)} problem(s) in the scenario runs:")
            for line in problems[:20]:
                print(f"        {line}")
            return EXIT_FAILED
        print(f"  PASS  scenarios: SB-04 deterministic (journal {a.journal_sha256[:12]}, three runs: one with random "
              f"sidecar delays, one with posing off); SB-05 robots on the platform by the links their bodies allow")
        print(f"  PASS  model-driven NPCs (fake model): {npc_note}; canary clean in SB-04 and SB-05; "
              f"NPCs and Robot R perceive only through the observer filter")
        print(f"  PASS  pulse (D-61): {pulse_note}; FN-1 held, FN-2 glances within 0.5 s, no zombie time, no pacing")
        return EXIT_PASSED
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_tests(godot: str, test_filter: str) -> int:
    """Steps 4 and 5: run the Godot test scene once and validate what it wrote."""
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
    if test_filter and code == 0 and not report.passed and not report.failed and not report.errors:
        print(f"  no Godot test name contains {test_filter!r}")
        shutil.rmtree(artifacts, ignore_errors=True)
        return EXIT_PASSED
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
