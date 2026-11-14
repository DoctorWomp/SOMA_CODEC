class_name MapBuilder
extends RefCounted
## Builds a map's static world from its data (configs/maps/*.yaml, exported per D-30).
##
## Everything placed here comes from the map file. Sizes the map contract does not
## describe yet (wall thickness, ramp and stair width, prop sizes) use the constants
## below and are recorded in D-31.
##
## Coordinates follow D-29: meters, x right, z toward the viewer on a top-down view, y up.

const WALL_THICKNESS_M := 0.2
const FLOOR_THICKNESS_M := 0.2
const RAMP_WIDTH_M := 1.5
const STAIR_WIDTH_M := 1.5
const MAX_STEP_RISE_M := 0.18
const GRID_STEP_M := 5.0
const ZONE_VOLUME_HEIGHT_M := 3.0

## Greybox collision sizes per prop type, until a props catalog contract exists (G6).
const PROP_SIZES := {
	"CHAIR": Vector3(0.5, 0.9, 0.5),
	"PA_SPEAKER": Vector3(0.45, 1.9, 0.45),
}


## Build the map under `root`. Returns a registry of what was built, keyed by the map's ids.
## Static geometry that navigation should bake from goes under the "NavSource" child.
static func build(root: Node3D, map: Dictionary) -> Dictionary:
	var bounds := Vector2(float(map["bounds"]["width_m"]), float(map["bounds"]["depth_m"]))
	var reg := {
		"bounds": bounds,
		"walls": {},
		"platforms": {},
		"links": {},
		"props": {},
		"zones": {},
		"spawns": {},
	}
	var nav_source := Node3D.new()
	nav_source.name = "NavSource"
	root.add_child(nav_source)
	reg["nav_source"] = nav_source
	for group_name in ["Links", "Zones", "Spawns", "Labels"]:
		var group := Node3D.new()
		group.name = group_name
		root.add_child(group)

	_build_floor(nav_source, root, bounds)
	for wall in map.get("walls", []):
		reg["walls"][wall["wall_id"]] = _build_wall(nav_source, root, wall, bounds)
	for platform in map.get("platforms", []):
		reg["platforms"][platform["platform_id"]] = _build_platform(nav_source, platform)
	for link in map.get("nav_links", []):
		var built := _build_link(root.get_node("Links"), link, map)
		if not built.is_empty():
			reg["links"][link["link_id"]] = built
	for prop in map.get("props", []):
		var node := _build_prop(nav_source, prop, map)
		if node != null:
			reg["props"][prop["prop_id"]] = node
	var index := 0
	for zone in map.get("zones", []):
		reg["zones"][zone["zone_id"]] = _build_zone(root.get_node("Zones"), zone, map, index)
		index += 1
	for spawn in map.get("spawn_points", []):
		reg["spawns"][spawn["spawn_id"]] = _build_spawn(root.get_node("Spawns"), spawn, map)
	return reg


## Height of the walkable surface at (x, z): the highest platform containing the point, else 0.
static func ground_height(map: Dictionary, p: Vector2) -> float:
	var h := 0.0
	for platform in map.get("platforms", []):
		var a: Dictionary = platform["area"]
		if p.x >= float(a["x_min"]) and p.x <= float(a["x_max"]) and p.y >= float(a["z_min"]) and p.y <= float(a["z_max"]):
			h = maxf(h, float(platform["height_m"]))
	return h


static func _p2(point: Dictionary) -> Vector2:
	return Vector2(float(point["x"]), float(point["z"]))


static func _static_box(parent: Node, node_name: String, center: Vector3, size: Vector3, yaw: float,
		color_name: String, layer := Layers.WORLD) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.collision_layer = layer
	body.collision_mask = 0
	body.position = center
	body.rotation.y = yaw
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	if color_name != "":
		body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(size), Palette.material(color_name), "Mesh"))
	parent.add_child(body)
	return body


static func _add_label(parent: Node, text: String, position: Vector3, font_size := 48) -> Label3D:
	var l := MeshKit.label(text, font_size)
	l.position = position
	parent.add_child(l)
	return l


static func _build_floor(nav_source: Node3D, root: Node3D, bounds: Vector2) -> void:
	_static_box(nav_source, "Floor", Vector3(bounds.x / 2, -FLOOR_THICKNESS_M / 2, bounds.y / 2),
		Vector3(bounds.x, FLOOR_THICKNESS_M, bounds.y), 0.0, "floor")
	var grid := Node3D.new()
	grid.name = "FloorGrid"
	root.add_child(grid)
	var mat := Palette.material("floor_grid")
	var x := GRID_STEP_M
	while x < bounds.x - 0.01:
		grid.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.03, 0.002, bounds.y)), mat, "GridX",
			Vector3(x, 0.002, bounds.y / 2)))
		x += GRID_STEP_M
	var z := GRID_STEP_M
	while z < bounds.y - 0.01:
		grid.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(bounds.x, 0.002, 0.03)), mat, "GridZ",
			Vector3(bounds.x / 2, 0.002, z)))
		z += GRID_STEP_M


