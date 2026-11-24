"""The viewer feed (G4a, D-93): what the layer viewer draws, per observer, from logged run data.

One builder makes the same records whether a run is live or finished:

- **Live** (a watched run): the sidecar feeds the builder as things happen (packets, the requests it
  sends and the world's results, decision records, the pulse log, holds and drops before sending)
  and appends the new records to ``RUN/viewer/observer_feed.jsonl``, which Godot's viewer reads.
- **Replay** (every run, at its end; old run folders with ``tools/view_run.py``): ``build_run``
  feeds the builder from the run folder's logs, the very messages the sidecar saw
  (``sidecar_received``, ``sidecar_sent``, ``decision_records``, ``prompts``, ``pulse``, ``delivery``).

Two audiences, two files (contracts/viewer_record):

- ``observer_feed.jsonl``, audience ``OBSERVER`` (any seat holding VIEW_LAYERS): per observer, only
  what that observer's own packets, decisions and requests hold. People appear as the observer's
  own anonymous track ids (with its D-111 handle beside them); never another avatar's real id,
  never a private goal, a scenario label or prompt text. Robot R's ``reason_summary`` (FULL only;
  LEAN has none, D-85) is the model's own words and is labelled so.
- ``evaluator_truth.jsonl``, audience ``EVALUATOR`` (the Evaluator seat only): which avatar each
  track was (Godot's ``truth_tracks.json``, written at run end), scenario labels, private goals,
  assembled prompts and raw answers, errors, and the own words of agents whose prompt holds a
  private goal (an NPC's own goal enters its own prompt, D-51).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
OBSERVER_FILE = "observer_feed.jsonl"
EVALUATOR_FILE = "evaluator_truth.jsonl"
TRUTH_TRACKS_FILE = "truth_tracks.json"
OBSERVER_LANES = ("meta", "sight", "hearing", "tracks", "handles", "pulse", "decision", "action", "result",
                  "delivery", "beacon")
EVALUATOR_LANES = ("truth_tracks", "truth_labels", "truth_goals", "prompt", "answer")
# HORIZON layers: shown in the viewer, empty until G5 builds them (no layer is faked).
HORIZON_LAYERS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8")


def _ms(tick: int | float) -> int:
    return math.floor(int(tick) * 1000.0 / 60)


def _r(x: Any, nd: int = 3) -> Any:
    return round(float(x), nd) if isinstance(x, (int, float)) and not isinstance(x, bool) else x


def reason_summary_of(text: str | None) -> str | None:
    """The model's own reason_summary, if its answer has one (FULL; LEAN never does, D-85)."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    reason = data.get("reason_summary") if isinstance(data, dict) else None
    return reason if isinstance(reason, str) and reason.strip() else None


