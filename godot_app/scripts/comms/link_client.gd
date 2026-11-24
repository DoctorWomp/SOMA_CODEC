class_name LinkClient
extends Node
## The Godot end of the Godot ↔ Python link (D-05, D-43). Connects to the sidecar on 127.0.0.1
## with the session token from the RANGE_SESSION_TOKEN environment variable in the handshake
## (never in a message or a log). Sends link.hello, then each controlled agent's observation
## packets at every sample; answers each agent.action_request with the action gate's
## world.action_result.
##
## LIVE runs (default, D-44): the world never waits for Python. Everything here is polled once
## per frame, the outgoing queue is capped (oldest dropped first), inbound messages are
## size-limited, and a lost or refused connection is retried with back-off while the simulation
## keeps its 60 Hz tick.
##
## STEPPED runs (D-48): after each sample's packets this sends link.step SAMPLE_SENT and holds
## the world until the sidecar's link.step AGENTS_DONE for that sample. Only the world waits; this
## node, the camera and the UI keep running. If no answer comes within STEP_TIMEOUT_MS the world
## goes on, and the journal records it (the run is then not a valid stepped run).

signal status_changed(status: String)
signal ready_changed(is_ready: bool)

const TOKEN_ENV := "RANGE_SESSION_TOKEN"
const TOKEN_HEADER := "X-Range-Session-Token"
const MAX_QUEUE := 256
const MAX_MESSAGE_BYTES := 64 * 1024
const HEARTBEAT_MS := 1000
const CLOSE_UNAUTHORIZED := 4401   # wrong or missing session token
const CLOSE_BUSY := 4409           # another client is connected
const RETRY_MIN_MS := 500
const RETRY_MAX_MS := 8000
const CONNECT_TIMEOUT_MS := 3000   # give up on a connection that never opens (Windows never reports a refused local port)
const ENVELOPE_TYPES := ["world.observation", "horizon.delta_feature", "horizon.hypothesis", "agent.action_request",
	"world.action_result", "comms.event", "director.intervention", "link.hello", "link.heartbeat", "link.step"]
const STEP_TIMEOUT_MS := 15000

var world: RangeWorld
var port := 0
var agents: Array = []
var status := "IDLE"     # IDLE, CONNECTING, CONNECTED, DISCONNECTED, REFUSED
var run_mode := "LIVE"   # LIVE or STEPPED (D-48)
var sidecar_ready := false   # the sidecar answered link.hello
var waiting_step := -1   # stepped: the sample tick the world is held for, or -1
var stats := {"sent": 0, "received": 0, "dropped": 0, "invalid": 0, "connects": 0, "disconnects": 0, "refused": 0,
	"steps": 0, "step_timeouts": 0}
var _step_started_ms := 0
var _token := ""
var _ws: WebSocketPeer
var _queue: Array[String] = []
var _was_open := false
var _retry_ms := RETRY_MIN_MS
var _next_attempt_ms := 0
var _connect_started_ms := 0
var _last_heartbeat_ms := 0
var _seq := 0


func _init() -> void:
	name = "LinkClient"
	process_mode = Node.PROCESS_MODE_ALWAYS


## Start linking `controlled_agents` to the sidecar on `link_port`. `token` defaults to the
## RANGE_SESSION_TOKEN environment variable.
func setup(target_world: RangeWorld, link_port: int, controlled_agents: Array, token := "", mode := "LIVE") -> void:
	world = target_world
	run_mode = mode
	port = link_port
	agents = controlled_agents
	_token = token if token != "" else OS.get_environment(TOKEN_ENV)
	world.senses.sampled.connect(_on_sampled)


func is_connected_to_sidecar() -> bool:
	return status == "CONNECTED"


func _process(_delta: float) -> void:
	if world == null:
		return
	var now := Time.get_ticks_msec()
	if _ws == null:
		_check_step_timeout(now)
		if now >= _next_attempt_ms:
			_connect()
		return
	_ws.poll()
	match _ws.get_ready_state():
		WebSocketPeer.STATE_CONNECTING:
			if now - _connect_started_ms >= CONNECT_TIMEOUT_MS:
				_ws.close()
				_ws = null
				stats["refused"] += 1
				_set_status("REFUSED", "no answer from the sidecar within %d ms" % CONNECT_TIMEOUT_MS)
				_set_ready(false)
				_check_step_timeout(now)
				_next_attempt_ms = now + _retry_ms
				_retry_ms = mini(_retry_ms * 2, RETRY_MAX_MS)
		WebSocketPeer.STATE_OPEN:
			if not _was_open:
				_was_open = true
				stats["connects"] += 1
				_queue.push_front(_envelope("link.hello", {"protocol": "range-link/1", "agents": agents,
					"tick_hz": SimClock.TICK_HZ, "sample_hz": world.sample_hz, "map_id": String(world.map_data["map_id"]),
					"run_mode": run_mode}))
				_set_status("CONNECTED", "")
			if stats["received"] > 0:
				_retry_ms = RETRY_MIN_MS   # a real exchange happened: reconnect quickly next time
			while _ws.get_available_packet_count() > 0:
				_on_message(_ws.get_packet())
			if now - _last_heartbeat_ms >= HEARTBEAT_MS:
				_last_heartbeat_ms = now
				_enqueue(_envelope("link.heartbeat", {}))
			while not _queue.is_empty() and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
				if _ws.send_text(_queue.pop_front()) == OK:
					stats["sent"] += 1
			_check_step_timeout(now)
		WebSocketPeer.STATE_CLOSED:
			var code := _ws.get_close_code()
			if code == CLOSE_UNAUTHORIZED or code == CLOSE_BUSY:
				stats["refused"] += 1
				_set_status("REFUSED", "the sidecar refused this session (close code %d)" % code)
			elif _was_open:
				stats["disconnects"] += 1
				_set_status("DISCONNECTED", "closed (code %d)" % code)
			else:
				stats["refused"] += 1
				_set_status("REFUSED", "handshake refused or no sidecar listening")
			_ws = null
			_was_open = false
			_set_ready(false)
			_check_step_timeout(now)
			_next_attempt_ms = now + _retry_ms
			_retry_ms = mini(_retry_ms * 2, RETRY_MAX_MS)


