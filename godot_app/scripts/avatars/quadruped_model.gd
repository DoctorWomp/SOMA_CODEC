class_name QuadrupedModel
extends Node3D
## Quadruped robot, V0 greybox (ART_DIRECTION §2, §7; D-36), after
## docs/concept-art/robot_quadruped_concept.jpg, on the quadruped skeleton (D-54, D-56): white
## faceted body, a front sensor head on a neck joint with a dark visor and lens array, a dark
## dorsal mounting rail, four legs with dark hip and knee joints, and (variant) a utility arm on
## the rail, stowed unless it gestures.
##
## The visor is a camera array, not a face: the Beacon is a narrow light strip above it
## (simple symbols and light, never over the lenses; D-52), plus a thin light below it.
## Identity: matte trim panels on both sides with 1-3 stripes as a pattern that does not rely on
## color, plus a number badge on each side (ART_DIRECTION §2.1). No gait yet (rig step B).
##
## Bones: Body (rigid root), Neck, and per leg (FL, FR, BL, BR) HipAbd, HipFlex, Knee, Foot; the
## arm module adds ArmBase, ArmShoulder, ArmElbow, ArmWrist, Gripper, GripperFingerL/R.
##
## Designed at 1.10 x 0.50 m and 0.70 m tall (body), matching configs/bodies/quadruped.yaml.

const DESIGN_LENGTH_M := 1.10
const SENSOR_HEIGHT_M := 0.55
## Leg design points (model space, right side; knees point back): hip, knee and foot centre.
const HIP_Y := 0.46
const KNEE_Y := 0.25
const KNEE_BACK_M := 0.08
const FOOT_Y := 0.045
const LEG_X := 0.19
const LEG_Z := 0.30
## Arm module design (model space): base on the rail, shoulder, and the stowed elbow and wrist.
const ARM_BASE := Vector3(0, 0.705, 0.16)
const ARM_SHOULDER := Vector3(0, 0.74, 0.16)
const ARM_STOWED_ELBOW := Vector3(0, 0.79, 0.34)
const ARM_STOWED_WRIST := Vector3(0, 0.79, -0.30)
const GRIPPER_CENTER_M := 0.05     # gripper body centre, from the wrist along the gripper
const GRIPPER_STOWED_WRIST_DEG := 85.0   # gripper hangs down, slightly forward

var beacon: Beacon
var rig: Rig
var poser: Poser
var upper_leg_m := 0.0
var lower_leg_m := 0.0
var arm_upper_m := 0.0
var arm_fore_m := 0.0


## `appearance`: "badge", "trim", "bands" as for HumanoidModel.
static func create(length_m: float, rig_spec: Dictionary, appearance := {}) -> QuadrupedModel:
	var m := QuadrupedModel.new()
	m.name = "QuadrupedModel"
	m.rig = Rig.create(rig_spec)
	m.add_child(m.rig)
	m._assemble(bool(rig_spec["arm_module"]), String(appearance.get("trim", "robot_trim_brown")),
		clampi(int(appearance.get("bands", 1)), 1, 3), String(appearance.get("badge", "R")))
	m.scale = Vector3.ONE * (length_m / DESIGN_LENGTH_M)
	m.poser = Poser.new(m.rig, m)
	m.poser.stand_pose()
	m.rig.store_rest_angles()
	m.rig.apply()
	return m


func foot_point(leg: String) -> Vector3:
	return Vector3(LEG_X * (-1.0 if leg.ends_with("L") else 1.0), FOOT_Y, LEG_Z * (-1.0 if leg.begins_with("F") else 1.0))


