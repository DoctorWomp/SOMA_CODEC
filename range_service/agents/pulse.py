"""Continuous presence between model decisions (PULSE_PROTOCOL §2–§7; G3c-2, D-61).

Four deterministic parts, all keyed on simulated time from the agent's own packets, so stepped
runs stay byte-exact; none of them calls the model:

- ``IntentMonitor`` (loop 3): holds the current activity and checks its wake conditions on
  every packet. A condition that fires (after its cooldown) wakes the runtime with
  ``WAKE_CONDITION``; otherwise nothing happens.
- ``Pulse`` (loop 4): at review time, a triage of what changed since the last review. Nothing
  changed and the activity still holds → ``CONTINUE`` (logged, no model call), and the next
  review backs off (15 → 30 → 60 s ... up to the activity's review time). A change → a
  ``PULSE_REVIEW`` decision with a short sitrep. Seeded jitter; an idle budget of model reviews
  per minute.
- ``Presence`` (loop 2): a glance (LOOK_AT through the normal action path) toward a new person
  or a voice within range, rate-limited per source, never while the agent is speaking; gaze
  returns to the conversation partner after a glance away; slow Beacon "breathing" while idle.
- ``Survey``: with no task and no post duty, roam toward the cell of the hall the agent has
  observed least recently (its own position history only), keep clear of people, never return
  to a cell observed recently (no pacing), and go back to post on a schedule.

Only the agent's own senses are used. HORIZON layers (Focus, Prism, Haze, Trail) are G5; their
wake conditions are reserved, never faked.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from .activity import IDLE_KINDS, Activity

CLOSING_WORDS = ("bye", "goodbye", "see you", "excuse me", "sorry", "i need to go", "i have to go", "be right back",
                 "back in a moment", "one moment", "i'll be back", "i will be back", "take care", "enjoy")


WORLD_LOOK_HOLD_MS = 3000      # the world holds a LOOK_AT this long (avatar.gd GAZE_HOLD_TICKS = 180)


def is_closing(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in CLOSING_WORDS)


def voice_key(bearing_rad: float) -> str:
    """An unplaced voice, identified by its direction (45° sectors) for rate limits and metrics."""
    return f"voice@{round(bearing_rad / (math.pi / 4)) % 8 * 45}deg"


def seeded_fraction(*parts: Any) -> float:
    """A number in [0, 1) from the given parts (the run seed among them): jitter that is the same
    on every run with the same seed."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass
class Event:
    kind: str
    at_ms: int
    data: dict[str, Any] = field(default_factory=dict)

    def record(self) -> dict[str, Any]:
        return {"event": self.kind, "at_ms": self.at_ms, **self.data}


# ---------- loop 3: the intent monitor ----------

class IntentMonitor:
    def __init__(self, cooldowns_s: dict[str, float]) -> None:
        self.cooldowns_ms = {k: int(v * 1000) for k, v in cooldowns_s.items()}
        self.last_fired: dict[str, int] = {}

    def check(self, activity: Activity | None, *, now_ms: int, perceived: Any, ws: Any, addressed: bool,
              heard_tracks: list[str], new_tracks: list[str], due_commitment: bool) -> list[str]:
        """The wake conditions of ``activity`` that fire on this packet (after their cooldowns)."""
        if activity is None:
            return []
        fired = []
        target = activity.target_id
        for cond in activity.wake_if:
            (key, value), = cond.items()
            hit = False
            if key == "addressed":
                hit = addressed
            elif key == "speech_heard":
                hit = bool(heard_tracks)
            elif key == "new_track":
                hit = bool(new_tracks)
            elif key == "commitment_due":
                hit = due_commitment
            elif key == "target_lost" and target is not None:
                hit = target in perceived.lost_tracks and not ws.visible(target)
            elif key == "target_within_m" and target is not None:
                state = ws.tracks.get(target)
                near = state is not None and ws.visible(target) and state.range_m is not None and state.range_m <= value
                # Fires when the person comes within range, not if they already were when the
                # activity began (the first check of an activity only notes where they are).
                key_seen = f"near_seen:{target}:{activity.started_ms}"
                was = self.last_fired.get(f"near:{target}") is not None
                hit = near and not was and key_seen in self.last_fired
                self.last_fired[key_seen] = now_ms
                if near:
                    self.last_fired[f"near:{target}"] = now_ms
                else:
                    self.last_fired.pop(f"near:{target}", None)
                if hit:
                    fired.append(key)
                continue
            if not hit:
                continue
            last = self.last_fired.get(key)
            if last is not None and now_ms - last < self.cooldowns_ms.get(key, 0):
                continue
            self.last_fired[key] = now_ms
            fired.append(key)
        return fired


# ---------- loop 4: the pulse ----------

@dataclass
class Digest:
    """What triage compares between reviews (a short Trail difference, own senses only)."""

    tracks: frozenset[str]
    speech: int
    due: frozenset[str]
    target_visible: bool | None
    progress_m: float | None


