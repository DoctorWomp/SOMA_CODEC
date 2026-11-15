class_name HumanoidModel
extends Node3D
## Humanoid robots, V0 greybox (ART_DIRECTION §2, §7; D-36). Two bases under one upper body:
##
## - LEGS: the legged humanoid, after docs/concept-art/robot_avatar_lowpoly_concept.jpg.
## - WHEELS: the wheeled humanoid, after docs/concept-art/robot_wheeled_humanoid_concept.jpg:
##   the same upper body on a dark lift column and a four-wheeled base.
##
## Upper body: helmet with black visor (the Beacon glyph display), ear pods (the Beacon light),
## dark neck band, white chest shell with dark side panels, dark waist, arms with
## shoulder, elbow and wrist joints. Identity: matte trim on shoulders, forearms and chest
## band, a number badge front and back, and 1-3 forearm bands as a pattern that does not
## rely on color (ART_DIRECTION §2.1). No leg animation yet: bodies glide.
##
## Joint nodes (Neck, ShoulderL/R, ElbowL/R, WristL/R, HipL/R, KneeL/R, AnkleL/R) are named
## so a later Blender mesh on the same skeleton can replace this one.

const UPPER_BODY_M := 0.8675   # from the hip line to the top of the helmet
const WHEEL_RADIUS_M := 0.12

var base_kind := "LEGS"
var beacon: Beacon
var _wheels: Array[Node3D] = []


## `appearance`: "badge" (text), "trim" (Palette color name), "bands" (1-3).
static func create(height_m: float, base: String, appearance := {}) -> HumanoidModel:
	var m := HumanoidModel.new()
	m.name = "HumanoidModel"
	m.base_kind = base
	var hip := height_m - UPPER_BODY_M
	var trim := String(appearance.get("trim", "robot_trim_green"))
	var bands := clampi(int(appearance.get("bands", 1)), 1, 3)
	if base == "WHEELS":
		m._wheeled_base(hip)
	else:
		m._legs(hip)
	m._upper_body(hip, trim, bands, String(appearance.get("badge", "R")))
	return m


## Spin the wheels to match forward speed (visual only).
func animate(forward_speed: float, delta: float) -> void:
	for wheel in _wheels:
		wheel.rotate_x(-forward_speed * delta / WHEEL_RADIUS_M)


