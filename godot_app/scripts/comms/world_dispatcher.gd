class_name WorldDispatcher
extends Node
## The world dispatcher (G4a, D-90; INTERACTION_MODES §2.2): every request carries its requester's
## principal and is checked here against configs/permissions.yaml (exported to
## data/permissions/permissions.json). Hiding a button is not enforcement.
##
## Principals: the seats SPECTATOR, DIRECTOR, PARTICIPANT, EVALUATOR (this client has one seat,
## chosen at launch), and the internal AGENT (the sidecar session) and HOST (the event tape).
##
## - Agent and host requests that are allowed go to the action gate exactly as before, so the
##   journal is unchanged. The agent session drives only the avatars it linked whose controller it
##   runs (SCRIPTED, LLM_AGENT; D-91): a request for any other avatar reaches the gate as one the
##   session does not control (CAPABILITY_DENIED, journaled as before).
## - Seat requests (cameras, views, pause, and the Director and Participant requests of G4b/G4c)
##   are answered here. Refusals and uses a capability marks `logged_for` go to the operator log
##   (`operator_log_path`, one JSON line each), never the journal: watching is not part of the
##   world's record (D-92).
##
## `decide` must give the same answer as range_service/viewer/permissions.py `check` (tested by
## comparing both matrices in tools/godot_check.py).

const SEATS := ["SPECTATOR", "DIRECTOR", "PARTICIPANT", "EVALUATOR"]
const PRINCIPALS := ["SPECTATOR", "DIRECTOR", "PARTICIPANT", "EVALUATOR", "AGENT", "HOST"]
const CONTROLLERS := ["SCRIPTED", "LLM_AGENT", "HUMAN_INPUT", "REPLAY_TAPE"]
const AGENT_CONTROLLERS := ["SCRIPTED", "LLM_AGENT"]
const MAX_LOG_IN_MEMORY := 2000

var world: RangeWorld
var table: Dictionary = {}
var seat := "SPECTATOR"
var own_avatar := ""             # a participant seat's body (HUMAN_INPUT), else ""
var operator_log_path := ""
var operator_log: Array = []     # the newest entries (tests, the status panel)


func _init() -> void:
	name = "WorldDispatcher"
	process_mode = Node.PROCESS_MODE_ALWAYS


func setup(target_world: RangeWorld, permissions := {}) -> void:
	world = target_world
	table = permissions if not permissions.is_empty() else WorldData.load_config("permissions", "permissions")


## Take a seat (launch option). A participant names its own body, which must be HUMAN_INPUT.
func set_seat(new_seat: String, avatar_id := "") -> bool:
	if not SEATS.has(new_seat):
		return false
	seat = new_seat
	own_avatar = avatar_id if new_seat == "PARTICIPANT" else ""
	_log({"event": "SEAT", "seat": seat, "own_avatar": own_avatar})
	return true


## The decision itself: {"code", "logged", "gate"}. Codes: OK, PERMISSION_DENIED, NOT_OWN_AVATAR,
## NOT_CONTROLLED, NOT_BUILT. Same rules as permissions.py `check`.
static func decide(permissions: Dictionary, principal: String, capability: String, target := "", own := "",
		controlled: Array = []) -> Dictionary:
	var caps: Dictionary = permissions.get("capabilities", {})
	if not caps.has(capability) or not PRINCIPALS.has(principal):
		return {"code": "PERMISSION_DENIED", "logged": false, "gate": ""}
	var cap: Dictionary = caps[capability]
	var grants: Dictionary = cap["grants"]
	if not grants.has(principal):
		return {"code": "PERMISSION_DENIED", "logged": false, "gate": ""}
	var scope := String(grants[principal])
	if scope == "OWN_AVATAR" and (own == "" or target != own):
		return {"code": "NOT_OWN_AVATAR", "logged": false, "gate": ""}
	if scope == "CONTROLLED" and not controlled.has(target):
		return {"code": "NOT_CONTROLLED", "logged": false, "gate": ""}
	var logged: bool = cap.get("logged_for", []).has(principal)
	if not bool(cap["built"]):
		return {"code": "NOT_BUILT", "logged": logged, "gate": String(cap.get("gate", ""))}
	return {"code": "OK", "logged": logged, "gate": ""}


