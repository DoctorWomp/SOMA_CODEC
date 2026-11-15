extends Node
## G1 headless tests. Run through tools/godot_check.py (part of tools/check.py):
##
##   godot --headless --path godot_app --fixed-fps 60 res://tests/test_main.tscn
##
## Add "-- --filter=<text>" to run only tests whose name contains <text>.
## Each test returns "" on success or a message saying what went wrong. The runner prints
## one PASS/FAIL line per test and a final summary line that tools/godot_check.py reads.

const MAP_ID := "sandbox_flats"
const TESTS := [
	"test_project_settings",
	"test_fixed_tick",
	"test_map_built_from_data",
	"test_body_dimensions_and_navigation_radius",
	"test_robot_models",
	"test_gesture_permissions",
	"test_navigation_per_body_size",
	"test_visitors_reach_goals",
	"test_wall_collision",
	"test_avatar_collision",
	"test_sb05_path_choice",
	"test_no_capability_no_platform_path",
	"test_sb05_wheeled_takes_ramp",
	"test_sb05_stair_climbers",
	"test_robot_blocked_by_steps",
	"test_speed_and_turn_limits",
	"test_camera",
	"test_lineup_scene",
	"test_demo_smoke",
	"test_partly_seen_behind_partition_edge",
	"test_low_divider_and_sensor_height",
	"test_crowd_occludes",
	"test_lost_track_then_dropped",
	"test_gesture_perception",
	"test_gesture_refused_is_never_seen",
	"test_speech_audibility",
	"test_walls_range_and_noise_on_speech",
	"test_sampling_and_packets",
	"test_journal_is_deterministic",
	"test_avoidance_crossing",
	"test_router_gesture_t13",
	"test_router_local_t14",
	"test_group_messages_t15",
	"test_pa_authorization_t16",
	"test_action_gate_reason_codes",
	"test_link_end_to_end",
	"test_link_wrong_token",
	"test_link_slow_sidecar",
	"test_link_no_sidecar",
]

## Where tests write journals and packets for tools/godot_check.py to validate in Python.
var artifacts_dir := "user://test_artifacts"

const ROBOT_BODIES := ["legged_humanoid", "wheeled_humanoid", "quadruped", "quadruped_arm"]
const ALL_BODIES := ["legged_humanoid", "wheeled_humanoid", "quadruped", "quadruped_arm", "human_walker"]

## Same numbers as tests/test_bodies.py (D-37): turning radius and navigation radius.
const EXPECTED_RADII := {
	"legged_humanoid": [0.28, 0.30],
	"wheeled_humanoid": [0.4478, 0.45],
	"quadruped": [0.6042, 0.65],
	"quadruped_arm": [0.6042, 0.65],
	"human_walker": [0.25, 0.25],
}

## Every gesture in contracts/common.schema.json, and the ones each body may perform (D-36).
const ALL_GESTURES := ["WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "NOD", "SHAKE_HEAD",
	"OPEN_PALM", "BOW", "HEAD_TILT", "SIT_IN_PLACE", "HAND_OVER"]
const ALLOWED_GESTURES := {
	"legged_humanoid": ["WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "NOD", "SHAKE_HEAD",
		"OPEN_PALM", "BOW", "HEAD_TILT", "HAND_OVER"],
	"wheeled_humanoid": ["WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "NOD", "SHAKE_HEAD",
		"OPEN_PALM", "BOW", "HEAD_TILT", "HAND_OVER"],
	"quadruped": ["HEAD_TILT", "SIT_IN_PLACE"],
	"quadruped_arm": ["HEAD_TILT", "SIT_IN_PLACE", "POINT", "HAND_OVER"],
}

## SB-05 setup: start beside the stairs, goal on the platform, so the stairs are by far
## the shorter way and only capability can explain the robot taking the ramp.
const SB05_START := Vector3(18.5, 0.0, 2.5)
const SB05_GOAL := Vector3(25.0, 0.6, 2.5)

var _node: Node = null   # what the current test built; freed after each test


func _ready() -> void:
	Engine.max_fps = 0
	var filter := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--filter="):
			filter = arg.trim_prefix("--filter=")
		elif arg.begins_with("--artifacts-dir="):
			artifacts_dir = arg.trim_prefix("--artifacts-dir=")
	DirAccess.make_dir_recursive_absolute(artifacts_dir)
	await get_tree().process_frame
	var passed := 0
	var failed := 0
	for test_name in TESTS:
		if filter != "" and not test_name.contains(filter):
			continue
		var start := Time.get_ticks_msec()
		var err: String = await call(test_name)
		var ms := Time.get_ticks_msec() - start
		if err == "":
			passed += 1
			print("PASS %s (%d ms)" % [test_name, ms])
		else:
			failed += 1
			print("FAIL %s: %s" % [test_name, err])
		await _cleanup()
	print("G1 TESTS DONE passed=%d failed=%d" % [passed, failed])
	get_tree().quit(1 if failed > 0 else 0)


# ---------- helpers ----------

func _cleanup() -> void:
	Input.action_release("cam_forward")
	if _node != null:
		_node.queue_free()
		_node = null
	for i in 3:
		await get_tree().physics_frame


func _world(body_ids := ["wheeled_humanoid", "human_walker"]) -> RangeWorld:
	var w := RangeWorld.new()
	add_child(w)
	_node = w
	if not w.build(MAP_ID, body_ids):
		return null
	await w.wait_navigation_ready()
	return w


## Run up to `max_ticks`, recording each avatar's position and yaw every tick.
## Stops early once `done` returns true. Returns {avatar_id: {"pos": [...], "yaw": [...]}}.
func _run(avatars: Array, max_ticks: int, done := Callable()) -> Dictionary:
	var traces := {}
	for a in avatars:
		traces[a.avatar_id] = {"pos": [a.global_position], "yaw": [a.rotation.y]}
	for i in max_ticks:
		await get_tree().physics_frame
		for a in avatars:
			traces[a.avatar_id]["pos"].append(a.global_position)
			traces[a.avatar_id]["yaw"].append(a.rotation.y)
		if done.is_valid() and done.call():
			break
	await get_tree().physics_frame
	for a in avatars:
		traces[a.avatar_id]["pos"].append(a.global_position)
		traces[a.avatar_id]["yaw"].append(a.rotation.y)
	return traces


func _all_idle(avatars: Array) -> Callable:
	return func() -> bool:
		for a in avatars:
			if a.mode != Avatar.Mode.IDLE:
				return false
		return true


func _v(p: Vector3) -> String:
	return "(%.2f, %.2f, %.2f)" % [p.x, p.y, p.z]


func _grow(poly: PackedVector2Array, margin: float) -> PackedVector2Array:
	var out := Geometry2D.offset_polygon(poly, margin)
	return out[0] if not out.is_empty() else poly


func _in_poly(p: Vector3, poly: PackedVector2Array) -> bool:
	return Geometry2D.is_point_in_polygon(Vector2(p.x, p.z), poly)


func _ray_down(w: RangeWorld, x: float, z: float, mask: int) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 5.0, z), Vector3(x, -1.0, z), mask)
	var hit := w.get_world_3d().direct_space_state.intersect_ray(q)
	return hit["position"].y if not hit.is_empty() else -INF


func _on_platform(w: RangeWorld, p: Vector3) -> bool:
	return absf(p.y - 0.6) < 0.08 and w.ground_height(p.x, p.z) > 0.5


# ---------- tests ----------

func test_project_settings() -> String:
	if Engine.physics_ticks_per_second != 60:
		return "physics ticks per second is %d, expected 60" % Engine.physics_ticks_per_second
	var engine_name := String(ProjectSettings.get_setting("physics/3d/physics_engine"))
	if engine_name != "Jolt Physics":
		return "3D physics engine is '%s', expected 'Jolt Physics' (D-33)" % engine_name
	if int(ProjectSettings.get_setting("application/run/max_fps")) != 60:
		return "frame rate must be capped at 60 (ART_DIRECTION §3)"
	# D-38: every GDScript warning that is on by default is an error, so none can slip in.
	for warning in ["integer_division", "shadowed_variable", "shadowed_variable_base_class",
			"shadowed_global_identifier", "unused_variable", "unused_parameter", "narrowing_conversion",
			"unreachable_code", "standalone_expression", "unsafe_void_return"]:
		var level := int(ProjectSettings.get_setting("debug/gdscript/warnings/" + warning))
		if level != 2:
			return "GDScript warning '%s' is at level %d; it must be an error (2), see D-38" % [warning, level]
	for action in ["cam_forward", "cam_back", "cam_left", "cam_right", "cam_up", "cam_down", "cam_fast",
			"cam_toggle_mode", "select_prev", "select_next", "sim_pause", "demo_restart", "hud_toggle", "sense_view"]:
		if not InputMap.has_action(action) or InputMap.action_get_events(action).is_empty():
			return "input action '%s' is missing from project.godot" % action
	return ""


func test_fixed_tick() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var engine_start := Engine.get_physics_frames()
	var tick_start := w.clock.tick
	for i in 120:
		await get_tree().physics_frame
		if not is_equal_approx(get_physics_process_delta_time(), 1.0 / 60.0):
			return "physics step is %f s, expected 1/60" % get_physics_process_delta_time()
	await get_tree().process_frame
	var engine_steps := Engine.get_physics_frames() - engine_start
	var ticks := w.clock.tick - tick_start
	if ticks != engine_steps:
		return "clock counted %d ticks over %d physics steps" % [ticks, engine_steps]
	if ticks < 120:
		return "only %d ticks after 120 physics frames" % ticks
	return ""


