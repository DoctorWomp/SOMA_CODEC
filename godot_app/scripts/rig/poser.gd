class_name Poser
extends RefCounted
## Poses a robot's skeleton from world state, once per physics tick (D-54, D-56; RIG_PLAN.md).
## Presentation only: it reads the avatar (position, facing, its gesture event, its gaze target)
## and writes bone poses; nothing in the world reads them back. Layers, in order:
##
## 1. Locomotion: wheels spin from the body's measured travel and turn (never from the
##    requested speed), so a robot pushing against a wall does not spin its wheels. Gaits are
##    rig step B; legged bodies keep their standing pose.
## 2. Posture: a slight lean with acceleration (spine, or the wheeled torso mount), BOW, and the
##    quadruped's SIT_IN_PLACE (the body tips back about its front hips, the hind legs fold with
##    their feet planted).
## 3. Gesture: one-shot tracks on the arms, head or spine for the gesture the world is showing,
##    fitted inside the world's duration: attack, hold, release. Arm gestures use analytic
##    two-bone IK so the hand reaches the sense model's HAND point (SenseModel.gesture_point) at
##    the gesture's peak, halfway through. Amplitude scales the swing; tempo is already in the
##    duration. A gesture that replaces one still showing cross-fades from it.
## 4. Gaze: with a neck (G3e, D-72) the head is world state: the Neck joint shows the avatar's
##    simulated head yaw and pitch (Avatar.head_yaw / head_pitch) and never drives it. Without one
##    the head turns toward the gaze target at the body's head speed, within its joint limits
##    (head yaw at most ±85°).
##
## The quadruped has no neck, like current robot dogs (owner, 2026-11-16). Its gaze and HEAD_TILT
## are whole-body poses: the Body joint turns, pitches and rolls the body over planted feet, and
## leg IK (hip abduction, hip flex, knee) makes the left and right legs work asymmetrically to
## hold it, as a real chassis would.
##
## Every layer stays inside the joint limits by design; Rig counts any clamp and the tests
## require none.

const ATTACK := 0.25           # fractions of the gesture's world duration
const RELEASE := 0.25
const HOLD := 1.0 - ATTACK - RELEASE
const LEAN_ACCEL_RAD := 0.05   # forward lean at full acceleration (about 3°)
const LEAN_SPEED_RAD := 0.03   # forward lean at full speed
const LEAN_FOLLOW := 0.12      # per tick
const IK_PASSES := 4
## A leg is never stretched further than this share of its full length: when the body rolls or
## pitches, it is lowered just enough (a slight crouch), as a real robot dog would.
const LEG_REACH := 0.96
## Humanoid hand targets are the sense model's points; the raised hand sits 4 cm in front of
## it so the shoulder stays away from its pitch limit (well inside the 10 cm the test allows).
const RAISED_FORWARD_M := 0.04
## Elbow directions (right side, in the chest's frame): out and forward for raised hands, down,
## out and back for hands held forward.
const POLE_RAISED := Vector3(0.6, -0.3, -0.7)
const POLE_FORWARD := Vector3(0.3, -1.0, 0.4)
## Quadruped arm: gripper direction in the arm's plane (degrees: 90 up, 180 forward) per gesture.
const GRIPPER_AXIS_DEG := {"WAVE": 120.0, "BECKON": 130.0, "RAISED_HAND": 110.0, "POINT": 180.0, "HAND_OVER": 190.0}
const GRIPPER_OPEN_DEG := {"WAVE": 30.0, "BECKON": 20.0, "RAISED_HAND": 55.0, "POINT": 0.0, "HAND_OVER": 25.0}

var rig: Rig
var model: Node3D
var family := ""
var base := ""
## Gaze after the head-speed limit: x yaw (+ left), y pitch (+ down), radians.
var head := Vector2.ZERO
var lean := 0.0
var sit_weight := 0.0
var last_tick := -1
var _prev_pos := Vector3.ZERO
var _prev_yaw := 0.0
var _prev_v := 0.0
var _has_prev := false


func _init(target_rig: Rig, target_model: Node3D) -> void:
	rig = target_rig
	model = target_model
	family = String(rig.spec["family"])
	base = String(rig.spec["base"])


# ---------- the rest pose ----------

