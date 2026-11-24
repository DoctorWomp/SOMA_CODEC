class_name ViewerStore
extends Node
## The layer viewer's data (G4a, D-93): the run's viewer feed, read from RUN/viewer/ as files.
## Live (a watched run): the sidecar appends records as they happen and this reads the new lines
## every POLL_MS. Replay: the files are read once. Nothing here is ever sent to an agent.
##
## Records are let in through the world dispatcher's audience check (D-90): a seat stores only the
## audiences it may read for each observer. The evaluator file (EVALUATOR TRUTH) is not even
## opened for a seat without VIEW_EVALUATOR_TRUTH.

const OBSERVER_FILE := "observer_feed.jsonl"
const EVALUATOR_FILE := "evaluator_truth.jsonl"
const POLL_MS := 250
const MAX_READ_BYTES := 4 * 1024 * 1024   # per poll, so a large backlog never stalls a frame for long

var dir := ""
var dispatcher: WorldDispatcher
var live := false
var meta: Dictionary = {}
var observers: Array = []
## observer -> lane -> Array of records, sorted by t_ms when `_dirty` is cleared.
var lanes: Dictionary = {}
## Evaluator-only records: "" (run level) or observer -> lane -> Array. Empty for other seats.
var evaluator: Dictionary = {}
## observer -> request id -> {"action", "result", "delivery": []}
var requests: Dictionary = {}
## observer -> track id -> handle (D-111), from the observer's own handle maps.
var handles: Dictionary = {}
var t_max := 0
var version := 0                 # bumps whenever new records arrive
var refused := 0                 # records left out by the audience check
var _offsets := {}
var _partial := {}
var _dirty := false
var _next_poll_ms := 0


func _init() -> void:
	name = "ViewerStore"
	process_mode = Node.PROCESS_MODE_ALWAYS


## Open a run's viewer folder. `is_live`: keep reading new lines as the run writes them.
func open(viewer_dir: String, seat_dispatcher: WorldDispatcher, is_live: bool) -> bool:
	dir = viewer_dir
	dispatcher = seat_dispatcher
	live = is_live
	_offsets = {OBSERVER_FILE: 0, EVALUATOR_FILE: 0}
	_partial = {OBSERVER_FILE: PackedByteArray(), EVALUATOR_FILE: PackedByteArray()}
	poll()
	return FileAccess.file_exists(dir.path_join(OBSERVER_FILE))


func _process(_delta: float) -> void:
	if not live or dir == "":
		return
	var now := Time.get_ticks_msec()
	if now >= _next_poll_ms:
		_next_poll_ms = now + POLL_MS
		poll()


## Read what is new in the feed files. Returns how many records were stored.
func poll() -> int:
	var stored := _read(OBSERVER_FILE)
	if dispatcher != null and dispatcher.allows("VIEW_EVALUATOR_TRUTH"):
		stored += _read(EVALUATOR_FILE)
	if stored > 0:
		version += 1
	return stored


func _read(file_name: String) -> int:
	var path := dir.path_join(file_name)
	if not FileAccess.file_exists(path):
		return 0
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return 0
	var length := f.get_length()
	var start: int = _offsets[file_name]
	if length <= start:
		return 0
	f.seek(start)
	var chunk := f.get_buffer(mini(length - start, MAX_READ_BYTES))
	f.close()
	_offsets[file_name] = start + chunk.size()
	var data: PackedByteArray = _partial[file_name] + chunk
	var cut := data.rfind(10)
	if cut < 0:
		_partial[file_name] = data
		return 0
	_partial[file_name] = data.slice(cut + 1)
	var stored := 0
	for line in data.slice(0, cut).get_string_from_utf8().split("\n", false):
		var rec = JSON.parse_string(line)
		if rec is Dictionary and ingest(rec):
			stored += 1
	return stored


## Store one record if this seat may read its audience for its observer.
func ingest(rec: Dictionary) -> bool:
	var observer := String(rec["observer"]) if rec.get("observer") != null else ""
	var audience := String(rec.get("audience", ""))
	if dispatcher == null or not dispatcher.audiences(observer).has(audience):
		refused += 1
		return false
	var lane := String(rec.get("lane", ""))
	var t := int(rec.get("t_ms", 0))
	if audience == "EVALUATOR":
		var per: Dictionary = evaluator.get(observer, {})
		evaluator[observer] = per
		if not per.has(lane):
			per[lane] = []
		per[lane].append(rec)
		return true
	if lane == "meta":
		meta = rec["data"]
		observers = meta.get("observers", [])
		return true
	if not lanes.has(observer):
		lanes[observer] = {}
		if not observers.has(observer):
			observers.append(observer)
	var per_lane: Dictionary = lanes[observer]
	if not per_lane.has(lane):
		per_lane[lane] = []
	per_lane[lane].append(rec)
	t_max = maxi(t_max, t)
	_dirty = true
	var data: Dictionary = rec["data"]
	match lane:
		"action", "result":
			_request(observer, String(data["request_id"]))[lane] = rec
		"delivery":
			_request(observer, String(data["action_request_id"]))["delivery"].append(rec)
		"handles":
			var mine: Dictionary = handles.get(observer, {})
			handles[observer] = mine
			for h in data["handles"]:
				mine[String(data["handles"][h])] = String(h)
	return true


func _request(observer: String, request_id: String) -> Dictionary:
	var per: Dictionary = requests.get(observer, {})
	requests[observer] = per
	if not per.has(request_id):
		per[request_id] = {"action": {}, "result": {}, "delivery": []}
	return per[request_id]


func _sort() -> void:
	if not _dirty:
		return
	_dirty = false
	for observer in lanes:
		for lane in lanes[observer]:
			(lanes[observer][lane] as Array).sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
				return int(a["t_ms"]) < int(b["t_ms"]))


func records(observer: String, lane: String) -> Array:
	_sort()
	return lanes.get(observer, {}).get(lane, [])


## The last record at or before `t` (ms), or {}.
func latest(observer: String, lane: String, t: int) -> Dictionary:
	var recs := records(observer, lane)
	var lo := 0
	var hi := recs.size() - 1
	var found := -1
	while lo <= hi:
		var mid := (lo + hi) >> 1
		if int(recs[mid]["t_ms"]) <= t:
			found = mid
			lo = mid + 1
		else:
			hi = mid - 1
	return recs[found] if found >= 0 else {}


## Records with t0 <= t_ms <= t1.
func between(observer: String, lane: String, t0: int, t1: int) -> Array:
	var out := []
	for r in records(observer, lane):
		var t := int(r["t_ms"])
		if t > t1:
			break
		if t >= t0:
			out.append(r)
	return out


## A track as this observer knows it: its own anonymous id, with its handle beside it (D-111).
func track_label(observer: String, track) -> String:
	if track == null or String(track) == "":
		return "nobody"
	var h := String(handles.get(observer, {}).get(String(track), ""))
	return String(track) + (" (%s)" % h if h != "" else "")


func evaluator_records(observer: String, lane: String) -> Array:
	return evaluator.get(observer, {}).get(lane, [])
