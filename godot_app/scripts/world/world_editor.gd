class_name WorldEditor
extends Node
## The World Director's hands in the world (G4b, D-99, D-100): props placed, moved and removed
## while a run goes. Godot stays the only world authority (D-04): every change is checked here
## and refused with a reason when it cannot be made.
##
## Refused: OFF_MAP (the footprint leaves the map), INSIDE_WALL (it overlaps a wall, the
## platform, the stairs or ramp, or another prop), ON_AVATAR (it overlaps a body, with a margin),
## BLOCKS_ROUTE (an avatar could reach a spawn point or another avatar before and not after: tested
## on scratch navigation maps for every body size, D-37), UNKNOWN_PROP, NOT_FOUND.
##
## Placed props collide; a blocking prop's footprint is cut out of every size's navigation mesh,
## applied in the same tick (synchronous, D-47). Shared avoidance (D-42) is unchanged: it steers
## bodies around each other; props are in the navigation meshes.
##
## Perception, through the observer filter only (ART_DIRECTION §5; registered as an extra source):
## - a SIGN's text (SIGN_TEXT) within its legible range (SIGN_LEGIBLE_M, scaled by the zone's light
##   level and visual range factor), inside the head's field of view, from in front of the sign
##   (within FRONT_HALF_ANGLE of its face), with a clear line of sight; a NOTE only up close;
## - a SOUND_SOURCE (AUDIO_SOUND) while it plays, through the hearing model (distance, walls, noise
##   floor): its class and the level heard, a bearing, no position (a sound is not a place).
## Nothing is perceived from a prop until one is placed, so runs without interventions are unchanged.

const SIGN_LEGIBLE_M := 6.0
const NOTE_LEGIBLE_M := 2.0        # eye to a sheet on the floor (a standing person is ~1.7 m away)
const FRONT_HALF_ANGLE_DEG := 75.0
const AVATAR_MARGIN_M := 0.3
const EDGE_MARGIN_M := 0.2
const SIGN_PROVENANCE := "synthetic_text_legibility_v1"
const SOUND_PROVENANCE := "synthetic_acoustic_v1"
const SOUND_CLASSES := ["LAUGHTER", "APPLAUSE", "MUSIC", "IMPACT", "MACHINE", "UNKNOWN"]
const TEXT_PROPS := ["SIGN", "NOTE"]
const PLACEABLE := ["SIGN", "NOTE", "BARRIER", "CONE", "CRATE", "SOUND_SOURCE"]

var world: RangeWorld
var placed: Dictionary = {}       # prop id -> {"node": StaticBody3D, "prop": {...}, "event_id", "until_tick"}
var _root: Node3D


func _init() -> void:
	name = "WorldEditor"


func setup(target_world: RangeWorld) -> void:
	world = target_world
	_root = Node3D.new()
	_root.name = "PlacedProps"
	world.add_child(_root)
	world.senses.extra_sources.append(_perceived)


## Place a prop. `prop`: {"prop_id", "prop_type", "x", "z", "yaw_rad", "text"?, "sound_class"?,
## "level_db"?, "duration_s"?}. Returns {"code", "after"} (after: the prop as placed, as JSON text).
func place(prop: Dictionary) -> Dictionary:
	var prop_type := String(prop.get("prop_type", ""))
	if not PLACEABLE.has(prop_type):
		return {"code": "UNKNOWN_PROP", "detail": "unknown prop '%s'" % prop_type}
	var p := _normalized(prop)
	var problem := _check(p, "")
	if problem["code"] != "OK":
		return problem
	if MapBuilder.NAV_BLOCKING.has(prop_type):
		var meshes := world.bake_with_obstructions(_footprints("", p))
		var blocked := world.routes_blocked(meshes)
		if blocked != "":
			return {"code": "BLOCKS_ROUTE", "detail": blocked}
		_add(p)
		world.apply_navmeshes(meshes)
	else:
		_add(p)
	return {"code": "OK", "after": _describe(p)}


func move(prop_id: String, x: float, z: float, yaw = null) -> Dictionary:
	if not placed.has(prop_id):
		return {"code": "NOT_FOUND", "detail": "no placed prop '%s'" % prop_id}
	var old: Dictionary = placed[prop_id]["prop"]
	var p := old.duplicate()
	p["x"] = x
	p["z"] = z
	if yaw != null:
		p["yaw_rad"] = float(yaw)
	var problem := _check(p, prop_id)
	if problem["code"] != "OK":
		return problem
	var meshes := {}
	if MapBuilder.NAV_BLOCKING.has(String(p["prop_type"])):
		meshes = world.bake_with_obstructions(_footprints(prop_id, p))
		var blocked := world.routes_blocked(meshes)
		if blocked != "":
			return {"code": "BLOCKS_ROUTE", "detail": blocked}
	var keep_event = placed[prop_id].get("event_id")
	var keep_until = placed[prop_id].get("until_tick")
	_remove_node(prop_id)
	_add(p)
	placed[prop_id]["event_id"] = keep_event
	placed[prop_id]["until_tick"] = keep_until
	if not meshes.is_empty():
		world.apply_navmeshes(meshes)
	return {"code": "OK", "before": _describe(old), "after": _describe(p)}


