class_name Director
extends Node
## Director interventions (G4b, D-97 to D-102; INTERACTION_MODES §5). One door: every request is
## checked by the world dispatcher's permission table (D-90): only the DIRECTOR seat may intervene
## (a recipe is the Director's work, scheduled). Spectator, Participant, Evaluator and agents are
## refused, and their attempts go to the operator log, never the journal (D-92).
##
## A request the Director may make is checked for shape (the rules of range_service/director.py),
## then carried out:
##   - world-side here: PLACE_PROP / MOVE_PROP / REMOVE_PROP (WorldEditor), TRIGGER_EVENT (the tape's
##     events through the action gate as the host), PA_ANNOUNCEMENT (the venue's PA, operator
##     "director"), NPC_SAY (the NPC says the line through the gate, like the tape);
##   - agent-side in the sidecar: EDIT_DIRECTIVE (director.request over the link; the sidecar answers
##     with director.result holding before/after; INSPECT_AGENT reads the editable parts).
## Every Director attempt that reaches this point is journaled (INTERVENTION, applied or refused):
## interventions change the world, unlike watching. Applied world-side interventions are also sent
## to the sidecar as director.intervention, so the viewer feed and the run manifest see them.
##
## Ids: each attempt gets the next "dir_NNNN" (request id and intervention id); a placed prop is
## "prop_" + that id, so a recipe can name a prop it placed earlier.

signal intervened(entry: Dictionary)        # {"status", "reason", "request", "intervention"} as journaled
signal inspected(result: Dictionary)

const OPERATIONS := {
	"DIRECTIVE_EDIT": ["EDIT_DIRECTIVE"],
	"WORLD_CHANGE": ["PLACE_PROP", "MOVE_PROP", "REMOVE_PROP"],
	"EVENT_TRIGGER": ["TRIGGER_EVENT"],
	"ENVIRONMENTAL_INFLUENCE": ["PLACE_PROP", "MOVE_PROP", "REMOVE_PROP", "PA_ANNOUNCEMENT"],
	"SOCIAL_INFLUENCE": ["NPC_SAY"],
}
const CAPABILITY := {"DIRECTIVE_EDIT": "EDIT_DIRECTIVE", "WORLD_CHANGE": "WORLD_CHANGE", "EVENT_TRIGGER": "TRIGGER_EVENT",
	"ENVIRONMENTAL_INFLUENCE": "INFLUENCE", "SOCIAL_INFLUENCE": "INFLUENCE"}
const TEXT_PROPS := ["SIGN", "NOTE"]
const EVENTS := ["say", "pa_announcement", "wave", "small_wave", "gesture", "move_to", "avatar_approaches", "leave", "turn_to"]
const EDITABLE := ["directive", "goal", "slider"]
const MAX_TEXT := 500

var world: RangeWorld
var link: LinkClient
var counter := 0
var history: Array = []        # every journaled entry, in order (tests, the HUD)
var _waiting: Dictionary = {}  # request id -> request sent to the sidecar
var _hold_started_ms := -1
const ANSWER_TIMEOUT_MS := 15000   # a stepped world never stays held for good (as LinkClient.STEP_TIMEOUT_MS)


func _init() -> void:
	name = "Director"
	process_mode = Node.PROCESS_MODE_ALWAYS


func setup(target_world: RangeWorld) -> void:
	world = target_world


## A request from this client's seat (the Director console).
func from_seat(itype, operation: String, target_id, args: Dictionary) -> Dictionary:
	return request(world.dispatcher.seat, "director" if world.dispatcher.seat == "DIRECTOR" else world.dispatcher.seat.to_lower(),
		itype, operation, target_id, args, false)


## A recipe's intervention, scheduled on the tape: the Director's work, declared before the run.
func from_recipe(recipe_id: String, entry: Dictionary) -> Dictionary:
	return request("DIRECTOR", "recipe:" + recipe_id, entry["intervention_type"], String(entry["operation"]),
		entry.get("target_id"), entry.get("args", {}), true)


