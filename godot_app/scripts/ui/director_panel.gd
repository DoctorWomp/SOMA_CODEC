class_name DirectorPanel
extends PanelContainer
## The Director console (G4b, D-97): typed commands, for the Director seat only (F6). Every command
## goes through world.director, which asks the world dispatcher (D-90); what it changes is journaled.
## Ctrl + left click on the floor sets the point where props go (a marker shows it).
##
##   inspect <avatar>                         show its editable directive, goal and persona sliders
##   directive <avatar> <text>                edit its scenario directive (next decision)
##   goal <avatar> <text>                     edit its goal (the task)
##   slider <avatar> <name> <0-100>           edit a persona slider
##   sign <text> | note <text>                text at the point, facing the camera (influence)
##   barrier | cone | crate [yaw°]            a prop at the point (world change)
##   sound <class> [dB] [seconds]             a sound source at the point (MUSIC, LAUGHTER, ...)
##   move <prop_id> | remove <prop_id>        move a placed prop to the point, or remove it
##   pa <text>                                a PA announcement
##   say <npc> [@<avatar>] <text>             an NPC says a line (social influence)
##   event <type> <actor> [<target>]          a tape event: wave, small_wave, turn_to, move_to (to the point), leave
##   help

const BORDER := Color("#d070e0")

var world: RangeWorld
var rig: CameraRig
var point := Vector3.INF
var input: LineEdit
var output: RichTextLabel
var _marker: MeshInstance3D


static func create(target_world: RangeWorld, camera_rig: CameraRig) -> DirectorPanel:
	if target_world.dispatcher.seat != "DIRECTOR":
		return null
	var p := DirectorPanel.new()
	p.world = target_world
	p.rig = camera_rig
	return p


func _init() -> void:
	name = "DirectorPanel"
	process_mode = Node.PROCESS_MODE_ALWAYS


func _ready() -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.09, 0.06, 0.1, 0.92)
	style.border_color = BORDER
	style.set_border_width_all(3)
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	add_theme_stylebox_override("panel", style)
	var box := VBoxContainer.new()
	box.name = "Box"
	add_child(box)
	var title := Label.new()
	title.text = "DIRECTOR — every change is journaled (help: type help) · Ctrl+click sets the point"
	title.add_theme_color_override("font_color", BORDER)
	title.add_theme_font_size_override("font_size", UiStyle.fs(13))
	box.add_child(title)
	output = RichTextLabel.new()
	output.scroll_following = true
	output.size_flags_vertical = Control.SIZE_EXPAND_FILL
	output.add_theme_font_size_override("normal_font_size", UiStyle.fs(11))
	box.add_child(output)
	input = LineEdit.new()
	input.placeholder_text = "command (help)"
	input.text_submitted.connect(func(t: String) -> void:
		input.clear()
		say(run(t)))
	box.add_child(input)
	_marker = MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.15
	mesh.bottom_radius = 0.15
	mesh.height = 0.04
	_marker.mesh = mesh
	_marker.material_override = Palette.material("robot_trim_teal")
	_marker.visible = false
	world.add_child(_marker)
	world.director.inspected.connect(func(r: Dictionary) -> void:
		var e: Dictionary = r.get("editable", {})
		say("inspected: directive «%s» · goal «%s» · sliders %s · never editable: %s" % [e.get("directive"), e.get("goal"),
			JSON.stringify(e.get("sliders", {})), ", ".join(e.get("locked", []))]))
	world.director.intervened.connect(func(entry: Dictionary) -> void:
		say("%s %s %s%s" % [entry["request"]["request_id"], entry["status"], entry["request"]["operation"],
			(" — " + String(entry["reason"])) if entry["reason"] != null else ""]))


func say(text: String) -> void:
	if output != null and text != "":
		output.append_text(text + "\n")


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not event is InputEventMouseButton:
		return
	var mb := event as InputEventMouseButton
	if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT and mb.ctrl_pressed and rig != null:
		var cam := rig.camera
		var from := cam.project_ray_origin(mb.position)
		var to := from + cam.project_ray_normal(mb.position) * 200.0
		var hit := world.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, to, Layers.WORLD))
		if not hit.is_empty():
			set_point(hit["position"])
			get_viewport().set_input_as_handled()


func set_point(p: Vector3) -> void:
	point = p
	_marker.position = p + Vector3.UP * 0.02
	_marker.visible = true
	say("point (%.1f, %.1f)" % [p.x, p.z])


