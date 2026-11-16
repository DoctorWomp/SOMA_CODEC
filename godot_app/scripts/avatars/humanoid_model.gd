class_name HumanoidModel
extends Node3D
## Humanoid robots, V0 greybox (ART_DIRECTION §2, §7; D-36), on the humanoid skeleton (D-54,
## D-56). Two bases under one upper body:
##
## - LEGS: the legged humanoid, after docs/concept-art/robot_avatar_lowpoly_concept.jpg.
## - WHEELS: the wheeled humanoid, after docs/concept-art/robot_wheeled_humanoid_concept.jpg:
##   the same upper body on a torso mount, a dark lift column and a four-wheeled base.
##
## Upper body: helmet with black visor (the Beacon glyph display), ear pods (the Beacon light),
## dark neck band, white chest shell with dark side panels, dark waist, arms with shoulder,
## elbow and wrist joints, a palm, a finger group and a thumb. Identity: matte trim on
## shoulders, forearms and chest band, a number badge front and back, and 1-3 forearm bands as
## a pattern that does not rely on color (ART_DIRECTION §2.1). No gait yet (rig step B): legged
## bodies glide.
##
## Every part hangs from one bone of `rig` (bone names: Pelvis or Base and TorsoMount,
## SpineLower, SpineUpper, Neck, ShoulderL/R, ElbowL/R, WristL/R, FingersL/R, ThumbL/R,
## HipL/R, KneeL/R, AnkleL/R, ToeL/R, WheelFL/FR/BL/BR), so a later Blender mesh on the same
## skeleton can replace the primitives.

const UPPER_BODY_M := 0.8675   # from the hip line to the top of the helmet
const WHEEL_RADIUS_M := 0.12
const WHEEL_TRACK_M := 0.47    # between the left and right wheels
const SHOULDER_HANG_RAD := 0.08   # arms hang slightly away from the body, like the concepts

var base_kind := "LEGS"
var beacon: Beacon
var rig: Rig
var poser: Poser
var wheels: Array[String] = []


## `appearance`: "badge" (text), "trim" (Palette color name), "bands" (1-3).
static func create(height_m: float, rig_spec: Dictionary, appearance := {}) -> HumanoidModel:
	var m := HumanoidModel.new()
	m.name = "HumanoidModel"
	m.base_kind = String(rig_spec["base"])
	m.rig = Rig.create(rig_spec)
	m.add_child(m.rig)
	var hip := height_m - UPPER_BODY_M
	var trim := String(appearance.get("trim", "robot_trim_green"))
	var bands := clampi(int(appearance.get("bands", 1)), 1, 3)
	if m.base_kind == "WHEELS":
		m._wheeled_base(hip)
	else:
		m._legs(hip)
	m._upper_body(trim, bands, String(appearance.get("badge", "R")))
	for side in ["L", "R"]:
		m.rig.set_angle("Shoulder" + side, "roll", SHOULDER_HANG_RAD)
	m.rig.store_rest_angles()
	m.rig.apply()
	m.poser = Poser.new(m.rig, m)
	return m