func _upper_body(hip: float, trim: String, bands: int, badge_text: String) -> void:
	var p := RobotParts
	if base_kind == "LEGS":
		p.cyl(self, "Pelvis", 0.15, 0.12, 0.10, 6, "robot_shell", Vector3(0, hip + 0.05, 0), 0.75)
		p.box(self, "PelvisPanel", Vector3(0.10, 0.08, 0.10), "robot_joint", Vector3(0, hip - 0.01, 0))
	else:
		p.cyl(self, "Hip", 0.11, 0.10, 0.10, 8, "robot_joint", Vector3(0, hip + 0.05, 0), 0.85)
	p.cyl(self, "Waist", 0.115, 0.115, 0.10, 8, "robot_joint", Vector3(0, hip + 0.15, 0), 0.8)

	# Chest: wider at the shoulders, flattened front to back, dark side panels.
	p.cyl(self, "Torso", 0.20, 0.14, 0.30, 6, "robot_shell", Vector3(0, hip + 0.35, 0), 0.62)
	for side in [["SidePanelL", -1.0], ["SidePanelR", 1.0]]:
		p.box(self, String(side[0]), Vector3(0.03, 0.20, 0.10), "robot_joint",
			Vector3(0.165 * float(side[1]), hip + 0.36, 0))
	p.cyl(self, "ChestTrim", 0.155, 0.15, 0.03, 6, trim, Vector3(0, hip + 0.225, 0), 0.66)
	p.badge(self, "BadgeFront", badge_text, Vector3(0, hip + 0.37, -0.135), Vector3.FORWARD)
	p.badge(self, "BadgeBack", badge_text, Vector3(0, hip + 0.37, 0.135), Vector3.BACK)

	# Collar, neck band, and the helmet on a neck joint.
	p.cyl(self, "Collar", 0.06, 0.11, 0.04, 8, "robot_joint", Vector3(0, hip + 0.52, 0))
	p.cyl(self, "NeckBand", 0.05, 0.05, 0.07, 8, "robot_joint", Vector3(0, hip + 0.57, 0))
	var neck := p.joint(self, "Neck", Vector3(0, hip + 0.60, 0))
	p.sphere(neck, "Head", 0.128, 0.285, 8, 4, "robot_shell", Vector3(0, 0.125, 0))
	p.sphere(neck, "Visor", 0.108, 0.175, 8, 4, "robot_visor", Vector3(0, 0.115, -0.08), Vector3(1, 1, 0.55))
	var pods: Array[MeshInstance3D] = []
	for side in [["EarPodL", -1.0], ["EarPodR", 1.0]]:
		var pod := p.cyl(neck, String(side[0]), 0.048, 0.048, 0.035, 6, "robot_ear", Vector3(0.127 * float(side[1]), 0.115, 0.01))
		pod.rotation.z = PI / 2
		pods.append(pod)
	# Beacon (D-52): glyph just in front of the visor, light on the ear pods.
	beacon = Beacon.attach(neck, Vector3(0, 0.118, -0.135), 0.09, pods)

	# Arms with a slight outward hang, like the concepts.
	for side in [["L", -1.0], ["R", 1.0]]:
		var s := float(side[1])
		var shoulder := p.joint(self, "Shoulder" + String(side[0]), Vector3(0.215 * s, hip + 0.46, 0))
		shoulder.rotation.z = 0.08 * s
		p.sphere(shoulder, "Pauldron", 0.07, 0.12, 6, 3, trim, Vector3(0.01 * s, 0.01, 0))
		p.sphere(shoulder, "ShoulderJoint", 0.045, 0.09, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(shoulder, "UpperArm", 0.042, 0.038, 0.20, 6, "robot_shell", Vector3(0, -0.13, 0))
		var elbow := p.joint(shoulder, "Elbow" + String(side[0]), Vector3(0, -0.245, 0))
		p.sphere(elbow, "ElbowJoint", 0.04, 0.08, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(elbow, "Forearm", 0.038, 0.032, 0.19, 6, "robot_shell", Vector3(0, -0.11, 0))
		for i in bands:
			p.cyl(elbow, "ForearmBand%d" % (i + 1), 0.041, 0.04, 0.022, 6, trim, Vector3(0, -0.045 - 0.04 * i, 0))
		var wrist := p.joint(elbow, "Wrist" + String(side[0]), Vector3(0, -0.215, 0))
		p.box(wrist, "Hand", Vector3(0.045, 0.09, 0.06), "robot_joint", Vector3(0, -0.045, 0))


func _legs(hip: float) -> void:
	var p := RobotParts
	for side in [["L", -1.0], ["R", 1.0]]:
		var s := float(side[1])
		var hip_joint := p.joint(self, "Hip" + String(side[0]), Vector3(0.09 * s, hip - 0.03, 0))
		p.sphere(hip_joint, "HipJoint", 0.06, 0.12, 6, 3, "robot_joint", Vector3.ZERO)
		p.cyl(hip_joint, "Thigh", 0.068, 0.052, 0.36, 6, "robot_shell", Vector3(0, -0.20, 0))
		var knee := p.joint(hip_joint, "Knee" + String(side[0]), Vector3(0, -0.39, 0))
		p.sphere(knee, "KneeJoint", 0.058, 0.11, 6, 3, "robot_joint", Vector3.ZERO)
		p.box(knee, "KneePad", Vector3(0.07, 0.08, 0.03), "robot_joint", Vector3(0, 0, -0.05))
		p.cyl(knee, "Shin", 0.052, 0.042, 0.34, 6, "robot_shell", Vector3(0, -0.19, 0))
		var ankle := p.joint(knee, "Ankle" + String(side[0]), Vector3(0, -0.3725, 0))   # sole rests on the floor
		p.sphere(ankle, "AnkleJoint", 0.04, 0.08, 6, 3, "robot_joint", Vector3.ZERO)
		p.box(ankle, "Foot", Vector3(0.10, 0.06, 0.22), "robot_shell", Vector3(0, -0.045, -0.03))
		p.box(ankle, "Sole", Vector3(0.105, 0.015, 0.225), "robot_joint", Vector3(0, -0.0825, -0.03))


## Four-wheeled base and lift column (wheeled humanoid concept sheet).
func _wheeled_base(hip: float) -> void:
	var p := RobotParts
	var base := p.joint(self, "Base", Vector3.ZERO)
	p.box(base, "Chassis", Vector3(0.44, 0.15, 0.62), "robot_shell", Vector3(0, 0.215, 0))
	p.box(base, "Bumper", Vector3(0.46, 0.06, 0.66), "robot_joint", Vector3(0, 0.13, 0))
	p.box(base, "Deck", Vector3(0.28, 0.02, 0.36), "robot_joint", Vector3(0, 0.30, 0))
	for end in [["GrillFront", -0.32], ["GrillBack", 0.32]]:
		p.box(base, String(end[0]), Vector3(0.30, 0.05, 0.02), "robot_joint", Vector3(0, 0.20, float(end[1])))
	for wheel_spec in [["WheelFL", -1.0, -1.0], ["WheelFR", 1.0, -1.0], ["WheelBL", -1.0, 1.0], ["WheelBR", 1.0, 1.0]]:
		var hub := p.joint(base, String(wheel_spec[0]), Vector3(0.235 * float(wheel_spec[1]), WHEEL_RADIUS_M, 0.21 * float(wheel_spec[2])))
		var tire := p.cyl(hub, "Tire", WHEEL_RADIUS_M, WHEEL_RADIUS_M, 0.09, 10, "robot_wheel", Vector3.ZERO)
		tire.rotation.z = PI / 2
		var cap := p.cyl(hub, "HubCap", 0.065, 0.065, 0.095, 8, "robot_ear", Vector3.ZERO)
		cap.rotation.z = PI / 2
		_wheels.append(hub)
	# Lift column from the deck up to the hip line.
	p.box(self, "ColumnMount", Vector3(0.20, 0.05, 0.24), "robot_joint", Vector3(0, 0.325, 0))
	var column_top := hip
	var lower_h := (column_top - 0.35) * 0.48
	p.cyl(self, "ColumnLower", 0.095, 0.10, lower_h, 8, "robot_joint", Vector3(0, 0.35 + lower_h / 2, 0))
	p.cyl(self, "ColumnRing", 0.105, 0.105, 0.03, 8, "robot_ear", Vector3(0, 0.35 + lower_h + 0.015, 0))
	var upper_h := column_top - (0.35 + lower_h + 0.03)
	p.cyl(self, "ColumnUpper", 0.085, 0.09, upper_h, 8, "robot_joint", Vector3(0, column_top - upper_h / 2, 0))
