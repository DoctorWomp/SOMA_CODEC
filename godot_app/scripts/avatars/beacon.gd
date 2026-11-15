class_name Beacon
extends Node3D
## The Beacon display of a robot (D-14, D-19, D-52): a glyph and a light, shown by
## Avatar.show_expression(). Emissive only on the display parts, so identity trim colors are
## never read as signals (ART_DIRECTION §2). Rendering only: what others perceive comes from the
## observer filter, never from these nodes.

var glyph: Label3D
var lights: Array[MeshInstance3D] = []
var light_state := "OFF"
var pattern := "STEADY"
var _original: Array[Material] = []
var _material: StandardMaterial3D
var _glyph_size := 0.0


## `glyph_pos`/`glyph_facing` place the glyph (in `parent` space); `light_meshes` light up.
static func attach(parent: Node3D, glyph_pos: Vector3, glyph_size_m: float, light_meshes: Array[MeshInstance3D]) -> Beacon:
	var b := Beacon.new()
	b.name = "Beacon"
	parent.add_child(b)
	b.glyph = MeshKit.label("", 48, false)
	b.glyph.name = "Glyph"
	b._glyph_size = glyph_size_m
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
	b._material = StandardMaterial3D.new()
	b._material.emission_enabled = true
	b._material.roughness = 0.4
	return b


func show_expression(glyph_text: String, light: String, light_pattern: String) -> void:
	glyph.text = glyph_text
	# Longer glyphs ("STOP") shrink to stay on the display.
	glyph.pixel_size = _glyph_size / 40.0 * minf(1.0, 2.5 / maxf(1.0, glyph_text.length()))
	glyph.visible = glyph_text != ""
	light_state = light
	pattern = light_pattern
	if light == "OFF" or not BeaconRules.LIGHT_COLORS.has(light):
		_restore()
		return
	var c: Color = BeaconRules.LIGHT_COLORS[light]
	_material.albedo_color = c
	_material.emission = c
	_material.emission_energy_multiplier = 1.5
	for m in lights:
		m.material_override = _material
	glyph.modulate = c.lerp(Color.WHITE, 0.3)


func clear() -> void:
	glyph.visible = false
	glyph.text = ""
	light_state = "OFF"
	_restore()


func _restore() -> void:
	for i in lights.size():
		lights[i].material_override = _original[i]


## Slow pulse, rendering only. 0.5 Hz, far below the 3 Hz limit.
func _process(_delta: float) -> void:
	if light_state == "OFF" or pattern != "SLOW_PULSE":
		return
	var phase := float(Time.get_ticks_msec()) / 1000.0 * BeaconRules.PULSE_HZ * TAU
	_material.emission_energy_multiplier = 0.6 + 0.9 * (0.5 + 0.5 * sin(phase))
