"""The contracts themselves are well-formed and follow the shared rules (D-27)."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from range_service import contracts

from .helpers import EXAMPLES, example_files

EXPECTED = {
    # messages
    "envelope", "observation", "delta_feature", "hypothesis", "action_request",
    "action_result", "comms_event", "intervention",
    # records
    "memory_item", "run_manifest", "journal_entry",
    # configs
    "scenario", "persona", "body", "map", "preset",
    # shared definitions
    "common",
}
NAMES = contracts.schema_names()
NON_SHARED = [n for n in NAMES if n != "common"]


def test_every_planned_contract_exists():
    assert set(NAMES) == EXPECTED


@pytest.mark.parametrize("name", NAMES)
def test_schema_is_valid_draft_2020_12(name):
    schema = contracts.load_schema(name)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith(f"/{name}.schema.json")
    assert schema["x-audience"] in contracts.AUDIENCES


@pytest.mark.parametrize("name", NON_SHARED)
def test_every_contract_has_valid_and_invalid_examples(name):
    assert example_files(name, "valid"), f"{name}: no valid examples"
    assert example_files(name, "invalid"), f"{name}: no invalid examples"
    assert (EXAMPLES / name / "invalid" / "_expect.json").is_file()


@pytest.mark.parametrize("name", NON_SHARED)
def test_every_contract_requires_schema_version(name):
    schema = contracts.load_schema(name)
    assert "schema_version" in schema["required"]
    assert schema["properties"]["schema_version"] == {"$ref": "common.schema.json#/$defs/schema_version"}


def _object_nodes(node, path="#"):
    """Yield (path, node) for every subschema that declares ``"type": "object"``."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield path, node
        for key, child in node.items():
            yield from _object_nodes(child, f"{path}/{key}")
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from _object_nodes(child, f"{path}/{i}")


def _declared_property_names(node):
    if isinstance(node, dict):
        for key, child in node.items():
            if key == "properties" and isinstance(child, dict):
                yield from child.keys()
            yield from _declared_property_names(child)
    elif isinstance(node, list):
        for child in node:
            yield from _declared_property_names(child)


@pytest.mark.parametrize("name", [n for n in NAMES if contracts.audience(n) in ("agent", "transport", "shared")])
def test_agent_facing_objects_are_closed(name):
    """Unknown fields are rejected: every object is closed, or closed per type/kind/action (x-closed-by)."""
    open_nodes = [
        path
        for path, node in _object_nodes(contracts.load_schema(name))
        if node.get("additionalProperties") is not False and "x-closed-by" not in node
    ]
    assert not open_nodes, f"{name}: open object schemas at {open_nodes}"


@pytest.mark.parametrize("name", [n for n in NAMES if contracts.audience(n) == "agent"])
def test_agent_facing_contracts_declare_no_evaluator_only_field(name):
    forbidden = set(contracts.evaluator_only_fields())
    declared = set(_declared_property_names(contracts.load_schema(name)))
    assert not (declared & forbidden), f"{name} declares evaluator-only fields {sorted(declared & forbidden)}"


def test_evaluator_only_list_covers_known_leak_routes():
    fields = set(contracts.evaluator_only_fields())
    for required in ("private_goal", "evaluator_only", "delivered_to", "not_delivered_to",
                     "wants_robot_help", "true_identity", "scenario_labels"):
        assert required in fields


def test_shared_enums_match_decisions():
    defs = contracts.load_schema("common")["$defs"]
    assert defs["validity"]["enum"] == ["OBSERVED", "DEGRADED", "OCCLUDED", "MISSING", "EXPIRED", "UNKNOWN_SOURCE"]
    assert defs["read_label"]["enum"] == ["COMMIT", "LEAN", "HELD_OPEN", "UNKNOWN"]  # D-10
    assert defs["scope"]["enum"] == ["PUBLIC", "GROUP", "ONE_TO_ONE", "SEALED"]  # D-12
    assert defs["channel"]["enum"] == ["GESTURE", "LOCAL", "GROUP", "PA"]  # D-07
    assert defs["tick"] == {"description": defs["tick"]["description"], "type": "integer", "minimum": 0}


def test_no_schema_reaches_the_network():
    """Every $ref points at a local contract file (or inside the same file)."""
    local_files = {f"{n}.schema.json" for n in NAMES}

    def refs(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "$ref":
                    yield child
                else:
                    yield from refs(child)
        elif isinstance(node, list):
            for child in node:
                yield from refs(child)

    for name in NAMES:
        for ref in refs(contracts.load_schema(name)):
            target = ref.split("#", 1)[0]
            assert target == "" or target in local_files, f"{name}: non-local $ref {ref!r}"
