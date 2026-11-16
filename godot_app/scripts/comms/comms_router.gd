class_name CommsRouter
extends Node
## RANGE COMMS (Blueprint §8, D-07, D-43): the four channels, on top of the G2a senses.
##
## - GESTURE: shown with the body (only gestures it has, D-36); received by whoever can see the
##   gesturing part while it lasts (observer filter).
## - LOCAL: speech; received by whoever can hear it at the next sample (observer filter).
## - GROUP: device messages to the members of a group, at any distance. Membership needs an
##   invitation AND its acceptance; declining does nothing; leaving stops delivery at once.
##   Never delivered to anyone else, even standing next to the sender; not a sound.
## - PA: announcements through the venue's PA speaker, from authorized senders only (body
##   capability can_use_pa, or listed as a PA operator for the run). Everyone in coverage hears
##   it; an unauthorized attempt is refused (PA_UNAUTHORIZED) and nobody hears anything.
##
## Every message produces one comms_event record (contracts/comms_event.schema.json) listing who
## received it and who did not. Those lists are evaluator-only: the record goes to the journal,
## never to an agent.

const PA_PROVENANCE := "synthetic_pa_v1"
const DEVICE_PROVENANCE := "device_group_v1"

var world: RangeWorld
var groups: Dictionary = {}        # group_id -> {"name", "creator", "members": Array, "invited": Array}
var pa_operators: Dictionary = {}  # avatar ids allowed to use the PA for this run
var events: Array = []             # comms_event records, in order (evaluator)
var _pending: Array = []           # messages waiting for their delivery to be known
var _device_queue: Array = []      # group messages and invitations for the next sample
var _pa_queue: Array = []          # announcements for the next sample
var _comms_counter := 0
var _group_counter := 0


func _init() -> void:
	name = "CommsRouter"


func setup(target_world: RangeWorld) -> void:
	world = target_world
	world.senses.extra_sources.append(_device_and_pa_items)
	world.senses.sampled.connect(_on_sampled)


# ---------- sending ----------

## Results are {"ok": bool, "reason_code": String, "event_id": String}.
## `amplitude` and `tempo` below 0 mean "not given" (D-56). With an addressee, the sender's head
## turns toward them while the gesture lasts (presentation only, D-54).
func send_gesture(sender: Avatar, gesture: String, addressee_id = null, sign_text := "",
		amplitude := -1.0, tempo := -1.0) -> Dictionary:
	if not sender.perform_gesture(gesture, "", amplitude, tempo):
		return _reject(sender, "GESTURE", "CAPABILITY_DENIED")
	var shown: Dictionary = sender.active_gesture(world.clock.tick)
	var expression := {"gesture": gesture}
	if sign_text != "":
		expression["sign_text"] = sign_text
	if addressee_id is String:
		sender.look_toward(addressee_id, int(shown["until_tick"]) - world.clock.tick + 30)
	var comm := _comm("GESTURE", sender, addressee_id, sign_text if sign_text != "" else "(%s)" % gesture, shown["event_id"])
	comm["expression"] = expression
	_pending.append({"comm": comm, "event_id": shown["event_id"], "until_tick": int(shown["until_tick"]), "seen": {}})
	return _ok(shown["event_id"])


## Show an expression from the catalog (EXPRESS, D-52) on the GESTURE channel: its gesture, glyph
## and light together. Whoever perceives any part (VISUAL_GESTURE or VISUAL_EXPRESSION, same
## event id) received it. Refused whole (CAPABILITY_DENIED) if the body lacks any part.
func send_expression(sender: Avatar, expression_id: String, addressee_id = null, amplitude := -1.0, tempo := -1.0) -> Dictionary:
	var expression: Dictionary = world.expressions.get(expression_id, {})
	if expression.is_empty():
		return _reject(sender, "GESTURE", "INVALID_SCHEMA")
	var event_id := world.next_event_id()
	var outcome := sender.show_expression(expression, event_id, amplitude, tempo)
	if outcome != "OK":
		return _reject(sender, "GESTURE", outcome)
	var shown: Dictionary = sender.active_expression(world.clock.tick)
	if addressee_id is String:
		sender.look_toward(addressee_id, int(shown["until_tick"]) - world.clock.tick)
	var obj := {"light": String(expression["light"]), "light_pattern": String(expression["light_pattern"])}
	if expression.has("gesture"):
		obj["gesture"] = String(expression["gesture"])
	if expression.has("glyph"):
		obj["glyph"] = String(expression["glyph"]["glyph_id"])
		obj["display"] = BeaconRules.glyph_display(sender.body)
	elif BeaconRules.light_display(sender.body) != "":
		obj["display"] = BeaconRules.light_display(sender.body)
	var comm := _comm("GESTURE", sender, addressee_id, "(%s)" % expression_id, event_id)
	comm["expression"] = obj
	_pending.append({"comm": comm, "event_id": event_id, "until_tick": int(shown["until_tick"]), "seen": {}})
	world.journal_write("EXPRESSION_SHOWN", sender.avatar_id, {"avatar_id": sender.avatar_id, "event_id": event_id,
		"expression_id": expression_id, "expression": obj, "hold_ms": int(expression["hold_ms"])})
	return _ok(event_id)