func remove(prop_id: String) -> Dictionary:
	if not placed.has(prop_id):
		return {"code": "NOT_FOUND", "detail": "no placed prop '%s'" % prop_id}
	var old: Dictionary = placed[prop_id]["prop"]
	_remove_node(prop_id)
	if MapBuilder.NAV_BLOCKING.has(String(old["prop_type"])):
		world.apply_navmeshes(world.bake_with_obstructions(_footprints("", {})))
	return {"code": "OK", "before": _describe(old)}


func _normalized(prop: Dictionary) -> Dictionary:
	var p := {"prop_id": String(prop["prop_id"]), "prop_type": String(prop["prop_type"]),
		"x": snappedf(float(prop["x"]), 0.01), "z": snappedf(float(prop["z"]), 0.01),
		"yaw_rad": snappedf(float(prop.get("yaw_rad", 0.0)), 0.0001)}
	if TEXT_PROPS.has(p["prop_type"]):
		p["text"] = String(prop.get("text", ""))
	if p["prop_type"] == "SOUND_SOURCE":
		var sc := String(prop.get("sound_class", "MUSIC"))
		p["sound_class"] = sc if SOUND_CLASSES.has(sc) else "UNKNOWN"
		p["level_db"] = clampf(float(prop.get("level_db", 70.0)), 30.0, 110.0)
		p["duration_s"] = maxf(float(prop.get("duration_s", 0.0)), 0.0)
	return p


func _check(p: Dictionary, moving_id: String) -> Dictionary:
	var center := Vector2(float(p["x"]), float(p["z"]))
	var bounds: Vector2 = world.registry["bounds"]
	for c in MapBuilder.prop_footprint(String(p["prop_type"]), center, float(p["yaw_rad"])):
		if c.x < EDGE_MARGIN_M or c.y < EDGE_MARGIN_M or c.x > bounds.x - EDGE_MARGIN_M or c.y > bounds.y - EDGE_MARGIN_M:
			return {"code": "OFF_MAP", "detail": "the footprint leaves the map at (%.1f, %.1f)" % [c.x, c.y]}
	var size: Vector3 = MapBuilder.PROP_SIZES[p["prop_type"]]
	var space := world.get_world_3d().direct_space_state
	var shape := BoxShape3D.new()
	var exclude: Array[RID] = []
	if moving_id != "":
		exclude.append((placed[moving_id]["node"] as StaticBody3D).get_rid())
	# Structure: anything solid from just above the floor (walls, platform, stairs, ramp, props).
	shape.size = Vector3(size.x, maxf(size.y, 0.3), size.z)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	var ground := world.ground_height(center.x, center.y)      # on the floor or on the platform
	q.transform = Transform3D(Basis(Vector3.UP, float(p["yaw_rad"])), Vector3(center.x, ground + 0.06 + shape.size.y / 2, center.y))
	q.collision_mask = Layers.WORLD | Layers.STAIRS_WALK_SURFACE | Layers.STAIRS_STEPS
	q.exclude = exclude
	if not space.intersect_shape(q, 1).is_empty():
		return {"code": "INSIDE_WALL", "detail": "it would overlap a wall, the platform, the stairs or ramp, or another prop"}
	for other_id in placed:
		if other_id != moving_id and String(placed[other_id]["prop"]["prop_type"]) == "NOTE" and p["prop_type"] == "NOTE":
			var o: Dictionary = placed[other_id]["prop"]
			if Vector2(float(o["x"]), float(o["z"])).distance_to(center) < 0.3:
				return {"code": "INSIDE_WALL", "detail": "another note lies there"}
	shape.size = Vector3(size.x + 2 * AVATAR_MARGIN_M, 2.0, size.z + 2 * AVATAR_MARGIN_M)
	q.transform = Transform3D(Basis(Vector3.UP, float(p["yaw_rad"])), Vector3(center.x, ground + 1.0, center.y))
	q.collision_mask = Layers.AVATARS
	if not space.intersect_shape(q, 1).is_empty():
		return {"code": "ON_AVATAR", "detail": "a body stands there (with a %.1f m margin)" % AVATAR_MARGIN_M}
	return {"code": "OK"}


## The footprints of every blocking placed prop, with `p` in place of `replacing` (or added).
func _footprints(replacing: String, p: Dictionary) -> Array:
	var out := []
	var ids := placed.keys()
	ids.sort()
	for prop_id in ids:
		if prop_id == replacing:
			continue
		var q: Dictionary = placed[prop_id]["prop"]
		if MapBuilder.NAV_BLOCKING.has(String(q["prop_type"])):
			out.append(MapBuilder.prop_footprint(String(q["prop_type"]), Vector2(float(q["x"]), float(q["z"])), float(q["yaw_rad"])))
	if not p.is_empty() and MapBuilder.NAV_BLOCKING.has(String(p["prop_type"])):
		out.append(MapBuilder.prop_footprint(String(p["prop_type"]), Vector2(float(p["x"]), float(p["z"])), float(p["yaw_rad"])))
	return out


