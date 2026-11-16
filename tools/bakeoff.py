"""Model bake-off (D-20, D-55; G3b-2). Results go to results/bakeoff/results.md and results.json.

    uv run python tools/bakeoff.py offline                       # every core model you have x KV f16, q8_0
    uv run python tools/bakeoff.py offline --models F1 F2 F3 --kv f16 q8_0
    uv run python tools/bakeoff.py live --models F1 F3           # finalists: SB-04 live and stepped
    uv run python tools/bakeoff.py report                        # print results.md again

    uv run python tools/bakeoff.py build-set                     # maintainers: rebuild bakeoff/prompts_v1.jsonl

**offline** sends every prompt of the committed prompt set (Robot R's logged SB-04 decisions,
in each robot body) to each model under each KV cache type, at temperature 0, with no Godot
running, one llama-server at a time. **live** runs SB-04 in Godot (headless) in LIVE and STEPPED
mode for each finalist, through tools/run_scenario.py's runner. Both add to results.json and
rewrite results.md: paste that file back.

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
from range_service.configs import load_and_check  # noqa: E402
from range_service.eval import bakeoff as bk  # noqa: E402
from range_service.models import registry as reg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PROMPT_SET = REPO / "bakeoff" / "prompts_v1.jsonl"
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
    raw = path.read_bytes()
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
    persona = cs.items["personas"][scenario["cast"]["robot_r"]["persona"]]
    items = []
    with tempfile.TemporaryDirectory(prefix="bakeoff_set_") as tmp:
        for body_id in args.bodies:
            out = Path(tmp) / body_id
            print(f"SB-04 with Robot R as {body_id} (Demo policy through the fake model)...")
            asyncio.run(run_scenario(RunOptions("SB04_POLITE_BID", godot, model="fake", out_dir=out,
                                                body_overrides={"robot_r": body_id}, timeout_s=900)))
            prompts = {}
            for line in (out / "sidecar" / "prompts.jsonl").read_text(encoding="utf-8").splitlines():
                p = json.loads(line)
                prompts[p["decision_id"]] = p["prompt"]
            body = cs.items["bodies"][body_id]
            available = sorted(expression_rules.available(body, cs.items["expressions"]))
            for line in (out / "sidecar" / "decision_records.jsonl").read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec["agent_id"] != "robot_r" or not rec["model_calls"] or rec["decision_id"] not in prompts:
                    continue
                demo = rec["model_calls"][0]["response_text"] or ""
                actions, _, _ = parse_output(demo, persona["allowed_actions"], "robot_r", rec["based_on_tick_id"])
                prompt = prompts[rec["decision_id"]]
                items.append({
                    "item_id": f"sb04_{body_id}_{rec['decision_id']}", "scenario": "SB04_POLITE_BID",
                    "agent_id": "robot_r", "tier": rec["tier"], "triggers": rec["triggers"], "body_id": body_id,
                    "allowed_actions": persona["allowed_actions"], "gestures": body["gestures"], "expressions": available,
                    "max_tokens": OUTPUT_CAPS.get(rec["tier"], 120), "based_on_tick_id": rec["based_on_tick_id"],
                    "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "reference": {"demo_answer": demo,
                                  "demo_fulfilled": any(a.get("fulfills_commitment") for a in actions or [])},
                })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(i, sort_keys=True) + "\n" for i in items), encoding="utf-8")
    print(f"Wrote {len(items)} prompts to {args.out}")
    return 0


# ---------- offline ----------

async def _run_condition(entry: dict, kv: str, items: list[dict], inf: dict, limit: int | None) -> dict:
    setup = build_llama(entry["id"], kv_cache_type=kv, inference=inf,
                        log_path=RESULTS / f"server_{entry['label']}_{kv}.log")
    started = time.perf_counter()
    await setup.gateway.start()
    load_s = round(time.perf_counter() - started, 1)
    proc = setup.provider.server.process if setup.provider.server else None
    vram, note = bk.vram_mib(proc.pid if proc else None)
    scored = []
    try:
        for n, item in enumerate(items[:limit] if limit else items, start=1):
            result = await setup.gateway.decide(agent_id=item["agent_id"], tier=item["tier"], prompt=item["prompt"],
                                                prompt_sha256=item["prompt_sha256"], max_tokens=item["max_tokens"],
                                                allowed_actions=item["allowed_actions"], tick=item["based_on_tick_id"])
            s = bk.score_item(item, result)
            scored.append(s)
            print(f"\r  {entry['label']} {kv}: {n}/{len(items[:limit] if limit else items)} "
                  f"({'ok' if s['final_valid'] else s['fallback']})   ", end="", flush=True)
    finally:
        await setup.gateway.stop()
    print()
    return {"label": entry["label"], "id": entry["id"], "model": entry["model"], "quant": entry["quant"],
            "qat": entry["qat"], "kv": kv, "sha256": setup.model.sha256, "load_s": load_s,
            "vram_mib": vram, "vram_note": note, "summary": bk.summarize_condition(scored), "items": scored}


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
    results.update({"prompt_set": args.set.name, "prompt_set_sha256": set_sha})
    print(f"{len(entries)} model(s) x {len(args.kv)} KV type(s) x {len(items[:args.limit] if args.limit else items)} prompts")
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

def cmd_live(args: argparse.Namespace) -> int:
    from range_service.eval.runner import RunError, RunOptions, run_scenario
    from tools.godot_check import find_godot

    godot = find_godot()
    if godot is None:
        print("Godot not found (set GODOT_BIN or run tools/install_godot.py)")
        return 2
    catalog = reg.load_catalog()
    results = _load_results()
    for name in args.models:
        entry = reg.catalog_entry(catalog, name)
        for mode in args.modes:
            out = RESULTS / f"run_{entry['label']}_{mode.lower()}"
            print(f"SB-04 {mode} with {entry['label']} {entry['model']} {entry['quant']}...")
            try:
                r = asyncio.run(run_scenario(RunOptions("SB04_POLITE_BID", godot, mode=mode, model=f"llama:{entry['id']}",
                                                        out_dir=out, timeout_s=1800)))
            except RunError as exc:
                print(f"  FAILED: {exc}")
                continue
            calls = [c for line in (out / "sidecar" / "decision_records.jsonl").read_text(encoding="utf-8").splitlines()
                     for c in json.loads(line)["model_calls"]]
            totals = sorted(c["timings"]["total_ms"] for c in calls)
            p95 = totals[min(len(totals) - 1, int(round(0.95 * (len(totals) - 1))))] if totals else None
            s = r.summary
            row = {"label": f"{entry['label']} {entry['model']} {entry['quant']}", "mode": mode,
                   "ok": r.exit_code == 0 and not r.godot_errors and not s["sidecar_problems"],
                   "decisions": len(calls), "timeouts": sum(c["outcome"] == "TIMEOUT" for c in calls),
                   "fallbacks": s["agents"]["robot_r"]["fallbacks"], "p50_ms": bk._median([float(t) for t in totals]),
                   "p95_ms": p95, "journal": r.journal_sha256 or "", "run_dir": str(out)}
            results["live"] = [x for x in results["live"] if (x["label"], x["mode"]) != (row["label"], mode)] + [row]
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
    p_set.add_argument("--out", type=Path, default=PROMPT_SET)
    p_set.add_argument("--bodies", nargs="+", default=list(BODIES))
    p_off = sub.add_parser("offline")
    p_off.add_argument("--models", nargs="*", default=[])
    p_off.add_argument("--kv", nargs="+", default=["f16", "q8_0"], choices=["f16", "q8_0", "q4_0"])
    p_off.add_argument("--set", type=Path, default=PROMPT_SET)
    p_off.add_argument("--limit", type=int, default=None, help="only the first N prompts (smoke tests)")
    p_live = sub.add_parser("live")
    p_live.add_argument("--models", nargs="+", required=True)
    p_live.add_argument("--modes", nargs="+", default=["LIVE", "STEPPED"], choices=["LIVE", "STEPPED"])
    sub.add_parser("report")
    args = parser.parse_args(argv)
    try:
        return {"build-set": cmd_build_set, "offline": cmd_offline, "live": cmd_live, "report": cmd_report}[args.command](args)
    except reg.ModelError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
