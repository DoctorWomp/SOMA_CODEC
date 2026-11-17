"""Model bake-off (D-20, D-55; G3b-2). Results go to results/bakeoff/results.md and results.json.

    uv run python tools/bakeoff.py offline                       # every core model you have x KV f16, q8_0
    uv run python tools/bakeoff.py offline --models N1 N3 S1 --kv q8_0
    uv run python tools/bakeoff.py offline --set bakeoff/prompts_v1.jsonl   # the G3b set, for comparison
    uv run python tools/bakeoff.py live --models F3 F1 --npc-model N3       # Option C runs of SB-04
    uv run python tools/bakeoff.py report                        # print results.md again

    uv run python tools/bakeoff.py build-set                     # maintainers: rebuild bakeoff/prompts_v3.jsonl

**offline** sends every prompt of the prompt set to each model under each KV cache type, at
temperature 0, with no Godot running, one llama-server at a time. prompts_v2 (G3c-1, the
default) holds Robot R's SB-04 decisions in each robot body, the visitors' own C1/C2 decisions
from the same runs (so NPC candidates are scored on NPC prompts), and 16 promise situations;
results show Robot R and NPC prompts in separate tables. prompts_v1 (G3b) stays unchanged.
**live** runs SB-04 in Godot (headless) with Option C, the model under test on Robot R's
server and the NPC model on the NPC server, in four modes: LIVE, LIVE_COLD (no pre-warming),
LIVE_LOAD (synthetic NPC calls keep the NPC server busy) and STEPPED. It reports Robot R's
p50/p95, NPC calls, promotion latency warm and cold, and VRAM per server. Both commands add to
results.json and rewrite results.md: paste that file back.

Nothing is downloaded: models come from your registry (tools/models.py). Needs an NVIDIA GPU for
meaningful speeds; on a CPU it runs, slowly (the cloud smoke test uses model T1).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service import expressions as expression_rules  # noqa: E402
from range_service.agents.gateway import ProviderError, parse_output  # noqa: E402
from range_service.agents.inference import ENGINE, build_llama, load_inference  # noqa: E402
from range_service.agents.runtime import OUTPUT_CAPS  # noqa: E402
from range_service.eval.promptset import promise_items  # noqa: E402
from range_service.configs import load_and_check  # noqa: E402
from range_service.eval import bakeoff as bk  # noqa: E402
from range_service.models import registry as reg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PROMPT_SET_V1 = REPO / "bakeoff" / "prompts_v1.jsonl"
PROMPT_SET_V2 = REPO / "bakeoff" / "prompts_v2.jsonl"  # G3c-1: Robot R, NPCs and promise situations
PROMPT_SET = REPO / "bakeoff" / "prompts_v3.jsonl"     # G3c-2: C1 formats and observations, answer choices
RESULTS = REPO / "results" / "bakeoff"
BODIES = ("wheeled_humanoid", "legged_humanoid", "quadruped", "quadruped_arm")


def _load_results() -> dict:
    path = RESULTS / "results.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"offline": [], "live": []}


def _save(results: dict) -> None:
    results["created"] = time.strftime("%Y-%m-%d %H:%M")
    results["engine"] = ENGINE
    j, m = bk.write_report(results, RESULTS)
    print(f"\nResults: {m}\n         {j}")


def load_set(path: Path) -> tuple[list[dict], str]:
    """The prompt set and its SHA-256, taken over LF line endings: a Windows checkout with CRLF
    gives the same hash (the first bake-off's 93e215698db0 is prompts_v1 with CRLF, ee2b7c03be96)."""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()], hashlib.sha256(raw).hexdigest()


# ---------- build-set ----------

def cmd_build_set(args: argparse.Namespace) -> int:
    from range_service.eval.runner import RunOptions, run_scenario
    from tools.godot_check import find_godot

    godot = find_godot()
    if godot is None:
        print("Godot not found (set GODOT_BIN or run tools/install_godot.py)")
        return 2
    cs, problems = load_and_check()
    if problems:
        print("configs have problems; run tools/validate_configs.py")
        return 1
    scenario = cs.items["scenarios"]["SB04_POLITE_BID"]
    items = []
    with tempfile.TemporaryDirectory(prefix="bakeoff_set_") as tmp:
        for body_id in args.bodies:
            out = Path(tmp) / body_id
            print(f"SB-04 with Robot R as {body_id} (Demo policy and NPC templates through the fake model)...")
            asyncio.run(run_scenario(RunOptions("SB04_POLITE_BID", godot, model="fake", out_dir=out,
                                                body_overrides={"robot_r": body_id}, timeout_s=900)))
            prompts = {}
            for line in (out / "sidecar" / "prompts.jsonl").read_text(encoding="utf-8").splitlines():
                p = json.loads(line)
                prompts[p["decision_id"]] = p
            for line in (out / "sidecar" / "decision_records.jsonl").read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if not rec["model_calls"] or rec["decision_id"] not in prompts:
                    continue
                agent = rec["agent_id"]
                entry = scenario["cast"][agent]
                persona = cs.items["personas"][entry["persona"]]
                role = "ROBOT_R" if agent == "robot_r" else "NPC"
                agent_body_id = body_id if role == "ROBOT_R" else entry["body"]
                body = cs.items["bodies"][agent_body_id]
                available = sorted(expression_rules.available(body, cs.items["expressions"]))
                demo = rec["model_calls"][0]["response_text"] or ""
                actions, _, _ = parse_output(demo, persona["allowed_actions"], agent, rec["based_on_tick_id"])
                prompt = prompts[rec["decision_id"]]["prompt"]
                choices = prompts[rec["decision_id"]].get("choices")
                items.append({
                    "item_id": f"sb04_{body_id}_{rec['decision_id']}", "scenario": "SB04_POLITE_BID", "role": role,
                    "agent_id": agent, "tier": rec["tier"], "triggers": rec["triggers"], "body_id": agent_body_id,
                    "allowed_actions": persona["allowed_actions"], "gestures": body["gestures"], "expressions": available,
                    "max_tokens": OUTPUT_CAPS.get(rec["tier"], 120), "based_on_tick_id": rec["based_on_tick_id"],
                    "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "choices": choices,
                    "reference": {"demo_answer": demo,
                                  "demo_fulfilled": any(a.get("fulfills_commitment") for a in actions or [])},
                })
    # SB-05 has no NPCs (its cast is Robot R in three bodies), so it adds no NPC contexts.
    items += promise_items(cs, tuple(args.bodies))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(i, sort_keys=True) + "\n" for i in items), encoding="utf-8")
    print(f"Wrote {len(items)} prompts to {args.out}")
    return 0


