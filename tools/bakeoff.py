"""Model bake-off (D-20, D-55; G3b-2). Results go to results/bakeoff/results.md and results.json.

    uv run python tools/bakeoff.py offline                       # every core model you have x KV f16, q8_0
    uv run python tools/bakeoff.py offline --models N1 N3 S1 --kv q8_0
    uv run python tools/bakeoff.py offline --set bakeoff/prompts_v1.jsonl   # the G3b set, for comparison
    uv run python tools/bakeoff.py live --models F3 F1 --npc-model N3       # Option C runs of SB-04
    uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_RENDERED \
        --resolution 1920x1080 --render-preset v0                           # the render tax (G3d)
    uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE --no-pulse  # pulse off (G3d)
    uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD \
        --focal-layout SYSTEM_PREFIX --focal-answer SHORT --gpu-guard on      # G3f conditions (D-76 to D-78)
    uv run python tools/bakeoff.py diagnose                      # G3f: Robot R's calls in existing run folders
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
p50/p95, NPC calls, promotion latency warm and cold, and VRAM per server. G3d (D-69): LIVE_RENDERED
is LIVE with the rendered client open at a declared resolution and render preset; every live row
records frame times (p50/p95/p99, spikes) and the peak VRAM sampled during the run, and results.md
compares LIVE with LIVE_RENDERED (the render tax, ART_DIRECTION §7) and pulse on with pulse off
(--no-pulse) where both were run. Both commands add to results.json and rewrite results.md:
paste that file back.

G3f (D-75 to D-78): every run gets a clean folder (several files are appended to during a run, and
the old harness pooled a folder's earlier run into the next row); each live row breaks Robot R's
calls down by outcome (timeout in the queue or at the model, invalid output by kind, repairs) and
by cost (queue, prefill, generation, prompt, cached and generated tokens, other server busy); the
conditions --focal-layout, --focal-answer and --gpu-guard are part of a row's identity, offline
too (--focal-layout, --focal-answer on Robot R's prompts). results.md leaves out rows from the
pre-G3c-2 harness (not real time) and marks rows that pooled an earlier run. ``diagnose`` reads
existing run folders (also the old pooled ones, split run by run) and writes diagnosis.md: counts
and timings only.

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
from range_service.eval import live_diag  # noqa: E402
from range_service.models import registry as reg  # noqa: E402
from range_service.agents import lean  # noqa: E402
from range_service.eval import tokens  # noqa: E402

PULSE_MAX_REVIEW_S = 600   # configs/pulse.yaml pulse.max_review_after_s, as a live run offers it

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


def npc_prefix(item: dict, focal_layout: str = "ONE_MESSAGE") -> str | None:
    """NPC prompts are sent as in a run: the persona prefix (guardrails + identity) as its own
    system message (configs/inference.yaml personas.system_prefix). Robot R's stay one message,
    unless the SYSTEM_PREFIX condition is asked for (G3f, D-76)."""
    if item.get("role") != "NPC" and focal_layout != "SYSTEM_PREFIX":
        return None
    head, sep, _ = item["prompt"].partition("\n\n## COMMITMENTS")
    return head if sep else None

def condition_key(c: dict) -> tuple:
    """An offline condition's identity: model, KV cache and Robot R's layout, answer (G3f) and
    whether its prompts offer an activity (G3g)."""
    return (c["label"], c["kv"], c.get("focal_layout", "ONE_MESSAGE"), c.get("focal_answer", "FULL"),
            bool(c.get("focal_activity")))


def focal_item(item: dict, focal_answer: str, activity: bool) -> dict:
    """A prompt-set item as Robot R gets it under an answer condition (G3g, D-85): only the
    answer-format lines of its prompt change (prompts_v3 holds FULL prompts without the pulse's
    activity format). With ``activity`` the prompt offers an activity, as with the pulse on in a
    live run. NPC items are never changed."""
    if item.get("role") == "NPC" or (focal_answer != "LEAN" and not activity):
        return item
    prompt = lean.rewrite_prompt(item["prompt"], focal_answer, activity)
    choices = dict(item.get("choices") or {})
    if activity:
        choices["activity"] = PULSE_MAX_REVIEW_S
    return dict(item, prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(), choices=choices)


async def answer_pieces(provider, text: str) -> list[str] | None:
    """The model's own tokenization of ``text`` as token pieces (llama-server ``/tokenize`` with
    ``with_pieces``), or None when the server does not give pieces."""
    from range_service.agents import localhttp   # noqa: PLC0415

    try:
        reply = await localhttp.request(provider.port, "POST", "/tokenize",
                                        {"content": text, "add_special": False, "with_pieces": True}, provider.api_key)
        data = reply.json() if reply.status == 200 else None
    except localhttp.HttpError:
        return None
    toks = data.get("tokens") if isinstance(data, dict) else None
    if not isinstance(toks, list) or not all(isinstance(x, dict) and isinstance(x.get("piece"), str) for x in toks):
        return None
    return [x["piece"] for x in toks]


async def _run_condition(entry: dict, kv: str, items: list[dict], inf: dict, limit: int | None,
                         focal_layout: str = "ONE_MESSAGE", focal_answer: str = "FULL", activity: bool = False) -> dict:
    setup = build_llama(entry["id"], kv_cache_type=kv, inference=inf,
                        log_path=RESULTS / f"server_{entry['label']}_{kv}.log")
    setup.gateway.answer = focal_answer
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
            item = focal_item(item, focal_answer, activity)
            result = await setup.gateway.decide(agent_id=item["agent_id"], tier=item["tier"], prompt=item["prompt"],
                                                prompt_sha256=item["prompt_sha256"], max_tokens=item["max_tokens"],
                                                allowed_actions=item["allowed_actions"], tick=item["based_on_tick_id"],
                                                prefix=npc_prefix(item, focal_layout), choices=item.get("choices"))
            s = bk.score_item(item, result)
            if s.get("answer_text"):
                pieces = await answer_pieces(setup.provider, s["answer_text"])
                s["field_tokens"] = tokens.account(s["answer_text"], pieces) if pieces is not None else None
            scored.append(s)
            progress.update(f"  {entry['label']} {kv}: {n}/{len(todo)} ({'ok' if s['final_valid'] else s['fallback']})")
    finally:
        progress.done()
        await setup.gateway.stop()
    return {"label": entry["label"], "id": entry["id"], "model": entry["model"], "quant": entry["quant"],
            "qat": entry["qat"], "kv": kv, "focal_layout": focal_layout, "focal_answer": focal_answer,
            "focal_activity": activity,
            "sha256": setup.model.sha256, "load_s": load_s,
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
                cond = asyncio.run(_run_condition(entry, kv, items, inf, args.limit, args.focal_layout, args.focal_answer,
                                                  args.activity == "on"))
            except ProviderError as exc:
                print(f"  {entry['label']} {kv}: FAILED: {exc}")
                continue
            results["offline"] = [c for c in results["offline"] if condition_key(c) != condition_key(cond)] + [cond]
            _save(results)
    by_key = {condition_key(c): c for c in results["offline"]}
    for c in results["offline"]:
        same = [o for o in results["offline"] if o["kv"] == c["kv"] and condition_key(o)[2:] == condition_key(c)[2:]]
        ref = bk.reference_for(c, same)
        ag = bk.agreement(c["items"], ref["items"]) if ref else None
        c["agreement_precision"] = dict(ag, reference=f"{ref['label']} {ref['quant']}") if ag else None
        f16 = by_key.get((c["label"], "f16") + condition_key(c)[2:])
        c["agreement_kv"] = bk.agreement(c["items"], f16["items"]) if c["kv"] != "f16" and f16 else None
    _save(results)
    return 0


# ---------- live ----------

# mode -> (run mode, pre-warm, persona snapshots, synthetic NPC load). LIVE_COLD switches off both
# pre-warming and snapshots: with snapshots on, a promotion's first call restores its prefix and is
# never cold (G3c-2, D-60). LIVE_LOAD keeps all NPC slots but one busy ("slots - 1" streams), so a
# real NPC call always finds a slot.
LIVE_MODES = {"LIVE": ("LIVE", True, True, 0), "LIVE_COLD": ("LIVE", False, False, 0),
              "LIVE_LOAD": ("LIVE", True, True, -1), "STEPPED": ("STEPPED", True, True, 0),
              "LIVE_RENDERED": ("LIVE", True, True, 0)}          # G3d: LIVE with the rendered client open
RENDERED_MODES = {"LIVE_RENDERED"}


def _p(values: list[float], q: float) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return float(vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))]) if vals else None


HARNESS = "g3f"     # live rows from this harness on: one run per folder, Robot R's per-call breakdown


def conditions_suffix(c: dict) -> str:
    """The run-folder suffix of non-default conditions (G3f)."""
    parts = []
    if c.get("prompt_layout") == "SYSTEM_PREFIX":
        parts.append("sysprefix")
    if c.get("answer") in ("SHORT", "LEAN"):
        parts.append(c["answer"].lower())
    if c.get("gpu_guard"):
        parts.append(f"guard{c.get('npc_cap', 0)}" + ("dec" if c.get("guard_hold") == "DECISIONS" else ""))
    if c.get("salvage") is False:
        parts.append("nosalvage")
    return "".join(f"_{p}" for p in parts)


def live_key(row: dict) -> tuple:
    c = row.get("conditions") or {}
    return (row["label"], row["mode"], row.get("npc_label"), row.get("pulse", True), c.get("prompt_layout", "ONE_MESSAGE"),
            c.get("answer", "FULL"), bool(c.get("gpu_guard")), c.get("npc_cap", 0) if c.get("gpu_guard") else 0,
            c.get("guard_hold", "ALL") if c.get("gpu_guard") else "ALL", c.get("salvage", True) is not False)


def live_row(entry: dict, npc_label: str, mode: str, runs: list[tuple[Path, object]]) -> dict:
    """One live row over all repeats: Robot R's calls only for its latency; NPC calls (queue,
    prefill, generation, and how long Robot R's server was busy meanwhile), Robot R's action
    outcomes (accepted or stale), promotions, event-loop lag and VRAM apart."""
    robot, npc, promos, lags, accepted, stale, journals = [], [], [], [], 0, 0, []
    frames, vram_peaks, minutes = [], [], 0.0
    all_records, all_delivery, pooled_runs = [], [], 0
    ok = True
    s = None
    for out, r in runs:
        render = r.summary.get("render") or {}
        if (render.get("frames") or {}).get("available"):
            frames.append(render["frames"])
        if (render.get("vram") or {}).get("peak_mib") is not None:
            vram_peaks.append(render["vram"]["peak_mib"])
        minutes += (r.summary.get("ticks_run") or 0) / 3600
        recs = [json.loads(line) for line in (out / "sidecar" / "decision_records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
        segments = live_diag.split_runs(recs)
        if len(segments) > 1:
            # Never again (G3f: run folders are cleared), but never pooled silently either: keep this run's.
            pooled_runs += 1
            recs = segments[-1]
        all_records += recs
        delivery = out / "sidecar" / "delivery.jsonl"
        if delivery.is_file():
            all_delivery += [json.loads(x) for x in delivery.read_text(encoding="utf-8").splitlines() if x.strip()]
        for rec in recs:
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
            "run_dir": str(runs[0][0]),
            # G3d (D-69): pulse, render, frame pacing (worst repeat) and peak VRAM sampled during the runs.
            "pulse": bool(((runs[-1][1].summary.get("render") or {}).get("pulse"))),
            "render": None if (runs[-1][1].summary.get("render") or {}).get("headless", True)
            else f"{runs[-1][1].summary['render']['resolution']} {runs[-1][1].summary['render']['preset']}",
            "npc_calls_per_min": round(len(npc) / minutes, 1) if minutes else None,
            "frame_p50_ms": max((x["p50_ms"] for x in frames if x["p50_ms"] is not None), default=None),
            "frame_p95_ms": max((x["p95_ms"] for x in frames if x["p95_ms"] is not None), default=None),
            "frame_p99_ms": max((x["p99_ms"] for x in frames if x["p99_ms"] is not None), default=None),
            "frame_spikes": sum(x["spikes"] for x in frames) if frames else None,
            "frame_headless": all(x.get("display_server") == "headless" for x in frames) if frames else None,
            "vram_peak_mib": max(vram_peaks) if vram_peaks else None,
            "vram_peak_note": None if vram_peaks else ((runs[-1][1].summary.get("render") or {}).get("vram") or {}).get("reason"),
            # G3f (D-75): one run per folder; Robot R's calls by outcome and cost; the conditions.
            "harness": HARNESS, "pooled_runs_split": pooled_runs,
            "conditions": dict(runs[-1][1].summary.get("conditions") or {}),
            "gpu_guard_stats": runs[-1][1].summary.get("gpu_guard"),
            # G3g (D-87): GPU memory other programs held before the servers started (largest of the repeats),
            # and the smallest free memory after both servers started.
            "vram_other_mib": max((x for x in (((r.summary.get("vram_hygiene") or {}).get("other_programs_mib"))
                                               for _, r in runs) if x is not None), default=None),
            "vram_free_after_mib": min((x for x in (((r.summary.get("vram_hygiene") or {}).get("free_after_servers_mib"))
                                                    for _, r in runs) if x is not None), default=None),
            "vram_warnings": sum(1 for _, r in runs if (r.summary.get("vram_hygiene") or {}).get("warning")),
            "robot": live_diag.robot_breakdown(all_records, all_delivery)}


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
    from range_service.agents.runmodels import Conditions   # noqa: PLC0415

    conditions = Conditions(args.focal_layout, args.focal_answer,
                            None if args.gpu_guard is None else args.gpu_guard == "on", args.npc_cap,
                            args.guard_hold, False if args.no_salvage else None)
    suffix = conditions_suffix(conditions.resolve(_inf()))
    for name in args.models:
        entry = reg.catalog_entry(catalog, name)
        for mode in args.modes:
            run_mode, prewarm, snapshots, load = LIVE_MODES[mode]
            load = max(1, npc_slots - 1) if load < 0 else load
            npc_spec = {"config": "auto", "none": "none"}.get(args.npc_model, f"llama:{args.npc_model}")
            runs = []
            for k in range(args.repeat):
                npc_part = "" if npc_label in ("config",) else f"_{str(npc_label).lower()}"
                out = RESULTS / (f"run_{entry['label']}{npc_part}_{mode.lower()}{'_nopulse' if args.no_pulse else ''}"
                                 f"{suffix}_{k + 1}")
                print(f"SB-04 {mode} {k + 1}/{args.repeat} with {entry['label']} {entry['model']} {entry['quant']} "
                      f"(NPC model: {npc_label})...")
                try:
                    r = asyncio.run(run_scenario(RunOptions(
                        "SB04_POLITE_BID", godot, mode=run_mode, model=f"llama:{entry['id']}", npc_model=npc_spec,
                        prewarm=prewarm, snapshots=snapshots, out_dir=out, timeout_s=1800,
                        npc_load_streams=load, npc_load_prompts=npc_items,
                        headless=mode not in RENDERED_MODES, resolution=args.resolution,
                        render_preset=args.render_preset, frame_stats=True,
                        pulse="off" if args.no_pulse else "auto", conditions=conditions)))
                except RunError as exc:
                    print(f"  FAILED: {exc}")
                    continue
                runs.append((out, r))
            if not runs:
                continue
            row = live_row(entry, npc_label, mode, runs)
            if row["fallback"]:
                print(f"  NOTE: Option B (one server): {row['fallback']}")
            results["live"] = [x for x in results["live"] if live_key(x) != live_key(row)] + [row]
            _save(results)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    """G3f (D-75): Robot R's calls in existing run folders, split run by run (folders the old harness
    reused hold several runs). Writes diagnosis.json and diagnosis.md: counts and timings only."""
    folders = args.folders or sorted(p for p in RESULTS.glob("run_*") if (p / "sidecar" / "decision_records.jsonl").is_file())
    if not folders:
        print(f"No run folders with decision records under {RESULTS}")
        return 1
    rows = []
    for folder in folders:
        manifest = folder / "run_manifest.json"
        settings = json.loads(manifest.read_text(encoding="utf-8")).get("resolved_settings", {}) if manifest.is_file() else {}
        for row in live_diag.diagnose_folder(folder):
            row["model"] = settings.get("model.catalog_label")
            row["npc_model"] = settings.get("npc_model.catalog_label") or settings.get("npc_model")
            row["run_mode"] = settings.get("run_mode") or settings.get("mode")
            rows.append(row)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "diagnosis.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = bk.diagnosis_lines(rows)
    (RESULTS / "diagnosis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nWritten: {RESULTS / 'diagnosis.md'} (paste it back) and diagnosis.json")
    return 0


# ---------- tokens (G3g, D-84) ----------

def item_schema(item: dict, answer: str = "FULL") -> dict:
    from range_service.agents.output_schema import ALL_CHANNELS, answer_schema   # noqa: PLC0415

    c = item.get("choices") or {}
    limits = {"FULL": "FOCAL", "SHORT": "FOCAL_SHORT", "LEAN": "FOCAL_LEAN"}[answer]
    return answer_schema(tuple(item["allowed_actions"]), tuple(c["targets"]) if c.get("targets") is not None else None,
                         tuple(c.get("channels", ALL_CHANNELS)), limits,
                         tuple(c["gestures"]) if c.get("gestures") is not None else None,
                         tuple(c["expressions"]) if c.get("expressions") is not None else None,
                         int(c["activity"]) if c.get("activity") else 0)


async def _generate(provider, item: dict, schema: dict) -> dict:
    """One answer with the generated token pieces (``logprobs``) and the server's counts."""
    body = provider._body(item["prompt"], item["max_tokens"], schema, -1)
    body["logprobs"] = True
    body["top_logprobs"] = 1          # llama-server b12443 returns the generated tokens only with at least 1
    data = await provider._post(body)
    choice = data["choices"][0]
    text = choice["message"]["content"]
    content = (choice.get("logprobs") or {}).get("content") or []
    pieces = [x.get("token") for x in content if isinstance(x, dict) and isinstance(x.get("token"), str)]
    canonical = await answer_pieces(provider, text)
    timings = data.get("timings") or {}
    return {"text": text, "finish": choice.get("finish_reason"), "generated": timings.get("predicted_n"),
            "generation_ms": round(timings["predicted_ms"]) if isinstance(timings.get("predicted_ms"), (int, float)) else None,
            "pieces": pieces if len(pieces) == len(content) and pieces else None,
            "whitespace_tokens": sum(1 for x in pieces if x and not x.strip()) if pieces else None,
            "canonical": len(canonical) if canonical is not None else None,
            "fields": tokens.account(text, pieces) if pieces else (tokens.account(text, canonical) if canonical else None)}


