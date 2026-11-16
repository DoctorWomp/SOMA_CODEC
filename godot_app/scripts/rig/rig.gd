class_name Rig
extends Skeleton3D
## A robot's skeleton (D-54, D-56): bones built from the model's layout and the body's rig
## settings (RigSpec), with every primitive part rigidly attached to one bone through a
## BoneAttachment3D named after it. Pose is presentation only: the rig has no collider and
## nothing reads it back into the world.
##
## Joint angles go through set_angle(), which clamps them to the joint's limits and counts every
## clamp, and apply() turns them into bone poses. Bones rest with no rotation, so all zero angles
## is the zero pose described in RigSpec. A few bones are not joints: the root (posture can move
## it), wheels (free spin) and the gripper fingers (driven by the Gripper joint's `open`).

var spec: Dictionary = {}
## joint -> {axis: angle in radians}, the angles applied last.
var angles: Dictionary = {}
## Times an angle was asked for beyond its limit (the layers are designed never to need it).
var clamp_count := 0
var clamp_log: Array[String] = []
## The root bone's transform on top of its rest (posture), in skeleton space.
var root_pose := Transform3D.IDENTITY
## Wheel bone -> spin angle (radians, about the axle).
var spin: Dictionary = {}
## Bones kept level with the root whatever their parents do (the quadruped's point feet).
var level_bones: Array[String] = []
## The point the quadruped's "Body" joint pivots about (its body centre at hip height).
var body_pivot := Vector3.ZERO
## How far the body is lowered so every leg still reaches the floor (Poser sets it).
var body_drop := 0.0

var _offsets: Dictionary = {}       # bone -> rest offset in the parent bone's space
var _attachments: Dictionary = {}   # bone -> BoneAttachment3D
var _root := ""
var _rest_angles: Dictionary = {}


static func create(rig_spec: Dictionary) -> Rig:
	var r := Rig.new()
	r.name = "Rig"
	r.spec = rig_spec
	# Bone attachments follow poses set in the physics step (D-33).
	r.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	for joint_name in rig_spec.get("joints", {}):
		var a := {}
		for axis_pair in rig_spec["joints"][joint_name]["axes"]:
			a[String(axis_pair[0])] = 0.0
		r.angles[joint_name] = a
	return r


## Add a bone at `offset` in its parent's space (the parent's zero pose).
func bone(bone_id: String, parent_id: String, offset: Vector3) -> int:
	var i := add_bone(bone_id)
	if parent_id != "":
		set_bone_parent(i, find_bone(parent_id))
	else:
		_root = bone_id
	set_bone_rest(i, Transform3D(Basis.IDENTITY, offset))
	set_bone_pose_position(i, offset)
	set_bone_pose_rotation(i, Quaternion.IDENTITY)
	_offsets[bone_id] = offset
	return i


func has_joint(joint_name: String) -> bool:
	return angles.has(joint_name)


## The node parts of `bone_id` hang from (created once, named after the bone).
func attach(bone_id: String) -> Node3D:
	if _attachments.has(bone_id):
		return _attachments[bone_id]
	var att := BoneAttachment3D.new()
	att.name = bone_id
	att.bone_name = bone_id
	add_child(att)
	_attachments[bone_id] = att
	return att


## Rest offset of a bone from its parent (its zero-pose position in the parent's space).
func offset_of(bone_id: String) -> Vector3:
	return _offsets.get(bone_id, Vector3.ZERO)


## Zero-pose position of a bone in skeleton (model) space.
func rest_position(bone_id: String) -> Vector3:
	var p := Vector3.ZERO
	var i := find_bone(bone_id)
	while i >= 0:
		p += _offsets[get_bone_name(i)]
		i = get_bone_parent(i)
	return p


func limits(joint_name: String, axis: String) -> Vector2:
	return spec["joints"][joint_name]["limits"][axis]


## Ask for an angle; it is clamped to the joint's limits (and the clamp is counted).
func set_angle(joint_name: String, axis: String, value: float) -> void:
	var lim := limits(joint_name, axis)
	var clamped := clampf(value, lim.x, lim.y)
	if absf(clamped - value) > deg_to_rad(0.5):
		clamp_count += 1
		if clamp_log.size() < 20:
			clamp_log.append("%s.%s %.1f° (limits %.0f..%.0f)" % [joint_name, axis, rad_to_deg(value),
				rad_to_deg(lim.x), rad_to_deg(lim.y)])
	angles[joint_name][axis] = clamped


func set_angles(values: Dictionary) -> void:
	for joint_name in values:
		for axis in values[joint_name]:
			set_angle(joint_name, axis, float(values[joint_name][axis]))


## Remember the current angles as the pose every layer starts from.
func store_rest_angles() -> void:
	_rest_angles = angles.duplicate(true)


func rest_angles() -> Dictionary:
	return _rest_angles.duplicate(true)


