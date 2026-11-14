class_name Layers
extends RefCounted
## Physics and navigation layer bits (names are also set in project.godot), and how a
## body's capability flags map onto them (D-31).

# Physics layers (bit values).
const WORLD := 1                 # floor, walls, partitions, platform, ramp, props
const AVATARS := 2               # every avatar body
const STAIRS_WALK_SURFACE := 4   # smooth slope over the stairs, solid only for can_use_stairs
const STAIRS_STEPS := 8          # the real steps, solid for everyone else

# Navigation layers (bit values). Floor and platform tops are always walkable;
# each nav link sits only on the layer of the capability it requires.
const NAV_FLOOR := 1
const NAV_CAPABILITY := {
	"can_use_ramp": 2,
	"can_use_stairs": 4,
}


static func has_capability(body: Dictionary, capability: String) -> bool:
	var caps: Dictionary = body.get("capabilities", {})
	return bool(caps.get(capability, false))


## Navigation layers a body's paths may use.
static func nav_mask_for(body: Dictionary) -> int:
	var mask := NAV_FLOOR
	for capability in NAV_CAPABILITY:
		if has_capability(body, capability):
			mask |= int(NAV_CAPABILITY[capability])
	return mask


## Physics layers a body collides with. Bodies that cannot use stairs meet the real steps.
static func collision_mask_for(body: Dictionary) -> int:
	var mask := WORLD | AVATARS
	mask |= STAIRS_WALK_SURFACE if has_capability(body, "can_use_stairs") else STAIRS_STEPS
	return mask
