"""G3f (D-75 to D-78): the Robot R conditions on a simulated shared GPU, faster than real time.

    uv run python tools/contention_sim.py                  # every condition, LIVE and LIVE_LOAD, F3 and F1 with N3
    uv run python tools/contention_sim.py --minutes 5 --scale 0.1 --robot F3 --npc N3 S1

Runs the real ``ModelGateway``, ``SlotScheduler`` (slots, priorities, deadlines, stale-drop) and
``FocalGuard`` from configs/inference.yaml against ``agents/simgpu.py``: Robot R's server and the
NPC server on one simulated GPU, with each model's speeds from the owner's offline bake-off.
Every time (deadlines, aging, the GPU) runs ``--scale`` times faster than real time.

The workload follows the owner's 2026-11-18 SB-04 LIVE runs (F3 + N3): Robot R decides about
every 7.5 s (36 calls in 270 s), one call at a time; two visitors make C2 calls about every 16 s
each (33 NPC calls in 270 s); LIVE_LOAD adds three synthetic NPC streams, as the bake-off does
(all NPC slots but one). Prompt sizes: Robot R ~1900 tokens with a ~700-token persona prefix
(guardrails + identity, D-51 budgets), C2 ~1300 with ~850, load prompts ~650 with ~400. The
arrivals are seeded, so every condition sees the same workload.

**A model of the mechanism, not a measurement.** It shows which conditions help and roughly how
much under the stated assumptions (agents/simgpu.py). The owner's PC measures each one for real
(docs/gates/G3f_OWNER_CHECKLIST.md). Prints a table and writes ``results/contention_sim.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.agents.gateway import ModelGateway, ServerActivity  # noqa: E402
from range_service.agents.inference import load_inference  # noqa: E402
from range_service.agents.scheduler import FocalGuard, SlotScheduler  # noqa: E402
from range_service.agents.simgpu import SimGpu, SimGpuModel  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CONDITIONS = {   # name -> (prompt_layout, answer, gpu_guard, npc_cap)
    "baseline": ("ONE_MESSAGE", "FULL", False, 0),
    "system_prefix": ("SYSTEM_PREFIX", "FULL", False, 0),
    "short": ("ONE_MESSAGE", "SHORT", False, 0),
    "guard_cap0": ("ONE_MESSAGE", "FULL", True, 0),
    "guard_cap1": ("ONE_MESSAGE", "FULL", True, 1),
    "short_guard0": ("ONE_MESSAGE", "SHORT", True, 0),
    "all_three": ("SYSTEM_PREFIX", "SHORT", True, 0),
}
ROBOT_EVERY_S, NPC_EVERY_S, VISITORS, LOAD_STREAMS = 7.5, 16.0, 2, 3
ACTIONS = ["SPEAK", "WAIT", "LOOK_AT"]


def _prompt(prefix_tokens: int, total_tokens: int, tag: str, rng: random.Random) -> tuple[str, str]:
    prefix = f"## GUARDRAILS {tag}\n" + "rule " * (prefix_tokens * 4 // 5)
    prefix = prefix[: prefix_tokens * 4]
    body = "\n\n## COMMITMENTS\n" + "".join(rng.choice("abcdefgh ") for _ in range((total_tokens - prefix_tokens) * 4))
    return prefix, prefix + body


def _hint(text_chars: int) -> str:
    return json.dumps({"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "w" * text_chars,
                                                               "addressee_id": "anon_x0000001"}}]})


def _scaled(inf: dict, scale: float) -> tuple[dict, dict]:
    deadlines = {t: max(1, round(s["deadline_ms"] * scale)) for t, s in inf["tiers"].items()}
    sched = dict(inf["scheduler"], aging_ms=max(1, round(inf["scheduler"]["aging_ms"] * scale)),
                 min_service_ms=max(1, round(inf["scheduler"]["min_service_ms"] * scale)))
    return deadlines, sched


async def run_cell(robot: str, npc: str, workload: str, condition: str, minutes: float, scale: float, seed: int) -> dict:
    layout, answer, guard_on, cap = CONDITIONS[condition]
    inf = load_inference()
    deadlines, sched = _scaled(inf, scale)
    deadlines["LOAD"] = deadlines["C1"]
    gpu = SimGpu(time_scale=scale)
    focal_sched = SlotScheduler(inf["servers"]["focal"]["parallel_slots"], pinned_tiers=("FOCAL",),
                                reserved=sched["reserved_slots"], priorities=sched["priorities"],
                                aging_ms=sched["aging_ms"], min_service_ms=sched["min_service_ms"])
    npc_sched = SlotScheduler(inf["servers"]["npc"]["parallel_slots"], pinned_tiers=(), reserved=0,
                              priorities=sched["priorities"], aging_ms=sched["aging_ms"],
                              min_service_ms=sched["min_service_ms"])
    focal = ModelGateway(SimGpuModel(gpu, robot, server="focal"), deadlines_ms=deadlines, scheduler=focal_sched, server="focal")
    npcg = ModelGateway(SimGpuModel(gpu, npc, server="npc"), deadlines_ms=deadlines, scheduler=npc_sched, server="npc")
    shared = ServerActivity()
    focal.activity = npcg.activity = shared
    focal.prompt_layout, focal.answer = layout, answer
    guard = None
    if guard_on:
        guard = FocalGuard(cap)
        focal.guard = guard
        npc_sched.set_guard(guard)
    rng = random.Random(seed)
    end = time.monotonic() + minutes * 60 * scale
    robot_calls: list[dict] = []
    npc_calls: list[dict] = []

    async def agent(agent_id: str, tier: str, every_s: float, prefix_tok: int, total_tok: int, text_chars: int,
                    out: list[dict], gw: ModelGateway, stream: bool = False) -> None:
        arng = random.Random(f"{seed}:{agent_id}")
        while time.monotonic() < end:
            if not stream:
                await asyncio.sleep(arng.expovariate(1.0 / every_s) * scale)
                if time.monotonic() >= end:
                    return
            prefix, prompt = _prompt(prefix_tok, total_tok + arng.randint(-150, 150), agent_id, arng)
            result = await gw.decide(agent_id=agent_id, tier=tier, prompt=prompt,
                                     prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), max_tokens=200 if tier == "FOCAL" else 220,
                                     allowed_actions=ACTIONS, tick=1, demo_hint=_hint(text_chars),
                                     prefix=prefix if (tier != "FOCAL" or layout == "SYSTEM_PREFIX") else None)
            out.extend(result.model_calls)
            await asyncio.sleep(0)

    tasks = [asyncio.create_task(agent("robot_r", "FOCAL", ROBOT_EVERY_S, 700, 1900, 90, robot_calls, focal))]
    tasks += [asyncio.create_task(agent(f"visitor_{k}", "C2", NPC_EVERY_S, 850, 1300, 70, npc_calls, npcg))
              for k in range(VISITORS)]
    if workload == "LIVE_LOAD":
        tasks += [asyncio.create_task(agent(f"npc_load_{k}", "LOAD", 0, 400, 650, 60, npc_calls, npcg, stream=True))
                  for k in range(LOAD_STREAMS)]
    await asyncio.gather(*tasks)

    def unscale(v):
        return None if v is None else round(v / scale)

    def pct(values, q):
        vals = sorted(v for v in values if v is not None)
        return vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))] if vals else None
    rt = [c["timings"]["total_ms"] for c in robot_calls]
    real_npc = [c for c in npc_calls if not c["call_id"].startswith("call_npc_load")]
    load = [c for c in npc_calls if c["call_id"].startswith("call_npc_load")]
    return {"robot": robot, "npc": npc, "workload": workload, "condition": condition,
            "robot_calls": len(robot_calls), "robot_timeouts": sum(c["outcome"] == "TIMEOUT" for c in robot_calls),
            "robot_p50_ms": unscale(pct(rt, 0.5)), "robot_p95_ms": unscale(pct(rt, 0.95)),
            "robot_gen_p50_ms": unscale(pct([c["timings"]["generation_ms"] for c in robot_calls], 0.5)),
            "robot_prefill_p50_ms": unscale(pct([c["timings"]["prefill_ms"] for c in robot_calls], 0.5)),
            "robot_generated_tokens_p50": pct([c["generated_tokens"] for c in robot_calls], 0.5),
            "npc_calls": len(real_npc), "npc_timeouts": sum(c["outcome"] == "TIMEOUT" for c in real_npc),
            "npc_p50_ms": unscale(pct([c["timings"]["total_ms"] for c in real_npc], 0.5)),
            "npc_p95_ms": unscale(pct([c["timings"]["total_ms"] for c in real_npc], 0.95)),
            "load_calls": len(load), "load_timeouts": sum(c["outcome"] == "TIMEOUT" for c in load),
            "guard": dict(guard.stats) if guard else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/contention_sim.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--robot", nargs="+", default=["F3", "F1"])
    parser.add_argument("--npc", nargs="+", default=["N3"])
    parser.add_argument("--workloads", nargs="+", default=["LIVE", "LIVE_LOAD"], choices=["LIVE", "LIVE_LOAD"])
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(CONDITIONS))
    parser.add_argument("--minutes", type=float, default=10.0, help="simulated minutes per cell")
    parser.add_argument("--scale", type=float, default=0.1, help="wall-clock seconds per simulated second")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=REPO / "results" / "contention_sim.json")
    args = parser.parse_args(argv)
    rows = []
    print("| Robot R | NPC | Workload | Condition | Robot R calls | Timeouts | p50 / p95 ms | prefill / gen p50 ms | "
          "gen tokens p50 | NPC calls (timeouts) | NPC p50 / p95 ms | Load calls (timeouts) | Target |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for robot in args.robot:
        for npc in args.npc:
            for workload in args.workloads:
                for cond in args.conditions:
                    r = asyncio.run(run_cell(robot, npc, workload, cond, args.minutes, args.scale, args.seed))
                    share = r["robot_timeouts"] / r["robot_calls"] if r["robot_calls"] else None
                    r["target_met"] = bool(r["robot_p95_ms"] is not None and r["robot_p95_ms"] < 4000 and share is not None
                                           and share <= 0.05)
                    rows.append(r)
                    print(f"| {robot} | {npc} | {workload} | {cond} | {r['robot_calls']} | {r['robot_timeouts']} "
                          f"({share:.0%}) | {r['robot_p50_ms']} / {r['robot_p95_ms']} | {r['robot_prefill_p50_ms']} / "
                          f"{r['robot_gen_p50_ms']} | {r['robot_generated_tokens_p50']} | {r['npc_calls']} ({r['npc_timeouts']}) | "
                          f"{r['npc_p50_ms']} / {r['npc_p95_ms']} | {r['load_calls']} ({r['load_timeouts']}) | "
                          f"{'met' if r['target_met'] else 'NOT met'} |", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"assumptions": "agents/simgpu.py; workload in tools/contention_sim.py",
                                    "minutes": args.minutes, "scale": args.scale, "seed": args.seed, "rows": rows},
                                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nWritten: {args.out}  (a model of the mechanism: the owner's PC measures each condition for real)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