func test_map_built_from_data() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var m := w.map_data
	var reg := w.registry
	var counts := {
		"walls": [reg["walls"].size(), m["walls"].size()],
		"platforms": [reg["platforms"].size(), m["platforms"].size()],
		"links": [reg["links"].size(), m["nav_links"].size()],
		"props": [reg["props"].size(), m["props"].size()],
		"zones": [reg["zones"].size(), m["zones"].size()],
		"spawns": [reg["spawns"].size(), m["spawn_points"].size()],
	}
	for key in counts:
		if counts[key][0] != counts[key][1]:
			return "%s: built %d, map file has %d" % [key, counts[key][0], counts[key][1]]
	# Exact content of Sandbox Flats (RANGE_V0_SCOPE §2.1).
	var partitions := 0
	for wall in reg["walls"].values():
		if wall.get_meta("movable"):
			partitions += 1
	if reg["walls"].size() != 7 or partitions != 3:
		return "expected 4 outer walls + 2 partitions + 1 low divider, got %d walls, %d movable" % [reg["walls"].size(), partitions]
	if not is_equal_approx(float(m["walls"][6]["height_m"]), 1.1) or reg["walls"]["divider_low"].get_meta("blocks_sound"):
		return "divider_low should be 1.1 m high and let sound pass"
	if not reg["walls"]["wall_west"].get_meta("acoustically_reflective"):
		return "wall_west is not marked acoustically reflective"
	if w.find_child("ReflectiveWallMarker", true, false) == null or w.find_child("ReflectiveWallLabel", true, false) == null:
		return "reflective wall has no visible marker and label"
	var types := {}
	for prop in reg["props"].values():
		types[prop.get_meta("prop_type")] = types.get(prop.get_meta("prop_type"), 0) + 1
	if types.get("PA_SPEAKER", 0) != 1 or types.get("CHAIR", 0) != 3:
		return "expected 1 PA speaker and 3 chairs, got %s" % types
	for prop in m["props"]:
		var node: Node3D = reg["props"][prop["prop_id"]]
		var want := Vector2(float(prop["position"]["x"]), float(prop["position"]["z"]))
		if Vector2(node.global_position.x, node.global_position.z).distance_to(want) > 1e-4:
			return "%s is at %s, map says %s" % [prop["prop_id"], _v(node.global_position), want]
	var kinds := []
	for link in reg["links"].values():
		kinds.append(link["kind"])
	kinds.sort()
	if kinds != ["RAMP", "STAIRS"]:
		return "expected one ramp and one stair, got %s" % [kinds]
	if reg["links"]["platform_stairs"]["steps"] < 3:
		return "stairs have too few steps"
	if not reg["zones"]["chair_corner"].get_meta("environment").has("light_level"):
		return "zone environment values are missing"
	# Surfaces where the map says they are.
	await get_tree().physics_frame
	await get_tree().physics_frame
	var probes := [
		["floor", 5.0, 5.0, Layers.WORLD, 0.0],
		["platform top", 26.0, 4.0, Layers.WORLD, 0.6],
		["ramp middle", 18.4, 7.0, Layers.WORLD, 0.3],
		["stairs top step", 21.8, 2.0, Layers.STAIRS_STEPS, 0.6],
		["stairs walk surface middle", 21.25, 2.0, Layers.STAIRS_WALK_SURFACE, 0.3],
	]
	for probe in probes:
		var y := _ray_down(w, probe[1], probe[2], probe[3])
		if absf(y - probe[4]) > 0.02:
			return "%s at (%.1f, %.1f): surface height %.3f, expected %.2f" % [probe[0], probe[1], probe[2], y, probe[4]]
	return ""


func test_body_dimensions_and_navigation_radius() -> String:
	var w := await _world(ALL_BODIES)
	if w == null:
		return "world failed to build"
	var x := 4.0
	for body_id in ALL_BODIES:
		var body: Dictionary = w.bodies[body_id]
		var expected: Array = EXPECTED_RADII[body_id]
		if absf(Bodies.turning_radius(body) - float(expected[0])) > 0.001:
			return "%s turning radius %.4f, expected %.4f" % [body_id, Bodies.turning_radius(body), expected[0]]
		if not is_equal_approx(Bodies.nav_radius(body), float(expected[1])):
			return "%s navigation radius %.3f, expected %.2f" % [body_id, Bodies.nav_radius(body), expected[1]]
		var a := w.spawn_avatar(body_id, body_id, Vector3(x, 0, 16.5), 0.0)
		x += 2.5
		var collider: Dictionary = body["dimensions"]["collider"]
		var shape: Shape3D = (a.get_node("Collider") as CollisionShape3D).shape
		var height := float(body["dimensions"]["height_m"])
		match String(collider["shape"]):
			"BOX":
				var want := Vector3(float(collider["width_m"]), height, float(collider["length_m"]))
				var legged := Layers.has_capability(body, "can_use_stairs")
				if legged != (shape is ConvexPolygonShape3D):
					return "%s: box bodies that use stairs get a bevelled collider, others a flat box" % body_id
				var size := (shape as BoxShape3D).size if shape is BoxShape3D else _points_size((shape as ConvexPolygonShape3D).points)
				if not size.is_equal_approx(want):
					return "%s box collider is %s, config says %s" % [body_id, size, want]
			"CAPSULE":
				var capsule := shape as CapsuleShape3D
				if not is_equal_approx(capsule.radius, float(collider["width_m"]) / 2) or not is_equal_approx(capsule.height, height):
					return "%s capsule collider does not match its config" % body_id
			_:
				return "%s has an unexpected collider shape %s" % [body_id, collider["shape"]]
		var mount := a.get_node("SensorMount") as Marker3D
		if not is_equal_approx(mount.position.y, float(body["sensors"]["mount_height_m"])):
			return "%s sensor mount at %.2f m, config says %s" % [body_id, mount.position.y, body["sensors"]["mount_height_m"]]
		if a.nav_agent.navigation_layers != Layers.nav_mask_for(body):
			return "%s navigation layers do not follow its capabilities" % body_id
	# Low sensors: the quadruped sees under a 2 m partition's top edge only if it is shorter.
	if float(w.bodies["quadruped"]["sensors"]["mount_height_m"]) >= 1.0:
		return "quadruped sensors should be mounted low"
	return ""


func _points_size(points: PackedVector3Array) -> Vector3:
	var lo := points[0]
	var hi := points[0]
	for q in points:
		lo = Vector3(minf(lo.x, q.x), minf(lo.y, q.y), minf(lo.z, q.z))
		hi = Vector3(maxf(hi.x, q.x), maxf(hi.y, q.y), maxf(hi.z, q.z))
	return hi - lo


## Combined bounds of an avatar's model meshes, in the avatar's own space.
func _model_bounds(a: Avatar) -> AABB:
	var bounds := AABB()
	var first := true
	for mi in a.model.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var b: AABB = (a.global_transform.affine_inverse() * m.global_transform) * m.get_aabb()
		bounds = b if first else bounds.merge(b)
		first = false
	return bounds


func test_robot_models() -> String:
	var w := await _world(ALL_BODIES)
	if w == null:
		return "world failed to build"
	var parts := {
		"legged_humanoid": ["Head", "Visor", "EarPodL", "EarPodR", "Torso", "ShoulderL", "ElbowR", "WristL",
			"HipL", "KneeR", "AnkleL", "BadgeFront", "ForearmBand1"],
		"wheeled_humanoid": ["Head", "Visor", "EarPodL", "Torso", "ShoulderR", "WristR", "WheelFL", "WheelFR",
			"WheelBL", "WheelBR", "ColumnLower", "ColumnUpper", "BadgeBack", "ForearmBand2"],
		"quadruped": ["SensorHead", "Visor", "LensC", "VisorLight", "DorsalRail", "LegFL", "LegFR", "LegBL",
			"LegBR", "BadgeL", "BadgeR", "TrimL3"],
		"quadruped_arm": ["SensorHead", "Visor", "DorsalRail", "Arm", "ArmShoulder", "ArmElbow", "Gripper"],
	}
	var no_parts := {
		"legged_humanoid": ["WheelFL", "Arm"],
		"wheeled_humanoid": ["HipL", "KneeL"],
		"quadruped": ["Arm", "Gripper", "Head"],
		"quadruped_arm": ["Head"],
	}
	var appearance := {"badge": "7", "trim": "robot_trim_teal", "bands": 3}
	var x := 4.0
	for body_id in ROBOT_BODIES:
		var a := w.spawn_avatar(body_id, body_id, Vector3(x, 0, 16.5), 0.0, appearance)
		x += 2.5
		for part in parts[body_id]:
			if a.model.find_child(part, true, false) == null:
				return "%s model has no part '%s'" % [body_id, part]
		for part in no_parts[body_id]:
			if a.model.find_child(part, true, false) != null:
				return "%s model should not have a part '%s'" % [body_id, part]
		var bounds := _model_bounds(a)
		if bounds.position.y < -0.01 or absf(bounds.end.y - a.height) > 0.04:
			return "%s model spans y %.3f..%.3f, config height %.2f" % [body_id, bounds.position.y, bounds.end.y, a.height]
		# The model fits its collider footprint (small tolerance for shoulder caps).
		var half_len := maxf(-bounds.position.z, bounds.end.z)
		var half_wid := maxf(-bounds.position.x, bounds.end.x)
		var round_body := String(a.body["dimensions"]["collider"]["shape"]) != "BOX"
		var limit_len := a.radius if round_body else a.footprint.x / 2
		var limit_wid := a.radius if round_body else a.footprint.y / 2
		if half_len > limit_len + 0.03 or half_wid > limit_wid + 0.03:
			return "%s model reaches %.3f m forward/back and %.3f m sideways, beyond its collider (%.3f x %.3f)" % [
				body_id, half_len, half_wid, limit_len, limit_wid]
		# The visor or sensor head faces forward (-z) at about the sensor mount height.
		var visor: Node3D = a.model.find_child("Visor", true, false)
		var visor_pos := a.global_transform.affine_inverse() * visor.global_position
		if visor_pos.z > -0.05:
			return "%s visor is not on the front (-z)" % body_id
		if absf(visor_pos.y - a.sensor_mount_height) > 0.05:
			return "%s visor at %.2f m, sensor mount at %.2f m" % [body_id, visor_pos.y, a.sensor_mount_height]
		var badge: Label3D = a.model.find_child("BadgeFront", true, false)
		if badge == null:
			badge = a.model.find_child("BadgeL", true, false)
		if badge.text != "7":
			return "%s badge shows '%s', expected the number from its appearance" % [body_id, badge.text]
	return ""


