"""Compare runs side by side from their summary.json files (G3d, D-69).

    uv run python tools/compare_runs.py runs/<pulse on> runs/<pulse off>
    uv run python tools/compare_runs.py runs/<headless> runs/<rendered> --agent robot_r

For the pulse on/off and headless/rendered comparisons: keep the scene, seed, models and render
preset the same and change one thing. Prints a Markdown table of what each run measured: offered
vs accepted actions, response latency, timeouts and fallbacks, model calls, glances, FN-1
continuity, Robot R's model-call latency, NPC throughput, frame pacing and peak VRAM. Reads only
summary.json and the decision records' timings (no prompt or memory text is printed), so the
table is safe to paste.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _pct(values: list[float], q: float):
    if not values:
        return None
    vals = sorted(values)
    return vals[min(len(vals) - 1, int(q * (len(vals) - 1) + 0.5))]


def model_latency(run_dir: Path, agent: str) -> dict:
    """The agent's model-call totals (ms) and other agents' calls per minute (NPC throughput)."""
    path = run_dir / "sidecar" / "decision_records.jsonl"
    mine, others = [], 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            for call in rec["model_calls"]:
                if rec["agent_id"] == agent:
                    mine.append(call["timings"]["total_ms"])
                else:
                    others += 1
    return {"p50": _pct(mine, 0.5), "p95": _pct(mine, 0.95), "n": len(mine), "npc_calls": others}


def column(run_dir: Path, agent: str) -> dict[str, str]:
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    r = (s.get("report") or {}).get(agent, {})
    render = s.get("render") or {}
    frames = render.get("frames") or {}
    vram = render.get("vram") or {}
    lat = r.get("response_latency_ms", {})
    m = model_latency(run_dir, agent)
    minutes = (s.get("ticks_run") or 0) / 60 / 60
    pulse = (s.get("pulse") or {}).get(agent, {})
    return {
        "scenario / seed / mode": f"{manifest['scenario_id']} / {manifest['seed']} / {manifest['simulation']['mode']}",
        "models": f"{manifest['resolved_settings'].get('model')}",
        "pulse": "on" if render.get("pulse") else "off",
        "render": "headless" if render.get("headless", True) else f"{render.get('resolution')} {render.get('preset')}",
        "actions accepted / offered": f"{r.get('actions', {}).get('accepted')} / {r.get('actions', {}).get('offered')}",
        "dropped before sending": str(r.get("actions", {}).get("dropped_before_send")),
        "response latency p50 / p95 ms (n, unanswered)": f"{lat.get('p50')} / {lat.get('p95')} ({lat.get('n')}, {lat.get('unanswered')})",
        "model calls / timeouts / fallbacks": f"{r.get('model_calls')} / {r.get('timeouts')} / {sum((r.get('fallbacks') or {}).values())}",
        f"{agent} model call p50 / p95 ms (n)": f"{m['p50']} / {m['p95']} ({m['n']})",
        "NPC model calls per minute": f"{m['npc_calls'] / minutes:.1f}" if minutes else "-",
        "glances accepted": str(r.get("glances_accepted")),
        "zombie events (accepted)": str(pulse.get("zombie", {}).get("events")) if pulse else "pulse off",
        "FN-1 departures mid-conversation (without goodbye)":
            f"{r.get('fn1', {}).get('departures_mid_conversation')} ({r.get('fn1', {}).get('without_goodbye')})",
        "frame p50 / p95 / p99 ms": f"{frames.get('p50_ms')} / {frames.get('p95_ms')} / {frames.get('p99_ms')}"
        if frames.get("available") else "not recorded",
        "frame spikes (target p95 <= 16.7 ms)": f"{frames.get('spikes')} ({ {True: 'met', False: 'not met', None: 'n/a headless'}[frames.get('meets_target')] })"
        if frames.get("available") else "-",
        "peak VRAM MiB": str(vram.get("peak_mib")) if vram else "not sampled",
        "Godot video memory peak MiB": str(frames.get("godot_video_mem_peak_mib")) if frames.get("available") else "-",
        "layer viewer (G4a): mode / open s / redraws":
            f"{frames.get('viewer_mode')} / {frames.get('viewer_open_s')} / {frames.get('viewer_draws')}"
            if frames.get("available") and frames.get("viewer_mode") else "-",
        "event loop lag p95 ms": str((s.get("event_loop_lag_ms") or {}).get("p95")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/compare_runs.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--agent", default="robot_r")
    args = parser.parse_args(argv)
    cols = [column(r, args.agent) for r in args.runs]
    names = [r.name[-28:] for r in args.runs]
    print("| measure | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for key in cols[0]:
        print(f"| {key} | " + " | ".join(c[key] for c in cols) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
