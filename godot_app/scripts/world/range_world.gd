class_name RangeWorld
extends Node3D
## One simulated world: the map, its navigation, the fixed-tick clock and the avatars.
## Godot is the only world authority (D-04): positions, collision and paths live here.
##
## Navigation is per body size (D-37): one navigation map for each distinct navigation
## radius among the loaded bodies, each baked so that bodies of that size keep clear of walls.
## A quadruped's long footprint therefore does not narrow the paths of people. Every world
## owns its maps, so several worlds can exist side by side later (isolated controlled trials).

signal navigation_ready

const NAV_CELL_SIZE := Bodies.NAV_CELL_M
const NAV_CELL_HEIGHT := 0.05
const NAV_MAX_CLIMB_M := 0.2
const NAV_MAX_SLOPE_DEG := 30.0
const NAV_OBSTRUCTION_HEIGHT_M := 3.0

var map_data: Dictionary = {}
var bodies: Dictionary = {}       # body_id -> body config
var registry: Dictionary = {}     # what MapBuilder built, by map id
var clock: SimClock
## Navigation per size: size key (e.g. "r045") -> {"radius", "map" (RID), "region", "links": {link_id: NavigationLink3D}}
var nav_sizes: Dictionary = {}
var avatars: Dictionary = {}      # avatar_id -> Avatar
## Senses (G2a): observations are sampled sample_hz times per second; tick_id stays the 60 Hz
## physics tick (D-33). The seed drives anonymous track ids.
var sample_hz := 10
var seed_value := 1
var senses: ObserverFilter
var comms: CommsRouter
var actions: ActionGate
var journal: Journal
## One avoidance map shared by every avatar, whatever navigation map its size uses (D-42).
var avoidance_map: RID
var _avatar_root: Node3D
var _nav_ready := false
var _event_counter := 0
var _spoken: Array = []           # speech events not yet delivered to listeners
var _zones_by_size: Array = []    # zone dictionaries, smallest area first


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
	avoidance_map = NavigationServer3D.map_create()
	NavigationServer3D.map_set_up(avoidance_map, Vector3.UP)
	NavigationServer3D.map_set_active(avoidance_map, true)
	_zones_by_size = map_data["zones"].duplicate()
	_zones_by_size.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return _area(a) < _area(b))
	senses = ObserverFilter.new()
	senses.setup(self, seed_value)
	add_child(senses)
	comms = CommsRouter.new()
	add_child(comms)
	comms.setup(self)
	actions = ActionGate.new()
	add_child(actions)
	actions.setup(self)
	return true


static func _area(zone: Dictionary) -> float:
	var a: Dictionary = zone["area"]
	return (float(a["x_max"]) - float(a["x_min"])) * (float(a["z_max"]) - float(a["z_min"]))


## Start a recorded run: set the seed and sampling rate, open the journal (if a path is given)
## and write RUN_STARTED with every avatar's pose. Call after spawning the avatars.
func start_run(run_seed: int, journal_path := "", run_sample_hz := 10) -> bool:
	if 60 % run_sample_hz != 0:
		push_error("RangeWorld: sample_hz %d must divide 60 (D-33)" % run_sample_hz)
		return false
	seed_value = run_seed
	sample_hz = run_sample_hz
	senses.setup(self, run_seed)
	if journal_path != "":
		journal = Journal.new()
		if not journal.open(journal_path):
			journal = null
			return false
	var poses := []
	for a in avatar_list():
		poses.append({"avatar_id": a.avatar_id, "x": snappedf(a.global_position.x, 0.0001),
			"z": snappedf(a.global_position.z, 0.0001), "yaw_rad": snappedf(wrapf(a.rotation.y, -PI, PI), 0.0001)})
	journal_write("RUN_STARTED", null, {"seed": run_seed, "map_id": String(map_data["map_id"]),
		"tick_hz": SimClock.TICK_HZ, "sample_hz": sample_hz, "avatars": poses})
	return true


## Write RUN_ENDED and close the journal. Returns its SHA-256 (empty if there was none).
func end_run() -> String:
	if journal == null:
		return ""
	journal_write("RUN_ENDED", null, {"ticks_run": clock.tick})
	var digest := journal.close()
	journal = null
	return digest


