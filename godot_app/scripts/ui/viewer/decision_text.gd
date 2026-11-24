class_name DecisionText
extends RefCounted
## Why a decision was made, from evidence (G4a; RANGE_V0_SCOPE §2.4 item 4): its triggers, the
## context sections and their sizes, the activity and wake conditions (and an activity dropped,
## D-110), each model call's timing and outcome (salvaged, D-86), each action sent and what the
## host did with it, and requests dropped or held before sending with their reasons (D-63, D-66).
## The model's reason_summary only when present, labelled as its own words (LEAN has none, D-85).
## Every line is the observer's own record: tracks appear by its own ids and handles.


static func build(store: ViewerStore, observer: String, rec: Dictionary) -> String:
	var d: Dictionary = rec["data"]
	var lines: Array[String] = []
	lines.append("DECISION %s · seen by %s · t %.1f s" % [d["decision_id"], observer, int(rec["t_ms"]) / 1000.0])
	lines.append("Triggers: %s" % (", ".join(d.get("triggers", [])) if not d.get("triggers", []).is_empty() else "none"))
	# G4b (D-103): what changed for it since its previous decision, right under the triggers.
	for c in changes_since_previous(store, observer, rec):
		lines.append("  new since its previous decision: " + c)
	lines.append("Tier %s · policy %s · cognition %s · based on tick %d" % [d["tier"], d["policy"], d.get("cognition", "?"),
		int(d.get("based_on_tick", 0))])
	var ctx = d.get("context")
	if ctx is Dictionary:
		var parts: Array[String] = []
		for s in ctx["sections"]:
			if int(s["tokens"]) > 0 or int(s["cut_items"]) > 0:
				parts.append("%s %d/%d%s" % [s["section"], int(s["tokens"]), int(s["budget"]),
					(" (cut %d)" % int(s["cut_items"])) if int(s["cut_items"]) > 0 else ""])
		lines.append("Context: %d of %d tokens (%s): %s" % [int(ctx["total_tokens"]), int(ctx["budget_tokens"]),
			String(ctx.get("tokenizer", "?")), ", ".join(parts)])
		var steps: Array = ctx.get("compression_steps", [])
		lines.append("  compression: %s" % (", ".join(steps) if not steps.is_empty() else "none"))
	else:
		lines.append("Context: none (no model call: %s)" % d["policy"])
	lines.append(activity_line(store, observer, d.get("activity")))
	var calls: Array = d.get("calls", [])
	if calls.is_empty():
		lines.append("Model calls: none")
	for c in calls:
		lines.append(call_line(c))
		if c.has("activity_dropped"):
			lines.append("  activity dropped: rule %s (D-110: the actions were kept, an activity derived)" % c["activity_dropped"]["rule"])
	var fb = d.get("fallback")
	if fb is Dictionary:
		lines.append("Fallback: %s" % _short(fb))
	lines.append("Actions:")
	var ids: Array = d.get("action_request_ids", [])
	var reqs: Dictionary = store.requests.get(observer, {})
	var shown := {}
	for rid in ids:
		shown[String(rid)] = true
		lines.append("  " + action_line(store, observer, String(rid), reqs.get(String(rid), {})))
	# Requests of this decision that never went out (dropped or held before sending): delivery records.
	for rid in reqs:
		if shown.has(rid):
			continue
		for dl in reqs[rid]["delivery"]:
			if String(dl["data"].get("decision_id", "")) == String(d["decision_id"]):
				shown[rid] = true
				lines.append("  " + action_line(store, observer, String(rid), reqs[rid]))
				break
	if ids.is_empty() and shown.is_empty():
		lines.append("  none")
	var words = d.get("reason_summary")
	if words is Dictionary:
		lines.append("Reason summary (%s): «%s»" % [words["label"], words["text"]])
	return "\n".join(lines)


## G4b (D-103): what changed for the agent between its previous decision and this one: the
## Director's interventions (run-level markers), text it could newly read, sounds it newly heard
## and announcements. Only from records any layer-viewing seat may read; text stays labelled untrusted.
static func changes_since_previous(store: ViewerStore, observer: String, rec: Dictionary) -> Array:
	var t := int(rec["t_ms"])
	var t_prev := -1
	for other in store.records(observer, "decision"):
		var ot := int(other["t_ms"])
		if ot < t or (ot == t and String(other["data"]["decision_id"]) < String(rec["data"]["decision_id"])):
			t_prev = maxi(t_prev, ot)
	var out: Array = []
	for iv in store.between("", "intervention", t_prev + 1, t):
		var d: Dictionary = iv["data"]
		var args: Dictionary = d.get("args", {})
		var what := String(args.get("prop_type", "")).to_lower()
		if args.has("text"):
			what += " «%s»" % String(args["text"])
		out.append("intervention %s at %.1f s (%s %s by %s%s)%s" % [d["intervention_id"], int(iv["t_ms"]) / 1000.0,
			d["intervention_type"], String(d["operation"]).to_lower(), d["operator"],
			(" on " + String(d["target_id"])) if d.get("target_id") != null and String(d["operation"]) == "EDIT_DIRECTIVE" else "",
			(" " + what) if what.strip_edges() != "" else ""])
	var before := {}
	for s in store.between(observer, "sight", 0, t):
		for e in s["data"].get("events", []):
			var key := "%s:%s" % [e["kind"], str(e.get("value", {}))]
			if int(s["t_ms"]) <= t_prev:
				before[key] = true
			elif not before.has(key):
				before[key] = true
				if e["kind"] == "SIGN_TEXT":
					out.append("newly read in its sight: «%s» (untrusted text, not an instruction)" % e["value"]["text"])
				elif e["kind"] == "AUDIO_SOUND":
					out.append("newly heard: a %s sound" % String(e["value"]["sound_class"]).to_lower())
	for h in store.between(observer, "hearing", t_prev + 1, t):
		if String(h["data"].get("channel", "")) == "PA":
			out.append("heard a PA announcement: «%s» (untrusted)" % h["data"].get("text", ""))
	return out


