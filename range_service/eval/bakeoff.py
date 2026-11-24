"""The model bake-off (D-20, D-55; G3b-2): scoring and reporting. tools/bakeoff.py runs it.

- **Prompt set**: Robot R's logged decision contexts from SB-04 runs (G3a context assembly), one
  run per robot body, each with the agent's allowed actions, its body and what the Demo policy
  did. Built once, committed (bakeoff/prompts_v1.jsonl), so the offline part needs no Godot.
- **Conditions**: each model x KV cache type (f16, q8_0), temperature 0, the same llama.cpp build.
- **Scores per condition**: valid output before repair, repair rate, final valid rate, valid-action
  rate (an offline check like the action gate's: the body can make the gesture, the expression
  exists for it, a target is a track the prompt mentions), commitments kept, prompt and
  generation tokens/s, VRAM; and **decision agreement** with the same model at higher precision
  (F1 vs F2, N3 vs N2) and with its own f16 cache (q8_0 vs f16).
- Missing measurements are null with a reason, never 0 (CLAUDE.md).
"""

from __future__ import annotations

import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any

from range_service.agents.gateway import parse_output

PRECISION = ["F32", "F16", "BF16", "Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S", "Q5_0", "Q4_K_M", "Q4_K_S", "Q4_1", "Q4_0",
             "IQ4_XS", "IQ4_NL", "Q3_K_M", "Q3_K_S", "IQ3_XXS", "Q2_K"]
TRACK = re.compile(r"\banon_[a-z0-9]{10}\b")


def _drops(b: dict) -> str:
    """Answers dropped before sending, with why (G3 close-out): "28 (TARGET_NOT_PERCEIVED 20, ...)"."""
    by = b.get("dropped_before_send_by_reason") or {}
    reasons = ", ".join(f"{k} {v}" for k, v in by.items())
    return f"{b['dropped_before_send']} ({reasons})" if reasons else str(b["dropped_before_send"])


# ---------- signatures and offline checks ----------

def signature(action: dict[str, Any]) -> str:
    """What a decision *is*, for agreement: the action and its deciding arguments (not wording)."""
    a, args = action["action"], action.get("args", {})
    key = {"GESTURE": args.get("gesture"), "EXPRESS": args.get("expression_id"),
           "SPEAK": f"{args.get('channel')}:{'to' if args.get('addressee_id') else 'all'}",
           "TURN_TO": args.get("target_id") or "point", "LOOK_AT": args.get("target_id") or "point",
           "MOVE_TO": args.get("target_id") or "point"}.get(a, "")
    return f"{a}:{key}" if key else a


def offline_gate(actions: list[dict[str, Any]], item: dict[str, Any]) -> list[str]:
    """Problems the world's action gate would raise without needing the world (D-36, D-52)."""
    tracks = set(TRACK.findall(item["prompt"])) | set((item.get("handles") or {}).values())   # G3h: handles
    found = []
    for act in actions:
        args = act.get("args", {})
        if act["action"] == "GESTURE" and args.get("gesture") not in item["gestures"]:
            found.append(f"{item['body_id']} cannot make the gesture {args.get('gesture')}")
        if act["action"] == "EXPRESS" and args.get("expression_id") not in item["expressions"]:
            found.append(f"expression {args.get('expression_id')} is not available to {item['body_id']}")
        if act["action"] == "SPEAK" and args.get("channel") == "GROUP":
            found.append("GROUP message without a group")
        for key in ("target_id", "addressee_id"):
            ref = args.get(key)
            if isinstance(ref, str) and ref.startswith("anon_") and ref not in tracks:
                found.append(f"{key} {ref} is not a track this agent perceives")
    return found


_OPEN_LINE = re.compile(r"^- OPEN (?:mem_\S+ )?-\d+s to ([^:]+):", re.MULTILINE)
PROMISE_TARGET_ARGS = ("addressee_id", "target_id", "to_id")


def promised_to(item: dict[str, Any]) -> set[str]:
    """Who the agent has open promises to: from the item's reference (prompts_v2) or, for older
    sets, read off the COMMITMENTS section of the prompt the agent was shown."""
    ref = item["reference"].get("promised_to")
    if ref is not None:
        return set(ref)
    found: set[str] = set()
    for group in _OPEN_LINE.findall(item["prompt"]):
        found |= {t.strip() for t in group.split(",") if t.strip().startswith("anon_")}
    return found


def promise_due(item: dict[str, Any]) -> bool:
    """Does this prompt call for keeping a promise? v2 items say so (``promise_due``); v1 items
    count when the Demo policy kept one."""
    ref = item["reference"]
    return bool(ref.get("promise_due", ref.get("demo_fulfilled")))


def kept_commitment(actions: list[dict[str, Any]], item: dict[str, Any]) -> bool | None:
    """Flagged: did an action set ``fulfills_commitment``? None when the situation did not call for
    keeping a promise."""
    if not promise_due(item):
        return None
    return any(a.get("fulfills_commitment") for a in actions)


def kept_in_behavior(actions: list[dict[str, Any]], item: dict[str, Any]) -> bool | None:
    """Kept in behavior: did an action address, face, approach or gesture at a person the agent
    had promised to help, flag or no flag? None outside promise situations, or when the prompt
    names nobody the promise was made to."""
    if not promise_due(item):
        return None
    targets = promised_to(item)
    if not targets:
        return None
    return any(a.get("args", {}).get(k) in targets for a in actions for k in PROMISE_TARGET_ARGS)


