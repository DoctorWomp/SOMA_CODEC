class_name FrameStats
extends Node
## Frame pacing for the render-tax comparison (ART_DIRECTION §7; G3d, D-69). Measurement only:
## records the wall-clock interval between rendered (process) frames and samples Godot's own video
## memory once a second, and writes them to a side file at the end of the run. Nothing here
## enters the journal, so stepped runs stay byte-exact. Python summarises the file (p50/p95/p99,
## spikes) in the run's summary.json.
##
## Enabled by main.gd with -- --frame-stats=PATH.

const MAX_FRAMES := 400000          # ~1.8 h at 60 FPS; beyond that only the newest KEEP_FRAMES are kept
const KEEP_FRAMES := 200000

var frame_ms: PackedFloat32Array = PackedFloat32Array()
var dropped := 0
var video_mem_peak_bytes := 0.0
var extra: Dictionary = {}          # G4a: the viewer's state for the run (open time, draws)
var _last_usec := 0
var _next_sample_usec := 0


func _ready() -> void:
	process_priority = -1000          # first in each frame, so the interval is frame to frame
	_last_usec = Time.get_ticks_usec()


func _process(_delta: float) -> void:
	var now := Time.get_ticks_usec()
	frame_ms.append(float(now - _last_usec) / 1000.0)
	_last_usec = now
	if frame_ms.size() > MAX_FRAMES:
		dropped += frame_ms.size() - KEEP_FRAMES
		frame_ms = frame_ms.slice(frame_ms.size() - KEEP_FRAMES)
	if now >= _next_sample_usec:
		_next_sample_usec = now + 1000000
		video_mem_peak_bytes = maxf(video_mem_peak_bytes, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED))


func write(path: String) -> bool:
	var size := DisplayServer.window_get_size()
	var out := {
		"frame_ms": Array(frame_ms),
		"frames_dropped_from_record": dropped,
		"display_server": DisplayServer.get_name(),
		"rendering_method": RenderingServer.get_current_rendering_method(),
		"window_size": [size.x, size.y],
		"max_fps": Engine.max_fps,
		"vsync_mode": DisplayServer.window_get_vsync_mode(),
		"godot_video_mem_peak_mib": snappedf(video_mem_peak_bytes / 1048576.0, 0.1),
	}
	out.merge(extra)
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("frame_stats: cannot write %s" % path)
		return false
	f.store_string(JSON.stringify(out))
	f.close()
	return true
