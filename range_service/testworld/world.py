"""Headless 2D test world (D-04): a test double, never a second world authority.

Only what G0 tests need: walls that block sight, avatars with position and
heading, field of view / range / line of sight, a fixed tick, a seeded RNG and
an event journal. COMMS channels and the full observer filter arrive at G2.

Observations are built only from what the observer's simulated senses could
receive. Avatars carry evaluator-only data (``private_goal``) to prove it never
leaks into an observation.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .geometry import Vec2, bearing, segments_intersect, wrap_angle
from .journal import EventJournal

PROVENANCE = "testworld_visual_fov_los_v1"
OBSERVATION_TTL_MS = 1000


@dataclass(frozen=True)
class Wall:
    wall_id: str
    a: Vec2
    b: Vec2
    blocks_sight: bool = True


@dataclass
class Avatar:
    avatar_id: str
    position: Vec2
    yaw_rad: float = 0.0
    fov_deg: float = 180.0
    visual_range_m: float = 25.0
    dropout_rate: float = 0.0
    # Evaluator-only: exists in the world, must never appear in any observation.
    private_goal: str | None = None

    def state(self) -> dict[str, Any]:
        return {"avatar_id": self.avatar_id, "x": self.position.x, "z": self.position.z, "yaw_rad": self.yaw_rad}


@dataclass(frozen=True)
class Command:
    """A scripted input applied at the start of ``tick``.

    ``SET_POSE`` uses x/z/yaw_rad; ``MOVE_BY`` uses dx/dz; ``TURN_BY`` uses dyaw_rad.
    """

    tick: int
    op: str
    avatar_id: str
    x: float | None = None
    z: float | None = None
    yaw_rad: float | None = None
    dx: float = 0.0
    dz: float = 0.0
    dyaw_rad: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError(f"command tick must be a non-negative integer, got {self.tick!r}")
        if self.op not in ("SET_POSE", "MOVE_BY", "TURN_BY"):
            raise ValueError(f"unknown command op {self.op!r}")
        if self.op == "SET_POSE" and None in (self.x, self.z, self.yaw_rad):
            raise ValueError("SET_POSE needs x, z and yaw_rad")


@dataclass
class TestWorld:
    seed: int
    tick_hz: int = 10
    map_id: str = "inline_test_map"
    walls: list[Wall] = field(default_factory=list)

    # Not collected by pytest despite the "Test" prefix.
    __test__ = False

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not isinstance(self.tick_hz, int) or self.tick_hz <= 0:
            raise ValueError("tick_hz must be a positive integer")
        self.rng = random.Random(self.seed)
        # Salt for anonymous track IDs, drawn from the seeded RNG so it is
        # reproducible per seed and different across seeds.
        self._session_salt = f"{self.rng.getrandbits(64):016x}"
        self.avatars: dict[str, Avatar] = {}
        self.tick = 0
        self.journal = EventJournal()
        self._started = False

    # ----- setup -------------------------------------------------------------

    @classmethod
    def from_map_config(cls, map_config: Mapping[str, Any], *, seed: int, tick_hz: int = 10) -> "TestWorld":
        """Build a world from a validated map config (contracts/map.schema.json)."""
        walls = [
            Wall(
                wall_id=w["wall_id"],
                a=Vec2(w["a"]["x"], w["a"]["z"]),
                b=Vec2(w["b"]["x"], w["b"]["z"]),
                blocks_sight=w["blocks_sight"],
            )
            for w in map_config["walls"]
        ]
        return cls(seed=seed, tick_hz=tick_hz, map_id=map_config["map_id"], walls=walls)

    def add_avatar(self, avatar: Avatar) -> Avatar:
        if self._started:
            raise RuntimeError("add avatars before the run starts")
        if avatar.avatar_id in self.avatars:
            raise ValueError(f"duplicate avatar {avatar.avatar_id!r}")
        self.avatars[avatar.avatar_id] = avatar
        return avatar

    @property
    def sim_time_ms(self) -> int:
        return self.tick * 1000 // self.tick_hz

    # ----- senses (deterministic geometry; no RNG) ---------------------------

    def line_of_sight(self, a: Vec2, b: Vec2) -> bool:
        return not any(w.blocks_sight and segments_intersect(a, b, w.a, w.b) for w in self.walls)

    def can_see(self, observer_id: str, target_id: str) -> bool:
        """Within range, within field of view and with clear line of sight."""
        obs = self.avatars[observer_id]
        tgt = self.avatars[target_id]
        if observer_id == target_id:
            return False
        if (tgt.position - obs.position).length() > obs.visual_range_m:
            return False
        if obs.fov_deg < 360.0:
            half_fov = math.radians(obs.fov_deg) / 2.0
            if abs(bearing(obs.position, obs.yaw_rad, tgt.position)) > half_fov + 1e-12:
                return False
        return self.line_of_sight(obs.position, tgt.position)

    def track_id(self, observer_id: str, target_id: str) -> str:
        """Anonymous ID scoped to this observer and session; not reversible to the entity ID."""
        digest = hashlib.sha256(f"{self._session_salt}|{observer_id}|{target_id}".encode()).hexdigest()
        return f"anon_{digest[:12]}"

    # ----- run loop ----------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.journal.append(
            tick_id=self.tick,
            sim_time_ms=self.sim_time_ms,
            kind="RUN_STARTED",
            actor_id=None,
            payload={
                "seed": self.seed,
                "map_id": self.map_id,
                "tick_hz": self.tick_hz,
                "avatars": [self.avatars[k].state() for k in sorted(self.avatars)],
            },
        )

    def apply(self, command: Command) -> None:
        av = self.avatars[command.avatar_id]
        payload: dict[str, Any] = {"op": command.op, "avatar_id": command.avatar_id}
        if command.op == "SET_POSE":
            av.position = Vec2(command.x, command.z)  # type: ignore[arg-type]
            av.yaw_rad = wrap_angle(command.yaw_rad)  # type: ignore[arg-type]
            payload.update(x=command.x, z=command.z, yaw_rad=command.yaw_rad)
        elif command.op == "MOVE_BY":
            av.position = Vec2(av.position.x + command.dx, av.position.z + command.dz)
            payload.update(dx=command.dx, dz=command.dz)
        else:  # TURN_BY
            av.yaw_rad = wrap_angle(av.yaw_rad + command.dyaw_rad)
            payload.update(dyaw_rad=command.dyaw_rad)
        payload["result"] = av.state()
        self.journal.append(
            tick_id=self.tick, sim_time_ms=self.sim_time_ms, kind="COMMAND_APPLIED",
            actor_id=command.avatar_id, payload=payload,
        )

    def observe(self, observer_id: str) -> dict[str, Any]:
        """Build ``observer_id``'s observation packet for this tick and journal it.

        Uses the seeded RNG for sensor dropout. Dropped detections are simply
        absent from the packet; the journal records them for the evaluator.
        """
        self.start()
        obs = self.avatars[observer_id]
        items: list[dict[str, Any]] = []
        for target_id in sorted(self.avatars):
            if not self.can_see(observer_id, target_id):
                continue
            if obs.dropout_rate > 0 and self.rng.random() < obs.dropout_rate:
                self.journal.append(
                    tick_id=self.tick, sim_time_ms=self.sim_time_ms, kind="OBSERVATION_DROPPED",
                    actor_id=observer_id,
                    payload={"observer_id": observer_id, "target_id": target_id, "reason": "SENSOR_DROPOUT"},
                )
                continue
            tgt = self.avatars[target_id]
            items.append(
                {
                    "observation_id": f"obs_{observer_id}_{self.tick}_{len(items)}",
                    "event_id": None,
                    "kind": "VISUAL_PRESENCE",
                    "track_id": self.track_id(observer_id, target_id),
                    "source_entity_id": None,
                    "position_estimate": {"x": tgt.position.x, "y": 0.0, "z": tgt.position.z},
                    "bearing_rad": bearing(obs.position, obs.yaw_rad, tgt.position),
                    "range_m": (tgt.position - obs.position).length(),
                    "value": {},
                    "observed_at_ms": self.sim_time_ms,
                    "expires_at_ms": self.sim_time_ms + OBSERVATION_TTL_MS,
                    "validity": "OBSERVED",
                    "quality": 1.0,
                    "provenance": PROVENANCE,
                }
            )
        packet = {
            "schema_version": "1.0",
            "observer_id": observer_id,
            "based_on_tick_id": self.tick,
            "sim_time_ms": self.sim_time_ms,
            "coordinate_frame": "world_meters_xyz",
            "observer_pose": {"x": obs.position.x, "y": 0.0, "z": obs.position.z, "yaw_rad": obs.yaw_rad},
            "observations": items,
        }
        stored = self.journal.append(
            tick_id=self.tick, sim_time_ms=self.sim_time_ms, kind="OBSERVATION_DELIVERED",
            actor_id=observer_id, payload=packet,
        )
        return stored["payload"]

    def run(self, script: Iterable[Command], *, ticks: int, observers: Iterable[str]) -> EventJournal:
        """Run ``ticks`` ticks: apply that tick's commands, then let each observer observe."""
        if not isinstance(ticks, int) or ticks < 0:
            raise ValueError("ticks must be a non-negative integer")
        by_tick: dict[int, list[Command]] = {}
        for cmd in script:
            by_tick.setdefault(cmd.tick, []).append(cmd)
        observer_ids = list(observers)
        self.start()
        for _ in range(ticks):
            for cmd in by_tick.get(self.tick, []):
                self.apply(cmd)
            for observer_id in observer_ids:
                self.observe(observer_id)
            self.tick += 1
        self.journal.append(
            tick_id=self.tick, sim_time_ms=self.sim_time_ms, kind="RUN_ENDED",
            actor_id=None, payload={"ticks_run": ticks},
        )
        return self.journal
