extends Node3D
## Screenshots of the Beacon (G3a, D-52): each robot body showing expressions from the catalog.
##
##   godot --path godot_app --fixed-fps 60 --resolution 1600x900 res://dev/beacon_capture.tscn -- --out=<folder>
##
## In a cloud session, run it under a virtual display with the Compatibility renderer
## (docs/BUILD_AND_RUN.md). Rendering proof only: what agents perceive comes from the observer filter.

## [avatar id, body, x, z, expression]
const CAST := [
	["legged", "legged_humanoid", 13.6, 16.0, "stop"],
	["wheeled", "wheeled_humanoid", 15.0, 16.0, "listening"],
	["quad", "quadruped", 16.6, 16.0, "greeting_light"],
	["quad_arm", "quadruped_arm", 18.4, 16.0, "waiting"],
]
## [file, camera from, camera at]
const SHOTS := [
	["beacon_lineup.png", Vector3(16.0, 1.45, 12.2), Vector3(16.0, 0.85, 16.0)],
	["beacon_humanoid_visor.png", Vector3(14.3, 1.45, 14.6), Vector3(14.3, 1.30, 16.0)],
	["beacon_quadruped_strip.png", Vector3(16.75, 0.75, 14.75), Vector3(16.65, 0.55, 15.6)],
]

var out_dir := ""


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
	if out_dir == "":
		push_error("beacon_capture: pass -- --out=<folder>")
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(out_dir)
	Stage.add_lighting(self)
	var world := RangeWorld.new()
	add_child(world)
	var bodies := []
	for c in CAST:
		bodies.append(c[1])
	world.build("sandbox_flats", bodies)
	var badge := 0
	for c in CAST:
		badge += 1
		world.spawn_avatar(c[0], c[1], Vector3(c[2], 0, c[3]), 0.0,
			{"badge": str(badge), "trim": ["robot_trim_green", "robot_trim_teal", "robot_trim_brown"][(badge - 1) % 3], "bands": (badge - 1) % 3 + 1})
	await world.wait_navigation_ready()
	for c in CAST:
		var result := world.comms.send_expression(world.avatars[c[0]], String(c[4]))
		print("%s shows %s: %s" % [c[0], c[4], result["reason_code"]])
	var cam := Camera3D.new()
	add_child(cam)
	cam.current = true
	cam.fov = 50
	for shot in SHOTS:
		cam.look_at_from_position(shot[1], shot[2], Vector3.UP)
		for i in 4:
			await RenderingServer.frame_post_draw
		var path := out_dir.path_join(shot[0])
		var err := get_viewport().get_texture().get_image().save_png(path)
		print("saved %s (%s)" % [path, error_string(err)])
	get_tree().quit()
