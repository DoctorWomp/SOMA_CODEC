class_name LayerViewer
extends Control
## Layer viewer v1 (G4a; RANGE_V0_SCOPE §2.4 items 1–4 and 8): a 2D panel drawn from the run's
## viewer feed (ViewerStore), so it works live and on replays. Diagnostic look (ART_DIRECTION §8);
## meaning is in words and glyphs, never color alone.
##
## Per observer (D-62): every panel is labelled with the observer it belongs to, and shows only that
## observer's own records; tracks appear by its own anonymous ids with its handles beside them (D-111).
## Lanes for what exists today, then HORIZON L0–L8, present and empty: "not built (G5)".
## Solo / Mute only show or hide a lane (view only). Bypass would remove a layer from the avatar's
## perception (an ablation): it is shown, disabled, with its reason, until G5.
## Cost (ART_DIRECTION §3.1): no textures; `_draw` runs only when the data, the playhead or the
## observer changed; only records inside the visible time window are drawn.
##
## Keys while open: , and . step 1 s (Shift: 10 s) · N / P next / previous decision · L follow live
## · - and = zoom the time window · click a pin or drag on the lanes to scrub.

signal decision_selected(decision_id: String)

const BG := Color(0.07, 0.09, 0.12, 1.0)   # opaque: the 3D scene never shows through the diagnostics
const ACCENT := Color("#3fc1d0")
const TEXT := Color("#e6eef2")
const DIM := Color("#8a96a3")
const WARN := Color("#e0a040")
const BAD := Color("#e06a5a")
const OK_COLOR := Color("#7fd18b")
const HEADER_H := 54.0
const NAME_W := 232.0
const PIN_H := 16.0
const AXIS_H := 18.0
const FONT_SIZE := 13
const LIVE_REPAINT_MS := 500
const HORIZON := [["L0", "Anchor"], ["L1", "Halo"], ["L2", "Echo"], ["L3", "Wake"], ["L4", "Focus"],
	["L5", "Contour"], ["L6", "Prism"], ["L7", "Haze"], ["L8", "Trail"]]
## The lanes built today, in order: [key, label].
const LANES := [["sight", "Sight (in view)"], ["hearing", "Hearing (bearings)"], ["tracks", "Tracks (own ids)"],
	["head", "Head & gaze"], ["pulse", "Pulse · activity · wake"], ["model", "Model calls"],
	["actions", "Actions → host"], ["beacon", "Beacon & ambient"]]
const BYPASS_REASON := "Bypass removes this layer from the avatar's perception (an ablation, logged; mid-run it taints the run, D-03). Not available until G5: no HORIZON layer exists yet to remove."

var store: ViewerStore
var dispatcher: WorldDispatcher
var observer := ""
var playhead_ms := 0
var follow_live := true
var window_ms := 60000
var selected_decision := ""
var solo := {}       # lane key -> true
var muted := {}      # lane key -> true
var map_data: Dictionary = {}
var draws := 0       # how many times the panel was drawn (cost accounting)
var lane_rows: Array = []   # [{"key", "label", "built"}] in display order
var buttons := {}    # lane key -> {"solo": Button, "mute": Button, "bypass": Button}
var decision_label: Label
var _font: Font
var _seen_version := -1
var _next_live_repaint_ms := 0
var _c: Control                        # the canvas being painted
var _vp: SubViewport
var _canvas: PanelCanvas
var _drag := false


func _init() -> void:
	name = "LayerViewer"
	process_mode = Node.PROCESS_MODE_ALWAYS
	mouse_filter = Control.MOUSE_FILTER_STOP
	for l in LANES:
		lane_rows.append({"key": l[0], "label": l[1], "built": true})
	for h in HORIZON:
		lane_rows.append({"key": h[0], "label": "%s %s" % [h[0], h[1]], "built": false})


func setup(viewer_store: ViewerStore, seat_dispatcher: WorldDispatcher, first_observer: String) -> void:
	store = viewer_store
	dispatcher = seat_dispatcher
	set_observer(first_observer)


