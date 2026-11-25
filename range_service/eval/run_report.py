"""Per-run measurements for comparisons (G3d, D-69): pulse on vs off, headless vs rendered.

Evaluator only; computed after a run from its own files, never fed back to an agent:

- **frame pacing** (``frames.json``, written by Godot's FrameStats with ``--frame-stats``):
  frame-time p50/p95/p99/max and spikes, against the target of p95 <= 20 ms at the 60 FPS cap
  (D-109, proposed; D-69's 16.7 ms was the frame period itself), spikes (> 33.3 ms) always reported;
- **peak VRAM** sampled once a second while the run is going (``VramSampler``, nvidia-smi), not
  only after the model servers started; null with the reason where it cannot be read;
- **actions per agent**: offered (sent to the world) vs accepted, and dropped before sending
  (``sidecar/delivery.jsonl``);
- **response latency**: from speech addressed to an agent (journal SPEECH_EMITTED) to that
  agent's next action the world accepted (simulated ms; LIVE runs are real time);
- **model calls**, **timeouts** and **fallbacks** per agent (decision records);
- **glances**: accepted LOOK_AT actions;
- **conversation continuity (FN-1)**: the agent's accepted MOVE_TOs that took it away from a
  conversation that was still open, and how many came after a closing line its partner could hear.
  Since G4b (D-108) this applies the runtime's FN-1 definition (D-61, D-66) to what the world saw:
  open = an exchange with the partner in the last 20 s, the partner within 3.5 m (positions from
  each avatar's own packets), and no farewell from the partner since; away = a destination farther
  from the partner (by more than 0.5 m) or another target; audible goodbye = a closing line
  addressed to the partner, or unaddressed LOCAL speech within 3.5 m of it. Until G4b it counted
  every MOVE_TO within 20 s of any exchange (also after the partner's own "Bye!", or toward the
  partner), so it disagreed with the pulse log's FN1_VIOLATION count.
"""

from __future__ import annotations

from collections import Counter

import asyncio
import json
import math
import re
from pathlib import Path
from typing import Any

FRAME_PERIOD_MS = 1000 / 60            # 16.7 ms: one frame at the 60 FPS cap (ART_DIRECTION §3)
# G4b (D-109, proposed): p95 <= 20 ms at the 60 FPS cap. D-69's p95 <= 16.7 ms could not be met: at
# a 60 FPS cap 16.7 ms is the frame period itself, so ordinary jitter put p95 just above it.
FRAME_TARGET_MS = 20.0
SPIKE_FACTOR = 2.0                     # a spike: a frame longer than two frame periods (33.3 ms, a dropped frame or worse)
CONVERSATION_WINDOW_MS = 20_000        # configs/pulse.yaml conversation.silence_limit_s
UNANSWERED_AFTER_MS = 10_000


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    return round(vals[min(len(vals) - 1, int(q * (len(vals) - 1) + 0.5))], 2)


def frame_summary(path: Path) -> dict[str, Any]:
    """Frame pacing from Godot's frames.json (the first second is skipped: loading, not pacing)."""
    if not path.is_file():
        return {"available": False, "reason": "no frames.json (run without --frame-stats, or Godot did not finish)"}
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = [float(f) for f in data.get("frame_ms", [])]
    skip, total = 0, 0.0
    for f in frames:
        if total >= 1000:
            break
        total += f
        skip += 1
    body = frames[skip:]
    spike_ms = FRAME_PERIOD_MS * SPIKE_FACTOR
    p95 = _pct(body, 0.95)
    headless = data.get("display_server") == "headless"
    return {
        "available": True, "frames": len(body), "skipped_start_frames": skip,
        "p50_ms": _pct(body, 0.50), "p95_ms": p95, "p99_ms": _pct(body, 0.99),
        "max_ms": round(max(body), 2) if body else None,
        "mean_fps": round(1000 * len(body) / sum(body), 1) if body and sum(body) > 0 else None,
        "spikes": sum(1 for f in body if f > spike_ms), "spike_threshold_ms": round(spike_ms, 1),
        "target_p95_ms": round(FRAME_TARGET_MS, 1),
        # Only a rendered run can meet or miss the frame target; headless frames are the simulation loop.
        "meets_target": (p95 is not None and p95 <= FRAME_TARGET_MS + 0.05) if body and not headless else None,
        "display_server": data.get("display_server"), "rendering_method": data.get("rendering_method"),
        "window_size": data.get("window_size"), "max_fps": data.get("max_fps"), "vsync_mode": data.get("vsync_mode"),
        "godot_video_mem_peak_mib": data.get("godot_video_mem_peak_mib"),
        # G4a: the layer viewer's state during the run (closed, open), seconds open, panel redraws.
        "viewer_mode": data.get("viewer_mode"), "viewer_open_s": data.get("viewer_open_s"),
        "viewer_draws": data.get("viewer_draws"),
        "note": "headless: no rendering, frame times show the simulation loop only" if headless else None,
    }