class FeedBuilder:
    """Turns one run's messages and records into viewer records; ``take()`` returns the new ones.

    ``words_evaluator_only``: agents whose prompts hold a private goal (D-51): their model's own
    words go to the evaluator file only. ``expressions``: the expression catalog (ambient states)."""

    def __init__(self, words_evaluator_only: Iterable[str] = (), expressions: dict[str, Any] | None = None) -> None:
        self.words_evaluator_only = set(words_evaluator_only)
        self.expressions = expressions or {}
        self._obs: list[dict[str, Any]] = []
        self._eval: list[dict[str, Any]] = []
        self._sent: dict[str, dict[str, Any]] = {}
        self._tracks: dict[str, dict[str, str]] = {}      # observer -> track -> "SEEN" | "LOST"
        self._handles: dict[str, dict[str, str]] = {}     # observer -> handle -> track

    # ---- output ----
    def _add(self, audience: str, observer: str | None, lane: str, t_ms: int, data: dict[str, Any]) -> None:
        rec = {"schema_version": SCHEMA_VERSION, "audience": audience, "observer": observer, "lane": lane,
               "t_ms": max(0, int(t_ms)), "data": data}
        (self._obs if audience == "OBSERVER" else self._eval).append(rec)

    def take(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        obs, ev = self._obs, self._eval
        self._obs, self._eval = [], []
        return obs, ev

    # ---- run-level ----
    def meta(self, data: dict[str, Any]) -> None:
        self._add("OBSERVER", None, "meta", 0, data)

    def truth(self, scenario: dict[str, Any], personas: dict[str, dict[str, Any]]) -> None:
        """Evaluator truth known before the run: scenario labels and every cast member's private goal."""
        self._add("EVALUATOR", None, "truth_labels", 0, {
            "scenario_id": scenario["scenario_id"], "evaluator_only": scenario.get("evaluator_only", {}),
            "measure": scenario.get("measure", [])})
        goals = {}
        for avatar_id, entry in sorted(scenario["cast"].items()):
            persona = personas.get(entry["persona"], {})
            goals[avatar_id] = {"persona_id": entry["persona"], "private_goal": persona.get("private_goal")}
        self._add("EVALUATOR", None, "truth_goals", 0, {"goals": goals})

    def truth_tracks(self, tracks: dict[str, dict[str, str]], t_ms: int) -> None:
        for observer, per in sorted(tracks.items()):
            self._add("EVALUATOR", observer, "truth_tracks", t_ms, {"tracks": dict(sorted(per.items()))})

    # ---- what the sidecar saw ----
    def packet(self, packet: dict[str, Any]) -> None:
        observer = packet["observer_id"]
        t = int(packet["sim_time_ms"])
        pose = packet["observer_pose"]
        p = {"x": _r(pose["x"]), "y": _r(pose["y"]), "z": _r(pose["z"]), "yaw": _r(pose["yaw_rad"], 4)}
        if "head_yaw_rad" in pose:
            p["head_yaw"] = _r(pose["head_yaw_rad"], 4)
            p["head_pitch"] = _r(pose["head_pitch_rad"], 4)
        items, events = [], []
        for o in packet["observations"]:
            pos = o.get("position_estimate")
            base = {"track": o.get("track_id"), "validity": o["validity"], "bearing": _r(o.get("bearing_rad"), 4),
                    "range": _r(o.get("range_m")), "pos": {"x": _r(pos["x"]), "z": _r(pos["z"])} if pos else None}
            if o.get("validity_reason"):
                base["reason"] = o["validity_reason"]
            kind = o["kind"]
            if kind == "VISUAL_PRESENCE":
                items.append(dict(base, parts=o.get("visible_parts", []), quality=_r(o.get("quality"))))
            elif kind == "AUDIO_SPEECH":
                v = o.get("value", {})
                self._add("OBSERVER", observer, "hearing", int(o.get("observed_at_ms", t)), dict(
                    base, text=v.get("text"), channel=v.get("channel"), addressed=v.get("addressed_to_observer")))
            else:
                events.append(dict(base, kind=kind, value=o.get("value", {})))
        data: dict[str, Any] = {"pose": p, "items": items}
        if events:
            data["events"] = events
        self._add("OBSERVER", observer, "sight", t, data)
        # Tracks: a track's first sight, its loss and its return, as this observer saw them.
        known = self._tracks.setdefault(observer, {})
        for item in items:
            track, seen = item["track"], item["validity"] in ("OBSERVED", "DEGRADED")
            if not track:
                continue
            before = known.get(track)
            now = "SEEN" if seen else "LOST"
            if before != now and (before is not None or seen):
                event = "NEW" if before is None else ("BACK" if seen else "LOST")
                rec = {"event": event, "track": track}
                if event == "LOST" and item.get("reason"):
                    rec["reason"] = item["reason"]
                self._add("OBSERVER", observer, "tracks", t, rec)
                known[track] = now

    def sent(self, request: dict[str, Any], tick: int) -> None:
        self._sent[request["action_request_id"]] = request
        self._add("OBSERVER", request["agent_id"], "action", _ms(tick), {
            "request_id": request["action_request_id"], "action": request["action"], "args": request.get("args", {}),
            "based_on_tick": int(request["based_on_tick_id"])})

    def result(self, result: dict[str, Any]) -> None:
        rid = result["action_request_id"]
        agent = result["agent_id"]
        t = _ms(result["resolved_at_tick_id"])
        self._add("OBSERVER", agent, "result", t, {"request_id": rid, "accepted": bool(result["accepted"]),
                                                   "reason_code": result["reason_code"]})
        request = self._sent.get(rid)
        if request is not None and request["action"] == "EXPRESS" and result["accepted"]:
            eid = request["args"]["expression_id"]
            entry = self.expressions.get(eid, {})
            rec = {"expression_id": eid, "request_id": rid}
            ambient = (entry.get("ambient") or {}).get("state")
            if ambient:
                rec["ambient_state"] = ambient
            if entry.get("light") is not None:
                rec["light"] = entry["light"]
                rec["light_pattern"] = entry.get("light_pattern")
            self._add("OBSERVER", agent, "beacon", t, rec)

    def decision(self, record: dict[str, Any]) -> None:
        agent = record["agent_id"]
        t = _ms(record["based_on_tick_id"])
        ctx = record.get("context")
        calls, answers = [], []
        for c in record.get("model_calls", []):
            tm = c.get("timings", {})
            call = {"call_id": c["call_id"], "attempt": c["attempt"], "outcome": c["outcome"],
                    "deadline_ms": c.get("deadline_ms"), "queue_ms": tm.get("queue_ms"),
                    "prefill_ms": tm.get("prefill_ms"), "generation_ms": tm.get("generation_ms"),
                    "total_ms": tm.get("total_ms"), "prompt_tokens": c.get("prompt_tokens"),
                    "generated_tokens": c.get("generated_tokens"), "cached_tokens": c.get("cached_tokens"),
                    "error": c.get("error") is not None}
            for key in ("salvaged", "prefix_state", "other_server_busy_ms"):
                if c.get(key) is not None:
                    call[key] = c[key]
            if c.get("activity_dropped"):
                call["activity_dropped"] = {"rule": c["activity_dropped"]["rule"]}
            calls.append(call)
            answers.append({"call_id": c["call_id"], "response_text": c.get("response_text"), "error": c.get("error")})
        data: dict[str, Any] = {
            "decision_id": record["decision_id"], "tier": record["tier"], "policy": record["policy"],
            "cognition": record["cognition_level"], "triggers": record.get("triggers", []),
            "based_on_tick": int(record["based_on_tick_id"]), "activity": record.get("activity"),
            "fallback": record.get("fallback"), "action_request_ids": record.get("action_request_ids", []),
            "calls": calls,
            "context": None if ctx is None else {
                "total_tokens": ctx["total_tokens"], "budget_tokens": ctx["budget_tokens"],
                "tokenizer": ctx.get("tokenizer"), "compression_steps": ctx.get("compression_steps", []),
                "sections": [{k: s[k] for k in ("section", "tokens", "budget", "items", "cut_items")}
                             for s in ctx["sections"]]},
        }
        words = next((w for w in (reason_summary_of(a["response_text"]) for a in reversed(answers)) if w), None)
        if words is not None and agent not in self.words_evaluator_only:
            data["reason_summary"] = {"text": words, "label": "the model's own words"}
        self._add("OBSERVER", agent, "decision", t, data)
        if answers:
            ev: dict[str, Any] = {"decision_id": record["decision_id"], "answers": answers}
            if words is not None:
                ev["reason_summary"] = words
            self._add("EVALUATOR", agent, "answer", t, ev)

    def prompt(self, entry: dict[str, Any], t_ms: int) -> None:
        agent = entry["agent_id"]
        handles = entry.get("handles") or {}
        if handles:
            mine = self._handles.setdefault(agent, {})
            new = {h: tr for h, tr in handles.items() if mine.get(h) != tr}
            if new:
                mine.update(new)
                self._add("OBSERVER", agent, "handles", t_ms, {"decision_id": entry["decision_id"],
                                                                "handles": dict(sorted(handles.items()))})
        self._add("EVALUATOR", agent, "prompt", t_ms, {"decision_id": entry["decision_id"], "prompt": entry["prompt"],
                                                        "handles": dict(sorted(handles.items()))})

    def pulse(self, agent_id: str, event: dict[str, Any]) -> None:
        data = {k: v for k, v in event.items() if k not in ("agent_id",)}
        self._add("OBSERVER", agent_id, "pulse", int(event.get("at_ms", 0)), data)

    def delivery(self, agent_id: str, event: dict[str, Any]) -> None:
        data = {k: event.get(k) for k in ("event", "decision_id", "action_request_id", "action", "target", "reason")}
        self._add("OBSERVER", agent_id, "delivery", int(event.get("at_ms", 0)), data)


# ---------------------------------------------------------------------------------------------
# Run-level helpers
# ---------------------------------------------------------------------------------------------

def body_card(body: dict[str, Any]) -> dict[str, Any]:
    """What a body can perceive and do, for the capability card (scope §2.4 item 8)."""
    sensors = body.get("sensors", {})
    caps = body.get("capabilities", {})
    head = body.get("head") or {}
    return {"body_id": body["body_id"], "kind": body.get("kind"),
            "fov_deg": sensors.get("fov_deg"), "visual_range_m": sensors.get("visual_range_m"),
            "acoustic_range_m": sensors.get("acoustic_range_m"), "sensor_height_m": sensors.get("mount_height_m"),
            "neck": bool(head.get("neck", False)), "max_speed_mps": body.get("motion", {}).get("max_speed_m_s"),
            "stairs": bool(caps.get("can_use_stairs")), "ramp": bool(caps.get("can_use_ramp")),
            "gestures": len(body.get("gestures", [])), "channels": body.get("expression_channels", [])}


def meta_record(scenario: dict[str, Any], cs: Any, mode: str, cards: dict[str, str],
                body_overrides: dict[str, str] | None = None, answer_format: str | None = None) -> dict[str, Any]:
    overrides = body_overrides or {}
    bodies = {}
    for avatar_id, entry in sorted(scenario["cast"].items()):
        body = cs.items["bodies"].get(overrides.get(avatar_id, entry["body"]))
        if body is not None:
            bodies[avatar_id] = body_card(body)
    return {"scenario_id": scenario["scenario_id"], "map_id": scenario["map"], "run_mode": mode,
            "duration_ms": int(scenario["duration_ticks"]) * 1000 // int(scenario["tick_hz"]),
            "observers": sorted(scenario["cast"]), "capability_cards": dict(sorted(cards.items())),
            "bodies": bodies, "focal_answer": answer_format,
            "horizon_layers": {layer: "not built (G5)" for layer in HORIZON_LAYERS}}


def words_evaluator_only(scenario: dict[str, Any], personas: dict[str, dict[str, Any]]) -> set[str]:
    """Agents whose prompts may hold their own private goal (D-51)."""
    return {a for a, e in scenario["cast"].items() if (personas.get(e["persona"]) or {}).get("private_goal")}


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]], append: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a" if append else "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
            n += 1
    return n


