"""Build one runtime per cast member from a scenario (G3a, D-48, D-49).

This is where evaluator-only data is left behind: a runtime gets the public part of its
persona, its body, its directive, the expressions its body can show, public map facts and its
task. Never the scenario's ``evaluator_only`` labels, its ``measure`` list, any persona's style,
or another agent's anything.

G3c-1 (D-51, D-59): when a run has an NPC model, every non-focal cast member is model-driven at
C1/C2 and gets the NPC gateway; its **own** private goal goes into its own identity, labelled,
and nowhere else. Robot R (focal) only ever gets the focal gateway and never a private goal.
"""

from __future__ import annotations

from typing import Any

from range_service import expressions as expression_rules
from range_service.configs import ConfigSet

from .gateway import ModelGateway
from .runtime import AgentRuntime
from .tokenizer import Tokenizer

PUBLIC_PERSONA_FIELDS = ("persona_id", "display_name", "role", "public_goal", "knows", "does_not_know",
                         "cognition_level", "allowed_actions", "default_body")


def public_persona(persona: dict[str, Any]) -> dict[str, Any]:
    """The persona without its private goal and style (D-13; evaluator / own-agent only)."""
    return {k: persona[k] for k in PUBLIC_PERSONA_FIELDS if k in persona}


def directive_for(entry: dict[str, Any], persona: dict[str, Any], directives: dict[str, Any]) -> str:
    if "directive" in entry:
        return directives[entry["directive"]]["directive"]
    for d in sorted(directives.values(), key=lambda d: d["directive_id"]):
        if persona["role"] in d.get("default_for_roles", []):
            return d["directive"]
    return persona["public_goal"]


def setting_lines(game_map: dict[str, Any]) -> list[str]:
    """Public facts about the map, for section 4 (anything a visitor could read off a floor plan)."""
    b = game_map["bounds"]
    lines = [f"Venue: {game_map['map_id']} ({b['width_m']} x {b['depth_m']} m). Positions are (x, z) in meters."]
    for zone in game_map["zones"]:
        a = zone["area"]
        lines.append(f"Zone {zone['zone_id']}: x {a['x_min']}-{a['x_max']}, z {a['z_min']}-{a['z_max']}.")
    for link in game_map.get("nav_links", []):
        lines.append(f"{link['kind'].title()} {link['link_id']}: from ({link['from']['x']}, {link['from']['z']}) "
                     f"to ({link['to']['x']}, {link['to']['z']}).")
    return lines


def task_goal_point(entry: dict[str, Any], game_map: dict[str, Any]) -> dict[str, float] | None:
    goal = entry.get("task_goal")
    if goal is None:
        return None
    if "point" in goal:
        return {"x": float(goal["point"]["x"]), "z": float(goal["point"]["z"])}
    zone = next(z for z in game_map["zones"] if z["zone_id"] == goal["zone"])
    a = zone["area"]
    return {"x": round((a["x_min"] + a["x_max"]) / 2, 2), "z": round((a["z_min"] + a["z_max"]) / 2, 2)}


def build_runtimes(scenario: dict[str, Any], cs: ConfigSet, *, gateway: ModelGateway | None = None,
                   body_overrides: dict[str, str] | None = None, tokenizer: Tokenizer | None = None,
                   npc_gateway: ModelGateway | None = None, npc_tokenizer: Tokenizer | None = None,
                   prewarm: bool = True) -> dict[str, AgentRuntime]:
    overrides = body_overrides or {}
    game_map = cs.items["maps"][scenario["map"]]
    catalog = cs.items["expressions"]
    setting = setting_lines(game_map)
    out: dict[str, AgentRuntime] = {}
    for avatar_id in sorted(scenario["cast"]):
        entry = scenario["cast"][avatar_id]
        full_persona = cs.items["personas"][entry["persona"]]
        persona = public_persona(full_persona)
        body = cs.items["bodies"][overrides.get(avatar_id, entry["body"])]
        focal = entry["persona"] == "robot_r" or entry["controller"] == "LLM_AGENT"
        if focal:
            agent_gateway = gateway if entry["controller"] == "LLM_AGENT" else None
            agent_tokenizer = tokenizer if agent_gateway is not None else None
            own_goal = None
        else:
            agent_gateway, agent_tokenizer = npc_gateway, npc_tokenizer if npc_gateway is not None else None
            own_goal = full_persona.get("private_goal") if npc_gateway is not None else None
        out[avatar_id] = AgentRuntime(
            avatar_id, persona=persona, body=body, directive=directive_for(entry, persona, cs.items["directives"]),
            expressions=expression_rules.available(body, catalog), setting=setting, task=entry.get("task"),
            task_goal=task_goal_point(entry, game_map), focal=focal, pin=bool(entry.get("pin_cognition")),
            controller=entry["controller"], gateway=agent_gateway, tokenizer=agent_tokenizer,
            expression_gestures={eid: e["gesture"] for eid, e in catalog.items() if "gesture" in e},
            own_private_goal=own_goal, prewarm=prewarm)
    return out
