class_name MeshKit
extends RefCounted
## Small helpers for building greybox geometry from primitives.


## Re-shade a primitive mesh with one normal per triangle: the faceted low-poly look
## (ART_DIRECTION §1, §3). Winding is kept, so back-face culling still works.
static func faceted(mesh: PrimitiveMesh) -> ArrayMesh:
	var arrays := mesh.get_mesh_arrays()
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
	var count := indices.size() if indices.size() > 0 else verts.size()
	var out_v := PackedVector3Array()
	var out_n := PackedVector3Array()
	for t in range(0, count - 2, 3):
		var ia := indices[t] if indices.size() > 0 else t
		var ib := indices[t + 1] if indices.size() > 0 else t + 1
		var ic := indices[t + 2] if indices.size() > 0 else t + 2
		var a := verts[ia]
		var b := verts[ib]
		var c := verts[ic]
		var n := (b - a).cross(c - a)
		if n.length_squared() < 1e-14:
			continue
		n = n.normalized()
		if n.dot(normals[ia] + normals[ib] + normals[ic]) < 0.0:
			n = -n
		out_v.append_array([a, b, c])
		out_n.append_array([n, n, n])
	var out := []
	out.resize(Mesh.ARRAY_MAX)
	out[Mesh.ARRAY_VERTEX] = out_v
	out[Mesh.ARRAY_NORMAL] = out_n
	var result := ArrayMesh.new()
	result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, out)
	return result


## Mesh from convex polygon faces (each a list of 3+ points), with normals pointing away
## from the shape's center. Use a double-sided material with it.
static func convex_faces(faces: Array) -> ArrayMesh:
	var center := Vector3.ZERO
	var n_points := 0
	for face in faces:
		for p in face:
			center += p
			n_points += 1
	center /= maxf(n_points, 1)
	var out_v := PackedVector3Array()
	var out_n := PackedVector3Array()
	for face in faces:
		var pts: Array = face
		var face_center := Vector3.ZERO
		for p in pts:
			face_center += p
		face_center /= pts.size()
		var n: Vector3 = (pts[1] - pts[0]).cross(pts[2] - pts[0]).normalized()
		if n.dot(face_center - center) < 0.0:
			n = -n
		for i in range(1, pts.size() - 1):
			out_v.append_array([pts[0], pts[i], pts[i + 1]])
			out_n.append_array([n, n, n])
	var out := []
	out.resize(Mesh.ARRAY_MAX)
	out[Mesh.ARRAY_VERTEX] = out_v
	out[Mesh.ARRAY_NORMAL] = out_n
	var result := ArrayMesh.new()
	result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, out)
	return result


static func mesh_instance(mesh: Mesh, material: Material, node_name: String, position := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = mesh
	mi.material_override = material
	mi.position = position
	return mi


static func box_mesh(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


## A floating text label, readable from both sides (billboard) or fixed (facing +z).
static func label(text: String, font_size := 48, billboard := true) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font_size = font_size
	l.pixel_size = 0.005
	l.modulate = Palette.color("label")
	l.outline_modulate = Color(1, 1, 1, 0.85)
	l.outline_size = 8
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED if billboard else BaseMaterial3D.BILLBOARD_DISABLED
	return l
