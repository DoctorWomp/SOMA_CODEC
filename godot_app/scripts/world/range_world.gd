class_name RangeWorld
extends Node3D
## One simulated world: the map, its navigation, the fixed-tick clock and the avatars.
## Godot is the only world authority (D-04): positions, collision and paths live here.
##
## Each world has its own navigation map, so several worlds can exist side by side
## later (isolated controlled trials) without sharing paths.

signal navigation_ready

const NAV_CELL_SIZE := 0.1
const NAV_CELL_HEIGHT := 0.05
const NAV_MAX_CLIMB_M := 0.2
const NAV_MAX_SLOPE_DEG := 30.0
const NAV_OBSTRUCTION_HEIGHT_M := 3.0

var map_data: Dictionary = {}
var bodies: Dictionary = {}       # body_id -> body config
var registry: Dictionary = {}     # what MapBuilder built, by map id
var clock: SimClock
var nav_map: RID
var nav_region: NavigationRegion3D
var nav_links: Dictionary = {}    # link_id -> NavigationLink3D
var avatars: Dictionary = {}      # avatar_id -> Avatar
var _avatar_root: Node3D
var _nav_ready := false


## Load the map and bodies, build everything. Returns false (with an error printed) on bad data.
func build(map_id: String, body_ids: Array) -> bool:
	map_data = WorldData.load_map(map_id)
	if map_data.is_empty():
		return false
	for body_id in body_ids:
		var body := WorldData.load_body(String(body_id))
		if body.is_empty():
			return false
		bodies[String(body_id)] = body
	name = "World_" + map_id
	clock = SimClock.new()
	add_child(clock)
	var map_root := Node3D.new()
	map_root.name = "Map"
	add_child(map_root)
	registry = MapBuilder.build(map_root, map_data)
	_avatar_root = Node3D.new()
	_avatar_root.name = "Avatars"
	add_child(_avatar_root)
	_build_navigation()
	return true


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and nav_map.is_valid():
		NavigationServer3D.free_rid(nav_map)


## Navigation is ready once the map can answer queries: the baked polygons and every link
## are in the map's current iteration. Map updates are asynchronous, so this takes a few ticks.
func _physics_process(_delta: float) -> void:
	if _nav_ready or not nav_map.is_valid():
		return
	if NavigationServer3D.map_get_iteration_id(nav_map) == 0:
		return
	if NavigationServer3D.map_get_links(nav_map).size() != nav_links.size():
		return
	var probe := Vector3(0.5, 0.0, 0.5) * Vector3(registry["bounds"].x, 0.0, registry["bounds"].y)
	if NavigationServer3D.map_get_closest_point_owner(nav_map, probe) != nav_region.get_rid():
		return
	_nav_ready = true
	navigation_ready.emit()


func is_navigation_ready() -> bool:
	return _nav_ready


func wait_navigation_ready() -> void:
	if not _nav_ready:
		await navigation_ready


