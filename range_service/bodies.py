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
    found += rig_problems(body)
    found += head_problems(body)
    return found


# ---------- the head (G3e, D-72): host-owned world state for bodies with a neck ----------

NECK_KINDS = frozenset({"LEGGED_HUMANOID", "WHEELED_HUMANOID"})
# The rig's default Neck limits (godot_app/scripts/rig/rig_spec.gd): yaw +/-85, pitch -40..60 with
# positive looking DOWN. The head block's pitch is positive UP, so its max must fit 40 and its
# min -60: the rig must be able to show every head pose the world simulates, unclamped.
RIG_NECK_LIMITS_DEG = {"yaw": (-85.0, 85.0), "pitch": (-40.0, 60.0)}


def head_settings(body: dict[str, Any]) -> dict[str, Any] | None:
    """The neck (yaw limit, pitch limits, turn speed), or None when the sensor head is fixed to the body."""
    head = body.get("head")
    if not head or not head.get("neck"):
        return None
    return head


def head_problems(body: dict[str, Any]) -> list[str]:
    head = body.get("head")
    if head is None:
        return []
    found = []
    keys = ("yaw_limit_deg", "pitch_limit_deg", "turn_speed_deg_s")
    if head["neck"]:
        if body["kind"] not in NECK_KINDS:
            found.append(f"head.neck: a {body['kind']} body has no neck; its sensor head is fixed to the body (D-56, D-72)")
        missing = [k for k in keys if k not in head]
        if missing:
            found.append(f"head: a neck needs {', '.join(missing)}")
        limits = {**{k: list(v) for k, v in RIG_NECK_LIMITS_DEG.items()},
                  **body.get("rig", {}).get("joint_limits_deg", {}).get("Neck", {})}
        if "yaw_limit_deg" in head and head["yaw_limit_deg"] > min(-limits["yaw"][0], limits["yaw"][1]):
            found.append(f"head.yaw_limit_deg {head['yaw_limit_deg']} is beyond the rig's Neck yaw {limits['yaw']}")
        if "pitch_limit_deg" in head:
            lo, hi = head["pitch_limit_deg"]["min"], head["pitch_limit_deg"]["max"]
            if hi > -limits["pitch"][0] or -lo > limits["pitch"][1]:
                found.append(f"head.pitch_limit_deg {lo}..{hi} is beyond the rig's Neck pitch {limits['pitch']} "
                             f"(the rig's pitch is positive looking down)")
        if "head_turn_speed_deg_s" in body.get("rig", {}):
            found.append("rig.head_turn_speed_deg_s: with a neck the head turns at head.turn_speed_deg_s (D-72); "
                         "remove it from the rig block")
    elif any(k in head for k in keys):
        found.append("head: limits and a turn speed are only for a neck (neck: true)")
    return found


# ---------- rig (D-54, D-56): pose is presentation; these rules keep the rig block honest ----------

# Gestures last 90 ticks (1.5 s) at tempo 1; the world divides by the clamped tempo (D-56).
# Godot states the same rule in godot_app/scripts/rig/rig_spec.gd; tests on both sides pin it.
GESTURE_BASE_TICKS = 90
PROSODY_RANGE = (0.5, 1.5)
HEAD_YAW_LIMIT_DEG = 85.0

# Joints and axes of each skeleton family (docs/gates/RIG_PLAN.md). Sided joints end in L/R; the
# arm module's joints are added when the rig has one. Godot's table (rig_spec.gd) must match:
# godot_app/tests/test_main.gd pins the same names.
_HUMANOID_UPPER = {
    "SpineLower": ("yaw", "pitch", "roll"), "SpineUpper": ("yaw", "pitch", "roll"),
    "Neck": ("yaw", "pitch", "roll"),
    "Shoulder": ("pitch", "roll", "yaw"), "Elbow": ("flex",), "Wrist": ("roll", "pitch"),
    "Fingers": ("curl",), "Thumb": ("curl",),
}
_HUMANOID_LEGS = {"Hip": ("pitch", "roll", "yaw"), "Knee": ("flex",), "Ankle": ("pitch", "roll"), "Toe": ("flex",)}
_WHEELED_BASE = {"TorsoMount": ("yaw", "pitch", "roll")}
# The quadruped has no neck (owner, 2026-11-16): its "Body" joint is the whole body's pose over
# planted feet (yaw, pitch, roll), made by the legs, as on current robot dogs.
_QUADRUPED = {"Body": ("yaw", "pitch", "roll"), "HipAbd": ("abduct",), "HipFlex": ("flex",), "Knee": ("flex",)}
_ARM_MODULE = {"ArmBase": ("yaw",), "ArmShoulder": ("pitch",), "ArmElbow": ("flex",),
               "ArmWrist": ("pitch", "yaw", "roll"), "Gripper": ("open",)}
