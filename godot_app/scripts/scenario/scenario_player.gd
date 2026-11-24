class_name ScenarioPlayer
extends Node
## Runs a scenario in the world (G3a, D-48): spawns the cast, then plays the event tape at exact
## ticks through the action gate, with each actor's own body limits. The scenario file Godot reads
## (godot_app/data/scenarios/) is a world-only view: no evaluator labels, measures or personas.
##
## Timing: at_tick and duration_ticks count scenario ticks at tick_hz; the world tick is 60 Hz
## (D-33), so one scenario tick is 60 / tick_hz world ticks, counted from the start tick.
##
## Start: navigation must be ready and, in a stepped run, the sidecar must have answered
## link.hello. The world always holds for one step at that point and starts on the next tick,
## whether the link was already ready or not, so the start tick never depends on timing. A live
## run never waits for the sidecar (D-44); agents that connect late miss the first samples.
## Event types mirror range_service/scenarios.py.

signal finished_run

enum Phase { WAIT_NAV, STARTING, RUNNING, DONE }

const ROBOT_TRIMS := ["robot_trim_green", "robot_trim_teal", "robot_trim_brown"]
const VISITOR_COLORS := ["visitor_sand", "visitor_slate", "visitor_mauve"]

var world: RangeWorld
var scenario: Dictionary = {}
var link: LinkClient
var run_seed := 0
var journal_path := ""
var phase: Phase = Phase.WAIT_NAV
var start_tick := -1
var finished := false
var results: Array = []          # [{"index", "event_type", "actor_id", "reason_code"}] (evaluator)
var _events: Array = []          # [{"index", "at", "event"}] sorted by world tick
var _next := 0
var _per := 6                    # world ticks per scenario tick
## G4b (D-102): a recipe's interventions, played on the tape as the Director's pre-scheduled work.
var recipe_id := ""


func _init() -> void:
	name = "ScenarioPlayer"
	process_physics_priority = -50   # after the clock, before avatars and senses


## Body ids the world must load for this scenario (with any overrides {avatar_id: body_id}).
static func body_ids(scen: Dictionary, overrides := {}) -> Array:
	var ids := []
	for avatar_id in scen["cast"]:
		var body_id := String(overrides.get(avatar_id, scen["cast"][avatar_id]["body"]))
		if not ids.has(body_id):
			ids.append(body_id)
	ids.sort()
	return ids


func setup(target_world: RangeWorld, scen: Dictionary, overrides := {}) -> bool:
	world = target_world
	scenario = scen
	_per = roundi(float(SimClock.TICK_HZ) / int(scen["tick_hz"]))
	var cast_ids: Array = scen["cast"].keys()
	cast_ids.sort()
	var robots := 0
	var visitors := 0
	for avatar_id in cast_ids:
		var body_id := String(overrides.get(avatar_id, scen["cast"][avatar_id]["body"]))
		var appearance := {}
		if String(world.bodies[body_id]["kind"]) in ["HUMAN_WALKER", "SCRIPTED_CROWD"]:
			appearance = {"color": VISITOR_COLORS[visitors % VISITOR_COLORS.size()]}
			visitors += 1
		else:
			appearance = {"badge": str(robots + 1), "trim": ROBOT_TRIMS[robots % ROBOT_TRIMS.size()], "bands": robots % 3 + 1}
			robots += 1
		var spawned := world.spawn_at(String(avatar_id), body_id, String(scen["cast"][avatar_id]["spawn"]), appearance)
		if spawned == null:
			return false
		# The presence dial's baseline (G3e, D-74), resolved by Python from persona and directive.
		spawned.controller = String(scen["cast"][avatar_id].get("controller", "SCRIPTED"))   # D-91
		spawned.presence_baseline = float(scen["cast"][avatar_id].get("presence_amplitude", spawned.presence_baseline))
	for operator_id in scen.get("pa_operators", []):
		world.comms.pa_operators[String(operator_id)] = true
	for i in scen["events"].size():
		var e: Dictionary = scen["events"][i]
		_events.append({"index": i, "at": int(e["at_tick"]) * _per, "event": e})
	if recipe_id != "":
		var recipe := WorldData.load_config("recipes", recipe_id)
		if recipe.is_empty():
			return false
		var n: int = scen["events"].size()
		for i in recipe["interventions"].size():
			var it: Dictionary = recipe["interventions"][i]
			_events.append({"index": n + i, "at": int(it["at_tick"]) * _per, "intervention": it})
	_events.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return a["at"] < b["at"] or (a["at"] == b["at"] and a["index"] < b["index"]))
	return true


