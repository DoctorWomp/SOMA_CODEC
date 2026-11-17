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
- ``inference_events.jsonl``: which servers ran (Option C or the fallback to B, with the
  reason), VRAM, persona snapshots and pre-warms (G3c-1);
- ``promotions.jsonl``: every NPC promotion with its latency to the first validated action,
  cold or warm (G3c-1). Wall-clock values stay out of the journal, so stepped runs stay exact;
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
from range_service.agents.gateway import ProviderError, tokenizer_for
from range_service.agents.runmodels import RunModels, models_from_specs
from range_service.configs import ConfigSet, load_and_check
from range_service.link.sidecar import Sidecar

REPO = contracts.REPO_ROOT
GODOT_PROJECT = REPO / "godot_app"
APP_VERSION = "0.3.0"
STEP_TIMEOUT_DETAIL = "stepped run: no AGENTS_DONE"
LOAD_TIER = "LOAD"   # synthetic NPC load in the bake-off; ranked after every real tier


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
    npc_model: str = "auto"   # G3c-1: what drives C1/C2 NPCs (agents/runmodels.py)
    prewarm: bool | None = None   # None = configs/inference.yaml personas.prewarm
    configs: ConfigSet | None = None   # tests: a checked config set to use instead of configs/
    npc_load_streams: int = 0          # bake-off: synthetic NPC calls kept running on the NPC server
    npc_load_prompts: list[dict[str, Any]] = field(default_factory=list)


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
             tainted_reasons: list[str], details: dict[str, Any], model_hash: str | None = None,
             npc_spec: str | None = None, npc_hash: str | None = None) -> dict[str, Any]:
    game_map = cs.items["maps"][scenario["map"]]
    avatars = []
    for avatar_id in sorted(scenario["cast"]):
        entry = scenario["cast"][avatar_id]
        persona = cs.items["personas"][entry["persona"]]
        preset = cs.items["presets"][entry["preset"]]
        llm = entry["controller"] == "LLM_AGENT"
        focal = entry["persona"] == "robot_r" or llm
        npc_driven = not focal and npc_spec not in (None, "none")
        spec = opts.model if llm else (npc_spec if npc_driven else "none")
        model_id = (spec.split(":", 1)[0] if spec.startswith("replay:") else spec) \
            if ((llm or npc_driven) and spec != "none") else None
        brain = f"LLM: {spec}" if model_id else ("LLM: none (Demo policy)" if llm else "SCRIPTED")
        if npc_driven:
            brain = f"C0 routine, C1/C2 NPC model: {spec}"
        avatars.append({
            "avatar_id": avatar_id, "controller": entry["controller"], "policy": entry["policy"],
            "cognition_level": persona["cognition_level"], "persona_id": entry["persona"],
            "body_id": opts.body_overrides.get(avatar_id, entry["body"]), "perception_preset": entry["preset"],
            "perception_mask": preset["layers"], "sensor_package": entry["sensor_package"],
            "model": {"model_id": model_id[-120:] if model_id else None,
                      "model_hash": (model_hash if llm else npc_hash) if model_id else None},
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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def inference_events(models: RunModels) -> list[dict[str, Any]]:
    """Server events (Option C started or the fallback to B, VRAM) and persona snapshots/pre-warms."""
    rows = [dict(e) for e in models.events]
    if models.inference is not None:
        rows.append({"event": "VRAM", **models.inference.vram})
    seen = set()
    for gw in (models.focal, models.npc):
        if gw is not None and id(gw) not in seen:
            seen.add(id(gw))
            rows += [dict(e) for e in gw.persona_events]
    return rows


async def snapshot_personas(runtimes: dict[str, Any], models: RunModels) -> None:
    """T5: at scene load, warm (and save, where the server supports it) every model-driven NPC's
    persona prefix for each level it can think at. Only for providers with slots (llama-server)."""
    gw = models.npc
    if gw is None or not gw.supports_personas() or models.inference is None:
        return
    if not models.inference.inference.get("personas", {}).get("snapshots", True):
        return
    todo = []
    for agent_id in sorted(runtimes):
        rt = runtimes[agent_id]
        for tier in rt.model_tiers():
            key, prefix = rt.persona_prefix(tier)
            todo.append((agent_id, tier, key, prefix))
    await gw.prepare_personas(todo)


async def _npc_load(models: RunModels, stream: int, prompts: list[dict[str, Any]], out: list[dict[str, Any]]) -> None:
    """Bake-off: keep the NPC server busy with recorded NPC prompts (lowest priority), to measure
    Robot R's latency while NPCs load the other server."""
    gw = models.npc
    assert gw is not None
    # Its own tier, below every real agent (the scheduler ranks unknown tiers last), with the C1
    # deadline: the load never pushes a real NPC's call back, only fills free slots.
    gw.deadlines_ms.setdefault(LOAD_TIER, gw.deadlines_ms["C1"])
    i = stream
    while True:
        item = prompts[i % len(prompts)]
        i += 1
        result = await gw.decide(agent_id=f"npc_load_{stream}", tier=LOAD_TIER, prompt=item["prompt"],
                                 prompt_sha256=item["prompt_sha256"], max_tokens=item["max_tokens"],
                                 allowed_actions=item["allowed_actions"], tick=item["based_on_tick_id"])
        for call in result.model_calls:
            out.append({"stream": stream, "item_id": item["item_id"], "outcome": call["outcome"], **call["timings"]})
        await asyncio.sleep(0)


def promotion_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Promotion latency (promotion event -> first validated action), cold vs warm (G3c-1).
    Warm = the first model call found the persona prefix in its slot (WARM or RESTORED)."""
    def p50(values: list[int]) -> float | None:
        vals = sorted(values)
        return float(vals[len(vals) // 2]) if vals else None
    done = [r for r in records if r["status"] == "VALIDATED" and r["first_validated_action_ms"] is not None]
    warm = [r["first_validated_action_ms"] for r in done
            if (r["first_model_call"] or {}).get("prefix_state") in ("WARM", "RESTORED")]
    cold = [r["first_validated_action_ms"] for r in done
            if (r["first_model_call"] or {}).get("prefix_state") not in ("WARM", "RESTORED")]
    return {"count": len(records), "validated": len(done), "warm_n": len(warm), "warm_p50_ms": p50(warm),
            "cold_n": len(cold), "cold_p50_ms": p50(cold),
            "note": "cold includes calls whose slot state is unknown (fake or replay models have no slots)"}


async def run_scenario(opts: RunOptions) -> RunResult:
    if opts.configs is not None:
        cs, problems = opts.configs, []
    else:
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
        models = models_from_specs(opts.model, opts.npc_model, run_dir=run_dir, seed=seed, prewarm=opts.prewarm)
    except (ValueError, ProviderError) as exc:
        raise RunError(str(exc)) from exc
    try:
        await models.start()   # llama: load the model(s), warm them up (T1); Option C or the fallback to B
    except ProviderError as exc:
        raise RunError(str(exc)) from exc
    for event in models.events:
        if event["event"] == "OPTION_C_FALLBACK":
            print(f"WARNING  NPC server not used, running Option B: {event['reason']}")
    sidecar = None
    load_tasks: list[asyncio.Task] = []
    load_records: list[dict[str, Any]] = []
    try:
        tokenizer = tokenizer_for(models.focal)
        npc_tokenizer = tokenizer if models.npc is models.focal else tokenizer_for(models.npc)
        runtimes = build_runtimes(scenario, cs, gateway=models.focal, body_overrides=opts.body_overrides,
                                  tokenizer=tokenizer, npc_gateway=models.npc, npc_tokenizer=npc_tokenizer,
                                  prewarm=models.prewarm)
        await snapshot_personas(runtimes, models)            # T5: at scene load, before the world starts
        token = secrets.token_hex(24)
        sidecar = Sidecar(token, {}, record_dir=run_dir / "sidecar", runtimes=runtimes, jitter_ms=opts.jitter_ms)
        port = await sidecar.start()
        env = dict(os.environ, RANGE_SESSION_TOKEN=token)
        if opts.npc_load_streams and models.npc is not None and opts.npc_load_prompts:
            load_tasks = [asyncio.create_task(_npc_load(models, k, opts.npc_load_prompts, load_records))
                          for k in range(opts.npc_load_streams)]
        code, lines = await _run_godot(godot_command(opts, scenario, run_dir, port, seed), env, opts.timeout_s,
                                       run_dir / "godot.log")
    finally:
        for task in load_tasks:
            task.cancel()
        if load_tasks:
            await asyncio.gather(*load_tasks, return_exceptions=True)
        if sidecar is not None:
            await sidecar.stop()
        await models.stop()   # only the servers this run started
    if tokenizer is not None:
        details["tokenizer"] = tokenizer.name
    details.update(models.manifest_settings())
    setup = getattr(models.focal, "setup", None)
    npc_setup = getattr(models.inference, "npc", None) if models.inference is not None else None
    _write_jsonl(run_dir / "inference_events.jsonl", inference_events(models))
    promotions = [r for aid in sorted(runtimes) for r in runtimes[aid].promotion_records(run_ended=True)]
    _write_jsonl(run_dir / "promotions.jsonl", [dict(r, run_mode=opts.mode) for r in promotions])
    if load_records:
        _write_jsonl(run_dir / "npc_load.jsonl", load_records)

    journal_path = run_dir / "journal.jsonl"
    if not journal_path.is_file():
        raise RunError(f"Godot wrote no journal (exit code {code}); see {run_dir / 'godot.log'}")
    journal = read_journal(journal_path)
    digest = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    summary = summarize(journal, runtimes)
    summary["sidecar_problems"] = list(sidecar.problems)
    summary["inference"] = {"option": models.option, "npc_model": models.npc_spec,
                            "fallback": next((e["reason"] for e in models.events if e["event"] == "OPTION_C_FALLBACK"), None)}
    summary["promotions"] = promotion_summary(promotions)
    summary["npc_load_calls"] = len(load_records)
    errors = [line for line in lines if line.startswith(("ERROR", "SCRIPT ERROR"))]
    taint = []
    if summary["step_timeouts"]:
        taint.append("OTHER")
        details["taint_detail"] = "stepped run had step timeouts"
    if not any(e["kind"] == "RUN_ENDED" for e in journal):
        taint.append("OTHER")
        details["taint_detail"] = "the run did not end normally"
    run_manifest = manifest(opts, cs, scenario, seed, run_id, sorted(set(taint)), details,
                            model_hash=setup.model.sha256 if setup is not None else None,
                            npc_spec=models.npc_spec if models.npc is not None else None,
                            npc_hash=npc_setup.model.sha256 if npc_setup is not None and models.option == "C"
                            else (setup.model.sha256 if setup is not None and models.npc is not None else None))
    found = contracts.problems("run_manifest", run_manifest)
    if found:
        raise RunError(f"run manifest does not match its contract: {found[0]}")
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary["journal_sha256"] = digest
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RunResult(run_dir, code, digest, summary, errors)