func test_gesture_permissions() -> String:
	var w := await _world(ROBOT_BODIES)
	if w == null:
		return "world failed to build"
	var x := 4.0
	for body_id in ROBOT_BODIES:
		var a := w.spawn_avatar(body_id, body_id, Vector3(x, 0, 16.5), 0.0)
		x += 2.5
		var allowed: Array = ALLOWED_GESTURES[body_id]
		for gesture in ALL_GESTURES:
			var accepted := a.perform_gesture(gesture)
			if accepted != allowed.has(gesture):
				return "%s %s %s" % [body_id, "performed" if accepted else "refused", gesture]
		if a.refused_gestures.size() != ALL_GESTURES.size() - allowed.size():
			return "%s did not record its refused gestures" % body_id
	# The quadruped has no face display; the humanoids do.
	if w.avatars["quadruped"].supports_channel("FACE") or not w.avatars["legged_humanoid"].supports_channel("FACE"):
		return "FACE channel permissions are wrong"
	return ""


## D-37: one navigation map per body size. A pocket of floor between the stairs and the north
## wall (about 1.15 m wide) is open to a walker but too narrow for a quadruped turning on the spot.
func test_navigation_per_body_size() -> String:
	var w := await _world(ALL_BODIES)
	if w == null:
		return "world failed to build"
	var keys := w.nav_sizes.keys()
	keys.sort()
	if keys != ["r025", "r030", "r045", "r065"]:
		return "navigation sizes are %s, expected r025, r030, r045 and r065" % [keys]
	var pocket := Vector3(21.3, 0.0, 0.6)
	var start := Vector3(17.0, 0.0, 4.0)
	var walker_plan := w.query_path(start, pocket, w.bodies["human_walker"])
	var walker_path: PackedVector3Array = walker_plan["path"]
	if walker_path.is_empty() or Vector2(walker_path[-1].x - pocket.x, walker_path[-1].z - pocket.z).length() > 0.15:
		return "a walker cannot reach the pocket by the stairs; one mesh for the largest body would cause this"
	var quad_plan := w.query_path(start, pocket, w.bodies["quadruped"])
	var quad_path: PackedVector3Array = quad_plan["path"]
	if not quad_path.is_empty() and Vector2(quad_path[-1].x - pocket.x, quad_path[-1].z - pocket.z).length() < 0.4:
		return "the quadruped got a path into a pocket narrower than its turning circle"
	# Each body's avatar uses the map of its own size.
	var q := w.spawn_avatar("q", "quadruped", Vector3(10, 0, 16), 0.0)
	var h := w.spawn_avatar("h", "human_walker", Vector3(13, 0, 16), 0.0)
	if q.nav_agent.get_navigation_map() != w.nav_sizes["r065"]["map"] or h.nav_agent.get_navigation_map() != w.nav_sizes["r025"]["map"]:
		return "avatars are not on the navigation map of their size"
	return ""


func test_visitors_reach_goals() -> String:
	var w := await _world(["human_walker"])
	if w == null:
		return "world failed to build"
	# a: around partition_a; b: long diagonal; c: to the chair corner.
	var plan := [
		["a", Vector3(8.0, 0, 9.0), Vector3(12.0, 0, 9.0)],
		["b", Vector3(3.0, 0, 3.0), Vector3(16.0, 0, 18.0)],
		["c", Vector3(24.0, 0, 17.5), Vector3(5.0, 0, 14.5)],
	]
	var avatars := []
	for p in plan:
		var a := w.spawn_avatar(p[0], "human_walker", p[1], 0.0)
		a.navigate_to(w.ground_point(p[2].x, p[2].z))
		avatars.append(a)
	var traces := await _run(avatars, 60 * 40, _all_idle(avatars))
	for i in avatars.size():
		var a: Avatar = avatars[i]
		if a.ever_stuck:
			return "%s got stuck" % a.avatar_id
		if not a.last_goal_reached or a.horizontal_distance_to(a.goal) > 0.4:
			return "%s ended at %s, goal %s" % [a.avatar_id, _v(a.global_position), _v(a.goal)]
	for p in traces["a"]["pos"]:
		if absf(p.x - 10.0) < 0.3 and p.z > 6.0 and p.z < 12.0:
			return "avatar a went through partition_a at %s" % _v(p)
	return ""


func test_wall_collision() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	# partition_a runs along x = 10 (z 6..12), 0.2 m thick: its west face is at x = 9.9.
	var walker := w.spawn_avatar("walker", "human_walker", Vector3(8.6, 0, 9.0), -PI / 2)
	# partition_b runs along z = 13 (x 17..21): its north face is at z = 12.9.
	var robot := w.spawn_avatar("robot", "wheeled_humanoid", Vector3(19.0, 0, 11.3), PI)
	walker.drive(Vector3(1.4, 0, 0))
	robot.drive(Vector3(0, 0, 1.0))
	var traces := await _run([walker, robot], 60 * 4)
	var max_x := -INF
	for p in traces["walker"]["pos"]:
		max_x = maxf(max_x, p.x)
	if max_x > 9.9 - 0.25 + 0.03:
		return "walker reached x = %.3f, inside partition_a (face at 9.9, radius 0.25)" % max_x
	if max_x < 9.9 - 0.25 - 0.1:
		return "walker stopped at x = %.3f, before reaching the partition" % max_x
	var max_z := -INF
	for p in traces["robot"]["pos"]:
		max_z = maxf(max_z, p.z)
	if max_z > 12.9 - 0.35 + 0.03:
		return "robot reached z = %.3f, inside partition_b (face at 12.9, radius 0.35)" % max_z
	if max_z < 12.9 - 0.35 - 0.1:
		return "robot stopped at z = %.3f, before reaching the partition" % max_z
	return ""


func test_avatar_collision() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var a := w.spawn_avatar("walker_a", "human_walker", Vector3(4.0, 0, 4.0), -PI / 2)
	var b := w.spawn_avatar("walker_b", "human_walker", Vector3(8.0, 0, 4.0), PI / 2)
	var r := w.spawn_avatar("robot", "wheeled_humanoid", Vector3(4.0, 0, 8.0), -PI / 2)
	var c := w.spawn_avatar("walker_c", "human_walker", Vector3(8.0, 0, 8.0), PI / 2)
	a.drive(Vector3(1.4, 0, 0))
	b.drive(Vector3(-1.4, 0, 0))
	r.drive(Vector3(1.0, 0, 0))
	c.drive(Vector3(-1.4, 0, 0))
	var traces := await _run([a, b, r, c], 60 * 4)
	# [avatar, avatar, sum of radii, fastest of the two in m/s]
	var pairs := [["walker_a", "walker_b", 0.5, 1.4], ["robot", "walker_c", 0.6, 1.4]]
	for pair in pairs:
		var pa: Array = traces[pair[0]]["pos"]
		var pb: Array = traces[pair[1]]["pos"]
		var need := float(pair[2])
		var closest := INF
		for i in pa.size():
			closest = minf(closest, Vector2(pa[i].x - pb[i].x, pa[i].z - pb[i].z).length())
		var last := pa.size() - 1
		var final_gap := Vector2(pa[last].x - pb[last].x, pa[last].z - pb[last].z).length()
		# Two bodies moving into each other in the same tick each treat the other as standing
		# still, so they may overlap by at most one tick of travel for a moment, and must then
		# be pushed apart and stay apart while still pushing (no sinking in, no passing through).
		var one_tick := float(pair[3]) / 60.0
		if closest < need - one_tick - 0.002:
			return "%s and %s overlapped by %.3f m, more than one tick of travel (%.3f m)" % [
				pair[0], pair[1], need - closest, one_tick]
		if final_gap < need - 0.005:
			return "%s and %s are still overlapping after 4 s of pushing (%.3f m apart, need %.2f)" % [
				pair[0], pair[1], final_gap, need]
		if closest > need + 0.25:
			return "%s and %s never met (closest %.3f m); the test did not exercise contact" % [pair[0], pair[1], closest]
		if pa[last].x > pb[last].x:
			return "%s passed through %s" % [pair[0], pair[1]]
	return ""


func test_sb05_path_choice() -> String:
	var w := await _world(ALL_BODIES)
	if w == null:
		return "world failed to build"
	var expected := {
		"wheeled_humanoid": ["platform_ramp"],
		"legged_humanoid": ["platform_stairs"],
		"quadruped": ["platform_stairs"],
		"quadruped_arm": ["platform_stairs"],
		"human_walker": ["platform_stairs"],
	}
	for body_id in expected:
		var plan := w.query_path(SB05_START, SB05_GOAL, w.bodies[body_id])
		if plan["links"] != expected[body_id]:
			return "%s's path uses %s, expected %s" % [body_id, plan["links"], expected[body_id]]
		var path: PackedVector3Array = plan["path"]
		if path.is_empty() or path[path.size() - 1].distance_to(SB05_GOAL) > 0.3:
			return "%s's path does not reach the platform goal" % body_id
	return ""


func test_no_capability_no_platform_path() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var body: Dictionary = w.bodies["wheeled_humanoid"].duplicate(true)
	body["capabilities"]["can_use_ramp"] = false
	body["capabilities"]["can_use_stairs"] = false
	var plan := w.query_path(SB05_START, SB05_GOAL, body)
	if not plan["links"].is_empty():
		return "a body with no stairs/ramp capability got a path through %s" % [plan["links"]]
	var path: PackedVector3Array = plan["path"]
	if not path.is_empty() and path[path.size() - 1].y > 0.3:
		return "a body with no stairs/ramp capability got a path onto the platform"
	return ""