## Draws the panel when asked; lives in a SubViewport that renders only after a change.
class PanelCanvas extends Control:
	var viewer: LayerViewer

	func _draw() -> void:
		viewer.paint(self)


func _ready() -> void:
	_font = ThemeDB.fallback_font
	# Cost (ART_DIRECTION §3.1, measured in G4a): the panel is painted into its own texture only when
	# its data, playhead or observer change (~4 times a second live), and each frame composites that
	# one texture. Painting every frame cost ~5 ms of a software renderer's frame. The texture is
	# the panel's size (about 2-5 MB). Buttons and the decision text stay outside it.
	var holder := SubViewportContainer.new()
	holder.name = "Paint"
	holder.stretch = true
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(holder)
	_vp = SubViewport.new()
	_vp.transparent_bg = true
	_vp.disable_3d = true
	_vp.gui_disable_input = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	holder.add_child(_vp)
	_canvas = PanelCanvas.new()
	_canvas.viewer = self
	_canvas.set_anchors_preset(Control.PRESET_FULL_RECT)
	_vp.add_child(_canvas)
	visibility_changed.connect(_repaint)
	decision_label = Label.new()
	decision_label.name = "DecisionPanel"
	decision_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	decision_label.add_theme_font_size_override("font_size", 12)
	decision_label.add_theme_color_override("font_color", TEXT)
	decision_label.clip_text = true
	add_child(decision_label)
	for row in lane_rows:
		var key := String(row["key"])
		var b := {}
		if bool(row["built"]):
			b["solo"] = _button("S", "Solo: show only this lane (view only, changes nothing in the run)", true)
			b["mute"] = _button("M", "Mute: hide this lane (view only, changes nothing in the run)", true)
			b["solo"].toggled.connect(func(on: bool) -> void: set_solo(key, on))
			b["mute"].toggled.connect(func(on: bool) -> void: set_mute(key, on))
		var bypass := _button("⊘ BYPASS", BYPASS_REASON, false)
		bypass.disabled = true
		var style := StyleBoxFlat.new()
		style.bg_color = Color(0.2, 0.08, 0.08, 0.6)
		style.border_color = BAD
		style.set_border_width_all(1)
		style.set_corner_radius_all(2)
		bypass.add_theme_stylebox_override("disabled", style)
		bypass.add_theme_color_override("font_disabled_color", Color(0.85, 0.6, 0.55))
		b["bypass"] = bypass
		buttons[key] = b
	map_data = WorldData.load_map(String(store.meta.get("map_id", "sandbox_flats"))) if store != null else {}
	resized.connect(_layout)
	_layout()


func _button(text: String, tip: String, toggle: bool) -> Button:
	var b := Button.new()
	b.text = text
	b.tooltip_text = tip
	b.toggle_mode = toggle
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 10)
	add_child(b)
	return b


func set_observer(avatar_id: String) -> void:
	if avatar_id == observer:
		return
	observer = avatar_id
	selected_decision = ""
	_refresh_decision()
	_repaint()


func set_solo(key: String, on: bool) -> void:
	if on:
		solo[key] = true
	else:
		solo.erase(key)
	_repaint()


func set_mute(key: String, on: bool) -> void:
	if on:
		muted[key] = true
	else:
		muted.erase(key)
	_repaint()


## Ask for one new paint of the panel (and one render of its texture).
func _repaint() -> void:
	if _canvas == null:
		return
	_canvas.size = size
	_canvas.queue_redraw()
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE


## What an empty HORIZON lane says (no layer is faked).
func lane_note(key: String) -> String:
	return "%s — not built (G5): no data, nothing drawn" % key


## Is a lane drawn? View only: nothing here touches the run.
func lane_visible(key: String) -> bool:
	if muted.has(key):
		return false
	return solo.is_empty() or solo.has(key)