static func _build_wall(nav_source: Node3D, root: Node3D, wall: Dictionary, bounds: Vector2) -> StaticBody3D:
	var a := _p2(wall["a"])
	var b := _p2(wall["b"])
	var d := b - a
	var length := d.length()
	var height := float(wall["height_m"])
	var movable := bool(wall.get("movable", false))
	var reflective := bool(wall.get("acoustically_reflective", false))
	var mid := (a + b) / 2
	var body := _static_box(nav_source, String(wall["wall_id"]), Vector3(mid.x, height / 2, mid.y),
		Vector3(length + WALL_THICKNESS_M, height, WALL_THICKNESS_M), atan2(-d.y, d.x),
		"partition" if movable else "wall")
	body.set_meta("wall_id", wall["wall_id"])
	body.set_meta("blocks_sight", bool(wall["blocks_sight"]))
	body.set_meta("blocks_sound", bool(wall["blocks_sound"]))
	body.set_meta("movable", movable)
	body.set_meta("acoustically_reflective", reflective)
	if movable:
		_add_label(root.get_node("Labels"), String(wall["wall_id"]), Vector3(mid.x, height + 0.35, mid.y), 40)
	if reflective:
		_add_reflective_marker(root.get_node("Labels"), a, b, height, bounds)
	return body


## Diagonal stripes and a label on the inner face of an acoustically reflective wall (SB-03).
## Pattern plus words, never color alone (ART_DIRECTION §8).
static func _add_reflective_marker(parent: Node3D, a: Vector2, b: Vector2, height: float, bounds: Vector2) -> void:
	var d := (b - a).normalized()
	var n := Vector2(-d.y, d.x)
	var mid := (a + b) / 2
	if n.dot(bounds / 2 - mid) < 0.0:
		n = -n
	var normal := Vector3(n.x, 0, n.y)
	var basis := Basis(Vector3.UP.cross(normal).normalized(), Vector3.UP, normal)
	var panel_len := (b - a).length() - 0.6
	var panel_h := minf(1.6, height - 0.6)

	var img := Image.create(16, 16, false, Image.FORMAT_RGB8)
	for px in 16:
		for py in 16:
			var stripe := ((px + py) / 4) % 2 == 0
			img.set_pixel(px, py, Palette.color("reflective_b" if stripe else "reflective_a"))
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = ImageTexture.create_from_image(img)
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	mat.uv1_scale = Vector3(panel_len / 0.8, panel_h / 0.8, 1)
	mat.roughness = 0.9

	var quad := QuadMesh.new()
	quad.size = Vector2(panel_len, panel_h)
	var panel := MeshKit.mesh_instance(quad, mat, "ReflectiveWallMarker")
	panel.transform = Transform3D(basis, Vector3(mid.x, 0.4 + panel_h / 2, mid.y) + normal * (WALL_THICKNESS_M / 2 + 0.01))
	parent.add_child(panel)

	var text := MeshKit.label("ACOUSTICALLY REFLECTIVE WALL", 64, false)
	text.transform = Transform3D(basis, Vector3(mid.x, 0.4 + panel_h + 0.35, mid.y) + normal * (WALL_THICKNESS_M / 2 + 0.02))
	text.name = "ReflectiveWallLabel"
	parent.add_child(text)


static func _build_platform(nav_source: Node3D, platform: Dictionary) -> StaticBody3D:
	var a: Dictionary = platform["area"]
	var x0 := float(a["x_min"])
	var x1 := float(a["x_max"])
	var z0 := float(a["z_min"])
	var z1 := float(a["z_max"])
	var h := float(platform["height_m"])
	var body := _static_box(nav_source, String(platform["platform_id"]), Vector3((x0 + x1) / 2, h / 2, (z0 + z1) / 2),
		Vector3(x1 - x0, h, z1 - z0), 0.0, "platform")
	body.set_meta("height_m", h)
	return body


## Six corners of a wedge rising from the `from` edge (height fh) to the `to` edge (height th).
static func _wedge_points(fl: Vector2, fr: Vector2, tl: Vector2, tr: Vector2, fh: float, th: float) -> Array:
	return [
		Vector3(fl.x, fh, fl.y), Vector3(fr.x, fh, fr.y),  # A, B: low edge
		Vector3(tl.x, fh, tl.y), Vector3(tr.x, fh, tr.y),  # C, D: under the high edge
		Vector3(tl.x, th, tl.y), Vector3(tr.x, th, tr.y),  # E, F: high edge
	]


