"""Director interventions (G4b, D-97 to D-102): the rules shared by recipes, the sidecar and tests.

Godot's world dispatcher (``godot_app/scripts/comms/world_dispatcher.gd``) checks the seat and carries
out world-side interventions; the sidecar carries out agent-side ones (``DIRECTIVE_EDIT``). Both
apply the same rules, written here once for Python and mirrored in ``director.gd``:

- which operations each intervention type may use, and which capability (configs/permissions.yaml)
  the seat needs for it;
- the prop catalog the World Director may place;
- the arguments each operation needs.
"""

from __future__ import annotations

from typing import Any, Iterable

TYPES = ("DIRECTIVE_EDIT", "WORLD_CHANGE", "EVENT_TRIGGER", "ENVIRONMENTAL_INFLUENCE", "SOCIAL_INFLUENCE")
OPERATIONS = {
    "DIRECTIVE_EDIT": ("EDIT_DIRECTIVE",),
    "WORLD_CHANGE": ("PLACE_PROP", "MOVE_PROP", "REMOVE_PROP"),
    "EVENT_TRIGGER": ("TRIGGER_EVENT",),
    "ENVIRONMENTAL_INFLUENCE": ("PLACE_PROP", "MOVE_PROP", "REMOVE_PROP", "PA_ANNOUNCEMENT"),
    "SOCIAL_INFLUENCE": ("NPC_SAY",),
}
CAPABILITY = {"DIRECTIVE_EDIT": "EDIT_DIRECTIVE", "WORLD_CHANGE": "WORLD_CHANGE", "EVENT_TRIGGER": "TRIGGER_EVENT",
              "ENVIRONMENTAL_INFLUENCE": "INFLUENCE", "SOCIAL_INFLUENCE": "INFLUENCE"}
# Props the Director may place (greybox sizes live in godot_app/scripts/world/map_builder.gd).
# Text props are influence (world content an agent may read); the others change the world.
TEXT_PROPS = ("SIGN", "NOTE")
WORLD_PROPS = ("BARRIER", "CONE", "CRATE", "SOUND_SOURCE")
PROPS = TEXT_PROPS + WORLD_PROPS
SOUND_CLASSES = ("LAUGHTER", "APPLAUSE", "MUSIC", "IMPACT", "MACHINE", "UNKNOWN")
# Events the Director may trigger: the tape's event types (range_service/scenarios.py).
EVENTS = ("say", "pa_announcement", "wave", "small_wave", "gesture", "move_to", "avatar_approaches", "leave",
          "turn_to")
# Agent Director (D-98): what may be edited, and what is shown but never editable (Blueprint §10.2).
EDITABLE_FIELDS = ("directive", "goal", "slider")
LOCKED = ("guardrails", "allowed actions", "permissions", "body and physics", "tools (the action list)",
          "private goal (evaluator only)")
