"""Expressions a body can show (configs/expressions/*.yaml; EXPRESSION_PRINCIPLES §1, D-14, D-52).

An expression combines an optional gesture, an optional glyph and a light state. Where each part
is shown depends on the body (D-36 as amended at G3a):

- legged and wheeled humanoids: glyph on the visor (needs the FACE channel), light on the ear
  pods (needs LIGHT);
- quadrupeds: a simple symbol on a narrow light strip above the camera cluster, never over the
  lenses, plus light (both need LIGHT);
- people and anything else: no Beacon display, so no glyph and no light.

A body may show an expression only if it can show **every** part; otherwise the host refuses it
(CAPABILITY_DENIED) and nothing is shown. Godot mirrors these rules in
godot_app/scripts/core/beacon.gd; tests on both sides pin the same answers.
"""

from __future__ import annotations

from typing import Any

from . import bodies as body_rules

HUMANOID_KINDS = frozenset({"LEGGED_HUMANOID", "WHEELED_HUMANOID"})
QUADRUPED_KINDS = frozenset({"QUADRUPED"})


def glyph_display(body: dict[str, Any]) -> str | None:
    """Where this body shows glyphs: VISOR, LIGHT_STRIP or None."""
    if body["kind"] in HUMANOID_KINDS and body_rules.supports_channel(body, "FACE"):
        return "VISOR"
    if body["kind"] in QUADRUPED_KINDS and body_rules.supports_channel(body, "LIGHT"):
        return "LIGHT_STRIP"
    return None


def light_display(body: dict[str, Any]) -> str | None:
    """Where this body shows its Beacon light: EAR_PODS, LIGHT_STRIP or None."""
    if not body_rules.supports_channel(body, "LIGHT"):
        return None
    if body["kind"] in HUMANOID_KINDS:
        return "EAR_PODS"
    if body["kind"] in QUADRUPED_KINDS:
        return "LIGHT_STRIP"
    return None


def refusal(body: dict[str, Any], expression: dict[str, Any]) -> str | None:
    """Why this body cannot show the expression, or None if it can."""
    gesture = expression.get("gesture")
    if gesture is not None and not body_rules.supports_gesture(body, gesture):
        return f"the body cannot perform the gesture {gesture}"
    glyph = expression.get("glyph")
    if glyph is not None:
        display = glyph_display(body)
        if display is None:
            return "the body has no glyph display"
        if display == "VISOR" and "visor" not in glyph:
            return "the glyph has no visor form"
        if display == "LIGHT_STRIP" and "strip" not in glyph:
            return "the glyph has no light-strip form"
    if expression["light"] != "OFF" and light_display(body) is None:
        return "the body has no Beacon light"
    return None


def can_show(body: dict[str, Any], expression: dict[str, Any]) -> bool:
    return refusal(body, expression) is None


def available(body: dict[str, Any], catalog: dict[str, dict[str, Any]], include_ambient: bool = False) -> list[str]:
    """Expression ids this body can show, sorted. Ambient state displays (G3e, D-73) are left out
    unless asked for: the runtime shows them from the agent's own state; models never choose them."""
    return sorted(eid for eid, e in catalog.items() if can_show(body, e) and (include_ambient or "ambient" not in e))


def ambient_for(body: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Ambient state -> the expression id this body shows for it (G3e, D-73); {} without a Beacon."""
    return {e["ambient"]["state"]: eid for eid, e in sorted(catalog.items()) if "ambient" in e and can_show(body, e)}


def catalog_problems(catalog: dict[str, dict[str, Any]], all_bodies: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Rules the JSON Schema cannot express, per expression id."""
    found: dict[str, list[str]] = {}
    texts: dict[str, tuple[str, dict[str, Any]]] = {}
    for eid in sorted(catalog):
        e = catalog[eid]
        problems: list[str] = []
        glyph = e.get("glyph")
        if glyph is not None:
            first = texts.setdefault(glyph["glyph_id"], (eid, glyph))
            if first[1] != glyph:
                problems.append(f"glyph {glyph['glyph_id']!r} has different texts than in {first[0]!r}; "
                                "one glyph id must look the same everywhere")
        if e["light"] not in ("OFF", "NEUTRAL") and e.get("gesture") is None and glyph is None:
            problems.append(f"light {e['light']} needs a gesture or a glyph with it: a Beacon light is never "
                            "shown on its own (D-14)")
        if all_bodies and not any(can_show(b, e) for b in all_bodies.values()):
            problems.append("no body in configs/bodies/ can show this expression")
        problems += _ambient_problems(eid, e, catalog)
        if problems:
            found[eid] = problems
    return found


def _ambient_problems(eid: str, e: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> list[str]:
    """G3e (D-73): an ambient display shows a status with no gesture (it may last minutes), has a
    frame loop for every glyph form it has, and each state has one entry. Frame rate <= 3 Hz is in
    the contract (D-14)."""
    amb = e.get("ambient")
    if amb is None:
        return []
    found = []
    if "gesture" in e:
        found.append("an ambient display has no gesture: it is a status shown for as long as the state lasts")
    glyph = e.get("glyph") or {}
    for form, key in (("visor", "visor_frames"), ("strip", "strip_frames")):
        if form in glyph and key not in amb:
            found.append(f"ambient.{key} is missing for the glyph's {form} form")
        if form not in glyph and key in amb:
            found.append(f"ambient.{key} given but the glyph has no {form} form")
    same = sorted(other for other, o in catalog.items() if other != eid and o.get("ambient", {}).get("state") == amb["state"])
    if same:
        found.append(f"ambient state {amb['state']} is also shown by {', '.join(same)}: one entry per state")
    return found
