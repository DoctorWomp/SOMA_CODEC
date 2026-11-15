class_name BeaconRules
extends RefCounted
## Which expressions a body can show (EXPRESSION_PRINCIPLES §1, D-14, D-36 as amended, D-52).
## Mirrors range_service/expressions.py; tests on both sides pin the same answers.
##
## - Legged and wheeled humanoids: glyph on the visor (FACE channel), light on the ear pods (LIGHT).
## - Quadrupeds: a simple symbol on a narrow light strip above the camera cluster, never over the
##   lenses, plus light (both need LIGHT).
## - People and anything else: no Beacon display.
## A body shows an expression only if it can show every part of it; otherwise nothing is shown.

const HUMANOID_KINDS := ["LEGGED_HUMANOID", "WHEELED_HUMANOID"]
const QUADRUPED_KINDS := ["QUADRUPED"]
## D-14 public palette. Green is never a light: it is identity trim.
const LIGHT_COLORS := {
	"NEUTRAL": Color("#f2f2ee"),
	"WARM": Color("#f2c14e"),
	"CALM": Color("#4a90d9"),
	"CONSIDERED": Color("#8e6cc4"),
	"CAUTION": Color("#f08a24"),
	"STOP": Color("#d64545"),
}
## Slow pulse: 0.5 Hz. Nothing flashes faster than 3 Hz (D-14).
const PULSE_HZ := 0.5
const MAX_FLASH_HZ := 3.0
## Expression changes per avatar: at most 3 per second (light safety, D-14).
const MIN_CHANGE_TICKS := 20


static func glyph_display(body: Dictionary) -> String:
	if HUMANOID_KINDS.has(String(body["kind"])) and Bodies.supports_channel(body, "FACE"):
		return "VISOR"
	if QUADRUPED_KINDS.has(String(body["kind"])) and Bodies.supports_channel(body, "LIGHT"):
		return "LIGHT_STRIP"
	return ""


static func light_display(body: Dictionary) -> String:
	if not Bodies.supports_channel(body, "LIGHT"):
		return ""
	if HUMANOID_KINDS.has(String(body["kind"])):
		return "EAR_PODS"
	if QUADRUPED_KINDS.has(String(body["kind"])):
		return "LIGHT_STRIP"
	return ""


## Why `body` cannot show `expression` (a catalog entry), or "" if it can.
static func refusal(body: Dictionary, expression: Dictionary) -> String:
	if expression.has("gesture") and not Bodies.supports_gesture(body, String(expression["gesture"])):
		return "the body cannot perform the gesture %s" % expression["gesture"]
	if expression.has("glyph"):
		var display := glyph_display(body)
		if display == "":
			return "the body has no glyph display"
		if display == "VISOR" and not expression["glyph"].has("visor"):
			return "the glyph has no visor form"
		if display == "LIGHT_STRIP" and not expression["glyph"].has("strip"):
			return "the glyph has no light-strip form"
	if String(expression["light"]) != "OFF" and light_display(body) == "":
		return "the body has no Beacon light"
	return ""


## The glyph text this body shows for an expression ("" if none).
static func glyph_text(body: Dictionary, expression: Dictionary) -> String:
	if not expression.has("glyph"):
		return ""
	return String(expression["glyph"].get("visor" if glyph_display(body) == "VISOR" else "strip", ""))
