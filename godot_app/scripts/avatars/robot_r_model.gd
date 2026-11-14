class_name RobotRModel
extends Node3D
## Robot R, V0 greybox (ART_DIRECTION §2, §7; D-32).
##
## Assembled from primitives in the proportions of the low-poly concept
## (docs/concept-art/robot_avatar_lowpoly_concept.jpg): white faceted shell panels, dark
## joints, waist and neck band, black visor, ear pods and articulated arms. Its body config
## is a WHEELED_ROBOT, so the concept's legs are replaced by a wheeled base; the upper body
## keeps the concept's proportions at about life size.
##
## Identity: matte green trim on shoulders, forearms and chest band, plus an "R" badge
## (ART_DIRECTION §2.1). Green is not a Beacon color (D-14). The visor and ear pods are the
## future Beacon face and light strip; they stay unlit until Beacon output exists.
##
## Joint nodes (Neck, ShoulderL/R, ElbowL/R, WristL/R) are named so a later Blender mesh on
## the same skeleton can replace this one without changing anything else.

const DESIGN_HEIGHT_M := 1.4
const WHEEL_RADIUS_M := 0.09

var _wheels: Array[Node3D] = []


static func create(height_m: float, badge_text := "R") -> RobotRModel:
	var m := RobotRModel.new()
	m.name = "RobotRModel"
	m._assemble(badge_text)
	m.scale = Vector3.ONE * (height_m / DESIGN_HEIGHT_M)
	return m


## Spin the wheels to match forward speed (visual only).
func animate(forward_speed: float, delta: float) -> void:
	for wheel in _wheels:
		wheel.rotate_x(-forward_speed * delta / WHEEL_RADIUS_M)


func _mat(color_name: String) -> StandardMaterial3D:
	return Palette.material(color_name)


func _cyl(parent: Node3D, node_name: String, top_r: float, bottom_r: float, h: float, segments: int,
		color_name: String, pos: Vector3, squash_z := 1.0) -> MeshInstance3D:
	var c := CylinderMesh.new()
	c.top_radius = top_r
	c.bottom_radius = bottom_r
	c.height = h
	c.radial_segments = segments
	c.rings = 1
	var mi := MeshKit.mesh_instance(MeshKit.faceted(c), _mat(color_name), node_name, pos)
	mi.scale = Vector3(1, 1, squash_z)
	parent.add_child(mi)
	return mi


func _sphere(parent: Node3D, node_name: String, r: float, h: float, segments: int, rings: int,
		color_name: String, pos: Vector3, scale_xyz := Vector3.ONE) -> MeshInstance3D:
	var s := SphereMesh.new()
	s.radius = r
	s.height = h
	s.radial_segments = segments
	s.rings = rings
	var mi := MeshKit.mesh_instance(MeshKit.faceted(s), _mat(color_name), node_name, pos)
	mi.scale = scale_xyz
	parent.add_child(mi)
	return mi


func _joint(parent: Node3D, node_name: String, pos: Vector3) -> Node3D:
	var j := Node3D.new()
	j.name = node_name
	j.position = pos
	parent.add_child(j)
	return j


