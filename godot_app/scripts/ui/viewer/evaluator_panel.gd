class_name EvaluatorPanel
extends PanelContainer
## EVALUATOR TRUTH (G4a, D-90; INTERACTION_MODES §4): what the simulator knows and no agent sees:
## which avatar each of the observer's tracks was, the scenario's labels, every cast member's private
## goal, and the selected decision's assembled prompt and raw answer (an NPC's prompt holds its own
## private goal, D-51, so prompt text is evaluator-only).
##
## A separate panel, always labelled EVALUATOR TRUTH, in its own look (amber border) so it is never
## mistaken for what an agent perceives. It is created only for a seat holding VIEW_EVALUATOR_TRUTH
## (`create` returns null for any other seat), and every refresh asks the world dispatcher again.

const TITLE := "EVALUATOR TRUTH — what the simulator knows; no agent sees this"
const BORDER := Color("#e0a040")
const MAX_PROMPT_CHARS := 6000

var store: ViewerStore
var dispatcher: WorldDispatcher
var observer := ""
var decision_id := ""
var body: RichTextLabel
var refreshes := 0


## The panel for this seat, or null when the seat may not see evaluator truth (D-90).
static func create(viewer_store: ViewerStore, seat_dispatcher: WorldDispatcher) -> EvaluatorPanel:
	if seat_dispatcher == null or seat_dispatcher.seat_request("VIEW_EVALUATOR_TRUTH")["code"] != "OK":
		return null
	var p := EvaluatorPanel.new()
	p.store = viewer_store
	p.dispatcher = seat_dispatcher
	return p


func _init() -> void:
	name = "EvaluatorPanel"
	process_mode = Node.PROCESS_MODE_ALWAYS


func _ready() -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.07, 0.04, 0.92)
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
	title.name = "Title"
	title.text = TITLE
	title.add_theme_color_override("font_color", BORDER)
	title.add_theme_font_size_override("font_size", 15)
	box.add_child(title)
	body = RichTextLabel.new()
	body.name = "Body"
	body.bbcode_enabled = false
	body.scroll_active = true
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_font_size_override("normal_font_size", 12)
	box.add_child(body)
	refresh()


func show_for(avatar_id: String, selected_decision: String) -> void:
	observer = avatar_id
	decision_id = selected_decision
	refresh()


func refresh() -> void:
	if body == null:
		return
	body.text = text_for()
	refreshes += 1


## The panel's text. Empty unless the dispatcher still allows it.
func text_for() -> String:
	if dispatcher == null or not dispatcher.allows("VIEW_EVALUATOR_TRUTH", observer):
		return ""
	var lines: Array[String] = ["Observer: %s" % observer, "", "Its tracks were (real ids):"]
	var tracks := _tracks()
	if tracks.is_empty():
		lines.append("  (none yet)")
	var ids := tracks.keys()
	ids.sort()
	for t in ids:
		var h := String(store.handles.get(observer, {}).get(String(t), ""))
		lines.append("  %s%s = %s" % [t, (" (%s)" % h) if h != "" else "", tracks[t]])
	for rec in store.evaluator_records("", "truth_labels"):
		var d: Dictionary = rec["data"]
		lines.append("")
		lines.append("Scenario %s labels: %s" % [d["scenario_id"], JSON.stringify(d.get("evaluator_only", {}))])
		lines.append("Measures: %s" % ", ".join(d.get("measure", [])))
	for rec in store.evaluator_records("", "truth_goals"):
		lines.append("")
		lines.append("Private goals:")
		var goals: Dictionary = rec["data"]["goals"]
		for a in goals:
			lines.append("  %s (%s): %s" % [a, goals[a]["persona_id"], str(goals[a]["private_goal"])])
	if decision_id != "":
		lines.append("")
		lines.append("Decision %s — prompt as assembled:" % decision_id)
		var found := false
		for rec in store.evaluator_records(observer, "prompt"):
			if String(rec["data"]["decision_id"]) == decision_id:
				var text := String(rec["data"]["prompt"])
				lines.append(text if text.length() <= MAX_PROMPT_CHARS else text.substr(0, MAX_PROMPT_CHARS) + "\n[... cut for display]")
				found = true
		if not found:
			lines.append("  (no prompt: this decision made no model call)")
		for rec in store.evaluator_records(observer, "answer"):
			if String(rec["data"]["decision_id"]) == decision_id:
				for ans in rec["data"]["answers"]:
					lines.append("Raw answer %s: %s" % [ans["call_id"], str(ans.get("response_text"))])
					if ans.get("error") != null:
						lines.append("  error: %s" % str(ans["error"]))
				if rec["data"].has("reason_summary"):
					lines.append("Reason summary (the model's own words): %s" % rec["data"]["reason_summary"])
	return "\n".join(lines)


## Live: the world's own track table through the dispatcher; replay: Godot's truth_tracks.json.
func _tracks() -> Dictionary:
	if dispatcher.world != null and dispatcher.world.senses != null:
		return dispatcher.truth_tracks(observer)
	var out := {}
	for rec in store.evaluator_records(observer, "truth_tracks"):
		out = rec["data"]["tracks"]
	return out