func _process(_delta: float) -> void:
	if not visible or store == null:
		return
	# New live data repaints at most every LIVE_REPAINT_MS (input repaints at once): each repaint
	# renders the panel's texture once, which a software renderer shows as one slower frame.
	var now := Time.get_ticks_msec()
	if store.version != _seen_version and now >= _next_live_repaint_ms:
		_seen_version = store.version
		_next_live_repaint_ms = now + LIVE_REPAINT_MS
		if map_data.is_empty() and store.meta.has("map_id"):
			map_data = WorldData.load_map(String(store.meta["map_id"]))
		if follow_live and store.live:
			playhead_ms = store.t_max
		_refresh_decision()
		_repaint()


func scrub_to(t_ms: int) -> void:
	playhead_ms = clampi(t_ms, 0, maxi(store.t_max if store != null else 0, 0))
	follow_live = false
	_repaint()


func decisions() -> Array:
	return store.records(observer, "decision") if store != null else []


## Select a decision (a pin): the playhead moves to it and the panel shows why.
func select_decision(decision_id: String) -> bool:
	for rec in decisions():
		if String(rec["data"]["decision_id"]) == decision_id:
			selected_decision = decision_id
			scrub_to(int(rec["t_ms"]))
			_refresh_decision()
			decision_selected.emit(decision_id)
			return true
	return false


func step_decision(direction: int) -> void:
	var list := decisions()
	if list.is_empty():
		return
	var index := -1
	for i in list.size():
		if String(list[i]["data"]["decision_id"]) == selected_decision:
			index = i
	if index < 0:
		index = 0 if direction > 0 else list.size() - 1
		for i in list.size():
			if int(list[i]["t_ms"]) >= playhead_ms:
				index = i if direction > 0 else maxi(i - 1, 0)
				break
	else:
		index = clampi(index + direction, 0, list.size() - 1)
	select_decision(String(list[index]["data"]["decision_id"]))


func selected_decision_record() -> Dictionary:
	for rec in decisions():
		if String(rec["data"]["decision_id"]) == selected_decision:
			return rec
	return {}


func _refresh_decision() -> void:
	if decision_label == null:
		return
	var rec := selected_decision_record()
	if rec.is_empty():
		decision_label.text = "No decision selected · seen by %s\nClick a pin (▼) above the lanes, or press N / P." % observer
	else:
		decision_label.text = DecisionText.build(store, observer, rec)


func decision_text() -> String:
	return decision_label.text if decision_label != null else ""


## The capability card (scope §2.4 item 8): the manifest's line, and what the body can sense and do.
func capability_card() -> String:
	if store == null:
		return ""
	var card := String(store.meta.get("capability_cards", {}).get(observer, "[%s | no card]" % observer))
	var b: Dictionary = store.meta.get("bodies", {}).get(observer, {})
	if b.is_empty():
		return card
	return "%s\n%s · sees %s° to %s m · hears %s m · sensors at %s m · neck %s · %s m/s · stairs %s · ramp %s · %d gestures · %s" % [
		card, b.get("body_id", "?"), str(b.get("fov_deg")), str(b.get("visual_range_m")), str(b.get("acoustic_range_m")),
		str(b.get("sensor_height_m")), "yes" if b.get("neck") else "no", str(b.get("max_speed_mps")),
		"yes" if b.get("stairs") else "no", "yes" if b.get("ramp") else "no", int(b.get("gestures", 0)),
		", ".join(b.get("channels", []))]


# ---------------- layout and input ----------------

func _areas() -> Dictionary:
	var w := size.x
	var h := size.y
	var top := HEADER_H
	var upper_h := floorf((h - top) * 0.42)
	var map_rect := Rect2(8, top, floorf(w * 0.42), upper_h)
	var text_rect := Rect2(map_rect.end.x + 8, top, w - map_rect.end.x - 16, upper_h)
	var lanes_top := top + upper_h + 6 + PIN_H
	var lanes_h := h - lanes_top - AXIS_H - 6
	var row_h := floorf(lanes_h / lane_rows.size())
	var plot := Rect2(NAME_W, lanes_top, w - NAME_W - 8, row_h * lane_rows.size())
	return {"map": map_rect, "text": text_rect, "plot": plot, "row_h": row_h, "pins": Rect2(NAME_W, lanes_top - PIN_H, plot.size.x, PIN_H)}


