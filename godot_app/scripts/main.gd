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
##
## G4a (D-90 to D-93): -- --seat=spectator|director|evaluator (default spectator) is this client's
## seat; every camera, view and request goes through the world dispatcher. --operator-log=PATH
## writes the seat's requests and refusals (never the journal). --truth-tracks=PATH writes, at the
## end of a scenario, which avatar each observer's tracks were (evaluator only). --viewer-dir=DIR
## reads the run's live viewer feed; --viewer=open|closed opens the layer viewer at start (F3
## toggles it, F4 the EVALUATOR TRUTH panel for the Evaluator seat); --observer=ID selects the avatar.
## Replay: -- --replay=RUN/viewer opens the layer viewer on a finished run without a world
## (tools/view_run.py); --viewer-self-test scrubs to every decision of the observer, prints a summary
## line and quits (tools/godot_check.py).

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
## The presence dial for every robot (G3e, D-74): below 0 = each avatar's configured baseline.
## -- --presence-amplitude=0.2 (subtle) ... 1.0 (performative). Presentation only.
@export var presence_amplitude := -1.0

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
## G4a: the seat and the viewer.
var seat_name := "SPECTATOR"
var operator_log_path := ""
var truth_tracks_path := ""
var viewer_dir := ""
var viewer_mode := "off"
var viewer_observer := ""
var replay_dir := ""
var viewer_self_test := false
var screenshot_path := ""               # replay: save the window to PNG after selecting --decision=N
var screenshot_decision := -1
var recipe_id := ""                     # G4b (D-102): a recipe's interventions, scheduled on the tape
var dispatcher: WorldDispatcher        # the world's, or a stand-alone one in replay
var viewer_store: ViewerStore
var layer_viewer: LayerViewer
var evaluator_panel: EvaluatorPanel
var viewer_open_s := 0.0


func _ready() -> void:
	_read_args()
	if replay_dir != "":
		_run_replay()
		return
	Stage.add_lighting(self)
	if scenario_id != "":
		_run_scenario()
		return
	DisplayServer.window_set_title("SOMA RANGE — Sandbox Flats (G1)")
	world = RangeWorld.new()
	world.posing_enabled = posing
	world.presence_override = presence_amplitude
	add_child(world)
	if not world.build(MAP_ID, DemoRoutes.body_ids()):
		push_error("main: could not build %s; see the errors above" % MAP_ID)
		return
	demo = DemoRoutes.new()
	world.add_child(demo)
	demo.spawn_cast(world)

	_take_seat()
	camera_rig = CameraRig.new()
	camera_rig.dispatcher = dispatcher
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
		elif arg.begins_with("--presence-amplitude="):
			presence_amplitude = clampf(float(arg.trim_prefix("--presence-amplitude=")), 0.0, 1.0)
		elif arg.begins_with("--seat="):
			seat_name = arg.trim_prefix("--seat=").to_upper()
		elif arg.begins_with("--operator-log="):
			operator_log_path = arg.trim_prefix("--operator-log=")
		elif arg.begins_with("--truth-tracks="):
			truth_tracks_path = arg.trim_prefix("--truth-tracks=")
		elif arg.begins_with("--viewer-dir="):
			viewer_dir = arg.trim_prefix("--viewer-dir=")
		elif arg.begins_with("--viewer="):
			viewer_mode = arg.trim_prefix("--viewer=")
		elif arg.begins_with("--observer="):
			viewer_observer = arg.trim_prefix("--observer=")
		elif arg.begins_with("--replay="):
			replay_dir = arg.trim_prefix("--replay=")
		elif arg == "--viewer-self-test":
			viewer_self_test = true
		elif arg.begins_with("--screenshot="):
			screenshot_path = arg.trim_prefix("--screenshot=")
		elif arg.begins_with("--recipe="):
			recipe_id = arg.trim_prefix("--recipe=")
		elif arg.begins_with("--decision="):
			screenshot_decision = int(arg.trim_prefix("--decision="))


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
	world.presence_override = presence_amplitude
	add_child(world)
	world.sensing_enabled = false
	if not world.build(String(scen["map"]), ScenarioPlayer.body_ids(scen, body_overrides)):
		_fail("main: could not build the world for %s" % scenario_id)
		return
	scenario_player = ScenarioPlayer.new()
	scenario_player.run_seed = run_seed if _seed_given else int(scen["default_seed"])
	scenario_player.recipe_id = recipe_id
	scenario_player.journal_path = journal_path
	if journal_path == "auto":
		scenario_player.journal_path = Journal.new_default_path("%s_%s" % [scenario_id, Time.get_datetime_string_from_system().replace(":", "-")])
	if not scenario_player.setup(world, scen, body_overrides):
		_fail("main: could not place the cast of %s" % scenario_id)
		return
	world.add_child(scenario_player)
	_take_seat()
	camera_rig = CameraRig.new()
	camera_rig.dispatcher = dispatcher
	add_child(camera_rig)
	camera_rig.set_targets(world.avatar_list())
	camera_rig.look_from(Vector3(15, 24, 33), Vector3(15, 0, 9))
	if viewer_observer != "":
		camera_rig.select_avatar(viewer_observer)
	hud = Hud.new()
	hud.setup(world, camera_rig, null)
	add_child(hud)
	sense_view = SenseView.new()
	sense_view.setup(world, camera_rig)
	add_child(sense_view)
	if viewer_dir != "" and viewer_mode != "off":
		_setup_viewer(viewer_dir, true, camera_rig.selected_id())
		sense_view.store = viewer_store
	_start_link_if_asked()
	if link == null and link_port > 0:
		var cast: Array = scen["cast"].keys()
		cast.sort()
		link = LinkClient.new()
		add_child(link)
		link.setup(world, link_port, cast, "", run_mode)
		hud.link = link
	scenario_player.link = link
	world.director.link = link
	scenario_player.finished_run.connect(_on_scenario_finished)