# ---------- offline ----------

def limited(items: list[dict], limit: int | None) -> list[dict]:
    """The first ``limit`` prompts of each role (smoke tests), or all."""
    if not limit:
        return items
    out, seen = [], {}
    for item in items:
        role = item.get("role", "ROBOT_R")
        if seen.get(role, 0) < limit:
            seen[role] = seen.get(role, 0) + 1
            out.append(item)
    return out


def npc_prefix(item: dict) -> str | None:
    """NPC prompts are sent as in a run: the persona prefix (guardrails + identity) as its own
    system message (configs/inference.yaml personas.system_prefix). Robot R's stay one message."""
    if item.get("role") != "NPC":
        return None
    head, sep, _ = item["prompt"].partition("\n\n## COMMITMENTS")
    return head if sep else None

async def _run_condition(entry: dict, kv: str, items: list[dict], inf: dict, limit: int | None) -> dict:
    setup = build_llama(entry["id"], kv_cache_type=kv, inference=inf,
                        log_path=RESULTS / f"server_{entry['label']}_{kv}.log")
    total_before = bk.gpu_memory_used_mib()     # for Windows, where per-process memory is N/A
    started = time.perf_counter()
    await setup.gateway.start()
    load_s = round(time.perf_counter() - started, 1)
    proc = setup.provider.server.process if setup.provider.server else None
    vram, note = bk.vram_mib(proc.pid if proc else None, total_before)
    scored = []
    progress = bk.Progress()
    todo = limited(items, limit)
    try:
        for n, item in enumerate(todo, start=1):
            result = await setup.gateway.decide(agent_id=item["agent_id"], tier=item["tier"], prompt=item["prompt"],
                                                prompt_sha256=item["prompt_sha256"], max_tokens=item["max_tokens"],
                                                allowed_actions=item["allowed_actions"], tick=item["based_on_tick_id"],
                                                prefix=npc_prefix(item), choices=item.get("choices"))
            s = bk.score_item(item, result)
            scored.append(s)
            progress.update(f"  {entry['label']} {kv}: {n}/{len(todo)} ({'ok' if s['final_valid'] else s['fallback']})")
    finally:
        progress.done()
        await setup.gateway.stop()
    return {"label": entry["label"], "id": entry["id"], "model": entry["model"], "quant": entry["quant"],
            "qat": entry["qat"], "kv": kv, "sha256": setup.model.sha256, "load_s": load_s,
            "vram_mib": vram, "vram_note": note, "summary": bk.summarize_condition(scored),
            "summary_by_role": bk.summarize_by_role(scored), "items": scored}


