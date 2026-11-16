"""The robot body family (D-36) and the rules in range_service/bodies.py (D-37)."""

from __future__ import annotations

import pytest

from range_service import bodies as rules
from range_service.configs import load_and_check
from tests.test_validate_configs import _edit, _messages, config_copy  # noqa: F401  (fixture)

ROBOTS = ("legged_humanoid", "wheeled_humanoid", "quadruped", "quadruped_arm")


@pytest.fixture(scope="module")
def body():
    config_set, problems = load_and_check()
    assert not problems
    return config_set.items["bodies"]


def test_three_robot_families_and_the_arm_variant_exist(body):
    kinds = {b: body[b]["kind"] for b in ROBOTS}
    assert kinds == {"legged_humanoid": "LEGGED_HUMANOID", "wheeled_humanoid": "WHEELED_HUMANOID",
                     "quadruped": "QUADRUPED", "quadruped_arm": "QUADRUPED"}


@pytest.mark.parametrize("body_id, stairs, ramp", [
    ("legged_humanoid", True, True),
    ("wheeled_humanoid", False, True),
    ("quadruped", True, True),
    ("quadruped_arm", True, True),
    ("human_walker", True, True),
])
def test_stairs_and_ramp_capabilities(body, body_id, stairs, ramp):
    caps = body[body_id]["capabilities"]
    assert (caps["can_use_stairs"], caps["can_use_ramp"]) == (stairs, ramp)


# Godot's test_body_dimensions_and_navigation_radius pins the same numbers.
@pytest.mark.parametrize("body_id, turning, nav", [
    ("legged_humanoid", 0.28, 0.30),
    ("wheeled_humanoid", 0.4478, 0.45),
    ("quadruped", 0.6042, 0.65),
    ("quadruped_arm", 0.6042, 0.65),
    ("human_walker", 0.25, 0.25),
])
def test_turning_and_navigation_radius(body, body_id, turning, nav):
    assert rules.turning_radius(body[body_id]) == pytest.approx(turning, abs=1e-3)
    assert rules.nav_radius(body[body_id]) == pytest.approx(nav)


def test_dimensions_are_plausible_and_sensors_sit_inside_the_body(body):
    for body_id, b in body.items():
        assert 0 < b["sensors"]["mount_height_m"] <= b["dimensions"]["height_m"], body_id
    # Humanoids are person-height; quadrupeds are low, with low sensors that partitions
    # (2 m) and crowds hide (G2 observer filter).
    for humanoid in ("legged_humanoid", "wheeled_humanoid"):
        assert 1.3 <= body[humanoid]["dimensions"]["height_m"] <= 1.9
        assert body[humanoid]["sensors"]["mount_height_m"] > 1.2
    for quad in ("quadruped", "quadruped_arm"):
        assert body[quad]["dimensions"]["height_m"] < 1.0
        assert body[quad]["sensors"]["mount_height_m"] < 0.7
        collider = body[quad]["dimensions"]["collider"]
        assert collider["shape"] == "BOX" and collider["length_m"] > 2 * collider["width_m"]
    assert body["quadruped_arm"]["dimensions"]["height_m"] > body["quadruped"]["dimensions"]["height_m"]


