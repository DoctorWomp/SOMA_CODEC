class_name SenseView
extends Node3D
## F2 (Blueprint §7.4 "sensor view"): draws what the selected avatar perceived at its last
## observation sample, from its own packet, not from world truth. A spectator debug view in the
## HUD's diagnostic style (ART_DIRECTION §8); meaning is always in words, never color alone.
##
## - its field of view (two short lines) from its sensor height;
## - a line to each avatar it perceives, labelled "seen", "partly seen: …" or "lost: …";
## - for speech it heard, a label "heard: «…»" and a short arrow toward where it came from.

const SEEN := Color("#3fc1d0")
const LOST := Color("#9aa3ad")
const FOV_LEN_M := 4.0

var world: RangeWorld
var rig: CameraRig
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
		visible = not visible


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
	var eye := SenseModel.sensor_origin(a)
	var half := deg_to_rad(float(a.body["sensors"]["fov_deg"])) / 2
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	for s in [-1.0, 1.0]:
		var dir := SenseModel.forward_of(a).rotated(Vector3.UP, half * s)
		_line(eye, eye + dir * FOV_LEN_M, SEEN)
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
			_line(eye, target, color)
			_label(used, target + Vector3.UP * 0.35, text)
			used += 1
		elif kind == "AUDIO_SPEECH":
			var b := float(item["bearing_rad"])
			var dir := SenseModel.forward_of(a).rotated(Vector3.UP, b)
			_line(eye, eye + dir * 1.2, LOST)
	_mesh.surface_end()
	# Speech is delivered in a single sample; keep showing the last thing heard for 3 s.
	var heard: Dictionary = world.senses.last_heard.get(a.avatar_id, {})
	if not heard.is_empty() and SimClock.ms_at(world.clock.tick) - int(heard["ms"]) <= 3000:
		_label(used, eye + Vector3.UP * 0.9, "heard: «%s»" % heard["text"])


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
