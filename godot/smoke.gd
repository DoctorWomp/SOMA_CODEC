extends SceneTree
## Fails on missing scene/script; runtime errors are also checked by check.py.
func _initialize() -> void:
	var scene := load("res://main.tscn") as PackedScene
	if scene == null:
		quit(1)
		return
	var instance := scene.instantiate()
	root.add_child.call_deferred(instance)
	_finish.call_deferred()

func _finish() -> void:
	await process_frame
	await process_frame
	if root.get_node_or_null("RangeHarness") == null:
		quit(1)
		return
	var harness := root.get_node("RangeHarness")
	var port := OS.get_environment("RANGE_TEST_PORT")
	if port.is_empty():
		quit(1)
		return
	harness.endpoint = "http://127.0.0.1:%s/v1/decision" % port
	harness._send_demo()
	await harness.request.request_completed
	if not harness.output.text.begins_with("Offline decision (display only): acknowledge"):
		push_error("Sidecar bridge failed: " + harness.output.text)
		quit(1)
		return
	print("RANGE_GODOT_SMOKE_OK")
	quit(0)