func test_sb05_wheeled_takes_ramp() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var robot := w.spawn_avatar("robot_wheeled", "wheeled_humanoid", SB05_START, -PI / 2)
	robot.navigate_to(SB05_GOAL)
	var traces := await _run([robot], 60 * 60, _all_idle([robot]))
	if robot.ever_stuck:
		return "the wheeled humanoid got stuck at %s" % _v(robot.global_position)
	if not robot.last_goal_reached or not _on_platform(w, robot.global_position):
		return "the wheeled humanoid did not reach the platform goal; it ended at %s" % _v(robot.global_position)
	if robot.links_used != ["platform_ramp"]:
		return "the wheeled humanoid entered links %s, expected only platform_ramp" % [robot.links_used]
	var stairs := _grow(w.registry["links"]["platform_stairs"]["footprint"], 0.05)
	var ramp: PackedVector2Array = w.registry["links"]["platform_ramp"]["footprint"]
	var on_ramp := 0
	for p in traces["robot_wheeled"]["pos"]:
		if _in_poly(p, stairs):
			return "the wheeled humanoid entered the stairs footprint at %s" % _v(p)
		if _in_poly(p, ramp) and p.y > 0.1 and p.y < 0.5:
			on_ramp += 1
	if on_ramp < 60:
		return "the wheeled humanoid spent only %d ticks partway up the ramp" % on_ramp
	return ""


## SB-05: the legged humanoid, both quadrupeds and a walker may use the stairs, and from beside
## the stairs they do, physically climbing them.
func test_sb05_stair_climbers() -> String:
	var w := await _world(ALL_BODIES)
	if w == null:
		return "world failed to build"
	var stairs: PackedVector2Array = w.registry["links"]["platform_stairs"]["footprint"]
	for body_id in ["legged_humanoid", "quadruped", "quadruped_arm", "human_walker"]:
		var a := w.spawn_avatar(body_id, body_id, SB05_START, -PI / 2)
		a.navigate_to(SB05_GOAL)
		var traces := await _run([a], 60 * 30, _all_idle([a]))
		if a.ever_stuck or not a.last_goal_reached or not _on_platform(w, a.global_position):
			return "%s did not reach the platform by the stairs; ended at %s" % [body_id, _v(a.global_position)]
		if a.links_used != ["platform_stairs"]:
			return "%s entered links %s, expected only platform_stairs" % [body_id, a.links_used]
		var climbing := 0
		for p in traces[body_id]["pos"]:
			if _in_poly(p, stairs) and p.y > 0.1 and p.y < 0.5:
				climbing += 1
		if climbing < 10:
			return "%s was seen partway up the stairs on only %d ticks" % [body_id, climbing]
		w.avatars.erase(body_id)
		a.queue_free()
		await get_tree().physics_frame
	return ""


func test_robot_blocked_by_steps() -> String:
	var w := await _world(["wheeled_humanoid", "quadruped"])
	if w == null:
		return "world failed to build"
	# Drive straight at the bottom step (x = 20.5) without navigation. Two lanes inside the
	# 1.5 m wide stairs (z 1.25..2.75): the wheeled robot at z 1.62, the quadruped at z 2.46.
	var robot := w.spawn_avatar("robot", "wheeled_humanoid", Vector3(19.2, 0, 1.62), -PI / 2)
	var quad := w.spawn_avatar("quad", "quadruped", Vector3(18.9, 0, 2.46), -PI / 2)
	robot.drive(Vector3(1.0, 0, 0))
	quad.drive(Vector3(1.0, 0, 0))
	var traces := await _run([robot, quad], 60 * 5)
	var robot_max_y := -INF
	var robot_max_x := -INF
	for p in traces["robot"]["pos"]:
		robot_max_y = maxf(robot_max_y, p.y)
		robot_max_x = maxf(robot_max_x, p.x)
	var half_length := robot.footprint.x / 2
	if robot_max_y > 0.05:
		return "the wheeled humanoid climbed to y = %.3f on the stairs; it must be stopped by the steps" % robot_max_y
	if robot_max_x > 20.5 - half_length + 0.03:
		return "the wheeled humanoid reached x = %.3f, into the first step at 20.5" % robot_max_x
	if robot_max_x < 20.5 - half_length - 0.1:
		return "the wheeled humanoid stopped at x = %.3f, before reaching the stairs" % robot_max_x
	# Control: the same push takes the quadruped (can_use_stairs) up onto the platform.
	if quad.global_position.y < 0.55:
		return "the quadruped driven the same way did not climb the stairs (y = %.3f)" % quad.global_position.y
	return ""


func test_speed_and_turn_limits() -> String:
	var w := await _world(DemoRoutes.body_ids())
	if w == null:
		return "world failed to build"
	var demo := DemoRoutes.new()
	w.add_child(demo)
	demo.spawn_cast(w)
	demo.start()
	var avatars := w.avatar_list()
	var traces := await _run(avatars, 60 * 25)
	var dt := 1.0 / 60.0
	for a in avatars:
		var pos: Array = traces[a.avatar_id]["pos"]
		var yaw: Array = traces[a.avatar_id]["yaw"]
		var moved := 0.0
		for i in range(1, pos.size()):
			var step := Vector2(pos[i].x - pos[i - 1].x, pos[i].z - pos[i - 1].z).length()
			moved += step
			if step > a.max_speed * dt * 1.02 + 0.001:
				return "%s moved %.4f m in one tick; limit %.4f (max_speed %.2f m/s)" % [
					a.avatar_id, step, a.max_speed * dt, a.max_speed]
			var turn := absf(wrapf(yaw[i] - yaw[i - 1], -PI, PI))
			if turn > a.max_turn_rate * dt + 1e-4:
				return "%s turned %.4f rad in one tick; limit %.4f" % [a.avatar_id, turn, a.max_turn_rate * dt]
		if moved < 3.0:
			return "%s moved only %.2f m; the limits were not exercised" % [a.avatar_id, moved]
	return ""


func test_camera() -> String:
	var w := await _world(["wheeled_humanoid", "human_walker"])
	if w == null:
		return "world failed to build"
	var r := w.spawn_avatar("robot_wheeled", "wheeled_humanoid", Vector3(10, 0, 10), 0.0)
	w.spawn_avatar("visitor_x", "human_walker", Vector3(20, 0, 15), 0.0)
	var rig := CameraRig.new()
	w.add_child(rig)
	rig.set_targets(w.avatar_list())
	if rig.selected_target() != r:
		return "first selected avatar should be robot_wheeled"
	rig.select_next()
	if (rig.selected_target() as Avatar).avatar_id != "visitor_x":
		return "select_next did not move to visitor_x"
	rig.select_next()
	rig.select_prev()
	rig.select_prev()
	if rig.selected_target() != r:
		return "select_prev did not cycle back to robot_wheeled"
	rig.toggle_mode()
	if rig.mode != CameraRig.Mode.ORBIT:
		return "toggle_mode did not switch to orbit"
	r.position = Vector3(12, 0, 6)
	for i in 3:
		await get_tree().process_frame
	var focus := r.global_position + Vector3.UP * CameraRig.ORBIT_FOCUS_HEIGHT
	var cam := rig.camera.global_transform
	if absf(cam.origin.distance_to(focus) - rig.orbit_distance) > 0.01:
		return "orbit camera is %.2f m from the avatar, expected %.2f" % [cam.origin.distance_to(focus), rig.orbit_distance]
	if (-cam.basis.z).dot((focus - cam.origin).normalized()) < 0.999:
		return "orbit camera is not looking at the selected avatar"
	rig.toggle_mode()
	if rig.mode != CameraRig.Mode.FREE:
		return "toggle_mode did not switch back to free"
	var before := rig.camera.global_position
	var forward := -rig.camera.global_transform.basis.z
	Input.action_press("cam_forward")
	for i in 30:
		await get_tree().process_frame
	Input.action_release("cam_forward")
	var moved := (rig.camera.global_position - before).dot(forward)
	if moved < 0.5 * CameraRig.FREE_SPEED * 0.4:
		return "free camera moved %.2f m forward in 0.5 s with W held" % moved
	return ""


func test_lineup_scene() -> String:
	var lineup: Node = load("res://scenes/robot_lineup.tscn").instantiate()
	add_child(lineup)
	_node = lineup
	await get_tree().physics_frame
	var bodies_seen := []
	for a in lineup.world.avatar_list():
		bodies_seen.append(String((a as Avatar).body["body_id"]))
	bodies_seen.sort()
	if bodies_seen != ["human_walker", "legged_humanoid", "quadruped", "quadruped_arm", "wheeled_humanoid"]:
		return "lineup shows %s" % [bodies_seen]
	return ""


func test_demo_smoke() -> String:
	var main: Node = load("res://scenes/main.tscn").instantiate()
	main.journal_path = ""
	add_child(main)
	_node = main
	var started := false
	for i in 120:
		await get_tree().physics_frame
		if main.demo != null and main.demo.started():
			started = true
			break
	if not started:
		return "demo did not start"
	var avatars: Array = main.world.avatar_list()
	if avatars.size() != 6:
		return "expected three robots and three visitors, got %d avatars" % avatars.size()
	var kinds := {}
	for a in avatars:
		kinds[(a as Avatar).kind] = true
	for kind in ["LEGGED_HUMANOID", "WHEELED_HUMANOID", "QUADRUPED", "HUMAN_WALKER"]:
		if not kinds.has(kind):
			return "no %s in the demo" % kind
	await _run(avatars, 60 * 45, func() -> bool: return main.demo.finished)
	if not main.demo.finished:
		return "demo routes did not finish within 45 s"
	for a in avatars:
		if a.ever_stuck:
			return "%s got stuck" % a.avatar_id
		if not a.last_goal_reached:
			return "%s did not reach its last goal" % a.avatar_id
		if not a.contacts.is_empty():
			return "%s touched %s in the demo" % [a.avatar_id, a.contacts]
	# SB-05 in the demo: everyone ends on the platform, the wheeled humanoid by the ramp.
	var expected := {"robot_wheeled": "platform_ramp", "robot_legged": "platform_stairs", "robot_quadruped": "platform_stairs"}
	for robot_id in expected:
		var robot: Avatar = main.world.avatars[robot_id]
		if robot.links_used != [expected[robot_id]]:
			return "%s used links %s in the demo, expected %s" % [robot_id, robot.links_used, expected[robot_id]]
		if not _on_platform(main.world, robot.global_position):
			return "%s did not end on the platform" % robot_id
	if not String(main.hud.status_text()).contains("stairs"):
		return "HUD does not show the selected body's capabilities"
	return ""