func _connect() -> void:
	_ws = WebSocketPeer.new()
	_ws.handshake_headers = PackedStringArray([TOKEN_HEADER + ": " + _token])
	_ws.inbound_buffer_size = MAX_MESSAGE_BYTES
	_ws.outbound_buffer_size = MAX_MESSAGE_BYTES * 4
	_connect_started_ms = Time.get_ticks_msec()
	if _ws.connect_to_url("ws://127.0.0.1:%d" % port) != OK:
		_ws = null
		stats["refused"] += 1
		_set_status("REFUSED", "could not start a connection")
		_next_attempt_ms = Time.get_ticks_msec() + _retry_ms
		return
	if status != "CONNECTING":
		status = "CONNECTING"


func _set_status(new_status: String, detail: String) -> void:
	if status == new_status:
		return
	status = new_status
	var payload := {"status": new_status}
	if detail != "":
		payload["detail"] = detail
	world.journal_write("LINK_STATUS", null, payload)
	status_changed.emit(new_status)


func _on_sampled(tick: int, packets: Dictionary) -> void:
	if status != "CONNECTED":
		return
	for agent_id in agents:
		if packets.has(agent_id):
			_enqueue(_envelope("world.observation", packets[agent_id]))
	if run_mode == "STEPPED" and sidecar_ready:
		_enqueue(_envelope("link.step", {"sample_tick_id": tick, "phase": "SAMPLE_SENT"}))
		waiting_step = tick
		_step_started_ms = Time.get_ticks_msec()
		stats["steps"] += 1
		world.hold("step")


func _set_ready(value: bool) -> void:
	if sidecar_ready != value:
		sidecar_ready = value
		ready_changed.emit(value)


## A stepped run never freezes for good: after STEP_TIMEOUT_MS without AGENTS_DONE the world goes
## on, and the journal says so (wall-clock time decides here, so such a run is not deterministic).
func _check_step_timeout(now: int) -> void:
	if waiting_step < 0 or now - _step_started_ms < STEP_TIMEOUT_MS:
		return
	stats["step_timeouts"] += 1
	world.journal_write("LINK_STATUS", null, {"status": "DISCONNECTED" if status != "CONNECTED" else "CONNECTED",
		"detail": "stepped run: no AGENTS_DONE for sample %d within %d ms; the world went on" % [waiting_step, STEP_TIMEOUT_MS]})
	waiting_step = -1
	world.release("step")


func _enqueue(text: String) -> void:
	_queue.append(text)
	while _queue.size() > MAX_QUEUE:
		_queue.pop_front()
		stats["dropped"] += 1


func _envelope(kind: String, payload: Dictionary) -> String:
	_seq += 1
	var tick := world.clock.tick
	return JSON.stringify({"schema_version": "1.0", "message_id": "gd_%06d" % _seq, "type": kind, "tick_id": tick,
		"sim_time_ms": SimClock.ms_at(tick), "source": "godot_world", "payload": payload}, "", true)


## A structural check of the envelope (the sidecar validates the full contracts); anything odd
## is counted and ignored, never acted on.
func _on_message(raw: PackedByteArray) -> void:
	stats["received"] += 1
	if raw.size() > MAX_MESSAGE_BYTES:
		stats["invalid"] += 1
		return
	var env = JSON.parse_string(raw.get_string_from_utf8())
	if typeof(env) != TYPE_DICTIONARY or env.get("schema_version") != "1.0" or not ENVELOPE_TYPES.has(env.get("type")) \
			or not env.get("payload") is Dictionary or env.get("source") != "range_service":
		stats["invalid"] += 1
		return
	match String(env["type"]):
		"agent.action_request":
			# Through the world dispatcher (D-90): the agent session drives only the avatars it linked
			# whose controller it runs (D-91); the action gate then checks the request as before.
			var result := world.dispatcher.agent_request(env["payload"], agents)
			_enqueue(_envelope("world.action_result", result))
		"link.hello":
			_set_ready(true)
		"link.step":
			var p: Dictionary = env["payload"]
			if p.get("phase") == "AGENTS_DONE" and int(p.get("sample_tick_id", -2)) == waiting_step:
				waiting_step = -1
				world.release("step")
		"link.heartbeat":
			pass
		_:
			pass   # valid but not for Godot: ignored