static func _wedge_body(parent: Node, node_name: String, pts: Array, layer: int, color_name: String) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.collision_layer = layer
	body.collision_mask = 0
	var cs := CollisionShape3D.new()
	var shape := ConvexPolygonShape3D.new()
	shape.points = PackedVector3Array(pts)
	cs.shape = shape
	body.add_child(cs)
	if color_name != "":
		var faces := [
			[pts[0], pts[1], pts[3], pts[2]],  # bottom
			[pts[0], pts[1], pts[5], pts[4]],  # slope
			[pts[2], pts[3], pts[5], pts[4]],  # high end
			[pts[0], pts[2], pts[4]],  # side
			[pts[1], pts[3], pts[5]],  # side
		]
		body.add_child(MeshKit.mesh_instance(MeshKit.convex_faces(faces), Palette.material(color_name, true), "Mesh"))
	parent.add_child(body)
	return body


## A ramp or a stair between the floor and a platform, placed by a map nav_link.
## Ramp: one solid wedge for everyone. Stairs: real steps for bodies that cannot use stairs,
## plus a smooth walking surface only bodies with can_use_stairs collide with (D-31).
static func _build_link(parent: Node3D, link: Dictionary, map: Dictionary) -> Dictionary:
	var link_id := String(link["link_id"])
	var kind := String(link["kind"])
	var from2 := _p2(link["from"])
	var to2 := _p2(link["to"])
	var fh := ground_height(map, from2)
	var th := ground_height(map, to2)
	if th <= fh or from2.distance_to(to2) < 0.1:
		push_error("MapBuilder: nav link '%s' must rise from 'from' to 'to' (got %.2f m -> %.2f m)" % [link_id, fh, th])
		return {}
	var length := from2.distance_to(to2)
	var d := (to2 - from2) / length
	var n := Vector2(-d.y, d.x)
	var width := RAMP_WIDTH_M if kind == "RAMP" else STAIR_WIDTH_M
	var fl := from2 + n * width / 2
	var fr := from2 - n * width / 2
	var tl := to2 + n * width / 2
	var tr := to2 - n * width / 2
	var pts := _wedge_points(fl, fr, tl, tr, fh, th)
	var yaw := atan2(-d.y, d.x)

	var node := Node3D.new()
	node.name = link_id
	parent.add_child(node)
	var steps := 0
	if kind == "RAMP":
		_wedge_body(node, "Ramp", pts, Layers.WORLD, "ramp")
	else:
		steps = int(ceil((th - fh) / MAX_STEP_RISE_M - 1e-6))
		var rise := (th - fh) / steps
		var run := length / steps
		for i in steps:
			var start := from2 + d * run * i
			var c := (start + to2) / 2
			var h := rise * (i + 1)
			_static_box(node, "Step%d" % (i + 1), Vector3(c.x, fh + h / 2, c.y),
				Vector3(run * (steps - i), h, width), yaw, "stairs", Layers.STAIRS_STEPS)
		_wedge_body(node, "WalkSurface", pts, Layers.STAIRS_WALK_SURFACE, "")
	var mid := (from2 + to2) / 2
	_add_label(node, kind, Vector3(mid.x, th + 0.9, mid.y), 40)
	node.set_meta("kind", kind)
	node.set_meta("required_capability", String(link["required_capability"]))
	return {
		"kind": kind,
		"required_capability": String(link["required_capability"]),
		"from": Vector3(from2.x, fh, from2.y),
		"to": Vector3(to2.x, th, to2.y),
		"width": width,
		"steps": steps,
		"footprint": PackedVector2Array([fl, tl, tr, fr]),
		"node": node,
	}


static func _build_prop(nav_source: Node3D, prop: Dictionary, map: Dictionary) -> Node3D:
	var prop_type := String(prop["prop_type"])
	if not PROP_SIZES.has(prop_type):
		push_error("MapBuilder: prop '%s' has unknown prop_type '%s' (known: %s)" % [
			prop["prop_id"], prop_type, ", ".join(PROP_SIZES.keys())])
		return null
	var size: Vector3 = PROP_SIZES[prop_type]
	var p := _p2(prop["position"])
	var body := StaticBody3D.new()
	body.name = String(prop["prop_id"])
	body.collision_layer = Layers.WORLD
	body.collision_mask = 0
	body.position = Vector3(p.x, ground_height(map, p), p.y)
	body.rotation.y = float(prop.get("yaw_rad", 0.0))
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	cs.position.y = size.y / 2
	body.add_child(cs)
	body.set_meta("prop_type", prop_type)
	match prop_type:
		"CHAIR":
			_chair_visual(body)
		"PA_SPEAKER":
			_pa_speaker_visual(body)
	nav_source.add_child(body)
	return body


