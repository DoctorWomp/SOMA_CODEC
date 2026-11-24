class_name ObserverFilter
extends Node
## Builds each avatar's observation packet (contracts/observation.schema.json) from what its
## simulated senses could perceive (D-39, D-40). Runs after every avatar has moved, every
## 60 / sample_hz physics ticks; packets carry the 60 Hz tick (D-33).
##
## Rules:
## - A target the observer has never seen is absent: a packet never reveals that someone
##   hidden exists.
## - Seen with every sampled part → OBSERVED; some parts → DEGRADED / PARTLY_OCCLUDED.
## - Seen before, not now, within TRACK_TTL_MS → OCCLUDED (blocked) or MISSING (left the field of
##   view or range), at the last known position, with no quality: missing is never zero.
## - Track ids are anonymous, random and per observer; source_entity_id stays null until
##   identity is legitimately introduced (G3+).
## - Speech is an event: delivered once, at the first sample after it was spoken, to those who
##   could hear it then. Nothing is backfilled.

signal sampled(tick: int, packets: Dictionary)

const TRACK_TTL_MS := 3000
## Expressions (G3a, D-52): a glyph is readable within 8 m (times the zone's visual range factor),
## a visor glyph only from within 75 degrees of the visor's facing, a light-strip symbol within
## 110 degrees. Ear-pod lights show from every side; a quadruped's strip light within 110 degrees.
const GLYPH_LEGIBLE_RANGE_M := 8.0
const VISOR_VIEW_COS := 0.2588     # cos 75 deg
const STRIP_VIEW_COS := -0.3420    # cos 110 deg
const EXPIRES_AFTER_MS := 1000
const VISUAL_PROVENANCE := "synthetic_visual_multipoint_v1"
const AUDIO_PROVENANCE := "synthetic_acoustic_v1"

var world: RangeWorld
var latest: Dictionary = {}        # observer id -> last packet
## For the spectator UI only: the last speech each avatar heard, {"text", "ms", "validity"}.
var last_heard: Dictionary = {}
## Other senders of perceivable items (the COMMS router: device messages, PA). Each is called as
## source.call(observer: Avatar, now_ms: int) -> Array of observation items, at every sample.
var extra_sources: Array[Callable] = []
var _tracks: Dictionary = {}       # observer id -> {target id -> {"track_id", "last_seen_ms", "last_pos"}}
## EVALUATOR ONLY (G4a, D-93): every track id ever issued, never dropped: observer -> {track id -> avatar id}.
var _issued: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _obs_counter := 0
var _last_sample_tick := -1


func _init() -> void:
	name = "ObserverFilter"
	process_physics_priority = 100   # after avatars and scripted controllers


func setup(target_world: RangeWorld, seed_value: int) -> void:
	world = target_world
	_rng.seed = seed_value


func _physics_process(_delta: float) -> void:
	if world == null or world.clock == null or not world.sensing_enabled:
		return
	if world.clock.tick % world.sample_period_ticks() == 0 and world.clock.tick != _last_sample_tick:
		sample()


## Observe for every avatar now. Returns {observer id: packet}.
func sample() -> Dictionary:
	var tick := world.clock.tick
	var packets := {}
	for observer in world.avatar_list():
		packets[(observer as Avatar).avatar_id] = observe(observer)
	world.clear_spoken_before(tick)
	_last_sample_tick = tick
	latest = packets
	for observer_id in packets:
		world.journal_write("OBSERVATION_DELIVERED", observer_id, packets[observer_id])
	sampled.emit(tick, packets)
	return packets


