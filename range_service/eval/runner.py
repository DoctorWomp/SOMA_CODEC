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
- ``frames.json`` (rendered runs, or ``frame_stats``): frame times and Godot's video memory (G3d);
- ``sidecar/delivery.jsonl``: requests held back or dropped before sending, and why (G3d);
- ``summary.json``: counts for a quick look (evaluator only), with ``render`` (frame pacing, peak
  VRAM sampled during the run) and ``report`` (offered vs accepted actions, response latency,
  timeouts and fallbacks, model calls, glances, FN-1 continuity) per agent (G3d, D-69).
  ``summary.json`` holds no prompt or memory text: it is the file to share.

A run folder holds one run (G3f, D-75): a folder that still holds an earlier run's files is
cleared of them first (``clear_previous_run``), because several files are appended to as the run
goes (decision records, prompts, link traffic) and a second run into the same folder used to pool
both runs' calls (the owner's 2026-11-19 baseline rows).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
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
from range_service.eval.run_report import VramSampler, frame_summary, run_report
from range_service.link.sidecar import Sidecar

REPO = contracts.REPO_ROOT
GODOT_PROJECT = REPO / "godot_app"
APP_VERSION = "0.3.0"
STEP_TIMEOUT_DETAIL = "stepped run: no AGENTS_DONE"
LOAD_TIER = "LOAD"   # synthetic NPC load in the bake-off; ranked after every real tier
# Rendered-client presets (G3d, D-69): named, so a comparison states what was rendered. The V0
# greybox is the project's own settings (Forward+, ART_DIRECTION §3) with the 60 FPS cap.
RENDER_PRESETS: dict[str, dict[str, Any]] = {
    "v0": {"args": [], "max_fps": 60, "about": "V0 greybox, project settings (Forward+), 60 FPS cap"},
    "v0_compat": {"args": ["--rendering-method", "gl_compatibility"], "max_fps": 60,
                  "about": "V0 greybox on the Compatibility renderer, 60 FPS cap"},
}
DEFAULT_RESOLUTION = "1920x1080"


# What a run writes into its folder (G3f, D-75): only these are removed from a folder that holds an
# earlier run, so a folder given with --out never loses anything else.
RUN_DIRS = ("sidecar", "slot_snapshots")
RUN_FILE_SUFFIXES = (".jsonl", ".json", ".log")


def holds_a_run(run_dir: Path) -> bool:
    return any((run_dir / n).exists() for n in ("journal.jsonl", "run_manifest.json", "summary.json", "sidecar"))


