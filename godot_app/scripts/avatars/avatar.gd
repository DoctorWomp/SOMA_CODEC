class_name Avatar
extends CharacterBody3D
## An avatar's body: collider, navigation and movement limits from its body config
## (configs/bodies/*.yaml). Controllers (scripted demo now; agents from G3) only set goals.
## The body enforces its own speed, acceleration and turn rate, whatever asks it to move.
##
## Movement happens only in the fixed physics step (60 Hz). Avatars move along their
## facing direction and turn at a limited rate, turning on the spot when facing away.

signal goal_reached(avatar: Avatar)

enum Mode { IDLE, NAVIGATE, DIRECT, TURN }

const GRAVITY := 9.8
const ARRIVE_DISTANCE_M := 0.25
const STUCK_WINDOW_TICKS := 180
const STUCK_MIN_PROGRESS_M := 0.05
const GESTURE_DURATION_TICKS := 90      # a gesture is visible for 1.5 s
## Local avoidance (D-42): RVO on the world's shared avoidance map, so bodies of every size
## steer around each other even though each size plans paths on its own navigation map.
const AVOID_MARGIN_M := 0.15
const AVOID_NEIGHBOR_DISTANCE_M := 5.0
const AVOID_TIME_HORIZON_S := 2.0

var avatar_id := ""
var body: Dictionary = {}
var kind := ""
var radius := 0.25                   # turning radius: the circle the body sweeps turning on the spot
var nav_radius := 0.25               # turning radius on the navigation grid; selects the navigation map
var footprint := Vector2(0.5, 0.5)   # collider length (along facing) and width, meters
var height := 1.7
var sensor_mount_height := 1.6
var max_speed := 1.0
var max_accel := 1.0
var max_turn_rate := 1.0
var nav_mask := Layers.NAV_FLOOR
var mode: Mode = Mode.IDLE
var goal := Vector3.ZERO
var last_goal_reached := false       # whether the last navigation ended at its goal
var links_used: Array[String] = []   # every nav link entered, in order (e.g. "platform_ramp")
var stuck := false
var ever_stuck := false
var speed := 0.0                     # current forward speed, m/s
var contacts: Dictionary = {}        # other avatar id -> ticks in contact (from physics)
var current_gesture := ""            # last gesture the body accepted (no animation yet)
var refused_gestures: Array[String] = []
var current_expression := ""         # last expression shown (G3a, D-52)
var avoidance_enabled := true
var world: RangeWorld
var nav_agent: NavigationAgent3D
var model: Node3D

var _direct_velocity := Vector3.ZERO
var _turn_yaw := 0.0
var _gesture := {}                   # {"gesture", "event_id", "until_tick"} while one is shown
var _expression := {}                # {"expression_id", "event_id", "until_tick", "glyph_id", "light", ...}
var _last_expression_tick := -1000
var _avoid_rid: RID
var _safe_velocity := Vector3.ZERO
var _has_safe_velocity := false
var _progress_anchor := Vector3.ZERO
var _progress_ticks := 0


func setup(id: String, body_config: Dictionary, appearance := {}) -> void:
	avatar_id = id
	name = id
	body = body_config
	kind = String(body_config["kind"])
	var collider: Dictionary = body_config["dimensions"]["collider"]
	footprint = Vector2(float(collider["length_m"]), float(collider["width_m"]))
	radius = Bodies.turning_radius(body_config)
	nav_radius = Bodies.nav_radius(body_config)
	height = float(body_config["dimensions"]["height_m"])
	sensor_mount_height = float(body_config["sensors"]["mount_height_m"])
	var motion: Dictionary = body_config["motion"]
	max_speed = float(motion["max_speed_m_s"])
	max_accel = float(motion["max_accel_m_s2"])
	max_turn_rate = float(motion["max_turn_rate_rad_s"])
	nav_mask = Layers.nav_mask_for(body_config)

	collision_layer = Layers.AVATARS
	collision_mask = Layers.collision_mask_for(body_config)
	motion_mode = CharacterBody3D.MOTION_MODE_GROUNDED
	floor_max_angle = deg_to_rad(46.0)
	floor_snap_length = 0.3
	floor_constant_speed = true

	var cs := CollisionShape3D.new()
	cs.name = "Collider"
	match String(collider["shape"]):
		"BOX":
			cs.shape = box_collider(footprint, height, Layers.has_capability(body_config, "can_use_stairs"))
		"CYLINDER":
			var cylinder := CylinderShape3D.new()
			cylinder.radius = footprint.y / 2
			cylinder.height = height
			cs.shape = cylinder
		_:
			var capsule := CapsuleShape3D.new()
			capsule.radius = footprint.y / 2
			capsule.height = height
			cs.shape = capsule
	cs.position.y = height / 2
	add_child(cs)

	match kind:
		"LEGGED_HUMANOID":
			model = HumanoidModel.create(height, "LEGS", appearance)
		"WHEELED_HUMANOID":
			model = HumanoidModel.create(height, "WHEELS", appearance)
		"QUADRUPED":
			model = QuadrupedModel.create(footprint.x, int(body_config["arms"]) > 0, appearance)
		_:
			model = VisitorModel.create(footprint.y / 2, height, String(appearance.get("color", "visitor_slate")), id)
	add_child(model)
	if kind != "HUMAN_WALKER" and kind != "SCRIPTED_CROWD":
		RobotParts.name_tag(model, id, height / model.scale.y)

	# Where the observer filter (G2) will cast sight lines from.
	var mount := Marker3D.new()
	mount.name = "SensorMount"
	mount.position = Vector3(0, sensor_mount_height, 0)
	add_child(mount)

	nav_agent = NavigationAgent3D.new()
	nav_agent.name = "NavAgent"
	nav_agent.navigation_layers = nav_mask
	nav_agent.radius = nav_radius
	nav_agent.height = height
	nav_agent.path_desired_distance = 0.4
	nav_agent.target_desired_distance = ARRIVE_DISTANCE_M
	nav_agent.avoidance_enabled = false
	nav_agent.link_reached.connect(_on_link_reached)
	add_child(nav_agent)