class Pulse:
    def __init__(self, cfg: dict[str, Any], agent_id: str, seed: int) -> None:
        self.backoff_ms = [int(s * 1000) for s in cfg["backoff_s"]]
        self.jitter = cfg["jitter_frac"]
        self.budget = cfg["idle_budget_per_min"]
        self.agent_id = agent_id
        self.seed = seed
        self.step = 0
        self.next_ms: int | None = None
        self.last_review_ms: int | None = None
        self.continues = 0
        self.reviews = 0
        self.model_reviews_at: list[int] = []
        self.digest: Digest | None = None
        self.continues_since_change = 0

    def schedule(self, now_ms: int, activity: Activity | None, reset: bool) -> None:
        """The next review: the current backoff step (15, 30, 60 s ...), never later than the
        activity's own review time; ``reset`` (a meaningful change) starts again at the first step."""
        if reset:
            self.step = 0
            self.continues_since_change = 0
        base = self.backoff_ms[min(self.step, len(self.backoff_ms) - 1)]
        if activity is not None:
            base = min(base, activity.review_after_s * 1000)
        jitter = (seeded_fraction(self.seed, self.agent_id, self.reviews, self.continues) * 2 - 1) * self.jitter
        self.next_ms = now_ms + int(base * (1 + jitter))

    def due(self, now_ms: int) -> bool:
        return self.next_ms is not None and now_ms >= self.next_ms

    def over_budget(self, now_ms: int) -> bool:
        self.model_reviews_at = [t for t in self.model_reviews_at if now_ms - t < 60_000]
        return len(self.model_reviews_at) >= self.budget

    def triage(self, now: Digest) -> list[str]:
        """What changed since the last review (empty: CONTINUE)."""
        before = self.digest
        changed = []
        if before is not None:
            if now.tracks - before.tracks:
                changed.append(f"new in view: {', '.join(sorted(now.tracks - before.tracks)[:3])}")
            if before.tracks - now.tracks:
                changed.append(f"no longer in view: {', '.join(sorted(before.tracks - now.tracks)[:3])}")
            if now.speech > before.speech:
                changed.append(f"speech heard nearby ({now.speech - before.speech})")
            if now.due - before.due:
                changed.append("a promise is due")
            if before.target_visible and now.target_visible is False:
                changed.append("the person you are with is out of view")
            if now.progress_m is not None and before.progress_m is not None and now.progress_m >= before.progress_m - 0.2 \
                    and now.progress_m > 1.0:
                changed.append("no progress toward your destination")
        self.digest = now
        return changed


# ---------- loop 2: presence ----------

class Presence:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.range_m = cfg["glance_range_m"]
        self.cooldown_ms = int(cfg["glance_cooldown_s"] * 1000)
        self.hold_ms = int(cfg["gaze_hold_s"] * 1000)
        self.return_ms = int(cfg["return_to_partner_s"] * 1000)
        self.idle_expression = cfg["idle_expression"]
        self.last_glance: dict[str, int] = {}
        self.gaze_target: str | None = None
        self.gaze_since_ms = 0
        self.return_at_ms: int | None = None
        self.shown_idle = False

    def step(self, *, now_ms: int, ws: Any, perceived: Any, heard: list[dict[str, Any]], partner: str | None,
             speaking_until_ms: int, activity: Activity | None, can_look: bool,
             expressions: list[str]) -> tuple[list[tuple[str, dict[str, Any]]], list[Event]]:
        """Presence actions for this packet: [(action, args)] and their log events, one event per
        action and in the same order (G3d: each event learns its request id and the host's result)."""
        out: list[tuple[str, dict[str, Any]]] = []
        events: list[Event] = []
        if not can_look:
            return out, events
        speaking = now_ms < speaking_until_ms
        sources: list[tuple[str, str]] = []
        voices: dict[str, dict[str, float]] = {}
        for item in heard:
            track = item.get("track_id")
            if track and ws.visible(track) and (ws.tracks[track].range_m or 99) <= self.range_m:
                sources.append((track, "speech"))
            elif track is None and item.get("bearing_rad") is not None and ws.pose is not None:
                # A voice it cannot see (FN-2): glance toward where it came from, 3 m out at head
                # height. Bearing is relative to its facing, positive to the left (D-29).
                key = voice_key(item["bearing_rad"])
                yaw = ws.pose["yaw_rad"] + item["bearing_rad"]
                voices[key] = {"x": round(ws.pose["x"] - 3.0 * math.sin(yaw), 2), "y": 1.6,
                               "z": round(ws.pose["z"] - 3.0 * math.cos(yaw), 2)}
                sources.append((key, "voice"))
        for track in perceived.new_tracks:
            if (ws.tracks[track].range_m or 99) <= self.range_m:
                sources.append((track, "movement"))
        if not speaking:
            for track, why in sources:
                # Already looking at it only while the world still holds the last LOOK_AT (G3d, D-65);
                # it used to count as looked at forever after one glance.
                held = track == self.gaze_target and now_ms - self.gaze_since_ms < WORLD_LOOK_HOLD_MS
                if held or now_ms - self.last_glance.get(track, -10**9) < self.cooldown_ms:
                    continue
                self.last_glance[track] = now_ms
                out.append(("LOOK_AT", {"point": voices[track]} if track in voices else {"target_id": track}))
                events.append(Event("GLANCE", now_ms, {"target": track, "why": why}))
                self.gaze_target, self.gaze_since_ms = track, now_ms
                if partner is not None and track != partner:
                    self.return_at_ms = now_ms + self.return_ms
                break
        if not out and partner is not None and ws.visible(partner):
            if self.return_at_ms is not None and now_ms >= self.return_at_ms:
                out.append(("LOOK_AT", {"target_id": partner}))
                events.append(Event("GAZE_RETURN", now_ms, {"target": partner}))
                self.gaze_target, self.gaze_since_ms, self.return_at_ms = partner, now_ms, None
            elif self.gaze_target != partner and self.return_at_ms is None and not speaking:
                out.append(("LOOK_AT", {"target_id": partner}))          # soft, steady gaze while listening
                events.append(Event("GAZE_PARTNER", now_ms, {"target": partner}))
                self.gaze_target, self.gaze_since_ms = partner, now_ms
            elif self.gaze_target == partner and now_ms - self.gaze_since_ms >= self.hold_ms and not speaking:
                out.append(("LOOK_AT", {"target_id": partner}))          # renew the hold (the world holds 3 s)
                events.append(Event("GAZE_HOLD", now_ms, {"target": partner}))   # logged: gaze intervals (G3d)
                self.gaze_since_ms = now_ms
        idle = activity is not None and activity.kind in IDLE_KINDS and partner is None
        if idle and not self.shown_idle and self.idle_expression in expressions and not out:
            out.append(("EXPRESS", {"expression_id": self.idle_expression, "target_id": None}))
            events.append(Event("BREATHE", now_ms, {"expression": self.idle_expression}))
            self.shown_idle = True
        if not idle:
            self.shown_idle = False
        return out, events


