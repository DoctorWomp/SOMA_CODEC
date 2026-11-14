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
]

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
			"cam_toggle_mode", "select_prev", "select_next", "sim_pause", "demo_restart", "hud_toggle"]:
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
	if reg["walls"].size() != 6 or partitions != 2:
		return "expected 4 outer walls + 2 movable partitions, got %d walls, %d movable" % [reg["walls"].size(), partitions]
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
