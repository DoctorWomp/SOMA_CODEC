extends Node3D
## Sandbox Flats (G1): builds the world from configs/maps/sandbox_flats.yaml (via the
## exported JSON, D-30), places Robot R and three visitors, and plays the walk-to-goal demo.
## Press F5 in the Godot editor to run it.

const MAP_ID := "sandbox_flats"

@export var run_demo := true

var world: RangeWorld
var demo: DemoRoutes
var camera_rig: CameraRig
var hud: Hud


func _ready() -> void:
	DisplayServer.window_set_title("SOMA RANGE — Sandbox Flats (G1)")
	Stage.add_lighting(self)
	world = RangeWorld.new()
	add_child(world)
	if not world.build(MAP_ID, DemoRoutes.body_ids()):
		push_error("main: could not build %s; see the errors above" % MAP_ID)
		return
	demo = DemoRoutes.new()
	world.add_child(demo)
	demo.spawn_cast(world)

	camera_rig = CameraRig.new()
	add_child(camera_rig)
	camera_rig.set_targets(world.avatar_list())
	camera_rig.look_from(Vector3(15, 24, 33), Vector3(15, 0, 9))

	hud = Hud.new()
	hud.setup(world, camera_rig, demo)
	add_child(hud)

	await world.wait_navigation_ready()
	if run_demo:
		demo.start()

