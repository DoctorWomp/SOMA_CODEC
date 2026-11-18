class_name ActionGate
extends Node
## The host's action gate (Blueprint §10.3, §12.3; D-04, D-43). Agents only propose; every
## agent.action_request is checked here and answered with an action_result:
##
##  1. INVALID_SCHEMA      the request does not match contracts/action_request.schema.json (a
##                         structural check in GDScript; the sidecar validates with JSON Schema)
##                         or claims a tick in the future
##  2. CAPABILITY_DENIED   this session does not control that agent
##  3. STALE_OBSERVATION   based on an observation older than STALE_AFTER_TICKS
##  4. RATE_LIMITED        more than RATE_LIMIT requests from one agent in one second
##  5. per action: TARGET_UNKNOWN, CAPABILITY_DENIED (gesture, voice or expression part the body
##     lacks), RATE_LIMITED (an expression change within 1/3 s, D-14),
##     GROUP_NOT_MEMBER, PA_UNAUTHORIZED, PRIVACY_SCOPE_DENIED (someone who could hear is
##     outside the declared disclosure scope, D-12)
##
## Agents name people by the anonymous track ids they were given (or ids they were introduced
## to through a group); the gate resolves those on the host side and never tells the agent who
## a track really is.

## 6.5 s: the longest model deadline (C2, 6 s; D-50) plus 0.5 s for the link. It was 60 ticks (1 s),
## which refused every answer from a model slower than 1 s in a live run, although the gateway
## allows Robot R 4 s; the gateway itself discards anything later than its deadline (G3c-2, D-60).
const STALE_AFTER_TICKS := 390
const RATE_LIMIT := 10
const ID_PATTERN := "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"
const ACTIONS := ["MOVE_TO", "LOOK_AT", "TURN_TO", "SPEAK", "GESTURE", "WAIT", "YIELD", "INTERACT", "JOIN_QUEUE",
	"REQUEST_CLARIFICATION", "CREATE_GROUP", "INVITE_GROUP", "ACCEPT_GROUP", "DECLINE_GROUP", "LEAVE_GROUP", "NO_OP",
	"EXPRESS"]
## Allowed argument names per action: [required, optional].
const ARGS := {
	"MOVE_TO": [[], ["destination", "target_id"]],
	"LOOK_AT": [[], ["point", "target_id"]],
	"TURN_TO": [[], ["yaw_rad", "target_id"]],
	"SPEAK": [["channel", "text"], ["addressee_id", "group_id", "disclosure_scope"]],
	"GESTURE": [["gesture"], ["target_id", "sign_text", "amplitude", "tempo"]],
	"WAIT": [["duration_ms"], []],
	"YIELD": [[], ["to_id"]],
	"INTERACT": [["object_id", "affordance"], []],
	"JOIN_QUEUE": [["queue_id"], []],
	"REQUEST_CLARIFICATION": [["text"], ["addressee_id"]],
	"CREATE_GROUP": [["group_name"], []],
	"INVITE_GROUP": [["group_id", "invitee_id"], []],
	"ACCEPT_GROUP": [["group_id"], []],
	"DECLINE_GROUP": [["group_id"], []],
	"LEAVE_GROUP": [["group_id"], []],
	"NO_OP": [[], []],
	"EXPRESS": [["expression_id"], ["target_id", "amplitude", "tempo"]],
}
const GESTURES := ["WAVE", "SMALL_WAVE", "RAISED_HAND", "POINT", "BECKON", "NOD", "SHAKE_HEAD", "OPEN_PALM", "BOW",
	"HEAD_TILT", "SIT_IN_PLACE", "HAND_OVER"]
const SCOPES := ["PUBLIC", "GROUP", "ONE_TO_ONE", "SEALED"]
const EXPRESSION_ID_PATTERN := "^[a-z][a-z0-9_]{1,31}$"

