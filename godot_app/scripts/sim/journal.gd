class_name Journal
extends RefCounted
## The world's event journal (D-41): one JSON object per line, in the journal_entry contract
## (contracts/journal_entry.schema.json). Godot writes it; tools/godot_check.py checks every
## line with the same contract in Python. Keys are sorted, so the same run gives the same
## bytes, and digest() is a SHA-256 over all lines (replay and determinism checks).

const DEFAULT_DIR := "user://journals"
const KEEP_RUNS := 10

var path := ""
var seq := 0
var _file: FileAccess
var _hash := HashingContext.new()


## Open a new journal file. Returns false (and prints why) if it cannot be written.
func open(file_path: String) -> bool:
	DirAccess.make_dir_recursive_absolute(file_path.get_base_dir())
	_file = FileAccess.open(file_path, FileAccess.WRITE)
	if _file == null:
		push_error("Journal: cannot write %s (%s)" % [file_path, error_string(FileAccess.get_open_error())])
		return false
	path = file_path
	_hash.start(HashingContext.HASH_SHA256)
	return true


func is_open() -> bool:
	return _file != null


func write(kind: String, tick: int, actor_id, payload: Dictionary) -> void:
	if _file == null:
		return
	var entry := {
		"schema_version": "1.0",
		"seq": seq,
		"tick_id": tick,
		"sim_time_ms": SimClock.ms_at(tick),
		"kind": kind,
		"actor_id": actor_id,
		"payload": payload,
	}
	var line := JSON.stringify(entry, "", true)
	_file.store_line(line)
	_hash.update((line + "\n").to_utf8_buffer())
	seq += 1


## Close the file and return the SHA-256 of everything written, as hex.
func close() -> String:
	if _file == null:
		return ""
	_file.close()
	_file = null
	return _hash.finish().hex_encode()


## A fresh file name in the default folder, keeping only the newest KEEP_RUNS journals.
static func new_default_path(run_id: String) -> String:
	DirAccess.make_dir_recursive_absolute(DEFAULT_DIR)
	var files := Array(DirAccess.get_files_at(DEFAULT_DIR)).filter(func(f: String) -> bool: return f.ends_with(".jsonl"))
	files.sort()
	while files.size() >= KEEP_RUNS:
		DirAccess.remove_absolute(DEFAULT_DIR.path_join(files.pop_front()))
	return DEFAULT_DIR.path_join(run_id + ".jsonl")