func _layout() -> void:
	if decision_label == null:
		return
	var a := _areas()
	var text_rect: Rect2 = a["text"]
	decision_label.position = text_rect.position + Vector2(6, 4)
	decision_label.size = text_rect.size - Vector2(12, 8)
	var plot: Rect2 = a["plot"]
	var row_h: float = a["row_h"]
	for i in lane_rows.size():
		var key := String(lane_rows[i]["key"])
		var y := plot.position.y + i * row_h + 1
		var bh := maxf(row_h - 2, 10)
		var b: Dictionary = buttons[key]
		if b.has("solo"):
			b["solo"].position = Vector2(NAME_W - 112, y)
			b["solo"].size = Vector2(22, bh)
			b["mute"].position = Vector2(NAME_W - 88, y)
			b["mute"].size = Vector2(22, bh)
		b["bypass"].position = Vector2(NAME_W - 64, y)
		b["bypass"].size = Vector2(60, bh)
	_repaint()


func time_window() -> Vector2i:
	var t0 := playhead_ms - ((window_ms * 3) >> 2)
	return Vector2i(t0, t0 + window_ms)


func _t_to_x(t: int, plot: Rect2) -> float:
	var win := time_window()
	return plot.position.x + float(t - win.x) / float(win.y - win.x) * plot.size.x


func _x_to_t(x: float, plot: Rect2) -> int:
	var win := time_window()
	return win.x + roundi((x - plot.position.x) / plot.size.x * float(win.y - win.x))


func _gui_input(event: InputEvent) -> void:
	var a := _areas()
	var plot: Rect2 = a["plot"]
	var pins: Rect2 = a["pins"]
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_drag = mb.pressed and plot.grow(2).has_point(mb.position)
			if mb.pressed and pins.grow(4).has_point(mb.position):
				var best := ""
				var best_d := 8.0
				for rec in decisions():
					var dx := absf(_t_to_x(int(rec["t_ms"]), plot) - mb.position.x)
					if dx < best_d:
						best_d = dx
						best = String(rec["data"]["decision_id"])
				if best != "":
					select_decision(best)
			elif _drag:
				scrub_to(_x_to_t(mb.position.x, plot))
			accept_event()
	elif event is InputEventMouseMotion and _drag:
		scrub_to(_x_to_t((event as InputEventMouseMotion).position.x, plot))
		accept_event()


func _unhandled_key_input(event: InputEvent) -> void:
	if not visible or not event.is_pressed() or not event is InputEventKey:
		return
	var k := event as InputEventKey
	var step := 10000 if k.shift_pressed else 1000
	match k.keycode:
		KEY_COMMA:
			scrub_to(playhead_ms - step)
		KEY_PERIOD:
			scrub_to(playhead_ms + step)
		KEY_N:
			step_decision(1)
		KEY_P:
			step_decision(-1)
		KEY_L:
			follow_live = true
			if store != null:
				playhead_ms = store.t_max
			_repaint()
		KEY_MINUS:
			window_ms = mini(window_ms * 2, 1920000)
			_repaint()
		KEY_EQUAL:
			window_ms = maxi(window_ms >> 1, 7500)
			_repaint()
		_:
			return
	get_viewport().set_input_as_handled()


# ---------------- drawing ----------------

## Paint the panel into `c` (the canvas inside the panel's SubViewport). Called only when something
## changed; every other frame shows the texture of the last paint.
func paint(c: Control) -> void:
	_c = c
	draws += 1
	_c.draw_rect(Rect2(Vector2.ZERO, size), BG)
	_c.draw_rect(Rect2(0, 0, 3, size.y), ACCENT)
	if store == null:
		return
	var a := _areas()
	var mode := "LIVE" if store.live and follow_live else ("LIVE (scrubbed back: L follows again)" if store.live else "REPLAY")
	_text(Vector2(12, 18), "LAYER VIEWER v1 · seen by %s · seat %s · %s · t %.1f s of %.1f s" % [observer,
		dispatcher.seat if dispatcher != null else "?", mode, playhead_ms / 1000.0, store.t_max / 1000.0], ACCENT, 14)
	var card := capability_card().split("\n")
	for i in card.size():
		_text(Vector2(12, 34 + 14 * i), card[i], DIM, 11)
	_draw_map(a["map"])
	_c.draw_rect(a["text"], Color(1, 1, 1, 0.04))
	_draw_lanes(a["plot"], a["row_h"], a["pins"])


