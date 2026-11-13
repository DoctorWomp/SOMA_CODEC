"""No route for private goals or scenario labels into anything an agent sees (Assessment P0-01, D-13).

Every evaluator-only field name is inserted at every object level of every valid
agent-facing example (and of envelopes carrying agent-facing payloads). Each
insertion must be rejected.
"""

from __future__ import annotations

import copy
import json

import pytest

from range_service import contracts
from range_service.testworld import Avatar, TestWorld, Vec2

from .helpers import example_files, get_at, load_json, object_paths

AGENT_FACING = [n for n in contracts.schema_names() if contracts.audience(n) == "agent"]
ENVELOPE_AGENT_TYPES = {
    "world.observation", "horizon.delta_feature", "horizon.hypothesis",
    "agent.action_request", "world.action_result",
}


def _cases():
    cases = []
    for name in AGENT_FACING:
        for path in example_files(name, "valid"):
            cases.append((name, path))
    for path in example_files("envelope", "valid"):
        if load_json(path)["type"] in ENVELOPE_AGENT_TYPES:
            cases.append(("envelope", path))
    return cases


CASES = _cases()


@pytest.mark.parametrize("case", CASES, ids=[f"{n}/{p.stem}" for n, p in CASES])
def test_evaluator_only_field_rejected_at_every_level(case):
    name, path = case
    original = load_json(path)
    assert contracts.is_valid(name, original)
    accepted = []
    for obj_path in object_paths(original):
        for field in contracts.evaluator_only_fields():
            mutated = copy.deepcopy(original)
            target = get_at(mutated, obj_path)
            if field in target:
                continue
            target[field] = "leak"
            if contracts.is_valid(name, mutated):
                accepted.append(f"{'/'.join(map(str, obj_path)) or '<root>'}.{field}")
    assert not accepted, f"{name}/{path.name} accepted evaluator-only fields: {accepted}"


def _discriminated_values(schema, prop):
    """Values of ``prop`` that some allOf if-branch handles."""
    handled = set()
    for rule in schema.get("allOf", []):
        cond = rule.get("if", {}).get("properties", {}).get(prop, {})
        if "const" in cond:
            handled.add(cond["const"])
        handled.update(cond.get("enum", []))
    return handled


@pytest.mark.parametrize(
    "name,pointer,prop,enum_source",
    [
        ("observation", ("$defs", "observation_item"), "kind", ("$defs", "observation_item", "properties", "kind")),
        ("action_request", (), "action", None),
        ("envelope", (), "type", ("properties", "type")),
        ("journal_entry", (), "kind", ("properties", "kind")),
    ],
)
def test_per_kind_objects_cover_every_kind(name, pointer, prop, enum_source):
    """Fields marked x-closed-by are only closed if every kind/action/type has a closed rule."""
    schema = contracts.load_schema(name)
    node = get_at(schema, pointer)
    if enum_source is None:
        values = set(contracts.load_schema("common")["$defs"]["action_name"]["enum"])
    else:
        values = set(get_at(schema, enum_source)["enum"])
    assert values <= _discriminated_values(node, prop)


def test_testworld_observation_never_contains_private_goal_or_true_identity():
    world = TestWorld(seed=7)
    world.add_avatar(Avatar("robot_r", Vec2(0, 0), yaw_rad=0.0, fov_deg=120))
    world.add_avatar(Avatar("visitor_y", Vec2(0, -5), private_goal="SECRET_wants_cafe"))
    packet = world.observe("robot_r")
    text = json.dumps(packet)
    assert len(packet["observations"]) == 1
    assert "SECRET_wants_cafe" not in text
    assert "visitor_y" not in text  # true entity ID is never exposed; only an anonymous track
    assert packet["observations"][0]["source_entity_id"] is None
    contracts.validate("observation", packet)


def test_track_ids_are_scoped_per_observer():
    world = TestWorld(seed=7)
    for avatar_id, x in (("a", 0.0), ("b", 2.0), ("c", 4.0)):
        world.add_avatar(Avatar(avatar_id, Vec2(x, 0), fov_deg=360))
    assert world.track_id("a", "c") != world.track_id("b", "c")
    assert world.track_id("a", "c") == world.track_id("a", "c")
