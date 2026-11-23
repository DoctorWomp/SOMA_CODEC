"""Where Robot R's time goes in a live run (G3f, D-75).

Reads a run's ``sidecar/decision_records.jsonl`` (and ``sidecar/delivery.jsonl``) and breaks
Robot R's model calls down by outcome and by cost, so the live bake-off can say *why* a call
missed its deadline instead of only that it did:

- **outcomes**, per call: VALID on the first try, VALID after a repair, TIMEOUT (dropped in the
  scheduler's queue vs at the model), INVALID_OUTPUT by kind (cut off at the output cap, not
  JSON / wrong shape, bad arguments, the FN-1 conversation rule, the activity rules, not repaired
  for lack of time), PROVIDER_ERROR; per decision: how many ended in a fallback and why; answers
  dropped before sending (D-63);
- **cost**, per call: queue, prefill and generation time; prompt tokens (from the server, and the
  assembled context size, which is known even when the call timed out); cached tokens and the
  share of prompt tokens served from the cache; generated tokens and how many hit the output cap;
  how much of the call's time the other model server was also busy (one GPU, Option C).

``split_runs`` separates records that several runs appended to one file (the run-folder bug fixed
in G3f): each agent's decision numbers restart with every run. Only counts, times and token
numbers leave this module: never prompt or answer text.
"""

from __future__ import annotations

from collections import Counter

import json
from pathlib import Path
from typing import Any

ROBOT = "robot_r"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _num(decision_id: str) -> int:
    tail = decision_id.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else -1


def split_runs(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Records of one file, split wherever an agent's decision number does not increase: a later
    run appended to the same file. One run gives one segment."""
    segments: list[list[dict[str, Any]]] = [[]]
    last: dict[str, int] = {}
    for rec in records:
        n = _num(rec.get("decision_id", ""))
        agent = rec.get("agent_id", "?")
        if agent in last and n <= last[agent]:
            segments.append([])
            last = {}
        last[agent] = n
        segments[-1].append(rec)
    return [s for s in segments if s]


def pooled(records: list[dict[str, Any]]) -> bool:
    """True when the file holds more than one run's records."""
    return len(split_runs(records)) > 1


def classify_error(error: str | None) -> str:
    """The kind of an INVALID_OUTPUT call, from the gateway's or the runtime's error text."""
    e = (error or "").lower()
    if "cut off at the" in e:
        return "TRUNCATED"
    if "you are in a conversation with" in e:
        return "FN1_RULE"
    if e.startswith(("activity", '"activity"', '"review_after_s"', '"wake_if"', "each wake condition", "wake condition",
                     "unknown wake condition", '"target_within_m"')) or " needs a target_id" in e:
        return "ACTIVITY_RULE"
    if "not valid json" in e or "must be an object" in e or '"actions" must be' in e or '"reason_summary" must' in e:
        return "FORMAT"
    if e.startswith("action "):
        return "ARGS"
    return "OTHER"


def activity_rule(error: str | None) -> str | None:
    """G3h (D-110): which activity rule an ACTIVITY_RULE error broke (the kind only), else None."""
    if classify_error(error) != "ACTIVITY_RULE":
        return None
    from range_service.agents.activity import rule_of   # noqa: PLC0415

    return rule_of(error)


def _pct(values: list[float], q: float) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return float(vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))]) if vals else None


