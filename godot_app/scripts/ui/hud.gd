class_name Hud
extends CanvasLayer
## Minimal status and help panel for G1. The full operator HUD and layer viewer come at G4.
## Diagnostic look (dark panel, cyan accent) so it is never confused with in-world objects
## (ART_DIRECTION §8). Also handles pause (Space), restart (R) and hide (H).

var world: RangeWorld
var rig: CameraRig
var demo: DemoRoutes
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
	lines.append("SOMA RANGE · Sandbox Flats · G1 greybox")
	lines.append("Tick %d (60 Hz) · %.1f s · %s" % [world.clock.tick, world.clock.seconds(), state])
	var target: Node3D = rig.selected_target() if rig != null else null
	var mode_name := "ORBIT" if rig != null and rig.mode == CameraRig.Mode.ORBIT else "FREE"
	lines.append("Camera: %s" % mode_name)
	if target is Avatar:
		var a := target as Avatar
		lines.append("Selected: %s (%s) · %.2f m/s" % [a.avatar_id, a.kind, a.speed])
		lines.append("  position (%.1f, %.1f, %.1f)" % [a.global_position.x, a.global_position.y, a.global_position.z])
		if demo != null:
			lines.append("  " + demo.status_text(a.avatar_id))
		lines.append("  links used: %s" % (", ".join(a.links_used) if not a.links_used.is_empty() else "none yet"))
	lines.append("")
	lines.append("C camera mode · [ ] select avatar · right mouse look/orbit · wheel zoom")
	lines.append("W A S D move · Q E down/up · Shift fast · Space pause · R restart · H hide")
	return "\n".join(lines)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("sim_pause"):
		get_tree().paused = not get_tree().paused
	elif event.is_action_pressed("demo_restart"):
		get_tree().paused = false
		get_tree().reload_current_scene()
	elif event.is_action_pressed("hud_toggle"):
		_panel.visible = not _panel.visible