func _on_scenario_finished() -> void:
	var digest := world.end_run()
	if truth_tracks_path != "":
		_write_json(truth_tracks_path, world.senses.truth_tracks())   # evaluator only, never the journal (D-93)
	if frame_stats != null:
		frame_stats.extra = {"viewer_mode": viewer_mode, "viewer_open_s": snappedf(viewer_open_s, 0.1),
			"viewer_draws": layer_viewer.draws if layer_viewer != null else 0}
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
	world.director.link = link


# ---------------- G4a: seat, viewer, replay ----------------

## The client's seat (D-90): the world's dispatcher, with the operator log (never the journal, D-92).
func _take_seat() -> void:
	dispatcher = world.dispatcher
	dispatcher.operator_log_path = operator_log_path
	if not dispatcher.set_seat(seat_name if seat_name != "PARTICIPANT" else "SPECTATOR"):
		push_warning("main: unknown seat '%s'; taking the SPECTATOR seat" % seat_name)
		dispatcher.set_seat("SPECTATOR")
	seat_name = dispatcher.seat


func _setup_viewer(dir: String, live: bool, first_observer: String) -> void:
	viewer_store = ViewerStore.new()
	add_child(viewer_store)
	viewer_store.open(dir, dispatcher, live)
	if first_observer == "" and not viewer_store.observers.is_empty():
		first_observer = String(viewer_store.observers[0])
	var layer := CanvasLayer.new()
	layer.name = "ViewerLayer"
	layer.layer = 5
	add_child(layer)
	layer_viewer = LayerViewer.new()
	layer_viewer.setup(viewer_store, dispatcher, first_observer)
	layer_viewer.anchor_left = 0.42
	layer_viewer.anchor_right = 1.0
	layer_viewer.anchor_bottom = 1.0
	layer_viewer.visible = false
	layer.add_child(layer_viewer)
	evaluator_panel = EvaluatorPanel.create(viewer_store, dispatcher)   # null unless the seat may (D-90)
	if evaluator_panel != null:
		evaluator_panel.anchor_top = 0.45
		evaluator_panel.anchor_right = 0.41
		evaluator_panel.anchor_bottom = 1.0
		evaluator_panel.offset_left = 8
		evaluator_panel.offset_bottom = -8
		layer.add_child(evaluator_panel)
		evaluator_panel.show_for(first_observer, "")
		layer_viewer.decision_selected.connect(func(id: String) -> void: evaluator_panel.show_for(layer_viewer.observer, id))
	if viewer_mode == "open" or replay_dir != "":
		toggle_viewer()