func _upper_body(trim: String, bands: int, badge_text: String) -> void:
	var p := RobotParts
	var below := "Pelvis" if base_kind == "LEGS" else "TorsoMount"
	# Hip line bone first: Pelvis (legged root) or TorsoMount (wheeled); parts as in G1b.
	var hip_node := rig.attach(below)
	if base_kind == "LEGS":
		p.cyl(hip_node, "Pelvis", 0.15, 0.12, 0.10, 6, "robot_shell", Vector3(0, 0.05, 0), 0.75)
		p.box(hip_node, "PelvisPanel", Vector3(0.10, 0.08, 0.10), "robot_joint", Vector3(0, -0.01, 0))
	else:
		p.cyl(hip_node, "Hip", 0.11, 0.10, 0.10, 8, "robot_joint", Vector3(0, 0.05, 0), 0.85)

	rig.bone("SpineLower", below, Vector3(0, 0.10, 0))          # hip + 0.10
	var waist := rig.attach("SpineLower")
	p.cyl(waist, "Waist", 0.115, 0.115, 0.10, 8, "robot_joint", Vector3(0, 0.05, 0), 0.8)

	rig.bone("SpineUpper", "SpineLower", Vector3(0, 0.15, 0))   # hip + 0.25
	var chest := rig.attach("SpineUpper")
	# Chest: wider at the shoulders, flattened front to back, dark side panels.
	p.cyl(chest, "Torso", 0.20, 0.14, 0.30, 6, "robot_shell", Vector3(0, 0.10, 0), 0.62)
	for side in [["SidePanelL", -1.0], ["SidePanelR", 1.0]]:
		p.box(chest, String(side[0]), Vector3(0.03, 0.20, 0.10), "robot_joint", Vector3(0.165 * float(side[1]), 0.11, 0))
	p.cyl(chest, "ChestTrim", 0.155, 0.15, 0.03, 6, trim, Vector3(0, -0.025, 0), 0.66)
	p.badge(chest, "BadgeFront", badge_text, Vector3(0, 0.12, -0.135), Vector3.FORWARD)
	p.badge(chest, "BadgeBack", badge_text, Vector3(0, 0.12, 0.135), Vector3.BACK)
	# Collar and neck band.
	p.cyl(chest, "Collar", 0.06, 0.11, 0.04, 8, "robot_joint", Vector3(0, 0.27, 0))
	p.cyl(chest, "NeckBand", 0.05, 0.05, 0.07, 8, "robot_joint", Vector3(0, 0.32, 0))

	# The helmet on the neck joint (hip + 0.60).
	rig.bone("Neck", "SpineUpper", Vector3(0, 0.35, 0))
	var neck := rig.attach("Neck")
	p.sphere(neck, "Head", 0.128, 0.285, 8, 4, "robot_shell", Vector3(0, 0.125, 0))
	p.sphere(neck, "Visor", 0.108, 0.175, 8, 4, "robot_visor", Vector3(0, 0.115, -0.08), Vector3(1, 1, 0.55))
	var pods: Array[MeshInstance3D] = []
	for side in [["EarPodL", -1.0], ["EarPodR", 1.0]]:
		var pod := p.cyl(neck, String(side[0]), 0.048, 0.048, 0.035, 6, "robot_ear", Vector3(0.127 * float(side[1]), 0.115, 0.01))
		pod.rotation.z = PI / 2
		pods.append(pod)
	# Beacon (D-52): glyph just in front of the visor, light on the ear pods.
	beacon = Beacon.attach(neck, Vector3(0, 0.118, -0.147), 0.08, pods)

	# Arms (hip + 0.46), hanging straight in the zero pose; the rest pose adds a slight outward hang.
	for side in [["L", -1.0], ["R", 1.0]]:
		var sd := String(side[0])
		var s := float(side[1])
		rig.bone("Shoulder" + sd, "SpineUpper", Vector3(0.215 * s, 0.21, 0))
		var shoulder := rig.attach("Shoulder" + sd)
		p.sphere(shoulder, "Pauldron", 0.07, 0.12, 6, 3, trim, Vector3(0.01 * s, 0.01, 0))
		p.sphere(shoulder, "ShoulderJoint", 0.045, 0.09, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(shoulder, "UpperArm", 0.042, 0.038, 0.20, 6, "robot_shell", Vector3(0, -0.13, 0))
		rig.bone("Elbow" + sd, "Shoulder" + sd, Vector3(0, -0.245, 0))
		var elbow := rig.attach("Elbow" + sd)
		p.sphere(elbow, "ElbowJoint", 0.04, 0.08, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(elbow, "Forearm", 0.038, 0.032, 0.19, 6, "robot_shell", Vector3(0, -0.11, 0))
		for i in bands:
			p.cyl(elbow, "ForearmBand%d" % (i + 1), 0.041, 0.04, 0.022, 6, trim, Vector3(0, -0.045 - 0.04 * i, 0))
		rig.bone("Wrist" + sd, "Elbow" + sd, Vector3(0, -0.215, 0))
		var wrist := rig.attach("Wrist" + sd)
		p.box(wrist, "Palm", Vector3(0.045, 0.05, 0.06), "robot_joint", Vector3(0, -0.025, 0))
		var center := Marker3D.new()
		center.name = "HandCenter"
		center.position = Vector3(0, -0.045, 0)   # the middle of the hand, palm and fingers together
		wrist.add_child(center)
		rig.bone("Fingers" + sd, "Wrist" + sd, Vector3(0, -0.05, 0))
		p.box(rig.attach("Fingers" + sd), "Fingers", Vector3(0.04, 0.045, 0.055), "robot_joint", Vector3(0, -0.0225, 0))
		rig.bone("Thumb" + sd, "Wrist" + sd, Vector3(-0.012 * s, -0.012, -0.033))
		p.box(rig.attach("Thumb" + sd), "Thumb", Vector3(0.016, 0.035, 0.016), "robot_joint", Vector3(0, -0.0175, 0))


func _legs(hip: float) -> void:
	var p := RobotParts
	rig.bone("Pelvis", "", Vector3(0, hip, 0))
	for side in [["L", -1.0], ["R", 1.0]]:
		var sd := String(side[0])
		var s := float(side[1])
		rig.bone("Hip" + sd, "Pelvis", Vector3(0.09 * s, -0.03, 0))
		var hip_joint := rig.attach("Hip" + sd)
		p.sphere(hip_joint, "HipJoint", 0.06, 0.12, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(hip_joint, "Thigh", 0.068, 0.052, 0.36, 6, "robot_shell", Vector3(0, -0.20, 0))
		rig.bone("Knee" + sd, "Hip" + sd, Vector3(0, -0.39, 0))
		var knee := rig.attach("Knee" + sd)
		p.sphere(knee, "KneeJoint", 0.058, 0.11, 6, 3, "robot_joint", Vector3.ZERO)
		p.box(knee, "KneePad", Vector3(0.07, 0.08, 0.03), "robot_joint", Vector3(0, 0, -0.05))
		p.cyl(knee, "Shin", 0.052, 0.042, 0.34, 6, "robot_shell", Vector3(0, -0.19, 0))
		rig.bone("Ankle" + sd, "Knee" + sd, Vector3(0, -0.3725, 0))   # sole rests on the floor
		var ankle := rig.attach("Ankle" + sd)
		p.sphere(ankle, "AnkleJoint", 0.04, 0.08, 6, 3, "robot_joint", Vector3.ZERO)
		p.box(ankle, "Foot", Vector3(0.10, 0.06, 0.22), "robot_shell", Vector3(0, -0.045, -0.03))
		p.box(ankle, "Sole", Vector3(0.105, 0.015, 0.225), "robot_joint", Vector3(0, -0.0825, -0.03))
		rig.bone("Toe" + sd, "Ankle" + sd, Vector3(0, -0.0825, -0.10))   # the toe hinge, for the gait (step B)


## Four-wheeled base, lift column and torso mount (wheeled humanoid concept sheet).
func _wheeled_base(hip: float) -> void:
	var p := RobotParts
	rig.bone("Base", "", Vector3.ZERO)
	var base := rig.attach("Base")
	p.box(base, "Chassis", Vector3(0.44, 0.15, 0.62), "robot_shell", Vector3(0, 0.215, 0))
	p.box(base, "Bumper", Vector3(0.46, 0.06, 0.66), "robot_joint", Vector3(0, 0.13, 0))
	p.box(base, "Deck", Vector3(0.28, 0.02, 0.36), "robot_joint", Vector3(0, 0.30, 0))
	for end in [["GrillFront", -0.32], ["GrillBack", 0.32]]:
		p.box(base, String(end[0]), Vector3(0.30, 0.05, 0.02), "robot_joint", Vector3(0, 0.20, float(end[1])))
	for wheel_spec in [["WheelFL", -1.0, -1.0], ["WheelFR", 1.0, -1.0], ["WheelBL", -1.0, 1.0], ["WheelBR", 1.0, 1.0]]:
		var wheel_id := String(wheel_spec[0])
		rig.bone(wheel_id, "Base", Vector3(WHEEL_TRACK_M / 2 * float(wheel_spec[1]), WHEEL_RADIUS_M, 0.21 * float(wheel_spec[2])))
		var hub := rig.attach(wheel_id)
		var tire := p.cyl(hub, "Tire", WHEEL_RADIUS_M, WHEEL_RADIUS_M, 0.09, 10, "robot_wheel", Vector3.ZERO)
		tire.rotation.z = PI / 2
		var cap := p.cyl(hub, "HubCap", 0.065, 0.065, 0.095, 8, "robot_ear", Vector3.ZERO)
		cap.rotation.z = PI / 2
		# A spoke mark on the hub cap so the spin is visible.
		p.box(hub, "Spoke", Vector3(0.10, 0.10, 0.02), "robot_joint", Vector3.ZERO)
		wheels.append(wheel_id)
		rig.spin[wheel_id] = 0.0
	# Lift column from the deck up to the hip line, on the base.
	p.box(base, "ColumnMount", Vector3(0.20, 0.05, 0.24), "robot_joint", Vector3(0, 0.325, 0))
	var column_top := hip
	var lower_h := (column_top - 0.35) * 0.48
	p.cyl(base, "ColumnLower", 0.095, 0.10, lower_h, 8, "robot_joint", Vector3(0, 0.35 + lower_h / 2, 0))
	p.cyl(base, "ColumnRing", 0.105, 0.105, 0.03, 8, "robot_ear", Vector3(0, 0.35 + lower_h + 0.015, 0))
	var upper_h := column_top - (0.35 + lower_h + 0.03)
	p.cyl(base, "ColumnUpper", 0.085, 0.09, upper_h, 8, "robot_joint", Vector3(0, column_top - upper_h / 2, 0))
	# The torso mount at the top of the column: leaning in and backing off (D-54).
	rig.bone("TorsoMount", "Base", Vector3(0, hip, 0))