## Quadruped standing pose: legs solved so each foot is on its design point; arm stowed.
func stand_pose() -> void:
	var pose := {}
	for leg in RigSpec.LEGS:
		_leg_ik(leg, Transform3D.IDENTITY, pose)
	if rig.has_joint("ArmBase"):
		var up := QuadrupedModel.ARM_STOWED_ELBOW - QuadrupedModel.ARM_SHOULDER
		var shoulder := atan2(up.y, up.z)                       # from pointing back, toward up
		var fore := QuadrupedModel.ARM_STOWED_WRIST - QuadrupedModel.ARM_STOWED_ELBOW
		var fore_abs := atan2(fore.y, fore.z)
		if fore_abs < 0.0:
			fore_abs += TAU
		pose["ArmShoulder"] = {"pitch": shoulder}
		pose["ArmElbow"] = {"flex": fore_abs - shoulder}
		pose["ArmWrist"] = {"pitch": deg_to_rad(QuadrupedModel.GRIPPER_STOWED_WRIST_DEG), "yaw": 0.0, "roll": 0.0}
		pose["Gripper"] = {"open": 0.0}
	rig.set_angles(pose)


# ---------- per tick ----------

func update(avatar: Avatar, tick: int) -> void:
	var dt := 1.0 / SimClock.TICK_HZ
	last_tick = tick
	var pose := rig.rest_angles()
	var motion := _measure(avatar, dt)
	_spin_wheels(motion, dt)
	_lean(avatar, motion, pose)
	var shown := avatar.gesture_layers(tick)
	_posture(shown, pose)
	if family == "QUADRUPED":
		# The body pose first: the legs hold it, and the arm aims from it.
		_gaze(avatar, tick, dt, pose)
		_head_gestures(shown, pose)
		_clamp_look(pose)
		# Sitting owns the body: other body poses fade out while it sits.
		for axis in pose["Body"]:
			pose["Body"][axis] = float(pose["Body"][axis]) * (1.0 - sit_weight)
		_legs_hold_body(pose)
	rig.set_angles(pose)
	rig.apply(false)
	_gesture_layer(avatar, shown, pose)
	if family == "HUMANOID":
		_gaze(avatar, tick, dt, pose)
		_head_gestures(shown, pose)
		_clamp_look(pose)
	rig.set_angles(pose)
	rig.apply()


func _measure(avatar: Avatar, dt: float) -> Dictionary:
	var pos := avatar.global_position
	var yaw := avatar.rotation.y
	var v := 0.0
	var w := 0.0
	if _has_prev:
		var fwd := SenseModel.forward_of(avatar)
		v = Vector2(pos.x - _prev_pos.x, pos.z - _prev_pos.z).dot(Vector2(fwd.x, fwd.z)) / dt
		w = wrapf(yaw - _prev_yaw, -PI, PI) / dt
	var a := (v - _prev_v) / dt if _has_prev else 0.0
	_prev_pos = pos
	_prev_yaw = yaw
	_prev_v = v
	_has_prev = true
	return {"v": v, "w": w, "a": a}


## Wheels roll with the measured forward speed; turning, the right side runs faster for a left
## turn (skid steer). Never sideways (D-33: the body only moves along its facing).
func _spin_wheels(motion: Dictionary, dt: float) -> void:
	for wheel in rig.spin:
		var side := 1.0 if String(wheel).ends_with("R") else -1.0
		var surface := float(motion["v"]) + side * float(motion["w"]) * HumanoidModel.WHEEL_TRACK_M / 2.0
		rig.spin[wheel] = wrapf(float(rig.spin[wheel]) - surface * dt / HumanoidModel.WHEEL_RADIUS_M, -PI, PI)


func _lean(avatar: Avatar, motion: Dictionary, pose: Dictionary) -> void:
	if family != "HUMANOID":
		return
	var target := LEAN_ACCEL_RAD * clampf(float(motion["a"]) / avatar.max_accel, -1.0, 1.0) \
		+ LEAN_SPEED_RAD * clampf(float(motion["v"]) / avatar.max_speed, -1.0, 1.0)
	lean += (target - lean) * LEAN_FOLLOW
	var joint := "TorsoMount" if base == "WHEELS" else "SpineLower"
	pose[joint]["pitch"] = float(pose[joint]["pitch"]) + lean


# ---------- gesture timing ----------

