"""Promise situations for the bake-off prompt set v2 (G3c-1, D-59).

prompts_v1 had only 4 prompts that called for keeping a promise, too few to score. These are
built through the real runtime and context assembler (nothing hand-written): Robot R talks with
one visitor while another waits, promises to help the waiting one, the first conversation ends,
and then the waiting visitor waves, asks, or just stands there. Four situations in each robot
body. Each item records who the promise was made to (``reference.promised_to``), so scoring can
check both the ``fulfills_commitment`` flag and the behavior (addressing, facing, approaching or
gesturing at that person).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from range_service import expressions as expression_rules
from range_service.agents.context import OUTPUT_CAPS
from range_service.agents.factory import public_persona, setting_lines
from range_service.agents.runtime import AgentRuntime
from range_service.configs import ConfigSet

PROMISED, OTHER, BYSTANDER = "anon_pr0m1sed00", "anon_0therv1s1t", "anon_bystand3r0"
ROBOT_POSE = {"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0}

SITUATIONS = {
    "waves": "the waiting visitor waves again",
    "asks": "the waiting visitor asks for help",
    "waits": "the waiting visitor just stands there",
    "bystander": "the waiting visitor stands there while someone else walks past",
}


class _Packets:
    """Minimal observation packets for one observer (same shapes as the world's)."""

    def __init__(self, observer: str) -> None:
        self.observer, self.tick, self.n, self.items = observer, 60, 0, []

    def _item(self, kind: str, track: str, x: float, z: float, event: str | None) -> dict[str, Any]:
        self.n += 1
        ms = self.tick * 1000 // 60
        return {"observation_id": f"obs_{self.observer}_{self.n:06d}", "event_id": event, "kind": kind,
                "track_id": track, "source_entity_id": None, "position_estimate": {"x": x, "y": 0.0, "z": z},
                "bearing_rad": 0.0, "range_m": round(math.hypot(x - ROBOT_POSE["x"], z - ROBOT_POSE["z"]), 3),
                "value": {}, "observed_at_ms": ms, "expires_at_ms": ms + 1000, "validity": "OBSERVED",
                "quality": 0.9, "provenance": "promptset_v2"}

    def see(self, track: str, x: float, z: float) -> "_Packets":
        self.items.append(self._item("VISUAL_PRESENCE", track, x, z, None))
        return self

    def hear(self, track: str, x: float, z: float, text: str) -> "_Packets":
        item = self._item("AUDIO_SPEECH", track, x, z, f"evt_say_{self.tick}_{self.n}")
        item["value"] = {"channel": "LOCAL", "text": text, "addressed_to_observer": True}
        self.items.append(item)
        return self

    def wave(self, track: str, x: float, z: float) -> "_Packets":
        item = self._item("VISUAL_GESTURE", track, x, z, f"evt_wave_{self.tick}_{self.n}")
        item["value"] = {"gesture": "SMALL_WAVE", "direction": "TOWARD_OBSERVER"}
        self.items.append(item)
        return self

    def packet(self, advance: int = 60) -> dict[str, Any]:
        p = {"schema_version": "1.0", "observer_id": self.observer, "based_on_tick_id": self.tick,
             "sim_time_ms": self.tick * 1000 // 60, "coordinate_frame": "world_meters_xyz",
             "observer_pose": dict(ROBOT_POSE), "observations": self.items}
        self.items = []
        self.tick += advance
        return p


def _step(rt: AgentRuntime, packet: dict[str, Any]):
    job = rt.observe(packet)
    if job is not None:
        rt.decide_now(job)
    return job


def promise_items(cs: ConfigSet, bodies: tuple[str, ...]) -> list[dict[str, Any]]:
    persona = public_persona(cs.items["personas"]["robot_r"])
    directive = cs.items["directives"]["expo_assistant"]["directive"]
    setting = setting_lines(cs.items["maps"]["sandbox_flats"])
    catalog = cs.items["expressions"]
    items = []
    for body_id in bodies:
        body = cs.items["bodies"][body_id]
        available = sorted(expression_rules.available(body, catalog))
        for n, (situation, about) in enumerate(SITUATIONS.items()):
            rt = AgentRuntime("robot_r", persona=persona, body=body, directive=directive, expressions=available,
                              setting=setting, task="Answer visitors' questions in the sandbox.", focal=True,
                              controller="LLM_AGENT",
                              expression_gestures={k: e["gesture"] for k, e in catalog.items() if "gesture" in e})
            px, pz = 15.0 + 1.5 + n * 0.8, 10.0 - 1.5 - n * 0.5        # the waiting visitor, 2-5 m away
            s = _Packets("robot_r")
            _step(rt, s.see(OTHER, 15.0, 8.8).see(PROMISED, px, pz)
                  .hear(OTHER, 15.0, 8.8, "Hi! Where is the demo?").packet())
            rt.memory.commit("Help them after the current conversation.", PROMISED, now_ms=s.tick * 1000 // 60)
            _step(rt, s.see(OTHER, 15.0, 8.8).see(PROMISED, px, pz).hear(OTHER, 15.0, 8.8, "Great, thanks. Bye!").packet())
            s.see(PROMISED, px, pz)
            if situation == "waves":
                s.wave(PROMISED, px, pz)
            elif situation == "asks":
                s.hear(PROMISED, px, pz, "Hello, could you help me now?")
            elif situation == "bystander":
                s.see(BYSTANDER, 12.0, 12.5)
            job = rt.observe(s.packet())
            if job is None or job.assembled is None:
                raise RuntimeError(f"no decision in the promise situation {situation!r} ({body_id})")
            prompt = job.assembled.prompt
            demo = rt.decide_now(job)
            items.append({
                "item_id": f"promise_{body_id}_{situation}", "scenario": "PROMISE_SITUATIONS", "role": "ROBOT_R",
                "agent_id": "robot_r", "tier": job.tier, "triggers": job.triggers, "body_id": body_id,
                "allowed_actions": persona["allowed_actions"], "gestures": body["gestures"], "expressions": available,
                "max_tokens": OUTPUT_CAPS.get(job.tier, 120), "based_on_tick_id": job.tick, "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "reference": {"situation": about, "promise_due": True, "promised_to": [PROMISED],
                              "demo_actions": [{"action": r["action"], "args": r["args"]} for r in demo],
                              "demo_fulfilled": any(p.fulfills for p in (job.proposals or []))},
            })
    return items
