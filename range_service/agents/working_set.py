"""The Working Set and Trail buffer: what an agent currently perceives (CONTEXT_MEMORY_STRATEGY §3, §5).

Built only from the agent's own observation packets. Compression happens here, before any
prompt is assembled:

- **Step 1, deduplicate and delta:** a track standing still is one entry with "since −Ns", not
  one per sample. Positions are kept to 0.5 m.
- **Step 2, expire by modality:** gestures after 30 s, expressions after 15 s, unplaced voices
  after 20 s, lost tracks 10 s after the host stops reporting them. An ``UNKNOWN`` marker stays
  while the thing is still unknown.

Overheard speech (addressed to someone else) is noted only as "speaking", never with its words
(D-12: overheard is not told or acted on).

G4b (D-100, D-101): what the Director can plant reaches an agent only through its senses, and
always as **untrusted text** (D-09): a sign or note it can read (SIGN_TEXT; kept while it can read
it and SIGN_TTL_MS after), a PA announcement (spoken to everyone in coverage, so its words are kept,
labelled as an announcement), and a sound it hears (AUDIO_SOUND: class and level, a bearing).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

GESTURE_TTL_MS = 30_000
EXPRESSION_TTL_MS = 15_000
VOICE_TTL_MS = 20_000
LOST_TRACK_TTL_MS = 10_000
SIGN_TTL_MS = 30_000            # G4b: a sign stays in mind this long after it was last readable
SOUND_TTL_MS = 10_000           # G4b: a sound this long after it was last heard
CONVERSATION_KEEP = 24          # turns kept in the Working Set; older ones live on as episode cards
PLACE_GRID_M = 0.5
GREETING_GESTURES = frozenset({"WAVE", "SMALL_WAVE", "RAISED_HAND", "BECKON"})


def _q(v: float) -> float:
    return round(round(v / PLACE_GRID_M) * PLACE_GRID_M, 1)


@dataclass
class TrackState:
    track_id: str
    first_seen_ms: int
    last_seen_ms: int
    x: float | None = None
    z: float | None = None
    place_since_ms: int = 0
    range_m: float | None = None
    validity: str = "OBSERVED"
    validity_reason: str | None = None
    speaking_ms: int | None = None                       # last time heard speaking to someone else
    gestures: list[dict[str, Any]] = field(default_factory=list)
    expression: dict[str, Any] | None = None
    left_ms: int | None = None                           # when the host stopped reporting it


@dataclass
class Turn:
    at_ms: int
    speaker: str            # "me", a track id, or "unknown"
    text: str
    untrusted: bool
    to: str | None = None   # who the agent addressed (for its own turns)


@dataclass
class Perceived:
    """What changed in one packet, for the runtime's triggers."""

    new_tracks: list[str] = field(default_factory=list)
    lost_tracks: list[str] = field(default_factory=list)
    addressed: list[dict[str, Any]] = field(default_factory=list)       # speech items addressed to the agent
    greetings: list[dict[str, Any]] = field(default_factory=list)       # gesture items directed at the agent
    expressions: list[dict[str, Any]] = field(default_factory=list)
    invites: list[dict[str, Any]] = field(default_factory=list)
    heard: list[dict[str, Any]] = field(default_factory=list)          # speech not addressed to it (G3c-2): words not kept
    signs: list[dict[str, Any]] = field(default_factory=list)          # G4b: text it could read for the first time
    announcements: list[dict[str, Any]] = field(default_factory=list)  # G4b: PA announcements heard