# ---------- per-condition scoring ----------

def score_item(item: dict[str, Any], result: Any) -> dict[str, Any]:
    """One prompt's answer, scored. ``role`` is ROBOT_R or NPC (prompts_v2; v1 is all Robot R)."""
    calls = result.model_calls
    first = calls[0] if calls else {}
    actions = result.actions if result.fallback is None else []
    problems = offline_gate(actions, item) if actions else []
    t = first.get("timings") or {}
    processed = (first.get("prompt_tokens") or 0) - (first.get("cached_tokens") or 0)
    return {
        "item_id": item["item_id"],
        "role": item.get("role", "ROBOT_R"),
        "first_valid": first.get("outcome") == "VALID",
        "repaired": len(calls) > 1 and result.fallback is None,
        "final_valid": result.fallback is None,
        "fallback": (result.fallback or {}).get("reason"),
        "signature": [signature(a) for a in actions],
        "gate_ok": bool(actions) and not problems, "gate_problems": problems,
        "kept": kept_commitment(actions, item),
        "kept_behavior": kept_in_behavior(actions, item),
        # Every answer that could not be used, raw, with why (to diagnose failures like F2's).
        "invalid_answers": [{"attempt": c.get("attempt"), "outcome": c.get("outcome"), "error": c.get("error"),
                             "response_text": c.get("response_text")} for c in calls if c.get("outcome") != "VALID"],
        "prompt_tps": round(processed / t["prefill_ms"] * 1000, 1) if t.get("prefill_ms") and processed > 0 else None,
        "gen_tps": round(first["generated_tokens"] / t["generation_ms"] * 1000, 1)
        if t.get("generation_ms") and first.get("generated_tokens") else None,
        "total_ms": t.get("total_ms"),
        "actions": actions,
        # G3g (D-84 to D-86): what the answer cost, and whether it was cut off at the output cap.
        "generated_tokens": first.get("generated_tokens"),
        "cut_off": any("cut off at the" in (c.get("error") or "") or bool(c.get("salvaged")) for c in calls[:1]),
        "salvaged": any(bool(c.get("salvaged")) for c in calls),
        "answer_text": first.get("response_text") if item.get("role", "ROBOT_R") == "ROBOT_R" else None,
    }


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _median(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def summarize_condition(items: list[dict[str, Any]]) -> dict[str, Any]:
    kept = [i["kept"] for i in items if i["kept"] is not None]
    behaved = [i.get("kept_behavior") for i in items if i.get("kept_behavior") is not None]
    return {
        "n": len(items),
        "valid_before_repair": _rate([i["first_valid"] for i in items]),
        "repair_rate": _rate([i["repaired"] for i in items]),
        "final_valid": _rate([i["final_valid"] for i in items]),
        "valid_action_rate": _rate([i["gate_ok"] for i in items]),
        "commitments_kept": _rate(kept) if kept else None,
        "commitments_note": None if kept else "no prompt in the set called for keeping a promise",
        "commitments_kept_behavior": _rate(behaved) if behaved else None,
        "invalid_answers": sum(len(i.get("invalid_answers", [])) for i in items),
        "prompt_tps_median": _median([i["prompt_tps"] for i in items]),
        "gen_tps_median": _median([i["gen_tps"] for i in items]),
        "latency_ms_p50": _median([i["total_ms"] for i in items]),
        # G3g (D-84, D-85): generated tokens per answer (first call), answers cut off at the output cap,
        # answers whose complete actions were salvaged (D-86), and the cost per field.
        "generated_tokens_p50": _median([i.get("generated_tokens") for i in items]),
        "generated_tokens_p95": _p95([i.get("generated_tokens") for i in items]),
        "cut_off": sum(1 for i in items if i.get("cut_off")),
        "salvaged": sum(1 for i in items if i.get("salvaged")),
        "fields": _fields([i.get("field_tokens") for i in items]),
    }


def _p95(values: list[float | None]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return float(vals[min(len(vals) - 1, int(round(0.95 * (len(vals) - 1))))]) if vals else None


def _fields(rows: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    from range_service.eval.tokens import summarize   # noqa: PLC0415

    rows = [r for r in rows if r]
    return summarize(rows) if rows else None


def summarize_by_role(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The same summary for Robot R's prompts and for NPC prompts separately (prompts_v2)."""
    roles = sorted({i.get("role", "ROBOT_R") for i in items})
    return {role: summarize_condition([i for i in items if i.get("role", "ROBOT_R") == role]) for role in roles}


def agreement(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Share of prompts where two conditions made the same decision (first action; all actions)."""
    other = {i["item_id"]: i for i in b}
    pairs = [(i, other[i["item_id"]]) for i in a if i["item_id"] in other and i["final_valid"] and other[i["item_id"]]["final_valid"]]
    if not pairs:
        return None
    return {"n": len(pairs),
            "first_action": round(sum(x["signature"][:1] == y["signature"][:1] for x, y in pairs) / len(pairs), 3),
            "all_actions": round(sum(x["signature"] == y["signature"] for x, y in pairs) / len(pairs), 3)}


def reference_for(model: dict[str, Any], others: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The same model at the next higher precision among the conditions run, if any."""
    def rank(q: str | None) -> int:
        return PRECISION.index(q) if q in PRECISION else len(PRECISION)
    better = [o for o in others if o["model"] == model["model"] and o["qat"] == model["qat"]
              and rank(o["quant"]) < rank(model["quant"])]
    return min(better, key=lambda o: rank(o["quant"])) if better else None


# ---------- VRAM ----------

def _smi() -> str | None:
    return shutil.which("nvidia-smi")


def gpu_memory_used_mib() -> int | None:
    """Total memory in use on the first GPU (nvidia-smi), or None."""
    exe = _smi()
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = out.strip().splitlines()[0].strip() if out.strip() else ""
    return int(first) if first.isdigit() else None


def gpu_memory_mib() -> tuple[int | None, int | None, str | None]:
    """(used, total, None) on the first GPU from nvidia-smi, or (None, None, why not). G3g (D-87)."""
    exe = _smi()
    if exe is None:
        return None, None, "nvidia-smi not found (no NVIDIA GPU or driver)"
    try:
        out = subprocess.run([exe, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, f"nvidia-smi failed: {exc}"[:200]
    parts = [x.strip() for x in (out.strip().splitlines() or [""])[0].split(",")]
    if len(parts) == 2 and all(x.isdigit() for x in parts):
        return int(parts[0]), int(parts[1]), None
    return None, None, "nvidia-smi gave no memory figures"


def vram_hygiene(before: tuple, after: tuple, reserve_mib: int, servers: bool) -> dict[str, Any]:
    """G3g (D-87): what else was on the GPU before any model server started ("other programs"),
    and whether the free memory after the servers started is below the reserve (Godot and
    headroom). On Windows, memory short of the reserve can push the driver into its system-memory
    fallback, which slows both servers (docs/OWNER_SETUP_WINDOWS.md)."""
    used0, total, why = before
    used1, total1, why1 = after
    out: dict[str, Any] = {"other_programs_mib": used0, "gpu_total_mib": total or total1, "reserve_mib": reserve_mib,
                           "after_servers_mib": used1 if servers else None, "free_after_servers_mib": None,
                           "warning": None, "note": why or why1}
    if servers and used1 is not None and (total or total1):
        free = (total or total1) - used1
        out["free_after_servers_mib"] = free
        if free < reserve_mib:
            out["warning"] = (f"only {free} MiB of GPU memory free after the model servers started, below the "
                              f"{reserve_mib} MiB reserve; other programs held {used0} MiB before they started. "
                              "Close GPU programs (Task Manager, GPU memory column) and see OWNER_SETUP_WINDOWS.md")
    return out


VRAM_DELTA_NOTE = ("measured as the change in total GPU memory from before the server started to after it was "
                   "ready (per-process memory is N/A, as nvidia-smi reports on Windows)")


def vram_mib(pid: int | None, total_before: int | None = None) -> tuple[int | None, str | None]:
    """GPU memory used by one server process. First nvidia-smi's per-process figure; where that is
    N/A (Windows/WDDM) or missing, the change in total GPU memory since ``total_before`` (taken
    just before the server started). (None, reason) when neither can be read. A note with a
    value says how it was measured."""
    exe = _smi()
    if exe is None:
        return None, "nvidia-smi not found (no NVIDIA GPU or driver)"
    if pid is None:
        return None, "no server process"
    try:
        out = subprocess.run([exe, "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"nvidia-smi failed: {exc}"
    listed = False
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0] == str(pid):
            listed = True
            if parts[1].isdigit():
                return int(parts[1]), None
    if total_before is not None:
        now = gpu_memory_used_mib()
        if now is not None and now > total_before:
            return now - total_before, VRAM_DELTA_NOTE
        return None, ("per-process memory is not reported and total GPU memory did not grow after the server "
                      "started (were any layers offloaded?)")
    why = "reported as N/A" if listed else "not listed"
    return None, f"the server's per-process GPU memory is {why} by nvidia-smi, and no before/after total was taken"


class Progress:
    """One console line rewritten in place. Each update pads over the previous text, so a shorter
    line never leaves old characters behind (bake-off bug 2026-11-17)."""

    def __init__(self, stream: Any = None) -> None:
        import sys   # noqa: PLC0415
        self.stream = stream or sys.stdout
        self._width = 0

    def update(self, text: str) -> None:
        self.stream.write("\r" + text.ljust(self._width))
        self.stream.flush()
        self._width = max(self._width, len(text))

    def done(self) -> None:
        if self._width:
            self.stream.write("\n")
            self.stream.flush()
        self._width = 0


# ---------- report ----------

def fmt(v: Any) -> str:
    return "–" if v is None else str(v)


def pct(v: Any) -> str:
    return "–" if v is None else f"{v:.0%}"


def offline_cond(c: dict[str, Any], role: str = "ROBOT_R") -> str:
    """Robot R's layout, answer and activity condition of an offline row, when not the measured
    default (G3f, G3g). NPC rows of such a run say so too (G3g display fix: the NPC table repeated F3
    and F1 without their labels): the conditions change Robot R's prompts only."""
    parts = [x for x in (c.get("focal_layout", "ONE_MESSAGE"), c.get("focal_answer", "FULL"))
             if x not in ("ONE_MESSAGE", "FULL")]
    if c.get("focal_activity"):
        parts.append("activity")
    if not parts:
        return ""
    if role != "ROBOT_R":
        return f" [run with Robot R {', '.join(parts)}; NPC prompts unchanged]"
    return f" [{', '.join(parts)}]"


def write_report(results: dict[str, Any], folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    json_path, md_path = folder / "results.json", folder / "results.md"
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# Bake-off results ({results.get('created', '?')})", "",
             f"Engine: {results.get('engine')} · prompt set: {results.get('prompt_set')} "
             f"({results.get('prompt_set_sha256', '')[:12]}) · temperature 0", ""]
    offline = results.get("offline", [])

    # G3f: numbers print as numbers; only shares print as percentages (before, any float <= 1 did, so
    # a 0.0 ms queue read "0%" and 0.03 ms headless frames "3%").
    f = fmt
    roles = sorted({r for c in offline for r in (c.get("summary_by_role") or {"ROBOT_R": None})},
                   key=lambda r: (r != "ROBOT_R", r))
    for role in roles:
        rows = [c for c in offline if role in (c.get("summary_by_role") or {"ROBOT_R": None})]
        if not rows:
            continue
        title = {"ROBOT_R": "Robot R prompts", "NPC": "NPC prompts (visitors at C1/C2)"}.get(role, role)
        lines += [f"## Offline prompt set: {title}" if len(roles) > 1 else "## Offline prompt set", "",
                  "| Model | Quant | KV | n | Valid before repair | Repair | Final valid | Valid actions | Promises kept (flag / behavior) | "
                  "Agree vs higher precision | Agree q8_0 vs f16 | Prompt tok/s | Gen tok/s | p50 ms | VRAM MiB |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in rows:
            s = (c.get("summary_by_role") or {}).get(role) or c["summary"]
            ag = c.get("agreement_precision")
            akv = c.get("agreement_kv")
            lines.append(f"| {c['label']} {c['model']}{offline_cond(c, role)} | "
                         f"{c['quant']}{' QAT' if c['qat'] else ''} | {c['kv']} | {s['n']} | "
                         f"{pct(s['valid_before_repair'])} | {pct(s['repair_rate'])} | {pct(s['final_valid'])} | "
                         f"{pct(s['valid_action_rate'])} | {pct(s['commitments_kept'])} / {pct(s.get('commitments_kept_behavior'))} | "
                         f"{pct(ag['first_action']) + ' vs ' + ag['reference'] if ag else '–'} | {pct(akv['first_action']) if akv else '–'} | "
                         f"{f(s['prompt_tps_median'])} | {f(s['gen_tps_median'])} | {f(s['latency_ms_p50'])} | "
                         f"{c['vram_mib'] if c['vram_mib'] is not None else '– (' + str(c['vram_note']) + ')'} |")
        lines.append("")
    lines += answer_cost_lines(offline)
    live_all = results.get("live", [])
    # G3f (D-75): rows from the pre-G3c-2 harness did not run in real time (void); rows of the
    # pre-G3f harness whose run folder an earlier row had used pooled that run's calls.
    void = [r for r in live_all if "repeats" not in r]
    live = [r for r in live_all if "repeats" in r]
    pooled = pooled_rows(live)
    if void:
        lines += [f"**{len(void)} live row(s) from the pre-G3c-2 harness are left out:** those runs were not real time "
                  "(headless LIVE ran ~15x faster, D-60), so their numbers are void. They stay in results.json "
                  "(rows without `repeats`).", ""]
    if pooled:
        lines += [f"**{len(pooled)} row(s) marked POOLED** pooled the calls of an earlier row's runs: the pre-G3f harness "
                  "reused run folders and appended to their decision records (D-75). Their call counts, timeouts, "
                  "p50/p95 and NPC columns include the earlier runs. Rerun them with this harness.", ""]
    if live:
        lines += ["## SB-04 in Godot: Robot R and the NPC server (Option C)", "",
                  "| Robot R model | NPC model | Mode | Runs | Option | OK | Robot R calls | Robot R p50 / p95 ms | "
                  "Robot R actions accepted / stale | NPC calls (timeouts) | NPC p50 ms: total / queue / prefill / gen | "
                  "NPC time with Robot R busy | Loop lag p95 ms | Promotion warm: to call / call / to action ms (n) | "
                  "Promotion cold: to call / call / to action ms (n) | VRAM focal / NPC MiB |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in live:
            lines.append(
                f"| {r['label']}{' (POOLED: ' + pooled[id(r)] + ')' if id(r) in pooled else ''}{cond_text(r)} | "
                f"{r.get('npc_label', '–')} | {r['mode']} | {r.get('repeats', 1)} | {r.get('option') or '–'} | "
                f"{'yes' if r['ok'] else 'NO'} | {r['decisions']} | {f(r['p50_ms'])} / {f(r['p95_ms'])} | "
                f"{f(r.get('robot_actions_accepted'))} / {f(r.get('robot_actions_stale'))} | "
                f"{f(r.get('npc_calls'))} ({f(r.get('npc_timeouts'))}) | {f(r.get('npc_p50_ms'))} / {f(r.get('npc_queue_p50_ms'))} / "
                f"{f(r.get('npc_prefill_p50_ms'))} / {f(r.get('npc_generation_p50_ms'))} | "
                f"{pct(r.get('npc_robot_busy_share'))} | {f(r.get('loop_lag_p95_ms'))} | "
                f"{f(r.get('promotion_warm_to_call_p50_ms'))} / {f(r.get('promotion_warm_call_p50_ms'))} / "
                f"{f(r.get('promotion_warm_p50_ms'))} ({r.get('promotion_warm_n', 0)}) | "
                f"{f(r.get('promotion_cold_to_call_p50_ms'))} / {f(r.get('promotion_cold_call_p50_ms'))} / "
                f"{f(r.get('promotion_cold_p50_ms'))} ({r.get('promotion_cold_n', 0)}) | "
                f"{f(r.get('vram_focal_mib'))} / {f(r.get('vram_npc_mib'))} |")
        lines += ["", "### Pulse, render, frame pacing and peak VRAM (G3d)", "",
                  "| Robot R model | NPC model | Mode | Pulse | Render | NPC calls/min | Frame p50 / p95 / p99 ms | "
                  "Frame spikes | Frame target p95 <= 20 ms (D-109) | Peak VRAM MiB (sampled during the run) | "
                  "Other programs before the servers / free after them MiB |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in live:
            target = "–" if r.get("frame_p95_ms") is None or r.get("frame_headless") else \
                ("met" if r["frame_p95_ms"] <= 20.05 else "NOT met")
            hyg = "–" if r.get("vram_other_mib") is None and r.get("vram_free_after_mib") is None else \
                f"{f(r.get('vram_other_mib'))} / {f(r.get('vram_free_after_mib'))}" + \
                (" (below the reserve)" if r.get("vram_warnings") else "")
            lines.append(f"| {r['label']}{cond_text(r)} | {r.get('npc_label', '–')} | {r['mode']} | {'on' if r.get('pulse', True) else 'off'} | "
                         f"{r.get('render') or 'headless'} | {f(r.get('npc_calls_per_min'))} | "
                         f"{f(r.get('frame_p50_ms'))} / {f(r.get('frame_p95_ms'))} / {f(r.get('frame_p99_ms'))} | "
                         f"{f(r.get('frame_spikes'))} | {target} | "
                         f"{f(r.get('vram_peak_mib')) if r.get('vram_peak_mib') is not None else '– (' + str(r.get('vram_peak_note')) + ')'} | "
                         f"{hyg} |")
        lines += render_tax_lines(live, f) + pulse_ab_lines(live, f) + robot_lines(live, f) + target_lines(live, f, pooled)
        lines += ["", "Modes: LIVE (pre-warm and snapshots on), LIVE_COLD (both off), LIVE_LOAD (pre-warm on, plus "
                  "synthetic NPC calls on all NPC slots but one, to measure Robot R under NPC load), STEPPED. Since "
                  "G3c-2 LIVE runs in real time (90 s per SB-04) and rows pool all repeats. Robot R columns count "
                  "Robot R's calls only. \"NPC time with Robot R busy\": share of NPC call time during which Robot R's "
                  "server also had a call in flight (both share one GPU). Promotion: promotion event to the first "
                  "model call (includes waiting for a trigger), the call itself, and to the first action the world "
                  "accepted; warm = the first call found the persona prefix in its slot.", ""]
    lines += ["Agreement = share of prompts where both conditions chose the same first action (and its key argument). "
              "Valid actions = the offline action-gate check. Promises kept: *flag* = the answer set "
              "`fulfills_commitment`; *behavior* = it addressed, faced, approached or gestured at the person it had "
              "promised to help. VRAM: per process, or the change in total GPU memory where per-process memory is N/A "
              "(see vram_note). Every unusable answer is saved raw in results.json (`invalid_answers`). "
              "– = not measured (see results.json for the reason)."]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


# G3g (D-85): the LEAN targets on prompts_v3, Robot R's prompts (F3's FULL baseline of 2026-11-20).
LEAN_TARGETS = {"final_valid": 0.98, "commitments_kept_behavior": 0.95, "commitments_kept": 0.60,
                "generated_tokens_p50": 70, "cut_off": 0}


def lean_target(s: dict[str, Any]) -> tuple[bool | None, list[str]]:
    """Whether a Robot R offline summary meets the LEAN targets, and which ones it misses."""
    t = LEAN_TARGETS
    missed = []
    for key in ("final_valid", "commitments_kept_behavior", "commitments_kept"):
        if s.get(key) is None or s[key] < t[key]:
            missed.append(f"{key} {pct(s.get(key))} < {t[key]:.0%}")
    g = s.get("generated_tokens_p50")
    if g is None or g > t["generated_tokens_p50"]:
        missed.append(f"generated tokens p50 {fmt(g)} > {t['generated_tokens_p50']}")
    if s.get("cut_off") is None or s["cut_off"] > t["cut_off"]:
        missed.append(f"{fmt(s.get('cut_off'))} answers at the cap")
    if g is None:
        return None, missed
    return not missed, missed


def answer_cost_lines(offline: list[dict[str, Any]]) -> list[str]:
    """G3g (D-84, D-85): Robot R's answers on the offline set: tokens per answer and per field, cut-off
    answers, salvaged answers, and the LEAN targets."""
    from range_service.eval.tokens import FIELDS   # noqa: PLC0415

    rows = [c for c in offline if (c.get("summary_by_role") or {}).get("ROBOT_R", {}).get("generated_tokens_p50") is not None]
    if not rows:
        return []
    out = ["## Robot R's answers: tokens per answer and per field (G3g)", "",
           "| Model | Generated tokens p50 / p95 | At the cap (salvaged) | " + " | ".join(f"{f} p50 / share" for f in FIELDS)
           + " | LEAN targets |", "|---|---|---|" + "---|" * len(FIELDS) + "---|"]
    for c in rows:
        s = c["summary_by_role"]["ROBOT_R"]
        fields = (s.get("fields") or {}).get("by_field") or {}
        cells = [f"{fmt(fields[f]['p50'])} / {pct(fields[f]['share'])}" if f in fields else "–" for f in FIELDS]
        met, missed = lean_target(s)
        verdict = "–" if met is None else ("met" if met else "NOT met: " + "; ".join(missed))
        out.append(f"| {c['label']} {c['model']}{offline_cond(c)} | {fmt(s['generated_tokens_p50'])} / "
                   f"{fmt(s.get('generated_tokens_p95'))} | {fmt(s.get('cut_off'))} ({fmt(s.get('salvaged'))}) | "
                   + " | ".join(cells) + f" | {verdict} |")
    out += ["", "Generated tokens: the server's count for the first call of each prompt. Per field: the model's own "
            "tokenization of the answer, each token counted for the field of its first character (actions = action "
            "names and the list's JSON; args = arguments other than speech; speech = SPEAK/REQUEST_CLARIFICATION text; "
            "promise = commitment, fulfills_commitment; activity; wake = wake conditions; reason = reason_summary; "
            "other = braces and spaces between fields). LEAN targets (D-85): final valid >= 98%, promises kept "
            "(behavior) >= 95% and (flag) >= 60%, generated tokens p50 <= 70, no answer at the cap.", ""]
    return out


TARGET_P95_MS = 4000          # G3f target: Robot R p95 under the 4 s deadline ...
TARGET_TIMEOUT_SHARE = 0.05   # ... and at most 5% of its calls timed out, in LIVE and LIVE_LOAD


def pooled_rows(live: list[dict]) -> dict[int, str]:
    """Rows (by id) whose first run folder an earlier pre-G3f row had used, with that row's name."""
    out, seen = {}, {}
    for r in live:
        folder = str(r.get("run_dir", "")).replace("\\", "/").rsplit("/", 1)[-1]
        if r.get("harness") != "g3f" and folder in seen:
            out[id(r)] = f"with {seen[folder]}"
        seen.setdefault(folder, f"{r['label'].split(' ')[0]}+{r.get('npc_label', '–')} {r['mode']}")
    return out


def cond_text(r: dict) -> str:
    c = r.get("conditions") or {}
    parts = []
    if c.get("prompt_layout", "ONE_MESSAGE") != "ONE_MESSAGE":
        parts.append(c["prompt_layout"])
    if c.get("answer", "FULL") != "FULL":
        parts.append(f"answer {c['answer']}")
    if c.get("gpu_guard"):
        parts.append(f"GPU guard cap {c.get('npc_cap', 0)}" + (", decisions only" if c.get("guard_hold") == "DECISIONS" else ""))
    if c.get("salvage") is False:
        parts.append("no salvage")
    return f" [{', '.join(parts)}]" if parts else ""


def robot_lines(live: list[dict], f) -> list[str]:
    """G3f (D-75): Robot R's calls by outcome and by cost, for rows from the G3f harness."""
    rows = [r for r in live if r.get("robot")]
    if not rows:
        return []
    out = ["", "### Robot R's calls: outcomes and where the time goes (G3f)", "",
           "| Robot R model | NPC model | Mode | Calls | Valid first try / after repair | Timeouts at model / in queue | "
           "Invalid output (kinds) | Fallback decisions (why) | Dropped before send | Queue / prefill / gen p50 ms | "
           "Prefill / gen p95 ms | Prompt tokens p50 / p95 | Cache share | Generated tokens p50 / p95 / max (cap) | "
           "Other server busy: all / timeouts |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        b = r["robot"]
        o = b["outcomes"]
        kinds = ", ".join(f"{k} {v}" for k, v in b["invalid_kinds"].items()) or "–"
        why = ", ".join(f"{k} {v}" for k, v in b["fallbacks_by_reason"].items()) or "–"
        if b.get("activity_dropped"):
            kinds += "; activities dropped " + ", ".join(f"{k} {v}" for k, v in b["activity_dropped"].items())
        out.append(f"| {r['label']}{cond_text(r)} | {r.get('npc_label', '–')} | {r['mode']} | {b['calls']} | "
                   f"{o['VALID_FIRST_TRY']} / {o['VALID_AFTER_REPAIR']}{' (' + str(b['salvaged']) + ' salvaged)' if b.get('salvaged') else ''} | "
                   f"{o['TIMEOUT_AT_MODEL']} / {o['TIMEOUT_IN_QUEUE']} | "
                   f"{o['INVALID_OUTPUT']} ({kinds}) | {sum(b['fallbacks_by_reason'].values())} ({why}) | {_drops(b)} | "
                   f"{f(b['queue_ms_p50'])} / {f(b['prefill_ms_p50'])} / {f(b['generation_ms_p50'])} | "
                   f"{f(b['prefill_ms_p95'])} / {f(b['generation_ms_p95'])} | {f(b['prompt_tokens_p50'])} / {f(b['prompt_tokens_p95'])} | "
                   f"{pct(b['cache_share'])} | {f(b['generated_tokens_p50'])} / {f(b['generated_tokens_p95'])} / "
                   f"{f(b['generated_tokens_max'])} ({b['output_cap']}) | {pct(b['other_server_busy_share'])} / "
                   f"{pct(b['other_server_busy_share_timeouts'])} |")
    out += ["", "Calls include repairs. Prefill, generation and token columns come from answered calls (llama-server's "
            "own timings); a timed-out call has none, so its prompt size is the assembled context's (the `robot` block "
            "in results.json: `context_tokens_p50/p95`). Cache share = cached prompt tokens / prompt tokens. Invalid "
            "kinds: TRUNCATED (cut off at the output cap), FORMAT (not JSON or wrong shape), ARGS (an action's "
            "arguments), FN1_RULE (left a conversation without a closing line), ACTIVITY_RULE (the pulse's activity "
            "rules), OTHER."]
    return out


# G3g (D-87): the target counts what the world sees: Robot R's fallback decisions (a timeout or an
# unusable answer both end in WAIT), not only timeouts. Proposed shares (owner, 2026-11-20).
TARGET_FALLBACK_ALONE = 0.05      # Robot R alone (no NPC model)
TARGET_FALLBACK_WITH_NPC = 0.10   # with an NPC model (LIVE; LIVE_LOAD reported against the same share)


def fallback_share(r: dict) -> tuple[int | None, int | None]:
    """(fallback decisions, decisions) of Robot R in a live row; from the G3f breakdown where there is one.
    Decisions held by FN-1 (G3h, D-110) are not failures and are left out."""
    b = r.get("robot")
    if b:
        return sum(v for k, v in (b.get("fallbacks_by_reason") or {}).items() if k != "FN1_HELD"), b.get("decisions")
    return None, None


STRESS_MODES = ("LIVE_LOAD",)   # G3h (owner, 2026-11-21): a stress test, reported, not judged


def target_lines(live: list[dict], f, pooled: dict[int, str]) -> list[str]:
    """G3g target (D-87): Robot R p95 < 4000 ms and its fallback decisions at most 5% alone, 10% with an
    NPC model, in LIVE and LIVE_LOAD; G3f's timeouts and the NPC timeouts beside."""
    rows = [r for r in live if r["mode"] in ("LIVE", "LIVE_LOAD") and id(r) not in pooled]
    if not rows:
        return []
    out = ["", f"### Target (D-87, D-110): Robot R p95 < {TARGET_P95_MS} ms and fallback decisions (timeouts + unusable "
           f"answers, each a WAIT) <= {TARGET_FALLBACK_ALONE:.0%} alone, <= {TARGET_FALLBACK_WITH_NPC:.0%} with an NPC "
           "model, judged in LIVE; LIVE_LOAD is a stress test, reported, not judged (owner, 2026-11-21). Decisions held "
           "by FN-1 are counted apart, not as failures. Pooled rows left out", "",
           "| Robot R model | NPC model | Mode | Robot R p95 ms | Robot R fallback decisions | Held by FN-1 | "
           "Activities dropped (actions kept) | Robot R timeouts (calls) | Salvaged answers | Target | "
           "G3f target (timeouts <= 5%) | NPC timeouts |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        share = r["timeouts"] / r["decisions"] if r["decisions"] else None
        g3f = r["p95_ms"] is not None and r["p95_ms"] < TARGET_P95_MS and share is not None and share <= TARGET_TIMEOUT_SHARE
        fb, dec = fallback_share(r)
        alone = r.get("npc_label") in (None, "none", "–")
        limit = TARGET_FALLBACK_ALONE if alone else TARGET_FALLBACK_WITH_NPC
        fshare = fb / dec if fb is not None and dec else None
        met = None if fshare is None else (r["p95_ms"] is not None and r["p95_ms"] < TARGET_P95_MS and fshare <= limit)
        b = r.get("robot") or {}
        salvaged = b.get("salvaged")
        held = b.get("held_by_fn1", (b.get("fallbacks_by_reason") or {}).get("FN1_HELD")) if b else None
        drops = sum((b.get("activity_dropped") or {}).values()) if b else None
        if r["mode"] in STRESS_MODES:
            verdict, g3f_cell = "stress: reported, not judged", "–"
        else:
            verdict, g3f_cell = ("–" if met is None else ("met" if met else "NOT met")), ("met" if g3f else "NOT met")
        out.append(f"| {r['label']}{cond_text(r)} | {r.get('npc_label', '–')} | {r['mode']} | {f(r['p95_ms'])} | "
                   f"{'–' if fb is None else f'{fb}/{dec} ({pct(fshare)})'} | {f(held)} | {f(drops)} | "
                   f"{r['timeouts']}/{r['decisions']} ({pct(share)}) | "
                   f"{f(salvaged)} | {verdict} | {g3f_cell} | "
                   f"{f(r.get('npc_timeouts'))}/{f(r.get('npc_calls'))} |")
    return out


def diagnosis_lines(rows: list[dict]) -> list[str]:
    """``tools/bakeoff.py diagnose``: one line per run found in each folder (G3f, D-75)."""
    def f(v: Any) -> str:
        return "–" if v is None else str(v)
    out = ["# Robot R's calls in existing run folders (bakeoff.py diagnose, G3f)", "",
           "Each folder is split run by run (the pre-G3f harness appended later runs to a folder's records). "
           "Counts and timings only.", "",
           "| Folder | Run | Model / NPC | Calls | Valid 1st / repaired | Timeouts model / queue | Invalid (kinds) | "
           "Activity rules: rejected / dropped (G3h) | Held by FN-1 | Dropped before send (why) | "
           "Queue / prefill / gen p50 ms | Gen p95 ms | Prompt tok p50 (context p50) | Cache share | Gen tok p50 / p95 / max | "
           "Other busy (timeouts) | NPC calls (timeouts) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o = r["outcomes"]
        kinds = ", ".join(f"{k} {v}" for k, v in r["invalid_kinds"].items()) or "–"
        rules = (", ".join(f"{k} {v}" for k, v in (r.get("activity_rules_rejected") or {}).items()) or "–") + " / " + \
            (", ".join(f"{k} {v}" for k, v in (r.get("activity_dropped") or {}).items()) or "–")
        out.append(f"| {r['run_dir']} | {r['segment']}/{r['segments']} | {f(r.get('model'))} / {f(r.get('npc_model'))} | "
                   f"{r['calls']} | {o['VALID_FIRST_TRY']} / {o['VALID_AFTER_REPAIR']} | {o['TIMEOUT_AT_MODEL']} / "
                   f"{o['TIMEOUT_IN_QUEUE']} | {o['INVALID_OUTPUT']} ({kinds}) | {rules} | {f(r.get('held_by_fn1'))} | "
                   f"{_drops(r) if 'dropped_before_send' in r else '–'} | {f(r['queue_ms_p50'])} / "
                   f"{f(r['prefill_ms_p50'])} / {f(r['generation_ms_p50'])} | {f(r['generation_ms_p95'])} | "
                   f"{f(r['prompt_tokens_p50'])} ({f(r['context_tokens_p50'])}) | {f(r['cache_share'])} | "
                   f"{f(r['generated_tokens_p50'])} / {f(r['generated_tokens_p95'])} / {f(r['generated_tokens_max'])} | "
                   f"{f(r['other_server_busy_share'])} ({f(r['other_server_busy_share_timeouts'])}) | "
                   f"{r['npc_calls']} ({r['npc_timeouts']}) |")
    out += ["", "Activity rules (G3h, D-110): the kind of rule an answer's activity broke; *rejected* = the answer "
            "was refused for it (before G3h), *dropped* = the activity was dropped and the actions kept. Kinds only, "
            "no answer text."]
    return out


def render_tax_lines(live: list[dict], f) -> list[str]:
    """ART_DIRECTION §7: the same scenario headless (LIVE) and rendered (LIVE_RENDERED)."""
    out = []
    for r in [x for x in live if x["mode"] == "LIVE_RENDERED"]:
        base = next((x for x in live if x["mode"] == "LIVE" and x["label"] == r["label"]
                     and x.get("npc_label") == r.get("npc_label") and x.get("pulse", True) == r.get("pulse", True)), None)
        if base is None:
            continue

        def change(a, b):
            return f"{(b - a) / a * 100:+.0f}%" if a and b is not None else "–"
        if not out:
            out = ["", "### Render tax: headless LIVE vs LIVE_RENDERED (ART_DIRECTION §7; proposed limit <= 10% of focal throughput)", "",
                   "| Robot R model | NPC model | Render | Robot R p50 ms headless / rendered (change) | "
                   "Robot R p95 ms headless / rendered (change) | NPC calls/min headless / rendered (change) |",
                   "|---|---|---|---|---|---|"]
        out.append(f"| {r['label']} | {r.get('npc_label', '–')} | {r.get('render')} | "
                   f"{f(base['p50_ms'])} / {f(r['p50_ms'])} ({change(base['p50_ms'], r['p50_ms'])}) | "
                   f"{f(base['p95_ms'])} / {f(r['p95_ms'])} ({change(base['p95_ms'], r['p95_ms'])}) | "
                   f"{f(base.get('npc_calls_per_min'))} / {f(r.get('npc_calls_per_min'))} "
                   f"({change(base.get('npc_calls_per_min'), r.get('npc_calls_per_min'))}) |")
    return out


def pulse_ab_lines(live: list[dict], f) -> list[str]:
    """Pulse on vs off for the same model, NPC model and mode (G3d, --no-pulse)."""
    out = []
    for off in [x for x in live if x.get("pulse") is False]:
        on = next((x for x in live if x.get("pulse", True) and x["label"] == off["label"] and x["mode"] == off["mode"]
                   and x.get("npc_label") == off.get("npc_label")), None)
        if on is None:
            continue
        if not out:
            out = ["", "### Pulse on vs off (same models, mode and scene)", "",
                   "| Robot R model | Mode | Robot R calls on / off | Robot R p50 / p95 ms on | off | "
                   "Robot R actions accepted on / off | Timeouts on / off | Frame p95 ms on / off |",
                   "|---|---|---|---|---|---|---|---|"]
        out.append(f"| {off['label']} | {off['mode']} | {on['decisions']} / {off['decisions']} | "
                   f"{f(on['p50_ms'])} / {f(on['p95_ms'])} | {f(off['p50_ms'])} / {f(off['p95_ms'])} | "
                   f"{f(on.get('robot_actions_accepted'))} / {f(off.get('robot_actions_accepted'))} | "
                   f"{f(on['timeouts'])} / {f(off['timeouts'])} | {f(on.get('frame_p95_ms'))} / {f(off.get('frame_p95_ms'))} |")
    return out