## The avatars the agent session may drive: linked, with a controller it runs (D-91).
func agent_controlled(linked: Array) -> Array:
	var candidates := []
	for avatar_id in linked:
		if world.avatars.has(avatar_id) and AGENT_CONTROLLERS.has((world.avatars[avatar_id] as Avatar).controller):
			candidates.append(avatar_id)
	var out := []
	for avatar_id in candidates:
		if decide(table, "AGENT", "ACT_IN_WORLD", avatar_id, "", candidates)["code"] == "OK":
			out.append(avatar_id)
	return out


## An agent.action_request from the sidecar session that linked `linked`.
func agent_request(request, linked: Array) -> Dictionary:
	return world.actions.submit(request, agent_controlled(linked))


## The scenario's event tape (D-48): may name avatars by their real ids.
func host_request(request: Dictionary, actor_id: String) -> Dictionary:
	if decide(table, "HOST", "ACT_IN_WORLD", actor_id)["code"] != "OK":
		return world.actions.submit(request, [])
	return world.actions.submit_host(request, actor_id)


## An action from this client's seat (G4c: a participant's own body). Anything else is refused here,
## logged, and never reaches the gate or the journal. Returns {"code", ...} or the gate's result.
func seat_action(request: Dictionary) -> Dictionary:
	var agent_id := String(request.get("agent_id", ""))
	var d := seat_request("ACT_IN_WORLD", agent_id)
	if d["code"] != "OK":
		return d
	if not world.avatars.has(agent_id) or (world.avatars[agent_id] as Avatar).controller != "HUMAN_INPUT":
		d = {"code": "NOT_OWN_AVATAR", "logged": true, "gate": ""}
		_log({"event": "REQUEST", "seat": seat, "capability": "ACT_IN_WORLD", "target": agent_id, "code": d["code"]})
		return d
	return world.actions.submit(request, [agent_id])


## A seat request for `capability` on `target` (an avatar id or ""): cameras, views, pause, and
## the Director's requests. Returns {"code", "logged", "gate"}.
func seat_request(capability: String, target := "") -> Dictionary:
	var d := decide(table, seat, capability, target, own_avatar)
	if d["code"] != "OK" or d["logged"]:
		_log({"event": "REQUEST", "seat": seat, "capability": capability, "target": target, "code": d["code"]})
	return d


func allows(capability: String, target := "") -> bool:
	return decide(table, seat, capability, target, own_avatar)["code"] == "OK"


## Viewer-record audiences this seat may read for `observer` (data/permissions audiences).
func audiences(observer := "") -> Array:
	var out := []
	var auds: Dictionary = table.get("audiences", {})
	for aud in ["OBSERVER", "EVALUATOR"]:
		if auds.has(aud) and allows(String(auds[aud]), observer):
			out.append(aud)
	return out


## EVALUATOR TRUTH, live (D-93): the observer's tracks as {track id: avatar id}, only for a seat that
## holds VIEW_EVALUATOR_TRUTH; {} for any other seat. The request is logged.
func truth_tracks(observer: String) -> Dictionary:
	if seat_request("VIEW_EVALUATOR_TRUTH", observer)["code"] != "OK" or world.senses == null:
		return {}
	return world.senses.truth_tracks().get(observer, {})


func _log(entry: Dictionary) -> void:
	var tick := world.clock.tick if world != null and world.clock != null else 0
	var row := {"tick": tick, "sim_ms": SimClock.ms_at(tick)}
	row.merge(entry)
	operator_log.append(row)
	if operator_log.size() > MAX_LOG_IN_MEMORY:
		operator_log = operator_log.slice(operator_log.size() - MAX_LOG_IN_MEMORY)
	if operator_log_path == "":
		return
	var f := FileAccess.open(operator_log_path, FileAccess.READ_WRITE if FileAccess.file_exists(operator_log_path) else FileAccess.WRITE)
	if f == null:
		return
	f.seek_end()
	f.store_line(JSON.stringify(row, "", true))
	f.close()


## Every principal x capability x case, for the comparison with permissions.py `matrix`.
static func matrix(permissions: Dictionary) -> Dictionary:
	var cases := {"any": ["visitor_y", "", []], "own": ["visitor_y", "visitor_y", []],
		"other": ["robot_r", "visitor_y", []], "controlled": ["robot_r", "", ["robot_r"]],
		"not_controlled": ["visitor_y", "", ["robot_r"]]}
	var out := {}
	var caps: Array = permissions["capabilities"].keys()
	caps.sort()
	for principal in PRINCIPALS:
		for capability in caps:
			for c in cases:
				var spec: Array = cases[c]
				out["%s %s %s" % [principal, capability, c]] = decide(permissions, principal, String(capability),
					String(spec[0]), String(spec[1]), spec[2])["code"]
	return out
