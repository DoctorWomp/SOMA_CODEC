extends Node
## Saves screenshots of the robot lineup and the running demo (needs a display; not headless).
##
##   godot --path godot_app --fixed-fps 60 --resolution 1600x900 res://dev/capture.tscn -- --out=<folder>
##
## In a cloud session without a GPU, run it under a virtual display with the Compatibility
## renderer (see docs/BUILD_AND_RUN.md); the owner's PC uses Forward+.

const SCENES := {
	"lineup": "res://scenes/robot_lineup.tscn",
	"demo": "res://scenes/main.tscn",
	"senses": "",
}

## Staged avatars for the "senses" shots: [id, body, x, z, yaw].
const STAGE := [
	["visitor", "human_walker", 4.5, 3.2, PI],
	["quad", "quadruped", 5.6, 7.4, 0.0],
	["humanoid", "legged_humanoid", 3.4, 7.4, 0.0],
	["observer", "legged_humanoid", 13.0, 12.05, PI / 2],
	["half_hidden", "human_walker", 8.5, 12.05, -PI / 2],
	["past_the_end", "human_walker", 8.5, 13.4, -PI / 2],
]

## [file name, scene, simulated seconds, camera mode, camera settings, show HUD]
## Orbit "yaw_from_front" is relative to the avatar's facing: 0 = straight in front of it.
const SHOTS := [
	["bodies_lineup.png", "lineup", 0.2, "free", {"from": Vector3(6.3, 1.9, 15.6), "at": Vector3(6.3, 0.75, 9.0)}, false],
	["body_legged_humanoid.png", "lineup", 0.2, "orbit", {"target": "robot_legged", "yaw_from_front": 0.45, "pitch": -0.1, "distance": 2.9}, false],
	["body_wheeled_humanoid.png", "lineup", 0.2, "orbit", {"target": "robot_wheeled", "yaw_from_front": 0.45, "pitch": -0.12, "distance": 2.6}, false],
	["body_quadruped.png", "lineup", 0.2, "orbit", {"target": "robot_quadruped", "yaw_from_front": 0.7, "pitch": -0.3, "distance": 2.3}, false],
	["body_quadruped_arm.png", "lineup", 0.2, "orbit", {"target": "robot_quadruped_arm", "yaw_from_front": -0.75, "pitch": -0.3, "distance": 2.3}, false],
	["demo_overview.png", "demo", 7.0, "free", {"from": Vector3(15, 16.5, 26.5), "at": Vector3(15, 0, 9.0)}, true],
	["sb05_ramp_and_stairs.png", "demo", 7.1, "free", {"from": Vector3(15.5, 3.6, 12.5), "at": Vector3(20.5, 0.4, 4.0)}, true],
	["sb05_all_on_platform.png", "demo", 20.0, "free", {"from": Vector3(21.0, 3.2, 11.5), "at": Vector3(26.0, 0.6, 4.2)}, false],
	["reflective_wall_pa_chairs.png", "demo", 8.5, "free", {"from": Vector3(11, 4.5, 16.5), "at": Vector3(1.5, 1.0, 11.5)}, false],
	["senses_demo_heard_and_seen.png", "demo", 18.4, "free", {"from": Vector3(19.5, 5.5, 10.5), "at": Vector3(24.5, 0.6, 3.5), "senses": "robot_legged"}, true],
	["senses_divider_quadruped.png", "senses", 0.3, "free", {"from": Vector3(8.6, 3.2, 10.6), "at": Vector3(4.6, 0.6, 5.0), "senses": "quad"}, false],
	["senses_divider_humanoid.png", "senses", 0.3, "free", {"from": Vector3(8.6, 3.2, 10.6), "at": Vector3(4.6, 0.6, 5.0), "senses": "humanoid"}, false],
	["senses_partly_seen.png", "senses", 0.3, "free", {"from": Vector3(14.5, 4.2, 16.5), "at": Vector3(9.5, 0.8, 11.5), "senses": "observer"}, false],
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
	for scene_key in SCENES:
		await _capture_scene(scene_key)
	get_tree().quit()


func _capture_scene(scene_key: String) -> void:
	var scene: Node = _stage() if SCENES[scene_key] == "" else load(SCENES[scene_key]).instantiate()
	if scene_key == "demo":
		scene.journal_path = ""
	add_child(scene)
	if scene_key == "demo":
		while scene.demo == null or not scene.demo.started():
			await get_tree().process_frame
	else:
		for i in 3:
			await get_tree().process_frame
	var shots := []
	for shot in SHOTS:
		if shot[1] == scene_key:
			shots.append(shot)
	shots.sort_custom(func(a: Array, b: Array) -> bool: return a[2] < b[2])
	for shot in shots:
		while scene.world.clock.seconds() < shot[2]:
			await get_tree().process_frame
		var rig: CameraRig = scene.camera_rig
		var cam: Dictionary = shot[4]
		if shot[3] == "orbit":
			var target: Avatar = scene.world.avatars[cam["target"]]
			rig.selected = rig.targets.find(target)
			rig.mode = CameraRig.Mode.ORBIT
			rig.orbit_yaw = target.rotation.y + PI + float(cam["yaw_from_front"])
			rig.orbit_pitch = cam["pitch"]
			rig.orbit_distance = cam["distance"]
		else:
			rig.look_from(cam["from"], cam["at"])
		scene.hud.visible = shot[5]
		if cam.has("senses"):
			var watched: Avatar = scene.world.avatars[cam["senses"]]
			rig.selected = rig.targets.find(watched)
			scene.sense_view.visible = true
			scene.world.senses.latest[watched.avatar_id] = scene.world.senses.observe(watched)
		elif scene.get("sense_view") != null:
			scene.sense_view.visible = false
		get_tree().paused = true
		for i in 3:
			await RenderingServer.frame_post_draw
		var path := out_dir.path_join(shot[0])
		var err := get_viewport().get_texture().get_image().save_png(path)
		print("saved %s at t=%.2f s (%s)" % [path, scene.world.clock.seconds(), error_string(err)])
		get_tree().paused = false
	scene.queue_free()
	await get_tree().process_frame


## A small staged scene for the senses shots: the low divider and the partition-end cases.
func _stage() -> Node3D:
	var root := Node3D.new()
	root.set_script(load("res://dev/sense_stage.gd"))
	return root