@dataclass
class WorkingSet:
    agent_id: str
    tracks: dict[str, TrackState] = field(default_factory=dict)
    voices: list[dict[str, Any]] = field(default_factory=list)     # unplaced voices: {"at_ms", "bearing"}
    signs: dict[str, dict[str, Any]] = field(default_factory=dict)   # G4b: event id -> {"text", "x", "z", "range_m", "first_ms", "last_ms"}
    sounds: dict[str, dict[str, Any]] = field(default_factory=dict)  # G4b: event id -> {"sound_class", "level_db", "bearing", ...}
    turns: list[Turn] = field(default_factory=list)
    pose: dict[str, float] | None = None
    now_ms: int = 0
    tick: int = 0
    expired_count: int = 0
    _seen_events: set[str] = field(default_factory=set)

    def update(self, packet: dict[str, Any]) -> Perceived:
        self.now_ms = packet["sim_time_ms"]
        self.tick = packet["based_on_tick_id"]
        self.pose = packet["observer_pose"]
        out = Perceived()
        present: set[str] = set()
        for item in packet["observations"]:
            kind = item["kind"]
            track_id = item.get("track_id")
            if kind == "VISUAL_PRESENCE" and track_id:
                present.add(track_id)
                self._presence(item, out)
            elif kind == "VISUAL_GESTURE" and track_id:
                self._gesture(item, out)
            elif kind == "VISUAL_EXPRESSION" and track_id:
                state = self.tracks.get(track_id)
                if state is not None:
                    state.expression = {"at_ms": item["observed_at_ms"], **item["value"]}
                if self._first(item):
                    out.expressions.append(item)
            elif kind == "AUDIO_SPEECH":
                self._speech(item, out)
            elif kind == "GROUP_INVITE" and self._first(item):
                out.invites.append(item)
            elif kind == "SIGN_TEXT":
                self._sign(item, out)
            elif kind == "AUDIO_SOUND":
                self._sound(item)
        for track_id, state in self.tracks.items():
            if track_id not in present and state.left_ms is None:
                state.left_ms = self.now_ms
                out.lost_tracks.append(track_id)
        self._expire()
        return out

    def _first(self, item: dict[str, Any]) -> bool:
        key = item.get("event_id") or item["observation_id"]
        if key in self._seen_events:
            return False
        self._seen_events.add(key)
        return True

    def _presence(self, item: dict[str, Any], out: Perceived) -> None:
        track_id = item["track_id"]
        state = self.tracks.get(track_id)
        if state is None or state.left_ms is not None:
            state = TrackState(track_id, self.now_ms, self.now_ms, place_since_ms=self.now_ms)
            self.tracks[track_id] = state
            out.new_tracks.append(track_id)
        pos = item.get("position_estimate")
        if pos is not None:
            x, z = _q(pos["x"]), _q(pos["z"])
            if (x, z) != (state.x, state.z):
                state.x, state.z, state.place_since_ms = x, z, self.now_ms
        state.validity = item["validity"]
        state.validity_reason = item.get("validity_reason")
        state.range_m = item.get("range_m")
        if item["validity"] in ("OBSERVED", "DEGRADED"):
            state.last_seen_ms = self.now_ms

    def _gesture(self, item: dict[str, Any], out: Perceived) -> None:
        if not self._first(item):
            return
        value = item["value"]
        state = self.tracks.get(item["track_id"])
        if state is not None:
            state.gestures.append({"at_ms": item["observed_at_ms"], "gesture": value["gesture"],
                                   "direction": value.get("direction", "UNKNOWN")})
        if value["gesture"] in GREETING_GESTURES and value.get("direction") == "TOWARD_OBSERVER":
            out.greetings.append(item)

    def _sign(self, item: dict[str, Any], out: Perceived) -> None:
        key = item.get("event_id") or item["observation_id"]
        pos = item.get("position_estimate") or {}
        state = self.signs.get(key)
        if state is None:
            state = {"text": item["value"]["text"], "first_ms": self.now_ms}
            self.signs[key] = state
            out.signs.append(item)
        state.update(last_ms=self.now_ms, range_m=item.get("range_m"),
                     x=_q(pos["x"]) if pos else None, z=_q(pos["z"]) if pos else None)

    def _sound(self, item: dict[str, Any]) -> None:
        key = item.get("event_id") or item["observation_id"]
        state = self.sounds.setdefault(key, {"first_ms": self.now_ms})
        state.update(last_ms=self.now_ms, sound_class=item["value"]["sound_class"], level_db=item["value"].get("level_db"),
                     bearing=item.get("bearing_rad"), validity=item["validity"])

    def _speech(self, item: dict[str, Any], out: Perceived) -> None:
        if not self._first(item):
            return
        value = item["value"]
        track_id = item.get("track_id")
        if value.get("channel") == "PA":
            # G4b (D-101): an announcement is spoken to everyone in coverage, so its words are kept,
            # labelled as an announcement and as untrusted text (D-09). Until G4b they were dropped
            # like overheard speech; no scenario used the PA, so no run changes.
            self.turns.append(Turn(item["observed_at_ms"], "PA announcement", value["text"], True))
            del self.turns[:-CONVERSATION_KEEP]
            out.announcements.append(item)
            return
        if value.get("addressed_to_observer") is True and value.get("channel") == "LOCAL":
            self.turns.append(Turn(item["observed_at_ms"], track_id or "unknown", value["text"], True))
            del self.turns[:-CONVERSATION_KEEP]
            out.addressed.append(item)
        else:
            # Only that someone spoke, where, and whether it could be to us: never the words (D-12).
            out.heard.append({"track_id": track_id, "addressed": value.get("addressed_to_observer"),
                              "at_ms": item["observed_at_ms"], "range_m": item.get("range_m"),
                              "bearing_rad": item.get("bearing_rad")})
            if track_id and track_id in self.tracks:
                self.tracks[track_id].speaking_ms = item["observed_at_ms"]
            elif track_id is None:
                self.voices.append({"at_ms": item["observed_at_ms"], "bearing": item.get("bearing_rad")})

    def my_turn(self, text: str, to: str | None) -> None:
        self.turns.append(Turn(self.now_ms, "me", text, False, to))
        del self.turns[:-CONVERSATION_KEEP]

    def _expire(self) -> None:
        now = self.now_ms
        before = sum(len(s.gestures) for s in self.tracks.values()) + len(self.voices) + len(self.tracks)
        for state in self.tracks.values():
            state.gestures = [g for g in state.gestures if now - g["at_ms"] <= GESTURE_TTL_MS]
            if state.expression is not None and now - state.expression["at_ms"] > EXPRESSION_TTL_MS:
                state.expression = None
        self.voices = [v for v in self.voices if now - v["at_ms"] <= VOICE_TTL_MS]
        self.signs = {k: v for k, v in self.signs.items() if now - v["last_ms"] <= SIGN_TTL_MS}
        self.sounds = {k: v for k, v in self.sounds.items() if now - v["last_ms"] <= SOUND_TTL_MS}
        self.tracks = {k: s for k, s in self.tracks.items() if s.left_ms is None or now - s.left_ms <= LOST_TRACK_TTL_MS}
        after = sum(len(s.gestures) for s in self.tracks.values()) + len(self.voices) + len(self.tracks)
        self.expired_count += max(0, before - after)

    def visible(self, track_id: str) -> bool:
        s = self.tracks.get(track_id)
        return s is not None and s.left_ms is None and s.validity in ("OBSERVED", "DEGRADED")

    def bearing_to(self, track_id: str) -> float | None:
        s = self.tracks.get(track_id)
        if s is None or s.x is None or self.pose is None:
            return None
        return math.atan2(-(s.x - self.pose["x"]), -(s.z - self.pose["z"]))
