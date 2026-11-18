class_name Beacon
extends Node3D
## The Beacon display of a robot (D-14, D-19, D-52): a glyph and a light, shown by
## Avatar.show_expression(). Emissive only on the display parts, so identity trim colors are
## never read as signals (ART_DIRECTION §2). Rendering only: what others perceive comes from the
## observer filter, never from these nodes.
##
## G3e (D-73, D-74), all rendering only:
## - an ambient expression plays its glyph loop (at most 3 frames per second, D-14);
## - SWEEP moves the light across the display at 0.5 Hz (the ear pods alternate; a strip's light
##   travels along it);
## - presence signals on the ambient display only (a chosen expression shows exactly as authored):
##   seeded, irregular-looking blinks (every 3-6 s) and small eye shifts (a new offset every 2-5 s,
##   eased) on a still face, and slow light breathing (0.25 Hz) on a steady light, all scaled by
##   the presence amplitude (subtle 0 ... performative 1). Pulse and sweep depth scale with it too.
##   Nothing changes faster than 3 Hz at any amplitude.

const BLINK_S := 0.15             # a blink lasts 150 ms
const BLINK_EVERY_S := Vector2(3.0, 6.0)
const SHIFT_EVERY_S := Vector2(2.0, 5.0)
const SHIFT_EASE_S := 0.4
const MAX_EYE_SHIFT := 0.12       # of the glyph's size, at amplitude 1
const BREATH_HZ := 0.25
const MAX_BREATH_DEPTH := 0.35    # emission energy swing at amplitude 1
const SWEEP_HZ := 0.5

var glyph: Label3D
var lights: Array[MeshInstance3D] = []
var light_state := "OFF"
var pattern := "STEADY"
var frames := PackedStringArray()
var frame_hz := 0.0
var amplitude := 0.5              # the presence amplitude (D-74), set by the avatar
var seed_value := 0               # per avatar and run, so signals look irregular yet replay exactly
var _original: Array[Material] = []
var _material: StandardMaterial3D
var _materials: Array[StandardMaterial3D] = []
var _glyph_size := 0.0
var _glyph_pos := Vector3.ZERO
var _base_text := ""


## `glyph_pos`/`glyph_facing` place the glyph (in `parent` space); `light_meshes` light up.
static func attach(parent: Node3D, glyph_pos: Vector3, glyph_size_m: float, light_meshes: Array[MeshInstance3D]) -> Beacon:
	var b := Beacon.new()
	b.name = "Beacon"
	parent.add_child(b)
	b.glyph = MeshKit.label("", 48, false)
	b.glyph.name = "Glyph"
	b._glyph_size = glyph_size_m
	b._glyph_pos = glyph_pos
	b.glyph.pixel_size = glyph_size_m / 40.0
	b.glyph.outline_size = 0
	b.glyph.modulate = Color(0.95, 0.97, 1.0)
	b.glyph.shaded = false
	b.glyph.double_sided = false
	b.glyph.no_depth_test = false
	b.glyph.billboard = BaseMaterial3D.BILLBOARD_DISABLED
	# Label3D text faces +z; the display faces -z (forward).
	b.glyph.transform = Transform3D(Basis.looking_at(Vector3.BACK, Vector3.UP), glyph_pos)
	b.glyph.visible = false
	parent.add_child(b.glyph)
	b.lights = light_meshes
	for m in light_meshes:
		b._original.append(m.material_override)
		var mat := StandardMaterial3D.new()
		mat.emission_enabled = true
		mat.roughness = 0.4
		b._materials.append(mat)
	b._material = StandardMaterial3D.new()
	b._material.emission_enabled = true
	b._material.roughness = 0.4
	return b


func show_expression(glyph_text: String, light: String, light_pattern: String,
		glyph_frames := PackedStringArray(), glyph_frame_hz := 0.0) -> void:
	frames = glyph_frames
	frame_hz = minf(glyph_frame_hz, BeaconRules.MAX_FLASH_HZ)
	_base_text = glyph_text
	_set_text(glyph_text)
	glyph.visible = glyph_text != ""
	light_state = light
	pattern = light_pattern
	if light == "OFF" or not BeaconRules.LIGHT_COLORS.has(light):
		_restore()
		return
	var c: Color = BeaconRules.LIGHT_COLORS[light]
	for i in lights.size():
		_materials[i].albedo_color = c
		_materials[i].emission = c
		_materials[i].emission_energy_multiplier = 1.5
		lights[i].material_override = _materials[i]
	_material.albedo_color = c
	_material.emission = c
	glyph.modulate = c.lerp(Color.WHITE, 0.3)