def feed_from_logs(run_dir: Path, builder: FeedBuilder) -> None:
    """Feed ``builder`` with what the run's sidecar saw, in the order it saw it."""
    side = run_dir / "sidecar"
    received = _lines(side / "sidecar_received.jsonl")
    sent = _lines(side / "sidecar_sent.jsonl")
    # The sidecar handled one message at a time: replay sends and receipts in that order (by the
    # tick the sidecar had seen; a request is sent after the packet it answers, and its result comes
    # after it).
    stream: list[tuple[int, int, int, dict[str, Any]]] = []
    for i, env in enumerate(received):
        # A result can carry the tick its request was sent at: it is handled after that send.
        stream.append((env["tick_id"], 2 if env["type"] == "world.action_result" else 0, i, env))
    for i, env in enumerate(sent):
        stream.append((env["tick_id"], 1, i, env))
    stream.sort(key=lambda x: (x[0], x[1], x[2]))
    for _tick, _kind, _i, env in stream:
        if env["type"] == "world.observation":
            builder.packet(env["payload"])
        elif env["type"] == "agent.action_request":
            builder.sent(env["payload"], env["tick_id"])
        elif env["type"] == "world.action_result":
            builder.result(env["payload"])
    records = _lines(side / "decision_records.jsonl")
    for record in records:
        builder.decision(record)
    by_decision = {r["decision_id"]: r for r in records}
    for entry in _lines(side / "prompts.jsonl"):
        rec = by_decision.get(entry["decision_id"])
        builder.prompt(entry, _ms(rec["based_on_tick_id"]) if rec else 0)
    for event in _lines(run_dir / "pulse.jsonl"):
        builder.pulse(event["agent_id"], event)
    for event in _lines(side / "delivery.jsonl"):
        builder.delivery(event["agent_id"], event)


