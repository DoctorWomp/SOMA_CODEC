class_name RigSpec
extends RefCounted
## Skeleton families, joint axes and joint limits (D-54, D-56; docs/gates/RIG_PLAN.md), read
## together with a body config's optional `rig` block. Pose is presentation only: nothing here
## changes the collider, movement, senses or journal.
##
## Python states the same joint names and axes in range_service/bodies.py (the validator rejects
## unknown overrides), and both sides pin the gesture duration rule in their tests.
##
## Every joint angle is in radians, applied as rotations about the bone's own axes in the order
## listed in AXES (outermost first). Bones rest with no rotation, so an angle of 0 everywhere is
## the zero pose: humanoid arms and legs straight down, quadruped legs straight down, the arm
## module pointing straight back along the rail. Signs, for the right side (left mirrors):
##
## - yaw: + turns left (as yaw_rad, D-29). pitch on spine and neck: + bends or looks down.
## - roll on spine and neck: + leans or tilts to the right. Shoulder/hip roll: + away from the body.
## - Shoulder/hip pitch: + swings the limb forward. Elbow flex: + bends the forearm forward.
##   Knee flex (humanoid): + bends the shin back. Quadruped HipFlex and Knee: + swings back.
## - Quadruped Body (no neck, like current robot dogs; owner 2026-11-16): yaw + turns left, pitch +
##   noses down, roll + drops the right side. The legs make it, feet planted (Poser).
## - Arm module: ArmShoulder pitch + lifts the arm up and over toward the front, ArmElbow flex +
##   folds the same way, ArmWrist pitch likewise; Gripper open 0 is closed.

const GESTURE_BASE_TICKS := 90          # a gesture lasts 1.5 s at tempo 1 (was Avatar.GESTURE_DURATION_TICKS)
const PROSODY_MIN := 0.5
const PROSODY_MAX := 1.5
const HEAD_YAW_LIMIT_DEG := 85.0

## Rotation axes per joint kind: [axis name, local axis for the right side or the middle].
const AXES := {
	"Spine": [["yaw", Vector3.UP], ["pitch", Vector3.LEFT], ["roll", Vector3.FORWARD]],
	"Neck": [["yaw", Vector3.UP], ["pitch", Vector3.LEFT], ["roll", Vector3.FORWARD]],
	"TorsoMount": [["yaw", Vector3.UP], ["pitch", Vector3.LEFT], ["roll", Vector3.FORWARD]],
	"Shoulder": [["pitch", Vector3.RIGHT], ["roll", Vector3.BACK], ["yaw", Vector3.UP]],
	"Elbow": [["flex", Vector3.RIGHT]],
	"Wrist": [["roll", Vector3.UP], ["pitch", Vector3.RIGHT]],
	"Fingers": [["curl", Vector3.FORWARD]],
	"Thumb": [["curl", Vector3.FORWARD]],
	"Hip": [["pitch", Vector3.RIGHT], ["roll", Vector3.BACK], ["yaw", Vector3.UP]],
	"Knee": [["flex", Vector3.LEFT]],
	"Ankle": [["pitch", Vector3.RIGHT], ["roll", Vector3.BACK]],
	"Toe": [["flex", Vector3.RIGHT]],
	"HipAbd": [["abduct", Vector3.BACK]],
	"HipFlex": [["flex", Vector3.LEFT]],
	"QuadKnee": [["flex", Vector3.LEFT]],
	"BodyPose": [["yaw", Vector3.UP], ["pitch", Vector3.LEFT], ["roll", Vector3.FORWARD]],
	"ArmBase": [["yaw", Vector3.UP]],
	"ArmShoulder": [["pitch", Vector3.LEFT]],
	"ArmElbow": [["flex", Vector3.LEFT]],
	"ArmWrist": [["pitch", Vector3.LEFT], ["yaw", Vector3.UP], ["roll", Vector3.BACK]],
	"Gripper": [["open", Vector3.UP]],
}

## Default limits in degrees (RIG_PLAN.md joint tables; starting values). Changes from the plan,
## recorded in D-56: the quadruped has no neck; its whole body poses over planted feet instead
## (owner, 2026-11-16), and ArmElbow folds to 170 so the stowed arm lies flat on the back as before.
const LIMITS_DEG := {
	"SpineLower": {"yaw": [-45, 45], "pitch": [-30, 30], "roll": [-30, 30]},
	"SpineUpper": {"yaw": [-45, 45], "pitch": [-25, 25], "roll": [-25, 25]},
	"Neck": {"yaw": [-85, 85], "pitch": [-40, 60], "roll": [-30, 30]},
	"TorsoMount": {"yaw": [-90, 90], "pitch": [-20, 20], "roll": [-10, 10]},
	"Shoulder": {"pitch": [-60, 180], "roll": [-90, 90], "yaw": [-90, 90]},
	"Elbow": {"flex": [0, 145]},
	"Wrist": {"roll": [-90, 90], "pitch": [-70, 70]},
	"Fingers": {"curl": [0, 90]},
	"Thumb": {"curl": [0, 90]},
	"Hip": {"pitch": [-30, 120], "roll": [-30, 30], "yaw": [-45, 45]},
	"Knee": {"flex": [0, 140]},
	"Ankle": {"pitch": [-40, 40], "roll": [-20, 20]},
	"Toe": {"flex": [0, 40]},
	"HipAbd": {"abduct": [-35, 35]},
	"HipFlex": {"flex": [-60, 120]},
	"QuadKnee": {"flex": [-150, 0]},
	"BodyPose": {"yaw": [-15, 15], "pitch": [-15, 15], "roll": [-15, 15]},
	"ArmBase": {"yaw": [-170, 170]},
	"ArmShoulder": {"pitch": [-10, 150]},
	"ArmElbow": {"flex": [0, 170]},
	"ArmWrist": {"pitch": [-90, 90], "yaw": [-90, 90], "roll": [-170, 170]},
	"Gripper": {"open": [0, 60]},
}