## F3: open or close the layer viewer for the selected observer (VIEW_LAYERS, D-90).
func toggle_viewer() -> bool:
	if layer_viewer == null:
		return false
	if layer_viewer.visible:
		layer_viewer.visible = false
		return true
	if dispatcher.seat_request("VIEW_LAYERS", layer_viewer.observer)["code"] != "OK":
		return false
	layer_viewer.visible = true
	return true


func _process(delta: float) -> void:
	if layer_viewer == null:
		return
	if layer_viewer.visible:
		viewer_open_s += delta
	if camera_rig != null and camera_rig.selected_id() != "" and camera_rig.selected_id() != layer_viewer.observer:
		layer_viewer.set_observer(camera_rig.selected_id())
		if evaluator_panel != null:
			evaluator_panel.show_for(layer_viewer.observer, "")


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("viewer_toggle"):
		toggle_viewer()
	elif event.is_action_pressed("evaluator_toggle") and evaluator_panel != null:
		evaluator_panel.visible = not evaluator_panel.visible
		if evaluator_panel.visible:
			evaluator_panel.refresh()
	elif replay_dir != "" and layer_viewer != null and (event.is_action_pressed("select_next") or event.is_action_pressed("select_prev")):
		var obs := viewer_store.observers
		if not obs.is_empty():
			var i := obs.find(layer_viewer.observer)
			i = (i + (1 if event.is_action_pressed("select_next") else -1) + obs.size()) % obs.size()
			layer_viewer.set_observer(String(obs[i]))
			if evaluator_panel != null:
				evaluator_panel.show_for(layer_viewer.observer, "")


## Replay a finished run (tools/view_run.py): the layer viewer alone, no world. The seat's
## dispatcher stands alone; it reads the same permissions file.
func _run_replay() -> void:
	DisplayServer.window_set_title("SOMA RANGE — layer viewer (replay)")
	dispatcher = WorldDispatcher.new()
	add_child(dispatcher)
	dispatcher.setup(null)
	dispatcher.operator_log_path = operator_log_path
	if not dispatcher.set_seat(seat_name if seat_name != "PARTICIPANT" else "SPECTATOR"):
		dispatcher.set_seat("SPECTATOR")
	seat_name = dispatcher.seat
	var bg := CanvasLayer.new()
	add_child(bg)
	var back := ColorRect.new()
	back.color = Color(0.04, 0.05, 0.07)
	back.anchor_right = 1.0
	back.anchor_bottom = 1.0
	bg.add_child(back)
	var help := Label.new()
	help.text = "SOMA RANGE · layer viewer · REPLAY · seat %s\n[ ] observer · F3 viewer · F4 EVALUATOR TRUTH (Evaluator seat)\n, . step 1 s (Shift 10 s) · N / P decision · - = zoom" % seat_name
	help.position = Vector2(12, 12)
	help.add_theme_color_override("font_color", Color("#e6eef2"))
	bg.add_child(help)
	_setup_viewer(replay_dir, false, viewer_observer)
	if viewer_self_test:
		await get_tree().process_frame
		await get_tree().process_frame
		var code := self_test()
		get_tree().quit(code)
	elif screenshot_path != "":
		await get_tree().process_frame
		var list := layer_viewer.decisions()
		if screenshot_decision >= 0 and screenshot_decision < list.size():
			layer_viewer.select_decision(String(list[screenshot_decision]["data"]["decision_id"]))
			if evaluator_panel != null:
				evaluator_panel.show_for(layer_viewer.observer, layer_viewer.selected_decision)
		for i in 5:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(screenshot_path)
		get_tree().quit(0)