var world: RangeWorld
var resolved: Array = []    # [{"request", "result"}] in order (evaluator, tests)
var _recent: Dictionary = {}  # agent id -> ticks of its recent requests
var _id_regex := RegEx.create_from_string(ID_PATTERN)
var _expression_regex := RegEx.create_from_string(EXPRESSION_ID_PATTERN)
## Host requests (the scenario's event tape) may name avatars by their real ids (D-48).
var _host_request := false


func _init() -> void:
	name = "ActionGate"


func setup(target_world: RangeWorld) -> void:
	world = target_world


## A request from the host itself (the scenario's event tape, D-48): same checks and body limits,
## but it may name avatars by their real ids.
func submit_host(request: Dictionary, actor_id: String) -> Dictionary:
	_host_request = true
	var result := submit(request, [actor_id])
	_host_request = false
	return result


## Validate and, if allowed, carry out one request for a session controlling `controlled`.
func submit(request, controlled: Array) -> Dictionary:
	var tick := world.clock.tick
	var req: Dictionary = request if request is Dictionary else {}
	var request_id := String(req.get("action_request_id", "")) if req.get("action_request_id") is String else ""
	var agent_id := String(req.get("agent_id", "")) if req.get("agent_id") is String else ""
	var outcome := _check_shape(req)
	if outcome == "OK" and int(req["based_on_tick_id"]) > tick:
		outcome = "INVALID_SCHEMA"
	if outcome == "OK" and not controlled.has(agent_id):
		outcome = "CAPABILITY_DENIED"
	if outcome == "OK" and not world.avatars.has(agent_id):
		outcome = "TARGET_UNKNOWN"
	if outcome == "OK" and tick - int(req["based_on_tick_id"]) > STALE_AFTER_TICKS:
		outcome = "STALE_OBSERVATION"
	if outcome == "OK":
		var recent: Array = _recent.get(agent_id, []).filter(func(t: int) -> bool: return tick - t < SimClock.TICK_HZ)
		recent.append(tick)
		_recent[agent_id] = recent
		if recent.size() > RATE_LIMIT:
			outcome = "RATE_LIMITED"
	var events: Array = []
	if outcome == "OK":
		var done := _execute(world.avatars[agent_id], String(req["action"]), req["args"])
		outcome = done["reason_code"]
		if done.get("event_id", "") != "":
			events.append(done["event_id"])
	var result := {
		"schema_version": "1.0",
		"action_request_id": request_id if _id_regex.search(request_id) != null else "act_invalid",
		"agent_id": agent_id if _id_regex.search(agent_id) != null else "unknown",
		"accepted": outcome == "OK",
		"executed": outcome == "OK",
		"reason_code": outcome,
		"resulting_event_ids": events,
		"resolved_at_tick_id": tick,
	}
	resolved.append({"request": req, "result": result})
	world.journal_write("ACTION_RESOLVED", result["agent_id"], {"request": req, "result": result})
	return result


func _check_shape(req: Dictionary) -> String:
	for key in ["schema_version", "action_request_id", "agent_id", "based_on_tick_id", "action", "args"]:
		if not req.has(key):
			return "INVALID_SCHEMA"
	for key in req:
		if not key in ["schema_version", "action_request_id", "agent_id", "based_on_tick_id", "action", "args", "reason_summary"]:
			return "INVALID_SCHEMA"
	if req["schema_version"] != "1.0" or not _is_id(req["action_request_id"]) or not _is_id(req["agent_id"]):
		return "INVALID_SCHEMA"
	if not _is_tick(req["based_on_tick_id"]) or not req["action"] is String or not ACTIONS.has(req["action"]):
		return "INVALID_SCHEMA"
	if not req["args"] is Dictionary:
		return "INVALID_SCHEMA"
	var args: Dictionary = req["args"]
	var spec: Array = ARGS[req["action"]]
	for key in spec[0]:
		if not args.has(key):
			return "INVALID_SCHEMA"
	for key in args:
		if not spec[0].has(key) and not spec[1].has(key):
			return "INVALID_SCHEMA"
	match String(req["action"]):
		"GESTURE":
			if not GESTURES.has(args["gesture"]) or not _prosody_ok(args):
				return "INVALID_SCHEMA"
		"SPEAK":
			if not args["channel"] in ["LOCAL", "GROUP", "PA"] or not _is_text(args["text"]):
				return "INVALID_SCHEMA"
			if (args["channel"] == "GROUP") != args.has("group_id"):
				return "INVALID_SCHEMA"
			if args.has("disclosure_scope") and not SCOPES.has(args["disclosure_scope"]):
				return "INVALID_SCHEMA"
		"MOVE_TO", "LOOK_AT", "TURN_TO":
			if args.size() != 1:
				return "INVALID_SCHEMA"
		"WAIT":
			if not _is_tick(args["duration_ms"]) or float(args["duration_ms"]) > 60000:
				return "INVALID_SCHEMA"
		"REQUEST_CLARIFICATION":
			if not _is_text(args["text"]):
				return "INVALID_SCHEMA"
		"EXPRESS":
			if not args["expression_id"] is String or _expression_regex.search(args["expression_id"]) == null:
				return "INVALID_SCHEMA"
			if not _prosody_ok(args):
				return "INVALID_SCHEMA"
	return "OK"


