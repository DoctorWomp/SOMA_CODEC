extends Node3D
## Sandbox Flats (G1): builds the world from configs/maps/sandbox_flats.yaml (via the
## exported JSON, D-30), places Robot R and three visitors, and plays the walk-to-goal demo.
## Press F5 in the Godot editor to run it.

const MAP_ID := "sandbox_flats"

@export var run_demo := true
## Where to write the event journal: "auto" = a new file in user://journals (the newest 10 are
## kept), "" = no journal, anything else = that file path.
@export var journal_path := "auto"
@export var run_seed := 1

var world: RangeWorld
var demo: DemoRoutes
var camera_rig: CameraRig
var hud: Hud
var sense_view: SenseView
var link: LinkClient


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

	sense_view = SenseView.new()
	sense_view.setup(world, camera_rig)
	add_child(sense_view)

	var path := journal_path
	if path == "auto":
		path = Journal.new_default_path("run_" + Time.get_datetime_string_from_system().replace(":", "-"))
	world.start_run(run_seed, path)
	_start_link_if_asked()

	await world.wait_navigation_ready()
	if run_demo:
		demo.start()


## The Python link starts only when asked on the command line (tools/run_link_demo.py does
## this): "-- --link-port=PORT --link-agents=robot_legged,robot_quadruped". The session token
## comes from the RANGE_SESSION_TOKEN environment variable, never the command line.
func _start_link_if_asked() -> void:
	var link_port := 0
	var agents: Array = []
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--link-port="):
			link_port = int(arg.trim_prefix("--link-port="))
		elif arg.begins_with("--link-agents="):
			agents = Array(arg.trim_prefix("--link-agents=").split(",", false))
	if link_port <= 0 or agents.is_empty():
		return
	link = LinkClient.new()
	add_child(link)
	link.setup(world, link_port, agents)
	hud.link = link
