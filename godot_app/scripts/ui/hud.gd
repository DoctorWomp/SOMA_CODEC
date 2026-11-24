class_name Hud
extends CanvasLayer
## Status and help panel (G1; seat and cameras G4a). The layer viewer is ui/viewer/layer_viewer.gd.
## Diagnostic look (dark panel, cyan accent) so it is never confused with in-world objects
## (ART_DIRECTION §8). Also handles pause (Space), restart (R) and hide (H).

var world: RangeWorld
var rig: CameraRig
var demo: DemoRoutes
var link: LinkClient
var label: Label
var _panel: PanelContainer


func _init() -> void:
	name = "Hud"
	process_mode = Node.PROCESS_MODE_ALWAYS


func setup(target_world: RangeWorld, camera_rig: CameraRig, demo_routes: DemoRoutes) -> void:
	world = target_world
	rig = camera_rig
	demo = demo_routes


func _ready() -> void:
	_panel = PanelContainer.new()
	_panel.position = Vector2(12, 12)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.07, 0.09, 0.12, 0.82)
	style.border_color = Color("#3fc1d0")
	style.border_width_left = 3
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	_panel.add_theme_stylebox_override("panel", style)
	label = Label.new()
	label.add_theme_color_override("font_color", Color("#e6eef2"))
	label.add_theme_font_size_override("font_size", 15)
	_panel.add_child(label)
	add_child(_panel)


func _process(_delta: float) -> void:
	label.text = status_text()


func status_text() -> String:
	if world == null or world.clock == null:
		return "SOMA RANGE · loading"
	var lines: Array[String] = []
	var state := "PAUSED" if get_tree().paused else "running"
	if demo != null and demo.finished:
		state += " · demo finished (R restarts)"
	lines.append("SOMA RANGE · Sandbox Flats · greybox (G2a)")
	lines.append("Tick %d (60 Hz) · %.1f s · %s" % [world.clock.tick, world.clock.seconds(), state])
	var target: Node3D = rig.selected_target() if rig != null else null
	var mode_name := String(CameraRig.Mode.keys()[rig.mode]) if rig != null else "FREE"
	var seat := world.dispatcher.seat if world.dispatcher != null else "?"
	lines.append("Seat: %s · camera %s" % [seat, mode_name])
	if link != null:
		lines.append("Python link: %s · agents %s · sent %d · received %d" % [link.status, ", ".join(link.agents),
			link.stats["sent"], link.stats["received"]])
	if target is Avatar:
		var a := target as Avatar
		lines.append("Selected: %s · %s · %.2f m/s" % [a.avatar_id, Bodies.display_name(a.body), a.speed])
		lines.append("  " + capability_line(a))
		lines.append("  gestures: " + gesture_line(a))
		lines.append("  position (%.1f, %.1f, %.1f)" % [a.global_position.x, a.global_position.y, a.global_position.z])
		if demo != null:
			lines.append("  " + demo.status_text(a.avatar_id))
		lines.append("  links used: %s" % (", ".join(a.links_used) if not a.links_used.is_empty() else "none yet"))
		lines.append("  senses (F2 shows them): " + senses_line(world, a))
	lines.append("")
	lines.append("C camera (free, orbit, follow, POV) · [ ] select avatar · right mouse look/orbit · wheel zoom")
	lines.append("W A S D move · Q E down/up · Shift fast · Space pause · R restart · H hide")
	lines.append("F2 sensor view · F3 layer viewer · F4 EVALUATOR TRUTH (Evaluator seat only)")
	return "\n".join(lines)


## What the avatar perceived at the last sample, e.g. "sees 3 (1 partly) · lost 1 · heard «Hello»".
static func senses_line(w: RangeWorld, a: Avatar) -> String:
	if w.senses == null or not w.senses.latest.has(a.avatar_id):
		return "not sampled yet"
	var seen := 0
	var partly := 0
	var lost := 0
	for item in w.senses.latest[a.avatar_id]["observations"]:
		match String(item["kind"]):
			"VISUAL_PRESENCE":
				match String(item["validity"]):
					"OBSERVED":
						seen += 1
					"DEGRADED":
						seen += 1
						partly += 1
					_:
						lost += 1
	var line := "sees %d (%d partly) · lost %d" % [seen, partly, lost]
	var heard: Dictionary = w.senses.last_heard.get(a.avatar_id, {})
	var ago := (SimClock.ms_at(w.clock.tick) - int(heard.get("ms", -100000))) / 1000.0
	if not heard.is_empty() and ago <= 3.0:
		line += " · heard «%s»%s" % [heard["text"], "" if heard["validity"] == "OBSERVED" else " (%s)" % String(heard["validity"]).to_lower()]
	return line


## What the body can do, e.g. "stairs yes · ramp yes · sensors at 0.55 m, 120° · channels SPEECH, LIGHT".
static func capability_line(a: Avatar) -> String:
	return "stairs %s · ramp %s · sensors at %.2f m, %d° · channels %s" % [
		"yes" if Layers.has_capability(a.body, "can_use_stairs") else "NO",
		"yes" if Layers.has_capability(a.body, "can_use_ramp") else "NO",
		a.sensor_mount_height, int(a.body["sensors"]["fov_deg"]),
		", ".join(a.body.get("expression_channels", []))]


static func gesture_line(a: Avatar) -> String:
	var gestures: Array = a.body.get("gestures", [])
	if gestures.is_empty():
		return "none"
	if gestures.size() <= 6:
		return ", ".join(gestures)
	return "%s and %d more" % [", ".join(gestures.slice(0, 6)), gestures.size() - 6]


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("sim_pause"):
		if world == null or world.dispatcher == null or world.dispatcher.seat_request("PAUSE")["code"] == "OK":
			get_tree().paused = not get_tree().paused
	elif event.is_action_pressed("demo_restart"):
		get_tree().paused = false
		get_tree().reload_current_scene()
	elif event.is_action_pressed("hud_toggle"):
		_panel.visible = not _panel.visible