def tokens_summary(rows: list[dict]) -> dict:
    """With vs without maxLength: generated tokens for the same text, and against the text's own
    tokenization (generated - canonical = tokens the grammar may have forced)."""
    same = [r for r in rows if r["limited"]["text"] == r["unlimited"]["text"]]

    def stat(vals):
        vals = [v for v in vals if v is not None]
        return {"n": len(vals), "sum": sum(vals), "p50": _p(vals, 0.5)} if vals else {"n": 0}
    out = {"n": len(rows), "same_text": len(same)}
    for name in ("limited", "unlimited"):
        rs = [r[name] for r in rows]
        out[name] = {"generated": stat([r["generated"] for r in rs]),
                     "extra_vs_canonical": stat([r["generated"] - r["canonical"] for r in rs
                                                 if r["generated"] is not None and r["canonical"] is not None]),
                     "cut_off": sum(1 for r in rs if r["finish"] == "length"),
                     "whitespace_tokens": stat([r.get("whitespace_tokens") for r in rs]),
                     "generation_ms": stat([r["generation_ms"] for r in rs]),
                     "fields": tokens.summarize([r["fields"] for r in rs if r["fields"]])}
    out["same_text_generated_diff"] = stat([r["limited"]["generated"] - r["unlimited"]["generated"] for r in same
                                            if r["limited"]["generated"] is not None and r["unlimited"]["generated"] is not None])
    return out