def clear_previous_run(run_dir: Path, keep: tuple[Path, ...] = ()) -> list[str]:
    """Remove an earlier run's files from ``run_dir`` (G3f, D-75), so a new run never appends to
    them. Removes only what a run writes there: the ``sidecar/`` and ``slot_snapshots/`` folders
    and top-level ``.jsonl``, ``.json`` and ``.log`` files. Refuses (RunError) if a path in
    ``keep`` (a replay source) would be removed. Returns what it removed."""
    if not run_dir.is_dir() or not holds_a_run(run_dir):
        return []
    targets = [run_dir / d for d in RUN_DIRS if (run_dir / d).exists()]
    targets += sorted(p for p in run_dir.iterdir() if p.is_file() and p.suffix in RUN_FILE_SUFFIXES)
    for k in keep:
        k = k.resolve()
        for t in targets:
            if k == t.resolve() or t.resolve() in k.parents:
                raise RunError(f"{k} is in the run folder {run_dir}, which would be cleared for the new run: "
                               "replay from a copy, or run into another folder")
    for t in targets:
        if t.is_dir():
            shutil.rmtree(t)
        else:
            t.unlink()
    return [t.name for t in targets]


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
    snapshots: bool | None = None      # None = configs/inference.yaml personas.snapshots (bake-off LIVE_COLD: False)
    pulse: str = "auto"                # G3c-2: on, off, or auto (on if the scenario asks or a model drives Robot R)
    npc_load_prompts: list[dict[str, Any]] = field(default_factory=list)
    resolution: str | None = None      # rendered runs: WIDTHxHEIGHT (default 1920x1080) (G3d)
    render_preset: str = "v0"          # rendered runs: a RENDER_PRESETS name (G3d)
    conditions: Any = None             # G3f: runmodels.Conditions (Robot R's layout and answer, the GPU guard)
    frame_stats: bool | None = None    # None = on for rendered runs; True also records headless frames
    sample_vram: bool | None = None    # None = for LIVE, rendered or llama runs (nvidia-smi once a second)
    presence: str | None = None        # G3e (D-74): the presence dial for every robot (subtle/default/performative/0..1)
    presence_value: float | None = None   # resolved from `presence` by check_options


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
    if opts.presence is not None:
        from range_service.agents.presence_dial import resolve   # noqa: PLC0415

        try:
            opts.presence_value = resolve(opts.presence, cs.items["pulse"]["pulse"])
        except ValueError as exc:
            raise RunError(str(exc)) from exc
    if opts.render_preset not in RENDER_PRESETS:
        raise RunError(f"unknown render preset {opts.render_preset!r}; use one of {', '.join(RENDER_PRESETS)}")
    if opts.resolution is not None and not re.fullmatch(r"\d{3,5}x\d{3,5}", opts.resolution):
        raise RunError("--resolution must be WIDTHxHEIGHT, e.g. 1920x1080")
    for avatar_id, body_id in opts.body_overrides.items():
        if avatar_id not in scenario["cast"]:
            raise RunError(f"--body: {avatar_id!r} is not in the cast of {opts.scenario_id}")
        if body_id not in cs.items["bodies"]:
            raise RunError(f"--body: unknown body {body_id!r}; see configs/bodies/")
    return scenario


def godot_command(opts: RunOptions, scenario: dict[str, Any], run_dir: Path, port: int, seed: int) -> list[str]:
    # RANGE plays no sound yet: the dummy audio driver avoids audio-device errors on machines without one.
    cmd = [opts.godot, "--path", str(GODOT_PROJECT), "--audio-driver", "Dummy", *opts.godot_args]
    if not opts.headless:
        preset = RENDER_PRESETS[opts.render_preset]
        cmd += ["--resolution", opts.resolution or DEFAULT_RESOLUTION, "--max-fps", str(preset["max_fps"]), *preset["args"]]
    if opts.headless:
        cmd.append("--headless")
        # STEPPED: simulate as fast as the agents allow (the world waits for them anyway). LIVE must
        # run in real time: with --fixed-fps a headless world ran ~15x faster than the clock, so
        # every model answer arrived "stale" and NPC calls starved the sidecar (G3c-2, D-60).
        if opts.mode == "STEPPED":
            cmd += ["--fixed-fps", "60"]
    cmd += ["res://scenes/main.tscn", "--", f"--scenario={opts.scenario_id}", f"--run-mode={opts.mode}",
            f"--seed={seed}", f"--journal={(run_dir / 'journal.jsonl').as_posix()}", f"--link-port={port}",
            f"--link-agents={','.join(sorted(scenario['cast']))}", "--quit-when-done"]
    if opts.body_overrides:
        cmd.append("--bodies=" + ",".join(f"{a}:{b}" for a, b in sorted(opts.body_overrides.items())))
    if not opts.posing:
        cmd.append("--no-pose")
    if _frame_stats_on(opts):
        cmd.append(f"--frame-stats={(run_dir / 'frames.json').as_posix()}")
    if opts.presence_value is not None:
        cmd.append(f"--presence-amplitude={opts.presence_value:g}")
    return cmd


def _frame_stats_on(opts: RunOptions) -> bool:
    return opts.frame_stats if opts.frame_stats is not None else not opts.headless