## Check and carry out one request. Returns {"status": APPLIED|REFUSED|PENDING|INSPECTING, "reason", ...}.
func request(principal: String, operator: String, itype, operation: String, target_id, args: Dictionary,
		pre_scheduled: bool) -> Dictionary:
	var inspect := operation == "INSPECT_AGENT"
	var capability := "INSPECT_AGENT" if inspect else String(CAPABILITY.get(String(itype) if itype != null else "", ""))
	var target := String(target_id) if target_id != null else ""
	var d: Dictionary
	if principal == world.dispatcher.seat and not pre_scheduled:
		d = world.dispatcher.seat_request(capability, target)   # refusals go to the operator log (D-92)
	else:
		d = WorldDispatcher.decide(world.dispatcher.table, principal, capability, target)
	if d["code"] != "OK":
		return {"status": "REFUSED", "reason": "PERMISSION_DENIED" if d["code"] != "NOT_BUILT" else "NOT_BUILT", "journaled": false}
	counter += 1
	var req := {"request_id": "dir_%04d" % counter, "operator": operator, "intervention_type": itype,
		"operation": operation, "target_id": target_id, "args": args.duplicate(), "pre_scheduled": pre_scheduled}
	if inspect:
		req["intervention_type"] = null
	if inspect:
		# Checked here like every other request: an unknown name (two commands typed on one line,
		# owner's PC 2026-11-25) used to reach the sidecar, which refused the envelope and the run FAILed.
		if target.is_empty() or not world.avatars.has(target):
			return {"status": "REFUSED", "reason": "UNKNOWN_TARGET", "journaled": false}
		return _to_sidecar(req)
	var problem := problems(req)
	if problem != "":
		return _journal(req, "REFUSED", problem.get_slice(":", 0), null)
	match operation:
		"EDIT_DIRECTIVE":
			return _to_sidecar(req)
		"PLACE_PROP":
			var prop := args.duplicate()
			prop["prop_id"] = "prop_" + String(req["request_id"])
			var r := world.editor.place(prop)
			if r["code"] != "OK":
				return _journal(req, "REFUSED", r["code"], null)
			return _journal(req, "APPLIED", "", _record(req, prop["prop_id"], null, r["after"]))
		"MOVE_PROP":
			var r := world.editor.move(target, float(args["x"]), float(args["z"]), args.get("yaw_rad"))
			if r["code"] != "OK":
				return _journal(req, "REFUSED", r["code"], null)
			return _journal(req, "APPLIED", "", _record(req, target, r["before"], r["after"]))
		"REMOVE_PROP":
			var r := world.editor.remove(target)
			if r["code"] != "OK":
				return _journal(req, "REFUSED", r["code"], null)
			return _journal(req, "APPLIED", "", _record(req, target, r["before"], null))
		"TRIGGER_EVENT":
			var e := {"event_type": String(args["event_type"]), "actor": target, "args": {}}
			for k in args:
				if k != "event_type" and k != "where":
					e["args"][k] = args[k]
			if args.has("where"):
				e["where"] = args["where"]
			var conv := ScenarioPlayer.event_request(world, e)
			if conv.is_empty():
				return _journal(req, "REFUSED", "INVALID_VALUE", null)
			return _via_gate(req, target, conv["action"], conv["args"])
		"PA_ANNOUNCEMENT":
			var r := world.comms.send_pa_from(operator, String(args["text"]))
			if not r["ok"]:
				return _journal(req, "REFUSED", "EVENT_REFUSED", null)
			return _journal(req, "APPLIED", "", _record(req, null, null, JSON.stringify({"event_id": r["event_id"], "text": args["text"]})))
		"NPC_SAY":
			var to = args.get("to")
			return _via_gate(req, target, "SPEAK", {"channel": "LOCAL", "text": String(args["text"]), "addressee_id": to})
	return _journal(req, "REFUSED", "UNKNOWN_OPERATION", null)


## The shape rules (range_service/director.py request_problems): "" or "REASON: words".
func problems(req: Dictionary) -> String:
	var itype = req["intervention_type"]
	var op := String(req["operation"])
	var args: Dictionary = req["args"]
	var target = req["target_id"]
	if not OPERATIONS.has(String(itype) if itype != null else ""):
		return "UNKNOWN_OPERATION: unknown intervention type"
	if not OPERATIONS[itype].has(op):
		return "TYPE_MISMATCH: %s cannot use %s" % [itype, op]
	match op:
		"EDIT_DIRECTIVE":
			if target == null or not world.avatars.has(String(target)):
				return "UNKNOWN_TARGET: no such avatar"
			if not EDITABLE.has(String(args.get("field", ""))):
				return "NOT_EDITABLE: only the directive, goal and persona sliders are editable"
		"PLACE_PROP":
			var prop := String(args.get("prop_type", ""))
			if not WorldEditor.PLACEABLE.has(prop):
				return "UNKNOWN_PROP: unknown prop"
			if TEXT_PROPS.has(prop) != (itype == "ENVIRONMENTAL_INFLUENCE"):
				return "TYPE_MISMATCH: a sign or note is ENVIRONMENTAL_INFLUENCE, other props WORLD_CHANGE"
			if not (args.get("x") is float or args.get("x") is int) or not (args.get("z") is float or args.get("z") is int):
				return "INVALID_VALUE: x and z"
			if TEXT_PROPS.has(prop) and (String(args.get("text", "")).is_empty() or String(args.get("text", "")).length() > MAX_TEXT):
				return "INVALID_VALUE: text"
		"MOVE_PROP", "REMOVE_PROP":
			if target == null or not world.editor.placed.has(String(target)):
				return "NOT_FOUND: no such placed prop"
			if op == "MOVE_PROP" and not (args.has("x") and args.has("z")):
				return "INVALID_VALUE: x and z"
		"TRIGGER_EVENT":
			if not EVENTS.has(String(args.get("event_type", ""))):
				return "INVALID_VALUE: event_type"
			if target == null or not world.avatars.has(String(target)):
				return "UNKNOWN_TARGET: no such avatar"
		"PA_ANNOUNCEMENT":
			if String(args.get("text", "")).is_empty() or String(args.get("text", "")).length() > MAX_TEXT:
				return "INVALID_VALUE: text"
		"NPC_SAY":
			if target == null or not world.avatars.has(String(target)):
				return "UNKNOWN_TARGET: no such avatar"
			if String(args.get("text", "")).is_empty() or String(args.get("text", "")).length() > MAX_TEXT:
				return "INVALID_VALUE: text"
	return ""


