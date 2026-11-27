"""A readable account of one run: who said what to whom, gestures, Director interventions, refused
actions, and every decision that timed out or was held (with what the agent wanted to do).

    uv run python tools/transcript.py latest
    uv run python tools/transcript.py runs/<run> [--all] [--agent robot_r]

Live runs go by too fast to read (owner, 2026-11-27); this reads the run folder afterwards.
Writes ``transcript.md`` in the run folder and prints it.

**Evaluator-level (D-90):** it names avatars by their real ids (from viewer/truth_tracks.json) and
quotes raw model answers of held decisions. Fine on your own PC; share summaries, not this file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.eval.run_paths import RunPathError, resolve_run   # noqa: E402

TICK_HZ = 60
ANON = re.compile(r"\banon_[a-z0-9]{10}\b")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Names:
    """Real names for each observer's anonymous track ids and LEAN handles (evaluator truth)."""

    def __init__(self, run: Path) -> None:
        truth = run / "viewer" / "truth_tracks.json"
        self.tracks: dict[str, dict[str, str]] = json.loads(truth.read_text(encoding="utf-8")) if truth.is_file() else {}
        self.handles: dict[str, dict[str, str]] = {}          # decision_id -> {P1: anon_...}
        for entry in _jsonl(run / "sidecar" / "prompts.jsonl"):
            if entry.get("handles"):
                self.handles[entry["decision_id"]] = dict(entry["handles"])

    def of(self, observer: str, ref: Any, decision_id: str | None = None) -> str:
        if ref is None:
            return "?"
        ref = str(ref)
        if decision_id and ref in self.handles.get(decision_id, {}):
            ref = self.handles[decision_id][ref]
        return self.tracks.get(observer, {}).get(ref, ref)

    def text(self, observer: str, s: str) -> str:
        return ANON.sub(lambda m: self.of(observer, m.group(0)), s)


def _t(ms: Any) -> str:
    return f"{float(ms) / 1000.0:6.1f} s"


def _wanted(answer: str | None, agent: str, names: Names, decision_id: str) -> str:
    """What a raw answer asked for, in a few words."""
    if not answer:
        return "(no answer text)"
    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        return "(not readable: " + answer[:80] + ")"
    parts = []
    for a in data.get("actions", []) if isinstance(data, dict) else []:
        args = a.get("args", {}) or {}
        act = str(a.get("action", "?"))
        who = args.get("addressee_id", args.get("target_id"))
        bit = act
        if who is not None:
            bit += " " + names.of(agent, who, decision_id)
        dest = args.get("destination")
        if isinstance(dest, dict):
            bit += f" to ({dest.get('x')}, {dest.get('z')})"
        if args.get("text"):
            bit += f" “{args['text']}”"
        if args.get("gesture"):
            bit += f" {args['gesture']}"
        parts.append(bit)
    return "; ".join(parts) or "(no actions)"


def _intervention(iv: dict[str, Any]) -> str:
    """One Director intervention in words."""
    op, target, args = str(iv.get("operation")), iv.get("target_id"), iv.get("args") or {}
    after = iv.get("after")
    try:
        prop = json.loads(after) if isinstance(after, str) and after.startswith("{") else {}
    except json.JSONDecodeError:
        prop = {}
    if op == "EDIT_DIRECTIVE":
        return f"{target}'s {args.get('field', 'directive')} is now “{after}”"
    if op == "PLACE_PROP":
        kind = str(prop.get("prop_type", args.get("prop_type", "prop"))).lower()
        text = prop.get("text") or args.get("text")
        at = f"at ({prop.get('x', args.get('x'))}, {prop.get('z', args.get('z'))})"
        return f"placed a {kind} {at}" + (f" saying “{text}”" if text else "") + f" [{target}]"
    if op == "MOVE_PROP":
        return f"moved {target} to ({args.get('x')}, {args.get('z')})"
    if op == "REMOVE_PROP":
        return f"removed {target}"
    if op == "PA_ANNOUNCEMENT":
        return f"PA announcement “{prop.get('text', args.get('text'))}”"
    if op == "NPC_SAY":
        return f"told {target} to say “{args.get('text')}”"
    if op == "TRIGGER_EVENT":
        return f"triggered {args.get('event_type')} for {target}"
    return f"{op} {target or ''} {str(after or '')[:100]}".strip()