MAX_TEXT = 500                    # sign, note, announcement and NPC line (observation text limit)
MAX_DIRECTIVE = 800            # ~230 estimated tokens: IDENTITY keeps within its FOCAL budget of 300 (D-106)
MAX_GOAL = 300
REASONS = ("PERMISSION_DENIED", "NOT_BUILT", "UNKNOWN_OPERATION", "TYPE_MISMATCH", "UNKNOWN_TARGET", "NOT_EDITABLE",
           "INVALID_VALUE", "OFF_MAP", "INSIDE_WALL", "ON_AVATAR", "BLOCKS_ROUTE", "UNKNOWN_PROP", "NOT_FOUND",
           "EVENT_REFUSED", "NO_AGENT_LINK")


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def request_problems(itype: str | None, operation: str, target_id: str | None, args: dict[str, Any],
                     cast: Iterable[str] = (), sliders: Iterable[str] = ()) -> list[tuple[str, str]]:
    """(reason, words) for each problem with an intervention's shape, before any world check.
    ``cast``: the avatars it may name; ``sliders``: the persona style names."""
    cast = set(cast)
    out: list[tuple[str, str]] = []
    if itype not in OPERATIONS:
        return [("UNKNOWN_OPERATION", f"unknown intervention type {itype!r}")]
    if operation not in OPERATIONS[itype]:
        return [("TYPE_MISMATCH", f"{itype} cannot use {operation} (it may use {', '.join(OPERATIONS[itype])})")]
    if operation == "EDIT_DIRECTIVE":
        if target_id not in cast:
            out.append(("UNKNOWN_TARGET", f"no avatar {target_id!r} to edit"))
        field = args.get("field")
        if field not in EDITABLE_FIELDS:
            out.append(("NOT_EDITABLE", f"{field!r} cannot be edited; editable: {', '.join(EDITABLE_FIELDS)}; "
                                        f"never: {', '.join(LOCKED)}"))
        elif field == "directive" and not (isinstance(args.get("value"), str) and 0 < len(args["value"]) <= MAX_DIRECTIVE):
            out.append(("INVALID_VALUE", f"a directive is text of 1 to {MAX_DIRECTIVE} characters"))
        elif field == "goal" and not (isinstance(args.get("value"), str) and 0 < len(args["value"]) <= MAX_GOAL):
            out.append(("INVALID_VALUE", f"a goal is text of 1 to {MAX_GOAL} characters"))
        elif field == "slider":
            if sliders and args.get("name") not in set(sliders):
                out.append(("NOT_EDITABLE", f"no persona slider {args.get('name')!r}"))
            if not (_num(args.get("value")) and 0 <= args["value"] <= 100 and float(args["value"]).is_integer()):
                out.append(("INVALID_VALUE", "a persona slider is a whole number 0 to 100"))
    elif operation == "PLACE_PROP":
        prop = args.get("prop_type")
        if prop not in PROPS:
            out.append(("UNKNOWN_PROP", f"unknown prop {prop!r}; known: {', '.join(PROPS)}"))
        elif (prop in TEXT_PROPS) != (itype == "ENVIRONMENTAL_INFLUENCE"):
            out.append(("TYPE_MISMATCH", "a sign or note with text is ENVIRONMENTAL_INFLUENCE; other props WORLD_CHANGE"))
        if not (_num(args.get("x")) and _num(args.get("z"))):
            out.append(("INVALID_VALUE", "a placement needs x and z (meters)"))
        if prop in TEXT_PROPS and not (isinstance(args.get("text"), str) and 0 < len(args["text"]) <= MAX_TEXT):
            out.append(("INVALID_VALUE", f"a {prop.lower()} needs text of 1 to {MAX_TEXT} characters"))
        if prop == "SOUND_SOURCE" and args.get("sound_class", "MUSIC") not in SOUND_CLASSES:
            out.append(("INVALID_VALUE", f"sound_class must be one of {', '.join(SOUND_CLASSES)}"))
    elif operation in ("MOVE_PROP", "REMOVE_PROP"):
        if not target_id:
            out.append(("NOT_FOUND", "name the placed prop (target_id)"))
        if operation == "MOVE_PROP" and not (_num(args.get("x")) and _num(args.get("z"))):
            out.append(("INVALID_VALUE", "a move needs x and z (meters)"))
    elif operation == "TRIGGER_EVENT":
        if args.get("event_type") not in EVENTS:
            out.append(("INVALID_VALUE", f"event_type must be one of {', '.join(EVENTS)}"))
        if target_id not in cast:
            out.append(("UNKNOWN_TARGET", f"no avatar {target_id!r} to act"))
    elif operation == "PA_ANNOUNCEMENT":
        if not (isinstance(args.get("text"), str) and 0 < len(args["text"]) <= MAX_TEXT):
            out.append(("INVALID_VALUE", f"an announcement is text of 1 to {MAX_TEXT} characters"))
    elif operation == "NPC_SAY":
        if target_id not in cast:
            out.append(("UNKNOWN_TARGET", f"no avatar {target_id!r} to speak"))
        if not (isinstance(args.get("text"), str) and 0 < len(args["text"]) <= MAX_TEXT):
            out.append(("INVALID_VALUE", f"a line is text of 1 to {MAX_TEXT} characters"))
    return out


def recipe_problems(recipe: dict[str, Any], scenarios: dict[str, Any], personas: dict[str, Any]) -> list[str]:
    """configs/recipes: each intervention's shape against its scenario (if named)."""
    out = []
    scen = scenarios.get(recipe.get("scenario", "")) if recipe.get("scenario") else None
    if recipe.get("scenario") and scen is None:
        return [f"scenario {recipe['scenario']!r} not found in configs/scenarios/"]
    cast = list(scen["cast"]) if scen else []
    for i, item in enumerate(recipe["interventions"]):
        target = item.get("target_id")
        sliders = []
        if scen and target in scen["cast"]:
            sliders = list((personas.get(scen["cast"][target]["persona"]) or {}).get("style", {}))
        names = cast if scen else ([target] if target else [])
        for _reason, words in request_problems(item["intervention_type"], item["operation"], target, item["args"],
                                               names, sliders):
            out.append(f"interventions[{i}]: {words}")
        if scen and item["at_tick"] >= scen["duration_ticks"]:
            out.append(f"interventions[{i}]: at_tick {item['at_tick']} is after the scenario ends")
    return out