func _via_gate(req: Dictionary, actor: String, action: String, action_args: Dictionary) -> Dictionary:
	var result := world.dispatcher.host_request({"schema_version": "1.0", "action_request_id": String(req["request_id"]),
		"agent_id": actor, "based_on_tick_id": world.clock.tick, "action": action, "args": action_args}, actor)
	if String(result["reason_code"]) != "OK":
		return _journal(req, "REFUSED", "EVENT_REFUSED", null)
	return _journal(req, "APPLIED", "", _record(req, actor, null, JSON.stringify({"action": action, "args": action_args,
		"resulting_event_ids": result["resulting_event_ids"]})))


func _to_sidecar(req: Dictionary) -> Dictionary:
	if link == null or not link.is_connected_to_sidecar():
		if req["operation"] == "INSPECT_AGENT":
			return {"status": "REFUSED", "reason": "NO_AGENT_LINK", "journaled": false}
		return _journal(req, "REFUSED", "NO_AGENT_LINK", null)
	_waiting[req["request_id"]] = req
	link.send_director("director.request", req)
	if link.run_mode == "STEPPED":
		# Stepped runs hold the world until the sidecar answers, like a step (D-48): the edit is
		# journaled and in effect at the same tick on every run.
		world.hold("director")
		_hold_started_ms = Time.get_ticks_msec()
	return {"status": "PENDING" if req["operation"] != "INSPECT_AGENT" else "INSPECTING", "reason": null,
		"request_id": req["request_id"], "journaled": false}


func _process(_delta: float) -> void:
	if _waiting.is_empty() or _hold_started_ms < 0 or Time.get_ticks_msec() - _hold_started_ms < ANSWER_TIMEOUT_MS:
		return
	var ids := _waiting.keys()
	ids.sort()
	for request_id in ids:
		var req: Dictionary = _waiting[request_id]
		_waiting.erase(request_id)
		if req["operation"] != "INSPECT_AGENT":
			_journal(req, "REFUSED", "NO_AGENT_LINK", null)
	_hold_started_ms = -1
	world.release("director")


## The sidecar's answer (director.result): an agent-side intervention applied or refused, or an inspection.
func on_result(result: Dictionary) -> void:
	var req = _waiting.get(result.get("request_id"))
	if req == null:
		return                                   # not ours: ignored, never acted on
	_waiting.erase(result["request_id"])
	if _waiting.is_empty():
		world.release("director")
	if result["status"] == "INSPECTED":
		inspected.emit(result)
		return
	if result["status"] == "APPLIED":
		_journal(req, "APPLIED", "", result["intervention"], false)
	else:
		_journal(req, "REFUSED", String(result.get("reason", "INVALID_VALUE")), null)


func _record(req: Dictionary, target, before, after) -> Dictionary:
	return {"schema_version": "1.0", "intervention_id": req["request_id"], "tick_id": world.clock.tick,
		"sim_time_ms": SimClock.ms_at(world.clock.tick), "operator": req["operator"],
		"intervention_type": req["intervention_type"], "operation": req["operation"], "target_id": target,
		"args": req["args"], "before": before, "after": after, "pre_scheduled": req["pre_scheduled"],
		"trial_tainted": not bool(req["pre_scheduled"])}


func _journal(req: Dictionary, status: String, reason: String, record, notify := true) -> Dictionary:
	var entry := {"status": status, "reason": null, "request": req, "intervention": record}
	if reason != "":
		entry["reason"] = reason
	world.journal_write("INTERVENTION", null, entry)
	history.append(entry)
	if status == "APPLIED" and notify and link != null and link.is_connected_to_sidecar():
		link.send_director("director.intervention", record)
	intervened.emit(entry)
	var out := entry.duplicate()
	out["journaled"] = true
	return out