## Collider for a BOX body. Bodies that can use stairs step over edges with their legs, so the
## lower front and back edges are bevelled by BEVEL_M and the body glides onto the stairs'
## walking surface. Wheeled boxes stay flat-bottomed, so the real steps stop them (D-37).
const BEVEL_M := 0.10


static func box_collider(size_lw: Vector2, h: float, legged: bool) -> Shape3D:
	if not legged:
		var flat := BoxShape3D.new()
		flat.size = Vector3(size_lw.y, h, size_lw.x)
		return flat
	var half_l := size_lw.x / 2
	var half_w := size_lw.y / 2
	var bevel := minf(BEVEL_M, h / 3)
	var pts := PackedVector3Array()
	for sx in [-half_w, half_w]:
		pts.append_array([
			Vector3(sx, h / 2, -half_l), Vector3(sx, h / 2, half_l),
			Vector3(sx, -h / 2 + bevel, -half_l), Vector3(sx, -h / 2 + bevel, half_l),
			Vector3(sx, -h / 2, -half_l + bevel), Vector3(sx, -h / 2, half_l - bevel)])
	var shape := ConvexPolygonShape3D.new()
	shape.points = pts
	return shape


func attach_navigation(map: RID) -> void:
	nav_agent.set_navigation_map(map)


## Join a world: its journal, events and shared avoidance map.
func attach_world(target_world: RangeWorld) -> void:
	world = target_world
	_avoid_rid = NavigationServer3D.agent_create()
	NavigationServer3D.agent_set_map(_avoid_rid, world.avoidance_map)
	NavigationServer3D.agent_set_use_3d_avoidance(_avoid_rid, false)
	NavigationServer3D.agent_set_radius(_avoid_rid, radius + AVOID_MARGIN_M)
	NavigationServer3D.agent_set_height(_avoid_rid, height)
	NavigationServer3D.agent_set_max_speed(_avoid_rid, max_speed)
	NavigationServer3D.agent_set_neighbor_distance(_avoid_rid, AVOID_NEIGHBOR_DISTANCE_M)
	NavigationServer3D.agent_set_max_neighbors(_avoid_rid, 16)
	NavigationServer3D.agent_set_time_horizon_agents(_avoid_rid, AVOID_TIME_HORIZON_S)
	NavigationServer3D.agent_set_position(_avoid_rid, global_position)
	NavigationServer3D.agent_set_avoidance_callback(_avoid_rid, _on_safe_velocity)
	NavigationServer3D.agent_set_avoidance_enabled(_avoid_rid, true)


func _exit_tree() -> void:
	if _avoid_rid.is_valid():
		NavigationServer3D.free_rid(_avoid_rid)
		_avoid_rid = RID()


func _on_safe_velocity(safe: Vector3) -> void:
	_safe_velocity = Vector3(safe.x, 0, safe.z)
	_has_safe_velocity = true


## Walk to a point using navigation (only links this body's capabilities allow).
func navigate_to(target: Vector3) -> void:
	goal = target
	last_goal_reached = false
	nav_agent.target_position = target
	mode = Mode.NAVIGATE
	_reset_progress()