## Run one command line; returns what to show. Also used by tests.
func run(line: String) -> String:
	var words := line.strip_edges().split(" ", false)
	if words.is_empty():
		return ""
	var cmd := String(words[0]).to_lower()
	var rest := " ".join(words.slice(1))
	var d := world.director
	var r := {}
	match cmd:
		"help":
			return "inspect, directive, goal, slider, sign, note, barrier, cone, crate, sound, move, remove, pa, say, event"
		"inspect":
			r = d.from_seat(null, "INSPECT_AGENT", rest, {})
		"directive", "goal":
			if words.size() < 3:
				return "usage: %s <avatar> <text>" % cmd
			r = d.from_seat("DIRECTIVE_EDIT", "EDIT_DIRECTIVE", String(words[1]), {"field": cmd, "value": " ".join(words.slice(2))})
		"slider":
			if words.size() != 4 or not String(words[3]).is_valid_int():
				return "usage: slider <avatar> <name> <0-100>"
			r = d.from_seat("DIRECTIVE_EDIT", "EDIT_DIRECTIVE", String(words[1]),
				{"field": "slider", "name": String(words[2]), "value": int(words[3])})
		"sign", "note":
			if not _point_set():
				return "set the point first (Ctrl + left click on the floor)"
			r = d.from_seat("ENVIRONMENTAL_INFLUENCE", "PLACE_PROP", null, {"prop_type": cmd.to_upper(), "x": point.x,
				"z": point.z, "yaw_rad": _facing_camera(), "text": rest})
		"barrier", "cone", "crate":
			if not _point_set():
				return "set the point first (Ctrl + left click on the floor)"
			var yaw := deg_to_rad(float(rest)) if rest.is_valid_float() else 0.0
			r = d.from_seat("WORLD_CHANGE", "PLACE_PROP", null, {"prop_type": cmd.to_upper(), "x": point.x, "z": point.z, "yaw_rad": yaw})
		"sound":
			if not _point_set() or words.size() < 2:
				return "usage: sound <class> [dB] [seconds] (set the point first)"
			r = d.from_seat("WORLD_CHANGE", "PLACE_PROP", null, {"prop_type": "SOUND_SOURCE", "x": point.x, "z": point.z,
				"sound_class": String(words[1]).to_upper(), "level_db": float(words[2]) if words.size() > 2 else 70.0,
				"duration_s": float(words[3]) if words.size() > 3 else 20.0})
		"move":
			if not _point_set():
				return "set the point first (Ctrl + left click on the floor)"
			r = d.from_seat(_kind_of(rest), "MOVE_PROP", rest, {"x": point.x, "z": point.z})
		"remove":
			r = d.from_seat(_kind_of(rest), "REMOVE_PROP", rest, {})
		"pa":
			r = d.from_seat("ENVIRONMENTAL_INFLUENCE", "PA_ANNOUNCEMENT", null, {"text": rest})
		"say":
			if words.size() < 3:
				return "usage: say <npc> [@<avatar>] <text>"
			var to = null
			var start := 2
			if String(words[2]).begins_with("@"):
				to = String(words[2]).substr(1)
				start = 3
			r = d.from_seat("SOCIAL_INFLUENCE", "NPC_SAY", String(words[1]), {"text": " ".join(words.slice(start)), "to": to})
		"event":
			if words.size() < 3:
				return "usage: event <type> <actor> [<target>]"
			var args := {"event_type": String(words[1])}
			if words.size() > 3:
				args["target"] = String(words[3])
			if String(words[1]) == "move_to" and _point_set():
				args["x"] = point.x
				args["z"] = point.z
			r = d.from_seat("EVENT_TRIGGER", "TRIGGER_EVENT", String(words[2]), args)
		_:
			return "unknown command '%s' (help)" % cmd
	if r.get("journaled", false):
		return ""                      # the journaled entry is shown by the intervened signal
	return "%s%s" % [r.get("status", "?"), (" — " + String(r["reason"])) if r.get("reason") != null else ""]


func _point_set() -> bool:
	return point != Vector3.INF


## A sign's text faces the camera: its front (-z of the prop) points from the sign toward the camera.
func _facing_camera() -> float:
	if rig == null or rig.camera == null:
		return 0.0
	var to_cam := rig.camera.global_position - point
	return atan2(-to_cam.x, -to_cam.z)


func _kind_of(prop_id: String) -> String:
	var entry: Dictionary = world.editor.placed.get(prop_id, {})
	if entry.is_empty():
		return "WORLD_CHANGE"
	return "ENVIRONMENTAL_INFLUENCE" if WorldEditor.TEXT_PROPS.has(String(entry["prop"]["prop_type"])) else "WORLD_CHANGE"
