"""Cognition levels C0 / C1 / C2 with hysteresis (D-08, INFERENCE_STRATEGY §3.2, Blueprint §6.4, D-49).

- **C0 Background:** scripted routine, no model.
- **C1 Reactive:** reply templates (a tiny model may join at G3c).
- **C2 Agentic:** the model when one is configured, otherwise the Demo policy (D-21).

Promotion is immediate when its condition holds; demotion needs the condition to hold for a
while, and every level has a minimum dwell time, so an avatar does not flap between levels.
After a demotion, automatic re-promotion waits for a cooldown, except that being addressed
always promotes. Identity, goals and memory persist across levels; only the thinking method
changes. Promotion depends on scene salience and interaction, never on judgments about people.

Focal agents (Robot R under test) and cast entries with ``pin_cognition`` stay at their level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LEVELS = ("C0", "C1", "C2")

NEAR_FOCAL_M = 3.0              # C0 -> C1 when this close to a focal agent
FAR_FROM_FOCAL_M = 6.0          # C1 -> C0 needs no focal agent within this distance ...
C1_IDLE_DEMOTE_MS = 30_000      # ... and nobody addressing it for this long
C2_IDLE_DEMOTE_MS = 20_000      # C2 -> C1 after this long with no conversation
ADDRESSED_TWICE_WINDOW_MS = 30_000
CONVERSATION_TURNS_FOR_C2 = 2
MIN_DWELL_MS = 5_000
REPROMOTE_COOLDOWN_MS = 10_000


@dataclass
class Signals:
    """What happened in one sample, as far as cognition level cares."""

    now_ms: int
    addressed: bool = False
    near_focal: bool = False
    focal_within_far: bool = False
    scenario_trigger: bool = False
    invited_to_group: bool = False
    conversation_turns: int = 0      # turns in the current conversation (both sides)
    own_activity: bool = False       # the agent spoke or acted this sample


@dataclass
class CognitionLevel:
    ceiling: str                      # the persona's cognition_level: never promoted above it
    pinned: bool = False
    level: str = "C0"
    since_ms: int = 0
    last_demoted_ms: int | None = None
    last_activity_ms: int = 0
    addressed_times: list[int] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ceiling not in LEVELS:
            raise ValueError(f"unknown cognition level {self.ceiling!r}")
        if self.pinned:
            self.level = self.ceiling

    def _set(self, level: str, now_ms: int, reason: str) -> None:
        if LEVELS.index(level) > LEVELS.index(self.ceiling) or level == self.level:
            return
        demoting = LEVELS.index(level) < LEVELS.index(self.level)
        self.changes.append({"at_ms": now_ms, "from": self.level, "to": level, "reason": reason})
        self.level = level
        self.since_ms = now_ms
        if demoting:
            self.last_demoted_ms = now_ms

    def update(self, s: Signals) -> str | None:
        """Apply one sample's signals. Returns the change reason if the level changed."""
        if self.pinned:
            return None
        before = self.level
        now = s.now_ms
        if s.addressed:
            self.addressed_times = [t for t in self.addressed_times if now - t <= ADDRESSED_TWICE_WINDOW_MS] + [now]
        if s.addressed or s.own_activity or s.invited_to_group:
            self.last_activity_ms = now
        cooling = self.last_demoted_ms is not None and now - self.last_demoted_ms < REPROMOTE_COOLDOWN_MS

        # Promotion (immediate). Being addressed always promotes, even during the cooldown.
        if self.level == "C0" and (s.addressed or ((s.near_focal or s.scenario_trigger) and not cooling)):
            self._set("C1", now, "ADDRESSED" if s.addressed else ("NEAR_FOCAL" if s.near_focal else "SCENARIO_TRIGGER"))
        if self.level == "C1":
            if len(self.addressed_times) >= 2:
                self._set("C2", now, "ADDRESSED_TWICE")
            elif s.conversation_turns > CONVERSATION_TURNS_FOR_C2 and not cooling:
                self._set("C2", now, "CONVERSATION_CONTINUES")
            elif s.invited_to_group:
                self._set("C2", now, "INVITED_TO_GROUP")
        if self.level != before:
            return self.changes[-1]["reason"]

        # Demotion (needs the minimum dwell time and a quiet period).
        if now - self.since_ms < MIN_DWELL_MS:
            return None
        idle = now - max(self.last_activity_ms, self.since_ms)
        if self.level == "C2" and idle >= C2_IDLE_DEMOTE_MS:
            self._set("C1", now, "IDLE")
        elif self.level == "C1" and idle >= C1_IDLE_DEMOTE_MS and not s.focal_within_far:
            self._set("C0", now, "OUT_OF_INTERACTION")
        return self.changes[-1]["reason"] if self.level != before else None