func _text(at: Vector2, s: String, color: Color, font_size := FONT_SIZE, max_w := -1.0) -> void:
	_c.draw_string(_font, at, s, HORIZONTAL_ALIGNMENT_LEFT, max_w, font_size, color)


## Top-down view of the observer's own perception at the playhead: its pose, its head-anchored
## sight cone, its tracks where it estimated them, and speech it heard in the last 3 s as bearings.
func _draw_map(r: Rect2) -> void:
	_c.draw_rect(r, Color(1, 1, 1, 0.04))
	_text(r.position + Vector2(6, 14), "SIGHT · HEARING · TRACKS — seen by %s (its packets only)" % observer, DIM, 11)
	if map_data.is_empty():
		return
	var bounds: Dictionary = map_data["bounds"]
	var mw := float(bounds["width_m"])
	var md := float(bounds["depth_m"])
	var inner := r.grow(-10)
	inner.position.y += 12
	inner.size.y -= 12
	var s := minf(inner.size.x / mw, inner.size.y / md)
	var origin := inner.position
	var to_px := func(x: float, z: float) -> Vector2: return origin + Vector2(x, z) * s
	for wall in map_data["walls"]:
		_c.draw_line(to_px.call(float(wall["a"]["x"]), float(wall["a"]["z"])), to_px.call(float(wall["b"]["x"]), float(wall["b"]["z"])),
			DIM if bool(wall.get("blocks_sight", true)) else Color(DIM, 0.4), 2.0 if bool(wall.get("blocks_sight", true)) else 1.0)
	for p in map_data.get("platforms", []):
		var ar: Dictionary = p["area"]
		var p0: Vector2 = to_px.call(float(ar["x_min"]), float(ar["z_min"]))
		var p1: Vector2 = to_px.call(float(ar["x_max"]), float(ar["z_max"]))
		_c.draw_rect(Rect2(p0, p1 - p0), Color(DIM, 0.35), false, 1.0)
	var sight := store.latest(observer, "sight", playhead_ms)
	if sight.is_empty():
		_text(inner.position + Vector2(4, 16), "no packet yet", DIM, 11)
		return
	var pose: Dictionary = sight["data"]["pose"]
	var me: Vector2 = to_px.call(float(pose["x"]), float(pose["z"]))
	var yaw := float(pose["yaw"])
	var head := yaw + float(pose.get("head_yaw", 0.0))
	var body: Dictionary = store.meta.get("bodies", {}).get(observer, {})
	var half := deg_to_rad(float(body.get("fov_deg", 120))) / 2.0
	var reach := float(body.get("visual_range_m", 20)) * s
	var cone := PackedVector2Array([me])
	for i in 13:
		var ang := head - half + (2.0 * half) * i / 12.0
		cone.append(me + Vector2(-sin(ang), -cos(ang)) * reach)
	var frame := PackedVector2Array([inner.position, Vector2(inner.end.x, inner.position.y), inner.end,
		Vector2(inner.position.x, inner.end.y)])
	for piece in Geometry2D.intersect_polygons(cone, frame):   # draw only what is inside the map view
		_c.draw_colored_polygon(piece, Color(ACCENT, 0.08))
		_c.draw_polyline(piece + PackedVector2Array([piece[0]]), Color(ACCENT, 0.35), 1.0)
	var fwd := Vector2(-sin(yaw), -cos(yaw))
	var side := Vector2(fwd.y, -fwd.x)
	_c.draw_colored_polygon(PackedVector2Array([me + fwd * 9, me - fwd * 6 + side * 6, me - fwd * 6 - side * 6]), ACCENT)
	_text(me + Vector2(8, -6), observer, ACCENT, 11)
	for item in sight["data"]["items"]:
		if item.get("pos") == null:
			continue
		var p: Vector2 = to_px.call(float(item["pos"]["x"]), float(item["pos"]["z"]))
		var validity := String(item["validity"])
		var seen := validity == "OBSERVED" or validity == "DEGRADED"
		if seen:
			_c.draw_circle(p, 5, OK_COLOR if validity == "OBSERVED" else WARN)
		else:
			_c.draw_arc(p, 5, 0, TAU, 12, DIM, 1.0)
		var tag := "" if validity == "OBSERVED" else (" · partly" if validity == "DEGRADED" else " · %s" % String(item.get("reason", validity)).to_lower())
		_text(p + Vector2(7, 4), store.track_label(observer, item["track"]) + tag, TEXT if seen else DIM, 10)
	for heard in store.between(observer, "hearing", playhead_ms - 3000, playhead_ms):
		var b := float(heard["data"].get("bearing", 0.0))
		var dir := fwd.rotated(-b)   # bearings are relative to the body, positive left (screen y is +z)
		_c.draw_line(me, me + dir * 40, WARN, 2.0)
		var txt := String(heard["data"].get("text", ""))
		_text(me + dir * 44, "heard%s «%s»" % [" (to me)" if heard["data"].get("addressed") else "",
			txt if txt.length() < 40 else txt.substr(0, 37) + "..."], WARN, 10)


