extends SceneTree
## Loads every GDScript in the project, so a script that fails to parse (including a GDScript
## warning, which project.godot turns into an error, D-38) is reported at once. Godot's
## --import step does not compile every script, and a broken test script would otherwise make
## the test run hang instead of fail. Run by tools/godot_check.py:
##
##   godot --headless --path godot_app --script res://tests/compile_all.gd


func _initialize() -> void:
	var paths: Array[String] = []
	_collect("res://", paths)
	var failed := 0
	for path in paths:
		if path == get_script().resource_path:
			continue   # this script is already running
		var script := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as GDScript
		if script == null or not script.can_instantiate():
			failed += 1
			print("COMPILE FAIL %s" % path)
	print("COMPILE DONE scripts=%d failed=%d" % [paths.size(), failed])
	quit(1 if failed > 0 else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	for file in DirAccess.get_files_at(dir_path):
		if file.ends_with(".gd"):
			out.append(dir_path.path_join(file))
	for sub in DirAccess.get_directories_at(dir_path):
		if not sub.begins_with("."):
			_collect(dir_path.path_join(sub), out)
