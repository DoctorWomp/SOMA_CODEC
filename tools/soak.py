"""Soak check (G3d, D-70): a long run must stay bounded.

    uv run python tools/soak.py                         # SB-09 (21 simulated minutes), fake model, stepped
    uv run python tools/soak.py --model llama --mode live   # on the owner's PC: real models, real time
    uv run python tools/soak.py --check runs/<run>          # check a soak run that already exists

Runs SB09_SOAK with Robot R and the visitors deciding through the model path (the fake model by
default: Robot R plus C1/C2 NPCs), then splits the run into 5-minute windows and checks:

- **prompt tokens per decision**: per agent and tier, never over the tier budget, and flat once the
  sections have filled: the largest context in the last full window is at most 5% above the full
  window before it (contexts grow in the first minutes while facts, episodes and conversation
  fill their budgets; that is expected and reported);
- **memory per agent**: active memory items (counted from each item's own times) stop growing:
  the last full window's count is at most 10% (+2 items) above the one before; open promises stay
  at most 8 and episode cards at most 50; the count per store at the end is reported;
- **log and journal growth**: journal lines, decision records, pulse-log lines and link messages
  per window grow linearly, not faster: the last window's count is at most 1.5x the median window;
- the run itself: no sidecar problems, no step timeouts.

Writes ``soak_summary.json`` in the run folder: counts and sizes only, no prompt or memory text.
That file (or the printed table) is what to paste back. The run folder itself holds raw prompts
and memories and stays under runs/ (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.agents.context import BUDGETS  # noqa: E402
from range_service.agents.memory import MAX_EPISODE_CARDS, MAX_OPEN_COMMITMENTS  # noqa: E402

WINDOW_MS = 300_000
SCENARIO = "SB09_SOAK"


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _window(ms: int) -> int:
    return ms // WINDOW_MS


def _median(values: list[int]) -> float:
    vals = sorted(values)
    return vals[len(vals) // 2] if vals else 0


def soak_summary(run_dir: Path, tick_hz_world: int = 60) -> dict:
    journal = _jsonl(run_dir / "journal.jsonl")
    records = _jsonl(run_dir / "sidecar" / "decision_records.jsonl")
    pulse = _jsonl(run_dir / "pulse.jsonl")
    sent = _jsonl(run_dir / "sidecar" / "sidecar_sent.jsonl")
    received = _jsonl(run_dir / "sidecar" / "sidecar_received.jsonl")
    memory = json.loads((run_dir / "sidecar" / "agent_memory.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    end_ms = max((e["sim_time_ms"] for e in journal), default=0)
    windows = _window(end_ms) + 1
    problems: list[str] = []

    # Prompt tokens per decision, per agent and tier.
    tokens: dict[str, dict[int, int]] = {}
    for r in records:
        if not r.get("context"):
            continue
        key = f"{r['agent_id']}:{r['tier']}"
        w = _window(r["based_on_tick_id"] * 1000 // tick_hz_world)
        tokens.setdefault(key, {})
        tokens[key][w] = max(tokens[key].get(w, 0), r["context"]["total_tokens"])
    full = windows - 1 if end_ms % WINDOW_MS else windows      # the last window may be short
    for key, per in tokens.items():
        tier = key.split(":")[1]
        budget = sum(BUDGETS[tier].values())
        if max(per.values()) > budget:
            problems.append(f"{key}: a context of {max(per.values())} tokens is over the {tier} budget {budget}")
        seen = [per[w] for w in range(full) if w in per]
        if len(seen) >= 2 and seen[-1] > seen[-2] * 1.05:
            problems.append(f"{key}: largest context still growing in the last full window ({seen[-2]} -> {seen[-1]} tokens)")

    # Memory per agent: active items at the end of each window, from each item's own times.
    mem: dict[str, dict] = {}
    for aid, items in memory.items():
        if not isinstance(items, list) or not items or not isinstance(items[0], dict) or "store" not in items[0]:
            continue
        counts = []
        for w in range(windows):
            t = min(end_ms, (w + 1) * WINDOW_MS)
            counts.append(sum(1 for i in items if i["observed_at_ms"] <= t
                              and (i["expires_at_ms"] is None or i["expires_at_ms"] > t)
                              and not (i["status"] == "CONTRADICTED")))
        open_promises = sum(1 for i in items if i["store"] == "COMMITMENTS_AND_REFUSALS"
                            and i["content"].get("commitment_state") == "OPEN" and i["status"] != "EXPIRED")
        cards = sum(1 for i in items if i["store"] == "EPISODIC_LEDGER" and i["source_class"] == "SELF"
                    and i["status"] not in ("EXPIRED", "CONTRADICTED"))
        by_store: dict[str, int] = {}
        for i in items:
            if i["status"] in ("EXPIRED", "CONTRADICTED"):
                continue
            key = f"{i['store']}:{i['source_class']}"
            by_store[key] = by_store.get(key, 0) + 1
        mem[aid] = {"active_items_per_window": counts, "stored_items_total": len(items), "open_promises_end": open_promises,
                    "episode_cards_end": cards, "active_by_store_end": dict(sorted(by_store.items()))}
        body = counts[:full]
        if len(body) >= 2 and body[-1] > body[-2] * 1.10 + 2:
            problems.append(f"{aid}: active memory items still growing in the last full window {body} "
                            f"(at the end, by store: {dict(sorted(by_store.items()))})")
        if open_promises > MAX_OPEN_COMMITMENTS or cards > MAX_EPISODE_CARDS:
            problems.append(f"{aid}: {open_promises} open promises, {cards} episode cards (caps {MAX_OPEN_COMMITMENTS}/{MAX_EPISODE_CARDS})")

    # Logs and journal: per-window counts grow linearly (a steady rate), not faster.
    def per_window(times: list[int]) -> list[int]:
        out = [0] * windows
        for t in times:
            out[min(windows - 1, _window(t))] += 1
        return out
    growth = {
        "journal_lines": per_window([e["sim_time_ms"] for e in journal]),
        "decision_records": per_window([r["based_on_tick_id"] * 1000 // tick_hz_world for r in records]),
        "pulse_log_lines": per_window([e["at_ms"] for e in pulse]),
        "link_messages": per_window([e["sim_time_ms"] for e in sent + received]),
    }
    for name, counts in growth.items():
        body = counts[:full]
        if len(body) >= 2 and body[-1] > 1.5 * _median(body) + 10:
            problems.append(f"{name} per 5 minutes grows faster than linearly: {counts}")
    if summary["sidecar_problems"] or summary["step_timeouts"]:
        problems.append(f"sidecar problems {summary['sidecar_problems'][:2]}, step timeouts {summary['step_timeouts']}")
    sizes = {p.name: p.stat().st_size for p in [run_dir / "journal.jsonl", run_dir / "pulse.jsonl",
                                                run_dir / "sidecar" / "decision_records.jsonl",
                                                run_dir / "sidecar" / "prompts.jsonl"] if p.is_file()}
    return {"scenario": SCENARIO, "simulated_minutes": round(end_ms / 60000, 1), "window_minutes": WINDOW_MS // 60000,
            "prompt_tokens_max_per_window": {k: [v.get(w) for w in range(windows)] for k, v in sorted(tokens.items())},
            "memory": mem, "growth_per_window": growth, "file_bytes": sizes,
            "decisions": len(records), "model_calls": sum(len(r["model_calls"]) for r in records),
            "fallbacks": sum(1 for r in records if r["fallback"]), "problems": problems, "ok": not problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/soak.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="fake")
    parser.add_argument("--mode", default="stepped", choices=["stepped", "live"])
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None, help="only check an existing soak run folder")
    args = parser.parse_args(argv)
    run_dir = args.check
    if run_dir is None:
        from range_service.eval.runner import RunError, RunOptions, run_scenario
        from tools.godot_check import find_godot

        godot = find_godot()
        if godot is None:
            print("Godot not found. Set GODOT_BIN, or run: uv run python tools/install_godot.py")
            return 2
        try:
            result = asyncio.run(run_scenario(RunOptions(SCENARIO, godot, mode=args.mode.upper(), model=args.model,
                                                         out_dir=args.out, timeout_s=7200)))
        except RunError as exc:
            print(f"FAIL  {exc}")
            return 1
        run_dir = result.run_dir
    s = soak_summary(run_dir)
    (run_dir / "soak_summary.json").write_text(json.dumps(s, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Soak {s['scenario']}: {s['simulated_minutes']} simulated minutes, {s['decisions']} decisions, "
          f"{s['model_calls']} model calls, {s['fallbacks']} fallbacks (windows of {s['window_minutes']} min)")
    for key, per in s["prompt_tokens_max_per_window"].items():
        print(f"  prompt tokens, largest per window, {key}: {per}")
    for aid, m in s["memory"].items():
        print(f"  memory {aid}: active items per window {m['active_items_per_window']}; open promises "
              f"{m['open_promises_end']}, episode cards {m['episode_cards_end']}; by store {m['active_by_store_end']}")
    for name, counts in s["growth_per_window"].items():
        print(f"  {name} per window: {counts}")
    print(f"  files: {s['file_bytes']}")
    for p in s["problems"]:
        print(f"  PROBLEM {p}")
    print(f"{'OK' if s['ok'] else 'FAIL'}  summary: {run_dir / 'soak_summary.json'}")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
