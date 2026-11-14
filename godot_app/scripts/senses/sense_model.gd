class_name SenseModel
extends RefCounted
## Synthetic senses (D-16, D-39, D-40): what an observer could see and hear, from world state.
## Simple, labeled proxies, not models of real optics or acoustics; realism is a dial for later.
##
## Sight: rays from the observer's sensor (its mount height, D-36) to several points on the
## target. Each point needs range, field of view and a clear line. Walls (unless
## blocks_sight is false), the platform, props, steps and other avatars block sight.
## Hearing: level falls 20·log10(distance); each wall on the way takes some off; the
## listener's zone noise floor masks it.

const PARTS := ["HEAD", "TORSO", "LEFT_SIDE", "RIGHT_SIDE"]
const SIGHT_MASK := Layers.WORLD | Layers.AVATARS | Layers.STAIRS_STEPS
const GESTURE_LEGIBLE_RANGE_M := 12.0

## Gestures shown with a raised hand, a hand held forward, the head, or the whole torso.
const RAISED_HAND_GESTURES := ["WAVE", "SMALL_WAVE", "RAISED_HAND", "BECKON"]
const FORWARD_HAND_GESTURES := ["POINT", "OPEN_PALM", "HAND_OVER"]
const HEAD_GESTURES := ["NOD", "SHAKE_HEAD", "HEAD_TILT"]

const SPEECH_LEVEL_DB := 62.0      # conversational voice at 1 m, in a busy hall
const WALL_LOSS_DB := 30.0         # a wall that blocks sound
const PARTITION_LOSS_DB := 6.0     # a wall sound passes over (partitions, dividers)
const CLEAR_SPEECH_SNR_DB := 6.0   # below this, speech is weakened (DEGRADED)


static func forward_of(a: Node3D) -> Vector3:
	return Vector3(-sin(a.rotation.y), 0, -cos(a.rotation.y))


static func right_of(a: Node3D) -> Vector3:
	return forward_of(a).cross(Vector3.UP)


## Where an avatar's eyes or main sensors are: at its mount height, slightly forward (the
## quadruped's sensor head is at the front of its body).
static func sensor_origin(a: Avatar) -> Vector3:
	var ahead := a.footprint.x / 2 - 0.08 if a.kind == "QUADRUPED" else 0.1
	return a.global_position + forward_of(a) * ahead + Vector3.UP * a.sensor_mount_height


## Where an avatar's voice comes from.
static func mouth_of(a: Avatar) -> Vector3:
	return sensor_origin(a) - Vector3.UP * (0.08 if a.kind != "QUADRUPED" else 0.0)


## Points to test on a target, by part name. With `gesture`, adds HAND (or reuses the head or
## torso point for head and posture gestures).
static func sample_points(t: Avatar, gesture := "") -> Dictionary:
	var f := forward_of(t)
	var r := right_of(t)
	var p := t.global_position
	var pts := {}
	if t.kind == "QUADRUPED":
		var mid := p + Vector3.UP * 0.5
		pts["HEAD"] = p + f * (t.footprint.x / 2 - 0.08) + Vector3.UP * t.sensor_mount_height
		pts["TORSO"] = mid
		pts["LEFT_SIDE"] = mid - r * (t.footprint.y / 2 - 0.03)
		pts["RIGHT_SIDE"] = mid + r * (t.footprint.y / 2 - 0.03)
	else:
		var side := t.footprint.y / 2 - 0.05
		pts["HEAD"] = p + Vector3.UP * (t.height - 0.12)
		pts["TORSO"] = p + Vector3.UP * (t.height * 0.6)
		pts["LEFT_SIDE"] = pts["TORSO"] - r * side
		pts["RIGHT_SIDE"] = pts["TORSO"] + r * side
	if gesture != "":
		pts["HAND"] = gesture_point(t, gesture, pts)
	return pts