def _vram_on(opts: RunOptions) -> bool:
    if opts.sample_vram is not None:
        return opts.sample_vram
    return opts.mode == "LIVE" or not opts.headless or opts.model.startswith("llama") or opts.npc_model.startswith("llama")


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
    if opts.presence is not None:
        settings["presence_amplitude"] = opts.presence_value
    if not opts.headless:
        settings["render_preset"] = opts.render_preset
        settings["resolution"] = opts.resolution or DEFAULT_RESOLUTION
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
                                 allowed_actions=item["allowed_actions"], tick=item["based_on_tick_id"],
                                 choices=item.get("choices"))
        for call in result.model_calls:
            out.append({"stream": stream, "item_id": item["item_id"], "outcome": call["outcome"], **call["timings"]})
        await asyncio.sleep(0)


def _reserve_mib() -> int:
    from range_service.agents.inference import DEFAULT_VRAM, load_inference   # noqa: PLC0415

    try:
        return int(dict(DEFAULT_VRAM, **(load_inference().get("vram") or {}))["reserve_mib"])
    except Exception:   # noqa: BLE001 - a summary field only; never fail a run for it
        return int(DEFAULT_VRAM["reserve_mib"])


def promotion_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Promotion latency, cold vs warm (G3c-1), split at G3c-2 (D-60) into: promotion -> first model
    call starts (decisions are event-driven, so this includes waiting for a trigger), the first
    call itself, and promotion -> first action the world accepted. Warm = the first model call
    found the persona prefix in its slot (WARM or RESTORED)."""
    def p50(values: list[float]) -> float | None:
        vals = sorted(v for v in values if v is not None)
        return float(vals[len(vals) // 2]) if vals else None

    def warmth(r: dict[str, Any]) -> str:
        return "warm" if (r["first_model_call"] or {}).get("prefix_state") in ("WARM", "RESTORED") else "cold"
    out: dict[str, Any] = {"count": len(records),
                           "validated": sum(r["status"] == "VALIDATED" for r in records),
                           "note": "cold includes calls whose slot state is unknown (fake or replay models have no slots)"}
    for kind in ("warm", "cold"):
        rows = [r for r in records if r["first_model_call"] is not None and warmth(r) == kind]
        done = [r for r in rows if r["status"] == "VALIDATED"]
        out[f"{kind}_n"] = len(done)
        out[f"{kind}_p50_ms"] = p50([r["first_validated_action_ms"] for r in done])
        out[f"{kind}_calls_n"] = len(rows)
        out[f"{kind}_to_first_call_p50_ms"] = p50([r.get("to_first_model_call_ms") for r in rows])
        out[f"{kind}_first_call_p50_ms"] = p50([(r["first_model_call"] or {}).get("total_ms") for r in rows])
    return out


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
    keep = tuple(Path(spec.split(":", 1)[1]) for spec in (opts.model, opts.npc_model) if spec.startswith("replay:"))
    cleared = clear_previous_run(run_dir, keep)
    if cleared:
        print(f"NOTE  {run_dir} held an earlier run; removed its files first: {', '.join(cleared[:6])}"
              f"{' ...' if len(cleared) > 6 else ''}")
    run_dir.mkdir(parents=True, exist_ok=True)

    details: dict[str, Any] = {}
    tokenizer = None
    try:
        models = models_from_specs(opts.model, opts.npc_model, run_dir=run_dir, seed=seed, prewarm=opts.prewarm,
                                   snapshots=opts.snapshots, conditions=opts.conditions)
    except (ValueError, ProviderError) as exc:
        raise RunError(str(exc)) from exc
    from range_service.eval.bakeoff import gpu_memory_mib, vram_hygiene   # noqa: PLC0415

    gpu_before = gpu_memory_mib()            # G3g (D-87): what other programs hold before any server starts
    try:
        await models.start()   # llama: load the model(s), warm them up (T1); Option C or the fallback to B
    except ProviderError as exc:
        raise RunError(str(exc)) from exc
    servers = getattr(getattr(models.focal, "provider", None), "server", None) is not None or models.inference is not None
    hygiene = vram_hygiene(gpu_before, gpu_memory_mib() if servers else (None, None, None),
                           _reserve_mib(), servers)
    if hygiene["warning"]:
        print(f"WARNING  {hygiene['warning']}")
    for event in models.events:
        if event["event"] == "OPTION_C_FALLBACK":
            print(f"WARNING  NPC server not used, running Option B: {event['reason']}")
    sidecar = None
    vram = VramSampler()
    load_tasks: list[asyncio.Task] = []
    load_records: list[dict[str, Any]] = []
    try:
        tokenizer = tokenizer_for(models.focal)
        npc_tokenizer = tokenizer if models.npc is models.focal else tokenizer_for(models.npc)
        pulse_on = opts.pulse == "on" or (opts.pulse == "auto" and (bool(scenario.get("pulse")) or opts.model != "none"))
        details["pulse"] = pulse_on
        runtimes = build_runtimes(scenario, cs, gateway=models.focal, body_overrides=opts.body_overrides,
                                  tokenizer=tokenizer, npc_gateway=models.npc, npc_tokenizer=npc_tokenizer,
                                  prewarm=models.prewarm, pulse=cs.items["pulse"]["pulse"] if pulse_on else None,
                                  seed=seed)
        await snapshot_personas(runtimes, models)            # T5: at scene load, before the world starts
        token = secrets.token_hex(24)
        sidecar = Sidecar(token, {}, record_dir=run_dir / "sidecar", runtimes=runtimes, jitter_ms=opts.jitter_ms)
        port = await sidecar.start()
        env = dict(os.environ, RANGE_SESSION_TOKEN=token)
        if opts.npc_load_streams and models.npc is not None and opts.npc_load_prompts:
            load_tasks = [asyncio.create_task(_npc_load(models, k, opts.npc_load_prompts, load_records))
                          for k in range(opts.npc_load_streams)]
        if _vram_on(opts):
            vram.start()                      # peak VRAM during the run, not only after server start (G3d)
        code, lines = await _run_godot(godot_command(opts, scenario, run_dir, port, seed), env, opts.timeout_s,
                                       run_dir / "godot.log")
    finally:
        await vram.stop()
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
    pulse_rows = [dict(e, agent_id=aid) for aid in sorted(runtimes) for e in runtimes[aid].pulse_log]
    if pulse_rows:
        _write_jsonl(run_dir / "pulse.jsonl", pulse_rows)

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
    # G3f (D-75 to D-78): the conditions this run used, what the GPU guard held back, and Robot R's
    # calls broken down by outcome and cost (counts and timings only).
    from range_service.eval.live_diag import robot_breakdown   # noqa: PLC0415

    summary["conditions"] = dict(models.conditions)
    summary["gpu_guard"] = dict(models.guard.stats, npc_cap=models.guard.npc_cap, hold=models.guard.hold) \
        if models.guard is not None else None
    summary["vram_hygiene"] = hygiene
    if models.simgpu is not None:
        summary["simgpu"] = {"busy_s": round(models.simgpu.busy_s, 1), "peak_concurrency": models.simgpu.peak_concurrency}
    records_path = run_dir / "sidecar" / "decision_records.jsonl"
    recs = [json.loads(x) for x in records_path.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if records_path.is_file() else []
    delivery_path = run_dir / "sidecar" / "delivery.jsonl"
    deliv = [json.loads(x) for x in delivery_path.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if delivery_path.is_file() else []
    summary["robot_calls"] = robot_breakdown(recs, deliv)
    summary["event_loop_lag_ms"] = sidecar.loop_lag_summary()
    if details.get("pulse"):
        from range_service.eval.pulse_metrics import pulse_summary   # noqa: PLC0415

        summary["pulse"] = pulse_summary(runtimes, journal, scenario)
    summary["render"] = {"headless": opts.headless, "mode": opts.mode, "pulse": bool(details.get("pulse")),
                         "resolution": None if opts.headless else (opts.resolution or DEFAULT_RESOLUTION),
                         "preset": None if opts.headless else opts.render_preset,
                         "frames": frame_summary(run_dir / "frames.json") if _frame_stats_on(opts) else None,
                         "vram": vram.summary() if _vram_on(opts) else None}
    summary["report"] = run_report(run_dir, journal, sorted(runtimes))
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