def cmd_offline(args: argparse.Namespace) -> int:
    catalog = reg.load_catalog()
    registry = reg.Registry.load()
    if args.models:
        entries = [reg.catalog_entry(catalog, m) for m in args.models]
    else:
        entries = [e for e in catalog["models"] if e["set"] == "CORE" and registry.find(e["id"])]
    missing = [e["label"] for e in entries if not registry.find(e["id"])]
    if missing:
        print(f"Not on this machine: {', '.join(missing)}. Run tools/models.py plan.")
        return 1
    if not entries:
        print("No core model is registered yet. Run tools/models.py scan / download first.")
        return 1
    items, set_sha = load_set(args.set)
    inf = load_inference()
    for tier in inf["tiers"].values():
        tier["deadline_ms"] = 120000          # offline: no deadline pressure; speed is measured instead
    inf["scheduler"]["mode"] = "FIFO"
    results = _load_results()
    if results.get("prompt_set_sha256") not in (None, set_sha) and results["offline"]:
        print(f"Note: results.json held offline results for another prompt set ({results.get('prompt_set')}); "
              "they are moved to results_previous_set.json so sets are never mixed.")
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "results_previous_set.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        results["offline"] = []
    results.update({"prompt_set": args.set.name, "prompt_set_sha256": set_sha})
    print(f"{len(entries)} model(s) x {len(args.kv)} KV type(s) x {len(limited(items, args.limit))} prompts")
    for entry in entries:
        for kv in args.kv:
            try:
                cond = asyncio.run(_run_condition(entry, kv, items, inf, args.limit))
            except ProviderError as exc:
                print(f"  {entry['label']} {kv}: FAILED: {exc}")
                continue
            results["offline"] = [c for c in results["offline"] if (c["label"], c["kv"]) != (entry["label"], kv)] + [cond]
            _save(results)
    by_key = {(c["label"], c["kv"]): c for c in results["offline"]}
    for c in results["offline"]:
        ref = bk.reference_for(c, [o for o in results["offline"] if o["kv"] == c["kv"]])
        ag = bk.agreement(c["items"], ref["items"]) if ref else None
        c["agreement_precision"] = dict(ag, reference=f"{ref['label']} {ref['quant']}") if ag else None
        f16 = by_key.get((c["label"], "f16"))
        c["agreement_kv"] = bk.agreement(c["items"], f16["items"]) if c["kv"] != "f16" and f16 else None
    _save(results)
    return 0


# ---------- live ----------

# mode -> (run mode, pre-warm, persona snapshots, synthetic NPC load). LIVE_COLD switches off both
# pre-warming and snapshots: with snapshots on, a promotion's first call restores its prefix and is
# never cold (G3c-2, D-60). LIVE_LOAD keeps all NPC slots but one busy ("slots - 1" streams), so a
# real NPC call always finds a slot.
LIVE_MODES = {"LIVE": ("LIVE", True, True, 0), "LIVE_COLD": ("LIVE", False, False, 0),
              "LIVE_LOAD": ("LIVE", True, True, -1), "STEPPED": ("STEPPED", True, True, 0)}