static func gesture_point(t: Avatar, gesture: String, pts: Dictionary) -> Vector3:
	if HEAD_GESTURES.has(gesture):
		return pts["HEAD"]
	if not RAISED_HAND_GESTURES.has(gesture) and not FORWARD_HAND_GESTURES.has(gesture):
		return pts["TORSO"]   # BOW, SIT_IN_PLACE: the whole body
	var f := forward_of(t)
	var r := right_of(t)
	if t.kind == "QUADRUPED":
		return t.global_position + f * 0.5 + Vector3.UP * (t.height + 0.05)   # the arm's gripper
	if RAISED_HAND_GESTURES.has(gesture):
		return t.global_position + r * (t.footprint.y / 2) + Vector3.UP * (t.height + 0.05)
	return t.global_position + r * 0.2 + f * 0.45 + Vector3.UP * (t.height * 0.65)


## Angle from the observer's forward direction to `to`, positive to its left (D-29), in (-pi, pi].
static func bearing(observer: Node3D, from: Vector3, to: Vector3) -> float:
	var v := Vector2(to.x - from.x, to.z - from.z)
	var f := forward_of(observer)
	var left := -right_of(observer)
	var b := atan2(v.dot(Vector2(left.x, left.z)), v.dot(Vector2(f.x, f.z)))
	return PI if is_equal_approx(b, -PI) else b


## Is the segment from `from` to `to` clear for sight? `exclude` holds RIDs to ignore (the
## observer and target). Walls marked blocks_sight: false are seen through.
static func clear_line(space: PhysicsDirectSpaceState3D, from: Vector3, to: Vector3, exclude: Array[RID]) -> bool:
	var skip := exclude.duplicate()
	for i in 8:
		var q := PhysicsRayQueryParameters3D.create(from, to, SIGHT_MASK, skip)
		var hit := space.intersect_ray(q)
		if hit.is_empty():
			return true
		var collider: Object = hit["collider"]
		if collider.has_meta("blocks_sight") and not bool(collider.get_meta("blocks_sight")):
			skip.append(hit["rid"])
			continue
		return false
	return false


## Which parts of `target` the observer can see now. Returns {"visible": [parts], "in_view": bool
## (some point inside field of view and range), "in_range": bool, "points": {part: Vector3}}.
static func look(observer: Avatar, target: Avatar, visual_range: float, gesture := "") -> Dictionary:
	var space := observer.get_world_3d().direct_space_state
	var eye := sensor_origin(observer)
	var half_fov := deg_to_rad(float(observer.body["sensors"]["fov_deg"])) / 2
	var exclude: Array[RID] = [observer.get_rid(), target.get_rid()]
	var pts := sample_points(target, gesture)
	var visible: Array[String] = []
	var in_view := false
	var in_range := false
	for part in pts:
		var point: Vector3 = pts[part]
		if eye.distance_to(point) > visual_range:
			continue
		in_range = true
		if absf(bearing(observer, eye, point)) > half_fov:
			continue
		in_view = true
		if clear_line(space, eye, point, exclude):
			visible.append(String(part))
	return {"visible": visible, "in_view": in_view, "in_range": in_range, "points": pts}


## How speech from `mouth` reaches `listener`. Returns {"level_db", "snr_db", "wall_loss_db",
## "distance_m", "heard"}.
static func hear(world: RangeWorld, mouth: Vector3, listener: Avatar, level_at_1m: float) -> Dictionary:
	var ear := sensor_origin(listener)
	var d := mouth.distance_to(ear)
	var loss := 0.0
	var space := listener.get_world_3d().direct_space_state
	var skip: Array[RID] = [listener.get_rid()]
	for i in 12:
		var q := PhysicsRayQueryParameters3D.create(mouth, ear, Layers.WORLD, skip)
		var hit := space.intersect_ray(q)
		if hit.is_empty():
			break
		var collider: Object = hit["collider"]
		if collider.has_meta("wall_id"):
			loss += WALL_LOSS_DB if bool(collider.get_meta("blocks_sound")) else PARTITION_LOSS_DB
		skip.append(hit["rid"])
	var level := level_at_1m - 20.0 * log(maxf(d, 1.0)) / log(10.0) - loss
	var noise := float(world.environment_at(listener.global_position)["noise_floor_db"])
	var snr := level - noise
	var acoustic_range := float(listener.body["sensors"]["acoustic_range_m"])
	return {"level_db": level, "snr_db": snr, "wall_loss_db": loss, "distance_m": d,
		"heard": snr >= 0.0 and d <= acoustic_range}