class VramSampler:
    """Peak GPU memory in use, sampled every ``every_s`` while a run is going (nvidia-smi)."""

    def __init__(self, every_s: float = 1.0) -> None:
        self.every_s = every_s
        self.samples: list[int] = []
        self.reason: str | None = None
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        from range_service.eval.bakeoff import _smi, gpu_memory_used_mib   # noqa: PLC0415

        if _smi() is None:
            self.reason = "nvidia-smi not found (no NVIDIA GPU or driver)"
            return
        while True:
            value = await asyncio.to_thread(gpu_memory_used_mib)
            if value is not None:
                self.samples.append(value)
            await asyncio.sleep(self.every_s)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    def summary(self) -> dict[str, Any]:
        if not self.samples:
            return {"peak_mib": None, "samples": 0, "reason": self.reason or "no sample could be read"}
        return {"peak_mib": max(self.samples), "first_mib": self.samples[0], "samples": len(self.samples),
                "every_s": self.every_s, "what": "total GPU memory in use (all processes: Godot and both model servers)"}


_CLOSING = re.compile(r"\b(bye|goodbye|see you|excuse me|sorry|i need to go|i have to go|be right back|"
                      r"back in a moment|one moment|i'll be back|i will be back|take care|enjoy)\b", re.IGNORECASE)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


CONVERSATION_RANGE_M = 3.5             # configs/pulse.yaml conversation.range_m (D-66 earshot)


def avatar_poses(journal: list[dict[str, Any]]) -> dict[str, list[tuple[int, float, float]]]:
    """Each avatar's own position over time, from its observation packets: {id: [(ms, x, z)]}."""
    out: dict[str, list[tuple[int, float, float]]] = {}
    for e in journal:
        if e["kind"] == "OBSERVATION_DELIVERED":
            p = e["payload"]
            out.setdefault(p["observer_id"], []).append((p["sim_time_ms"], p["observer_pose"]["x"], p["observer_pose"]["z"]))
    return out


def _at(poses: list[tuple[int, float, float]], t: int) -> tuple[float, float] | None:
    best = None
    for ms, x, z in poses:
        if ms > t:
            break
        best = (x, z)
    return best


def fn1_departures(aid: str, accepted: list[dict[str, Any]], speech: list[dict[str, Any]],
                   poses: dict[str, list[tuple[int, float, float]]], tracks: dict[str, str]) -> tuple[int, int]:
    """(departures from an open conversation, of which after a goodbye the partner could hear)."""
    from range_service.agents.policy_demo import is_farewell   # noqa: PLC0415
    from range_service.agents.pulse import is_closing   # noqa: PLC0415

    departures = with_goodbye = 0
    for e in accepted:
        req = e["payload"]["request"]
        if req["action"] != "MOVE_TO":
            continue
        t = e["sim_time_ms"]
        exchanges = [s for s in speech if t - CONVERSATION_WINDOW_MS <= s["sim_time_ms"] <= t
                     and ((s["payload"]["avatar_id"] == aid and s["payload"].get("addressee_id"))
                          or s["payload"].get("addressee_id") == aid)]
        if not exchanges:
            continue
        last = exchanges[-1]
        partner = last["payload"]["addressee_id"] if last["payload"]["avatar_id"] == aid else last["payload"]["avatar_id"]
        if any(s["payload"]["avatar_id"] == partner and s["payload"].get("addressee_id") == aid
               and is_farewell(s["payload"].get("text") or "") for s in exchanges):
            continue                                       # the partner said goodbye: the conversation is closing
        me, them = _at(poses.get(aid, []), t), _at(poses.get(partner, []), t)
        if me is None or them is None or math.hypot(me[0] - them[0], me[1] - them[1]) > CONVERSATION_RANGE_M:
            continue                                       # not in a conversation any more (out of range)
        args = req.get("args") or {}
        if args.get("target_id") is not None:
            if tracks.get(args["target_id"]) == partner:
                continue                                   # toward the partner
        elif args.get("destination") is not None:
            d = args["destination"]
            if math.hypot(d["x"] - them[0], d["z"] - them[1]) <= math.hypot(me[0] - them[0], me[1] - them[1]) + 0.5:
                continue                                   # not away from the partner
        departures += 1
        for s in speech:
            if s["payload"]["avatar_id"] != aid or s["sim_time_ms"] > t or s["sim_time_ms"] < last["sim_time_ms"] - 1:
                continue
            if not is_closing(s["payload"].get("text") or ""):
                continue
            to = s["payload"].get("addressee_id")
            here = _at(poses.get(aid, []), s["sim_time_ms"])
            there = _at(poses.get(partner, []), s["sim_time_ms"])
            near = here is not None and there is not None and math.hypot(here[0] - there[0], here[1] - there[1]) <= CONVERSATION_RANGE_M
            if to == partner or (to is None and s["payload"].get("channel", "LOCAL") == "LOCAL" and near):
                with_goodbye += 1
                break
    return departures, with_goodbye