## Where the root sits: posture (root_pose) times the Body joint's pose about its pivot, if any.
## `body_angles` (optional) stands in for the Body joint's current angles.
func body_transform(body_angles := {}) -> Transform3D:
	if not angles.has("Body"):
		return root_pose
	var saved: Dictionary = angles["Body"]
	if not body_angles.is_empty():
		angles["Body"] = body_angles
	var b := joint_basis("Body")
	angles["Body"] = saved
	return root_pose * Transform3D(Basis.IDENTITY, body_pivot + Vector3(0, -body_drop, 0)) * Transform3D(b, Vector3.ZERO) \
		* Transform3D(Basis.IDENTITY, -body_pivot)


## Rotation of a joint from its angles: about each of its axes in order, outermost first.
func joint_basis(joint_name: String) -> Basis:
	var b := Basis.IDENTITY
	var a: Dictionary = angles[joint_name]
	for axis_pair in spec["joints"][joint_name]["axes"]:
		b = b * Basis(axis_pair[1], float(a[String(axis_pair[0])]))
	return b


## Write every angle into the bone poses and (unless `move_parts` is false: a step between
## layers) move the attached parts at once.
func apply(move_parts := true) -> void:
	for joint_name in angles:
		var i := find_bone(joint_name)
		if joint_name == "Body":
			continue   # applied to the root bone below
		if joint_name == "Gripper":
			var half := float(angles[joint_name]["open"]) / 2.0
			set_bone_pose_rotation(find_bone("GripperFingerL"), Quaternion(Vector3.UP, -half))
			set_bone_pose_rotation(find_bone("GripperFingerR"), Quaternion(Vector3.UP, half))
			continue
		set_bone_pose_rotation(i, joint_basis(joint_name).get_rotation_quaternion())
	for wheel in spin:
		set_bone_pose_rotation(find_bone(wheel), Quaternion(Vector3.RIGHT, float(spin[wheel])))
	if _root != "":
		var root_t := body_transform() * Transform3D(Basis.IDENTITY, _offsets[_root])
		set_bone_pose_position(find_bone(_root), root_t.origin)
		set_bone_pose_rotation(find_bone(_root), root_t.basis.get_rotation_quaternion())
	for level in level_bones:
		var i := find_bone(level)
		var parent_basis := get_bone_global_pose(get_bone_parent(i)).basis
		set_bone_pose_rotation(i, (parent_basis.inverse() * body_transform().basis).get_rotation_quaternion())
	if not move_parts:
		return
	for att in _attachments.values():
		(att as BoneAttachment3D).on_skeleton_update()


## A bone's transform in skeleton space with the poses set so far.
func bone_global(bone_id: String) -> Transform3D:
	return get_bone_global_pose(find_bone(bone_id))


## "" if every angle is inside its limits and every joint bone carries exactly the rotation its
## angles describe (so nothing bypassed the clamp); otherwise what is wrong.
func check_pose() -> String:
	for joint_name in angles:
		for axis in angles[joint_name]:
			var v := float(angles[joint_name][axis])
			var lim := limits(joint_name, axis)
			if v < lim.x - 1e-5 or v > lim.y + 1e-5:
				return "%s.%s is %.2f°, limits %.1f..%.1f°" % [joint_name, axis, rad_to_deg(v), rad_to_deg(lim.x), rad_to_deg(lim.y)]
		if joint_name == "Gripper":
			continue
		if joint_name == "Body":
			if not get_bone_pose_rotation(find_bone(_root)).is_equal_approx(body_transform().basis.get_rotation_quaternion()):
				return "the root bone does not carry the Body joint's pose"
			continue
		var q := get_bone_pose_rotation(find_bone(joint_name))
		if not q.is_equal_approx(joint_basis(joint_name).get_rotation_quaternion()):
			return "%s bone rotation does not match its joint angles" % joint_name
	return ""


## Every joint angle, rounded to 1e-6 rad, plus root and wheels: equal digests, equal poses.
func digest() -> String:
	var parts: PackedStringArray = []
	var names := angles.keys()
	names.sort()
	for joint_name in names:
		var axes: Array = angles[joint_name].keys()
		axes.sort()
		for axis in axes:
			parts.append("%s.%s=%d" % [joint_name, axis, roundi(float(angles[joint_name][axis]) * 1e6)])
	var wheels := spin.keys()
	wheels.sort()
	for wheel in wheels:
		parts.append("%s=%d" % [wheel, roundi(float(spin[wheel]) * 1e6)])
	parts.append("drop=%d" % roundi(body_drop * 1e6))
	for c in [root_pose.basis.x, root_pose.basis.y, root_pose.basis.z, root_pose.origin]:
		var v: Vector3 = c
		parts.append("root=%d,%d,%d" % [roundi(v.x * 1e6), roundi(v.y * 1e6), roundi(v.z * 1e6)])
	return "|".join(parts).sha256_text()