def build_run(run_dir: Path, cs: Any = None, write: bool = True) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild a run folder's viewer feed from its logs (replay), and write ``viewer/``."""
    if cs is None:
        from range_service.configs import load_and_check   # noqa: PLC0415

        cs, _ = load_and_check()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8")) \
        if (run_dir / "run_manifest.json").is_file() else None
    scenario_id = manifest["scenario_id"] if manifest else _scenario_from_journal(run_dir)
    scenario = cs.items["scenarios"][scenario_id]
    personas = cs.items["personas"]
    builder = FeedBuilder(words_evaluator_only(scenario, personas), cs.items["expressions"])
    cards = {a["avatar_id"]: a["capability_card"] for a in manifest["avatars"]} if manifest else {}
    overrides = {a["avatar_id"]: a["body_id"] for a in manifest["avatars"]} if manifest else {}
    mode = manifest["simulation"]["mode"] if manifest else "UNKNOWN"
    answer = (manifest or {}).get("resolved_settings", {}).get("focal.answer")
    builder.meta(meta_record(scenario, cs, mode, cards, overrides, answer))
    builder.truth(scenario, personas)
    feed_from_logs(run_dir, builder)
    tracks_path = run_dir / "viewer" / TRUTH_TRACKS_FILE
    if tracks_path.is_file():
        builder.truth_tracks(json.loads(tracks_path.read_text(encoding="utf-8")),
                             int(scenario["duration_ticks"]) * 1000 // int(scenario["tick_hz"]))
    obs, ev = builder.take()
    if write:
        write_jsonl(run_dir / "viewer" / OBSERVER_FILE, obs)
        write_jsonl(run_dir / "viewer" / EVALUATOR_FILE, ev)
    return obs, ev


def _scenario_from_journal(run_dir: Path) -> str:
    raise FileNotFoundError(f"{run_dir}: no run_manifest.json; cannot tell which scenario this run was")


def canonical(records: Iterable[dict[str, Any]]) -> list[str]:
    """Records as sorted JSON text: a live feed and a rebuilt one compare equal regardless of order."""
    return sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)


