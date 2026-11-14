class_name DemoRoutes
extends Node
## G1 walk-to-goal demo, with the robot body family (D-36). Each avatar walks a short list
## of goals once, then rests. Timing counts world ticks, so the demo plays out the same way on
## every run. A stand-in only: the scripted policy (G3) replaces it, and its routes are authored
## so that nobody meets head-on, because local avoidance is not part of G1.
##
## SB-05 for all three robot families: they start beside the stairs and each goes up onto the
## platform. Nobody tells them which way: navigation picks from what each body may use, so the
## wheeled humanoid takes the ramp while the legged humanoid and the quadruped take the stairs.

## route entries: [x, z, wait in seconds after arriving, optional {"gesture": ..., "say": ...} done on arrival]
## The quadruped also tries to WAVE, which its body cannot do: the world refuses it (D-36).
## appearance: number badge, matte trim color and 1-3 trim bands (ART_DIRECTION §2.1)
const CAST := [
	{"id": "robot_quadruped", "body": "quadruped", "spawn": "spawn_stairs_side_1", "start_s": 0.0,
		"appearance": {"badge": "3", "trim": "robot_trim_brown", "bands": 3},
		"route": [[28.2, 2.0, 0.0, {"gesture": "WAVE", "then_gesture": "HEAD_TILT", "say": "Hello from up here."}]]},
	{"id": "robot_legged", "body": "legged_humanoid", "spawn": "spawn_stairs_side_2", "start_s": 3.0,
		"appearance": {"badge": "1", "trim": "robot_trim_green", "bands": 1},
		"route": [[25.0, 4.5, 0.0, {"gesture": "WAVE", "say": "I took the stairs."}]]},
	{"id": "robot_wheeled", "body": "wheeled_humanoid", "spawn": "spawn_stairs_side_3", "start_s": 0.5,
		"appearance": {"badge": "2", "trim": "robot_trim_teal", "bands": 2},
		"route": [[25.5, 6.6, 0.0, {"say": "And I came up the ramp."}]]},
	{"id": "visitor_x", "body": "human_walker", "spawn": "spawn_entrance", "start_s": 0.0,
		"appearance": {"color": "visitor_sand"},
		"route": [[5.0, 14.8, 3.0, {"say": "These chairs look free."}], [7.5, 4.0, 0.0]]},
	{"id": "visitor_y", "body": "human_walker", "spawn": "spawn_edge", "start_s": 4.0,
		"appearance": {"color": "visitor_slate"},
		"route": [[12.5, 15.5, 0.0]]},
	{"id": "visitor_z", "body": "human_walker", "spawn": "spawn_talker", "start_s": 0.0,
		"appearance": {"color": "visitor_mauve"},
		"route": [[16.5, 10.8, 0.0], [21.0, 11.0, 1.0, {"gesture": "SMALL_WAVE"}], [25.0, 15.0, 1.0], [19.5, 17.5, 0.0]]},
]

var world: RangeWorld
var finished := false
var finished_tick := -1
var _state: Dictionary = {}   # avatar_id -> {"phase", "step", "until"}
var _start_tick := -1


static func body_ids() -> Array:
	var ids := []
	for entry in CAST:
		if not ids.has(entry["body"]):
			ids.append(entry["body"])
	return ids


func _init() -> void:
	name = "DemoRoutes"


func spawn_cast(target_world: RangeWorld) -> void:
	world = target_world
	for entry in CAST:
		world.spawn_at(entry["id"], entry["body"], entry["spawn"], entry.get("appearance", {}))
		_state[entry["id"]] = {"phase": "start", "step": 0, "until": 0}


## Start the clock of the demo. Call once navigation is ready.
func start() -> void:
	_start_tick = world.clock.tick


func started() -> bool:
	return _start_tick >= 0


func _ticks(seconds: float) -> int:
	return int(round(seconds * SimClock.TICK_HZ))


func _go(avatar: Avatar, entry: Dictionary, s: Dictionary) -> void:
	var goal: Array = entry["route"][s["step"]]
	avatar.navigate_to(world.ground_point(float(goal[0]), float(goal[1])))
	s["phase"] = "moving"


func _physics_process(_delta: float) -> void:
	if _start_tick < 0 or finished:
		return
	var now := world.clock.tick - _start_tick
	var all_done := true
	for entry in CAST:
		var avatar: Avatar = world.avatars.get(entry["id"])
		var s: Dictionary = _state[entry["id"]]
		match s["phase"]:
			"start":
				if now >= _ticks(float(entry["start_s"])):
					_go(avatar, entry, s)
			"moving":
				if avatar.mode == Avatar.Mode.IDLE:
					s["phase"] = "waiting"
					var step: Array = entry["route"][s["step"]]
					s["until"] = now + _ticks(float(step[2]))
					if step.size() > 3:
						_act(avatar, step[3])
			"waiting":
				if now >= s["until"]:
					s["step"] += 1
					if s["step"] < entry["route"].size():
						_go(avatar, entry, s)
					else:
						s["phase"] = "done"
		if s["phase"] != "done":
			all_done = false
	if all_done:
		finished = true
		finished_tick = world.clock.tick


func _act(avatar: Avatar, actions: Dictionary) -> void:
	if actions.has("gesture"):
		avatar.perform_gesture(String(actions["gesture"]))
	if actions.has("then_gesture"):
		avatar.perform_gesture(String(actions["then_gesture"]))
	if actions.has("say"):
		avatar.say(String(actions["say"]))


## One line for the HUD, e.g. "goal 1/2 → (26.0, 4.0) · moving".
func status_text(avatar_id: String) -> String:
	if not _state.has(avatar_id):
		return "not in demo"
	var s: Dictionary = _state[avatar_id]
	for entry in CAST:
		if entry["id"] == avatar_id:
			var route: Array = entry["route"]
			if s["phase"] == "done":
				return "route finished"
			var goal: Array = route[s["step"]]
			return "goal %d/%d → (%.1f, %.1f) · %s" % [s["step"] + 1, route.size(), goal[0], goal[1], s["phase"]]
	return ""
