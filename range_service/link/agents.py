"""Scripted agents for the sidecar (no LLM yet; G3 adds model-driven agents).

Each agent only ever sees its own observation packets and keeps its own memory (T17): there is
no shared state between agents, and nothing from world truth reaches them.
"""

from __future__ import annotations

from typing import Any

from range_service.comms import disclosure

GREETING_GESTURES = ("WAVE", "SMALL_WAVE", "RAISED_HAND")


class ScriptedAgent:
    """Base agent: remembers speech addressed to it (never overheard speech) and does nothing."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.memory: list[dict[str, Any]] = []
        self.results: dict[str, dict[str, Any]] = {}
        self.latest_packet: dict[str, Any] | None = None
        self._request_seq = 0
        self._memory_seq = 0

    def request(self, tick: int, action: str, args: dict[str, Any], label: str = "") -> dict[str, Any]:
        self._request_seq += 1
        tag = f"_{label}" if label else ""
        return {
            "schema_version": "1.0",
            "action_request_id": f"act_{self.agent_id}{tag}_{self._request_seq:04d}",
            "agent_id": self.agent_id,
            "based_on_tick_id": tick,
            "action": action,
            "args": args,
        }

    def on_observation(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        self.latest_packet = packet
        for item in packet["observations"]:
            if item["kind"] == "AUDIO_SPEECH":
                self._memory_seq += 1
                memory = disclosure.remember_speech(self.agent_id, item, packet, self._memory_seq)
                if memory is not None:
                    self.memory.append(memory)
        return []

    def on_result(self, result: dict[str, Any]) -> None:
        self.results[result["action_request_id"]] = result


class GreeterAgent(ScriptedAgent):
    """Waves back and says hello, once, to anyone it sees waving toward it."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(agent_id)
        self.greeted: set[str] = set()

    def on_observation(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        out = super().on_observation(packet)
        tick = packet["based_on_tick_id"]
        for item in packet["observations"]:
            if item["kind"] != "VISUAL_GESTURE" or item["track_id"] is None or item["track_id"] in self.greeted:
                continue
            if item["value"]["gesture"] in GREETING_GESTURES and item["value"].get("direction") == "TOWARD_OBSERVER":
                self.greeted.add(item["track_id"])
                out.append(self.request(tick, "GESTURE", {"gesture": "WAVE", "target_id": item["track_id"]}, "greet"))
                out.append(self.request(tick, "SPEAK", {"channel": "LOCAL", "text": "Hello!",
                                                        "addressee_id": item["track_id"]}, "greet"))
        return out


class ProbeAgent(GreeterAgent):
    """A greeter that, once the run is under way, also sends requests the host must refuse,
    each tagged so tests can find its result. Some are deliberately invalid (``raw``)."""

    START_TICK = 480   # later than the stale window (390 ticks, D-60), so the stale probe can be old enough

    def __init__(self, agent_id: str) -> None:
        super().__init__(agent_id)
        self.probed = False
        self.raw_ids: set[str] = set()

    def on_observation(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        out = super().on_observation(packet)
        tick = packet["based_on_tick_id"]
        if self.probed or tick < self.START_TICK:
            return out
        self.probed = True
        tracks = [i["track_id"] for i in packet["observations"]
                  if i["kind"] == "VISUAL_PRESENCE" and i["validity"] in ("OBSERVED", "DEGRADED")]
        out.append(self.request(tick - 450, "GESTURE", {"gesture": "NOD"}, "stale"))
        invalid = self.request(tick, "FLY", {"altitude_m": 3}, "invalid")
        self.raw_ids.add(invalid["action_request_id"])
        out.append(invalid)
        out.append(self.request(tick, "SPEAK", {"channel": "PA", "text": "Attention, please."}, "pa"))
        out.append(self.request(tick, "SPEAK", {"channel": "GROUP", "text": "Hi all.", "group_id": "grp_999999"}, "group"))
        if tracks:
            out.append(self.request(tick, "SPEAK", {"channel": "LOCAL", "text": "Your table is ready.",
                                                    "addressee_id": tracks[0], "disclosure_scope": "ONE_TO_ONE"}, "privacy"))
        out.append(self.request(tick, "MOVE_TO", {"target_id": "anon_doesnotexist"}, "unknowntarget"))
        not_mine = self.request(tick, "NO_OP", {}, "notmine")
        not_mine["agent_id"] = "visitor"
        out.append(not_mine)
        out.append(self.request(tick, "GESTURE", {"gesture": "NOD"}, "valid"))
        for _ in range(12):
            out.append(self.request(tick, "NO_OP", {}, "burst"))
        return out


SCRIPTS = {"quiet": ScriptedAgent, "greeter": GreeterAgent, "probe": ProbeAgent}