## A chair facing -z (its own forward), seat at 0.45 m.
static func _chair_visual(body: Node3D) -> void:
	var mat := Palette.material("chair")
	var leg := MeshKit.box_mesh(Vector3(0.04, 0.42, 0.04))
	for sx in [-0.2, 0.2]:
		for sz in [-0.2, 0.2]:
			body.add_child(MeshKit.mesh_instance(leg, Palette.material("prop_dark"), "Leg", Vector3(sx, 0.21, sz)))
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.46, 0.06, 0.46)), mat, "Seat", Vector3(0, 0.45, 0)))
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.46, 0.42, 0.05)), mat, "Back", Vector3(0, 0.69, 0.205)))


## A loudspeaker cabinet on a pole stand, front grille facing -z (its own forward).
static func _pa_speaker_visual(body: Node3D) -> void:
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.4, 0.03, 0.4)), Palette.material("prop_dark"), "Base", Vector3(0, 0.015, 0)))
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.05, 1.25, 0.05)), Palette.material("prop_mid"), "Pole", Vector3(0, 0.625, 0)))
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.42, 0.62, 0.36)), Palette.material("prop_dark"), "Cabinet", Vector3(0, 1.56, 0)))
	body.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(0.34, 0.5, 0.02)), Palette.material("prop_mid"), "Grille", Vector3(0, 1.56, -0.185)))
	var l := MeshKit.label("PA", 48)
	l.position = Vector3(0, 2.15, 0)
	body.add_child(l)


## A zone volume carrying its environment values, plus a floor shade whose darkness follows
## light_level, so what the viewer sees matches what senses will use (ART_DIRECTION §5).
static func _build_zone(parent: Node3D, zone: Dictionary, map: Dictionary, index: int) -> Area3D:
	var a: Dictionary = zone["area"]
	var x0 := float(a["x_min"])
	var x1 := float(a["x_max"])
	var z0 := float(a["z_min"])
	var z1 := float(a["z_max"])
	var center2 := Vector2((x0 + x1) / 2, (z0 + z1) / 2)
	var base := ground_height(map, center2)
	var env: Dictionary = zone["environment"]
	var area := Area3D.new()
	area.name = String(zone["zone_id"])
	area.collision_layer = 0
	area.collision_mask = Layers.AVATARS
	area.monitorable = false
	area.position = Vector3(center2.x, base + ZONE_VOLUME_HEIGHT_M / 2, center2.y)
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(x1 - x0, ZONE_VOLUME_HEIGHT_M, z1 - z0)
	cs.shape = shape
	area.add_child(cs)
	area.set_meta("zone_id", zone["zone_id"])
	area.set_meta("environment", env)
	var shade := MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(x1 - x0, 0.002, z1 - z0)),
		Palette.shade_material(float(env["light_level"])), "LightShade",
		Vector3(0, -ZONE_VOLUME_HEIGHT_M / 2 + 0.006 + 0.002 * index, 0))
	area.add_child(shade)
	var text := "%s\nlight %.1f · %d dB" % [zone["zone_id"], float(env["light_level"]), int(round(float(env["noise_floor_db"])))]
	var l := MeshKit.label(text, 72, false)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	l.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	l.rotation.x = -PI / 2
	l.position = Vector3(x0 - center2.x + 0.3, -ZONE_VOLUME_HEIGHT_M / 2 + 0.02, z0 - center2.y + 0.3)
	area.add_child(l)
	parent.add_child(area)
	return area


static func _build_spawn(parent: Node3D, spawn: Dictionary, map: Dictionary) -> Dictionary:
	var p := _p2(spawn["position"])
	var yaw := float(spawn["yaw_rad"])
	var pos := Vector3(p.x, ground_height(map, p), p.y)
	var marker := Node3D.new()
	marker.name = String(spawn["spawn_id"])
	marker.position = pos
	marker.rotation.y = yaw
	var disc := CylinderMesh.new()
	disc.top_radius = 0.3
	disc.bottom_radius = 0.3
	disc.height = 0.01
	disc.radial_segments = 12
	marker.add_child(MeshKit.mesh_instance(disc, Palette.material("marker"), "Disc", Vector3(0, 0.006, 0)))
	var arrow := MeshKit.box_mesh(Vector3(0.06, 0.012, 0.28))
	marker.add_child(MeshKit.mesh_instance(arrow, Palette.material("prop_dark"), "Facing", Vector3(0, 0.012, -0.14)))
	parent.add_child(marker)
	return {"position": pos, "yaw": yaw, "node": marker}