func send_local(sender: Avatar, text: String, addressee_id = null) -> Dictionary:
	var event_id := sender.say(text, addressee_id)
	if event_id == "":
		return _reject(sender, "LOCAL", "CAPABILITY_DENIED")
	if addressee_id is String:
		sender.look_toward(addressee_id, 120)
	_pending.append({"comm": _comm("LOCAL", sender, addressee_id, text, event_id), "event_id": event_id,
		"until_tick": world.clock.tick, "seen": {}})
	return _ok(event_id)


func pa_authorized(sender: Avatar) -> bool:
	return Layers.has_capability(sender.body, "can_use_pa") or pa_operators.has(sender.avatar_id)


func send_pa(sender: Avatar, text: String) -> Dictionary:
	if not pa_authorized(sender):
		return _reject(sender, "PA", "PA_UNAUTHORIZED")
	if pa_source() == null:
		return _reject(sender, "PA", "TARGET_UNKNOWN")
	var event_id := world.next_event_id()
	_pa_queue.append({"event_id": event_id, "text": text, "sender_id": sender.avatar_id})
	_pending.append({"comm": _comm("PA", sender, null, text, event_id), "event_id": event_id,
		"until_tick": world.clock.tick, "seen": {}})
	return _ok(event_id)


## Where announcements come from: the map's PA speaker, or null if the map has none.
func pa_source():
	for prop in world.registry["props"].values():
		if prop.get_meta("prop_type") == "PA_SPEAKER":
			return (prop as Node3D).global_position + Vector3.UP * 1.56
	return null


# ---------- groups ----------

func create_group(creator: Avatar, group_name: String) -> Dictionary:
	_group_counter += 1
	var group_id := "grp_%06d" % _group_counter
	groups[group_id] = {"name": group_name, "creator": creator.avatar_id, "members": [creator.avatar_id], "invited": []}
	_group_changed(group_id, "CREATED", creator.avatar_id, null)
	return {"ok": true, "reason_code": "OK", "event_id": group_id}


func is_member(avatar_id: String, group_id: String) -> bool:
	return groups.has(group_id) and groups[group_id]["members"].has(avatar_id)


func invite(sender: Avatar, group_id: String, invitee_id: String) -> Dictionary:
	if not is_member(sender.avatar_id, group_id):
		return _reject(sender, "GROUP", "GROUP_NOT_MEMBER")
	if not world.avatars.has(invitee_id):
		return _reject(sender, "GROUP", "TARGET_UNKNOWN")
	var g: Dictionary = groups[group_id]
	if not g["members"].has(invitee_id) and not g["invited"].has(invitee_id):
		g["invited"].append(invitee_id)
	var event_id := world.next_event_id()
	_device_queue.append({"recipient": invitee_id, "kind": "GROUP_INVITE", "event_id": event_id, "source": sender.avatar_id,
		"value": {"group_id": group_id, "group_name": g["name"]}})
	_group_changed(group_id, "INVITED", sender.avatar_id, invitee_id)
	return _ok(event_id)


func accept(invitee: Avatar, group_id: String) -> Dictionary:
	if not groups.has(group_id) or not groups[group_id]["invited"].has(invitee.avatar_id):
		return _reject(invitee, "GROUP", "GROUP_NOT_MEMBER")
	var g: Dictionary = groups[group_id]
	g["invited"].erase(invitee.avatar_id)
	g["members"].append(invitee.avatar_id)
	_group_changed(group_id, "ACCEPTED", invitee.avatar_id, null)
	return _ok(group_id)


func decline(invitee: Avatar, group_id: String) -> Dictionary:
	if not groups.has(group_id) or not groups[group_id]["invited"].has(invitee.avatar_id):
		return _reject(invitee, "GROUP", "GROUP_NOT_MEMBER")
	groups[group_id]["invited"].erase(invitee.avatar_id)
	_group_changed(group_id, "DECLINED", invitee.avatar_id, null)
	return _ok(group_id)


func leave(member: Avatar, group_id: String) -> Dictionary:
	if not is_member(member.avatar_id, group_id):
		return _reject(member, "GROUP", "GROUP_NOT_MEMBER")
	groups[group_id]["members"].erase(member.avatar_id)
	_device_queue = _device_queue.filter(func(d: Dictionary) -> bool:
		return not (d["recipient"] == member.avatar_id and d["value"].get("group_id") == group_id))
	_group_changed(group_id, "LEFT", member.avatar_id, null)
	return _ok(group_id)