# ---------- SURVEY and RETURN_TO_POST ----------

class Survey:
    def __init__(self, cfg: dict[str, Any], area: dict[str, float], post: dict[str, float] | None) -> None:
        self.cell = cfg["cell_m"]
        self.radius = cfg["observe_radius_m"]
        self.revisit_ms = int(cfg["min_revisit_s"] * 1000)
        self.clearance = cfg["people_clearance_m"]
        self.return_ms = int(cfg["return_to_post_s"] * 1000)
        self.dwell_ms = int(cfg["dwell_s"] * 1000)
        self.post = post
        self.cells: list[tuple[float, float]] = []
        x = area["x_min"] + self.cell / 2
        while x < area["x_max"]:
            z = area["z_min"] + self.cell / 2
            while z < area["z_max"]:
                self.cells.append((round(x, 2), round(z, 2)))
                z += self.cell
            x += self.cell
        self.seen: dict[tuple[float, float], int] = {}
        self.goal: tuple[float, float] | None = None
        self.arrived_ms: int | None = None
        self.left_post_ms: int | None = None
        self.returning = False

    def observe(self, now_ms: int, pose: dict[str, float] | None) -> None:
        if pose is None:
            return
        for c in self.cells:
            if math.hypot(c[0] - pose["x"], c[1] - pose["z"]) <= self.radius:
                self.seen[c] = now_ms

    def next_move(self, now_ms: int, pose: dict[str, float] | None,
                  people: list[tuple[float, float]]) -> tuple[str, dict[str, float]] | None:
        """(why, destination) when the agent should start moving now, else None."""
        if pose is None:
            return None
        here = (pose["x"], pose["z"])
        at_post = self.post is not None and math.hypot(here[0] - self.post["x"], here[1] - self.post["z"]) <= 1.0
        if self.post is not None and not at_post and self.left_post_ms is None:
            self.left_post_ms = now_ms
        if at_post:
            self.left_post_ms, self.returning = None, False
        if self.goal is not None:
            if math.hypot(here[0] - self.goal[0], here[1] - self.goal[1]) > 1.2:
                return None                                              # still on the way
            if self.arrived_ms is None:
                self.arrived_ms = now_ms
            if now_ms - self.arrived_ms < self.dwell_ms:
                return None                                              # a pause at each place
            self.goal, self.arrived_ms = None, None
        if self.returning:
            return None
        if self.post is not None and self.left_post_ms is not None and now_ms - self.left_post_ms >= self.return_ms:
            self.returning = True
            self.goal = (self.post["x"], self.post["z"])
            return "RETURN_TO_POST", {"x": self.post["x"], "z": self.post["z"]}
        candidates = []
        for c in self.cells:
            last = self.seen.get(c)
            if last is not None and now_ms - last < self.revisit_ms:
                continue                                                 # seen recently: no pacing
            if any(math.hypot(c[0] - px, c[1] - pz) < self.clearance for px, pz in people):
                continue                                                 # never approach people to look busy
            candidates.append((last if last is not None else -1, round(math.hypot(c[0] - here[0], c[1] - here[1]), 2), c))
        if not candidates:
            return None
        _, _, cell = min(candidates)
        self.goal = cell
        return "SURVEY", {"x": cell[0], "z": cell[1]}
