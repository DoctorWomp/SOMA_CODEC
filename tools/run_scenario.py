"""Run a scenario end to end: Godot (the world) and the Python agent runtimes (G3a, D-48).

    uv run python tools/run_scenario.py SB04_POLITE_BID                 # stepped, Demo policy, headless
    uv run python tools/run_scenario.py SB05_RAMP_VS_STAIRS
    uv run python tools/run_scenario.py SB04_POLITE_BID --watch         # open the window and watch
    uv run python tools/run_scenario.py SB04_POLITE_BID --body robot_r=quadruped
    uv run python tools/run_scenario.py SB04_POLITE_BID --model fake    # the model path, with a fake model
    uv run python tools/run_scenario.py SB04_POLITE_BID --model replay:runs/<run>/sidecar/decision_records.jsonl

Modes: STEPPED (default) holds the world at each sample until every agent has answered, so a
run is exactly repeatable; LIVE never waits (use it to watch responsiveness). No model is ever
downloaded or called: --model takes none (Demo policy), fake, fake-slow:MS, fake-malformed or
replay:FILE. Real models arrive at G3b.

Writes a run folder under runs/ (git-ignored) and prints a short summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.eval.runner import RunError, RunOptions, run_scenario  # noqa: E402
from tools.godot_check import find_godot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/run_scenario.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", help="scenario id, e.g. SB04_POLITE_BID")
    parser.add_argument("--mode", default="stepped", choices=["stepped", "live"])
    parser.add_argument("--model", default="none")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--body", action="append", default=[], metavar="AVATAR=BODY")
    parser.add_argument("--out", type=Path, default=None, help="run folder (default: runs/<scenario>_<seed>_<time>)")
    parser.add_argument("--watch", action="store_true", help="open the Godot window instead of running headless")
    parser.add_argument("--jitter-ms", type=int, default=0, help="test: random delay before each agent answer")
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
                      godot_args=args.godot_arg)
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
    for agent_id, stats in s["agents"].items():
        print(f"  {agent_id}: {stats['decisions']} decisions, {stats['requests']} requests, "
              f"{stats['fallbacks']} fallbacks, level {stats['cognition']}, {stats['open_commitments']} open promises; "
              f"results {json.dumps(s['actions_by_agent'].get(agent_id, {}), sort_keys=True)}")
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