func journal_write(kind: String, actor_id, payload: Dictionary) -> void:
	if journal != null:
		journal.write(kind, clock.tick, actor_id, payload)


func sample_period_ticks() -> int:
	return maxi(1, roundi(float(SimClock.TICK_HZ) / sample_hz))


func next_event_id() -> String:
	_event_counter += 1
	return "evt_%06d" % _event_counter


## The environment values (light, visual range factor, noise floor) of the most specific zone
## containing the point; the map file declares them (ART_DIRECTION §5).
func environment_at(p: Vector3) -> Dictionary:
	for zone in _zones_by_size:
		var a: Dictionary = zone["area"]
		if p.x >= float(a["x_min"]) and p.x <= float(a["x_max"]) and p.z >= float(a["z_min"]) and p.z <= float(a["z_max"]):
			return zone["environment"]
	return {"light_level": 1.0, "visual_range_factor": 1.0, "noise_floor_db": 45.0}


## Sight range is cut by haze or darkness at either end (the lower factor applies).
func visual_range_factor(a: Vector3, b: Vector3) -> float:
	return minf(float(environment_at(a)["visual_range_factor"]), float(environment_at(b)["visual_range_factor"]))


## Called by Avatar.say(): records LOCAL speech for listeners to hear at the next sample.
func emit_speech(speaker: Avatar, text: String, addressee_id, level_db: float) -> String:
	var event_id := next_event_id()
	var duration_ms := maxi(1000, text.length() * 70)
	_spoken.append({"event_id": event_id, "speaker_id": speaker.avatar_id, "text": text,
		"addressee_id": addressee_id, "level_db": level_db, "tick": clock.tick})
	journal_write("SPEECH_EMITTED", speaker.avatar_id, {"avatar_id": speaker.avatar_id, "event_id": event_id,
		"channel": "LOCAL", "text": text, "addressee_id": addressee_id, "level_db": level_db, "duration_ms": duration_ms})
	return event_id


func spoken_since(_tick: int) -> Array:
	return _spoken


func clear_spoken_before(tick: int) -> void:
	_spoken = _spoken.filter(func(s: Dictionary) -> bool: return int(s["tick"]) > tick)


func _exit_tree() -> void:
	end_run()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		if avoidance_map.is_valid():
			NavigationServer3D.free_rid(avoidance_map)
		for size in nav_sizes.values():
			if size["map"].is_valid():
				NavigationServer3D.free_rid(size["map"])


## Navigation is ready once every map can answer queries: the baked polygons and every link
## are in the map's current iteration. Map updates are asynchronous, so this takes a few ticks.
func _physics_process(_delta: float) -> void:
	if _nav_ready or nav_sizes.is_empty():
		return
	var probe := Vector3(0.5, 0.0, 0.5) * Vector3(registry["bounds"].x, 0.0, registry["bounds"].y)
	for size in nav_sizes.values():
		var map: RID = size["map"]
		if NavigationServer3D.map_get_iteration_id(map) == 0:
			return
		if NavigationServer3D.map_get_links(map).size() != size["links"].size():
			return
		if NavigationServer3D.map_get_closest_point_owner(map, probe) != (size["region"] as NavigationRegion3D).get_rid():
			return
	_nav_ready = true
	navigation_ready.emit()


func is_navigation_ready() -> bool:
	return _nav_ready


func wait_navigation_ready() -> void:
	if not _nav_ready:
		await navigation_ready


static func size_key(radius: float) -> String:
	return "r%03d" % int(round(radius * 100))


## The navigation map for a body's size. Bodies must have been loaded with build().
func nav_map_for(body: Dictionary) -> RID:
	var key := size_key(Bodies.nav_radius(body))
	if not nav_sizes.has(key):
		push_error("RangeWorld: no navigation for size %s (body '%s' was not loaded)" % [key, body.get("body_id")])
		return RID()
	return nav_sizes[key]["map"]