## Push the body in a direction without navigation. For tests: shows that the host's
## collision and body limits hold even when navigation is bypassed.
func drive(velocity_request: Vector3) -> void:
	_direct_velocity = Vector3(velocity_request.x, 0, velocity_request.z)
	mode = Mode.DIRECT
	_reset_progress()


func stop() -> void:
	mode = Mode.IDLE
	_direct_velocity = Vector3.ZERO


## Turn on the spot to face `yaw` (D-29), at the body's turn rate.
func turn_to(yaw: float) -> void:
	_turn_yaw = wrapf(yaw, -PI, PI)
	mode = Mode.TURN


## Host-side gesture check (D-36): a body only performs gestures its config lists. Returns
## false and records the refusal otherwise. No animation yet (V0 greybox).
func perform_gesture(gesture: String, event_id := "") -> bool:
	if not Bodies.supports_gesture(body, gesture):
		refused_gestures.append(gesture)
		if world != null:
			world.journal_write("GESTURE_REFUSED", avatar_id, {"avatar_id": avatar_id, "gesture": gesture,
				"reason_code": "CAPABILITY_DENIED"})
		return false
	current_gesture = gesture
	if world != null:
		if event_id == "":
			event_id = world.next_event_id()
		_gesture = {"gesture": gesture, "event_id": event_id, "until_tick": world.clock.tick + GESTURE_DURATION_TICKS}
		world.journal_write("GESTURE_PERFORMED", avatar_id, {"avatar_id": avatar_id, "event_id": event_id,
			"gesture": gesture, "duration_ms": SimClock.ms_at(GESTURE_DURATION_TICKS)})
	return true


## The gesture being shown at `tick` ({"gesture", "event_id", ...}), or {} if none.
func active_gesture(tick: int) -> Dictionary:
	if _gesture.is_empty() or tick > int(_gesture["until_tick"]):
		return {}
	return _gesture


## Show an expression from the catalog (EXPRESS; EXPRESSION_PRINCIPLES §1, D-14, D-52): its
## gesture, glyph and light together, or nothing. Returns "OK", "CAPABILITY_DENIED" (the body
## lacks a part) or "RATE_LIMITED" (less than 1/3 s since the last change: light safety, D-14).
## The gesture shares the expression's event id, so observers' reports tie together.
func show_expression(expression: Dictionary, event_id: String) -> String:
	if BeaconRules.refusal(body, expression) != "":
		return "CAPABILITY_DENIED"
	var tick := world.clock.tick if world != null else 0
	if tick - _last_expression_tick < BeaconRules.MIN_CHANGE_TICKS:
		return "RATE_LIMITED"
	if expression.has("gesture") and not perform_gesture(String(expression["gesture"]), event_id):
		return "CAPABILITY_DENIED"
	_last_expression_tick = tick
	current_expression = String(expression["expression_id"])
	var glyph_text := BeaconRules.glyph_text(body, expression)
	_expression = {"expression_id": current_expression, "event_id": event_id,
		"until_tick": tick + int(roundf(float(expression["hold_ms"]) * SimClock.TICK_HZ / 1000.0)),
		"glyph_id": String(expression["glyph"]["glyph_id"]) if expression.has("glyph") else "",
		"glyph_text": glyph_text, "light": String(expression["light"]),
		"light_pattern": String(expression["light_pattern"])}
	var b := beacon()
	if b != null:
		b.show_expression(glyph_text, String(expression["light"]), String(expression["light_pattern"]))
	return "OK"


## The expression being shown at `tick`, or {} if none.
func active_expression(tick: int) -> Dictionary:
	if _expression.is_empty() or tick > int(_expression["until_tick"]):
		return {}
	return _expression


func beacon() -> Beacon:
	if model != null and "beacon" in model:
		return model.beacon
	return null


## Say something out loud (LOCAL speech). Who hears it is decided by the observer filter at the
## next sample (D-40). `addressee_id` may be null. Returns the event id, or "" if this body
## cannot speak.
func say(text: String, addressee_id = null) -> String:
	if world == null or not Layers.has_capability(body, "can_speak"):
		return ""
	return world.emit_speech(self, text, addressee_id, SenseModel.SPEECH_LEVEL_DB)


func supports_gesture(gesture: String) -> bool:
	return Bodies.supports_gesture(body, gesture)


func supports_channel(channel: String) -> bool:
	return Bodies.supports_channel(body, channel)


func horizontal_distance_to(p: Vector3) -> float:
	return Vector2(global_position.x - p.x, global_position.z - p.z).length()