def _p(values: list[float], q: float) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return float(vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))]) if vals else None


def live_row(entry: dict, npc_label: str, mode: str, runs: list[tuple[Path, object]]) -> dict:
    """One live row over all repeats: Robot R's calls only for its latency; NPC calls (queue,
    prefill, generation, and how long Robot R's server was busy meanwhile), Robot R's action
    outcomes (accepted or stale), promotions, event-loop lag and VRAM apart."""
    robot, npc, promos, lags, accepted, stale, journals = [], [], [], [], 0, 0, []
    ok = True
    s = None
    for out, r in runs:
        for line in (out / "sidecar" / "decision_records.jsonl").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            (robot if rec["agent_id"] == "robot_r" else npc).extend(rec["model_calls"])
        promos += [json.loads(line) for line in (out / "promotions.jsonl").read_text(encoding="utf-8").splitlines() if line]
        s = r.summary
        ok = ok and r.exit_code == 0 and not r.godot_errors and not s["sidecar_problems"]
        outcomes = s["actions_by_agent"].get("robot_r", {})
        accepted += outcomes.get("OK", 0)
        stale += outcomes.get("STALE_OBSERVATION", 0)
        lags.append((s.get("event_loop_lag_ms") or {}).get("p95"))
        journals.append(r.journal_sha256 or "")
    from range_service.eval.runner import promotion_summary   # noqa: PLC0415

    pr = promotion_summary(promos)
    manifest = json.loads((runs[-1][0] / "run_manifest.json").read_text(encoding="utf-8"))["resolved_settings"]
    tot = [c["timings"]["total_ms"] for c in robot]
    npc_t = lambda k: [c["timings"].get(k) for c in npc]   # noqa: E731
    busy = [c.get("other_server_busy_ms") for c in npc if c.get("other_server_busy_ms") is not None]
    npc_total = [c["timings"]["total_ms"] or 0 for c in npc if c.get("other_server_busy_ms") is not None]
    return {"label": f"{entry['label']} {entry['model']} {entry['quant']}", "npc_label": npc_label, "mode": mode,
            "repeats": len(runs), "option": s["inference"]["option"], "fallback": s["inference"]["fallback"], "ok": ok,
            "decisions": len(robot), "timeouts": sum(c["outcome"] == "TIMEOUT" for c in robot),
            "fallbacks": sum(c["outcome"] != "VALID" for c in robot), "p50_ms": _p(tot, 0.5), "p95_ms": _p(tot, 0.95),
            "robot_actions_accepted": accepted, "robot_actions_stale": stale,
            "npc_calls": len(npc), "npc_timeouts": sum(c["outcome"] == "TIMEOUT" for c in npc),
            "npc_p50_ms": _p(npc_t("total_ms"), 0.5), "npc_queue_p50_ms": _p(npc_t("queue_ms"), 0.5),
            "npc_prefill_p50_ms": _p(npc_t("prefill_ms"), 0.5), "npc_generation_p50_ms": _p(npc_t("generation_ms"), 0.5),
            "npc_robot_busy_share": round(sum(busy) / sum(npc_total), 2) if busy and sum(npc_total) else None,
            "loop_lag_p95_ms": max((x for x in lags if x is not None), default=None),
            "promotion_warm_p50_ms": pr["warm_p50_ms"], "promotion_warm_n": pr["warm_n"],
            "promotion_cold_p50_ms": pr["cold_p50_ms"], "promotion_cold_n": pr["cold_n"],
            "promotion_warm_to_call_p50_ms": pr["warm_to_first_call_p50_ms"],
            "promotion_cold_to_call_p50_ms": pr["cold_to_first_call_p50_ms"],
            "promotion_warm_call_p50_ms": pr["warm_first_call_p50_ms"],
            "promotion_cold_call_p50_ms": pr["cold_first_call_p50_ms"],
            "vram_focal_mib": manifest.get("vram.focal_mib"), "vram_npc_mib": manifest.get("vram.npc_mib"),
            "vram_note": manifest.get("vram.note"), "journal": journals[0], "journals": journals,
            "run_dir": str(runs[0][0])}


