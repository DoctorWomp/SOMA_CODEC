extends Node3D
## Robot body lineup (D-36): the four robot bodies and a walking visitor side by side, for
## comparing sizes, sensor heights and looks. Nothing moves. In the Godot editor, open
## scenes/robot_lineup.tscn and press F6 (Run Current Scene).

const MAP_ID := "sandbox_flats"
const ROW_Z := 9.0

## [body_id, avatar id, x, appearance]. The row stands on open floor west of partition_a.
const LINEUP := [
	["legged_humanoid", "robot_legged", 3.2, {"badge": "1", "trim": "robot_trim_green", "bands": 1}],
	["wheeled_humanoid", "robot_wheeled", 4.9, {"badge": "2", "trim": "robot_trim_teal", "bands": 2}],
	["quadruped", "robot_quadruped", 6.6, {"badge": "3", "trim": "robot_trim_brown", "bands": 3}],
	["quadruped_arm", "robot_quadruped_arm", 8.3, {"badge": "4", "trim": "robot_trim_green", "bands": 2}],
	["human_walker", "visitor", 9.45, {"color": "visitor_slate"}],
]

var world: RangeWorld
var camera_rig: CameraRig
var hud: Hud


func _ready() -> void:
	DisplayServer.window_set_title("SOMA RANGE — robot body lineup")
	Stage.add_lighting(self)
	world = RangeWorld.new()
	add_child(world)
	var body_ids := []
	for entry in LINEUP:
		body_ids.append(entry[0])
	if not world.build(MAP_ID, body_ids):
		push_error("robot_lineup: could not build %s; see the errors above" % MAP_ID)
		return
	for entry in LINEUP:
		# Face +z, toward the default camera.
		world.spawn_avatar(entry[1], entry[0], Vector3(float(entry[2]), 0, ROW_Z), PI, entry[3])
	camera_rig = CameraRig.new()
	add_child(camera_rig)
	camera_rig.set_targets(world.avatar_list())
	camera_rig.look_from(Vector3(6.3, 1.9, 15.6), Vector3(6.3, 0.75, 9.0))
	hud = Hud.new()
	hud.setup(world, camera_rig, null)
	add_child(hud)