# ---------- G2a: senses, journal, avoidance ----------

## Spawn avatars from [id, body, x, z, yaw] rows, then wait until physics knows their colliders.
func _place(w: RangeWorld, rows: Array) -> Dictionary:
	var out := {}
	for row in rows:
		out[row[0]] = w.spawn_avatar(row[0], row[1], Vector3(float(row[2]), 0, float(row[3])), float(row[4]))
	for i in 3:
		await get_tree().physics_frame
	return out


## The observation an observer has about a target (by its anonymous track), or {}.
func _about(w: RangeWorld, packet: Dictionary, observer: Avatar, target: Avatar, kind := "VISUAL_PRESENCE") -> Dictionary:
	var track := w.senses.track_id_for(observer.avatar_id, target.avatar_id)
	for item in packet["observations"]:
		if item["kind"] == kind and track != "" and item["track_id"] == track:
			return item
	return {}


func _speech(packet: Dictionary, text: String) -> Dictionary:
	for item in packet["observations"]:
		if item["kind"] == "AUDIO_SPEECH" and item["value"]["text"] == text:
			return item
	return {}


## A visitor standing just past the end of partition_a: only its right side shows (D-39).
func test_partly_seen_behind_partition_edge() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["observer", "legged_humanoid", 13.0, 12.05, PI / 2],     # faces -x, toward the partition end
		["half", "human_walker", 8.5, 12.05, -PI / 2],            # behind the end; its right side is +z
		["clear", "human_walker", 8.5, 13.0, -PI / 2],            # past the end: fully visible
		["hidden", "human_walker", 8.5, 10.0, -PI / 2],           # fully behind the partition
	])
	var packet := w.senses.observe(av["observer"])
	var half := _about(w, packet, av["observer"], av["half"])
	if half.is_empty() or half["validity"] != "DEGRADED" or half.get("validity_reason") != "PARTLY_OCCLUDED":
		return "half-hidden visitor should be DEGRADED / PARTLY_OCCLUDED, got %s" % [half]
	if half["visible_parts"] != ["RIGHT_SIDE"] or half["quality"] == null or float(half["quality"]) >= 0.5:
		return "half-hidden visitor: expected only RIGHT_SIDE visible and a low quality, got %s" % [half]
	var clear := _about(w, packet, av["observer"], av["clear"])
	if clear.is_empty() or clear["validity"] != "OBSERVED" or clear["visible_parts"].size() != 4:
		return "visitor past the partition should be OBSERVED with all four parts, got %s" % [clear]
	if w.senses.track_id_for("observer", "hidden") != "":
		return "a visitor never seen (fully behind the partition) must not appear at all"
	for item in packet["observations"]:
		if item["source_entity_id"] != null:
			return "source_entity_id must stay null without an introduction"
	return ""


## The 1.1 m divider hides a visitor from a quadruped's 0.55 m sensors, not from a humanoid's (D-36).
func test_low_divider_and_sensor_height() -> String:
	var w := await _world(["legged_humanoid", "quadruped", "human_walker"])
	var av := await _place(w, [
		["visitor", "human_walker", 4.5, 3.2, PI],
		["quad", "quadruped", 5.6, 7.4, 0.0],
		["humanoid", "legged_humanoid", 3.4, 7.4, 0.0],
	])
	var quad_packet := w.senses.observe(av["quad"])
	var humanoid_packet := w.senses.observe(av["humanoid"])
	if not _about(w, quad_packet, av["quad"], av["visitor"]).is_empty():
		return "the quadruped saw the visitor through the 1.1 m divider"
	var seen := _about(w, humanoid_packet, av["humanoid"], av["visitor"])
	if seen.is_empty() or seen["validity"] != "OBSERVED":
		return "the humanoid should see the visitor over the divider, got %s" % [seen]
	return ""


func test_crowd_occludes() -> String:
	var w := await _world(["quadruped", "human_walker"])
	var av := await _place(w, [
		["quad", "quadruped", 15.0, 17.5, 0.0],
		["blocker", "human_walker", 15.0, 15.8, 0.0],
		["target", "human_walker", 15.0, 13.8, PI],
	])
	if not _about(w, w.senses.observe(av["quad"]), av["quad"], av["target"]).is_empty():
		return "a person standing in between should hide the target from a low sensor"
	av["blocker"].global_position = Vector3(11.0, 0.0, 17.5)
	for i in 3:
		await get_tree().physics_frame
	var item := _about(w, w.senses.observe(av["quad"]), av["quad"], av["target"])
	if item.is_empty() or item["validity"] != "OBSERVED":
		return "with the blocker gone the target should be seen, got %s" % [item]
	return ""


## Seen, then walks behind partition_a: OCCLUDED at the last known spot with no quality, then gone.
func test_lost_track_then_dropped() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["observer", "legged_humanoid", 13.0, 14.0, PI / 2],
		["walker", "human_walker", 8.0, 14.0, 0.0],
	])
	w.start_run(3)
	var history: Array = []
	var track := {"id": ""}   # the walker's anonymous track, captured while it exists
	w.senses.sampled.connect(func(_tick: int, packets: Dictionary) -> void:
		history.append(packets["observer"])
		if track["id"] == "":
			track["id"] = w.senses.track_id_for("observer", "walker"))
	av["walker"].drive(Vector3(0, 0, -1.4))
	for i in 60 * 8:
		await get_tree().physics_frame
		if av["walker"].global_position.z <= 10.0:
			av["walker"].stop()
	var states: Array[String] = []
	var occluded := {}
	for packet in history:
		var item := {}
		for obs in packet["observations"]:
			if obs["kind"] == "VISUAL_PRESENCE" and obs["track_id"] == track["id"]:
				item = obs
		var state := "ABSENT" if item.is_empty() else String(item["validity"])
		if states.is_empty() or states[-1] != state:
			states.append(state)
		if state == "OCCLUDED" and occluded.is_empty():
			occluded = item
	if states.slice(0, 1) != ["OBSERVED"] or not states.has("OCCLUDED") or states[-1] != "ABSENT":
		return "expected OBSERVED ... OCCLUDED ... then absent, got %s" % [states]
	if occluded.get("validity_reason") != "OCCLUDED_SINCE_LAST_SEEN" or occluded["quality"] != null:
		return "occluded track should say OCCLUDED_SINCE_LAST_SEEN with no quality, got %s" % [occluded]
	if float(occluded["position_estimate"]["z"]) < 10.5:
		return "occluded track should stay at the last place it was seen, got %s" % [occluded["position_estimate"]]
	return ""


## T13 groundwork: a gesture is perceived only in view, in line of sight and within legible range.
func test_gesture_perception() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["observer", "legged_humanoid", 15.0, 15.5, 0.0],    # faces -z
		["front", "human_walker", 15.0, 12.5, PI],           # in view, 3 m
		["behind", "human_walker", 15.0, 18.5, PI],          # outside the field of view
		["walled", "human_walker", 19.0, 11.0, PI],          # behind partition_b
		["far", "human_walker", 12.5, 2.5, PI],              # in view but beyond legible range
	])
	for id in ["front", "behind", "walled", "far"]:
		if not av[id].perform_gesture("WAVE"):
			return "%s could not wave" % id
	var packet := w.senses.observe(av["observer"])
	var gestures: Array = packet["observations"].filter(func(item: Dictionary) -> bool: return item["kind"] == "VISUAL_GESTURE")
	if gestures.size() != 1:
		return "expected exactly one perceived gesture (the one in front), got %d" % gestures.size()
	var g: Dictionary = gestures[0]
	if g["track_id"] != w.senses.track_id_for("observer", "front") or g["value"]["gesture"] != "WAVE":
		return "the perceived gesture should be the WAVE in front, got %s" % [g]
	if g["value"]["direction"] != "TOWARD_OBSERVER" or g["event_id"] == null:
		return "gesture should carry its event id and face the observer, got %s" % [g]
	if _about(w, packet, av["observer"], av["far"]).is_empty():
		return "the far visitor should still be seen as present (only the gesture is too far to read)"
	return ""


func test_gesture_refused_is_never_seen() -> String:
	var w := await _world(["legged_humanoid", "quadruped"])
	var av := await _place(w, [
		["observer", "legged_humanoid", 15.0, 15.5, 0.0],
		["quad", "quadruped", 15.0, 12.5, PI],
	])
	if av["quad"].perform_gesture("WAVE"):
		return "an armless quadruped must not be able to wave"
	for item in w.senses.observe(av["observer"])["observations"]:
		if item["kind"] == "VISUAL_GESTURE":
			return "a refused gesture was perceived"
	if not av["quad"].perform_gesture("HEAD_TILT"):
		return "the quadruped should be able to tilt its sensor head"
	var tilt := _about(w, w.senses.observe(av["observer"]), av["observer"], av["quad"], "VISUAL_GESTURE")
	if tilt.is_empty() or tilt["value"]["gesture"] != "HEAD_TILT":
		return "HEAD_TILT in view should be perceived, got %s" % [tilt]
	return ""