def tokens_lines(results: dict) -> list[str]:
    out = ["# Robot R's answers: tokens per field, and the grammar's string limits (bakeoff.py tokens, G3g D-84)", "",
           f"Engine: {results.get('engine')} · prompt set: {results.get('prompt_set')} · temperature 0 · "
           f"activity offered: {results.get('activity')} · answer format: {results.get('answer', 'FULL')}", "",
           "## With and without maxLength (the same prompts, the same schema otherwise)", "",
           "| Model | Prompts | Same text both ways | Generated tokens with / without maxLength (sum) | "
           "For the same text: with − without (sum) | Generated − own tokenization: with / without (sum) | "
           "Cut off at the cap: with / without | Whitespace-only tokens with / without (sum) | "
           "Generation ms p50 with / without |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m in results["models"]:
        s = m["summary"]
        lim, unl = s["limited"], s["unlimited"]
        out.append(f"| {m['label']} {m['model']} | {s['n']} | {s['same_text']} | {lim['generated'].get('sum', '–')} / "
                   f"{unl['generated'].get('sum', '–')} | {s['same_text_generated_diff'].get('sum', '–')} | "
                   f"{lim['extra_vs_canonical'].get('sum', '–')} / {unl['extra_vs_canonical'].get('sum', '–')} | "
                   f"{lim['cut_off']} / {unl['cut_off']} | {lim['whitespace_tokens'].get('sum', '–')} / "
                   f"{unl['whitespace_tokens'].get('sum', '–')} | {lim['generation_ms'].get('p50', '–')} / "
                   f"{unl['generation_ms'].get('p50', '–')} |")
    out += ["", f"## What each field costs (answers as in a run: the {results.get('answer', 'FULL')} schema, with maxLength)", "",
            "| Model | Answers | Tokens p50 / mean | " + " | ".join(f"{f} mean (share)" for f in tokens.FIELDS) + " |",
            "|---|---|---|" + "---|" * len(tokens.FIELDS)]
    for m in results["models"]:
        f = m["summary"]["limited"]["fields"]
        if not f.get("n"):
            continue
        cells = [f"{f['by_field'][k]['mean']} ({f['by_field'][k]['share']:.0%})" for k in tokens.FIELDS]
        out.append(f"| {m['label']} {m['model']} | {f['n']} | {f['tokens_p50']} / {f['tokens_mean']} | " + " | ".join(cells) + " |")
    out += ["", "Generated tokens are the server's count; pieces come from the answer's own logprobs (what was generated), "
            "or the model's tokenization of the text where logprobs give none. \"Generated − own tokenization\" above 0 "
            "means the grammar made the model write the text in more, smaller tokens than its tokenizer would. "
            "Counts only; answers stay in tokens.json."]
    return out


def cmd_tokens(args: argparse.Namespace) -> int:
    from range_service.agents.output_schema import _without_max_length as without_max_length   # noqa: PLC0415

    catalog = reg.load_catalog()
    registry = reg.Registry.load()
    entries = [reg.catalog_entry(catalog, m) for m in args.models]
    missing = [e["label"] for e in entries if not registry.find(e["id"])]
    if missing:
        print(f"Not on this machine: {', '.join(missing)}. Run tools/models.py plan.")
        return 1
    items, set_sha = load_set(args.set)
    robot = [focal_item(i, args.answer, args.activity == "on") for i in items if i.get("role", "ROBOT_R") == "ROBOT_R"]
    robot = robot[: args.limit] if args.limit else robot
    inf = load_inference()
    out = {"created": time.strftime("%Y-%m-%d %H:%M"), "engine": ENGINE, "prompt_set": args.set.name,
           "prompt_set_sha256": set_sha, "activity": args.activity, "answer": args.answer, "models": []}

    async def run(entry: dict) -> dict:
        setup = build_llama(entry["id"], kv_cache_type=args.kv, inference=inf,
                            log_path=RESULTS / f"server_{entry['label']}_{args.kv}_tokens.log")
        await setup.gateway.start()
        rows = []
        progress = bk.Progress()
        try:
            for n, item in enumerate(robot, start=1):
                schema = item_schema(item, args.answer)
                row = {"item_id": item["item_id"], "limited": await _generate(setup.provider, item, schema),
                       "unlimited": await _generate(setup.provider, item, without_max_length(schema))}
                rows.append(row)
                progress.update(f"  {entry['label']}: {n}/{len(robot)}")
        finally:
            progress.done()
            await setup.gateway.stop()
        return {"label": entry["label"], "model": entry["model"], "quant": entry["quant"], "kv": args.kv,
                "summary": tokens_summary(rows), "rows": rows}

    for entry in entries:
        out["models"].append(asyncio.run(run(entry)))
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = "tokens" if args.answer == "FULL" else f"tokens_{args.answer.lower()}"
    (RESULTS / f"{stem}.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = tokens_lines(out)
    (RESULTS / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nWritten: {RESULTS / (stem + '.md')} (paste it back) and {stem}.json")
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
    p_off.add_argument("--focal-layout", default="ONE_MESSAGE", choices=["ONE_MESSAGE", "SYSTEM_PREFIX"],
                       help="G3f (D-76): Robot R's prompts as one message (as measured) or with the prefix as a system message")
    p_off.add_argument("--focal-answer", default="FULL", choices=["FULL", "SHORT", "LEAN"],
                       help="G3f (D-77), G3g (D-85): Robot R's answer format")
    p_off.add_argument("--activity", default="off", choices=["on", "off"],
                       help="G3g: Robot R's prompts offer an activity, as with the pulse on in a live run")
    p_tok = sub.add_parser("tokens", help="G3g (D-84): the same prompts with and without maxLength in the grammar")
    p_tok.add_argument("--models", nargs="+", required=True)
    p_tok.add_argument("--kv", default="q8_0", choices=["f16", "q8_0"])
    p_tok.add_argument("--set", type=Path, default=PROMPT_SET)
    p_tok.add_argument("--limit", type=int, default=None, help="only the first N of Robot R's prompts")
    p_tok.add_argument("--answer", default="FULL", choices=["FULL", "SHORT"],
                       help="the answer format whose string limits are compared (SHORT: reason <= 60 characters, D-77)")
    p_tok.add_argument("--activity", default="on", choices=["on", "off"],
                       help="offer an activity, as with the pulse on (default on: as Robot R answers in a live run)")
    p_live = sub.add_parser("live")
    p_live.add_argument("--models", nargs="+", required=True)
    p_live.add_argument("--modes", nargs="+", default=list(LIVE_MODES), choices=list(LIVE_MODES))
    p_live.add_argument("--repeat", type=int, default=3,
                        help="runs per mode, pooled (one SB-04 is 90 s real time; G3c-2)")
    p_live.add_argument("--npc-model", default="config",
                        help="NPC server model: config (configs/inference.yaml), a catalog label such as N3, or none")
    p_live.add_argument("--resolution", default="1920x1080", help="LIVE_RENDERED: the window size, WIDTHxHEIGHT")
    p_live.add_argument("--render-preset", default="v0", help="LIVE_RENDERED: v0 or v0_compat (range_service/eval/runner.py)")
    p_live.add_argument("--no-pulse", action="store_true",
                        help="the pulse protocol off in every run (compare with the same command without it)")
    p_live.add_argument("--focal-layout", default=None, choices=["ONE_MESSAGE", "SYSTEM_PREFIX"],
                        help="G3f (D-76): Robot R's prompt layout (default: configs/inference.yaml)")
    p_live.add_argument("--focal-answer", default=None, choices=["FULL", "SHORT", "LEAN"],
                        help="G3f (D-77), G3g (D-85): Robot R's answer format (default: configs/inference.yaml)")
    p_live.add_argument("--guard-hold", default=None, choices=["ALL", "DECISIONS"],
                        help="G3g (D-89): the GPU guard holds NPC calls during every Robot R call (ALL) or only its real "
                             "decisions, not its pulse reviews (DECISIONS); default: configs/inference.yaml")
    p_live.add_argument("--no-salvage", action="store_true",
                        help="G3g (D-86): never use a cut-off answer's complete actions (for comparison)")
    p_live.add_argument("--gpu-guard", default=None, choices=["on", "off"],
                        help="G3f (D-78): focal-first GPU guard on the NPC server (default: configs/inference.yaml)")
    p_live.add_argument("--npc-cap", type=int, default=None,
                        help="G3f (D-78): real NPC calls allowed in flight while Robot R thinks (default: config, 0)")
    p_diag = sub.add_parser("diagnose")
    p_diag.add_argument("folders", nargs="*", type=Path, help="run folders (default: every results/bakeoff/run_*)")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    try:
        return {"build-set": cmd_build_set, "offline": cmd_offline, "live": cmd_live, "diagnose": cmd_diagnose,
                "report": cmd_report, "tokens": cmd_tokens}[args.command](args)
    except reg.ModelError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
