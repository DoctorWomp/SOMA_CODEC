class_name SenseView
extends Node3D
## The Sensor view (F2; Blueprint §7.4; G4a): what the selected observer perceived at its last
## observation sample, drawn from its own packet only, never from world truth (D-39). A spectator
## view in the HUD's diagnostic style (ART_DIRECTION §8); meaning is always in words.
##
## - its sight cone, from the packet's own pose: the body's yaw plus the head's yaw (D-72), at its
##   sensor height, as wide as its body's field of view;
## - each track at the position the packet estimated, by the observer's own anonymous id (with its
##   D-111 handle beside it when the observer has one), labelled seen, partly seen or lost;
## - speech it heard, as an arrow along the packet's bearing (relative to the body, D-72) with the
##   words, for 3 s.
## Opening it is asked of the world dispatcher (VIEW_SENSOR, D-90): a participant (G4c) may open it
## only for its own body, and that is logged.

const SEEN := Color("#3fc1d0")
const LOST := Color("#9aa3ad")
const FOV_LEN_M := 4.0

var world: RangeWorld
var rig: CameraRig
var store: ViewerStore            # optional: the observer's own handles (D-111), from the viewer feed
var last_drawn: Dictionary = {}   # what the last frame drew (tests): {"observer", "eye", "cone_dir", "labels"}
var _mesh := ImmediateMesh.new()
var _labels: Array[Label3D] = []


func _init() -> void:
	name = "SenseView"
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func setup(target_world: RangeWorld, camera_rig: CameraRig) -> void:
	world = target_world
	rig = camera_rig


func _ready() -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = _mesh
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.no_depth_test = true
	mi.material_override = mat
	add_child(mi)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("sense_view"):
		toggle()


## Open or close the view; opening asks the dispatcher for the selected observer.
func toggle() -> bool:
	if visible:
		visible = false
		return true
	var target := rig.selected_id() if rig != null else ""
	if world != null and world.dispatcher != null and world.dispatcher.seat_request("VIEW_SENSOR", target)["code"] != "OK":
		return false
	visible = true
	return true


func _process(_delta: float) -> void:
	_mesh.clear_surfaces()
	for l in _labels:
		l.visible = false
	if not visible or world == null or rig == null:
		return
	var a := rig.selected_target() as Avatar
	if a == null or world.senses == null or not world.senses.latest.has(a.avatar_id):
		return
	draw_packet(a, world.senses.latest[a.avatar_id])


func draw_packet(a: Avatar, packet: Dictionary) -> void:
	var pose: Dictionary = packet["observer_pose"]
	var at := Vector3(float(pose["x"]), float(pose["y"]), float(pose["z"]))
	var yaw := float(pose["yaw_rad"])
	var head_yaw := float(pose.get("head_yaw_rad", 0.0))
	var eye := at + Vector3.UP * a.sensor_mount_height       # the body's own sensor height (its config)
	var body_fwd := Vector3(-sin(yaw), 0, -cos(yaw))
	var head_fwd := Vector3(-sin(yaw + head_yaw), 0, -cos(yaw + head_yaw))
	var half := deg_to_rad(float(a.body["sensors"]["fov_deg"])) / 2
	var labels: Array[String] = []
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	for s in [-1.0, 1.0]:
		_line(eye, eye + head_fwd.rotated(Vector3.UP, half * s) * FOV_LEN_M, SEEN)   # the cone follows the head (D-72)
	var used := 0
	for item in packet["observations"]:
		var kind := String(item["kind"])
		if kind == "VISUAL_PRESENCE" and item["position_estimate"] != null:
			var p: Dictionary = item["position_estimate"]
			var target := Vector3(float(p["x"]), float(p["y"]) + 1.0, float(p["z"]))
			var validity := String(item["validity"])
			var text := "seen"
			var color := SEEN
			if validity == "DEGRADED":
				text = "partly seen: " + ", ".join(item.get("visible_parts", []))
			elif validity != "OBSERVED":
				text = "lost: " + String(item.get("validity_reason", validity)).to_lower().replace("_", " ")
				color = LOST
			text = "%s · %s" % [_track_label(a.avatar_id, item.get("track_id")), text]
			_line(eye, target, color)
			_label(used, target + Vector3.UP * 0.35, text)
			labels.append(text)
			used += 1
		elif kind == "AUDIO_SPEECH":
			var dir := body_fwd.rotated(Vector3.UP, float(item["bearing_rad"]))   # bearings stay relative to the body
			_line(eye, eye + dir * 1.2, LOST)
	_mesh.surface_end()
	# Speech is delivered in a single sample; keep showing the last thing heard for 3 s.
	var heard: Dictionary = world.senses.last_heard.get(a.avatar_id, {})
	if not heard.is_empty() and SimClock.ms_at(world.clock.tick) - int(heard["ms"]) <= 3000:
		var text := "heard: «%s»" % heard["text"]
		_label(used, eye + Vector3.UP * 0.9, text)
		labels.append(text)
	last_drawn = {"observer": a.avatar_id, "eye": eye, "cone_dir": head_fwd, "labels": labels}


## The observer's own id for a track, with its handle beside it when it has one (D-111).
func _track_label(observer: String, track) -> String:
	if store != null:
		return store.track_label(observer, track)
	return String(track) if track != null else "unknown"


func _line(from: Vector3, to: Vector3, color: Color) -> void:
	_mesh.surface_set_color(color)
	_mesh.surface_add_vertex(from)
	_mesh.surface_set_color(color)
	_mesh.surface_add_vertex(to)


func _label(index: int, at: Vector3, text: String) -> void:
	while _labels.size() <= index:
		var l := Label3D.new()
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.font_size = 44
		l.pixel_size = 0.005
		l.modulate = Color("#e6eef2")
		l.outline_modulate = Color(0.07, 0.09, 0.12, 0.9)
		l.outline_size = 10
		add_child(l)
		_labels.append(l)
	_labels[index].text = text
	_labels[index].position = at
	_labels[index].visible = true