## T14 groundwork: speech is heard without sight, weakened through a partition.
func test_speech_audibility() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["listener", "legged_humanoid", 15.0, 15.5, 0.0],
		["behind", "human_walker", 15.0, 17.5, PI],
		["front", "human_walker", 15.0, 13.5, PI],
		["listener2", "legged_humanoid", 11.5, 9.0, PI / 2],
		["walled", "human_walker", 8.5, 9.0, -PI / 2],
	])
	av["behind"].say("Behind you.", "listener")
	av["front"].say("Hello there.")
	av["walled"].say("Anyone over there?")
	var packet := w.senses.observe(av["listener"])
	var behind := _speech(packet, "Behind you.")
	if behind.is_empty() or behind["validity"] != "UNKNOWN_SOURCE" or behind.get("validity_reason") != "SPEAKER_NOT_IN_VIEW":
		return "speech from behind should be heard as UNKNOWN_SOURCE / SPEAKER_NOT_IN_VIEW, got %s" % [behind]
	if behind["track_id"] != null or behind["position_estimate"] != null or absf(float(behind["bearing_rad"])) < 2.8:
		return "unseen speaker: no track or position, a direction behind, got %s" % [behind]
	if behind["value"]["addressed_to_observer"] != true:
		return "speech addressed to the listener should say so"
	var front := _speech(packet, "Hello there.")
	if front.is_empty() or front["validity"] != "OBSERVED" or front["track_id"] != w.senses.track_id_for("listener", "front"):
		return "speech from a visible speaker should be OBSERVED and on its track, got %s" % [front]
	if front["value"]["addressed_to_observer"] != null:
		return "speech with no addressee should have addressed_to_observer null"
	if not _speech(packet, "Anyone over there?").is_empty():
		return "speech 9 m away behind a partition should not reach this listener"
	var walled := _speech(w.senses.observe(av["listener2"]), "Anyone over there?")
	if walled.is_empty() or walled["validity"] != "UNKNOWN_SOURCE" or walled.get("validity_reason") != "THROUGH_WALL":
		return "speech through a partition 3 m away should be heard weakly, source unknown, got %s" % [walled]
	if float(walled["quality"]) >= float(behind["quality"]):
		return "speech through the partition should be weaker than open speech nearby"
	# Delivered once: after the sample, it is gone (no backfill, no repeats).
	w.senses.sample()
	if not _speech(w.senses.observe(av["listener"]), "Behind you.").is_empty():
		return "speech should be delivered once, at the first sample after it was spoken"
	return ""


func test_walls_range_and_noise_on_speech() -> String:
	var w := await _world(["legged_humanoid"])
	var av := await _place(w, [
		["by_wall", "legged_humanoid", 1.6, 13.0, PI / 2],
		["corner", "legged_humanoid", 7.0, 15.0, -PI / 2],
		["open", "legged_humanoid", 17.0, 17.5, -PI / 2],
	])
	var level := SenseModel.SPEECH_LEVEL_DB
	var outside := SenseModel.hear(w, Vector3(-1.0, 1.5, 13.0), av["by_wall"], level)
	var inside := SenseModel.hear(w, Vector3(4.2, 1.5, 13.0), av["by_wall"], level)
	if outside["heard"] or not inside["heard"] or float(outside["wall_loss_db"]) < SenseModel.WALL_LOSS_DB:
		return "a sound-blocking wall should stop speech that the same distance in the open carries: %s vs %s" % [outside, inside]
	var far := SenseModel.hear(w, Vector3(17.0, 1.5, 6.4), av["open"], level)
	if far["heard"]:
		return "speech 11 m away should be beyond hearing, got %s" % [far]
	var quiet := SenseModel.hear(w, Vector3(12.0, 1.5, 15.0), av["corner"], level)   # chair_corner, 40 dB floor
	var busy := SenseModel.hear(w, Vector3(22.0, 1.5, 17.5), av["open"], level)      # main floor, 45 dB floor
	if not (float(busy["snr_db"]) < SenseModel.CLEAR_SPEECH_SNR_DB and float(quiet["snr_db"]) >= SenseModel.CLEAR_SPEECH_SNR_DB):
		return "at 5 m speech should be clear in the quiet corner and weak on the busy floor: %s vs %s" % [quiet, busy]
	return ""


## Packets every 60/tick_hz ticks, on the 60 Hz tick, anonymous per observer. Writes the packets
## and the journal for tools/godot_check.py to validate against the contracts.
func test_sampling_and_packets() -> String:
	var w := await _world(["legged_humanoid", "quadruped", "human_walker"])
	var av := await _place(w, [
		["a", "legged_humanoid", 15.0, 15.5, 0.0],
		["b", "quadruped", 13.0, 15.5, 0.0],
		["c", "human_walker", 14.0, 12.5, PI],
	])
	var path := artifacts_dir.path_join("sampling.jsonl")
	if not w.start_run(7, path, 10):
		return "could not start a journaled run at %s" % path
	var samples: Array = []
	w.senses.sampled.connect(func(tick: int, packets: Dictionary) -> void: samples.append([tick, packets]))
	av["c"].perform_gesture("SMALL_WAVE")
	av["c"].say("Over here!")
	av["b"].perform_gesture("WAVE")
	for i in 60:
		await get_tree().physics_frame
	w.end_run()
	if samples.size() < 9 or samples.size() > 11:
		return "expected about 10 samples in 1 s at 10 Hz, got %d" % samples.size()
	var all_packets: Array = []
	var ids := {}
	for s in samples:
		if int(s[0]) % 6 != 0:
			return "sample at tick %d is not on the 60/10 = 6 tick grid" % s[0]
		for packet in s[1].values():
			if int(packet["based_on_tick_id"]) != int(s[0]):
				return "based_on_tick_id must be the 60 Hz tick of the sample"
			all_packets.append(packet)
			for item in packet["observations"]:
				if ids.has(item["observation_id"]):
					return "observation id %s used twice" % item["observation_id"]
				ids[item["observation_id"]] = true
	var ta := w.senses.track_id_for("a", "c")
	var tb := w.senses.track_id_for("b", "c")
	if ta == "" or tb == "" or ta == tb or ta.contains("c") and ta == "anon_c":
		return "each observer needs its own anonymous track for the same visitor (%s, %s)" % [ta, tb]
	var f := FileAccess.open(artifacts_dir.path_join("sampling.observations.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(all_packets, "", true))
	f.close()
	return ""


## Two runs of the demo with the same seed write the same journal, byte for byte (T28 groundwork).
func test_journal_is_deterministic() -> String:
	var digests: Array[String] = []
	for run in ["demo_a", "demo_b"]:
		var main: Node = load("res://scenes/main.tscn").instantiate()
		main.journal_path = artifacts_dir.path_join(run + ".jsonl")
		main.run_seed = 11
		add_child(main)
		_node = main
		for i in 60 * 30:
			await get_tree().physics_frame
			if main.demo != null and main.demo.finished:
				break
		if main.demo == null or not main.demo.finished:
			return "the demo did not finish in %s" % run
		digests.append(main.world.end_run())
		await _cleanup()
	if digests[0] == "" or digests[0] != digests[1]:
		return "two runs with the same seed gave different journals (%s vs %s)" % digests
	var kinds := {}
	for line in FileAccess.get_file_as_string(artifacts_dir.path_join("demo_a.jsonl")).split("\n", false):
		kinds[JSON.parse_string(line)["kind"]] = true
	for kind in ["RUN_STARTED", "OBSERVATION_DELIVERED", "GESTURE_PERFORMED", "GESTURE_REFUSED", "SPEECH_EMITTED", "RUN_ENDED"]:
		if not kinds.has(kind):
			return "the demo journal has no %s entry" % kind
	return ""


## Shared avoidance across navigation sizes (D-42): a wheeled humanoid and a quadruped cross
## head-on and at right angles; both arrive with no contact.
func test_avoidance_crossing() -> String:
	var cases := [
		["head-on", [11.0, 16.5, -PI / 2, 20.0, 16.5], [20.0, 16.5, PI / 2, 11.0, 16.5]],
		["right angles", [15.5, 14.2, PI, 15.5, 19.3], [11.0, 17.0, -PI / 2, 20.0, 17.0]],
	]
	for c in cases:
		var w := await _world(["wheeled_humanoid", "quadruped"])
		var wheeled := w.spawn_avatar("wheeled", "wheeled_humanoid", Vector3(c[1][0], 0, c[1][1]), c[1][2])
		var quad := w.spawn_avatar("quad", "quadruped", Vector3(c[2][0], 0, c[2][1]), c[2][2])
		wheeled.navigate_to(w.ground_point(c[1][3], c[1][4]))
		quad.navigate_to(w.ground_point(c[2][3], c[2][4]))
		var traces := await _run([wheeled, quad], 60 * 30, _all_idle([wheeled, quad]))
		for a in [wheeled, quad]:
			if a.ever_stuck or not a.last_goal_reached:
				return "%s: %s did not arrive (ended at %s)" % [c[0], a.avatar_id, _v(a.global_position)]
			if not a.contacts.is_empty():
				return "%s: %s touched %s" % [c[0], a.avatar_id, a.contacts]
		var closest := INF
		var pw: Array = traces["wheeled"]["pos"]
		var pq: Array = traces["quad"]["pos"]
		for i in pw.size():
			closest = minf(closest, Vector2(pw[i].x - pq[i].x, pw[i].z - pq[i].z).length())
		if closest > 3.0:
			return "%s: the robots never came near each other (closest %.2f m); the test did not exercise avoidance" % [c[0], closest]
		await _cleanup()
	return ""


# ---------- G2b: COMMS router, action gate, Python link ----------

func _comm_for(w: RangeWorld, event_id: String) -> Dictionary:
	for c in w.comms.events:
		if c["source_event_id"] == event_id:
			return c
	return {}


func _ticks(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


## Collect every observation each avatar receives, across samples, into `into`.
func _collect(w: RangeWorld, into: Dictionary) -> void:
	w.senses.sampled.connect(func(_tick: int, p: Dictionary) -> void:
		for id in p:
			if not into.has(id):
				into[id] = {"observations": []}
			into[id]["observations"].append_array(p[id]["observations"]))


func _saw_text(packets: Dictionary, avatar_id: String, kind: String, text: String) -> bool:
	for item in packets.get(avatar_id, {"observations": []})["observations"]:
		if item["kind"] == kind and item["value"].get("text", "") == text:
			return true
	return false


## T13 through the router: a gesture's comms_event lists only those who could see it.
func test_router_gesture_t13() -> String:
	var w := await _world(["legged_humanoid", "human_walker", "quadruped"])
	var av := await _place(w, [
		["waver", "human_walker", 15.0, 12.5, PI],
		["seer", "legged_humanoid", 15.0, 15.5, 0.0],
		["turned", "human_walker", 13.5, 15.5, PI],        # faces away from the waver
		["walled", "human_walker", 8.5, 10.0, -PI / 2],    # partition_a in between
		["quad", "quadruped", 18.0, 17.5, 0.0],
	])
	if w.comms.send_gesture(av["quad"], "WAVE")["reason_code"] != "CAPABILITY_DENIED":
		return "an armless quadruped's wave must be refused"
	var sent := w.comms.send_gesture(av["waver"], "WAVE")
	if not sent["ok"]:
		return "the visitor could not wave: %s" % [sent]
	await _ticks(Avatar.GESTURE_DURATION_TICKS + 12)
	var comm := _comm_for(w, sent["event_id"])
	if comm.is_empty() or comm["channel"] != "GESTURE" or comm["expression"] != {"gesture": "WAVE"}:
		return "expected a GESTURE comms_event with the expression, got %s" % [comm]
	if not comm["delivered_to"].has("seer"):
		return "the observer facing the visitor should receive the wave: %s" % [comm["delivered_to"]]
	for id in ["turned", "walled"]:
		if not comm["not_delivered_to"].has(id):
			return "%s could not see the wave and must not receive it: %s" % [id, comm]
	if w.comms.events.size() != 1:
		return "the refused wave must not produce a comms_event"
	return ""


## T14 through the router: speech reaches listeners in earshot, not those too far away.
func test_router_local_t14() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["speaker", "human_walker", 15.0, 13.5, PI],
		["near", "legged_humanoid", 15.0, 15.5, 0.0],
		["behind", "human_walker", 13.5, 15.5, PI],     # can't see the speaker, can hear
		["far", "human_walker", 15.0, 4.0, 0.0],        # 9.5 m: below the noise floor
		["walled", "human_walker", 8.5, 10.0, -PI / 2],
	])
	var sent := w.comms.send_local(av["speaker"], "Is the cafe this way?", "near")
	await _ticks(12)
	var comm := _comm_for(w, sent["event_id"])
	if comm.is_empty() or comm["channel"] != "LOCAL" or comm["addressee_id"] != "near":
		return "expected a LOCAL comms_event addressed to near, got %s" % [comm]
	if not comm["delivered_to"].has("near") or not comm["delivered_to"].has("behind"):
		return "listeners in earshot should receive the speech, seen or not: %s" % [comm["delivered_to"]]
	if not comm["not_delivered_to"].has("far"):
		return "a listener 9.5 m away on a 45 dB floor should not receive it: %s" % [comm]
	return ""


## T15: group messages reach members anywhere, never non-members, even right next to the sender.
func test_group_messages_t15() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["a", "legged_humanoid", 5.0, 3.0, 0.0],
		["b", "human_walker", 25.0, 17.0, 0.0],      # far member
		["c", "human_walker", 5.8, 3.0, 0.0],        # right next to the sender, never a member
		["d", "human_walker", 10.0, 17.0, 0.0],      # invited, never accepts
		["e", "human_walker", 12.0, 17.0, 0.0],      # invited, declines
	])
	var packets := {}
	_collect(w, packets)
	var group_id := String(w.comms.create_group(av["a"], "Cafe meetup")["event_id"])
	w.comms.invite(av["a"], group_id, "b")
	w.comms.invite(av["a"], group_id, "d")
	w.comms.invite(av["a"], group_id, "e")
	await _ticks(7)
	var got_invite := false
	for item in packets["b"]["observations"]:
		if item["kind"] == "GROUP_INVITE" and item["value"]["group_id"] == group_id and item["source_entity_id"] == "a":
			got_invite = true
	if not got_invite:
		return "b should receive the invitation on its device, from a"
	if w.comms.accept(av["c"], group_id)["reason_code"] != "GROUP_NOT_MEMBER":
		return "accepting without an invitation must be refused"
	w.comms.accept(av["b"], group_id)
	w.comms.decline(av["e"], group_id)
	packets.clear()
	var first := w.comms.send_group(av["a"], group_id, "Meet at the cafe at noon.")
	await _ticks(7)
	if not _saw_text(packets, "b", "GROUP_MESSAGE", "Meet at the cafe at noon."):
		return "the far member should receive the group message"
	for id in ["c", "d", "e"]:
		if _saw_text(packets, id, "GROUP_MESSAGE", "Meet at the cafe at noon.") \
				or _saw_text(packets, id, "AUDIO_SPEECH", "Meet at the cafe at noon."):
			return "%s is not a member and must not receive the group message" % id
	if _comm_for(w, first["event_id"])["delivered_to"] != ["b"]:
		return "comms_event should list only b: %s" % [_comm_for(w, first["event_id"])]
	if w.comms.send_group(av["c"], group_id, "Can I come?")["reason_code"] != "GROUP_NOT_MEMBER":
		return "a non-member must not be able to post to the group"
	w.comms.leave(av["b"], group_id)
	packets.clear()
	var second := w.comms.send_group(av["a"], group_id, "Changed to one o'clock.")
	await _ticks(7)
	if _saw_text(packets, "b", "GROUP_MESSAGE", "Changed to one o'clock."):
		return "after leaving, b must not receive group messages"
	if not _comm_for(w, second["event_id"])["delivered_to"].is_empty():
		return "nobody else is a member, so nobody should receive the second message"
	return ""


