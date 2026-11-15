class_name WorldData
extends RefCounted
## Reads the JSON copies of configs/ that tools/export_godot_data.py writes (D-30).
##
## The export already validated every file against its contract in contracts/.
## Here we only check the wrapper and the schema version, and fail loudly.

const DATA_DIR := "res://data"
## Contract version each config folder must carry (D-37: bodies moved to 2.0).
const SCHEMA_VERSIONS := {"maps": "1.0", "bodies": "2.0"}
const EXPORT_HINT := "Run: uv run python tools/export_godot_data.py"


static func load_config(kind: String, config_id: String) -> Dictionary:
	var path := "%s/%s/%s.json" % [DATA_DIR, kind, config_id]
	if not FileAccess.file_exists(path):
		push_error("WorldData: %s not found. %s" % [path, EXPORT_HINT])
		return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("data") or parsed.get("kind") != kind:
		push_error("WorldData: %s is not an exported '%s' file. %s" % [path, kind, EXPORT_HINT])
		return {}
	var data: Dictionary = parsed["data"]
	var expected: String = SCHEMA_VERSIONS.get(kind, "1.0")
	if data.get("schema_version") != expected:
		push_error("WorldData: %s has schema_version %s; this build reads %s" % [
			path, data.get("schema_version"), expected])
		return {}
	return data


static func load_map(map_id: String) -> Dictionary:
	return load_config("maps", map_id)


static func load_body(body_id: String) -> Dictionary:
	return load_config("bodies", body_id)


## A scenario's world-only view (D-48): no evaluator-only labels, measures or personas.
static func load_scenario(scenario_id: String) -> Dictionary:
	return load_config("scenarios", scenario_id)


## Every expression in the catalog (configs/expressions/), by id.
static func load_expressions() -> Dictionary:
	var out := {}
	var dir := DirAccess.open(DATA_DIR + "/expressions")
	if dir == null:
		push_error("WorldData: no expression catalog in %s/expressions. %s" % [DATA_DIR, EXPORT_HINT])
		return out
	var names := Array(dir.get_files())
	names.sort()
	for file_name in names:
		if String(file_name).ends_with(".json"):
			var data := load_config("expressions", String(file_name).get_basename())
			if not data.is_empty():
				out[String(data["expression_id"])] = data
	return out
