class_name RobotParts
extends RefCounted
## Shared builders for greybox robot models: faceted primitives, joints, limb segments,
## identity badges and trim bands (ART_DIRECTION §2, §3; D-36).


static func mat(color_name: String) -> StandardMaterial3D:
	return Palette.material(color_name)


static func joint(parent: Node3D, node_name: String, pos: Vector3) -> Node3D:
	var j := Node3D.new()
	j.name = node_name
	j.position = pos
	parent.add_child(j)
	return j


static func cyl(parent: Node3D, node_name: String, top_r: float, bottom_r: float, h: float, segments: int,
		color_name: String, pos: Vector3, squash_z := 1.0) -> MeshInstance3D:
	var c := CylinderMesh.new()
	c.top_radius = top_r
	c.bottom_radius = bottom_r
	c.height = h
	c.radial_segments = segments
	c.rings = 1
	var mi := MeshKit.mesh_instance(MeshKit.faceted(c), mat(color_name), node_name, pos)
	mi.scale = Vector3(1, 1, squash_z)
	parent.add_child(mi)
	return mi


static func sphere(parent: Node3D, node_name: String, r: float, h: float, segments: int, rings: int,
		color_name: String, pos: Vector3, scale_xyz := Vector3.ONE) -> MeshInstance3D:
	var s := SphereMesh.new()
	s.radius = r
	s.height = h
	s.radial_segments = segments
	s.rings = rings
	var mi := MeshKit.mesh_instance(MeshKit.faceted(s), mat(color_name), node_name, pos)
	mi.scale = scale_xyz
	parent.add_child(mi)
	return mi


static func box(parent: Node3D, node_name: String, size: Vector3, color_name: String, pos: Vector3) -> MeshInstance3D:
	var mi := MeshKit.mesh_instance(MeshKit.box_mesh(size), mat(color_name), node_name, pos)
	parent.add_child(mi)
	return mi


## A limb segment from a to b (in the parent's space): a faceted cylinder or a box.
static func segment(parent: Node3D, node_name: String, a: Vector3, b: Vector3, thickness: float,
		color_name: String, as_box := false) -> MeshInstance3D:
	var length := a.distance_to(b)
	var mesh: Mesh
	if as_box:
		mesh = MeshKit.box_mesh(Vector3(thickness, length, thickness * 1.3))
	else:
		var c := CylinderMesh.new()
		c.top_radius = thickness / 2
		c.bottom_radius = thickness / 2
		c.height = length
		c.radial_segments = 6
		c.rings = 1
		mesh = MeshKit.faceted(c)
	var mi := MeshKit.mesh_instance(mesh, mat(color_name), node_name)
	var up := (b - a).normalized()
	var side := up.cross(Vector3.FORWARD)
	if side.length() < 0.01:
		side = up.cross(Vector3.RIGHT)
	side = side.normalized()
	mi.transform = Transform3D(Basis(side, up, side.cross(up)).orthonormalized(), (a + b) / 2)
	parent.add_child(mi)
	return mi


## Identity badge (a number) facing along `facing` (ART_DIRECTION §2.1).
static func badge(parent: Node3D, node_name: String, text: String, pos: Vector3, facing: Vector3, size_m := 0.08) -> Label3D:
	var l := MeshKit.label(text, 40, false)
	l.name = node_name
	l.pixel_size = size_m / 32.0
	l.outline_size = 0
	parent.add_child(l)
	# Label3D text faces +z; turn it to face `facing`.
	l.transform = Transform3D(Basis.looking_at(-facing, Vector3.UP), pos)
	return l


static func name_tag(parent: Node3D, text: String, height_m: float) -> Label3D:
	var tag := MeshKit.label(text, 40)
	tag.name = "NameTag"
	tag.position = Vector3(0, height_m + 0.3, 0)
	parent.add_child(tag)
	return tag
