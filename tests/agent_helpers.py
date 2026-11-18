"""Synthetic observation packets for agent-runtime tests (G3a). Every packet they produce is
checked against contracts/observation.schema.json by tests/test_agent_runtime.py."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from range_service.agents.factory import build_runtimes, public_persona
from range_service.agents.gateway import ModelGateway
from range_service.agents.runtime import AgentRuntime
from range_service.configs import load_and_check

CONFIGS, _PROBLEMS = load_and_check()
assert not _PROBLEMS, _PROBLEMS


def robot(agent_id: str = "robot_r", body: str = "wheeled_humanoid", gateway: ModelGateway | None = None,
          controller: str = "LLM_AGENT", task_goal: dict | None = None) -> AgentRuntime:
    from range_service import expressions as expression_rules
    from range_service.agents.factory import setting_lines

    b = CONFIGS.items["bodies"][body]
    persona = public_persona(CONFIGS.items["personas"]["robot_r"])
    return AgentRuntime(agent_id, persona=persona, body=b, directive=CONFIGS.items["directives"]["expo_assistant"]["directive"],
                        expressions=expression_rules.available(b, CONFIGS.items["expressions"]),
                        setting=setting_lines(CONFIGS.items["maps"]["sandbox_flats"]), task="Answer visitors' questions.",
                        task_goal=task_goal, focal=True, controller=controller, gateway=gateway,
                        expression_gestures={eid: e["gesture"] for eid, e in CONFIGS.items["expressions"].items()
                                             if "gesture" in e})


def scenario_runtimes(scenario_id: str, gateway: ModelGateway | None = None) -> dict[str, AgentRuntime]:
    return build_runtimes(CONFIGS.items["scenarios"][scenario_id], CONFIGS, gateway=gateway)


def accept(rt: AgentRuntime, requests: list[dict[str, Any]], tick: int | None = None) -> list[dict[str, Any]]:
    """Play the world's action gate: accept every request (G3d, D-64: memory changes apply on acceptance)."""
    for r in requests:
        rt.on_result({"schema_version": "1.0", "action_request_id": r["action_request_id"], "agent_id": rt.agent_id,
                      "accepted": True, "executed": True, "reason_code": "OK", "resulting_event_ids": [],
                      "resolved_at_tick_id": tick if tick is not None else r["based_on_tick_id"] + 1})
    return requests


def refuse(rt: AgentRuntime, request: dict[str, Any], reason: str = "TARGET_UNKNOWN") -> None:
    rt.on_result({"schema_version": "1.0", "action_request_id": request["action_request_id"], "agent_id": rt.agent_id,
                  "accepted": False, "executed": False, "reason_code": reason, "resulting_event_ids": [],
                  "resolved_at_tick_id": request["based_on_tick_id"] + 1})


@dataclass
class Scene:
    """A tiny scripted world seen by one observer: call the item builders, then ``packet()``."""

    observer: str = "robot_r"
    tick: int = 60
    pose: dict[str, float] = field(default_factory=lambda: {"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    _n: int = 0
    _items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ms(self) -> int:
        return self.tick * 1000 // 60

    def _id(self) -> int:
        self._n += 1
        return self._n

    def _base(self, kind: str, track: str | None, x: float | None, z: float | None, event_id: str | None) -> dict[str, Any]:
        n = self._id()
        located = x is not None and z is not None
        rng = math.hypot(x - self.pose["x"], z - self.pose["z"]) if located else None
        return {"observation_id": f"obs_{self.observer}_{n:06d}"[:64], "event_id": event_id, "kind": kind,
                "track_id": track, "source_entity_id": None,
                "position_estimate": {"x": x, "y": 0.0, "z": z} if located else None,
                "bearing_rad": 0.0 if located else None, "range_m": round(rng, 3) if rng is not None else None,
                "value": {}, "observed_at_ms": self.ms, "expires_at_ms": self.ms + 1000, "validity": "OBSERVED",
                "quality": 0.9, "provenance": "synthetic_test_v1"}

    def see(self, track: str, x: float, z: float, validity: str = "OBSERVED") -> "Scene":
        item = self._base("VISUAL_PRESENCE", track, x, z, None)
        item["validity"] = validity
        if validity != "OBSERVED":
            item["quality"] = None
            item["validity_reason"] = "OCCLUDED_SINCE_LAST_SEEN" if validity == "OCCLUDED" else "PARTLY_OCCLUDED"
        self._items.append(item)
        return self

    def hear(self, track: str | None, text: str, addressed: bool | None = True, x: float = 15.0, z: float = 8.5,
             event_id: str | None = None) -> "Scene":
        item = self._base("AUDIO_SPEECH", track, x if track else None, z if track else None,
                          event_id or f"evt_say_{self.tick}_{self._n}")
        item["value"] = {"channel": "LOCAL", "text": text, "addressed_to_observer": addressed}
        if track is None:
            item["validity"] = "UNKNOWN_SOURCE"
            item["bearing_rad"] = 0.5
        self._items.append(item)
        return self

    def wave(self, track: str, x: float, z: float, gesture: str = "SMALL_WAVE", toward: bool = True,
             event_id: str | None = None) -> "Scene":
        item = self._base("VISUAL_GESTURE", track, x, z, event_id or f"evt_wave_{self.tick}_{self._n}")
        item["value"] = {"gesture": gesture, "direction": "TOWARD_OBSERVER" if toward else "AWAY_FROM_OBSERVER"}
        self._items.append(item)
        return self

    def packet(self, advance: int = 6) -> dict[str, Any]:
        p = {"schema_version": "1.0", "observer_id": self.observer, "based_on_tick_id": self.tick,
             "sim_time_ms": self.ms, "coordinate_frame": "world_meters_xyz", "observer_pose": dict(self.pose),
             "observations": self._items}
        self._items = []
        self.tick += advance
        return p
