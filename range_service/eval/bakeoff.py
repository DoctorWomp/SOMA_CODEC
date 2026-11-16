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
    tracks = set(TRACK.findall(item["prompt"]))
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


def kept_commitment(actions: list[dict[str, Any]], item: dict[str, Any]) -> bool | None:
    """None when the situation did not call for keeping a promise (the Demo policy kept none)."""
    if not item["reference"].get("demo_fulfilled"):
        return None
    return any(a.get("fulfills_commitment") for a in actions)


# ---------- per-condition scoring ----------

def score_item(item: dict[str, Any], result: Any) -> dict[str, Any]:
    calls = result.model_calls
    first = calls[0] if calls else {}
    actions = result.actions if result.fallback is None else []
    problems = offline_gate(actions, item) if actions else []
    t = first.get("timings") or {}
    processed = (first.get("prompt_tokens") or 0) - (first.get("cached_tokens") or 0)
    return {
        "item_id": item["item_id"],
        "first_valid": first.get("outcome") == "VALID",
        "repaired": len(calls) > 1 and result.fallback is None,
        "final_valid": result.fallback is None,
        "fallback": (result.fallback or {}).get("reason"),
        "signature": [signature(a) for a in actions],
        "gate_ok": bool(actions) and not problems, "gate_problems": problems,
        "kept": kept_commitment(actions, item),
        "prompt_tps": round(processed / t["prefill_ms"] * 1000, 1) if t.get("prefill_ms") and processed > 0 else None,
        "gen_tps": round(first["generated_tokens"] / t["generation_ms"] * 1000, 1)
        if t.get("generation_ms") and first.get("generated_tokens") else None,
        "total_ms": t.get("total_ms"),
        "actions": actions,
    }


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _median(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def summarize_condition(items: list[dict[str, Any]]) -> dict[str, Any]:
    kept = [i["kept"] for i in items if i["kept"] is not None]
    return {
        "n": len(items),
        "valid_before_repair": _rate([i["first_valid"] for i in items]),
        "repair_rate": _rate([i["repaired"] for i in items]),
        "final_valid": _rate([i["final_valid"] for i in items]),
        "valid_action_rate": _rate([i["gate_ok"] for i in items]),
        "commitments_kept": _rate(kept) if kept else None,
        "commitments_note": None if kept else "no prompt in the set called for keeping a promise",
        "prompt_tps_median": _median([i["prompt_tps"] for i in items]),
        "gen_tps_median": _median([i["gen_tps"] for i in items]),
        "latency_ms_p50": _median([i["total_ms"] for i in items]),
    }


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

def vram_mib(pid: int | None) -> tuple[int | None, str | None]:
    """GPU memory used by one process, from nvidia-smi. (None, reason) when it cannot be read."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None, "nvidia-smi not found (no NVIDIA GPU or driver)"
    if pid is None:
        return None, "no server process"
    try:
        out = subprocess.run([exe, "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"nvidia-smi failed: {exc}"
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0] == str(pid) and parts[1].isdigit():
            return int(parts[1]), None
    return None, "the server process uses no GPU memory (CPU build, or layers not offloaded)"


# ---------- report ----------

def write_report(results: dict[str, Any], folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    json_path, md_path = folder / "results.json", folder / "results.md"
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# Bake-off results ({results.get('created', '?')})", "",
             f"Engine: {results.get('engine')} · prompt set: {results.get('prompt_set')} "
             f"({results.get('prompt_set_sha256', '')[:12]}) · temperature 0", ""]
    offline = results.get("offline", [])
    if offline:
        lines += ["## Offline prompt set", "",
                  "| Model | Quant | KV | n | Valid before repair | Repair | Final valid | Valid actions | Promises kept | "
                  "Agree vs higher precision | Agree q8_0 vs f16 | Prompt tok/s | Gen tok/s | p50 ms | VRAM MiB |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

        def f(v: Any) -> str:
            return "–" if v is None else (f"{v:.0%}" if isinstance(v, float) and v <= 1.0 and not isinstance(v, bool) else str(v))
        for c in offline:
            s = c["summary"]
            ag = c.get("agreement_precision")
            akv = c.get("agreement_kv")
            lines.append(f"| {c['label']} {c['model']} | {c['quant']}{' QAT' if c['qat'] else ''} | {c['kv']} | {s['n']} | "
                         f"{f(s['valid_before_repair'])} | {f(s['repair_rate'])} | {f(s['final_valid'])} | "
                         f"{f(s['valid_action_rate'])} | {f(s['commitments_kept'])} | "
                         f"{f(ag['first_action']) + ' vs ' + ag['reference'] if ag else '–'} | {f(akv['first_action']) if akv else '–'} | "
                         f"{f(s['prompt_tps_median'])} | {f(s['gen_tps_median'])} | {f(s['latency_ms_p50'])} | "
                         f"{c['vram_mib'] if c['vram_mib'] is not None else '– (' + str(c['vram_note']) + ')'} |")
        lines.append("")
    live = results.get("live", [])
    if live:
        lines += ["## Live and stepped SB-04", "",
                  "| Model | Mode | Run OK | Decisions | Deadline misses | Fallbacks | p50 ms | p95 ms | Journal |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in live:
            lines.append(f"| {r['label']} | {r['mode']} | {'yes' if r['ok'] else 'NO'} | {r['decisions']} | {r['timeouts']} | "
                         f"{r['fallbacks']} | {r['p50_ms']} | {r['p95_ms']} | {r['journal'][:12]} |")
        lines.append("")
    lines += ["Agreement = share of prompts where both conditions chose the same first action (and its key argument). "
              "Valid actions = the offline action-gate check. – = not measured (see results.json for the reason)."]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
