class_name Palette
extends RefCounted
## V0 greybox colors (ART_DIRECTION §7). One shared matte material per color.
## Identity trim colors avoid the Beacon hues (yellow, blue, purple, orange, red, white; D-14).

const COLORS := {
	"background": Color("#d9dde2"),
	"floor": Color("#c9c6bd"),
	"floor_grid": Color("#aeaa9f"),
	"wall": Color("#e4e1da"),
	"partition": Color("#8e99a5"),
	"platform": Color("#b3ab9e"),
	"ramp": Color("#c2b8a6"),
	"stairs": Color("#a99f8f"),
	"reflective_a": Color("#eeeeee"),
	"reflective_b": Color("#4d6a85"),
	"prop_dark": Color("#3b3e43"),
	"prop_mid": Color("#6d7178"),
	"chair": Color("#7f6d5b"),
	"marker": Color("#71808f"),
	"label": Color("#24272b"),
	"robot_shell": Color("#e7e7e3"),
	"robot_joint": Color("#4a4d52"),
	"robot_visor": Color("#0e0f11"),
	"robot_wheel": Color("#25272a"),
	"robot_ear": Color("#b8bbbf"),
	"robot_trim": Color("#4e9a5c"),
	"visitor_sand": Color("#c8a46e"),
	"visitor_slate": Color("#7c8ca3"),
	"visitor_mauve": Color("#a27f9b"),
	"visitor_face": Color("#2d2f33"),
}

static var _materials: Dictionary = {}


static func color(color_name: String) -> Color:
	if not COLORS.has(color_name):
		push_error("Palette: unknown color '%s'" % color_name)
		return Color.MAGENTA
	return COLORS[color_name]


## Shared matte material. double_sided is for hand-built meshes (ramp, stairs wedge).
static func material(color_name: String, double_sided := false) -> StandardMaterial3D:
	var key := color_name + ("/2" if double_sided else "")
	if _materials.has(key):
		return _materials[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color(color_name)
	m.roughness = 0.9
	m.metallic = 0.0
	if double_sided:
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	_materials[key] = m
	return m


## Semi-transparent dark overlay whose strength follows a zone's light_level (ART_DIRECTION §5).
static func shade_material(light_level: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.05, 0.06, 0.08, clampf((1.0 - light_level) * 0.6, 0.0, 0.6))
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m