def run_report(run_dir: Path, journal: list[dict[str, Any]], agents: list[str]) -> dict[str, Any]:
    """The comparison measures for each agent the sidecar ran (see the module docstring)."""
    records = _jsonl(run_dir / "sidecar" / "decision_records.jsonl")
    delivery = _jsonl(run_dir / "sidecar" / "delivery.jsonl")
    resolved = [e for e in journal if e["kind"] == "ACTION_RESOLVED"
                and not e["payload"]["result"]["action_request_id"].startswith("tape_")]
    speech = [e for e in journal if e["kind"] == "SPEECH_EMITTED"]
    poses = avatar_poses(journal)
    tracks_path = run_dir / "viewer" / "truth_tracks.json"   # evaluator only: which avatar a track was
    tracks = json.loads(tracks_path.read_text(encoding="utf-8")) if tracks_path.is_file() else {}
    out: dict[str, Any] = {}
    for aid in agents:
        mine = [e for e in resolved if e["payload"]["result"]["agent_id"] == aid]
        accepted = [e for e in mine if e["payload"]["result"]["accepted"]]
        recs = [r for r in records if r["agent_id"] == aid]
        calls = [c for r in recs for c in r["model_calls"]]
        fallbacks: dict[str, int] = {}
        for r in recs:
            if r["fallback"]:
                fallbacks[r["fallback"]["reason"]] = fallbacks.get(r["fallback"]["reason"], 0) + 1
        # Response latency: speech to this agent -> its next accepted action.
        lat, unanswered = [], 0
        times = sorted(e["sim_time_ms"] for e in accepted)
        for s in speech:
            if s["payload"].get("addressee_id") != aid or s["payload"]["avatar_id"] == aid:
                continue
            nxt = next((t for t in times if t >= s["sim_time_ms"]), None)
            if nxt is None or nxt - s["sim_time_ms"] > UNANSWERED_AFTER_MS:
                unanswered += 1
            else:
                lat.append(nxt - s["sim_time_ms"])
        # Conversation continuity (FN-1), from what the world saw (D-108: the runtime's definition).
        departures, with_goodbye = fn1_departures(aid, accepted, speech, poses, tracks.get(aid, {}))
        if not (mine or recs):
            continue
        out[aid] = {
            "actions": {"offered": len(mine), "accepted": len(accepted), "refused": len(mine) - len(accepted),
                        "dropped_before_send": sum(1 for d in delivery if d["agent_id"] == aid and d["event"] == "DISCARDED"),
                        "dropped_before_send_by_reason": dict(sorted(Counter(
                            str(d.get("reason") or "UNKNOWN") for d in delivery
                            if d["agent_id"] == aid and d["event"] == "DISCARDED").items()))},
            "response_latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95), "max": max(lat) if lat else None,
                                    "n": len(lat), "unanswered": unanswered},
            "model_calls": len(calls), "timeouts": sum(1 for c in calls if c["outcome"] == "TIMEOUT"),
            "fallbacks": fallbacks, "decisions": len(recs),
            "glances_accepted": sum(1 for e in accepted if e["payload"]["request"]["action"] == "LOOK_AT"),
            "fn1": {"departures_mid_conversation": departures, "with_goodbye_first": with_goodbye,
                    "without_goodbye": departures - with_goodbye},
        }
    return out
