class_name Bodies
extends RefCounted
## Body rules (D-36, D-37), mirroring range_service/bodies.py. Tests on both sides pin the
## same numbers, so Python and Godot agree on sizes and gesture permissions.

## Navigation meshes are baked on a 5 cm grid; a body's navigation radius is its turning
## radius rounded up to that grid.
const NAV_CELL_M := 0.05


## Radius of the circle the body sweeps when it turns on the spot: half the width for round
## colliders, half the diagonal for a box.
static func turning_radius(body: Dictionary) -> float:
	var collider: Dictionary = body["dimensions"]["collider"]
	var length := float(collider["length_m"])
	var width := float(collider["width_m"])
	if collider["shape"] == "BOX":
		return Vector2(length / 2, width / 2).length()
	return width / 2


static func nav_radius(body: Dictionary) -> float:
	return ceilf(turning_radius(body) / NAV_CELL_M - 1e-6) * NAV_CELL_M


static func supports_gesture(body: Dictionary, gesture: String) -> bool:
	return Layers.has_capability(body, "can_gesture") and Array(body.get("gestures", [])).has(gesture)


static func supports_channel(body: Dictionary, channel: String) -> bool:
	return Array(body.get("expression_channels", [])).has(channel)


static func display_name(body: Dictionary) -> String:
	return String(body.get("display_name", body.get("body_id", "?")))
