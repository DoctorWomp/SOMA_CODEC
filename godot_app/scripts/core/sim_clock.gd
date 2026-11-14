class_name SimClock
extends Node
## The world's fixed tick (ART_DIRECTION §4): one tick per physics step, 60 per second.
## It runs before every avatar in each step, so all movement in tick N sees tick == N.
## Pausing the scene tree stops the clock and all movement together.

const TICK_HZ := 60

var tick: int = 0


func _init() -> void:
	name = "SimClock"
	process_physics_priority = -100


func _physics_process(_delta: float) -> void:
	tick += 1


func seconds() -> float:
	return float(tick) / TICK_HZ