## Optional amplitude and tempo (D-56): numbers from 0.5 to 1.5 (the body narrows them further).
func _prosody_ok(args: Dictionary) -> bool:
	for key in ["amplitude", "tempo"]:
		if args.has(key):
			var v = args[key]
			if not (v is float or v is int) or float(v) < RigSpec.PROSODY_MIN or float(v) > RigSpec.PROSODY_MAX:
				return false
	return true


static func _prosody(args: Dictionary, key: String) -> float:
	return float(args[key]) if args.has(key) else -1.0


func _is_id(v) -> bool:
	return v is String and _id_regex.search(v) != null


func _is_tick(v) -> bool:
	return (v is int or (v is float and v == floorf(v))) and v >= 0


func _is_text(v) -> bool:
	return v is String and v.length() >= 1 and v.length() <= 500


## Resolve a name the agent used (a track id it holds, or an id it knows) to an avatar.
func resolve(agent: Avatar, ref) -> Avatar:
	if not ref is String:
		return null
	var entity := world.senses.entity_for_track(agent.avatar_id, ref)
	if entity == "" and (world.comms.known_ids(agent.avatar_id).has(ref) or _host_request):
		entity = ref
	return world.avatars.get(entity)


func _execute(agent: Avatar, action: String, args: Dictionary) -> Dictionary:
	var ok := {"reason_code": "OK", "event_id": ""}
	match action:
		"GESTURE":
			var target = null
			if args.has("target_id") and args["target_id"] != null:
				var who := resolve(agent, args["target_id"])
				if who == null:
					return {"reason_code": "TARGET_UNKNOWN"}
				target = who.avatar_id
			return world.comms.send_gesture(agent, String(args["gesture"]), target, String(args.get("sign_text", "")),
				_prosody(args, "amplitude"), _prosody(args, "tempo"))
		"SPEAK", "REQUEST_CLARIFICATION":
			return _speak(agent, args if action == "SPEAK" else {"channel": "LOCAL", "text": args["text"],
				"addressee_id": args.get("addressee_id")})
		"MOVE_TO":
			var dest: Vector3
			if args.has("target_id"):
				var who := resolve(agent, args["target_id"])
				if who == null:
					return {"reason_code": "TARGET_UNKNOWN"}
				dest = who.global_position
			else:
				var d: Dictionary = args["destination"]
				var bounds: Vector2 = world.registry["bounds"]
				if not (d.get("x") is float or d.get("x") is int) or float(d["x"]) < 0 or float(d["x"]) > bounds.x \
						or float(d.get("z", -1)) < 0 or float(d.get("z", -1)) > bounds.y:
					return {"reason_code": "TARGET_UNKNOWN"}
				dest = world.ground_point(float(d["x"]), float(d["z"]))
			agent.navigate_to(dest)
			return ok
		"TURN_TO", "LOOK_AT":
			if args.has("target_id"):
				var who := resolve(agent, args["target_id"])
				if who == null:
					return {"reason_code": "TARGET_UNKNOWN"}
				var v := who.global_position - agent.global_position
				agent.turn_to(atan2(-v.x, -v.z))
				if action == "LOOK_AT":
					agent.look_toward(who.avatar_id)
			elif args.has("yaw_rad"):
				agent.turn_to(float(args["yaw_rad"]))
			else:
				var p: Dictionary = args["point"]
				agent.turn_to(atan2(-(float(p["x"]) - agent.global_position.x), -(float(p["z"]) - agent.global_position.z)))
				if action == "LOOK_AT":
					agent.look_toward(Vector3(float(p["x"]), float(p.get("y", agent.sensor_mount_height)), float(p["z"])))
			return ok
		"EXPRESS":
			var addressee = null
			if args.has("target_id") and args["target_id"] != null:
				var who := resolve(agent, args["target_id"])
				if who == null:
					return {"reason_code": "TARGET_UNKNOWN"}
				addressee = who.avatar_id
			return world.comms.send_expression(agent, String(args["expression_id"]), addressee,
				_prosody(args, "amplitude"), _prosody(args, "tempo"))
		"WAIT", "NO_OP":
			return ok
		"YIELD":
			agent.stop()
			return ok
		"INTERACT", "JOIN_QUEUE":
			return {"reason_code": "TARGET_UNKNOWN"}   # no interactable objects or queues exist yet
		"CREATE_GROUP":
			return world.comms.create_group(agent, String(args["group_name"]))
		"INVITE_GROUP":
			var invitee := resolve(agent, args["invitee_id"])
			if invitee == null:
				return {"reason_code": "TARGET_UNKNOWN"}
			return world.comms.invite(agent, String(args["group_id"]), invitee.avatar_id)
		"ACCEPT_GROUP":
			return world.comms.accept(agent, String(args["group_id"]))
		"DECLINE_GROUP":
			return world.comms.decline(agent, String(args["group_id"]))
		"LEAVE_GROUP":
			return world.comms.leave(agent, String(args["group_id"]))
	return {"reason_code": "INVALID_SCHEMA"}


