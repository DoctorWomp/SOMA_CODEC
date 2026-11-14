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
	_add_lighting()
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


## V0 lighting: one directional light without shadows plus flat ambient light (ART_DIRECTION §3, §7).
func _add_lighting() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Palette.color("background")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 0.55
	var we := WorldEnvironment.new()
	we.name = "Environment"
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation = Vector3(deg_to_rad(-55), deg_to_rad(-35), 0)
	sun.light_energy = 0.9
	sun.shadow_enabled = false
	add_child(sun)