def cmd_live(args: argparse.Namespace) -> int:
    from range_service.agents.inference import load_inference as _inf
    from range_service.eval.runner import RunError, RunOptions, run_scenario
    from tools.godot_check import find_godot

    godot = find_godot()
    if godot is None:
        print("Godot not found (set GODOT_BIN or run tools/install_godot.py)")
        return 2
    catalog = reg.load_catalog()
    results = _load_results()
    npc_items = [i for i in load_set(PROMPT_SET)[0] if i.get("role") == "NPC"]
    npc_label = reg.catalog_entry(catalog, args.npc_model)["label"] if args.npc_model not in ("config", "none") else args.npc_model
    npc_slots = _inf()["servers"].get("npc", {}).get("parallel_slots", 1)
    for name in args.models:
        entry = reg.catalog_entry(catalog, name)
        for mode in args.modes:
            run_mode, prewarm, snapshots, load = LIVE_MODES[mode]
            load = max(1, npc_slots - 1) if load < 0 else load
            npc_spec = {"config": "auto", "none": "none"}.get(args.npc_model, f"llama:{args.npc_model}")
            runs = []
            for k in range(args.repeat):
                out = RESULTS / f"run_{entry['label']}_{mode.lower()}_{k + 1}"
                print(f"SB-04 {mode} {k + 1}/{args.repeat} with {entry['label']} {entry['model']} {entry['quant']} "
                      f"(NPC model: {npc_label})...")
                try:
                    r = asyncio.run(run_scenario(RunOptions(
                        "SB04_POLITE_BID", godot, mode=run_mode, model=f"llama:{entry['id']}", npc_model=npc_spec,
                        prewarm=prewarm, snapshots=snapshots, out_dir=out, timeout_s=1800,
                        npc_load_streams=load, npc_load_prompts=npc_items)))
                except RunError as exc:
                    print(f"  FAILED: {exc}")
                    continue
                runs.append((out, r))
            if not runs:
                continue
            row = live_row(entry, npc_label, mode, runs)
            if row["fallback"]:
                print(f"  NOTE: Option B (one server): {row['fallback']}")
            results["live"] = [x for x in results["live"] if (x["label"], x["mode"], x.get("npc_label")) !=
                               (row["label"], mode, npc_label)] + [row]
            _save(results)
    return 0


def cmd_report(_args: argparse.Namespace) -> int:
    results = _load_results()
    if not results["offline"] and not results["live"]:
        print("No results yet. Run: uv run python tools/bakeoff.py offline")
        return 1
    _save(results)
    print((RESULTS / "results.md").read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/bakeoff.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_set = sub.add_parser("build-set")
    p_set.add_argument("--out", type=Path, default=PROMPT_SET)   # never overwrite prompts_v1 (results stay comparable)
    p_set.add_argument("--bodies", nargs="+", default=list(BODIES))
    p_off = sub.add_parser("offline")
    p_off.add_argument("--models", nargs="*", default=[])
    p_off.add_argument("--kv", nargs="+", default=["f16", "q8_0"], choices=["f16", "q8_0", "q4_0"])
    p_off.add_argument("--set", type=Path, default=PROMPT_SET)
    p_off.add_argument("--limit", type=int, default=None, help="only the first N prompts of each role (smoke tests)")
    p_live = sub.add_parser("live")
    p_live.add_argument("--models", nargs="+", required=True)
    p_live.add_argument("--modes", nargs="+", default=list(LIVE_MODES), choices=list(LIVE_MODES))
    p_live.add_argument("--repeat", type=int, default=3,
                        help="runs per mode, pooled (one SB-04 is 90 s real time; G3c-2)")
    p_live.add_argument("--npc-model", default="config",
                        help="NPC server model: config (configs/inference.yaml), a catalog label such as N3, or none")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    try:
        return {"build-set": cmd_build_set, "offline": cmd_offline, "live": cmd_live, "report": cmd_report}[args.command](args)
    except reg.ModelError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
