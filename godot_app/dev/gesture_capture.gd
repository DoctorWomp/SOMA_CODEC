extends Node3D
## Screenshots of rig step A (D-54, D-56): the four robot bodies side by side in every gesture of
## the shared vocabulary, held at the gesture's peak (halfway through its world duration). A body
## that cannot make a gesture stands in its rest pose. Plus a gaze shot and the quadruped sitting.
##
##   godot --path godot_app --fixed-fps 60 --resolution 1600x900 res://dev/gesture_capture.tscn -- --out=<folder>
##
## In a cloud session, run it under a virtual display with the Compatibility renderer
## (docs/BUILD_AND_RUN.md). Rendering proof only: pose never changes what anyone perceives.

## [avatar id, body, x, label]
const CAST := [
	["legged", "legged_humanoid", 10.6, "legged humanoid"],
	["wheeled", "wheeled_humanoid", 12.4, "wheeled humanoid"],
	["quad", "quadruped", 14.4, "quadruped"],
	["quad_arm", "quadruped_arm", 16.5, "quadruped + arm"],
]
const ROW_Z := 16.0
## Turned 50° to their left, so their right side (the gesturing arm) faces the camera.
const YAW := 0.9
const GESTURES := ["WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "NOD", "SHAKE_HEAD", "OPEN_PALM",
	"BOW", "HEAD_TILT", "SIT_IN_PLACE", "HAND_OVER"]

var out_dir := ""
var world: RangeWorld
var caption: Label
var cam: Camera3D


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
	if out_dir == "":
		push_error("gesture_capture: pass -- --out=<folder>")
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(out_dir)
	Stage.add_lighting(self)
	world = RangeWorld.new()
	add_child(world)
	var bodies := []
	for c in CAST:
		bodies.append(c[1])
	bodies.append("human_walker")
	world.build("sandbox_flats", bodies)
	var badge := 0
	for c in CAST:
		badge += 1
		world.spawn_avatar(c[0], c[1], Vector3(c[2], 0, ROW_Z), YAW,
			{"badge": str(badge), "trim": ["robot_trim_green", "robot_trim_teal", "robot_trim_brown"][(badge - 1) % 3], "bands": (badge - 1) % 3 + 1})
	await world.wait_navigation_ready()
	cam = Camera3D.new()
	add_child(cam)
	cam.current = true
	cam.fov = 50
	var layer := CanvasLayer.new()
	add_child(layer)
	caption = Label.new()
	caption.position = Vector2(24, 18)
	caption.add_theme_font_size_override("font_size", 30)
	caption.add_theme_color_override("font_color", Color(0.12, 0.13, 0.16))
	layer.add_child(caption)
	cam.look_at_from_position(Vector3(13.2, 1.45, 11.0), Vector3(13.2, 0.85, ROW_Z), Vector3.UP)
	for gesture in GESTURES:
		await _shot(gesture)
	await _gaze_shot()
	get_tree().quit()


## Every body that can, makes `gesture`; the world holds at the peak and the frame is saved.
func _shot(gesture: String) -> void:
	await _ticks(10)
	var peak := -1
	var who: PackedStringArray = []
	var cannot: PackedStringArray = []
	for c in CAST:
		var a: Avatar = world.avatars[c[0]]
		if a.supports_gesture(gesture):
			a.perform_gesture(gesture)
			var g := a.active_gesture(world.clock.tick)
			peak = int(g["start_tick"]) + roundi((int(g["until_tick"]) - int(g["start_tick"])) / 2.0)
			who.append(String(c[3]))
		else:
			cannot.append(String(c[3]))
	while world.clock.tick < peak:
		await get_tree().physics_frame
	world.hold("capture")
	caption.text = "%s  ·  peak of the gesture (tick %d)%s" % [gesture, world.clock.tick,
		("   ·   cannot: " + ", ".join(cannot)) if not cannot.is_empty() else ""]
	await _save("gesture_%s.png" % gesture.to_lower())
	world.release("capture")
	# Let the gesture finish before the next one.
	var done := peak + 120
	while world.clock.tick < done:
		await get_tree().physics_frame


## Gaze: every robot looks at a visitor off to its left.
func _gaze_shot() -> void:
	var visitor := world.spawn_avatar("visitor", "human_walker", Vector3(9.3, 0, 13.9), -PI / 2)
	for c in CAST:
		(world.avatars[c[0]] as Avatar).look_toward(visitor.avatar_id, 600)
	await _ticks(90)
	world.hold("capture")
	caption.text = "Gaze: every robot turns its head toward the visitor (head yaw at most ±85°)"
	cam.fov = 54
	cam.look_at_from_position(Vector3(12.6, 2.3, 9.8), Vector3(12.4, 0.8, 15.4), Vector3.UP)
	await _save("gaze_toward_visitor.png")
	world.release("capture")


func _save(file: String) -> void:
	for i in 4:
		await RenderingServer.frame_post_draw
	var path := out_dir.path_join(file)
	var err := get_viewport().get_texture().get_image().save_png(path)
	print("saved %s (%s)" % [path, error_string(err)])


func _ticks(n: int) -> void:
	for i in n:
		await get_tree().physics_frame
