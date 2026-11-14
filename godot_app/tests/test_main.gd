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
	"test_robot_model",
	"test_visitors_reach_goals",
	"test_wall_collision",
	"test_avatar_collision",
	"test_sb05_path_choice",
	"test_no_capability_no_platform_path",
	"test_sb05_robot_takes_ramp",
	"test_walker_climbs_stairs",
	"test_robot_blocked_by_steps",
	"test_speed_and_turn_limits",
	"test_camera",
	"test_demo_smoke",
]

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


func _world(body_ids := ["robot_r", "human_walker"]) -> RangeWorld:
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


func test_robot_model() -> String:
	var holder := Node3D.new()
	add_child(holder)
	_node = holder
	var model := RobotRModel.create(1.4)
	holder.add_child(model)
	for part in ["Base", "WheelL", "WheelR", "Torso", "ChestTrim", "BadgeFront", "Neck", "Head", "Visor",
			"EarPodL", "EarPodR", "ShoulderL", "ShoulderR", "ElbowL", "ElbowR", "WristL", "WristR"]:
		if model.find_child(part, true, false) == null:
			return "Robot R model has no part '%s'" % part
	var box := AABB()
	var first := true
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = (mi as MeshInstance3D).global_transform * (mi as MeshInstance3D).get_aabb()
		box = b if first else box.merge(b)
		first = false
	if absf(box.end.y - 1.4) > 0.03 or box.position.y < -0.01:
		return "model spans y %.3f..%.3f, expected 0..1.4 (body config height)" % [box.position.y, box.end.y]
	var half_width := maxf(maxf(absf(box.position.x), absf(box.end.x)), maxf(absf(box.position.z), absf(box.end.z)))
	if half_width > 0.355:
		return "model reaches %.3f m from its center, beyond the 0.35 m body radius" % half_width
	# The visor faces forward (-z), the way the body moves.
	var visor: Node3D = model.find_child("Visor", true, false)
	if visor.global_position.z > -0.05:
		return "visor is not on the front (-z) of the head"
	var model2 := RobotRModel.create(1.7)
	holder.add_child(model2)
	if not is_equal_approx(model2.scale.y, 1.7 / 1.4):
		return "model does not scale to the body height"
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
	var robot := w.spawn_avatar("robot", "robot_r", Vector3(19.0, 0, 11.3), PI)
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
	var r := w.spawn_avatar("robot", "robot_r", Vector3(4.0, 0, 8.0), -PI / 2)
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
	var w := await _world()
	if w == null:
		return "world failed to build"
	var robot_mask := Layers.nav_mask_for(w.bodies["robot_r"])
	var walker_mask := Layers.nav_mask_for(w.bodies["human_walker"])
	var robot_plan := w.query_path(SB05_START, SB05_GOAL, robot_mask)
	var walker_plan := w.query_path(SB05_START, SB05_GOAL, walker_mask)
	if robot_plan["links"] != ["platform_ramp"]:
		return "Robot R's path uses %s, expected only platform_ramp" % [robot_plan["links"]]
	if walker_plan["links"] != ["platform_stairs"]:
		return "walker's path uses %s, expected only platform_stairs (the shorter way)" % [walker_plan["links"]]
	for plan in [robot_plan, walker_plan]:
		var path: PackedVector3Array = plan["path"]
		if path.is_empty() or path[path.size() - 1].distance_to(SB05_GOAL) > 0.3:
			return "a path does not reach the platform goal"
	return ""


func test_no_capability_no_platform_path() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var body: Dictionary = w.bodies["robot_r"].duplicate(true)
	body["capabilities"]["can_use_ramp"] = false
	body["capabilities"]["can_use_stairs"] = false
	var plan := w.query_path(SB05_START, SB05_GOAL, Layers.nav_mask_for(body))
	if not plan["links"].is_empty():
		return "a body with no stairs/ramp capability got a path through %s" % [plan["links"]]
	var path: PackedVector3Array = plan["path"]
	if not path.is_empty() and path[path.size() - 1].y > 0.3:
		return "a body with no stairs/ramp capability got a path onto the platform"
	return ""


func test_sb05_robot_takes_ramp() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var robot := w.spawn_avatar("robot_r", "robot_r", SB05_START, -PI / 2)
	robot.navigate_to(SB05_GOAL)
	var traces := await _run([robot], 60 * 60, _all_idle([robot]))
	if robot.ever_stuck:
		return "Robot R got stuck at %s" % _v(robot.global_position)
	if not robot.last_goal_reached or not _on_platform(w, robot.global_position):
		return "Robot R did not reach the platform goal; it ended at %s" % _v(robot.global_position)
	if robot.links_used != ["platform_ramp"]:
		return "Robot R entered links %s, expected only platform_ramp" % [robot.links_used]
	var stairs := _grow(w.registry["links"]["platform_stairs"]["footprint"], 0.05)
	var ramp: PackedVector2Array = w.registry["links"]["platform_ramp"]["footprint"]
	var on_ramp := 0
	for p in traces["robot_r"]["pos"]:
		if _in_poly(p, stairs):
			return "Robot R entered the stairs footprint at %s" % _v(p)
		if _in_poly(p, ramp) and p.y > 0.1 and p.y < 0.5:
			on_ramp += 1
	if on_ramp < 60:
		return "Robot R spent only %d ticks partway up the ramp" % on_ramp
	return ""