## T16: the PA is refused for unauthorized senders (and nobody hears it); authorized reach everyone.
func test_pa_authorization_t16() -> String:
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["robot", "legged_humanoid", 15.0, 15.5, 0.0],
		["staff", "human_walker", 3.0, 8.0, 0.0],
		["visitor_1", "human_walker", 25.0, 17.0, 0.0],
		["visitor_2", "human_walker", 26.0, 4.0, 0.0],
	])
	var packets := {}
	_collect(w, packets)
	if w.comms.send_pa(av["robot"], "Everyone to the exit!")["reason_code"] != "PA_UNAUTHORIZED":
		return "a robot without PA permission must be refused"
	await _ticks(7)
	for id in ["staff", "visitor_1", "visitor_2"]:
		if _saw_text(packets, id, "AUDIO_SPEECH", "Everyone to the exit!"):
			return "an unauthorized announcement must reach nobody"
	if not w.comms.events.is_empty():
		return "a refused announcement must not produce a comms_event"
	w.comms.pa_operators["staff"] = true
	packets.clear()
	var sent := w.comms.send_pa(av["staff"], "The demo starts in five minutes.")
	await _ticks(7)
	for id in ["robot", "visitor_1", "visitor_2"]:
		var heard := {}
		for item in packets[id]["observations"]:
			if item["kind"] == "AUDIO_SPEECH" and item["value"]["text"] == "The demo starts in five minutes.":
				heard = item
		if heard.is_empty() or heard["value"]["channel"] != "PA" or absf(float(heard["position_estimate"]["x"]) - 1.0) > 0.01:
			return "%s should hear the announcement on channel PA from the speaker, got %s" % [id, heard]
	if _comm_for(w, sent["event_id"])["delivered_to"] != ["robot", "visitor_1", "visitor_2"]:
		return "the PA comms_event should list everyone in coverage"
	return ""


func _req(agent_id: String, tick: int, action: String, args: Dictionary, n: int) -> Dictionary:
	return {"schema_version": "1.0", "action_request_id": "act_t_%04d" % n, "agent_id": agent_id,
		"based_on_tick_id": tick, "action": action, "args": args}