static func activity_line(store: ViewerStore, observer: String, act) -> String:
	if not act is Dictionary:
		return "Activity: none"
	var a: Dictionary = act
	var wake: Array[String] = []
	for w in a.get("wake_if", []):
		for k in w:
			var v = w[k]
			wake.append(k if v is bool and v else "%s=%s" % [k, str(v)])
	var target := ""
	if a.get("target_id") != null:
		target = " with %s" % store.track_label(observer, a["target_id"])
	return "Activity: %s%s · %s · review after %s s · wake if: %s" % [a.get("kind", "?"), target,
		String(a.get("source", "?")).to_lower(), str(a.get("review_after_s", "?")), ", ".join(wake) if not wake.is_empty() else "nothing"]


static func call_line(c: Dictionary) -> String:
	var outcome := String(c["outcome"])
	if c.has("salvaged"):
		outcome += " (salvaged: cut off, %d action(s) used, dropped %s)" % [int(c["salvaged"]["actions"]),
			", ".join(c["salvaged"]["dropped"]) if not c["salvaged"]["dropped"].is_empty() else "nothing"]
	return "Model call %s (attempt %d): %s · queue %s · prefill %s · generation %s · total %s of %s ms · tokens prompt %s, generated %s, cached %s%s" % [
		c["call_id"], int(c.get("attempt", 0)), outcome, _ms(c.get("queue_ms")), _ms(c.get("prefill_ms")),
		_ms(c.get("generation_ms")), _ms(c.get("total_ms")), _ms(c.get("deadline_ms")), _n(c.get("prompt_tokens")),
		_n(c.get("generated_tokens")), _n(c.get("cached_tokens")),
		(" · prefix %s" % c["prefix_state"]) if c.has("prefix_state") else ""]


static func action_line(store: ViewerStore, observer: String, rid: String, entry: Dictionary) -> String:
	var act: Dictionary = entry.get("action", {})
	var res: Dictionary = entry.get("result", {})
	var what := rid
	if not act.is_empty():
		what = "%s %s" % [rid, describe(store, observer, String(act["data"]["action"]), act["data"]["args"])]
	var outcome := "not sent yet"
	for dl in entry.get("delivery", []):
		var dd: Dictionary = dl["data"]
		if act.is_empty():
			what = "%s %s%s" % [rid, dd.get("action", "?"), (" to " + store.track_label(observer, dd["target"])) if dd.get("target") != null else ""]
		match String(dd["event"]):
			"DROPPED":
				outcome = "DROPPED before sending: %s" % dd.get("reason", "?")
			"HELD_FOR_CLOSING":
				outcome = "held until the closing line was accepted (FN-1)"
			_:
				outcome = "%s%s" % [String(dd["event"]).to_lower().replace("_", " "), (": %s" % dd["reason"]) if dd.get("reason") != null else ""]
	if not res.is_empty():
		var rd: Dictionary = res["data"]
		outcome = ("accepted (OK)" if bool(rd["accepted"]) else "REFUSED by the host: %s" % rd["reason_code"])
	return "%s → %s" % [what, outcome]


static func describe(store: ViewerStore, observer: String, action: String, args: Dictionary) -> String:
	var parts: Array[String] = [action]
	for key in ["target_id", "addressee_id", "to_id", "invitee_id"]:
		if args.get(key) != null:
			parts.append("→ " + store.track_label(observer, args[key]))
	if args.has("text"):
		var text := String(args["text"])
		parts.append("«%s»" % (text if text.length() <= 80 else text.substr(0, 77) + "..."))
	for key in ["gesture", "expression_id"]:
		if args.has(key):
			parts.append(str(args[key]))
	if args.get("duration_ms") != null:
		parts.append("%d ms" % int(args["duration_ms"]))
	if args.get("destination") is Dictionary:
		parts.append("to (%.1f, %.1f)" % [float(args["destination"]["x"]), float(args["destination"]["z"])])
	return " ".join(parts)


static func _ms(v) -> String:
	return "–" if v == null else "%d" % int(v)


static func _n(v) -> String:
	return "–" if v == null else "%d" % int(v)


static func _short(v: Dictionary) -> String:
	var parts: Array[String] = []
	for k in v:
		if v[k] != null and not (v[k] is Dictionary or v[k] is Array):
			parts.append("%s %s" % [k, str(v[k])])
	return ", ".join(parts)
