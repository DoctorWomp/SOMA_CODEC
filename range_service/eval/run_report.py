"""Per-run measurements for comparisons (G3d, D-69): pulse on vs off, headless vs rendered.

Evaluator only; computed after a run from its own files, never fed back to an agent:

- **frame pacing** (``frames.json``, written by Godot's FrameStats with ``--frame-stats``):
  frame-time p50/p95/p99/max and spikes, against the initial target of p95 <= 16.7 ms at 60 FPS
  (reported, never tuned to);
- **peak VRAM** sampled once a second while the run is going (``VramSampler``, nvidia-smi), not
  only after the model servers started; null with the reason where it cannot be read;
- **actions per agent**: offered (sent to the world) vs accepted, and dropped before sending
  (``sidecar/delivery.jsonl``);
- **response latency**: from speech addressed to an agent (journal SPEECH_EMITTED) to that
  agent's next action the world accepted (simulated ms; LIVE runs are real time);
- **model calls**, **timeouts** and **fallbacks** per agent (decision records);
- **glances**: accepted LOOK_AT actions;
- **conversation continuity (FN-1)**: the agent's accepted MOVE_TOs while a conversation was
  going (an exchange with someone in the last 20 s), and how many came after a closing line the
  agent said to that person.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

FRAME_TARGET_MS = 1000 / 60            # 16.7 ms: the initial target, p95 at 60 FPS (ART_DIRECTION §3.1)
SPIKE_FACTOR = 2.0                     # a spike: a frame longer than twice the target (a dropped frame or worse)
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
    spike_ms = FRAME_TARGET_MS * SPIKE_FACTOR
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


def run_report(run_dir: Path, journal: list[dict[str, Any]], agents: list[str]) -> dict[str, Any]:
    """The comparison measures for each agent the sidecar ran (see the module docstring)."""
    records = _jsonl(run_dir / "sidecar" / "decision_records.jsonl")
    delivery = _jsonl(run_dir / "sidecar" / "delivery.jsonl")
    resolved = [e for e in journal if e["kind"] == "ACTION_RESOLVED"
                and not e["payload"]["result"]["action_request_id"].startswith("tape_")]
    speech = [e for e in journal if e["kind"] == "SPEECH_EMITTED"]
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
        # Conversation continuity (FN-1), from what the world saw.
        departures = with_goodbye = 0
        for e in accepted:
            if e["payload"]["request"]["action"] != "MOVE_TO":
                continue
            t = e["sim_time_ms"]
            recent = [s for s in speech if t - CONVERSATION_WINDOW_MS <= s["sim_time_ms"] <= t
                      and ((s["payload"]["avatar_id"] == aid and s["payload"].get("addressee_id"))
                           or s["payload"].get("addressee_id") == aid)]
            if not recent:
                continue
            last = recent[-1]
            partner = last["payload"]["addressee_id"] if last["payload"]["avatar_id"] == aid else last["payload"]["avatar_id"]
            departures += 1
            mine_to_partner = [s for s in recent if s["payload"]["avatar_id"] == aid and s["payload"].get("addressee_id") == partner]
            if mine_to_partner and _CLOSING.search(mine_to_partner[-1]["payload"]["text"] or ""):
                with_goodbye += 1
        if not (mine or recs):
            continue
        out[aid] = {
            "actions": {"offered": len(mine), "accepted": len(accepted), "refused": len(mine) - len(accepted),
                        "dropped_before_send": sum(1 for d in delivery if d["agent_id"] == aid and d["event"] == "DISCARDED")},
            "response_latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95), "max": max(lat) if lat else None,
                                    "n": len(lat), "unanswered": unanswered},
            "model_calls": len(calls), "timeouts": sum(1 for c in calls if c["outcome"] == "TIMEOUT"),
            "fallbacks": fallbacks, "decisions": len(recs),
            "glances_accepted": sum(1 for e in accepted if e["payload"]["request"]["action"] == "LOOK_AT"),
            "fn1": {"departures_mid_conversation": departures, "with_goodbye_first": with_goodbye,
                    "without_goodbye": departures - with_goodbye},
        }
    return out