const LEGS := ["FL", "FR", "BL", "BR"]


## The rig settings for a body: {"family", "arm_module", "joints": {joint: {"kind", "side",
## "axes": [[axis, Vector3]], "limits": {axis: Vector2 (radians)}}}, "head_turn_speed" (rad/s),
## "amplitude": Vector2, "tempo": Vector2}. Empty for bodies without a skeleton yet (visitors).
static func for_body(body: Dictionary) -> Dictionary:
	var kind := String(body.get("kind", ""))
	var family := ""
	match kind:
		"LEGGED_HUMANOID", "WHEELED_HUMANOID":
			family = "HUMANOID"
		"QUADRUPED":
			family = "QUADRUPED"
		_:
			return {}
	var rig: Dictionary = body.get("rig", {})
	var arm_module := bool(rig.get("arm_module", family == "QUADRUPED" and int(body.get("arms", 0)) > 0))
	var joints := {}
	if family == "HUMANOID":
		for j in ["SpineLower", "SpineUpper"]:
			_add(joints, j, "Spine", "", j)
		_add(joints, "Neck", "Neck", "", "Neck")
		for side in ["L", "R"]:
			for j in ["Shoulder", "Elbow", "Wrist", "Fingers", "Thumb"]:
				_add(joints, j + side, j, side, j)
			if kind == "LEGGED_HUMANOID":
				for j in ["Hip", "Knee", "Ankle", "Toe"]:
					_add(joints, j + side, j, side, j)
		if kind == "WHEELED_HUMANOID":
			_add(joints, "TorsoMount", "TorsoMount", "", "TorsoMount")
	else:
		_add(joints, "Body", "BodyPose", "", "BodyPose")
		for leg in LEGS:
			var side := "L" if String(leg).ends_with("L") else "R"
			_add(joints, "HipAbd" + leg, "HipAbd", side, "HipAbd")
			_add(joints, "HipFlex" + leg, "HipFlex", side, "HipFlex")
			_add(joints, "Knee" + leg, "QuadKnee", side, "QuadKnee")
	if arm_module:
		for j in ["ArmBase", "ArmShoulder", "ArmElbow", "ArmWrist", "Gripper"]:
			_add(joints, j, j, "", j)
	var overrides: Dictionary = rig.get("joint_limits_deg", {})
	for joint_name in overrides:
		if not joints.has(joint_name):
			push_error("RigSpec: %s has no joint %s" % [body.get("body_id", "?"), joint_name])
			continue
		for axis in overrides[joint_name]:
			var pair: Array = overrides[joint_name][axis]
			joints[joint_name]["limits"][axis] = Vector2(deg_to_rad(float(pair[0])), deg_to_rad(float(pair[1])))
	var default_speed := 180.0 if family == "HUMANOID" else 90.0   # a quadruped turns its whole body
	return {
		"family": family,
		"base": "LEGS" if kind == "LEGGED_HUMANOID" else ("WHEELS" if kind == "WHEELED_HUMANOID" else "QUADRUPED"),
		"arm_module": arm_module,
		"joints": joints,
		# With a neck the head is world state and turns at the head block's speed (G3e, D-72).
		"head_turn_speed": deg_to_rad(float(body.get("head", {}).get("turn_speed_deg_s",
			rig.get("head_turn_speed_deg_s", default_speed)))),
		"amplitude": _range(rig.get("gesture_amplitude", {})),
		"tempo": _range(rig.get("gesture_tempo", {})),
	}


static func _add(joints: Dictionary, joint_name: String, axes_kind: String, side: String, limits_kind: String) -> void:
	var axes := []
	for a in AXES[axes_kind]:
		var v: Vector3 = a[1]
		if side == "L":
			v = Vector3(v.x, -v.y, -v.z)   # mirror across the body's middle plane
		axes.append([String(a[0]), v])
	var limits := {}
	var table: Dictionary = LIMITS_DEG[limits_kind]
	for axis in table:
		limits[axis] = Vector2(deg_to_rad(float(table[axis][0])), deg_to_rad(float(table[axis][1])))
	joints[joint_name] = {"kind": axes_kind, "side": side, "axes": axes, "limits": limits}


static func _range(r: Dictionary) -> Vector2:
	return Vector2(float(r.get("min", PROSODY_MIN)), float(r.get("max", PROSODY_MAX)))


## A gesture's amplitude or tempo after the body's limits. `value` < 0 means "not given" (1).
static func clamp_prosody(spec: Dictionary, key: String, value: float) -> float:
	if value < 0.0:
		return 1.0
	var r: Vector2 = spec.get(key, Vector2(PROSODY_MIN, PROSODY_MAX)) if not spec.is_empty() else Vector2(PROSODY_MIN, PROSODY_MAX)
	return clampf(value, r.x, r.y)


## How long a gesture event lasts, in ticks, for an already clamped tempo (D-56). The world owns
## this number; the animation fits inside it.
static func gesture_duration_ticks(tempo: float) -> int:
	return roundi(GESTURE_BASE_TICKS / tempo)
