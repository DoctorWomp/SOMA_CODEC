class_name UiStyle
extends RefCounted
## Shared look of the operator UI (HUD, layer viewer, evaluator panel; ART_DIRECTION §8).
## FONT_BUMP is added to every UI font size in one place: the owner found the text too small at
## 1920x1080 (2026-11-24) and asked for everything two points larger. Change it here only.

const FONT_BUMP := 2


static func fs(size: int) -> int:
	return size + FONT_BUMP