## Bake the floor and platform tops into one region; add the ramp and stairs as links on
## their capability layers (D-31). The ramp and stair footprints are kept out of the bake,
## so the only way onto a platform is through a link the body is allowed to use.
func _build_navigation() -> void:
	nav_map = NavigationServer3D.map_create()
	NavigationServer3D.map_set_up(nav_map, Vector3.UP)
	NavigationServer3D.map_set_cell_size(nav_map, NAV_CELL_SIZE)
	NavigationServer3D.map_set_cell_height(nav_map, NAV_CELL_HEIGHT)
	NavigationServer3D.map_set_active(nav_map, true)

	var max_radius := 0.25
	var max_height := 1.7
	for body in bodies.values():
		max_radius = maxf(max_radius, float(body["dimensions"]["radius_m"]))
		max_height = maxf(max_height, float(body["dimensions"]["height_m"]))

	var nm := NavigationMesh.new()
	nm.cell_size = NAV_CELL_SIZE
	nm.cell_height = NAV_CELL_HEIGHT
	nm.agent_radius = ceilf(max_radius / NAV_CELL_SIZE - 1e-6) * NAV_CELL_SIZE
	nm.agent_height = max_height
	nm.agent_max_climb = NAV_MAX_CLIMB_M
	nm.agent_max_slope = NAV_MAX_SLOPE_DEG
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = Layers.WORLD
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_ROOT_NODE_CHILDREN
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(nm, source, registry["nav_source"])
	for link in registry["links"].values():
		var outline := PackedVector3Array()
		for p in link["footprint"]:
			outline.append(Vector3(p.x, 0.0, p.y))
		source.add_projected_obstruction(outline, -0.1, NAV_OBSTRUCTION_HEIGHT_M, false)
	NavigationServer3D.bake_from_source_geometry_data(nm, source)

	nav_region = NavigationRegion3D.new()
	nav_region.name = "NavRegion"
	nav_region.navigation_layers = Layers.NAV_FLOOR
	nav_region.navigation_mesh = nm
	add_child(nav_region)
	nav_region.set_navigation_map(nav_map)

	for link_id in registry["links"]:
		var info: Dictionary = registry["links"][link_id]
		var link := NavigationLink3D.new()
		link.name = link_id
		link.bidirectional = true
		link.start_position = info["from"]
		link.end_position = info["to"]
		link.navigation_layers = int(Layers.NAV_CAPABILITY[info["required_capability"]])
		add_child(link)
		link.set_navigation_map(nav_map)
		nav_links[link_id] = link


func ground_height(x: float, z: float) -> float:
	return MapBuilder.ground_height(map_data, Vector2(x, z))


func ground_point(x: float, z: float) -> Vector3:
	return Vector3(x, ground_height(x, z), z)


func spawn_point(spawn_id: String) -> Dictionary:
	return registry["spawns"].get(spawn_id, {})


## Place an avatar. `appearance` may hold "color" (a Palette name) for visitors.
func spawn_avatar(avatar_id: String, body_id: String, at: Vector3, yaw: float, appearance := {}) -> Avatar:
	if not bodies.has(body_id):
		push_error("RangeWorld: body '%s' was not loaded for avatar '%s'" % [body_id, avatar_id])
		return null
	if avatars.has(avatar_id):
		push_error("RangeWorld: avatar '%s' already exists" % avatar_id)
		return null
	var avatar := Avatar.new()
	avatar.setup(avatar_id, bodies[body_id], appearance)
	avatar.position = Vector3(at.x, ground_height(at.x, at.z), at.z)
	avatar.rotation.y = yaw
	_avatar_root.add_child(avatar)
	avatar.attach_navigation(nav_map)
	avatars[avatar_id] = avatar
	return avatar


func spawn_at(avatar_id: String, body_id: String, spawn_id: String, appearance := {}) -> Avatar:
	var spawn := spawn_point(spawn_id)
	if spawn.is_empty():
		push_error("RangeWorld: unknown spawn point '%s'" % spawn_id)
		return null
	return spawn_avatar(avatar_id, body_id, spawn["position"], spawn["yaw"], appearance)


func avatar_list() -> Array:
	var ids := avatars.keys()
	ids.sort()
	var out := []
	for avatar_id in ids:
		out.append(avatars[avatar_id])
	return out


## Plan a path without moving anyone. Returns {"path": PackedVector3Array, "links": [link ids used]}.
func query_path(from: Vector3, to: Vector3, nav_mask: int) -> Dictionary:
	var params := NavigationPathQueryParameters3D.new()
	params.map = nav_map
	params.start_position = from
	params.target_position = to
	params.navigation_layers = nav_mask
	params.metadata_flags = NavigationPathQueryParameters3D.PATH_METADATA_INCLUDE_OWNERS
	var result := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(params, result)
	var links: Array[String] = []
	for owner_id in result.path_owner_ids:
		var owner := instance_from_id(owner_id)
		if owner is NavigationLink3D and not links.has(String(owner.name)):
			links.append(String(owner.name))
	return {"path": result.path, "links": links}