func _add(p: Dictionary) -> void:
	var data := p.duplicate()
	data["position"] = {"x": float(p["x"]), "z": float(p["z"])}
	var node := MapBuilder.build_placed_prop(_root, data, world.map_data)
	node.set_meta("placed", true)
	var entry := {"node": node, "prop": p, "event_id": null, "until_tick": null}
	if p["prop_type"] == "SOUND_SOURCE":
		entry["event_id"] = world.next_event_id()
		entry["until_tick"] = world.clock.tick + roundi(float(p["duration_s"]) * SimClock.TICK_HZ) if float(p["duration_s"]) > 0 else -1
	elif TEXT_PROPS.has(p["prop_type"]):
		entry["event_id"] = world.next_event_id()
	placed[String(p["prop_id"])] = entry


func _remove_node(prop_id: String) -> void:
	var node: Node = placed[prop_id]["node"]
	_root.remove_child(node)
	node.free()
	placed.erase(prop_id)


static func _describe(p: Dictionary) -> String:
	return JSON.stringify(p, "", true)


# ---------- perception (an extra source of the observer filter) ----------

func _perceived(observer: Avatar, now_ms: int) -> Array:
	var items: Array = []
	if placed.is_empty():
		return items
	var eye := SenseModel.sensor_origin(observer)
	var ids := placed.keys()
	ids.sort()
	for prop_id in ids:
		var entry: Dictionary = placed[prop_id]
		var p: Dictionary = entry["prop"]
		match String(p["prop_type"]):
			"SIGN", "NOTE":
				var item := _text_item(observer, eye, entry, now_ms)
				if not item.is_empty():
					items.append(item)
			"SOUND_SOURCE":
				var item := _sound_item(observer, entry, now_ms)
				if not item.is_empty():
					items.append(item)
	return items


func _text_item(observer: Avatar, eye: Vector3, entry: Dictionary, now_ms: int) -> Dictionary:
	var p: Dictionary = entry["prop"]
	var node: StaticBody3D = entry["node"]
	var is_sign := String(p["prop_type"]) == "SIGN"
	var at := node.global_position + Vector3.UP * (1.4 if is_sign else 0.02)
	var env := world.environment_at(at)
	var legible := (SIGN_LEGIBLE_M if is_sign else NOTE_LEGIBLE_M) * clampf(float(env.get("light_level", 1.0)), 0.0, 1.0) \
		* world.visual_range_factor(observer.global_position, at)
	var d := eye.distance_to(at)
	if d > legible:
		return {}
	var half_fov := deg_to_rad(float(observer.body["sensors"]["fov_deg"])) / 2
	if absf(wrapf(SenseModel.bearing(observer, eye, at) - observer.head_yaw, -PI, PI)) > half_fov:
		return {}
	if is_sign:
		var yaw := float(p["yaw_rad"])
		var front := Vector3(-sin(yaw), 0, -cos(yaw))
		var to_eye := Vector3(eye.x - at.x, 0, eye.z - at.z).normalized()
		if front.dot(to_eye) < cos(deg_to_rad(FRONT_HALF_ANGLE_DEG)):
			return {}
	var exclude: Array[RID] = [observer.get_rid(), node.get_rid()]
	if not SenseModel.clear_line(observer.get_world_3d().direct_space_state, eye, at, exclude):
		return {}
	var quality := snappedf(clampf(1.0 - d / maxf(legible, 0.01), 0.1, 1.0), 0.0001)
	return world.senses.make_item("SIGN_TEXT", entry["event_id"], null, observer, eye, at, {"text": String(p["text"])},
		now_ms, "OBSERVED", quality, SIGN_PROVENANCE)


func _sound_item(observer: Avatar, entry: Dictionary, now_ms: int) -> Dictionary:
	var until := int(entry["until_tick"])
	if until >= 0 and world.clock.tick > until:
		return {}
	var p: Dictionary = entry["prop"]
	var source := (entry["node"] as Node3D).global_position + Vector3.UP * 0.6
	var heard := SenseModel.hear(world, source, observer, float(p["level_db"]))
	if not heard["heard"]:
		return {}
	var eye := SenseModel.sensor_origin(observer)
	var clear := float(heard["snr_db"]) >= SenseModel.CLEAR_SPEECH_SNR_DB
	var item := world.senses.make_item("AUDIO_SOUND", entry["event_id"], null, observer, eye, source,
		{"sound_class": String(p["sound_class"]), "level_db": snappedf(maxf(float(heard["level_db"]), 0.0), 0.1)},
		now_ms, "OBSERVED" if clear else "DEGRADED", snappedf(clampf(float(heard["snr_db"]) / 20.0, 0.05, 1.0), 0.0001),
		SOUND_PROVENANCE)
	item["position_estimate"] = null       # a sound is heard from a direction, not located
	item["range_m"] = null
	if not clear:
		item["validity_reason"] = "LOW_SIGNAL_TO_NOISE"
	return item