## Envelope weight at normalized time t (0..1 over the world duration): 0 at both ends.
static func envelope(t: float) -> float:
	if t <= 0.0 or t >= 1.0:
		return 0.0
	return smoothstep(0.0, ATTACK, t) * (1.0 - smoothstep(1.0 - RELEASE, 1.0, t))


## A swing with `cycles` periods over the hold, crossing zero at the peak (t = 0.5).
static func swing(t: float, cycles: float) -> float:
	return sin(TAU * cycles * (t - 0.5) / HOLD)


static func progress(g: Dictionary, tick: int) -> float:
	return float(tick - int(g["start_tick"])) / float(g["duration"])


# ---------- posture ----------

func _posture(shown: Array, pose: Dictionary) -> void:
	rig.root_pose = Transform3D.IDENTITY
	sit_weight = 0.0
	for layer in shown:
		var g: Dictionary = layer["gesture"]
		var w := float(layer["weight"]) * envelope(float(layer["t"]))
		var amp := float(g["amplitude"])
		match String(g["gesture"]):
			"BOW":
				if family == "HUMANOID":
					_add(pose, "SpineLower", "pitch", deg_to_rad(14.0) * amp * w)
					_add(pose, "SpineUpper", "pitch", deg_to_rad(10.0) * amp * w)
					if base == "WHEELS":
						_add(pose, "TorsoMount", "pitch", deg_to_rad(8.0) * amp * w)
			"SIT_IN_PLACE":
				if family == "QUADRUPED":
					sit_weight = maxf(sit_weight, w)
					_sit(deg_to_rad(15.0) * amp * w)


## The body tips back about the front hips by `angle` (the legs then fold with feet planted).
func _sit(angle: float) -> void:
	var pivot := Vector3(0, QuadrupedModel.HIP_Y, -QuadrupedModel.LEG_Z)
	var r := Transform3D(Basis(Vector3.RIGHT, angle), Vector3.ZERO)
	rig.root_pose = Transform3D(Basis.IDENTITY, pivot) * r * Transform3D(Basis.IDENTITY, -pivot)


## Solve the legs for the body pose. If they cannot hold it inside their joint limits, the body
## does proportionally less (a short search for the largest share that fits), as a real
## controller would: the feet stay planted and no leg joint is pushed past its limit.
func _legs_hold_body(pose: Dictionary) -> void:
	var wanted: Dictionary = pose["Body"].duplicate()
	if not _legs_fit(wanted, pose):
		var lo := 0.0
		var hi := 1.0
		for i in 8:
			var mid := (lo + hi) / 2.0
			if _legs_fit(_scaled(wanted, mid), {}):
				lo = mid
			else:
				hi = mid
		pose["Body"] = _scaled(wanted, lo)
		_legs_fit(pose["Body"], pose)


static func _scaled(angles: Dictionary, k: float) -> Dictionary:
	var out := {}
	for axis in angles:
		out[axis] = float(angles[axis]) * k
	return out


## Leg IK for these Body angles into `into` (if given); true if every leg angle is in its limits.
func _legs_fit(body_angles: Dictionary, into: Dictionary) -> bool:
	var trial := {}
	var body := _fit_body(body_angles)
	for leg in RigSpec.LEGS:
		_leg_ik(leg, body, trial)
	var ok := true
	for joint_name in trial:
		for axis in trial[joint_name]:
			var lim := rig.limits(joint_name, axis)
			var v := float(trial[joint_name][axis])
			if v < lim.x or v > lim.y:
				ok = false
	if not into.is_empty():
		for joint_name in trial:
			into[joint_name] = trial[joint_name]
	return ok


## The body transform for these Body angles, lowered just enough that every foot stays in reach.
func _fit_body(body_angles: Dictionary) -> Transform3D:
	var q := model as QuadrupedModel
	var reach := (q.upper_leg_m + q.lower_leg_m) * LEG_REACH
	rig.body_drop = 0.0
	var body := rig.body_transform(body_angles)
	var drop := 0.0
	for leg in RigSpec.LEGS:
		var hip := body * rig.offset_of("HipAbd" + leg)
		var foot := q.foot_point(leg)
		var flat := Vector2(hip.x - foot.x, hip.z - foot.z).length()
		var rise := hip.y - foot.y
		if flat < reach:
			drop = maxf(drop, rise - sqrt(reach * reach - flat * flat))
	rig.body_drop = maxf(drop, 0.0)
	return rig.body_transform(body_angles)