func test_walker_climbs_stairs() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	var walker := w.spawn_avatar("walker", "human_walker", SB05_START, -PI / 2)
	walker.navigate_to(SB05_GOAL)
	var traces := await _run([walker], 60 * 30, _all_idle([walker]))
	if walker.ever_stuck or not walker.last_goal_reached or not _on_platform(w, walker.global_position):
		return "walker did not reach the platform by the stairs; ended at %s" % _v(walker.global_position)
	if walker.links_used != ["platform_stairs"]:
		return "walker entered links %s, expected only platform_stairs" % [walker.links_used]
	var stairs: PackedVector2Array = w.registry["links"]["platform_stairs"]["footprint"]
	var climbing := 0
	for p in traces["walker"]["pos"]:
		if _in_poly(p, stairs) and p.y > 0.1 and p.y < 0.5:
			climbing += 1
	if climbing < 10:
		return "walker was seen partway up the stairs on only %d ticks" % climbing
	return ""


func test_robot_blocked_by_steps() -> String:
	var w := await _world()
	if w == null:
		return "world failed to build"
	# Drive straight at the bottom step (x = 20.5) without navigation.
	# Two lanes inside the 1.5 m wide stairs (z 1.25..2.75): robot at z 1.65, walker at z 2.45.
	var robot := w.spawn_avatar("robot", "robot_r", Vector3(19.2, 0, 1.65), -PI / 2)
	var walker := w.spawn_avatar("walker", "human_walker", Vector3(19.2, 0, 2.45), -PI / 2)
	robot.drive(Vector3(1.0, 0, 0))
	walker.drive(Vector3(1.4, 0, 0))
	var traces := await _run([robot, walker], 60 * 5)
	var robot_max_y := -INF
	var robot_max_x := -INF
	for p in traces["robot"]["pos"]:
		robot_max_y = maxf(robot_max_y, p.y)
		robot_max_x = maxf(robot_max_x, p.x)
	if robot_max_y > 0.05:
		return "Robot R climbed to y = %.3f on the stairs; wheeled bodies must be stopped by the steps" % robot_max_y
	if robot_max_x > 20.5 - 0.35 + 0.03:
		return "Robot R reached x = %.3f, into the first step at 20.5" % robot_max_x
	if robot_max_x < 20.5 - 0.35 - 0.1:
		return "Robot R stopped at x = %.3f, before reaching the stairs" % robot_max_x
	# Control: the same push takes a walker (can_use_stairs) up onto the platform.
	if walker.global_position.y < 0.55:
		return "walker driven the same way did not climb the stairs (y = %.3f)" % walker.global_position.y
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
	var w := await _world(["robot_r", "human_walker"])
	if w == null:
		return "world failed to build"
	var r := w.spawn_avatar("robot_r", "robot_r", Vector3(10, 0, 10), 0.0)
	w.spawn_avatar("visitor_x", "human_walker", Vector3(20, 0, 15), 0.0)
	var rig := CameraRig.new()
	w.add_child(rig)
	rig.set_targets(w.avatar_list())
	if rig.selected_target() != r:
		return "first selected avatar should be robot_r"
	rig.select_next()
	if (rig.selected_target() as Avatar).avatar_id != "visitor_x":
		return "select_next did not move to visitor_x"
	rig.select_next()
	rig.select_prev()
	rig.select_prev()
	if rig.selected_target() != r:
		return "select_prev did not cycle back to robot_r"
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
	if avatars.size() != 4:
		return "expected Robot R and 3 visitors, got %d avatars" % avatars.size()
	var traces := await _run(avatars, 60 * 45, func() -> bool: return main.demo.finished)
	if not main.demo.finished:
		return "demo routes did not finish within 45 s"
	for a in avatars:
		if a.ever_stuck:
			return "%s got stuck" % a.avatar_id
		if not a.last_goal_reached:
			return "%s did not reach its last goal" % a.avatar_id
	var robot: Avatar = main.world.avatars["robot_r"]
	if robot.links_used.has("platform_stairs") or not robot.links_used.has("platform_ramp"):
		return "Robot R used links %s in the demo" % [robot.links_used]
	if not main.world.avatars["visitor_y"].links_used.has("platform_stairs"):
		return "visitor_y should have taken the stairs in the demo"
	for i in avatars.size():
		for j in range(i + 1, avatars.size()):
			var a: Avatar = avatars[i]
			var b: Avatar = avatars[j]
			var pa: Array = traces[a.avatar_id]["pos"]
			var pb: Array = traces[b.avatar_id]["pos"]
			for k in pa.size():
				if Vector2(pa[k].x - pb[k].x, pa[k].z - pb[k].z).length() < a.radius + b.radius + 0.05:
					return "%s and %s came into contact in the demo at tick %d" % [a.avatar_id, b.avatar_id, k]
	if not String(main.hud.status_text()).contains("Sandbox Flats"):
		return "HUD text is missing"
	return ""