## One observer's packet for the current tick.
func observe(observer: Avatar) -> Dictionary:
	var tick := world.clock.tick
	var now_ms := SimClock.ms_at(tick)
	var eye := SenseModel.sensor_origin(observer)
	var tracks: Dictionary = _tracks.get(observer.avatar_id, {})
	_tracks[observer.avatar_id] = tracks
	var items: Array = []
	var seen_now := {}
	for target in world.avatar_list():
		var t := target as Avatar
		if t == observer:
			continue
		var gesture := t.active_gesture(tick)
		var visual_range := float(observer.body["sensors"]["visual_range_m"]) * world.visual_range_factor(observer.global_position, t.global_position)
		var seen := SenseModel.look(observer, t, visual_range, String(gesture.get("gesture", "")))
		var visible: Array = seen["visible"]
		var body_parts := visible.filter(func(part: String) -> bool: return part != "HAND")
		if not visible.is_empty():
			var track := _track(tracks, t.avatar_id)
			track["last_seen_ms"] = now_ms
			track["last_pos"] = t.global_position
			seen_now[t.avatar_id] = track["track_id"]
			var quality := _visual_quality(eye, t, visual_range, body_parts.size() if not body_parts.is_empty() else 1)
			var presence := _item("VISUAL_PRESENCE", null, track["track_id"], observer, eye, t.global_position, {}, now_ms,
				"OBSERVED" if body_parts.size() == SenseModel.PARTS.size() else "DEGRADED", quality, VISUAL_PROVENANCE)
			if body_parts.size() < SenseModel.PARTS.size():
				presence["validity_reason"] = "PARTLY_OCCLUDED"
			presence["visible_parts"] = visible.duplicate()
			items.append(presence)
			if not gesture.is_empty() and visible.has("HAND") \
					and eye.distance_to(seen["points"]["HAND"]) <= SenseModel.GESTURE_LEGIBLE_RANGE_M * world.visual_range_factor(observer.global_position, t.global_position):
				# Toward whom a gesture is made follows the gesturer's head (D-72).
				var facing := SenseModel.head_forward_of(t).dot((observer.global_position - t.global_position).normalized())
				var g := _item("VISUAL_GESTURE", gesture["event_id"], track["track_id"], observer, eye, t.global_position,
					{"gesture": gesture["gesture"], "direction": "TOWARD_OBSERVER" if facing > 0.5 else "AWAY_FROM_OBSERVER"},
					now_ms, "OBSERVED", quality, VISUAL_PROVENANCE)
				items.append(g)
			var shown := t.active_expression(tick)
			if not shown.is_empty() and visible.has("HEAD"):
				var e := _expression_item(observer, eye, t, shown, seen["points"]["HEAD"], track["track_id"], now_ms, quality)
				if not e.is_empty():
					items.append(e)
		elif tracks.has(t.avatar_id):
			var track: Dictionary = tracks[t.avatar_id]
			if now_ms - int(track["last_seen_ms"]) > TRACK_TTL_MS:
				tracks.erase(t.avatar_id)
				continue
			var lost := _item("VISUAL_PRESENCE", null, track["track_id"], observer, eye, track["last_pos"], {},
				int(track["last_seen_ms"]), "OCCLUDED", null, VISUAL_PROVENANCE)
			lost["expires_at_ms"] = int(track["last_seen_ms"]) + TRACK_TTL_MS
			if seen["in_view"]:
				lost["validity_reason"] = "OCCLUDED_SINCE_LAST_SEEN"
			else:
				lost["validity"] = "MISSING"
				lost["validity_reason"] = "LEFT_FIELD_OF_VIEW" if seen["in_range"] else "OUT_OF_RANGE"
			lost["visible_parts"] = []
			items.append(lost)
	for source in extra_sources:
		items.append_array(source.call(observer, now_ms))
	for speech in world.spoken_since(_last_sample_tick):
		var item := _speech_item(observer, eye, speech, seen_now, tracks, now_ms)
		if not item.is_empty():
			items.append(item)
			last_heard[observer.avatar_id] = {"text": speech["text"], "ms": now_ms, "validity": item["validity"]}
	var pose := {"x": _r(observer.global_position.x), "y": _r(observer.global_position.y),
		"z": _r(observer.global_position.z), "yaw_rad": _r(wrapf(observer.rotation.y, -PI, PI))}
	if observer.has_neck():
		# Own head pose (D-72): relative to the body, so bearings stay relative to the body.
		pose["head_yaw_rad"] = _r(observer.head_yaw)
		pose["head_pitch_rad"] = _r(observer.head_pitch)
	var issued: Dictionary = _issued.get(observer.avatar_id, {})   # evaluator only (truth_tracks)
	_issued[observer.avatar_id] = issued
	for target_id in tracks:
		issued[String(tracks[target_id]["track_id"])] = String(target_id)
	return {
		"schema_version": "1.0",
		"observer_id": observer.avatar_id,
		"based_on_tick_id": tick,
		"sim_time_ms": now_ms,
		"coordinate_frame": "world_meters_xyz",
		"observer_pose": pose,
		"observations": items,
	}