func _assemble(badge_text: String) -> void:
	# Wheeled base (replaces the concept's legs): chassis, two drive wheels, two casters.
	var base := _joint(self, "Base", Vector3.ZERO)
	_cyl(base, "Chassis", 0.27, 0.32, 0.16, 8, "robot_joint", Vector3(0, 0.15, 0))
	for side in [["WheelL", -1.0], ["WheelR", 1.0]]:
		var hub := _joint(base, String(side[0]), Vector3(0.30 * float(side[1]), WHEEL_RADIUS_M, 0))
		var wheel := _cyl(hub, "Tire", WHEEL_RADIUS_M, WHEEL_RADIUS_M, 0.06, 10, "robot_wheel", Vector3.ZERO)
		wheel.rotation.z = PI / 2
		_wheels.append(hub)
	_sphere(base, "CasterF", 0.04, 0.08, 6, 3, "robot_wheel", Vector3(0, 0.04, -0.2))
	_sphere(base, "CasterB", 0.04, 0.08, 6, 3, "robot_wheel", Vector3(0, 0.04, 0.2))

	# Mast from the base up to the hips (dark, like the concept's joints), with a white
	# collar ring, then the white pelvis and the dark waist band.
	_cyl(self, "Mast", 0.10, 0.16, 0.30, 8, "robot_joint", Vector3(0, 0.38, 0))
	_cyl(self, "MastRing", 0.125, 0.135, 0.05, 8, "robot_shell", Vector3(0, 0.40, 0))
	_cyl(self, "Pelvis", 0.15, 0.12, 0.10, 6, "robot_shell", Vector3(0, 0.58, 0), 0.75)
	_cyl(self, "Waist", 0.115, 0.115, 0.10, 8, "robot_joint", Vector3(0, 0.68, 0), 0.8)

	# Chest: wider at the shoulders, tapering to the waist, flattened front to back.
	_cyl(self, "Torso", 0.20, 0.14, 0.30, 6, "robot_shell", Vector3(0, 0.88, 0), 0.62)
	_cyl(self, "ChestTrim", 0.155, 0.15, 0.03, 6, "robot_trim", Vector3(0, 0.755, 0), 0.66)
	for side in [["BadgeFront", -0.135, PI], ["BadgeBack", 0.135, 0.0]]:
		var badge := MeshKit.label(badge_text, 40, false)
		badge.name = String(side[0])
		badge.pixel_size = 0.0025
		badge.outline_size = 0
		badge.position = Vector3(0, 0.9, float(side[1]))
		badge.rotation.y = float(side[2])
		add_child(badge)

	# Collar and neck band, then the head on a neck joint.
	_cyl(self, "Collar", 0.06, 0.11, 0.04, 8, "robot_joint", Vector3(0, 1.05, 0))
	_cyl(self, "NeckBand", 0.05, 0.05, 0.07, 8, "robot_joint", Vector3(0, 1.10, 0))
	var neck := _joint(self, "Neck", Vector3(0, 1.13, 0))
	_sphere(neck, "Head", 0.128, 0.285, 8, 4, "robot_shell", Vector3(0, 0.125, 0))
	_sphere(neck, "Visor", 0.108, 0.175, 8, 4, "robot_visor", Vector3(0, 0.115, -0.08), Vector3(1, 1, 0.55))
	for side in [["EarPodL", -1.0], ["EarPodR", 1.0]]:
		var pod := _cyl(neck, String(side[0]), 0.048, 0.048, 0.035, 6, "robot_ear", Vector3(0.127 * float(side[1]), 0.115, 0.01))
		pod.rotation.z = PI / 2

	# Arms: shoulder, elbow and wrist joints; slight outward hang like the concept.
	for side in [["L", -1.0], ["R", 1.0]]:
		var s := float(side[1])
		var shoulder := _joint(self, "Shoulder" + String(side[0]), Vector3(0.215 * s, 0.99, 0))
		shoulder.rotation.z = 0.08 * s
		_sphere(shoulder, "Pauldron", 0.07, 0.12, 6, 3, "robot_trim", Vector3(0.01 * s, 0.01, 0))
		_sphere(shoulder, "ShoulderJoint", 0.045, 0.09, 6, 3, "robot_joint", Vector3.ZERO)
		_cyl(shoulder, "UpperArm", 0.042, 0.038, 0.20, 6, "robot_shell", Vector3(0, -0.13, 0))
		var elbow := _joint(shoulder, "Elbow" + String(side[0]), Vector3(0, -0.245, 0))
		_sphere(elbow, "ElbowJoint", 0.04, 0.08, 6, 3, "robot_joint", Vector3.ZERO)
		_cyl(elbow, "Forearm", 0.038, 0.032, 0.19, 6, "robot_shell", Vector3(0, -0.11, 0))
		_cyl(elbow, "ForearmTrim", 0.041, 0.04, 0.03, 6, "robot_trim", Vector3(0, -0.05, 0))
		var wrist := _joint(elbow, "Wrist" + String(side[0]), Vector3(0, -0.215, 0))
		var hand := MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.045, 0.09, 0.06)), _mat("robot_joint"), "Hand", Vector3(0, -0.045, 0))
		wrist.add_child(hand)

	var tag := MeshKit.label("robot_r", 40)
	tag.name = "NameTag"
	tag.position = Vector3(0, DESIGN_HEIGHT_M + 0.3, 0)
	add_child(tag)