func _draw_lanes(plot: Rect2, row_h: float, pins: Rect2) -> void:
	var win := time_window()
	# Decision pins.
	for rec in decisions():
		var t := int(rec["t_ms"])
		if t < win.x or t > win.y:
			continue
		var x := _t_to_x(t, plot)
		var sel := String(rec["data"]["decision_id"]) == selected_decision
		var col := ACCENT if sel else TEXT
		var fb = rec["data"].get("fallback")
		if fb is Dictionary:
			col = BAD
		_c.draw_colored_polygon(PackedVector2Array([Vector2(x - 5, pins.position.y + 2), Vector2(x + 5, pins.position.y + 2),
			Vector2(x, pins.end.y - 1)]), col)
	_text(Vector2(8, pins.end.y - 3), "decisions ▼ (click)", DIM, 10)
	for i in lane_rows.size():
		var row: Dictionary = lane_rows[i]
		var key := String(row["key"])
		var y := plot.position.y + i * row_h
		var lane_r := Rect2(plot.position.x, y, plot.size.x, row_h)
		if i % 2 == 0:
			_c.draw_rect(Rect2(0, y, size.x, row_h), Color(1, 1, 1, 0.03))
		var built := bool(row["built"])
		var shown := built and lane_visible(key)
		_text(Vector2(8, y + row_h * 0.7), String(row["label"]), TEXT if shown else DIM, 11, NAME_W - 120)
		if not built:
			_text(Vector2(plot.position.x + 6, y + row_h * 0.7), lane_note(key), DIM, 10)
			continue
		if not shown:
			_text(Vector2(plot.position.x + 6, y + row_h * 0.7), "muted (view only)" if muted.has(key) else "hidden by solo (view only)", DIM, 10)
			continue
		match key:
			"sight":
				_lane_sight(lane_r, win)
			"hearing":
				_lane_hearing(lane_r, win)
			"tracks":
				_lane_tracks(lane_r, win)
			"head":
				_lane_head(lane_r, win)
			"pulse":
				_lane_pulse(lane_r, win)
			"model":
				_lane_model(lane_r, win)
			"actions":
				_lane_actions(lane_r, win)
			"beacon":
				_lane_beacon(lane_r, win)
	# Time axis and playhead.
	var axis_y := plot.end.y + 12
	var step := 5000 if window_ms <= 60000 else (30000 if window_ms <= 480000 else 120000)
	var tick_t := floori(float(win.x) / step) * step
	while tick_t <= win.y:
		if tick_t >= win.x:
			var x := _t_to_x(tick_t, plot)
			_c.draw_line(Vector2(x, plot.end.y), Vector2(x, plot.end.y + 4), DIM, 1.0)
			_text(Vector2(x + 2, axis_y), "%.0f s" % (tick_t / 1000.0), DIM, 10)
		tick_t += step
	var px := _t_to_x(playhead_ms, plot)
	_c.draw_line(Vector2(px, pins.position.y), Vector2(px, plot.end.y), ACCENT, 2.0)


