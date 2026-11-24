class_name CameraRig
extends Node3D
## Spectator cameras (Blueprint §7.1, §7.4; G4a T06). It never creates an in-world body.
##
## FREE:   W/A/S/D move, Q/E down/up, Shift faster, hold right mouse to look, wheel = speed.
## ORBIT:  around the selected avatar; hold right mouse to orbit, wheel to zoom.
## FOLLOW: behind the selected avatar, along its heading (third person); wheel to zoom.
## POV:    the selected avatar's own point of view: its sensor point, facing where its head faces
##         (D-72). What it *could* see; the Sensor view (F2) shows what its senses actually received.
## C cycles the modes the seat may use, [ and ] select the previous / next avatar.
##
## Orbit and follow keep the camera out of walls like a SpringArm3D: a ray from the avatar to the
## camera stops it short of the first wall it hits. Every mode and selection is asked of the world
## dispatcher (D-90) when one is set: a participant (G4c) gets only its own avatar's follow and POV.

enum Mode { FREE, ORBIT, FOLLOW, POV }

const MODE_CAPABILITY := {Mode.FREE: "CAMERA_FREE", Mode.ORBIT: "CAMERA_ORBIT", Mode.FOLLOW: "CAMERA_FOLLOW",
	Mode.POV: "CAMERA_POV"}
const FOLLOW_HEIGHT := 1.6
const FOLLOW_PITCH := -0.25
const CLIP_MARGIN := 0.2

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
var follow_distance := 4.0
var dispatcher: WorldDispatcher        # the seat's permissions (D-90); null = no checks (G1 tests)
var clipped := false                   # the last orbit/follow placement was pulled in by a wall
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
	_select_step(1)


func select_prev() -> void:
	_select_step(-1)


func _select_step(direction: int) -> void:
	for i in targets.size():
		var candidate := (selected + direction * (i + 1) + targets.size() * 4) % targets.size()
		if _allowed("SELECT_AVATAR", candidate):
			selected = candidate
			if not _allowed(MODE_CAPABILITY[mode], selected):
				mode = Mode.FREE
			return


## Select an avatar by id (launch option, tests). False if unknown or not allowed for the seat.
func select_avatar(avatar_id: String) -> bool:
	for i in targets.size():
		if (targets[i] as Avatar).avatar_id == avatar_id and _allowed("SELECT_AVATAR", i):
			selected = i
			return true
	return false


func selected_id() -> String:
	var t := selected_target()
	return (t as Avatar).avatar_id if t is Avatar else ""


func _allowed(capability: String, index := -1) -> bool:
	if dispatcher == null:
		return true
	var target := ""
	if index >= 0 and index < targets.size() and targets[index] is Avatar:
		target = (targets[index] as Avatar).avatar_id
	return dispatcher.seat_request(capability, target)["code"] == "OK"


## Switch to `new_mode` if the seat may use it for the selected avatar. Returns whether it did.
func set_mode(new_mode: Mode) -> bool:
	if new_mode != Mode.FREE and selected_target() == null:
		return false
	if not _allowed(MODE_CAPABILITY[new_mode], selected):
		return false
	if mode != Mode.FREE and new_mode == Mode.FREE and camera != null:
		free_position = camera.global_position
		free_yaw = camera.global_rotation.y
		free_pitch = clampf(camera.global_rotation.x, -1.5, 1.5)
	mode = new_mode
	_apply()
	return true


## C: the next mode the seat may use (FREE → ORBIT → FOLLOW → POV → FREE).
func cycle_mode() -> void:
	for i in range(1, 5):
		if set_mode(((int(mode) + i) % 4) as Mode):
			return


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
		var view_basis := Basis.from_euler(Vector3(free_pitch, free_yaw, 0))
		var world_move := view_basis * Vector3(move.x, 0, move.z) + Vector3.UP * move.y
		var speed := free_speed * (FAST_FACTOR if Input.is_action_pressed("cam_fast") else 1.0)
		free_position += world_move * speed * delta
	_apply()


func _apply() -> void:
	if camera == null:
		return
	var t := selected_target()
	clipped = false
	if mode == Mode.ORBIT and t != null:
		var focus := t.global_position + Vector3.UP * ORBIT_FOCUS_HEIGHT
		var view_basis := Basis.from_euler(Vector3(orbit_pitch, orbit_yaw, 0))
		global_transform = Transform3D(view_basis, _clip(focus, focus + view_basis.z * orbit_distance))
	elif mode == Mode.FOLLOW and t != null:
		var focus := t.global_position + Vector3.UP * ORBIT_FOCUS_HEIGHT
		var view_basis := Basis.from_euler(Vector3(FOLLOW_PITCH, t.rotation.y, 0))
		var want := t.global_position + Vector3.UP * FOLLOW_HEIGHT + view_basis.z * follow_distance
		var at := _clip(focus, want)
		if (focus - at).length() > 0.01:
			global_transform = Transform3D(Basis.looking_at(focus - at, Vector3.UP), at)
		else:
			global_transform = Transform3D(view_basis, at)
	elif mode == Mode.POV and t is Avatar:
		var a := t as Avatar
		var dir := SenseModel.head_forward_of(a)
		var view_basis := Basis.from_euler(Vector3(a.head_pitch, atan2(-dir.x, -dir.z), 0))
		global_transform = Transform3D(view_basis, SenseModel.sensor_origin(a))
	else:
		global_transform = Transform3D(Basis.from_euler(Vector3(free_pitch, free_yaw, 0)), free_position)


## Like a SpringArm3D: stop the camera short of the first wall between the avatar and `want`.
func _clip(from: Vector3, want: Vector3) -> Vector3:
	if not is_inside_tree() or get_world_3d() == null:
		return want
	var q := PhysicsRayQueryParameters3D.create(from, want, Layers.WORLD)
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return want
	clipped = true
	var p: Vector3 = hit["position"]
	return p + (from - p).normalized() * CLIP_MARGIN


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
			elif mode == Mode.FOLLOW:
				follow_distance = clampf(follow_distance * (0.9 if closer else 1.1), MIN_ORBIT_DISTANCE, 20.0)
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
		cycle_mode()
	elif event.is_action_pressed("select_next"):
		select_next()
	elif event.is_action_pressed("select_prev"):
		select_prev()