def compare(live: list[dict[str, Any]], replay: list[dict[str, Any]]) -> dict[str, Any]:
    a, b = canonical(live), canonical(replay)
    if a == b:
        return {"match": True, "records": len(a)}
    sa, sb = set(a), set(b)
    lanes = sorted({json.loads(x)["lane"] for x in (sa ^ sb)})
    return {"match": False, "live": len(a), "replay": len(b), "only_live": len(sa - sb), "only_replay": len(sb - sa),
            "lanes": lanes}


def observer_leaks(records: Iterable[dict[str, Any]], cast: Iterable[str], secrets: Iterable[str] = ()) -> list[str]:
    """Problems in observer-audience records: another avatar's real id, an evaluator lane, any of
    ``secrets`` (private goals, labels, prompt text), another observer's track ids."""
    cast = sorted(set(cast))
    secrets = [s for s in secrets if s]
    problems = []
    tracks_by: dict[str, set[str]] = {}
    for r in records:
        if r["audience"] != "OBSERVER":
            problems.append(f"{r['lane']}: audience {r['audience']} in the observer feed")
            continue
        if r["lane"] not in OBSERVER_LANES:
            problems.append(f"{r['lane']}: not an observer lane")
        text = json.dumps(r["data"], ensure_ascii=False)
        for s in secrets:
            if s in text:
                problems.append(f"{r['observer']} {r['lane']} at {r['t_ms']} ms holds evaluator-only text ({s[:30]}...)")
        if r["observer"] is None:
            continue
        for other in cast:
            if other != r["observer"] and _has_word(text, other):
                problems.append(f"{r['observer']} {r['lane']} at {r['t_ms']} ms names {other} by its real id")
        if r["lane"] == "sight":
            tracks_by.setdefault(r["observer"], set()).update(i["track"] for i in r["data"]["items"] if i["track"])
    for a, ta in tracks_by.items():
        for b, tb in tracks_by.items():
            if a < b and ta & tb:
                problems.append(f"{a} and {b} share track ids {sorted(ta & tb)[:2]} (D-62)")
    return problems


