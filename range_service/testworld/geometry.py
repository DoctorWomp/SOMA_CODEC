"""2D floor geometry in meters, Godot convention (D-29).

The floor is the (x, z) plane. ``yaw_rad`` is Godot's ``rotation.y``: yaw 0 faces
-z, and a positive yaw turns the avatar to its left (counter-clockwise seen from
above). Bearings use the same sign: positive means "to the observer's left".
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vec2:
    x: float
    z: float

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.z - other.z)

    def length(self) -> float:
        return math.hypot(self.x, self.z)


def wrap_angle(angle: float) -> float:
    """Wrap to the range (-pi, pi]."""
    wrapped = math.remainder(angle, math.tau)
    return math.pi if wrapped == -math.pi else wrapped


def forward(yaw_rad: float) -> Vec2:
    """Unit vector an avatar faces. Yaw 0 faces -z (Godot)."""
    return Vec2(-math.sin(yaw_rad), -math.cos(yaw_rad))


def yaw_toward(origin: Vec2, target: Vec2) -> float:
    """Yaw that would face ``target`` from ``origin``."""
    d = target - origin
    return math.atan2(-d.x, -d.z)


def bearing(observer: Vec2, observer_yaw: float, target: Vec2) -> float:
    """Angle from the observer's forward direction to the target, positive to the left."""
    return wrap_angle(yaw_toward(observer, target) - observer_yaw)


def _orient(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x)


def _on_segment(a: Vec2, b: Vec2, p: Vec2, tol: float) -> bool:
    return (
        min(a.x, b.x) - tol <= p.x <= max(a.x, b.x) + tol
        and min(a.z, b.z) - tol <= p.z <= max(a.z, b.z) + tol
    )


def segments_intersect(p1: Vec2, p2: Vec2, q1: Vec2, q2: Vec2, tol: float = 1e-9) -> bool:
    """True if segment p1-p2 touches segment q1-q2. Touching counts (conservative for sight)."""
    d1 = _orient(q1, q2, p1)
    d2 = _orient(q1, q2, p2)
    d3 = _orient(p1, p2, q1)
    d4 = _orient(p1, p2, q2)
    if ((d1 > tol and d2 < -tol) or (d1 < -tol and d2 > tol)) and (
        (d3 > tol and d4 < -tol) or (d3 < -tol and d4 > tol)
    ):
        return True
    if abs(d1) <= tol and _on_segment(q1, q2, p1, tol):
        return True
    if abs(d2) <= tol and _on_segment(q1, q2, p2, tol):
        return True
    if abs(d3) <= tol and _on_segment(p1, p2, q1, tol):
        return True
    if abs(d4) <= tol and _on_segment(p1, p2, q2, tol):
        return True
    return False