## G4a end-to-end check on a finished run (tools/godot_check.py): select the observer, scrub to every
## one of its decisions, build the "why" text, and check the per-observer labels, the empty HORIZON
## lanes, the disabled Bypass, and that the EVALUATOR TRUTH panel exists for the Evaluator seat only
## and no evaluator record was stored for any other seat.
func self_test() -> int:
	var problems: Array[String] = []
	var lv := layer_viewer
	var obs := lv.observer
	var list := lv.decisions()
	var drops := 0
	var with_calls := 0
	for rec in list:
		if not lv.select_decision(String(rec["data"]["decision_id"])):
			problems.append("could not select %s" % rec["data"]["decision_id"])
			continue
		if lv.playhead_ms != int(rec["t_ms"]):
			problems.append("scrub did not move to %s" % rec["data"]["decision_id"])
		var text := lv.decision_text()
		if not text.contains("seen by %s" % obs) or not text.contains("Triggers:") or not text.contains("Actions:"):
			problems.append("decision text of %s lacks its observer, triggers or actions" % rec["data"]["decision_id"])
		drops += text.count("DROPPED before sending")
		if not rec["data"]["calls"].is_empty():
			with_calls += 1
			if not text.contains("Model call"):
				problems.append("decision %s: model call missing from the text" % rec["data"]["decision_id"])
		for other in viewer_store.observers:
			if String(other) != obs and text.contains(String(other)):
				problems.append("decision %s's text names %s by its real id" % [rec["data"]["decision_id"], other])
	var not_built := 0
	for row in lv.lane_rows:
		if not bool(row["built"]):
			if lv.lane_note(String(row["key"])).contains("not built (G5)"):
				not_built += 1
		if not lv.buttons[row["key"]]["bypass"].disabled:
			problems.append("Bypass is enabled for %s" % row["key"])
	if not_built != 9:
		problems.append("%d HORIZON lanes say 'not built (G5)', expected 9" % not_built)
	var truth_allowed := dispatcher.allows("VIEW_EVALUATOR_TRUTH")
	if (evaluator_panel != null) != truth_allowed:
		problems.append("EVALUATOR TRUTH panel present=%s for seat %s" % [evaluator_panel != null, seat_name])
	if not truth_allowed and not viewer_store.evaluator.is_empty():
		problems.append("the %s seat stored evaluator records" % seat_name)
	if truth_allowed and evaluator_panel != null and not list.is_empty():
		evaluator_panel.show_for(obs, String(list[list.size() - 1]["data"]["decision_id"]))
		if not evaluator_panel.text_for().contains("Private goals:"):
			problems.append("the EVALUATOR TRUTH panel shows no private goals")
	if lv.capability_card().find("[%s |" % obs) < 0:
		problems.append("no capability card for %s" % obs)
	print("VIEWER SELF TEST observer=%s seat=%s decisions=%d with_model_calls=%d drops_shown=%d horizon_not_built=%d evaluator_panel=%s evaluator_records=%d refused=%d problems=%d" % [
		obs, seat_name, list.size(), with_calls, drops, not_built, "present" if evaluator_panel != null else "absent",
		viewer_store.evaluator.size(), viewer_store.refused, problems.size()])
	for p in problems:
		print("VIEWER PROBLEM " + p)
	return 0 if problems.is_empty() and not list.is_empty() else 1


static func _write_json(path: String, data) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("main: cannot write %s" % path)
		return
	f.store_string(JSON.stringify(data, "", true))
	f.close()
