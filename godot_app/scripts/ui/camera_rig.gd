class_name CameraRig
extends Node3D
## Spectator camera, basic version (Blueprint §7.1, §7.4). It never creates an in-world body.
##
## FREE:  W/A/S/D move, Q/E down/up, Shift faster, hold right mouse to look, wheel = speed.
## ORBIT: follows the selected avatar; hold right mouse to orbit, wheel to zoom.
## C switches mode, [ and ] select the previous / next avatar.

enum Mode { FREE, ORBIT }

const FREE_SPEED := 8.0
const FAST_FACTOR := 3.0
const MOUSE_SENSITIVITY := 0.004
const ORBIT_FOCUS_HEIGHT := 1.0
const MIN_ORBIT_DISTANCE := 1.5
const MAX_ORBIT_DISTANCE := 60.0

var mode: Mode = Mode.FREE
var camera: Camera3D
var targets: Array = []
var selected := 0
var free_position := Vector3(15, 24, 34)
var free_yaw := 0.0
var free_pitch := -0.75
var free_speed := FREE_SPEED
var orbit_yaw := 0.5
var orbit_pitch := -0.4
var orbit_distance := 5.0
var _looking := false


func _init() -> void:
	name = "CameraRig"
	process_mode = Node.PROCESS_MODE_ALWAYS


func _ready() -> void:
	camera = Camera3D.new()
	camera.name = "Camera"
	camera.fov = 60.0
	camera.near = 0.05
	camera.far = 400.0
	add_child(camera)
	camera.current = true
	_apply()


func set_targets(list: Array) -> void:
	targets = list
	selected = clampi(selected, 0, maxi(targets.size() - 1, 0))


func selected_target() -> Node3D:
	if targets.is_empty():
		return null
	return targets[selected]


func select_next() -> void:
	if not targets.is_empty():
		selected = (selected + 1) % targets.size()


func select_prev() -> void:
	if not targets.is_empty():
		selected = (selected - 1 + targets.size()) % targets.size()


func toggle_mode() -> void:
	if mode == Mode.ORBIT:
		# Continue flying from where the orbit view is.
		free_position = camera.global_position
		free_yaw = orbit_yaw
		free_pitch = orbit_pitch
		mode = Mode.FREE
	elif selected_target() != null:
		mode = Mode.ORBIT


## Point the free camera at a spot from a given position.
func look_from(from: Vector3, at: Vector3) -> void:
	var d := (at - from).normalized()
	free_position = from
	free_yaw = atan2(-d.x, -d.z)
	free_pitch = asin(clampf(d.y, -1.0, 1.0))
	mode = Mode.FREE
	_apply()


func _process(delta: float) -> void:
	if mode == Mode.FREE:
		var move := Vector3(
			Input.get_axis("cam_left", "cam_right"),
			Input.get_axis("cam_down", "cam_up"),
			Input.get_axis("cam_forward", "cam_back"))
		var basis := Basis.from_euler(Vector3(free_pitch, free_yaw, 0))
		var world_move := basis * Vector3(move.x, 0, move.z) + Vector3.UP * move.y
		var speed := free_speed * (FAST_FACTOR if Input.is_action_pressed("cam_fast") else 1.0)
		free_position += world_move * speed * delta
	_apply()


func _apply() -> void:
	if camera == null:
		return
	if mode == Mode.ORBIT and selected_target() != null:
		var focus := selected_target().global_position + Vector3.UP * ORBIT_FOCUS_HEIGHT
		var basis := Basis.from_euler(Vector3(orbit_pitch, orbit_yaw, 0))
		global_transform = Transform3D(basis, focus + basis.z * orbit_distance)
	else:
		global_transform = Transform3D(Basis.from_euler(Vector3(free_pitch, free_yaw, 0)), free_position)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			_looking = mb.pressed
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _looking else Input.MOUSE_MODE_VISIBLE
		elif mb.pressed and mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var closer := mb.button_index == MOUSE_BUTTON_WHEEL_UP
			if mode == Mode.ORBIT:
				orbit_distance = clampf(orbit_distance * (0.9 if closer else 1.1), MIN_ORBIT_DISTANCE, MAX_ORBIT_DISTANCE)
			else:
				free_speed = clampf(free_speed * (1.2 if closer else 1 / 1.2), 1.0, 60.0)
	elif event is InputEventMouseMotion and _looking:
		var rel := (event as InputEventMouseMotion).relative
		if mode == Mode.ORBIT:
			orbit_yaw -= rel.x * MOUSE_SENSITIVITY
			orbit_pitch = clampf(orbit_pitch - rel.y * MOUSE_SENSITIVITY, -1.45, 0.3)
		else:
			free_yaw -= rel.x * MOUSE_SENSITIVITY
			free_pitch = clampf(free_pitch - rel.y * MOUSE_SENSITIVITY, -1.5, 1.5)
	elif event.is_action_pressed("cam_toggle_mode"):
		toggle_mode()
	elif event.is_action_pressed("select_next"):
		select_next()
	elif event.is_action_pressed("select_prev"):
		select_prev()