## For each body size: bake the floor and platform tops into one region, and add the ramp and
## stairs as links on their capability layers (D-31). The ramp and stair footprints are kept
## out of the bake, so the only way onto a platform is a link the body is allowed to use.
func _build_navigation() -> void:
	var heights := {}   # size key -> tallest body of that size
	var radii := {}
	for body in bodies.values():
		var r := Bodies.nav_radius(body)
		var key := size_key(r)
		radii[key] = r
		heights[key] = maxf(float(heights.get(key, 0.0)), float(body["dimensions"]["height_m"]))
	if radii.is_empty():
		radii[size_key(0.25)] = 0.25
		heights[size_key(0.25)] = 1.7

	# The source geometry is the same for every size: parse it once.
	var template := _navmesh(0.25, 1.7)
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(template, source, registry["nav_source"])
	for link in registry["links"].values():
		var outline := PackedVector3Array()
		for p in link["footprint"]:
			outline.append(Vector3(p.x, 0.0, p.y))
		source.add_projected_obstruction(outline, -0.1, NAV_OBSTRUCTION_HEIGHT_M, false)

	var keys := radii.keys()
	keys.sort()
	for key in keys:
		var nm := _navmesh(float(radii[key]), float(heights[key]))
		NavigationServer3D.bake_from_source_geometry_data(nm, source)
		var map := NavigationServer3D.map_create()
		NavigationServer3D.map_set_up(map, Vector3.UP)
		NavigationServer3D.map_set_cell_size(map, NAV_CELL_SIZE)
		NavigationServer3D.map_set_cell_height(map, NAV_CELL_HEIGHT)
		NavigationServer3D.map_set_active(map, true)
		var group := Node3D.new()
		group.name = "Nav_" + key
		add_child(group)
		var region := NavigationRegion3D.new()
		region.name = "NavRegion"
		region.navigation_layers = Layers.NAV_FLOOR
		region.navigation_mesh = nm
		group.add_child(region)
		region.set_navigation_map(map)
		var links := {}
		for link_id in registry["links"]:
			var info: Dictionary = registry["links"][link_id]
			var link := NavigationLink3D.new()
			link.name = link_id
			link.bidirectional = true
			link.start_position = info["from"]
			link.end_position = info["to"]
			link.navigation_layers = int(Layers.NAV_CAPABILITY[info["required_capability"]])
			group.add_child(link)
			link.set_navigation_map(map)
			links[link_id] = link
		nav_sizes[key] = {"radius": float(radii[key]), "map": map, "region": region, "links": links}


func _navmesh(radius: float, agent_height: float) -> NavigationMesh:
	var nm := NavigationMesh.new()
	nm.cell_size = NAV_CELL_SIZE
	nm.cell_height = NAV_CELL_HEIGHT
	nm.agent_radius = radius
	nm.agent_height = ceilf(agent_height / NAV_CELL_HEIGHT - 1e-6) * NAV_CELL_HEIGHT   # whole cells
	nm.agent_max_climb = NAV_MAX_CLIMB_M
	nm.agent_max_slope = NAV_MAX_SLOPE_DEG
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = Layers.WORLD
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_ROOT_NODE_CHILDREN
	return nm


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
	avatar.attach_navigation(nav_map_for(bodies[body_id]))
	avatar.attach_world(self)
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


## Plan a path for a body without moving anyone: on the navigation map for its size, using
## only the links its capabilities allow. Returns {"path": PackedVector3Array, "links": [link ids used]}.
func query_path(from: Vector3, to: Vector3, body: Dictionary) -> Dictionary:
	var params := NavigationPathQueryParameters3D.new()
	params.map = nav_map_for(body)
	params.start_position = from
	params.target_position = to
	params.navigation_layers = Layers.nav_mask_for(body)
	params.metadata_flags = NavigationPathQueryParameters3D.PATH_METADATA_INCLUDE_OWNERS
	var result := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(params, result)
	var links: Array[String] = []
	for owner_id in result.path_owner_ids:
		var path_owner := instance_from_id(owner_id)
		if path_owner is NavigationLink3D and not links.has(String(path_owner.name)):
			links.append(String(path_owner.name))
	return {"path": result.path, "links": links}