func _assemble(with_arm: bool, trim: String, bands: int, badge_text: String) -> void:
	var p := RobotParts
	rig.bone("Body", "", Vector3.ZERO)
	var body := rig.attach("Body")
	# Body shell with a narrower top for a rounded, faceted look.
	p.box(body, "Torso", Vector3(0.40, 0.20, 0.78), "robot_shell", Vector3(0, 0.52, 0.03))
	p.box(body, "TorsoTop", Vector3(0.32, 0.04, 0.66), "robot_shell", Vector3(0, 0.64, 0.03))
	p.box(body, "RearVent", Vector3(0.28, 0.10, 0.02), "robot_joint", Vector3(0, 0.52, 0.43))
	p.box(body, "DorsalRail", Vector3(0.16, 0.025, 0.55), "robot_joint", Vector3(0, 0.672, 0.05))
	for i in 5:
		p.box(body, "RailSlot%d" % (i + 1), Vector3(0.12, 0.006, 0.02), "robot_shell", Vector3(0, 0.686, -0.17 + 0.11 * i))

	# Front sensor head on its neck joint: shell, dark visor with lenses, and the visor light strip.
	rig.bone("Neck", "Body", Vector3(0, SENSOR_HEIGHT_M - 0.01, -0.40))
	var head := Node3D.new()
	head.name = "SensorHead"
	rig.attach("Neck").add_child(head)
	p.box(head, "HeadShell", Vector3(0.38, 0.19, 0.16), "robot_shell", Vector3(0, 0, -0.04))
	p.box(head, "Visor", Vector3(0.32, 0.10, 0.02), "robot_visor", Vector3(0, 0.01, -0.125))
	for lens in [["LensL", -0.09, 0.025], ["LensC", 0.0, 0.035], ["LensR", 0.09, 0.025]]:
		var l := p.cyl(head, String(lens[0]), float(lens[2]), float(lens[2]), 0.012, 10, "robot_lens",
			Vector3(float(lens[1]), 0.015, -0.137))
		l.rotation.x = PI / 2
	var under := p.box(head, "VisorLight", Vector3(0.28, 0.012, 0.012), "robot_ear", Vector3(0, -0.05, -0.128))
	# Beacon (EXPRESSION_PRINCIPLES §1, D-36 as amended): a narrow light strip above the camera
	# cluster, never over the lenses, showing a few simple symbols plus light.
	# The strip stays dark and its symbol lights up in the Beacon color, like an LED band; the thin
	# bar under the visor carries the light itself.
	p.box(head, "LightStrip", Vector3(0.30, 0.03, 0.012), "robot_joint", Vector3(0, 0.078, -0.128))
	beacon = Beacon.attach(head, Vector3(0, 0.078, -0.136), 0.07, [under] as Array[MeshInstance3D])

	# Identity: side trim panels with 1-3 stripes, and a badge on each side.
	for side in [["L", -1.0], ["R", 1.0]]:
		var s := float(side[1])
		for i in bands:
			p.box(body, "Trim%s%d" % [side[0], i + 1], Vector3(0.012, 0.10, 0.06), trim,
				Vector3(0.203 * s, 0.52, -0.10 + 0.09 * i))
		p.badge(body, "Badge" + String(side[0]), badge_text, Vector3(0.207 * s, 0.52, 0.18), Vector3(s, 0, 0), 0.10)

	# Legs: hip joint, white upper leg, dark knee, dark lower leg, rubber foot. In the zero pose a
	# leg hangs straight down; the standing pose bends the knees back (Poser.stand_pose).
	upper_leg_m = Vector2(HIP_Y - KNEE_Y, KNEE_BACK_M).length()
	lower_leg_m = Vector2(KNEE_Y - FOOT_Y, KNEE_BACK_M).length()
	for leg in RigSpec.LEGS:
		var foot := foot_point(leg)
		rig.bone("HipAbd" + leg, "Body", Vector3(foot.x, HIP_Y, foot.z))
		p.sphere(rig.attach("HipAbd" + leg), "HipJoint", 0.055, 0.11, 6, 3, "robot_joint", Vector3.ZERO)
		rig.bone("HipFlex" + leg, "HipAbd" + leg, Vector3.ZERO)
		p.segment(rig.attach("HipFlex" + leg), "UpperLeg", Vector3.ZERO, Vector3(0, -upper_leg_m, 0), 0.08, "robot_shell", true)
		rig.bone("Knee" + leg, "HipFlex" + leg, Vector3(0, -upper_leg_m, 0))
		var knee := rig.attach("Knee" + leg)
		p.sphere(knee, "KneeJoint", 0.045, 0.09, 6, 3, "robot_joint", Vector3.ZERO)
		p.segment(knee, "LowerLeg", Vector3.ZERO, Vector3(0, -lower_leg_m, 0), 0.05, "robot_joint")
		rig.bone("Foot" + leg, "Knee" + leg, Vector3(0, -lower_leg_m, 0))
		rig.level_bones.append("Foot" + leg)
		var foot_node := rig.attach("Foot" + leg)
		p.sphere(foot_node, "Foot", 0.045, 0.09, 6, 3, "robot_wheel", Vector3.ZERO)
		p.cyl(foot_node, "FootBand", 0.047, 0.047, 0.02, 6, "robot_shell", Vector3(0, 0.05, 0))

	if with_arm:
		_arm()