func send_group(sender: Avatar, group_id: String, text: String) -> Dictionary:
	if not is_member(sender.avatar_id, group_id):
		return _reject(sender, "GROUP", "GROUP_NOT_MEMBER")
	var event_id := world.next_event_id()
	for member_id in groups[group_id]["members"]:
		if member_id != sender.avatar_id:
			_device_queue.append({"recipient": member_id, "kind": "GROUP_MESSAGE", "event_id": event_id,
				"source": sender.avatar_id, "value": {"group_id": group_id, "text": text}})
	var comm := _comm("GROUP", sender, null, text, event_id)
	comm["group_id"] = group_id
	_pending.append({"comm": comm, "event_id": event_id, "until_tick": world.clock.tick, "seen": {}})
	return _ok(event_id)


## Ids a member legitimately knows through its groups: co-members and whoever invited it.
func known_ids(avatar_id: String) -> Dictionary:
	var known := {}
	for g in groups.values():
		if g["members"].has(avatar_id) or g["invited"].has(avatar_id):
			for m in g["members"]:
				known[m] = true
	return known


# ---------- delivery ----------

## Called by the observer filter for each observer at each sample.
func _device_and_pa_items(observer: Avatar, now_ms: int) -> Array:
	var items := []
	var eye := SenseModel.sensor_origin(observer)
	for d in _device_queue:
		if d["recipient"] != observer.avatar_id:
			continue
		var item := world.senses.make_item(d["kind"], d["event_id"], null, observer, eye, null, d["value"], now_ms,
			"OBSERVED", 1.0, DEVICE_PROVENANCE)
		# Members know each other through the group (invitation and acceptance), so the sender
		# is named: an introduction, not simulator knowledge.
		item["source_entity_id"] = d["source"]
		items.append(item)
	var source = pa_source()
	for p in _pa_queue:
		if source == null or p["sender_id"] == observer.avatar_id or not _in_pa_coverage(observer):
			continue
		items.append(world.senses.make_item("AUDIO_SPEECH", p["event_id"], null, observer, eye, source,
			{"channel": "PA", "text": p["text"], "addressed_to_observer": null}, now_ms, "OBSERVED", 1.0, PA_PROVENANCE))
	return items


## PA coverage: the whole map (Sandbox Flats has one speaker covering the hall).
func _in_pa_coverage(a: Avatar) -> bool:
	var bounds: Vector2 = world.registry["bounds"]
	return a.global_position.x >= 0 and a.global_position.x <= bounds.x and a.global_position.z >= 0 and a.global_position.z <= bounds.y


func _on_sampled(tick: int, packets: Dictionary) -> void:
	var still: Array = []
	for p in _pending:
		for observer_id in packets:
			for item in packets[observer_id]["observations"]:
				if item["event_id"] == p["event_id"]:
					p["seen"][observer_id] = true
		if tick >= int(p["until_tick"]):
			_finish(p)
		else:
			still.append(p)
	_pending = still
	_device_queue.clear()
	_pa_queue.clear()


func _finish(p: Dictionary) -> void:
	var comm: Dictionary = p["comm"]
	var delivered: Array = p["seen"].keys()
	delivered.sort()
	var others := []
	for avatar_id in world.avatars.keys():
		if avatar_id != comm["sender_id"] and not p["seen"].has(avatar_id):
			others.append(avatar_id)
	others.sort()
	comm["delivered_to"] = delivered
	comm["not_delivered_to"] = others
	events.append(comm)
	world.journal_write("COMMS_EVENT", comm["sender_id"], comm)


func _comm(channel: String, sender: Avatar, addressee_id, text: String, event_id: String) -> Dictionary:
	_comms_counter += 1
	var modality := {"GESTURE": "SIMULATED_GESTURE", "LOCAL": "SIMULATED_TEXT_SPEECH", "GROUP": "DEVICE_MESSAGE",
		"PA": "PA_ANNOUNCEMENT"}
	var scope := {"GESTURE": "VISUAL_FOV_LOS", "LOCAL": "ACOUSTIC_AREA", "GROUP": "GROUP_MEMBERS", "PA": "PA_ZONES"}
	return {
		"schema_version": "1.0",
		"comms_id": "comms_%06d" % _comms_counter,
		"channel": channel,
		"sender_id": sender.avatar_id,
		"addressee_id": addressee_id,
		"text": text,
		"emitted_at_tick": world.clock.tick,
		"emitted_at_ms": SimClock.ms_at(world.clock.tick),
		"modality": modality[channel],
		"delivery_scope": scope[channel],
		"group_id": null,
		"delivered_to": [],
		"not_delivered_to": [],
		"source_event_id": event_id,
	}


func _group_changed(group_id: String, op: String, actor_id: String, subject_id) -> void:
	world.journal_write("GROUP_CHANGED", actor_id, {"group_id": group_id, "op": op, "actor_id": actor_id,
		"subject_id": subject_id, "member_ids": groups[group_id]["members"].duplicate()})


func _ok(event_id: String) -> Dictionary:
	return {"ok": true, "reason_code": "OK", "event_id": event_id}


func _reject(sender: Avatar, channel: String, reason_code: String) -> Dictionary:
	world.journal_write("COMMS_REJECTED", sender.avatar_id, {"sender_id": sender.avatar_id, "channel": channel,
		"reason_code": reason_code})
	return {"ok": false, "reason_code": reason_code, "event_id": ""}