def robot_breakdown(records: list[dict[str, Any]], delivery: list[dict[str, Any]] | None = None,
                    agent_id: str = ROBOT, output_cap: int | None = None) -> dict[str, Any]:
    """The breakdown of one agent's model calls over ``records`` (one or several runs)."""
    from range_service.agents.context import OUTPUT_CAPS   # noqa: PLC0415

    cap = output_cap if output_cap is not None else OUTPUT_CAPS["FOCAL"]
    recs = [r for r in records if r.get("agent_id") == agent_id and r.get("model_calls")]
    calls = [c for r in recs for c in r["model_calls"]]
    outcomes = {"VALID_FIRST_TRY": 0, "VALID_AFTER_REPAIR": 0, "TIMEOUT_IN_QUEUE": 0, "TIMEOUT_AT_MODEL": 0,
                "INVALID_OUTPUT": 0, "PROVIDER_ERROR": 0, "OTHER": 0}
    invalid_kinds: dict[str, int] = {}
    not_repaired = 0
    salvaged = 0
    activity_rules: dict[str, int] = {}     # G3h (D-110): rule kinds of rejected activities (old runs)
    activity_dropped: dict[str, int] = {}   # ... and of activities dropped with the actions kept
    for c in calls:
        o = c.get("outcome")
        if c.get("salvaged"):
            salvaged += 1                  # G3g (D-86): cut off, its complete actions used (also VALID)
        if c.get("activity_dropped"):
            rule = c["activity_dropped"].get("rule", "OTHER")
            activity_dropped[rule] = activity_dropped.get(rule, 0) + 1
        if o == "INVALID_OUTPUT" and activity_rule(c.get("error")):
            rule = activity_rule(c.get("error")) or "OTHER"
            activity_rules[rule] = activity_rules.get(rule, 0) + 1
        if o == "VALID":
            outcomes["VALID_AFTER_REPAIR" if c.get("attempt") == 1 else "VALID_FIRST_TRY"] += 1
        elif o == "TIMEOUT":
            dropped = "dropped before reaching the model" in (c.get("error") or "")
            outcomes["TIMEOUT_IN_QUEUE" if dropped else "TIMEOUT_AT_MODEL"] += 1
        elif o == "INVALID_OUTPUT":
            outcomes["INVALID_OUTPUT"] += 1
            kind = classify_error(c.get("error"))
            invalid_kinds[kind] = invalid_kinds.get(kind, 0) + 1
            if "not repaired:" in (c.get("error") or ""):
                not_repaired += 1
        elif o == "PROVIDER_ERROR":
            outcomes["PROVIDER_ERROR"] += 1
        else:
            outcomes["OTHER"] += 1
    fallbacks: dict[str, int] = {}
    for r in recs:
        if r.get("fallback"):
            reason = r["fallback"].get("reason", "?")
            fallbacks[reason] = fallbacks.get(reason, 0) + 1
    pulse_recs = [r for r in recs if r.get("triggers") == ["PULSE_REVIEW"]]
    t = lambda k: [c["timings"].get(k) for c in calls]   # noqa: E731
    answered = [c for c in calls if c.get("response_text") is not None or c.get("generated_tokens") is not None]
    prompt_tok = [c.get("prompt_tokens") for c in answered if c.get("prompt_tokens") is not None]
    cached_tok = [c.get("cached_tokens") for c in answered if c.get("cached_tokens") is not None]
    gen_tok = [c.get("generated_tokens") for c in answered if c.get("generated_tokens") is not None]
    sum_prompt = sum(c["prompt_tokens"] for c in answered if c.get("prompt_tokens") is not None and c.get("cached_tokens") is not None)
    sum_cached = sum(c["cached_tokens"] for c in answered if c.get("prompt_tokens") is not None and c.get("cached_tokens") is not None)
    ctx = [(r.get("context") or {}).get("total_tokens") for r in recs]
    busy = [c.get("other_server_busy_ms") for c in calls if c.get("other_server_busy_ms") is not None]
    busy_total = [c["timings"]["total_ms"] or 0 for c in calls if c.get("other_server_busy_ms") is not None]
    timeouts = [c for c in calls if c.get("outcome") == "TIMEOUT"]
    t_busy = [c.get("other_server_busy_ms") for c in timeouts if c.get("other_server_busy_ms") is not None]
    t_total = [c["timings"]["total_ms"] or 0 for c in timeouts if c.get("other_server_busy_ms") is not None]
    dropped = [d for d in (delivery or []) if d.get("agent_id") == agent_id and d.get("event") in ("DISCARDED", "DROPPED")]
    dropped_before_send = len(dropped)
    # G3 close-out (owner, 2026-11-23): why each answer was dropped before sending (D-63's relevance
    # check: TARGET_NOT_PERCEIVED, SOMEONE_ELSE_ADDRESSING; or DECISION_DEADLINE_PASSED).
    dropped_by_reason = Counter(str(d.get("reason") or "UNKNOWN") for d in dropped)
    return {
        "calls": len(calls), "decisions": len(recs), "decisions_pulse_review": len(pulse_recs),
        "outcomes": outcomes, "invalid_kinds": dict(sorted(invalid_kinds.items())), "invalid_not_repaired": not_repaired,
        "salvaged": salvaged,
        # G3h (D-110): held by FN-1 (stayed with the partner) is the right outcome, counted apart.
        "fallbacks": sum(v for k, v in fallbacks.items() if k != "FN1_HELD"),
        "held_by_fn1": fallbacks.get("FN1_HELD", 0),
        "activity_rules_rejected": dict(sorted(activity_rules.items())),
        "activity_dropped": dict(sorted(activity_dropped.items())),
        "fallbacks_by_reason": dict(sorted(fallbacks.items())),
        "timeouts_on_pulse_reviews": sum(1 for r in pulse_recs for c in r["model_calls"] if c.get("outcome") == "TIMEOUT"),
        "dropped_before_send": dropped_before_send,
        "dropped_before_send_by_reason": dict(sorted(dropped_by_reason.items())),
        "queue_ms_p50": _pct(t("queue_ms"), 0.5), "queue_ms_p95": _pct(t("queue_ms"), 0.95),
        "prefill_ms_p50": _pct(t("prefill_ms"), 0.5), "prefill_ms_p95": _pct(t("prefill_ms"), 0.95),
        "generation_ms_p50": _pct(t("generation_ms"), 0.5), "generation_ms_p95": _pct(t("generation_ms"), 0.95),
        "total_ms_p50": _pct(t("total_ms"), 0.5), "total_ms_p95": _pct(t("total_ms"), 0.95),
        "prompt_tokens_p50": _pct(prompt_tok, 0.5), "prompt_tokens_p95": _pct(prompt_tok, 0.95),
        "context_tokens_p50": _pct(ctx, 0.5), "context_tokens_p95": _pct(ctx, 0.95),
        "cached_tokens_p50": _pct(cached_tok, 0.5),
        "cache_share": round(sum_cached / sum_prompt, 2) if sum_prompt else None,
        "generated_tokens_p50": _pct(gen_tok, 0.5), "generated_tokens_p95": _pct(gen_tok, 0.95),
        "generated_tokens_max": max(gen_tok) if gen_tok else None,
        "at_output_cap": sum(1 for g in gen_tok if g >= cap), "output_cap": cap,
        "other_server_busy_share": round(sum(busy) / sum(busy_total), 2) if busy and sum(busy_total) else None,
        "other_server_busy_share_timeouts": round(sum(t_busy) / sum(t_total), 2) if t_busy and sum(t_total) else None,
    }


def diagnose_folder(run_dir: Path, agent_id: str = ROBOT) -> list[dict[str, Any]]:
    """One breakdown per run found in a run folder (several if runs were appended to it)."""
    records = _jsonl(run_dir / "sidecar" / "decision_records.jsonl")
    delivery = _jsonl(run_dir / "sidecar" / "delivery.jsonl")
    segments = split_runs(records)
    out = []
    for k, seg in enumerate(segments, start=1):
        row = robot_breakdown(seg, delivery if len(segments) == 1 else None, agent_id)
        row.update({"run_dir": run_dir.name, "segment": k, "segments": len(segments),
                    "npc_calls": sum(len(r["model_calls"]) for r in seg if r.get("agent_id") != agent_id),
                    "npc_timeouts": sum(1 for r in seg if r.get("agent_id") != agent_id
                                        for c in r["model_calls"] if c.get("outcome") == "TIMEOUT")})
        out.append(row)
    return out
