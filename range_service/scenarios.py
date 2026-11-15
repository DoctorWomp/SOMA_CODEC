"""The scenario event tape (configs/scenarios/*.yaml ``events``; G3a, D-48).

Events are played by the host (Godot) at exact ticks, through the action gate, with the
actor's own body limits. ``at_tick`` and ``duration_ticks`` count scenario ticks at the
scenario's ``tick_hz``; the world converts them to its 60 Hz tick (D-33).

This module is the single Python statement of which event types exist and what each needs.
Godot mirrors it in godot_app/scripts/scenario/scenario_player.gd.
"""

from __future__ import annotations

from typing import Any

WORLD_TICK_HZ = 60

# event type -> (required args, optional args, how the destination may be given)
#   destination: "where_or_point" means `where` (a spawn point or zone) or args x and z.
EVENT_TYPES: dict[str, dict[str, Any]] = {
    "move_to": {"args": set(), "optional": {"x", "z"}, "destination": True},
    "avatar_approaches": {"args": set(), "optional": {"x", "z"}, "destination": True},
    "leave": {"args": set(), "optional": {"x", "z"}, "destination": True},
    "turn_to": {"args": {"target"}, "optional": set(), "destination": False},
    "gesture": {"args": {"gesture"}, "optional": {"target"}, "destination": False},
    "wave": {"args": set(), "optional": {"target"}, "destination": False},
    "small_wave": {"args": set(), "optional": {"target"}, "destination": False},
    "say": {"args": {"text"}, "optional": {"to"}, "destination": False},
    "pa_announcement": {"args": {"text"}, "optional": set(), "destination": False},
}


def world_ticks(scenario: dict[str, Any], scenario_ticks: int) -> int:
    """Scenario ticks (at tick_hz) to world ticks (60 Hz)."""
    return scenario_ticks * (WORLD_TICK_HZ // scenario["tick_hz"])


def event_problems(scenario: dict[str, Any], index: int, event: dict[str, Any]) -> list[str]:
    """What is wrong with one tape event, beyond the JSON Schema."""
    where = f"events[{index}]"
    spec = EVENT_TYPES.get(event["event_type"])
    if spec is None:
        return [f"{where}.event_type {event['event_type']!r} is not one of {', '.join(sorted(EVENT_TYPES))}"]
    found: list[str] = []
    if "actor" not in event:
        found.append(f"{where}: {event['event_type']} needs an actor")
    args = event.get("args", {})
    for name in sorted(spec["args"] - set(args)):
        found.append(f"{where}: {event['event_type']} needs args.{name}")
    for name in sorted(set(args) - spec["args"] - spec["optional"]):
        found.append(f"{where}: {event['event_type']} does not take args.{name}")
    if spec["destination"]:
        has_point = "x" in args and "z" in args
        if ("x" in args) != ("z" in args):
            found.append(f"{where}: give both args.x and args.z, or neither")
        if has_point == ("where" in event):
            found.append(f"{where}: {event['event_type']} needs exactly one destination: `where` or args x and z")
    elif "where" in event:
        found.append(f"{where}: {event['event_type']} does not take `where`")
    for key in ("target", "to"):
        if key in args and args[key] not in scenario["cast"]:
            found.append(f"{where}: args.{key} {args[key]!r} is not in the cast")
    if event["event_type"] == "pa_announcement" and "actor" in event \
            and event["actor"] not in scenario.get("pa_operators", []):
        found.append(f"{where}: {event.get('actor')!r} is not listed in pa_operators")
    return found