func clear() -> void:
	glyph.visible = false
	glyph.text = ""
	_base_text = ""
	frames = PackedStringArray()
	light_state = "OFF"
	_restore()


func _set_text(text: String) -> void:
	glyph.text = text
	# Longer glyphs ("STOP") shrink to stay on the display.
	glyph.pixel_size = _glyph_size / 40.0 * minf(1.0, 2.5 / maxf(1.0, text.length()))


func _restore() -> void:
	for i in lights.size():
		lights[i].material_override = _original[i]


## What the display shows at time `t_s` (rendering only): {"text", "eye_shift" (meters),
## "energy": [per light]}. Pure and seeded, so tests can measure it at any amplitude.
func frame_at(t_s: float) -> Dictionary:
	var text := _base_text
	if frames.size() > 1 and frame_hz > 0.0:
		text = frames[int(floorf(t_s * frame_hz)) % frames.size()]
	var ambient := frames.size() > 0
	var still_face := frames.size() == 1
	var sig := presence_signal(t_s, seed_value, amplitude)
	if bool(sig["blink"]) and still_face:
		text = blink_text(text)                     # blinks only on a still ambient face, never on a loop
	var energy: Array[float] = []
	var depth := MAX_BREATH_DEPTH * amplitude if ambient else 0.0
	var swing := (0.3 + 0.6 * amplitude) if ambient else 0.9         # a chosen expression pulses as authored
	for i in lights.size():
		var e := 1.5
		match pattern:
			"SLOW_PULSE":
				e = 0.6 + swing * (0.5 + 0.5 * sin(t_s * BeaconRules.PULSE_HZ * TAU))
			"SWEEP":
				var phase := t_s * SWEEP_HZ * TAU + PI * float(i) / maxf(1.0, float(lights.size() - 1))
				e = 0.6 + swing * (0.5 + 0.5 * sin(phase))
			_:
				e = 1.5 + float(sig["breath"]) * depth
		energy.append(e)
	return {"text": text, "eye_shift": float(sig["eye_shift"]) * _glyph_size if still_face else 0.0, "energy": energy}


## Presence signals at time `t_s` for one avatar (D-74): {"blink": bool, "eye_shift": -1..1 times
## MAX_EYE_SHIFT x amplitude (of the glyph's size), "breath": -1..1}. Blinks come every 3-6 s
## (seeded intervals), eye shifts every 2-5 s eased over 0.4 s: both far below 3 Hz.
static func presence_signal(t_s: float, avatar_seed: int, amp: float) -> Dictionary:
	var a := clampf(amp, 0.0, 1.0)
	var blink := false
	if a > 0.0:
		var t := 0.0
		var k := 0
		while t <= t_s and k < 100000:
			var next := t + lerpf(BLINK_EVERY_S.x, BLINK_EVERY_S.y, _rand(avatar_seed, 1, k))
			if t_s >= next and t_s < next + BLINK_S:
				blink = true
				break
			t = next
			k += 1
	# Eye shifts: piecewise targets in -1..1 at seeded times, eased between them.
	var start := 0.0
	var j := 0
	var prev := 0.0
	var cur := 0.0
	while j < 100000:
		var length := lerpf(SHIFT_EVERY_S.x, SHIFT_EVERY_S.y, _rand(avatar_seed, 2, j))
		prev = cur
		cur = _rand(avatar_seed, 3, j) * 2.0 - 1.0
		if t_s < start + length:
			var w := smoothstep(0.0, SHIFT_EASE_S, t_s - start)
			var shift := lerpf(prev, cur, w) * MAX_EYE_SHIFT * a
			return {"blink": blink, "eye_shift": shift, "breath": sin(t_s * BREATH_HZ * TAU)}
		start += length
		j += 1
	return {"blink": blink, "eye_shift": 0.0, "breath": sin(t_s * BREATH_HZ * TAU)}


## Eyes closed: the face's eye characters become dashes.
static func blink_text(text: String) -> String:
	return text.replace("o", "-").replace("O", "-").replace(".", "-")


static func _rand(avatar_seed: int, stream: int, k: int) -> float:
	return float(hash([avatar_seed, stream, k]) & 0xFFFFFF) / float(0x1000000)


func _process(_delta: float) -> void:
	if not glyph.visible and light_state == "OFF":
		return
	var f := frame_at(float(Time.get_ticks_msec()) / 1000.0)
	if glyph.visible and glyph.text != String(f["text"]):
		_set_text(String(f["text"]))
	glyph.position = _glyph_pos + Vector3(float(f["eye_shift"]), 0, 0)
	if light_state == "OFF":
		return
	var energy: Array = f["energy"]
	for i in lights.size():
		_materials[i].emission_energy_multiplier = float(energy[i])