func _speech_item(listener: Avatar, eye: Vector3, speech: Dictionary, seen_now: Dictionary, tracks: Dictionary, now_ms: int) -> Dictionary:
	if speech["speaker_id"] == listener.avatar_id or not world.avatars.has(speech["speaker_id"]):
		return {}
	var speaker: Avatar = world.avatars[speech["speaker_id"]]
	var mouth := SenseModel.mouth_of(speaker)
	var heard := SenseModel.hear(world, mouth, listener, float(speech["level_db"]))
	if not heard["heard"]:
		return {}
	var addressee = speech["addressee_id"]
	var value := {"channel": "LOCAL", "text": speech["text"],
		"addressed_to_observer": null if addressee == null else addressee == listener.avatar_id}
	var quality := clampf(float(heard["snr_db"]) / 20.0, 0.05, 1.0)
	var reason := ""
	if float(heard["wall_loss_db"]) > 0.0:
		reason = "THROUGH_WALL"
	elif float(heard["snr_db"]) < SenseModel.CLEAR_SPEECH_SNR_DB:
		reason = "LOW_SIGNAL_TO_NOISE"
	var item: Dictionary
	if seen_now.has(speaker.avatar_id):
		item = _item("AUDIO_SPEECH", speech["event_id"], tracks[speaker.avatar_id]["track_id"], listener, eye,
			speaker.global_position, value, now_ms, "OBSERVED" if reason == "" else "DEGRADED", quality, AUDIO_PROVENANCE)
	else:
		# Heard but not seen: a direction, no position and no track (UNKNOWN_SOURCE).
		item = _item("AUDIO_SPEECH", speech["event_id"], null, listener, eye, mouth, value, now_ms,
			"UNKNOWN_SOURCE", quality, AUDIO_PROVENANCE)
		item["position_estimate"] = null
		item["range_m"] = null
		if reason == "":
			reason = "SPEAKER_NOT_IN_VIEW"
	if reason != "":
		item["validity_reason"] = reason
	return item


## EVALUATOR ONLY (tests, journal analysis): which anonymous track an observer uses for a
## target. Never part of anything an agent receives.
func track_id_for(observer_id: String, target_id: String) -> String:
	var tracks: Dictionary = _tracks.get(observer_id, {})
	return String(tracks[target_id]["track_id"]) if tracks.has(target_id) else ""


## HOST ONLY (action gate): which avatar an observer's anonymous track refers to, or "".
func entity_for_track(observer_id: String, track_id: String) -> String:
	var tracks: Dictionary = _tracks.get(observer_id, {})
	for target_id in tracks:
		if tracks[target_id]["track_id"] == track_id:
			return String(target_id)
	return ""


## EVALUATOR ONLY (G4a, D-93): every track each observer was ever given, including tracks since
## dropped, as {observer id: {track id: avatar id}}. Read through the world dispatcher (Evaluator
## seat) or written at run end to viewer/truth_tracks.json; never in the journal or a packet.
func truth_tracks() -> Dictionary:
	var out := {}
	var observers := _issued.keys()
	observers.sort()
	for observer_id in observers:
		out[String(observer_id)] = (_issued[observer_id] as Dictionary).duplicate()
	return out


