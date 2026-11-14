extends Node
## Saves screenshots of the running demo at set simulated times (needs a display; not headless).
##
##   godot --path godot_app --fixed-fps 60 --resolution 1600x900 res://dev/capture.tscn -- --out=<folder>
##
## In a cloud session without a GPU, run it under a virtual display with the Compatibility
## renderer (see docs/BUILD_AND_RUN.md); the owner's PC uses Forward+.

## [file name, simulated seconds, camera mode, camera settings, show HUD]
const SHOTS := [
	["g1_robot_r_closeup.png", 40.0, "orbit", {"target": "robot_r", "yaw_from_front": 0.5, "pitch": -0.12, "distance": 2.6}, false],
	["g1_overview.png", 7.0, "free", {"from": Vector3(15, 16.5, 26.5), "at": Vector3(15, 0, 9.0)}, true],
	["g1_robot_on_ramp.png", 10.0, "free", {"from": Vector3(13.5, 4.0, 13.5), "at": Vector3(21, 0.3, 5)}, true],
	["g1_visitor_on_stairs.png", 16.0, "free", {"from": Vector3(17.0, 3.2, 6.0), "at": Vector3(22.5, 0.4, 1.5)}, true],
	["g1_reflective_wall_pa_chairs.png", 8.5, "free", {"from": Vector3(11, 4.5, 16.5), "at": Vector3(1.5, 1.0, 11.5)}, false],
]

var out_dir := ""


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
	if out_dir == "":
		push_error("capture: pass -- --out=<folder>")
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(out_dir)
	var main: Node = load("res://scenes/main.tscn").instantiate()
	add_child(main)
	while main.demo == null or not main.demo.started():
		await get_tree().process_frame
	var shots := SHOTS.duplicate()
	shots.sort_custom(func(a, b): return a[1] < b[1])
	for shot in shots:
		while main.world.clock.seconds() < shot[1]:
			await get_tree().process_frame
		var rig: CameraRig = main.camera_rig
		var cam: Dictionary = shot[3]
		if shot[2] == "orbit":
			rig.selected = rig.targets.find(main.world.avatars[cam["target"]])
			rig.mode = CameraRig.Mode.ORBIT
			# Orbit yaw relative to the avatar's facing: 0 = straight in front of it.
			rig.orbit_yaw = main.world.avatars[cam["target"]].rotation.y + PI + cam["yaw_from_front"]
			rig.orbit_pitch = cam["pitch"]
			rig.orbit_distance = cam["distance"]
		else:
			rig.look_from(cam["from"], cam["at"])
		main.hud.visible = shot[4]
		get_tree().paused = true
		for i in 3:
			await RenderingServer.frame_post_draw
		var path := out_dir.path_join(shot[0])
		var err := get_viewport().get_texture().get_image().save_png(path)
		print("saved %s at t=%.2f s (%s)" % [path, main.world.clock.seconds(), error_string(err)])
		get_tree().paused = false
	get_tree().quit()
