class_name DemoRoutes
extends Node
## G1 walk-to-goal demo. Each avatar walks a short list of goals once, then rests.
## Timing counts world ticks, so the demo plays out the same way on every run.
## A G1 stand-in only: the scripted policy (G3) replaces it, and its routes are authored so
## that nobody meets head-on, because local avoidance is not part of G1.
##
## Robot R drives up the ramp to the platform and back; visitor_y takes the stairs.
## Neither is told which: navigation picks from what each body is allowed to use.

## route entries: [x, z, wait in seconds after arriving]
const CAST := [
	{"id": "robot_r", "body": "robot_r", "spawn": "spawn_robot", "start_s": 1.0,
		"route": [[26.0, 4.0, 4.0], [15.0, 10.5, 0.0]]},
	{"id": "visitor_x", "body": "human_walker", "spawn": "spawn_entrance", "color": "visitor_sand", "start_s": 0.0,
		"route": [[5.0, 14.8, 3.0], [7.5, 4.0, 0.0]]},
	{"id": "visitor_y", "body": "human_walker", "spawn": "spawn_edge", "color": "visitor_slate", "start_s": 6.0,
		"route": [[18.5, 3.0, 0.5], [27.0, 2.5, 0.0]]},
	{"id": "visitor_z", "body": "human_walker", "spawn": "spawn_talker", "color": "visitor_mauve", "start_s": 0.0,
		"route": [[16.5, 10.8, 0.0], [21.0, 11.0, 1.0], [25.0, 15.0, 1.0], [19.5, 17.5, 0.0]]},
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
		world.spawn_at(entry["id"], entry["body"], entry["spawn"], {"color": entry.get("color", "visitor_slate")})
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
					s["until"] = now + _ticks(float(entry["route"][s["step"]][2]))
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
