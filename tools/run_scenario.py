"""Run a scenario end to end: Godot (the world) and the Python agent runtimes (G3a, D-48).

    uv run python tools/run_scenario.py SB04_POLITE_BID                 # stepped, Demo policy, headless
    uv run python tools/run_scenario.py SB05_RAMP_VS_STAIRS
    uv run python tools/run_scenario.py SB04_POLITE_BID --watch         # open the window and watch
    uv run python tools/run_scenario.py SB04_POLITE_BID --body robot_r=quadruped
    uv run python tools/run_scenario.py SB04_POLITE_BID --model fake    # the model path, with a fake model
    uv run python tools/run_scenario.py SB04_POLITE_BID --model replay:runs/<run>/sidecar/decision_records.jsonl
    uv run python tools/run_scenario.py SB04_POLITE_BID --model llama   # Option C: Robot R + NPC server (G3c-1)
    uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --npc-model none   # NPCs on templates
    uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --resolution 1920x1080
        # rendered client at a declared resolution and preset: frame times and peak VRAM in summary.json (G3d)
    uv run python tools/run_scenario.py SB06_LONG_WAIT --no-pulse    # the same run with the pulse off (G3d)
    uv run python tools/compare_runs.py runs/<run A> runs/<run B>      # side by side, from the summaries
    uv run python tools/run_scenario.py SB06_LONG_WAIT --watch --presence subtle   # the presence dial (G3e)
    uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model fake-gpu --npc-load 3 --gpu-guard on
        # G3f: Robot R (F3) and NPCs (N3) on a simulated shared GPU, with a condition (D-75 to D-78)

Modes: STEPPED (default) holds the world at each sample until every agent has answered, so a
run is exactly repeatable; LIVE never waits (use it to watch responsiveness). No model is ever
downloaded: --model takes none (Demo policy), fake, fake-slow:MS, fake-malformed, replay:FILE,
llama, llama:MODEL or llama-attach:PORT (G3b), or fake-gpu[:PROFILE] (G3f: a fake model on a
simulated GPU shared with the NPCs, agents/simgpu.py). --npc-model (G3c-1) chooses what drives visitors
promoted to C1/C2: auto (default) follows --model (none keeps the templates; fake and replay
drive NPCs too; llama starts the NPC server from configs/inference.yaml, Option C).

Writes a run folder under runs/ (git-ignored) and prints a short summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.agents.runmodels import Conditions  # noqa: E402
from range_service.eval.runner import RunError, RunOptions, run_scenario  # noqa: E402
from tools.bakeoff import PROMPT_SET, load_set  # noqa: E402
from tools.godot_check import find_godot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/run_scenario.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", help="scenario id, e.g. SB04_POLITE_BID")
    parser.add_argument("--mode", default="stepped", choices=["stepped", "live"])
    parser.add_argument("--model", default="none")
    parser.add_argument("--npc-model", default="auto",
                        help="what drives C1/C2 NPCs: auto (follow --model), none, fake, replay:FILE, llama:MODEL")
    parser.add_argument("--pulse", default="auto", choices=["auto", "on", "off"],
                        help="the pulse protocol (G3c-2): auto = on if the scenario asks or a model drives Robot R")
    parser.add_argument("--no-pulse", action="store_true", help="the pulse protocol off (same as --pulse off)")
    parser.add_argument("--resolution", default=None, help="rendered runs (--watch): WIDTHxHEIGHT, default 1920x1080")
    parser.add_argument("--render-preset", default="v0", help="rendered runs (--watch): v0 or v0_compat")
    parser.add_argument("--presence", default=None, metavar="LEVEL",
                        help="the presence dial for every robot (G3e): subtle, default, performative, or 0..1")
    parser.add_argument("--frame-stats", action="store_true",
                        help="record frame times in a headless run too (always on with --watch)")
    parser.add_argument("--no-prewarm", action="store_true",
                        help="never pre-warm NPC persona prefixes (measures cold promotion latency)")
    parser.add_argument("--focal-layout", default=None, choices=["ONE_MESSAGE", "SYSTEM_PREFIX"],
                        help="G3f (D-76): Robot R's prompt layout (default: configs/inference.yaml focal.prompt_layout)")
    parser.add_argument("--focal-answer", default=None, choices=["FULL", "SHORT"],
                        help="G3f (D-77): Robot R's answer limits (default: configs/inference.yaml focal.answer)")
    parser.add_argument("--gpu-guard", default=None, choices=["on", "off"],
                        help="G3f (D-78): focal-first GPU guard in Option C (default: configs/inference.yaml gpu_guard)")
    parser.add_argument("--npc-cap", type=int, default=None, help="G3f: real NPC calls allowed while Robot R thinks")
    parser.add_argument("--npc-load", type=int, default=0, metavar="STREAMS",
                        help="keep STREAMS synthetic NPC calls running on the NPC server (as the bake-off's LIVE_LOAD)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--body", action="append", default=[], metavar="AVATAR=BODY")
    parser.add_argument("--out", type=Path, default=None, help="run folder (default: runs/<scenario>_<seed>_<time>)")
    parser.add_argument("--watch", action="store_true", help="open the Godot window instead of running headless")
    parser.add_argument("--jitter-ms", type=int, default=0, help="test: random delay before each agent answer")
    parser.add_argument("--no-pose", action="store_true",
                        help="keep robots in their rest pose (posing is presentation; the journal is the same)")
    parser.add_argument("--godot-arg", action="append", default=[], metavar="ARG",
                        help="extra Godot option, e.g. --godot-arg=--rendering-method --godot-arg=gl_compatibility")
    args = parser.parse_args(argv)

    godot = find_godot()
    if godot is None:
        print("Godot not found. Set GODOT_BIN, or run: uv run python tools/install_godot.py")
        return 2
    overrides = {}
    for spec in args.body:
        avatar_id, _, body_id = spec.partition("=")
        overrides[avatar_id] = body_id
    opts = RunOptions(args.scenario, godot, mode=args.mode.upper(), model=args.model, seed=args.seed,
                      body_overrides=overrides, out_dir=args.out, headless=not args.watch, jitter_ms=args.jitter_ms,
                      godot_args=args.godot_arg, posing=not args.no_pose, npc_model=args.npc_model,
                      prewarm=False if args.no_prewarm else None, pulse="off" if args.no_pulse else args.pulse,
                      resolution=args.resolution, render_preset=args.render_preset,
                      frame_stats=True if args.frame_stats else None, presence=args.presence,
                      conditions=Conditions(args.focal_layout, args.focal_answer,
                                            None if args.gpu_guard is None else args.gpu_guard == "on", args.npc_cap),
                      npc_load_streams=args.npc_load,
                      npc_load_prompts=[i for i in load_set(PROMPT_SET)[0] if i.get("role") == "NPC"] if args.npc_load else [])
    try:
        result = asyncio.run(run_scenario(opts))
    except RunError as exc:
        print(f"FAIL  {exc}")
        return 1
    s = result.summary
    print(f"Run folder: {result.run_dir}")
    print(f"  Godot exit code {result.exit_code}; {s['ticks_run']} ticks; held at {s['held_samples']} samples")
    print(f"  journal SHA-256 {result.journal_sha256}")
    print(f"  event tape: {s['tape']['played']} played, {len(s['tape']['refused'])} refused")
    inf = s["inference"]
    if inf["option"] is not None:
        print(f"  NPC model: {inf['npc_model']} (option {inf['option']}"
              + (f"; fallback: {inf['fallback']}" if inf["fallback"] else "") + ")")
    pr = s["promotions"]
    if pr["count"]:
        print(f"  NPC promotions: {pr['count']} ({pr['validated']} reached a validated action); latency p50 "
              f"warm {pr['warm_p50_ms']} ms (n={pr['warm_n']}), cold {pr['cold_p50_ms']} ms (n={pr['cold_n']})")
    for agent_id, stats in s["agents"].items():
        print(f"  {agent_id}: {stats['decisions']} decisions, {stats['requests']} requests, "
              f"{stats['fallbacks']} fallbacks, level {stats['cognition']}, {stats['open_commitments']} open promises; "
              f"results {json.dumps(s['actions_by_agent'].get(agent_id, {}), sort_keys=True)}")
    for agent_id, m in (s.get("pulse") or {}).items():
        print(f"  pulse {agent_id}: {m['decisions']} decisions ({m['reviews']} reviews), {m['continues']} CONTINUE, "
              f"{m['wakes']} wakes, {m['glances']} glances, {m['survey_moves']} survey moves, "
              f"{m['returns_to_post']} returns to post; zombie {m['zombie']['ms']} ms "
              f"({m['zombie']['events']}/{m['zombie']['relevant']}); FN-1 violations {m['fn1_violations']}, held {m['fn1_held']}; "
              f"model reviews per minute {m['model_reviews_per_minute']}")
    render = s.get("render") or {}
    frames = render.get("frames") or {}
    if frames.get("available"):
        print(f"  frames ({'headless' if render['headless'] else render['resolution'] + ', preset ' + render['preset']}): "
              f"p50 {frames['p50_ms']} / p95 {frames['p95_ms']} / p99 {frames['p99_ms']} ms, max {frames['max_ms']}, "
              f"{frames['spikes']} spikes > {frames['spike_threshold_ms']} ms; target p95 <= {frames['target_p95_ms']} ms: "
              f"{ {True: 'met', False: 'NOT met', None: 'n/a (headless)'}[frames['meets_target']] }")
    if render.get("vram") is not None:
        v = render["vram"]
        print(f"  peak VRAM during the run: {v['peak_mib']} MiB" + (f" ({v['reason']})" if v.get("reason") else
                                                                     f" ({v['samples']} samples)"))
    rc = s.get("robot_calls") or {}
    if rc.get("calls"):
        o = rc["outcomes"]
        print(f"  Robot R calls ({', '.join(f'{k} {v}' for k, v in s.get('conditions', {}).items())}): {rc['calls']}; "
              f"valid {o['VALID_FIRST_TRY']} + {o['VALID_AFTER_REPAIR']} repaired; timeouts {o['TIMEOUT_AT_MODEL']} at the model, "
              f"{o['TIMEOUT_IN_QUEUE']} in the queue; invalid {o['INVALID_OUTPUT']} {rc['invalid_kinds']}; "
              f"p50/p95 {rc['total_ms_p50']}/{rc['total_ms_p95']} ms (queue {rc['queue_ms_p50']}, prefill {rc['prefill_ms_p50']}, "
              f"gen {rc['generation_ms_p50']}); prompt tokens p50 {rc['prompt_tokens_p50']}, cache share {rc['cache_share']}, "
              f"generated p50 {rc['generated_tokens_p50']}; other server busy {rc['other_server_busy_share']}")
    if s.get("gpu_guard"):
        print(f"  GPU guard: {s['gpu_guard']}")
    for agent_id, r in (s.get("report") or {}).items():
        lat = r["response_latency_ms"]
        print(f"  report {agent_id}: actions {r['actions']['accepted']}/{r['actions']['offered']} accepted, "
              f"{r['actions']['dropped_before_send']} dropped before sending; response p50 {lat['p50']} / p95 {lat['p95']} ms "
              f"(n={lat['n']}, unanswered {lat['unanswered']}); {r['model_calls']} model calls, {r['timeouts']} timeouts, "
              f"fallbacks {r['fallbacks'] or 0}; {r['glances_accepted']} glances; FN-1 departures mid-conversation "
              f"{r['fn1']['departures_mid_conversation']} ({r['fn1']['without_goodbye']} without a goodbye first)")
    for state in s["final_states"]:
        links = ", ".join(state["links_used"]) or "none"
        print(f"  {state['avatar_id']} ended at ({state['x']:.1f}, {state['y']:.2f}, {state['z']:.1f}); links used: {links}")
    for line in result.godot_errors[:10]:
        print(f"  ERROR {line}")
    ok = result.exit_code == 0 and not result.godot_errors and not s["sidecar_problems"] and not s["step_timeouts"]
    print("OK" if ok else "FAIL  see the run folder")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