_SIDED = {"Shoulder", "Elbow", "Wrist", "Fingers", "Thumb", "Hip", "Knee", "Ankle", "Toe"}
_LEGS = ("FL", "FR", "BL", "BR")

RIGGED_KINDS = {"LEGGED_HUMANOID": "HUMANOID", "WHEELED_HUMANOID": "HUMANOID", "QUADRUPED": "QUADRUPED"}


def rig_settings(body: dict[str, Any]) -> dict[str, Any] | None:
    """The body's rig block with defaults filled in, or None for bodies without a rig yet."""
    family = RIGGED_KINDS.get(body["kind"])
    if family is None:
        return None
    rig = dict(body.get("rig", {}))
    rig.setdefault("skeleton", family)
    rig.setdefault("arm_module", family == "QUADRUPED" and body["arms"] > 0)
    for key in ("gesture_amplitude", "gesture_tempo"):
        rig.setdefault(key, {"min": PROSODY_RANGE[0], "max": PROSODY_RANGE[1]})
    return rig


def rig_joints(body: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Joint name -> axes for this body's skeleton ({} for bodies without a rig)."""
    rig = rig_settings(body)
    if rig is None:
        return {}
    if rig["skeleton"] == "HUMANOID":
        table = dict(_HUMANOID_UPPER)
        table.update(_HUMANOID_LEGS if body["kind"] == "LEGGED_HUMANOID" else _WHEELED_BASE)
    else:
        table = dict(_QUADRUPED)
    if rig["arm_module"]:
        table.update(_ARM_MODULE)
    joints: dict[str, tuple[str, ...]] = {}
    for name, axes in table.items():
        if rig["skeleton"] == "QUADRUPED" and name in ("HipAbd", "HipFlex", "Knee"):
            joints.update({name + leg: axes for leg in _LEGS})
        elif name in _SIDED:
            joints.update({name + side: axes for side in ("L", "R")})
        else:
            joints[name] = axes
    return joints


def clamp_prosody(body: dict[str, Any], key: str, value: float | None) -> float | None:
    """A gesture's amplitude or tempo after the body's limits (None stays None: the default, 1)."""
    rig = rig_settings(body)
    if value is None or rig is None:
        return value
    lo, hi = rig["gesture_" + key]["min"], rig["gesture_" + key]["max"]
    return min(max(value, lo), hi)


def gesture_duration_ticks(tempo: float | None) -> int:
    """How long a gesture event lasts, in 60 Hz ticks, for an already clamped tempo (D-56)."""
    # Half rounds up, as Godot's roundi does (Python's round() would round half to even).
    return math.floor(GESTURE_BASE_TICKS / (1.0 if tempo is None else tempo) + 0.5)


def rig_problems(body: dict[str, Any]) -> list[str]:
    if "rig" not in body:
        return []
    rig = body["rig"]
    family = RIGGED_KINDS.get(body["kind"])
    if family is None:
        return [f"rig: bodies of kind {body['kind']} have no skeleton yet (visitors come at rig step C)"]
    found: list[str] = []
    if rig["skeleton"] != family:
        found.append(f"rig.skeleton {rig['skeleton']} does not fit kind {body['kind']} (use {family})")
        return found
    if rig.get("arm_module") and (family != "QUADRUPED" or body["arms"] < 1):
        found.append("rig.arm_module needs a quadruped with arms >= 1 (humanoid arms are part of their skeleton)")
    if family == "QUADRUPED" and body["arms"] > 0 and rig.get("arm_module") is False:
        found.append(f"rig.arm_module is false but the body has {body['arms']} arm(s): its arm gestures could not be shown")
    joints = rig_joints(body)
    for joint, axes in rig.get("joint_limits_deg", {}).items():
        if joint not in joints:
            found.append(f"rig.joint_limits_deg: {joint} is not a joint of this skeleton "
                         f"(joints: {', '.join(sorted(joints))})")
            continue
        for axis, (lo, hi) in axes.items():
            if axis not in joints[joint]:
                found.append(f"rig.joint_limits_deg.{joint}: {joint} has no axis {axis} (axes: {', '.join(joints[joint])})")
            elif lo > hi:
                found.append(f"rig.joint_limits_deg.{joint}.{axis}: min {lo} is above max {hi}")
            elif joint == "Neck" and axis == "yaw" and max(-lo, hi) > HEAD_YAW_LIMIT_DEG:
                found.append(f"rig.joint_limits_deg.Neck.yaw: head yaw is at most +/-{HEAD_YAW_LIMIT_DEG:g} degrees "
                             f"on every body (D-54)")
    for key in ("gesture_amplitude", "gesture_tempo"):
        if key in rig:
            lo, hi = rig[key]["min"], rig[key]["max"]
            if not lo <= 1.0 <= hi:
                found.append(f"rig.{key}: the range {lo}-{hi} must include 1 (the normal gesture)")
    return found