def _has_word(text: str, word: str) -> bool:
    import re

    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", text) is not None


class LiveFeed:
    """The live viewer feed of a watched run (D-93): the sidecar calls these as messages pass, and
    ``flush`` appends the new records to ``viewer/observer_feed.jsonl`` and
    ``viewer/evaluator_truth.jsonl``, which Godot's viewer reads as they grow. Only file appends:
    no link message, so the agent link's traffic and buffers are untouched (D-93)."""

    def __init__(self, viewer_dir: Path, builder: FeedBuilder) -> None:
        self.dir = viewer_dir
        self.builder = builder
        self.dir.mkdir(parents=True, exist_ok=True)
        self._files = {"OBSERVER": (self.dir / OBSERVER_FILE).open("w", encoding="utf-8"),
                       "EVALUATOR": (self.dir / EVALUATOR_FILE).open("w", encoding="utf-8")}
        self._pulse_done: dict[str, int] = {}
        self._delivery_done: dict[str, int] = {}
        self._decision_ticks: dict[str, int] = {}
        self.written = {"OBSERVER": 0, "EVALUATOR": 0}

    def records(self, records: list[dict[str, Any]], prompts: list[dict[str, Any]]) -> None:
        for record in records:
            self._decision_ticks[record["decision_id"]] = int(record["based_on_tick_id"])
            self.builder.decision(record)
        for entry in prompts:
            tick = self._decision_ticks.get(entry["decision_id"])
            self.builder.prompt(entry, _ms(tick) if tick is not None else 0)

    def poll_logs(self, runtimes: dict[str, Any]) -> None:
        """New pulse and delivery events of every runtime, in agent-id order."""
        for agent_id in sorted(runtimes):
            rt = runtimes[agent_id]
            log = getattr(rt, "pulse_log", [])
            for event in log[self._pulse_done.get(agent_id, 0):]:
                self.builder.pulse(agent_id, event)
            self._pulse_done[agent_id] = len(log)
            log = getattr(rt, "delivery_log", [])
            for event in log[self._delivery_done.get(agent_id, 0):]:
                self.builder.delivery(agent_id, event)
            self._delivery_done[agent_id] = len(log)

    def flush(self) -> None:
        obs, ev = self.builder.take()
        for audience, recs in (("OBSERVER", obs), ("EVALUATOR", ev)):
            if not recs:
                continue
            fh = self._files[audience]
            for r in recs:
                fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
            fh.flush()
            self.written[audience] += len(recs)

    def close(self) -> None:
        self.flush()
        for fh in self._files.values():
            fh.close()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return _lines(path)
