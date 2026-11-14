"""Rules about bodies (configs/bodies/*.yaml, contract version 2.0; D-36, D-37).

A body is the physical part of an avatar. A role such as Robot R is not a body: a
scenario picks which body plays it. These helpers are the single Python statement of:

- how big a body is for navigation (its turning radius), and
- which gestures and expression channels it may use (the action gate uses this at G3),
- which combinations of fields make sense together (checked by tools/validate_configs.py).

Godot mirrors the radius rule in godot_app/scripts/core/bodies.gd; tests on both sides
pin the same numbers.
"""

from __future__ import annotations

import math
from typing import Any

# Navigation meshes are baked on a 5 cm grid; a body's navigation radius is its turning
# radius rounded up to that grid (D-37).
NAV_CELL_M = 0.05

# Gestures that need an arm (D-36).
ARM_GESTURES = frozenset({"WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "OPEN_PALM", "HAND_OVER"})

ROUND_SHAPES = frozenset({"CAPSULE", "CYLINDER"})


def turning_radius(body: dict[str, Any]) -> float:
    """Radius of the circle the body sweeps when it turns on the spot.

    Half the width for round colliders, half the diagonal for a box, so a body that
    navigation keeps this far from obstacles can turn anywhere without touching them.
    """
    collider = body["dimensions"]["collider"]
    if collider["shape"] in ROUND_SHAPES:
        return collider["width_m"] / 2
    return math.hypot(collider["length_m"] / 2, collider["width_m"] / 2)


def nav_radius(body: dict[str, Any]) -> float:
    """Turning radius rounded up to the navigation grid; selects the body's navigation map."""
    cells = math.ceil(turning_radius(body) / NAV_CELL_M - 1e-6)
    return round(cells * NAV_CELL_M, 4)


def supports_gesture(body: dict[str, Any], gesture: str) -> bool:
    return bool(body["capabilities"]["can_gesture"]) and gesture in body["gestures"]


def supports_channel(body: dict[str, Any], channel: str) -> bool:
    return channel in body["expression_channels"]


def body_problems(body: dict[str, Any]) -> list[str]:
    """Contradictions between fields that the JSON Schema alone cannot express."""
    found: list[str] = []
    dims = body["dimensions"]
    collider = dims["collider"]
    caps = body["capabilities"]
    gestures = set(body["gestures"])
    if collider["shape"] in ROUND_SHAPES and not math.isclose(collider["length_m"], collider["width_m"]):
        found.append(f"dimensions.collider: a {collider['shape']} is round, so length_m must equal width_m "
                     f"(got {collider['length_m']} and {collider['width_m']})")
    if body["sensors"]["mount_height_m"] > dims["height_m"]:
        found.append(f"sensors.mount_height_m {body['sensors']['mount_height_m']} is above the body's height "
                     f"{dims['height_m']}")
    if caps["can_gesture"] and not gestures:
        found.append("capabilities.can_gesture is true but gestures is empty")
    if not caps["can_gesture"] and gestures:
        found.append("gestures are listed but capabilities.can_gesture is false")
    needs_arm = sorted(gestures & ARM_GESTURES)
    if needs_arm and body["arms"] < 1:
        found.append(f"gestures {', '.join(needs_arm)} need an arm, but arms is 0")
    if "HAND_OVER" in gestures and not caps["can_grab"]:
        found.append("gesture HAND_OVER needs capabilities.can_grab")
    if caps["can_grab"] and (body["arms"] < 1 or body["reach_m"] <= 0):
        found.append("capabilities.can_grab needs at least one arm and reach_m above 0")
    if body["arms"] == 0 and body["reach_m"] > 0:
        found.append(f"reach_m is {body['reach_m']} but the body has no arm; use 0")
    if "SIT_IN_PLACE" in gestures and not caps["can_sit"]:
        found.append("gesture SIT_IN_PLACE needs capabilities.can_sit")
    if ("SPEECH" in body["expression_channels"]) != bool(caps["can_speak"]):
        found.append("expression channel SPEECH and capabilities.can_speak must agree")
    return found