func _track(tracks: Dictionary, target_id: String) -> Dictionary:
	if not tracks.has(target_id):
		var token := ""
		for i in 10:
			token += "abcdefghijklmnopqrstuvwxyz0123456789"[_rng.randi_range(0, 35)]
		tracks[target_id] = {"track_id": "anon_" + token, "last_seen_ms": 0, "last_pos": Vector3.ZERO}
	return tracks[target_id]


func _visual_quality(eye: Vector3, t: Avatar, visual_range: float, parts_seen: int) -> float:
	var fraction := float(parts_seen) / SenseModel.PARTS.size()
	var distance_factor := 1.0 - 0.5 * clampf(eye.distance_to(t.global_position) / visual_range, 0.0, 1.0)
	var light := float(world.environment_at(t.global_position)["light_level"])
	return _r(clampf(fraction * distance_factor * (0.5 + 0.5 * light), 0.0, 1.0))


## What `observer` can make out of the expression `t` is showing, under the same sight rules as
## everything else: the display (HEAD point) must be in view and unblocked. Returns {} if nothing.
func _expression_item(observer: Avatar, eye: Vector3, t: Avatar, shown: Dictionary, head: Vector3, track_id: String,
		now_ms: int, quality) -> Dictionary:
	var to_observer := Vector3(eye.x - head.x, 0, eye.z - head.z).normalized()
	var facing := SenseModel.head_forward_of(t).dot(to_observer)   # the visor turns with the head (D-72)
	var glyph_display := BeaconRules.glyph_display(t.body)
	var light_display := BeaconRules.light_display(t.body)
	var factor := world.visual_range_factor(observer.global_position, t.global_position)
	var legible: bool = String(shown["glyph_id"]) != "" and eye.distance_to(head) <= GLYPH_LEGIBLE_RANGE_M * factor \
		and facing >= (VISOR_VIEW_COS if glyph_display == "VISOR" else STRIP_VIEW_COS)
	var lit: bool = String(shown["light"]) != "OFF" and (light_display == "EAR_PODS" or facing >= STRIP_VIEW_COS)
	if not legible and not lit:
		return {}
	var value := {}
	if legible:
		value["glyph"] = shown["glyph_id"]
		value["display"] = glyph_display
	if lit:
		value["light"] = shown["light"]
		value["light_pattern"] = shown["light_pattern"]
		if not legible:
			value["display"] = light_display
	return _item("VISUAL_EXPRESSION", shown["event_id"], track_id, observer, eye, t.global_position, value, now_ms,
		"OBSERVED", quality, VISUAL_PROVENANCE)


func _item(kind: String, event_id, track_id, observer: Avatar, eye: Vector3, at, value: Dictionary,
		observed_ms: int, validity: String, quality, provenance: String) -> Dictionary:
	return make_item(kind, event_id, track_id, observer, eye, at, value, observed_ms, validity, quality, provenance)


## Build one observation item. `at` (Vector3) is where the source is perceived, or null when
## it cannot be located (device messages): then position, bearing and range are null.
func make_item(kind: String, event_id, track_id, observer: Avatar, eye: Vector3, at, value: Dictionary,
		observed_ms: int, validity: String, quality, provenance: String) -> Dictionary:
	_obs_counter += 1
	var position = null
	var bearing_rad = null
	var range_m = null
	if at is Vector3:
		position = {"x": _r(at.x), "y": _r(at.y), "z": _r(at.z)}
		bearing_rad = _r(SenseModel.bearing(observer, eye, at))
		range_m = _r(Vector2(at.x - eye.x, at.z - eye.z).length())
	return {
		"observation_id": "obs_%06d" % _obs_counter,
		"event_id": event_id,
		"kind": kind,
		"track_id": track_id,
		"source_entity_id": null,
		"position_estimate": position,
		"bearing_rad": bearing_rad,
		"range_m": range_m,
		"value": value,
		"observed_at_ms": observed_ms,
		"expires_at_ms": observed_ms + EXPIRES_AFTER_MS,
		"validity": validity,
		"quality": quality,
		"provenance": provenance,
	}


static func _r(x: float) -> float:
	return snappedf(x, 0.0001)
