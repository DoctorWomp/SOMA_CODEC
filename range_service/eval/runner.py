"""The scenario runner (G3a, D-48): one scenario, end to end, through the Godot <-> Python link.

Python loads and checks the scenario YAML and keeps everything evaluator-only on this side.
It starts the sidecar in this process with one agent runtime per cast member, then launches
Godot with the scenario's id; Godot reads its world-only copy (godot_app/data/scenarios/),
builds the world, spawns the cast, plays the event tape and writes the journal. When the
scenario's time is up Godot ends the run and quits.

A run folder holds:

- ``journal.jsonl``: Godot's event journal (contracts/journal_entry), the record of the run;
- ``run_manifest.json``: how the run was set up (contracts/run_manifest);
- ``sidecar/decision_records.jsonl``: every decision, its context sizes and model calls
  (contracts/decision_record), which ``--model replay:<file>`` can replay;
- ``sidecar/agent_memory.json``, ``sidecar/sidecar_*.jsonl``: memories and link traffic;
- ``summary.json``: counts for a quick look (evaluator only).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from range_service import contracts
from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import ProviderError, gateway_from_spec, tokenizer_for
from range_service.configs import ConfigSet, load_and_check
from range_service.link.sidecar import Sidecar

REPO = contracts.REPO_ROOT
GODOT_PROJECT = REPO / "godot_app"
APP_VERSION = "0.3.0"
STEP_TIMEOUT_DETAIL = "stepped run: no AGENTS_DONE"


@dataclass
class RunOptions:
    scenario_id: str
    godot: str
    mode: str = "STEPPED"
    model: str = "none"
    seed: int | None = None
    body_overrides: dict[str, str] = field(default_factory=dict)
    out_dir: Path | None = None
    headless: bool = True
    jitter_ms: int = 0
    timeout_s: float = 900.0
    godot_args: list[str] = field(default_factory=list)   # extra engine options, e.g. a renderer
    posing: bool = True   # skeleton poses (presentation only, D-54); the journal is the same either way


@dataclass
class RunResult:
    run_dir: Path
    exit_code: int
    journal_sha256: str | None
    summary: dict[str, Any]
    godot_errors: list[str]


class RunError(RuntimeError):
    pass


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = out.stdout.strip()
    return commit if out.returncode == 0 and len(commit) == 40 else None


def check_options(opts: RunOptions, cs: ConfigSet) -> dict[str, Any]:
    scenario = cs.items["scenarios"].get(opts.scenario_id)
    if scenario is None:
        raise RunError(f"unknown scenario {opts.scenario_id!r}; see configs/scenarios/")
    if opts.mode not in ("STEPPED", "LIVE"):
        raise RunError("mode must be STEPPED or LIVE")
    for avatar_id, body_id in opts.body_overrides.items():
        if avatar_id not in scenario["cast"]:
            raise RunError(f"--body: {avatar_id!r} is not in the cast of {opts.scenario_id}")
        if body_id not in cs.items["bodies"]:
            raise RunError(f"--body: unknown body {body_id!r}; see configs/bodies/")
    return scenario


def godot_command(opts: RunOptions, scenario: dict[str, Any], run_dir: Path, port: int, seed: int) -> list[str]:
    # RANGE plays no sound yet: the dummy audio driver avoids audio-device errors on machines without one.
    cmd = [opts.godot, "--path", str(GODOT_PROJECT), "--audio-driver", "Dummy", *opts.godot_args]
    if opts.headless:
        cmd += ["--headless", "--fixed-fps", "60"]
    cmd += ["res://scenes/main.tscn", "--", f"--scenario={opts.scenario_id}", f"--run-mode={opts.mode}",
            f"--seed={seed}", f"--journal={(run_dir / 'journal.jsonl').as_posix()}", f"--link-port={port}",
            f"--link-agents={','.join(sorted(scenario['cast']))}", "--quit-when-done"]
    if opts.body_overrides:
        cmd.append("--bodies=" + ",".join(f"{a}:{b}" for a, b in sorted(opts.body_overrides.items())))
    if not opts.posing:
        cmd.append("--no-pose")
    return cmd


async def _run_godot(cmd: list[str], env: dict[str, str], timeout_s: float, log_path: Path) -> tuple[int, list[str]]:
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=REPO, env=env, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT)
    lines: list[str] = []

    async def pump() -> None:
        assert proc.stdout is not None
        with log_path.open("w", encoding="utf-8") as log:
            async for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                lines.append(line)
                log.write(line + "\n")
    try:
        await asyncio.wait_for(asyncio.gather(pump(), proc.wait()), timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise RunError(f"Godot did not finish the scenario within {timeout_s:.0f} s (log: {log_path})")
    return proc.returncode if proc.returncode is not None else -1, lines


def read_journal(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(journal: list[dict[str, Any]], runtimes: dict[str, Any]) -> dict[str, Any]:
    actions: dict[str, dict[str, int]] = {}
    for entry in journal:
        if entry["kind"] == "ACTION_RESOLVED":
            result = entry["payload"]["result"]
            if result["action_request_id"].startswith("tape_"):
                continue
            per = actions.setdefault(result["agent_id"], {})
            per[result["reason_code"]] = per.get(result["reason_code"], 0) + 1
    ended = next((e["payload"] for e in journal if e["kind"] == "RUN_ENDED"), {})
    tape = [e["payload"] for e in journal if e["kind"] == "SCENARIO_EVENT"]
    return {
        "ticks_run": ended.get("ticks_run"),
        "held_samples": ended.get("held_ticks", 0),
        "final_states": ended.get("avatars", []),
        "tape": {"played": len(tape), "refused": [t for t in tape if t["reason_code"] != "OK"]},
        "actions_by_agent": actions,
        "agents": {aid: dict(rt.stats, cognition=rt.cognition.level, cognition_changes=len(rt.cognition.changes),
                             open_commitments=len(rt.memory.open_commitments()))
                   for aid, rt in sorted(runtimes.items())},
        "expressions_shown": sum(1 for e in journal if e["kind"] == "EXPRESSION_SHOWN"),
        "step_timeouts": sum(1 for e in journal if e["kind"] == "LINK_STATUS"
                             and STEP_TIMEOUT_DETAIL in e["payload"].get("detail", "")),
    }


def manifest(opts: RunOptions, cs: ConfigSet, scenario: dict[str, Any], seed: int, run_id: str,
             tainted_reasons: list[str], details: dict[str, Any], model_hash: str | None = None) -> dict[str, Any]:
    game_map = cs.items["maps"][scenario["map"]]
    avatars = []
    for avatar_id in sorted(scenario["cast"]):
        entry = scenario["cast"][avatar_id]
        persona = cs.items["personas"][entry["persona"]]
        preset = cs.items["presets"][entry["preset"]]
        llm = entry["controller"] == "LLM_AGENT"
        model_id = (opts.model.split(":", 1)[0] if opts.model.startswith("replay:") else opts.model) \
            if (llm and opts.model != "none") else None
        brain = f"LLM: {opts.model}" if model_id else ("LLM: none (Demo policy)" if llm else "SCRIPTED")
        avatars.append({
            "avatar_id": avatar_id, "controller": entry["controller"], "policy": entry["policy"],
            "cognition_level": persona["cognition_level"], "persona_id": entry["persona"],
            "body_id": opts.body_overrides.get(avatar_id, entry["body"]), "perception_preset": entry["preset"],
            "perception_mask": preset["layers"], "sensor_package": entry["sensor_package"],
            "model": {"model_id": model_id, "model_hash": model_hash if model_id else None},
            "capability_card": f"[{avatar_id} | {brain} | HORIZON: {entry['preset']} | memory: RCC | "
                               f"sensors: {entry['sensor_package']} | actions: v1]",
        })
    settings: dict[str, Any] = {"run_mode": opts.mode, "model": opts.model[-200:], "tokenizer": "approx_chars_v1",
                                "jitter_ms": opts.jitter_ms, "headless": opts.headless}
    for avatar_id, body_id in sorted(opts.body_overrides.items()):
        settings[f"body_override.{avatar_id}"] = body_id
    settings.update(details)
    return {
        "schema_version": "1.0", "run_id": run_id, "app_version": APP_VERSION, "git_commit": _git_commit(),
        "contracts_version": "1.0", "seed": seed, "scenario_id": opts.scenario_id, "map_id": scenario["map"],
        "map_version": game_map["version"],
        "simulation": {"tick_hz": scenario["tick_hz"], "mode": opts.mode, "world_authority": "GODOT"},
        "avatars": avatars, "resolved_settings": settings, "tainted": bool(tainted_reasons),
        "taint_reasons": tainted_reasons,
    }


async def run_scenario(opts: RunOptions) -> RunResult:
    cs, problems = load_and_check()
    if problems:
        raise RunError("configs have problems; run: uv run python tools/validate_configs.py")
    scenario = check_options(opts, cs)
    seed = scenario["default_seed"] if opts.seed is None else opts.seed
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    run_id = f"{opts.scenario_id.lower()}_{seed}_{stamp}"
    run_dir = opts.out_dir or (REPO / "runs" / run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    details: dict[str, Any] = {}
    tokenizer = None
    try:
        gateway = gateway_from_spec(opts.model, log_path=run_dir / "llama_server.log", seed=seed)
    except (ValueError, ProviderError) as exc:
        raise RunError(str(exc)) from exc
    if gateway is not None:
        try:
            await gateway.start()   # llama: load the model, warm it up (T1)
        except ProviderError as exc:
            raise RunError(str(exc)) from exc
    sidecar = None
    try:
        tokenizer = tokenizer_for(gateway)
        runtimes = build_runtimes(scenario, cs, gateway=gateway, body_overrides=opts.body_overrides, tokenizer=tokenizer)
        token = secrets.token_hex(24)
        sidecar = Sidecar(token, {}, record_dir=run_dir / "sidecar", runtimes=runtimes, jitter_ms=opts.jitter_ms)
        port = await sidecar.start()
        env = dict(os.environ, RANGE_SESSION_TOKEN=token)
        code, lines = await _run_godot(godot_command(opts, scenario, run_dir, port, seed), env, opts.timeout_s,
                                       run_dir / "godot.log")
    finally:
        if sidecar is not None:
            await sidecar.stop()
        if gateway is not None:
            await gateway.stop()   # only the server this run started
    if tokenizer is not None:
        details["tokenizer"] = tokenizer.name
    setup = getattr(gateway, "setup", None)
    if setup is not None:
        details.update(setup.manifest_settings())

    journal_path = run_dir / "journal.jsonl"
    if not journal_path.is_file():
        raise RunError(f"Godot wrote no journal (exit code {code}); see {run_dir / 'godot.log'}")
    journal = read_journal(journal_path)
    digest = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    summary = summarize(journal, runtimes)
    summary["sidecar_problems"] = list(sidecar.problems)
    errors = [line for line in lines if line.startswith(("ERROR", "SCRIPT ERROR"))]
    taint = []
    if summary["step_timeouts"]:
        taint.append("OTHER")
        details["taint_detail"] = "stepped run had step timeouts"
    if not any(e["kind"] == "RUN_ENDED" for e in journal):
        taint.append("OTHER")
        details["taint_detail"] = "the run did not end normally"
    run_manifest = manifest(opts, cs, scenario, seed, run_id, sorted(set(taint)), details,
                            model_hash=setup.model.sha256 if setup is not None else None)
    found = contracts.problems("run_manifest", run_manifest)
    if found:
        raise RunError(f"run manifest does not match its contract: {found[0]}")
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary["journal_sha256"] = digest
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RunResult(run_dir, code, digest, summary, errors)
