extends Control
## Connection/contract harness only. No Expo navigation or mode authority yet.

var output: Label
var request: HTTPRequest
var send_button: Button
var endpoint := "http://127.0.0.1:8765/v1/decision"

func _ready() -> void:
	var column := VBoxContainer.new()
	column.position = Vector2(32, 32)
	add_child(column)
	var heading := Label.new()
	heading.text = "SOMA RANGE | Expo development harness"
	column.add_child(heading)
	var modes := Label.new()
	modes.text = "Spectator scaffold — Director and Participant are planned."
	column.add_child(modes)
	var actors := Label.new()
	actors.text = "Fixture: Visitor X says hello to Robot R. No live NPCs or sensing."
	column.add_child(actors)
	send_button = Button.new()
	send_button.text = "Send synthetic observation to offline Python adapter"
	send_button.pressed.connect(_send_demo)
	column.add_child(send_button)
	output = Label.new()
	output.text = "Start the sidecar first. No credentials or internet required."
	column.add_child(output)
	request = HTTPRequest.new()
	request.timeout = 5.0
	request.request_completed.connect(_completed)
	add_child(request)

func _send_demo() -> void:
	var observation := {
		"protocol": "soma-range/1", "trace_id": "expo-001:1:hello",
		"tick": 1, "recipient_id": "robot-r", "source_id": "visitor-x",
		"channel": "speech", "visibility": "public", "content": "Hello Robot R"
	}
	send_button.disabled = true
	var error := request.request(endpoint,
		PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST,
		JSON.stringify({"observation": observation, "horizon_arm": "A"}))
	if error != OK:
		send_button.disabled = false
		output.text = "Could not start sidecar request: %s" % error

func _completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	send_button.disabled = false
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		output.text = "Sidecar unavailable or rejected request (%s/%s)." % [result, code]
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if not parsed is Dictionary or parsed.get("protocol") != "soma-range/1":
		output.text = "Invalid decision protocol."
		return
	if parsed.get("actor_id") != "robot-r" or parsed.get("observation_trace_id") != "expo-001:1:hello":
		output.text = "Decision recipient/trace mismatch."
		return
	if parsed.get("action") not in ["acknowledge", "wait"]:
		output.text = "Unsupported action."
		return
	output.text = "Offline decision (display only): %s\nTrace: %s" % [parsed.action, parsed.trace_id]
