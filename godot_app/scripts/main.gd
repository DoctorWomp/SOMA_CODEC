extends Node3D
## Sandbox Flats (G1): builds the world from configs/maps/sandbox_flats.yaml (via the
## exported JSON, D-30), places Robot R and three visitors, and plays the walk-to-goal demo.
## Press F5 in the Godot editor to run it.
##
## Scenario mode (G3a, D-48), used by tools/run_scenario.py:
##   -- --scenario=SB04_POLITE_BID [--run-mode=STEPPED|LIVE] [--seed=N] [--journal=PATH]
##      [--bodies=robot_r:quadruped,...] [--link-port=PORT --link-agents=a,b] [--quit-when-done]
##
## Either mode: -- --no-pose keeps every robot in its rest pose (D-54: posing is presentation and
## the journal is the same with it on or off). -- --frame-stats=PATH writes frame pacing and
## Godot's video-memory peak to PATH when the scenario ends (G3d, D-69; never in the journal).

const MAP_ID := "sandbox_flats"

@export var run_demo := true
## Where to write the event journal: "auto" = a new file in user://journals (the newest 10 are
## kept), "" = no journal, anything else = that file path.
@export var journal_path := "auto"
@export var run_seed := 1
## Scenario mode: the scenario to run instead of the demo (empty = the demo).
@export var scenario_id := ""
@export var run_mode := "LIVE"
@export var quit_when_done := false
## Scenario mode: {avatar_id: body_id} overrides, e.g. Robot R played by the quadruped.
@export var body_overrides := {}
## Scenario mode without --link-port (tests): connect to this port when above 0.
@export var link_port := 0
## Skeleton poses (gestures, gaze, wheels; D-54). Off with -- --no-pose.
@export var posing := true

var world: RangeWorld
var demo: DemoRoutes
var camera_rig: CameraRig
var hud: Hud
var sense_view: SenseView
var link: LinkClient
var scenario_player: ScenarioPlayer
var frame_stats: FrameStats
var frame_stats_path := ""
var _seed_given := false


func _ready() -> void:
	_read_args()
	Stage.add_lighting(self)
	if scenario_id != "":
		_run_scenario()
		return
	DisplayServer.window_set_title("SOMA RANGE — Sandbox Flats (G1)")
	world = RangeWorld.new()
	world.posing_enabled = posing
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


func _read_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--scenario="):
			scenario_id = arg.trim_prefix("--scenario=")
		elif arg.begins_with("--run-mode="):
			run_mode = arg.trim_prefix("--run-mode=").to_upper()
		elif arg.begins_with("--seed="):
			run_seed = int(arg.trim_prefix("--seed="))
			_seed_given = true
		elif arg.begins_with("--journal="):
			journal_path = arg.trim_prefix("--journal=")
		elif arg.begins_with("--bodies="):
			for pair in arg.trim_prefix("--bodies=").split(",", false):
				var parts := pair.split(":")
				if parts.size() == 2:
					body_overrides[parts[0]] = parts[1]
		elif arg == "--quit-when-done":
			quit_when_done = true
		elif arg == "--no-pose":
			posing = false
		elif arg.begins_with("--frame-stats="):
			frame_stats_path = arg.trim_prefix("--frame-stats=")


## Scenario mode: build the scenario's world and cast, link the agents, play the tape, end the run.
func _run_scenario() -> void:
	var scen := WorldData.load_scenario(scenario_id)
	if scen.is_empty():
		_fail("main: unknown scenario '%s'" % scenario_id)
		return
	if run_mode != "LIVE" and run_mode != "STEPPED":
		_fail("main: run mode must be LIVE or STEPPED, not '%s'" % run_mode)
		return
	DisplayServer.window_set_title("SOMA RANGE — %s (%s)" % [scenario_id, run_mode.to_lower()])
	if frame_stats_path != "":
		frame_stats = FrameStats.new()
		add_child(frame_stats)
	world = RangeWorld.new()
	world.posing_enabled = posing
	add_child(world)
	world.sensing_enabled = false
	if not world.build(String(scen["map"]), ScenarioPlayer.body_ids(scen, body_overrides)):
		_fail("main: could not build the world for %s" % scenario_id)
		return
	scenario_player = ScenarioPlayer.new()
	scenario_player.run_seed = run_seed if _seed_given else int(scen["default_seed"])
	scenario_player.journal_path = journal_path
	if journal_path == "auto":
		scenario_player.journal_path = Journal.new_default_path("%s_%s" % [scenario_id, Time.get_datetime_string_from_system().replace(":", "-")])
	if not scenario_player.setup(world, scen, body_overrides):
		_fail("main: could not place the cast of %s" % scenario_id)
		return
	world.add_child(scenario_player)
	camera_rig = CameraRig.new()
	add_child(camera_rig)
	camera_rig.set_targets(world.avatar_list())
	camera_rig.look_from(Vector3(15, 24, 33), Vector3(15, 0, 9))
	hud = Hud.new()
	hud.setup(world, camera_rig, null)
	add_child(hud)
	sense_view = SenseView.new()
	sense_view.setup(world, camera_rig)
	add_child(sense_view)
	_start_link_if_asked()
	if link == null and link_port > 0:
		var cast: Array = scen["cast"].keys()
		cast.sort()
		link = LinkClient.new()
		add_child(link)
		link.setup(world, link_port, cast, "", run_mode)
		hud.link = link
	scenario_player.link = link
	scenario_player.finished_run.connect(_on_scenario_finished)


func _on_scenario_finished() -> void:
	var digest := world.end_run()
	print("SCENARIO DONE %s ticks=%d held=%d journal_sha256=%s" % [scenario_id, world.clock.tick, world.held_samples, digest])
	if frame_stats != null:
		frame_stats.write(frame_stats_path)
	if quit_when_done:
		get_tree().quit(0)


func _fail(message: String) -> void:
	push_error(message)
	if quit_when_done:
		get_tree().quit(2)


## The Python link starts only when asked on the command line (tools/run_link_demo.py does
## this): "-- --link-port=PORT --link-agents=robot_legged,robot_quadruped". The session token
## comes from the RANGE_SESSION_TOKEN environment variable, never the command line.
func _start_link_if_asked() -> void:
	var port := 0
	var agents: Array = []
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--link-port="):
			port = int(arg.trim_prefix("--link-port="))
		elif arg.begins_with("--link-agents="):
			agents = Array(arg.trim_prefix("--link-agents=").split(",", false))
	if port <= 0 or agents.is_empty():
		return
	link = LinkClient.new()
	add_child(link)
	link.setup(world, port, agents, "", run_mode)
	hud.link = link