func _physics_process(delta: float) -> void:
	if not _expression.is_empty() and world != null and world.clock.tick > int(_expression["until_tick"]):
		_expression = {}
		var b := beacon()
		if b != null:
			b.clear()
	var dir := Vector3.ZERO
	var wanted_speed := 0.0
	match mode:
		Mode.NAVIGATE:
			if nav_agent.is_navigation_finished():
				_arrive()
			else:
				var next := nav_agent.get_next_path_position()
				var to_next := Vector3(next.x - global_position.x, 0, next.z - global_position.z)
				if to_next.length() > 0.001:
					dir = to_next.normalized()
					var remaining := horizontal_distance_to(goal)
					wanted_speed = minf(max_speed, sqrt(2.0 * max_accel * maxf(remaining - 0.05, 0.0)))
		Mode.TURN:
			if absf(wrapf(_turn_yaw - rotation.y, -PI, PI)) < 0.02:
				mode = Mode.IDLE
			else:
				dir = Vector3(-sin(_turn_yaw), 0, -cos(_turn_yaw))
		Mode.DIRECT:
			if _direct_velocity.length() > 0.001:
				dir = _direct_velocity.normalized()
				wanted_speed = minf(_direct_velocity.length(), max_speed)
	# Avoidance: tell the shared avoidance map where this body wants to go (zero when idle, so
	# others steer around it) and, when navigating, follow the safe velocity it returned for the
	# previous tick. Direct drive bypasses avoidance (tests of raw collision).
	if _avoid_rid.is_valid():
		NavigationServer3D.agent_set_position(_avoid_rid, global_position)
		NavigationServer3D.agent_set_velocity(_avoid_rid, dir * wanted_speed if mode == Mode.NAVIGATE else Vector3.ZERO)
		if avoidance_enabled and mode == Mode.NAVIGATE and _has_safe_velocity and wanted_speed > 0.0:
			if _safe_velocity.length() > 0.001:
				dir = _safe_velocity.normalized()
			wanted_speed = minf(_safe_velocity.length(), wanted_speed)
	_steer(dir, wanted_speed, delta)
	_track_progress()


func _steer(dir: Vector3, wanted_speed: float, delta: float) -> void:
	if dir != Vector3.ZERO:
		var target_yaw := atan2(-dir.x, -dir.z)
		var err := wrapf(target_yaw - rotation.y, -PI, PI)
		var step := max_turn_rate * delta
		rotation.y = wrapf(rotation.y + clampf(err, -step, step), -PI, PI)
		err = wrapf(target_yaw - rotation.y, -PI, PI)
		wanted_speed *= maxf(cos(err), 0.0)
	speed = move_toward(speed, wanted_speed, max_accel * delta)
	var forward := Vector3(-sin(rotation.y), 0, -cos(rotation.y))
	velocity.x = forward.x * speed
	velocity.z = forward.z * speed
	if is_on_floor():
		velocity.y = 0.0
	else:
		velocity.y -= GRAVITY * delta
	move_and_slide()
	for i in get_slide_collision_count():
		var other := get_slide_collision(i).get_collider()
		if other is Avatar:
			var other_id := (other as Avatar).avatar_id
			contacts[other_id] = int(contacts.get(other_id, 0)) + 1
	if model != null and model.has_method("animate"):
		model.animate(speed, delta)


func _arrive() -> void:
	mode = Mode.IDLE
	last_goal_reached = horizontal_distance_to(goal) <= ARRIVE_DISTANCE_M + 0.15 and absf(global_position.y - goal.y) < 0.3
	goal_reached.emit(self)


func _on_link_reached(details: Dictionary) -> void:
	var owner_node = details.get("owner")
	if owner_node is Node:
		links_used.append(String(owner_node.name))


func _reset_progress() -> void:
	_progress_anchor = global_position
	_progress_ticks = 0
	stuck = false


## Flags an avatar that has tried to navigate for 3 s without moving 5 cm.
func _track_progress() -> void:
	if mode != Mode.NAVIGATE:
		_reset_progress()
		return
	_progress_ticks += 1
	if _progress_ticks < STUCK_WINDOW_TICKS:
		return
	var moved := horizontal_distance_to(_progress_anchor)
	if moved < STUCK_MIN_PROGRESS_M and not stuck:
		stuck = true
		ever_stuck = true
		print("STUCK %s at (%.2f, %.2f, %.2f) heading to (%.2f, %.2f, %.2f)" % [
			avatar_id, global_position.x, global_position.y, global_position.z, goal.x, goal.y, goal.z])
	elif moved >= STUCK_MIN_PROGRESS_M:
		stuck = false
	_progress_anchor = global_position
	_progress_ticks = 0