## Leg IK with the foot held on its spot whatever the body does: HipAbd swings the leg out or in
## so the foot lies in the leg's plane, then two-bone IK in that plane for HipFlex and Knee
## (+ swings back), knee behind the hip-foot line.
func _leg_ik(leg: String, body: Transform3D, pose: Dictionary) -> void:
	var q := model as QuadrupedModel
	var hip_rest := rig.offset_of("HipAbd" + leg)
	var foot_local := body.basis.inverse() * (q.foot_point(leg) - body * hip_rest)
	var outward := -1.0 if leg.ends_with("L") else 1.0
	var abduct := atan2(outward * foot_local.x, -foot_local.y)
	var drop := -Vector2(foot_local.x, foot_local.y).length()   # the foot's height in the abducted plane
	var a := q.upper_leg_m
	var b := q.lower_leg_m
	var d := clampf(Vector2(foot_local.z, drop).length(), absf(a - b) + 1e-4, a + b - 1e-4)
	var gamma := atan2(foot_local.z, -drop)
	var alpha := acos(clampf((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0))
	var hip_angle := gamma + alpha
	var knee := Vector2(a * sin(hip_angle), -a * cos(hip_angle))
	var to_foot := Vector2(d * sin(gamma), -d * cos(gamma)) - knee
	var lower_angle := atan2(to_foot.x, -to_foot.y)
	pose["HipAbd" + leg] = {"abduct": abduct}
	pose["HipFlex" + leg] = {"flex": hip_angle}
	pose["Knee" + leg] = {"flex": lower_angle - hip_angle}


# ---------- gestures ----------

func _gesture_layer(avatar: Avatar, shown: Array, pose: Dictionary) -> void:
	for layer in shown:
		var g: Dictionary = layer["gesture"]
		var t := float(layer["t"])
		var w := float(layer["weight"]) * envelope(t)
		if w <= 0.0:
			continue
		var gesture := String(g["gesture"])
		var target := {}
		if family == "HUMANOID":
			target = _humanoid_arm(avatar, gesture, t, float(g["amplitude"]))
		elif rig.has_joint("ArmBase"):
			target = _quadruped_arm(avatar, gesture, t, float(g["amplitude"]))
		_blend(pose, target, w)


static func _blend(pose: Dictionary, target: Dictionary, w: float) -> void:
	for joint_name in target:
		for axis in target[joint_name]:
			pose[joint_name][axis] = lerpf(float(pose[joint_name][axis]), float(target[joint_name][axis]), w)


static func _add(pose: Dictionary, joint_name: String, axis: String, value: float) -> void:
	pose[joint_name][axis] = float(pose[joint_name][axis]) + value


## The hand point the sense model uses for `gesture`, in model (skeleton) space.
func _sense_hand(avatar: Avatar, gesture: String) -> Vector3:
	var pts := SenseModel.sample_points(avatar, gesture)
	return model.to_local(pts["HAND"])


## Right-arm targets for the humanoid hand gestures, as joint angles ({} for other gestures).
func _humanoid_arm(avatar: Avatar, gesture: String, t: float, amp: float) -> Dictionary:
	var raised := SenseModel.RAISED_HAND_GESTURES.has(gesture)
	if not raised and not SenseModel.FORWARD_HAND_GESTURES.has(gesture):
		return {}
	var hand := _sense_hand(avatar, gesture)
	if raised:
		hand += Vector3(0, 0, -RAISED_FORWARD_M)
	var wrist := {"roll": 0.0, "pitch": 0.0}
	var fingers := 0.0
	var thumb := deg_to_rad(15.0)
	match gesture:
		"WAVE":
			hand += Vector3(0.10 * amp * swing(t, 2.0), 0, 0)
			wrist["roll"] = deg_to_rad(-60.0)
		"SMALL_WAVE":
			hand += Vector3(0.035 * amp * swing(t, 3.0), 0, 0)
			wrist["roll"] = deg_to_rad(-60.0)
			wrist["pitch"] = deg_to_rad(15.0) * amp * swing(t, 3.0)
		"RAISED_HAND":
			wrist["roll"] = deg_to_rad(-70.0)
		"BECKON":
			wrist["roll"] = deg_to_rad(-20.0)
			fingers = deg_to_rad(45.0 + 40.0 * minf(amp, 1.5) / 1.5 * swing(t, 2.5))
			wrist["pitch"] = deg_to_rad(18.0) * amp * swing(t, 2.5)
		"POINT":
			thumb = deg_to_rad(40.0)
		"OPEN_PALM":
			wrist["pitch"] = -deg_to_rad(50.0 + 15.0 * (clampf(amp, 0.5, 1.5) - 0.5))   # hand up: "one moment"
			thumb = deg_to_rad(5.0)
		"HAND_OVER":
			wrist["roll"] = deg_to_rad(80.0)
			fingers = deg_to_rad(25.0)
	var out := _arm_ik("R", hand, POLE_RAISED if raised else POLE_FORWARD, wrist)
	out["FingersR"] = {"curl": fingers}
	out["ThumbR"] = {"curl": thumb}
	return out


## Two-bone IK for a humanoid arm: the hand centre (not the wrist) reaches `hand` (model space).
## Shoulder angles follow RigSpec's order (pitch, roll, yaw), solved in the chest's frame.
func _arm_ik(side: String, hand: Vector3, pole: Vector3, wrist: Dictionary) -> Dictionary:
	var mirror := -1.0 if side == "L" else 1.0
	var chest := rig.bone_global("SpineUpper")
	var target := chest.affine_inverse() * hand
	target.x *= mirror                                  # solve as a right arm
	var s := rig.offset_of("Shoulder" + side) * Vector3(mirror, 1, 1)
	var a := rig.offset_of("Elbow" + side).length()
	var b := rig.offset_of("Wrist" + side).length()
	var hand_offset := Vector3(0, -0.045, 0)
	var wrist_basis := Basis(Vector3.UP, float(wrist["roll"])) * Basis(Vector3.RIGHT, float(wrist["pitch"]))
	var aim := target
	var result := {}
	for i in IK_PASSES:
		var sol := _two_bone(s, aim, a, b, pole.normalized())
		var shoulder_b := Basis(Vector3.RIGHT, sol["pitch"]) * Basis(Vector3.BACK, sol["roll"]) * Basis(Vector3.UP, sol["yaw"])
		var fore_b := shoulder_b * Basis(Vector3.RIGHT, sol["flex"])
		var wrist_p := s + shoulder_b * Vector3(0, -a, 0) + fore_b * Vector3(0, -b, 0)
		var reached := wrist_p + (fore_b * wrist_basis) * hand_offset
		aim += target - reached
		result = sol
	return {
		"Shoulder" + side: {"pitch": result["pitch"], "roll": result["roll"], "yaw": result["yaw"]},
		"Elbow" + side: {"flex": result["flex"]},
		"Wrist" + side: {"roll": wrist["roll"], "pitch": wrist["pitch"]},
	}


## Shoulder at `s`, wrist to `w`: upper arm `a`, forearm `b`, elbow toward `pole`. Returns the
## shoulder's pitch, roll, yaw and the elbow's flex (radians), for a right arm.
static func _two_bone(s: Vector3, w: Vector3, a: float, b: float, pole: Vector3) -> Dictionary:
	var v := w - s
	var d := clampf(v.length(), absf(a - b) + 1e-4, a + b - 1e-4)
	v = v.normalized()
	var alpha := acos(clampf((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0))
	var q := (pole - v * pole.dot(v)).normalized()
	var elbow := s + (v * cos(alpha) + q * sin(alpha)) * a
	var u := (elbow - s).normalized()
	var f := ((s + v * d) - elbow).normalized()
	var flex := acos(clampf(u.dot(f), -1.0, 1.0))
	var roll := asin(clampf(u.x, -1.0, 1.0))
	var pitch := atan2(-u.z, -u.y)
	var yaw := 0.0
	if flex > 1e-4:
		var hinge := u.cross(f).normalized()
		var outer := Basis(Vector3.RIGHT, pitch) * Basis(Vector3.BACK, roll)
		yaw = atan2(-hinge.dot(outer * Vector3.BACK), hinge.dot(outer * Vector3.RIGHT))
	return {"pitch": pitch, "roll": roll, "yaw": yaw, "flex": flex}


## The quadruped's arm: base yaw toward the target, planar IK for shoulder and elbow, wrist
## pitch sets the gripper's direction. Angles measured in the arm's plane from pointing back
## (0) through up (90°) to forward (180°).
func _quadruped_arm(avatar: Avatar, gesture: String, t: float, amp: float) -> Dictionary:
	if not GRIPPER_AXIS_DEG.has(gesture):
		return {}
	var q := model as QuadrupedModel
	var hand := rig.bone_global("Body").affine_inverse() * _sense_hand(avatar, gesture)
	var shoulder := rig.rest_position("ArmShoulder")
	var rel := hand - shoulder
	var yaw := atan2(-rel.x, -rel.z)
	var fwd := Vector2(rel.x, rel.z).length()
	var axis := deg_to_rad(float(GRIPPER_AXIS_DEG[gesture]))
	var wrist_pitch_extra := 0.0
	var open := deg_to_rad(float(GRIPPER_OPEN_DEG[gesture]))
	match gesture:
		"WAVE":
			yaw += deg_to_rad(14.0) * amp * swing(t, 2.0)
		"BECKON":
			wrist_pitch_extra = deg_to_rad(18.0) * amp * swing(t, 2.5)
			open = deg_to_rad(10.0 + 12.0 * (0.5 + 0.5 * swing(t, 2.5)))
	# Wrist target in the plane: the gripper centre lies GRIPPER_CENTER_M along its axis.
	var dir_axis := Vector2(-cos(axis), sin(axis))           # (forward, up)
	var wp := Vector2(fwd, rel.y) - dir_axis * QuadrupedModel.GRIPPER_CENTER_M
	var a := q.arm_upper_m
	var b := q.arm_fore_m
	var d := clampf(wp.length(), absf(a - b) + 1e-4, a + b - 1e-4)
	var phi := atan2(wp.y, -wp.x)                            # direction of the wrist from the shoulder
	var alpha := acos(clampf((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0))
	var shoulder_angle := phi - alpha                        # elbow above the line
	var elbow := Vector2(-cos(shoulder_angle), sin(shoulder_angle)) * a
	var fore := wp.normalized() * d - elbow
	var fore_abs := atan2(fore.y, -fore.x)
	if fore_abs < shoulder_angle:
		fore_abs += TAU
	return {
		"ArmBase": {"yaw": yaw},
		"ArmShoulder": {"pitch": shoulder_angle},
		"ArmElbow": {"flex": fore_abs - shoulder_angle},
		"ArmWrist": {"pitch": wrapf(axis - fore_abs, -PI, PI) + wrist_pitch_extra, "yaw": 0.0, "roll": 0.0},
		"Gripper": {"open": open},
	}


## Nod, shake and tilt add to the gaze.
func _head_gestures(shown: Array, pose: Dictionary) -> void:
	for layer in shown:
		var g: Dictionary = layer["gesture"]
		var t := float(layer["t"])
		var w := float(layer["weight"]) * envelope(t)
		if w <= 0.0:
			continue
		var amp := float(g["amplitude"])
		match String(g["gesture"]):
			"NOD":
				var nods := 0.0
				if t > ATTACK and t < 1.0 - RELEASE:
					nods = 0.5 - 0.5 * cos(TAU * 2.0 * (t - ATTACK) / HOLD)
				_add(pose, _look_joint(), "pitch", deg_to_rad(4.0 + 12.0 * nods) * amp * w)
			"SHAKE_HEAD":
				_add(pose, _look_joint(), "yaw", deg_to_rad(22.0) * amp * swing(t, 2.5) * w)
			"HEAD_TILT":
				if family == "QUADRUPED":
					# No neck: the whole body rolls and dips its nose a little, feet planted.
					_add(pose, "Body", "roll", deg_to_rad(10.0) * amp * w)
					_add(pose, "Body", "pitch", deg_to_rad(3.0) * w)
				else:
					_add(pose, "Neck", "roll", deg_to_rad(15.0) * amp * w)
					_add(pose, "Neck", "pitch", deg_to_rad(-3.0) * w)
			"BOW":
				if family == "HUMANOID":
					_add(pose, "Neck", "pitch", deg_to_rad(12.0) * amp * w)


# ---------- gaze ----------

## The joint that looks: the humanoid's Neck, the quadruped's whole Body.
func _look_joint() -> String:
	return "Neck" if family == "HUMANOID" else "Body"


func _gaze(avatar: Avatar, tick: int, dt: float, pose: Dictionary) -> void:
	var joint := _look_joint()
	if family == "HUMANOID" and avatar.has_neck():
		# Follow the simulated head (D-72): the rig's Neck pitch is positive looking down. While the
		# ambient display shows, small seeded head adjustments ride on top (G3e, D-74): presentation
		# only, so they never move the sight cone (a world-side jitter could flicker tracks at its edge).
		head = Vector2(avatar.head_yaw, -avatar.head_pitch)
		if avatar.showing_ambient(tick):
			head += presence_head_offset(float(tick) / SimClock.TICK_HZ, hash([avatar.avatar_id, avatar.world.seed_value]),
				avatar.presence_amplitude())
		_add(pose, joint, "yaw", head.x)
		_add(pose, joint, "pitch", head.y)
		return
	var want := Vector2.ZERO
	var point = avatar.gaze_point(tick)
	if point != null:
		var local: Vector3
		if family == "HUMANOID":
			var parent := rig.bone_global("SpineUpper")
			var eyes := rig.bone_global("Neck").origin + parent.basis * Vector3(0, 0.115, 0)
			local = parent.basis.inverse() * (model.to_local(point) - eyes)
		else:
			# From the sensor head in the standing frame (the body pose itself is what turns).
			local = model.to_local(point) - Vector3(0, QuadrupedModel.SENSOR_HEIGHT_M, -0.44)
		var flat := Vector2(local.x, local.z).length()
		if flat > 0.05:
			want = Vector2(atan2(-local.x, -local.z), atan2(-local.y, flat))
	var yaw_lim := rig.limits(joint, "yaw")
	var pitch_lim := rig.limits(joint, "pitch")
	want = Vector2(clampf(want.x, yaw_lim.x, yaw_lim.y), clampf(want.y, pitch_lim.x, pitch_lim.y))
	var turn := float(rig.spec["head_turn_speed"]) * dt
	head = Vector2(move_toward(head.x, want.x, turn), move_toward(head.y, want.y, turn))
	_add(pose, joint, "yaw", head.x)
	_add(pose, joint, "pitch", head.y)


const HEAD_ADJUST_MAX := Vector2(3.0, 2.0)     # degrees of yaw and pitch at amplitude 1 (D-74)
const HEAD_ADJUST_EVERY_S := Vector2(3.0, 6.0)
const HEAD_ADJUST_EASE_S := 0.8


## A slight head adjustment at time `t_s` (G3e, D-74): a new small offset every 3-6 s (seeded),
## eased over 0.8 s, at most 3° yaw and 2° pitch times the amplitude. Far below 3 Hz. Radians,
## (yaw, rig pitch). The neck has room for it: the world's head stops 5° short of the rig's limit.
static func presence_head_offset(t_s: float, avatar_seed: int, amp: float) -> Vector2:
	var a := clampf(amp, 0.0, 1.0)
	var start := 0.0
	var prev := Vector2.ZERO
	var cur := Vector2.ZERO
	for j in 100000:
		var length := lerpf(HEAD_ADJUST_EVERY_S.x, HEAD_ADJUST_EVERY_S.y, _unit(avatar_seed, 4, j))
		prev = cur
		cur = Vector2(_unit(avatar_seed, 5, j) * 2.0 - 1.0, _unit(avatar_seed, 6, j) * 2.0 - 1.0)
		if t_s < start + length:
			var w := smoothstep(0.0, HEAD_ADJUST_EASE_S, t_s - start)
			var v := prev.lerp(cur, w)
			return Vector2(deg_to_rad(v.x * HEAD_ADJUST_MAX.x * a), deg_to_rad(v.y * HEAD_ADJUST_MAX.y * a))
		start += length
	return Vector2.ZERO


static func _unit(avatar_seed: int, stream: int, k: int) -> float:
	return float(hash([avatar_seed, stream, k]) & 0xFFFFFF) / float(0x1000000)


## Gaze plus head gestures stay inside the looking joint's limits (head yaw at most ±85°).
func _clamp_look(pose: Dictionary) -> void:
	var joint := _look_joint()
	for axis in pose[joint]:
		var lim := rig.limits(joint, axis)
		pose[joint][axis] = clampf(float(pose[joint][axis]), lim.x, lim.y)