func _speak(agent: Avatar, args: Dictionary) -> Dictionary:
	var channel := String(args["channel"])
	var scope := String(args.get("disclosure_scope", "PUBLIC"))
	var addressee = null
	if args.get("addressee_id") != null:
		var who := resolve(agent, args["addressee_id"])
		if who == null:
			return {"reason_code": "TARGET_UNKNOWN"}
		addressee = who.avatar_id
	if scope == "SEALED":
		return _deny(agent, channel)
	match channel:
		"PA":
			if scope != "PUBLIC":
				return _deny(agent, channel)
			return world.comms.send_pa(agent, String(args["text"]))
		"GROUP":
			var group_id := String(args["group_id"])
			if not world.comms.is_member(agent.avatar_id, group_id):
				return world.comms._reject(agent, "GROUP", "GROUP_NOT_MEMBER")
			if scope == "ONE_TO_ONE" and world.comms.groups[group_id]["members"].size() > 2:
				return _deny(agent, channel)
			return world.comms.send_group(agent, group_id, String(args["text"]))
	# LOCAL: everyone who could actually hear must be inside the declared scope (host truth).
	if scope != "PUBLIC":
		var allowed := {}
		if scope == "ONE_TO_ONE" and addressee != null:
			allowed[addressee] = true
		if scope == "GROUP":
			allowed = world.comms.known_ids(agent.avatar_id)
		var mouth := SenseModel.mouth_of(agent)
		for other in world.avatar_list():
			if other != agent and not allowed.has(other.avatar_id) \
					and SenseModel.hear(world, mouth, other, SenseModel.SPEECH_LEVEL_DB)["heard"]:
				return _deny(agent, channel)
	return world.comms.send_local(agent, String(args["text"]), addressee)


func _deny(agent: Avatar, channel: String) -> Dictionary:
	return world.comms._reject(agent, channel, "PRIVACY_SCOPE_DENIED")
