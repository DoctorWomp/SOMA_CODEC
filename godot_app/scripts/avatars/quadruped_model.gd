class_name QuadrupedModel
extends Node3D
## Quadruped robot, V0 greybox (ART_DIRECTION §2, §7; D-36), after
## docs/concept-art/robot_quadruped_concept.jpg: white faceted body, a front sensor head
## with a dark visor and lens array, a dark dorsal mounting rail, four legs with dark hip and
## knee joints, and (variant) a utility arm on the rail, shown stowed.
##
## The visor is a camera array, not a face: it carries a thin light strip (future Beacon
## light), never a face glyph. Identity: matte trim panels on both sides with 1-3 stripes as
## a pattern that does not rely on color, plus a number badge on each side (ART_DIRECTION §2.1).
## No leg animation yet: the body glides.
##
## Designed at 1.10 x 0.50 m and 0.70 m tall (body), matching configs/bodies/quadruped.yaml.

const DESIGN_LENGTH_M := 1.10
const SENSOR_HEIGHT_M := 0.55


## `appearance`: "badge", "trim", "bands" as for HumanoidModel.
static func create(length_m: float, with_arm: bool, appearance := {}) -> QuadrupedModel:
	var m := QuadrupedModel.new()
	m.name = "QuadrupedModel"
	m._assemble(with_arm, String(appearance.get("trim", "robot_trim_brown")),
		clampi(int(appearance.get("bands", 1)), 1, 3), String(appearance.get("badge", "R")))
	m.scale = Vector3.ONE * (length_m / DESIGN_LENGTH_M)
	return m


func _assemble(with_arm: bool, trim: String, bands: int, badge_text: String) -> void:
	var p := RobotParts
	# Body shell with a narrower top for a rounded, faceted look.
	p.box(self, "Torso", Vector3(0.40, 0.20, 0.78), "robot_shell", Vector3(0, 0.52, 0.03))
	p.box(self, "TorsoTop", Vector3(0.32, 0.04, 0.66), "robot_shell", Vector3(0, 0.64, 0.03))
	p.box(self, "RearVent", Vector3(0.28, 0.10, 0.02), "robot_joint", Vector3(0, 0.52, 0.43))
	p.box(self, "DorsalRail", Vector3(0.16, 0.025, 0.55), "robot_joint", Vector3(0, 0.672, 0.05))
	for i in 5:
		p.box(self, "RailSlot%d" % (i + 1), Vector3(0.12, 0.006, 0.02), "robot_shell", Vector3(0, 0.686, -0.17 + 0.11 * i))

	# Front sensor head: shell, dark visor with lenses, and the visor light strip.
	var head := p.joint(self, "SensorHead", Vector3(0, SENSOR_HEIGHT_M - 0.01, -0.40))
	p.box(head, "HeadShell", Vector3(0.38, 0.19, 0.16), "robot_shell", Vector3(0, 0, -0.04))
	p.box(head, "Visor", Vector3(0.32, 0.10, 0.02), "robot_visor", Vector3(0, 0.01, -0.125))
	for lens in [["LensL", -0.09, 0.025], ["LensC", 0.0, 0.035], ["LensR", 0.09, 0.025]]:
		var l := p.cyl(head, String(lens[0]), float(lens[2]), float(lens[2]), 0.012, 10, "robot_lens",
			Vector3(float(lens[1]), 0.015, -0.137))
		l.rotation.x = PI / 2
	p.box(head, "VisorLight", Vector3(0.28, 0.012, 0.012), "robot_ear", Vector3(0, -0.05, -0.128))

	# Identity: side trim panels with 1-3 stripes, and a badge on each side.
	for side in [["L", -1.0], ["R", 1.0]]:
		var s := float(side[1])
		for i in bands:
			p.box(self, "Trim%s%d" % [side[0], i + 1], Vector3(0.012, 0.10, 0.06), trim,
				Vector3(0.203 * s, 0.52, -0.10 + 0.09 * i))
		p.badge(self, "Badge" + String(side[0]), badge_text, Vector3(0.207 * s, 0.52, 0.18), Vector3(s, 0, 0), 0.10)

	# Legs: hip joint, white upper leg, dark knee, dark lower leg, rubber foot. Knees point back.
	for leg in [["FL", -1.0, -1.0], ["FR", 1.0, -1.0], ["BL", -1.0, 1.0], ["BR", 1.0, 1.0]]:
		var x := 0.19 * float(leg[1])
		var z := 0.30 * float(leg[2])
		var hip := Vector3(x, 0.46, z)
		var knee := Vector3(x, 0.25, z + 0.08)
		var foot := Vector3(x, 0.045, z)
		var leg_root := p.joint(self, "Leg" + String(leg[0]), Vector3.ZERO)
		p.sphere(leg_root, "HipJoint", 0.055, 0.11, 6, 3, "robot_joint", hip)
		p.segment(leg_root, "UpperLeg", hip, knee, 0.08, "robot_shell", true)
		p.sphere(leg_root, "KneeJoint", 0.045, 0.09, 6, 3, "robot_joint", knee)
		p.segment(leg_root, "LowerLeg", knee, foot, 0.05, "robot_joint")
		p.sphere(leg_root, "Foot", 0.045, 0.09, 6, 3, "robot_wheel", foot)
		p.cyl(leg_root, "FootBand", 0.047, 0.047, 0.02, 6, "robot_shell", foot + Vector3(0, 0.05, 0))

	if with_arm:
		_arm()


## The utility arm on the dorsal rail, stowed low and flat as on real service quadrupeds: a short
## shoulder on the rail, the upper arm folded back, the forearm lying forward along the top,
## and the gripper hanging down over the sensor head with its fingers closed. Kept low on
## purpose so it never reads as something aimed at people.
func _arm() -> void:
	var p := RobotParts
	var arm := p.joint(self, "Arm", Vector3.ZERO)
	var shoulder := Vector3(0, 0.74, 0.16)
	var elbow := Vector3(0, 0.79, 0.34)
	var wrist := Vector3(0, 0.79, -0.30)
	p.box(arm, "ArmBase", Vector3(0.14, 0.05, 0.14), "robot_joint", Vector3(0, 0.705, 0.16))
	p.sphere(arm, "ArmShoulder", 0.045, 0.09, 6, 3, "robot_ear", shoulder)
	p.segment(arm, "ArmUpper", shoulder, elbow, 0.055, "robot_joint", true)
	p.sphere(arm, "ArmElbow", 0.04, 0.08, 6, 3, "robot_ear", elbow)
	p.segment(arm, "ArmFore", elbow, wrist, 0.045, "robot_joint", true)
	p.sphere(arm, "ArmWrist", 0.035, 0.07, 6, 3, "robot_ear", wrist)
	p.box(arm, "Gripper", Vector3(0.07, 0.07, 0.06), "robot_joint", wrist + Vector3(0, -0.05, 0))
	for finger in [["FingerL", -0.022], ["FingerR", 0.022]]:
		p.box(arm, String(finger[0]), Vector3(0.014, 0.06, 0.03), "robot_ear", wrist + Vector3(float(finger[1]), -0.11, 0))