def build(run: Path, show_all: bool = False, only: str | None = None) -> list[str]:
    names = Names(run)
    rows: list[tuple[float, int, str]] = []
    seq = 0

    def add(ms: Any, line: str, actor: str | None) -> None:
        nonlocal seq
        if only and actor not in (only, None):
            return
        seq += 1
        rows.append((float(ms), seq, f"{_t(ms)}  {line}"))

    for e in _jsonl(run / "journal.jsonl"):
        kind, p, ms = e["kind"], e.get("payload", {}), e.get("sim_time_ms", 0)
        actor = e.get("actor_id")
        if kind == "SPEECH_EMITTED":
            to = p.get("addressee_id")
            add(ms, f"{p['avatar_id']} → {to if to else 'anyone nearby'} [{p.get('channel', '?')}]: “{p.get('text', '')}”", actor)
        elif kind == "GESTURE_PERFORMED":
            add(ms, f"{p['avatar_id']} gestures {p.get('gesture')}", actor)
        elif kind == "GESTURE_REFUSED":
            add(ms, f"{p['avatar_id']} could not gesture {p.get('gesture')} ({p.get('reason', 'refused')})", actor)
        elif kind == "EXPRESSION_SHOWN":
            eid = str(p.get("expression_id", "?"))
            if show_all or not eid.startswith("ambient_"):
                add(ms, f"{p['avatar_id']} shows {eid}", actor)
        elif kind == "ACTION_RESOLVED":
            req, res = p.get("request", {}), p.get("result", {})
            agent = str(req.get("agent_id", actor))
            act = str(req.get("action", "?"))
            args = req.get("args", {}) or {}
            if not res.get("accepted", True):
                add(ms, f"{agent}: {act} refused ({res.get('reason_code')})", agent)
            elif act == "MOVE_TO" or (show_all and act in ("TURN_TO", "LOOK_AT", "WAIT", "YIELD")):
                where = args.get("destination")
                tgt = args.get("target_id")
                place = (f"toward {names.of(agent, tgt)}" if tgt else
                         f"to ({where.get('x')}, {where.get('z')})" if isinstance(where, dict) else "")
                verb = {"MOVE_TO": "walks", "TURN_TO": "turns", "LOOK_AT": "looks", "WAIT": "waits", "YIELD": "yields"}[act]
                add(ms, f"{agent} {verb} {place}".rstrip(), agent)
        elif kind == "INTERVENTION":
            iv = p.get("intervention") or p.get("request") or {}
            status = p.get("status") or ("REFUSED" if p.get("reason") else "APPLIED")
            add(ms, f"[DIRECTOR] {status}: {_intervention(iv)}" + (f" ({p['reason']})" if p.get("reason") else ""), None)
        elif kind in ("RUN_STARTED", "RUN_ENDED"):
            add(ms, f"— {kind.replace('_', ' ').lower()} —", None)

    for r in _jsonl(run / "sidecar" / "decision_records.jsonl"):
        fb = r.get("fallback")
        if not fb:
            continue
        agent, did = r["agent_id"], r["decision_id"]
        ms = float(r["based_on_tick_id"]) * 1000.0 / TICK_HZ
        reason = str(fb.get("reason", "?"))
        calls = r.get("model_calls", [])
        if reason == "TIMEOUT":
            add(ms, f"{agent} took too long to decide (deadline missed) → waited", agent)
        elif reason == "FN1_HELD":
            wanted = _wanted(calls[-1].get("response_text") if calls else None, agent, names, did)
            add(ms, f"{agent} tried to leave a conversation without a goodbye → held. It wanted: {wanted}", agent)
        else:
            err = names.text(agent, str((calls[-1].get("error") if calls else "") or ""))[:140]
            add(ms, f"{agent}: unusable answer ({reason}) → waited. {err}", agent)

    rows.sort()
    return [f"# Transcript: {run.name}", "",
            "Evaluator-level: real names and raw answers of held decisions. Keep it local (D-90).", "",
            "```text", *[line for _, _, line in rows], "```"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/transcript.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", help="a run folder (as printed after 'Run folder:'), or 'latest'")
    parser.add_argument("--all", action="store_true", help="also glances, turns, waits and ambient displays")
    parser.add_argument("--agent", default=None, help="only this avatar (Director lines always shown)")
    args = parser.parse_args(argv)
    try:
        run = resolve_run(args.run)
    except RunPathError as exc:
        print(f"FAIL  {exc}")
        return 2
    lines = build(run, args.all, args.agent)
    out = run / "transcript.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