## The utility arm on the dorsal rail. In the zero pose it points straight back along the rail;
## stowed (the rest pose) it lies low and flat as on real service quadrupeds: the upper arm
## folded back, the forearm lying forward along the top, and the gripper hanging down over the
## sensor head with its fingers closed. Kept low on purpose so it never reads as something aimed
## at people.
func _arm() -> void:
	var p := RobotParts
	arm_upper_m = ARM_SHOULDER.distance_to(ARM_STOWED_ELBOW)
	arm_fore_m = ARM_STOWED_ELBOW.distance_to(ARM_STOWED_WRIST)
	rig.bone("ArmBase", "Body", ARM_BASE)
	p.box(rig.attach("ArmBase"), "ArmMount", Vector3(0.14, 0.05, 0.14), "robot_joint", Vector3.ZERO)
	rig.bone("ArmShoulder", "ArmBase", ARM_SHOULDER - ARM_BASE)
	var shoulder := rig.attach("ArmShoulder")
	p.sphere(shoulder, "ArmShoulderJoint", 0.045, 0.09, 6, 3, "robot_ear", Vector3.ZERO)
	p.segment(shoulder, "ArmUpper", Vector3.ZERO, Vector3(0, 0, arm_upper_m), 0.055, "robot_joint", true)
	rig.bone("ArmElbow", "ArmShoulder", Vector3(0, 0, arm_upper_m))
	var elbow := rig.attach("ArmElbow")
	p.sphere(elbow, "ArmElbowJoint", 0.04, 0.08, 6, 3, "robot_ear", Vector3.ZERO)
	p.segment(elbow, "ArmFore", Vector3.ZERO, Vector3(0, 0, arm_fore_m), 0.045, "robot_joint", true)
	rig.bone("ArmWrist", "ArmElbow", Vector3(0, 0, arm_fore_m))
	p.sphere(rig.attach("ArmWrist"), "ArmWristJoint", 0.035, 0.07, 6, 3, "robot_ear", Vector3.ZERO)
	# The gripper extends along the forearm in the zero pose.
	rig.bone("Gripper", "ArmWrist", Vector3.ZERO)
	var gripper := rig.attach("Gripper")
	p.box(gripper, "GripperBody", Vector3(0.07, 0.06, 0.07), "robot_joint", Vector3(0, 0, GRIPPER_CENTER_M))
	var center := Marker3D.new()
	center.name = "HandCenter"
	center.position = Vector3(0, 0, GRIPPER_CENTER_M)
	gripper.add_child(center)
	for finger in [["GripperFingerL", -0.022], ["GripperFingerR", 0.022]]:
		rig.bone(String(finger[0]), "Gripper", Vector3(float(finger[1]), 0, 0.08))
		p.box(rig.attach(String(finger[0])), "Finger", Vector3(0.014, 0.03, 0.06), "robot_ear", Vector3(0, 0, 0.03))