@pytest.mark.parametrize("body_id, allowed, refused", [
    ("legged_humanoid", {"WAVE", "POINT", "NOD", "BOW", "HAND_OVER", "HEAD_TILT"}, {"SIT_IN_PLACE"}),
    ("wheeled_humanoid", {"WAVE", "POINT", "NOD", "BOW", "HAND_OVER", "HEAD_TILT"}, {"SIT_IN_PLACE"}),
    ("quadruped", {"HEAD_TILT", "SIT_IN_PLACE"},
     {"WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "OPEN_PALM", "HAND_OVER", "NOD", "SHAKE_HEAD", "BOW"}),
    # Gripper wave, beckon and raised gripper for "stop" (owner, 2026-11-16); never hand or finger gestures.
    ("quadruped_arm", {"HEAD_TILT", "SIT_IN_PLACE", "POINT", "HAND_OVER", "WAVE", "BECKON", "RAISED_HAND"},
     {"SMALL_WAVE", "OPEN_PALM", "BOW", "NOD", "SHAKE_HEAD"}),
])
def test_gesture_permissions(body, body_id, allowed, refused):
    for gesture in allowed:
        assert rules.supports_gesture(body[body_id], gesture), f"{body_id} should be able to {gesture}"
    for gesture in refused:
        assert not rules.supports_gesture(body[body_id], gesture), f"{body_id} must not be able to {gesture}"


def test_no_gesture_when_the_body_cannot_gesture(body):
    still = dict(body["quadruped"], capabilities=dict(body["quadruped"]["capabilities"], can_gesture=False))
    assert not rules.supports_gesture(still, "HEAD_TILT")


def test_expression_channels(body):
    for humanoid in ("legged_humanoid", "wheeled_humanoid"):
        assert set(body[humanoid]["expression_channels"]) == {"SPEECH", "FACE", "LIGHT"}
    for quad in ("quadruped", "quadruped_arm"):
        assert rules.supports_channel(body[quad], "LIGHT")
        assert not rules.supports_channel(body[quad], "FACE"), "the quadruped's visor is a camera array, not a face"


def test_arm_variant_differs_only_by_the_arm(body):
    plain, arm = body["quadruped"], body["quadruped_arm"]
    assert (plain["arms"], arm["arms"]) == (0, 1)
    assert plain["reach_m"] == 0 and arm["reach_m"] > 0
    assert not plain["capabilities"]["can_grab"] and arm["capabilities"]["can_grab"]
    assert plain["motion"] == arm["motion"] and plain["sensors"] == arm["sensors"]
    assert plain["dimensions"]["collider"] == arm["dimensions"]["collider"]


# ---------- contradictions are reported (tools/validate_configs.py) ----------

@pytest.mark.parametrize("file, old, new, expected", [
    ("quadruped.yaml", "gestures: [HEAD_TILT, SIT_IN_PLACE]", "gestures: [HEAD_TILT, WAVE]",
     "gestures WAVE need an arm, but arms is 0"),
    ("quadruped.yaml", "  can_sit: true", "  can_sit: false", "gesture SIT_IN_PLACE needs capabilities.can_sit"),
    ("quadruped.yaml", "  can_gesture: true", "  can_gesture: false",
     "gestures are listed but capabilities.can_gesture is false"),
    ("quadruped.yaml", "reach_m: 0.0", "reach_m: 0.5", "reach_m is 0.5 but the body has no arm"),
    ("quadruped.yaml", "expression_channels: [SPEECH, LIGHT]", "expression_channels: [LIGHT]",
     "expression channel SPEECH and capabilities.can_speak must agree"),
    ("quadruped.yaml", "mount_height_m: 0.55", "mount_height_m: 0.9", "is above the body's height"),
    ("quadruped_arm.yaml", "  can_grab: true", "  can_grab: false", "gesture HAND_OVER needs capabilities.can_grab"),
    ("legged_humanoid.yaml", "collider: {shape: CAPSULE, length_m: 0.56, width_m: 0.56}",
     "collider: {shape: CAPSULE, length_m: 0.9, width_m: 0.56}", "a CAPSULE is round, so length_m must equal width_m"),
])
def test_body_contradictions_are_reported(config_copy, file, old, new, expected):  # noqa: F811
    path = config_copy / "bodies" / file
    _edit(path, old, new)
    messages = _messages(config_copy)
    assert any(expected in m and file in m for m in messages), messages


def test_tick_hz_must_divide_60(config_copy):  # noqa: F811
    _edit(config_copy / "scenarios" / "SB05_RAMP_VS_STAIRS.yaml", "tick_hz: 10", "tick_hz: 7")
    assert any("tick_hz 7 must divide 60" in m for m in _messages(config_copy))


def test_sb05_casts_one_robot_r_per_body_family():
    config_set, _ = load_and_check()
    cast = config_set.items["scenarios"]["SB05_RAMP_VS_STAIRS"]["cast"]
    assert {entry["persona"] for entry in cast.values()} == {"robot_r"}
    assert sorted(entry["body"] for entry in cast.values()) == ["legged_humanoid", "quadruped", "wheeled_humanoid"]


# ---------- rig step A (D-54, D-56): skeletons are presentation; these rules keep the rig block honest ----------

# The same joint names Godot builds (godot_app/tests/test_main.gd, EXPECTED_JOINTS).
EXPECTED_JOINTS = {
    "legged_humanoid": ["AnkleL", "AnkleR", "ElbowL", "ElbowR", "FingersL", "FingersR", "HipL", "HipR",
                        "KneeL", "KneeR", "Neck", "ShoulderL", "ShoulderR", "SpineLower", "SpineUpper", "ThumbL",
                        "ThumbR", "ToeL", "ToeR", "WristL", "WristR"],
    "wheeled_humanoid": ["ElbowL", "ElbowR", "FingersL", "FingersR", "Neck", "ShoulderL", "ShoulderR",
                         "SpineLower", "SpineUpper", "ThumbL", "ThumbR", "TorsoMount", "WristL", "WristR"],
    "quadruped": ["HipAbdBL", "HipAbdBR", "HipAbdFL", "HipAbdFR", "HipFlexBL", "HipFlexBR", "HipFlexFL",
                  "HipFlexFR", "KneeBL", "KneeBR", "KneeFL", "KneeFR", "Neck"],
    "quadruped_arm": ["ArmBase", "ArmElbow", "ArmShoulder", "ArmWrist", "Gripper", "HipAbdBL", "HipAbdBR",
                      "HipAbdFL", "HipAbdFR", "HipFlexBL", "HipFlexBR", "HipFlexFL", "HipFlexFR", "KneeBL",
                      "KneeBR", "KneeFL", "KneeFR", "Neck"],
}


@pytest.mark.parametrize("body_id", ROBOTS)
def test_rig_joints_match_godot(body, body_id):
    assert sorted(rules.rig_joints(body[body_id])) == EXPECTED_JOINTS[body_id]


def test_visitors_have_no_rig_yet(body):
    assert rules.rig_settings(body["human_walker"]) is None
    assert rules.rig_joints(body["human_walker"]) == {}


def test_rig_defaults_without_a_rig_block(body):
    plain = {k: v for k, v in body["quadruped_arm"].items() if k != "rig"}
    rig = rules.rig_settings(plain)
    assert rig["skeleton"] == "QUADRUPED" and rig["arm_module"] is True
    assert rig["gesture_tempo"] == {"min": 0.5, "max": 1.5}
    assert not rules.body_problems(plain)


# Same numbers as Godot's EXPECTED_DURATIONS: half a tick rounds up on both sides.
@pytest.mark.parametrize("tempo, ticks", [(0.5, 180), (0.8, 113), (1.0, 90), (1.2, 75), (1.5, 60), (None, 90)])
def test_gesture_duration_from_tempo(tempo, ticks):
    assert rules.gesture_duration_ticks(tempo) == ticks


def test_prosody_is_clamped_to_the_body_range(body):
    arm = body["quadruped_arm"]
    assert rules.clamp_prosody(arm, "tempo", 1.5) == 1.3
    assert rules.clamp_prosody(arm, "tempo", 0.5) == 0.7
    assert rules.clamp_prosody(arm, "amplitude", 1.5) == 1.5
    assert rules.clamp_prosody(arm, "tempo", None) is None


@pytest.mark.parametrize("file, old, new, expected", [
    ("legged_humanoid.yaml", "  skeleton: HUMANOID", "  skeleton: QUADRUPED", "rig.skeleton QUADRUPED does not fit kind"),
    ("legged_humanoid.yaml", "  skeleton: HUMANOID", "  skeleton: HUMANOID\n  arm_module: true",
     "rig.arm_module needs a quadruped with arms >= 1"),
    ("quadruped_arm.yaml", "  arm_module: true", "  arm_module: false", "its arm gestures could not be shown"),
    ("quadruped.yaml", "  skeleton: QUADRUPED", "  skeleton: QUADRUPED\n  joint_limits_deg: {Neck: {yaw: [-90, 90]}}",
     "head yaw is at most +/-85 degrees"),
    ("quadruped.yaml", "  skeleton: QUADRUPED", "  skeleton: QUADRUPED\n  joint_limits_deg: {ShoulderL: {pitch: [0, 90]}}",
     "ShoulderL is not a joint of this skeleton"),
    ("quadruped.yaml", "  skeleton: QUADRUPED", "  skeleton: QUADRUPED\n  joint_limits_deg: {Neck: {flex: [0, 10]}}",
     "Neck has no axis flex"),
    ("quadruped.yaml", "  skeleton: QUADRUPED", "  skeleton: QUADRUPED\n  joint_limits_deg: {Neck: {pitch: [20, 10]}}",
     "min 20 is above max 10"),
    ("wheeled_humanoid.yaml", "  gesture_tempo: {min: 0.5, max: 1.5}", "  gesture_tempo: {min: 1.1, max: 1.5}",
     "rig.gesture_tempo: the range 1.1-1.5 must include 1"),
    ("human_walker.yaml", "expression_channels:", "rig: {skeleton: HUMANOID}\nexpression_channels:",
     "have no skeleton yet"),
])
def test_rig_contradictions_are_reported(config_copy, file, old, new, expected):  # noqa: F811
    _edit(config_copy / "bodies" / file, old, new)
    messages = _messages(config_copy)
    assert any(expected in m and file in m for m in messages), messages


def test_rig_ranges_outside_the_contract_fail_the_schema(config_copy):  # noqa: F811
    _edit(config_copy / "bodies" / "quadruped.yaml", "  gesture_amplitude: {min: 0.5, max: 1.5}",
          "  gesture_amplitude: {min: 0.5, max: 2.0}")
    assert any("quadruped.yaml" in m for m in _messages(config_copy))
