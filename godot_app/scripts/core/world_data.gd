class_name WorldData
extends RefCounted
## Reads the JSON copies of configs/ that tools/export_godot_data.py writes (D-30).
##
## The export already validated every file against its contract in contracts/.
## Here we only check the wrapper and the schema version, and fail loudly.

const DATA_DIR := "res://data"
const SCHEMA_VERSION := "1.0"
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
	if data.get("schema_version") != SCHEMA_VERSION:
		push_error("WorldData: %s has schema_version %s; this build reads %s" % [
			path, data.get("schema_version"), SCHEMA_VERSION])
		return {}
	return data


static func load_map(map_id: String) -> Dictionary:
	return load_config("maps", map_id)


static func load_body(body_id: String) -> Dictionary:
	return load_config("bodies", body_id)
