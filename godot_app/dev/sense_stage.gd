extends Node3D
## Staged scene used by dev/capture.gd for the senses screenshots (see capture.gd STAGE).

var world: RangeWorld
var camera_rig: CameraRig
var hud: Hud
var sense_view: SenseView


func _ready() -> void:
	Stage.add_lighting(self)
	world = RangeWorld.new()
	add_child(world)
	world.build("sandbox_flats", ["legged_humanoid", "quadruped", "human_walker"])
	var capture_script: GDScript = load("res://dev/capture.gd")
	for row in capture_script.STAGE:
		world.spawn_avatar(row[0], row[1], Vector3(float(row[2]), 0, float(row[3])), float(row[4]))
	camera_rig = CameraRig.new()
	add_child(camera_rig)
	camera_rig.set_targets(world.avatar_list())
	hud = Hud.new()
	hud.setup(world, camera_rig, null)
	add_child(hud)
	sense_view = SenseView.new()
	sense_view.setup(world, camera_rig)
	add_child(sense_view)
