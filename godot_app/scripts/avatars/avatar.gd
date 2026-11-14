class_name Avatar
extends CharacterBody3D
## An avatar's body: collider, navigation and movement limits from its body config
## (configs/bodies/*.yaml). Controllers (scripted demo now; agents from G3) only set goals.
## The body enforces its own speed, acceleration and turn rate, whatever asks it to move.
##
## Movement happens only in the fixed physics step (60 Hz). Avatars move along their
## facing direction and turn at a limited rate, turning on the spot when facing away.

signal goal_reached(avatar: Avatar)

enum Mode { IDLE, NAVIGATE, DIRECT }

const GRAVITY := 9.8
const ARRIVE_DISTANCE_M := 0.25
const STUCK_WINDOW_TICKS := 180
const STUCK_MIN_PROGRESS_M := 0.05

var avatar_id := ""
var body: Dictionary = {}
var kind := ""
var radius := 0.25
var height := 1.7
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
var nav_agent: NavigationAgent3D
var model: Node3D

var _direct_velocity := Vector3.ZERO
var _progress_anchor := Vector3.ZERO
var _progress_ticks := 0


func setup(id: String, body_config: Dictionary, appearance := {}) -> void:
	avatar_id = id
	name = id
	body = body_config
	kind = String(body_config["kind"])
	radius = float(body_config["dimensions"]["radius_m"])
	height = float(body_config["dimensions"]["height_m"])
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
	if kind == "WHEELED_ROBOT":
		var cylinder := CylinderShape3D.new()
		cylinder.radius = radius
		cylinder.height = height
		cs.shape = cylinder
	else:
		var capsule := CapsuleShape3D.new()
		capsule.radius = radius
		capsule.height = height
		cs.shape = capsule
	cs.position.y = height / 2
	add_child(cs)

	if kind == "WHEELED_ROBOT":
		model = RobotRModel.create(height, String(appearance.get("badge", "R")))
	else:
		model = VisitorModel.create(radius, height, String(appearance.get("color", "visitor_slate")), id)
	add_child(model)

	nav_agent = NavigationAgent3D.new()
	nav_agent.name = "NavAgent"
	nav_agent.navigation_layers = nav_mask
	nav_agent.radius = radius
	nav_agent.height = height
	nav_agent.path_desired_distance = 0.4
	nav_agent.target_desired_distance = ARRIVE_DISTANCE_M
	nav_agent.avoidance_enabled = false
	nav_agent.link_reached.connect(_on_link_reached)
	add_child(nav_agent)


func attach_navigation(map: RID) -> void:
	nav_agent.set_navigation_map(map)


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


func horizontal_distance_to(p: Vector3) -> float:
	return Vector2(global_position.x - p.x, global_position.z - p.z).length()


func _physics_process(delta: float) -> void:
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
		Mode.DIRECT:
			if _direct_velocity.length() > 0.001:
				dir = _direct_velocity.normalized()
				wanted_speed = minf(_direct_velocity.length(), max_speed)
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