func duration_world_ticks() -> int:
	return int(scenario["duration_ticks"]) * _per


func _physics_process(_delta: float) -> void:
	match phase:
		Phase.WAIT_NAV:
			if world.is_navigation_ready():
				world.hold("link")
				if link == null or link.sidecar_ready or link.run_mode != "STEPPED":
					world.release("link")
				else:
					link.ready_changed.connect(_on_link_ready)
				phase = Phase.STARTING
		Phase.STARTING:
			_start()
			_tick()
		Phase.RUNNING:
			_tick()


func _on_link_ready(is_ready: bool) -> void:
	if is_ready:
		link.ready_changed.disconnect(_on_link_ready)
		world.release("link")


func _start() -> void:
	world.start_run(run_seed, journal_path, int(scenario["tick_hz"]))
	world.sensing_enabled = true
	start_tick = world.clock.tick
	phase = Phase.RUNNING


func _tick() -> void:
	var now := world.clock.tick - start_tick
	while _next < _events.size() and int(_events[_next]["at"]) <= now:
		if _events[_next].has("intervention"):
			world.director.from_recipe(recipe_id, _events[_next]["intervention"])
		else:
			_play(int(_events[_next]["index"]), _events[_next]["event"])
		_next += 1
	if now >= duration_world_ticks():
		phase = Phase.DONE
		finished = true
		finished_run.emit()


static func _destination(w: RangeWorld, e: Dictionary) -> Dictionary:
	var args: Dictionary = e.get("args", {})
	if args.has("x"):
		return {"x": float(args["x"]), "z": float(args["z"])}
	var spawn := w.spawn_point(String(e.get("where", "")))
	if not spawn.is_empty():
		return {"x": spawn["position"].x, "z": spawn["position"].z}
	for zone in w.map_data["zones"]:
		if zone["zone_id"] == e.get("where"):
			var a: Dictionary = zone["area"]
			return {"x": (float(a["x_min"]) + float(a["x_max"])) / 2, "z": (float(a["z_min"]) + float(a["z_max"])) / 2}
	return {}


## One tape event as an action request: {"action", "args"}, or {} for an unknown event. Shared by
## the tape and the Director's TRIGGER_EVENT (G4b, D-99).
static func event_request(w: RangeWorld, e: Dictionary) -> Dictionary:
	var args: Dictionary = e.get("args", {})
	match String(e["event_type"]):
		"move_to", "avatar_approaches", "leave":
			var dest := _destination(w, e)
			return {} if dest.is_empty() else {"action": "MOVE_TO", "args": {"destination": dest}}
		"turn_to":
			return {"action": "TURN_TO", "args": {"target_id": String(args.get("target", ""))}}
		"gesture", "wave", "small_wave":
			var gesture: String = {"wave": "WAVE", "small_wave": "SMALL_WAVE"}.get(String(e["event_type"]), String(args.get("gesture", "")))
			var gargs := {"gesture": gesture}
			if args.has("target"):
				gargs["target_id"] = String(args["target"])
			return {"action": "GESTURE", "args": gargs}
		"say":
			return {"action": "SPEAK", "args": {"channel": "LOCAL", "text": String(args.get("text", "")), "addressee_id": args.get("to")}}
		"pa_announcement":
			return {"action": "SPEAK", "args": {"channel": "PA", "text": String(args.get("text", ""))}}
	return {}


## One tape event becomes one host action request, checked by the action gate like any other.
func _play(index: int, e: Dictionary) -> void:
	var actor := String(e.get("actor", ""))
	var conv := event_request(world, e)
	var action := String(conv.get("action", ""))
	var action_args: Dictionary = conv.get("args", {})
	var reason := "INVALID_SCHEMA"
	var event_ids: Array = []
	if action != "" and world.avatars.has(actor):
		var result := world.dispatcher.host_request({"schema_version": "1.0", "action_request_id": "tape_%04d" % (index + 1),
			"agent_id": actor, "based_on_tick_id": world.clock.tick, "action": action, "args": action_args}, actor)
		reason = String(result["reason_code"])
		event_ids = result["resulting_event_ids"]
	var entry := {"index": index, "event_type": String(e["event_type"]), "actor_id": null,
		"reason_code": reason, "resulting_event_ids": event_ids}
	if actor != "":
		entry["actor_id"] = actor
	results.append(entry)
	world.journal_write("SCENARIO_EVENT", entry["actor_id"], entry)