func _lane_sight(r: Rect2, win: Vector2i) -> void:
	var last_x := -1.0
	var segs := PackedVector2Array()   # one batched draw call for the whole lane
	for rec in store.between(observer, "sight", win.x, win.y):
		var x := _t_to_x(int(rec["t_ms"]), r)
		if x - last_x < 1.0:
			continue
		last_x = x
		var n := 0
		for item in rec["data"]["items"]:
			if item["validity"] == "OBSERVED" or item["validity"] == "DEGRADED":
				n += 1
		if n > 0:
			var hh := minf(r.size.y - 4, 4.0 * n)
			segs.append(Vector2(x, r.end.y - 2))
			segs.append(Vector2(x, r.end.y - 2 - hh))
	if not segs.is_empty():
		_c.draw_multiline(segs, Color(OK_COLOR, 0.7), 1.0)


func _lane_hearing(r: Rect2, win: Vector2i) -> void:
	for rec in store.between(observer, "hearing", win.x, win.y):
		var x := _t_to_x(int(rec["t_ms"]), r)
		_text(Vector2(x - 3, r.end.y - 4), "▲" if rec["data"].get("addressed") else "·", WARN, 11)


func _lane_tracks(r: Rect2, win: Vector2i) -> void:
	for rec in store.between(observer, "tracks", win.x, win.y):
		var x := _t_to_x(int(rec["t_ms"]), r)
		var ev := String(rec["data"]["event"])
		var col := OK_COLOR if ev != "LOST" else DIM
		_c.draw_line(Vector2(x, r.position.y + 2), Vector2(x, r.end.y - 2), col, 1.0)
		_text(Vector2(x + 2, r.end.y - 4), "%s %s" % [ev, store.track_label(observer, rec["data"]["track"])], col, 9)


func _lane_head(r: Rect2, win: Vector2i) -> void:
	var pts := PackedVector2Array()
	var last_x := -1.0
	for rec in store.between(observer, "sight", win.x, win.y):
		var x := _t_to_x(int(rec["t_ms"]), r)
		if x - last_x < 2.0:
			continue
		last_x = x
		var hy := float(rec["data"]["pose"].get("head_yaw", 0.0))
		pts.append(Vector2(x, r.get_center().y - clampf(hy / (PI / 2), -1, 1) * (r.size.y / 2 - 2)))
	if pts.size() >= 2:
		_c.draw_polyline(pts, Color(ACCENT, 0.8), 1.0)
	for rec in store.between(observer, "pulse", win.x, win.y):
		var ev := String(rec["data"]["event"])
		if ev in ["GLANCE", "GAZE_HOLD", "GAZE_RETURN", "GAZE_PARTNER"]:
			_text(Vector2(_t_to_x(int(rec["t_ms"]), r) - 3, r.end.y - 3), "g" if ev == "GLANCE" else "·", TEXT, 10)