## The action gate answers each request with the right reason code (Blueprint §12.3).
func test_action_gate_reason_codes() -> String:
	var w := await _world(["legged_humanoid", "quadruped", "human_walker"])
	var av := await _place(w, [
		["agent", "legged_humanoid", 15.0, 15.5, 0.0],
		["quad", "quadruped", 12.0, 17.5, 0.0],
		["friend", "human_walker", 15.0, 14.0, PI],
		["bystander", "human_walker", 16.5, 15.0, PI],
	])
	await _ticks(130)
	w.senses.sample()
	var friend_track := w.senses.track_id_for("agent", "friend")
	var mine := ["agent", "quad"]
	var now := w.clock.tick
	var cases := [
		["INVALID_SCHEMA", _req("agent", now, "FLY", {}, 1)],
		["INVALID_SCHEMA", _req("agent", now, "GESTURE", {"gesture": "NOD", "color": "red"}, 2)],
		["INVALID_SCHEMA", {"schema_version": "1.0", "action_request_id": "act_t_0003", "agent_id": "agent"}],
		["INVALID_SCHEMA", _req("agent", now + 30, "NO_OP", {}, 4)],
		["CAPABILITY_DENIED", _req("bystander", now, "NO_OP", {}, 5)],
		["STALE_OBSERVATION", _req("agent", now - 120, "NO_OP", {}, 6)],
		["CAPABILITY_DENIED", _req("quad", now, "GESTURE", {"gesture": "WAVE"}, 7)],
		["PA_UNAUTHORIZED", _req("agent", now, "SPEAK", {"channel": "PA", "text": "Attention."}, 8)],
		["GROUP_NOT_MEMBER", _req("agent", now, "SPEAK", {"channel": "GROUP", "text": "Hi.", "group_id": "grp_999999"}, 9)],
		["PRIVACY_SCOPE_DENIED", _req("agent", now, "SPEAK", {"channel": "LOCAL", "text": "Your table is ready.",
			"addressee_id": friend_track, "disclosure_scope": "ONE_TO_ONE"}, 10)],
		["PRIVACY_SCOPE_DENIED", _req("agent", now, "SPEAK", {"channel": "LOCAL", "text": "x", "disclosure_scope": "SEALED"}, 11)],
		["TARGET_UNKNOWN", _req("agent", now, "MOVE_TO", {"target_id": "anon_nobody00000"}, 12)],
		["TARGET_UNKNOWN", _req("agent", now, "MOVE_TO", {"destination": {"x": 45.0, "z": 3.0}}, 13)],
		["OK", _req("agent", now, "GESTURE", {"gesture": "NOD", "target_id": friend_track}, 14)],
		["OK", _req("agent", now, "CREATE_GROUP", {"group_name": "Tour"}, 15)],
		["GROUP_NOT_MEMBER", _req("quad", now, "ACCEPT_GROUP", {"group_id": "grp_000001"}, 16)],
	]
	var results: Array = []
	var failures: Array[String] = []
	for c in cases:
		var result := w.actions.submit(c[1], mine)
		results.append(result)
		if result["reason_code"] != c[0]:
			failures.append("%s: expected %s, got %s" % [c[1].get("action_request_id", "?"), c[0], result["reason_code"]])
	var not_a_dict := w.actions.submit("hello", mine)
	results.append(not_a_dict)
	if not_a_dict["reason_code"] != "INVALID_SCHEMA":
		failures.append("a request that is not an object must be INVALID_SCHEMA")
	if results[13]["resulting_event_ids"].is_empty() or not results[13]["executed"]:
		failures.append("an accepted gesture should report its event id")
	# Alone with the friend, the one-to-one sentence is allowed.
	av["bystander"].global_position = Vector3(27.0, 0.0, 18.0)
	av["quad"].global_position = Vector3(3.0, 0.0, 18.0)
	await _ticks(3)
	var alone := w.actions.submit(_req("agent", w.clock.tick, "SPEAK", {"channel": "LOCAL", "text": "Your table is ready.",
		"addressee_id": friend_track, "disclosure_scope": "ONE_TO_ONE"}, 20), mine)
	results.append(alone)
	if alone["reason_code"] != "OK":
		failures.append("with nobody else in earshot, one-to-one speech should be allowed, got %s" % alone["reason_code"])
	# Rate limit: an eleventh request within one second is refused.
	await _ticks(61)
	var burst: Array = []
	for i in 11:
		burst.append(w.actions.submit(_req("quad", w.clock.tick, "NO_OP", {}, 30 + i), mine)["reason_code"])
	if burst.slice(0, 10).has("RATE_LIMITED") or burst[10] != "RATE_LIMITED":
		failures.append("expected ten accepted then RATE_LIMITED, got %s" % [burst])
	var f := FileAccess.open(artifacts_dir.path_join("gate.action_results.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(results, "", true))
	f.close()
	return "; ".join(failures)


# ----- the live link (sidecars started by tools/godot_check.py) -----

func _link_port(env_name: String) -> int:
	return int(OS.get_environment(env_name))


## Run frames at a real-time pace (the link talks to another process) and track how long the
## engine's own work per frame takes. Returns the longest such frame, in milliseconds.
func _run_linked(frames: int, done: Callable) -> float:
	var longest := 0.0
	for i in frames:
		var start := Time.get_ticks_usec()
		await get_tree().physics_frame
		longest = maxf(longest, (Time.get_ticks_usec() - start) / 1000.0)
		OS.delay_msec(3)
		if done.call():
			break
	return longest


func _results_by_label(w: RangeWorld) -> Dictionary:
	var by := {}
	for r in w.actions.resolved:
		var id := String(r["result"]["action_request_id"])
		for label in ["stale", "invalid", "pa", "group", "privacy", "unknowntarget", "notmine", "valid", "burst", "greet"]:
			if id.contains("_%s_" % label):
				var key := "%s:%s" % [r["result"]["agent_id"], label]
				if not by.has(key):
					by[key] = []
				by[key].append(r["result"]["reason_code"])
	return by


## End to end: observations to Python, scripted replies back, every refusal with its reason code;
## the sidecar drops the connection once and Godot reconnects while the world keeps ticking.
func test_link_end_to_end() -> String:
	if _link_port("RANGE_LINK_PORT") == 0:
		return "no test sidecar: run the Godot tests through tools/godot_check.py"
	var w := await _world(["legged_humanoid", "quadruped", "human_walker"])
	var av := await _place(w, [
		["robot_legged", "legged_humanoid", 15.0, 15.5, 0.0],
		["robot_quadruped", "quadruped", 13.5, 15.5, 0.0],
		["visitor", "human_walker", 14.3, 12.5, PI],
	])
	w.start_run(5, artifacts_dir.path_join("link.jsonl"))
	var link := LinkClient.new()
	add_child(link)
	link.setup(w, _link_port("RANGE_LINK_PORT"), ["robot_legged", "robot_quadruped"])
	var waved := {"done": false, "probed_at": -1}
	var ticks_before := w.clock.tick
	var frames := {"n": 0}
	var longest := await _run_linked(60 * 60, func() -> bool:
		frames["n"] += 1
		var seen := _results_by_label(w)
		if waved["probed_at"] < 0 and seen.has("robot_legged:valid"):
			waved["probed_at"] = w.clock.tick
		# Wave once the probes are answered and their burst has left the one-second rate window.
		if not waved["done"] and waved["probed_at"] >= 0 and w.clock.tick > int(waved["probed_at"]) + 90:
			av["visitor"].perform_gesture("WAVE")
			waved["done"] = true
		return seen.has("robot_legged:valid") and seen.has("robot_quadruped:greet") and seen.has("robot_legged:greet"))
	var ticks_linked := w.clock.tick - ticks_before
	await _ticks(12)   # the next sample delivers the robots' speech to the visitor
	var by := _results_by_label(w)
	link.queue_free()
	w.end_run()
	var expect := {"robot_legged:stale": "STALE_OBSERVATION", "robot_legged:invalid": "INVALID_SCHEMA",
		"robot_legged:pa": "PA_UNAUTHORIZED", "robot_legged:group": "GROUP_NOT_MEMBER",
		"robot_legged:privacy": "PRIVACY_SCOPE_DENIED", "robot_legged:unknowntarget": "TARGET_UNKNOWN",
		"visitor:notmine": "CAPABILITY_DENIED", "robot_legged:valid": "OK"}
	for key in expect:
		if not by.has(key) or by[key][0] != expect[key]:
			return "%s: expected %s, got %s (all: %s)" % [key, expect[key], by.get(key), by]
	if not by.get("robot_legged:burst", []).has("RATE_LIMITED"):
		return "the burst of requests should hit the rate limit: %s" % [by.get("robot_legged:burst")]
	if by.get("robot_legged:greet", []) != ["OK", "OK"]:
		return "the legged robot should wave back and say hello: %s" % [by.get("robot_legged:greet")]
	if by.get("robot_quadruped:greet", []) != ["CAPABILITY_DENIED", "OK"]:
		return "the quadruped cannot wave but can say hello: %s" % [by.get("robot_quadruped:greet")]
	if w.senses.last_heard.get("visitor", {}).get("text") != "Hello!":
		return "the visitor should have heard the robots' hello"
	if link.stats["disconnects"] < 1 or link.stats["connects"] < 2:
		return "the sidecar dropped the connection once; Godot should have reconnected: %s" % [link.stats]
	if ticks_linked != frames["n"]:
		return "the world must tick once per frame whatever the link does (%d ticks, %d frames)" % [ticks_linked, frames["n"]]
	if longest > 50.0:
		return "a frame took %.1f ms while linked; the world must not wait for Python" % longest
	return ""


func test_link_wrong_token() -> String:
	if _link_port("RANGE_LINK_PORT") == 0:
		return "no test sidecar: run the Godot tests through tools/godot_check.py"
	var w := await _world(["legged_humanoid"])
	await _place(w, [["robot_legged", "legged_humanoid", 15.0, 15.5, 0.0]])
	var link := LinkClient.new()
	add_child(link)
	link.setup(w, _link_port("RANGE_LINK_PORT"), ["robot_legged"], "not-the-session-token-at-all-0000")
	var before := w.clock.tick
	var longest := await _run_linked(600, func() -> bool: return link.stats["refused"] >= 1)
	var status := link.status
	var stats := link.stats.duplicate()
	link.queue_free()
	if status != "REFUSED" or stats["received"] != 0:
		return "a wrong token must be refused with nothing exchanged: %s %s" % [status, stats]
	if w.clock.tick == before or longest > 50.0:
		return "the world must keep ticking smoothly while refused"
	return ""


## A slow Python side: its answers arrive too late and are refused as stale; the world never waits.
func test_link_slow_sidecar() -> String:
	if _link_port("RANGE_LINK_PORT_SLOW") == 0:
		return "no slow test sidecar: run the Godot tests through tools/godot_check.py"
	var w := await _world(["legged_humanoid", "human_walker"])
	var av := await _place(w, [
		["robot_legged", "legged_humanoid", 15.0, 15.5, 0.0],
		["visitor", "human_walker", 15.0, 12.5, PI],
	])
	var link := LinkClient.new()
	add_child(link)
	link.setup(w, _link_port("RANGE_LINK_PORT_SLOW"), ["robot_legged"])
	var state := {"waved": false}
	var before := w.clock.tick
	var frames := {"n": 0}
	var longest := await _run_linked(60 * 60, func() -> bool:
		frames["n"] += 1
		if not state["waved"] and link.is_connected_to_sidecar() and w.clock.tick > 60:
			av["visitor"].perform_gesture("WAVE")
			state["waved"] = true
		return not w.actions.resolved.is_empty())
	link.queue_free()
	if w.actions.resolved.is_empty():
		return "the slow sidecar's answer never arrived"
	if w.actions.resolved[0]["result"]["reason_code"] != "STALE_OBSERVATION":
		return "an answer 1.5 s late should be refused as stale, got %s" % w.actions.resolved[0]["result"]["reason_code"]
	if w.clock.tick - before != frames["n"] or longest > 50.0:
		return "the world must keep its tick while Python is slow (longest frame %.1f ms)" % longest
	return ""


func test_link_no_sidecar() -> String:
	var w := await _world(["legged_humanoid"])
	await _place(w, [["robot_legged", "legged_humanoid", 15.0, 15.5, 0.0]])
	var link := LinkClient.new()
	add_child(link)
	link.setup(w, 9, ["robot_legged"], "a-token-for-a-port-nobody-listens-on")
	var before := w.clock.tick
	var longest := await _run_linked(300, func() -> bool: return link.stats["refused"] >= 1)
	var status := link.status
	link.queue_free()
	if status != "REFUSED" or w.clock.tick == before or longest > 50.0:
		return "with no sidecar the link should report REFUSED and the world keep ticking (%s, %.1f ms)" % [status, longest]
	return ""
