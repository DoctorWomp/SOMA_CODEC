"""The expression catalog rules (D-52, EXPRESSION_PRINCIPLES §1, D-14) and the scenario tape
rules (D-48). The Godot side mirrors both; Godot tests pin the same answers."""

from __future__ import annotations

import copy

import pytest

from range_service import expressions as rules
from range_service import scenarios
from range_service.configs import _cross_checks

from .agent_helpers import CONFIGS

CATALOG = CONFIGS.items["expressions"]
BODIES = CONFIGS.items["bodies"]


def test_who_can_show_what():
    assert rules.available(BODIES["human_walker"], CATALOG) == []                    # people have no Beacon
    quad = rules.available(BODIES["quadruped"], CATALOG)
    assert "greeting" not in quad and "acknowledge" not in quad and "stop" not in quad      # no arm, no nod
    assert {"greeting_light", "acknowledge_tilt", "listening", "stop_light", "waiting"} <= set(quad)
    assert set(rules.available(BODIES["wheeled_humanoid"], CATALOG)) == set(CATALOG)
    arm = rules.available(BODIES["quadruped_arm"], CATALOG)
    assert {"greeting", "stop"} <= set(arm)        # gripper wave and raised gripper (owner, 2026-11-16)
    assert "acknowledge" not in arm                 # still no nod: no neck on a quadruped


def test_refusal_reasons():
    assert "gesture WAVE" in rules.refusal(BODIES["quadruped"], CATALOG["greeting"])
    assert "no glyph display" in rules.refusal(BODIES["human_walker"], CATALOG["listening"])
    assert rules.refusal(BODIES["quadruped"], CATALOG["listening"]) is None


def test_displays_per_body():
    assert rules.glyph_display(BODIES["legged_humanoid"]) == "VISOR"
    assert rules.light_display(BODIES["legged_humanoid"]) == "EAR_PODS"
    assert rules.glyph_display(BODIES["quadruped"]) == "LIGHT_STRIP" == rules.light_display(BODIES["quadruped"])
    assert rules.glyph_display(BODIES["human_walker"]) is None


def test_catalog_has_no_strobe_and_no_green_light():
    for e in CATALOG.values():
        assert e["light_pattern"] in ("STEADY", "SLOW_PULSE") and e["light"] != "GREEN"


def test_catalog_rules_catch_mismatched_glyphs_and_bare_lights():
    bad = copy.deepcopy(CATALOG)
    bad["listening"]["glyph"]["visor"] = "O_O"                       # same glyph id, different text
    bad["stop_light"].pop("glyph")                                   # a red light with nothing else
    found = rules.catalog_problems(bad, BODIES)
    assert any("different texts" in p for p in found["listening"] + found.get("acknowledge", []))
    assert any("never shown on its own" in p for p in found["stop_light"])
    assert rules.catalog_problems(CATALOG, BODIES) == {}


def test_every_shipped_expression_is_showable_by_some_robot():
    for eid, e in CATALOG.items():
        assert any(rules.can_show(b, e) for b in BODIES.values()), eid


@pytest.mark.parametrize("event,expected", [
    ({"at_tick": 1, "event_type": "teleport", "actor": "visitor_x"}, "not one of"),
    ({"at_tick": 1, "event_type": "say", "actor": "visitor_x"}, "needs args.text"),
    ({"at_tick": 1, "event_type": "say", "actor": "visitor_x", "args": {"text": "hi", "to": "nobody"}}, "not in the cast"),
    ({"at_tick": 1, "event_type": "move_to", "actor": "visitor_x"}, "exactly one destination"),
    ({"at_tick": 1, "event_type": "move_to", "actor": "visitor_x", "where": "spawn_edge", "args": {"x": 1, "z": 2}}, "exactly one destination"),
    ({"at_tick": 1, "event_type": "move_to", "actor": "visitor_x", "args": {"x": 1}}, "both args.x and args.z"),
    ({"at_tick": 1, "event_type": "turn_to", "actor": "visitor_x", "where": "spawn_edge", "args": {"target": "robot_r"}}, "does not take `where`"),
    ({"at_tick": 1, "event_type": "pa_announcement", "actor": "visitor_x", "args": {"text": "Hello"}}, "pa_operators"),
    ({"at_tick": 1, "event_type": "wave"}, "needs an actor"),
])
def test_tape_rules(event, expected):
    scenario = copy.deepcopy(CONFIGS.items["scenarios"]["SB04_POLITE_BID"])
    assert any(expected in p for p in scenarios.event_problems(scenario, 0, event))


def test_shipped_tapes_are_valid_and_timed_in_scenario_ticks():
    for scenario in CONFIGS.items["scenarios"].values():
        for i, e in enumerate(scenario["events"]):
            assert scenarios.event_problems(scenario, i, e) == []
    sb04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
    assert scenarios.world_ticks(sb04, sb04["duration_ticks"]) == 900 * 6


def test_config_cross_checks_catch_scenario_mistakes():
    cs = copy.deepcopy(CONFIGS)
    s = cs.items["scenarios"]["SB04_POLITE_BID"]
    s["pa_operators"] = ["stranger"]
    s["cast"]["robot_r"]["directive"] = "no_such_directive"
    s["cast"]["visitor_x"]["task_goal"] = {"zone": "no_such_zone"}
    found = "\n".join(str(p) for p in _cross_checks(cs))
    assert "pa_operators: 'stranger'" in found and "no_such_directive" in found and "no_such_zone" in found