func _lane_pulse(r: Rect2, win: Vector2i) -> void:
	for rec in store.between(observer, "decision", win.x - window_ms, win.y):
		var act = rec["data"].get("activity")
		if act is Dictionary:
			var x := maxf(_t_to_x(int(rec["t_ms"]), r), r.position.x)
			_c.draw_line(Vector2(x, r.position.y + 1), Vector2(x, r.end.y - 1), Color(TEXT, 0.4), 1.0)
			_text(Vector2(x + 2, r.position.y + 10), String(act.get("kind", "?")), TEXT, 9)
	for rec in store.between(observer, "pulse", win.x, win.y):
		var ev := String(rec["data"]["event"])
		var glyph := String({"WAKE": "W", "REVIEW": "R", "CONTINUE": "c", "IDLE_DEBIT": "$", "ACTIVITY_DROPPED": "×", "PREEMPTED": "p"}.get(ev, ""))
		if glyph != "":
			_text(Vector2(_t_to_x(int(rec["t_ms"]), r) - 3, r.end.y - 2), glyph, WARN, 10)


func _lane_model(r: Rect2, win: Vector2i) -> void:
	var queue_segs := PackedVector2Array()
	var model_segs := PackedVector2Array()
	for rec in store.between(observer, "decision", win.x - 10000, win.y):
		var t := int(rec["t_ms"])
		for c in rec["data"].get("calls", []):
			var x0 := _t_to_x(t, r)
			var q := float(c.get("queue_ms", 0) if c.get("queue_ms") != null else 0)
			var total := float(c.get("total_ms", 0) if c.get("total_ms") != null else 0)
			var xq := _t_to_x(t + int(q), r)
			var x1 := maxf(_t_to_x(t + int(total), r), x0 + 2)
			var mid := r.get_center().y
			queue_segs.append_array([Vector2(x0, mid), Vector2(xq, mid)])     # queue
			model_segs.append_array([Vector2(xq, mid), Vector2(x1, mid)])     # in the model
			var outcome := String(c["outcome"])
			var glyph := "✓" if outcome == "VALID" else ("T" if outcome == "TIMEOUT" else "✗")
			if c.has("salvaged"):
				glyph = "S"
			_text(Vector2(x1 + 2, r.end.y - 3), glyph, OK_COLOR if glyph in ["✓", "S"] else BAD, 10)
	if not queue_segs.is_empty():
		_c.draw_multiline(queue_segs, Color(DIM, 0.8), 3.0)
		_c.draw_multiline(model_segs, Color(ACCENT, 0.9), 5.0)


func _lane_actions(r: Rect2, win: Vector2i) -> void:
	var reqs: Dictionary = store.requests.get(observer, {})
	for rec in store.between(observer, "action", win.x, win.y):
		var rid := String(rec["data"]["request_id"])
		var res: Dictionary = reqs.get(rid, {}).get("result", {})
		var glyph := "…"
		var col := DIM
		if not res.is_empty():
			glyph = "✓" if bool(res["data"]["accepted"]) else "✗"
			col = OK_COLOR if bool(res["data"]["accepted"]) else BAD
		_text(Vector2(_t_to_x(int(rec["t_ms"]), r) - 3, r.end.y - 3), glyph, col, 10)
	for rec in store.between(observer, "delivery", win.x, win.y):
		if String(rec["data"]["event"]) == "DROPPED":
			_text(Vector2(_t_to_x(int(rec["t_ms"]), r) - 3, r.position.y + 10), "⊘", WARN, 10)


func _lane_beacon(r: Rect2, win: Vector2i) -> void:
	var recs := store.records(observer, "beacon")
	for i in range(maxi(store.first_at_or_after(recs, win.x) - 1, 0), recs.size()):
		var t0 := int(recs[i]["t_ms"])
		var t1 := int(recs[i + 1]["t_ms"]) if i + 1 < recs.size() else maxi(store.t_max, playhead_ms)
		if t1 < win.x or t0 > win.y:
			continue
		var x0 := maxf(_t_to_x(t0, r), r.position.x)
		var x1 := minf(_t_to_x(t1, r), r.end.x)
		var d: Dictionary = recs[i]["data"]
		_c.draw_rect(Rect2(x0, r.position.y + 3, maxf(x1 - x0 - 1, 1), r.size.y - 6), Color(ACCENT, 0.15))
		_text(Vector2(x0 + 2, r.end.y - 4), String(d.get("ambient_state", d["expression_id"])).to_lower(), TEXT, 9, maxf(x1 - x0 - 3, 1))
