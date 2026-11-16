"""The JSON schema that constrains a model's answer (D-21, D-50; INFERENCE_STRATEGY T9).

Built from contracts/action_request for the agent's allowed actions: ``{"actions": [1-3 x one
of the allowed actions with its own args], "reason_summary"}``, plus the optional promise fields
on SPEAK, GESTURE and EXPRESS. References into other contract files are inlined, and only
keywords llama.cpp's schema-to-grammar converter understands are kept, so the server can turn
it into a grammar. The schema only guides generation: every answer is still checked against
the contracts afterwards (gateway.parse_output), which stay the authority.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from range_service import contracts

from .gateway import MAX_ACTIONS, PROMISE_ACTIONS

KEEP = {"type", "properties", "required", "additionalProperties", "items", "minItems", "maxItems", "enum",
        "const", "anyOf", "oneOf", "minLength", "maxLength", "pattern", "minimum", "maximum"}


def _resolve(node: Any, schemas: dict[str, dict[str, Any]], current: str, depth: int = 0) -> Any:
    """Inline every $ref (local or into another contract) and drop unsupported keywords."""
    if depth > 30:
        raise ValueError("schema references nest too deeply")
    if isinstance(node, list):
        return [_resolve(n, schemas, current, depth + 1) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = node["$ref"]
        file_part, _, pointer = ref.partition("#")
        target_name = file_part.removesuffix(".schema.json") if file_part else current
        if target_name not in schemas:
            schemas[target_name] = contracts.load_schema(target_name)
        target: Any = schemas[target_name]
        for part in pointer.strip("/").split("/") if pointer.strip("/") else []:
            target = target[part]
        merged = dict(target)
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return _resolve(merged, schemas, target_name, depth + 1)
    if "if" in node and "properties" in node:
        split = _split_conditional(node)
        if split is not None:
            return {"anyOf": [_resolve(v, schemas, current, depth + 1) for v in split]}
    out = {}
    for key, value in node.items():
        if key not in KEEP:
            continue
        if key == "properties":
            out[key] = {name: _resolve(sub, schemas, current, depth + 1) for name, sub in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            out[key] = _resolve(value, schemas, current, depth + 1)
        elif key in ("anyOf", "oneOf"):
            out[key] = [_resolve(v, schemas, current, depth + 1) for v in value]
        else:
            out[key] = copy.deepcopy(value)
    return out


def _split_conditional(node: dict[str, Any]) -> list[dict[str, Any]] | None:
    """``{if: {properties: {X: {const: V}}}, then: {required: [...]}, else: {not: {required: [...]}}}``
    as two plain alternatives the grammar converter understands: X is V and the fields are
    required, or X is anything else and the fields are absent. Other shapes: None (dropped)."""
    cond = node["if"].get("properties", {})
    if len(cond) != 1:
        return None
    (field_name, test), = cond.items()
    if set(test) != {"const"} or field_name not in node["properties"]:
        return None
    needed = node.get("then", {}).get("required", [])
    banned = node.get("else", {}).get("not", {}).get("required", [])
    if set(node.get("then", {})) - {"required"} or set(node.get("else", {})) - {"not"}:
        return None
    base = {k: v for k, v in node.items() if k not in ("if", "then", "else")}
    yes = dict(base, properties=dict(base["properties"], **{field_name: {"const": test["const"]}}),
               required=sorted(set(base.get("required", [])) | set(needed)))
    others = [v for v in node["properties"][field_name].get("enum", []) if v != test["const"]]
    if not others:
        return [yes]
    no_props = {k: v for k, v in base["properties"].items() if k not in banned}
    no = dict(base, properties=dict(no_props, **{field_name: {"enum": others}}))
    return [yes, no]


def _args_refs() -> dict[str, dict[str, Any]]:
    """action -> its args schema, read from action_request's per-action rules."""
    schema = contracts.load_schema("action_request")
    out: dict[str, dict[str, Any]] = {}
    for rule in schema.get("allOf", []):
        action = rule.get("if", {}).get("properties", {}).get("action", {}).get("const")
        args = rule.get("then", {}).get("properties", {}).get("args")
        if action and args:
            out[action] = args
    return out


@lru_cache(maxsize=64)
def answer_schema(allowed_actions: tuple[str, ...]) -> dict[str, Any]:
    schemas = {"action_request": contracts.load_schema("action_request")}
    args_for = _args_refs()
    choices = []
    for action in allowed_actions:
        args = _resolve(args_for.get(action, {"type": "object"}), schemas, "action_request")
        if action == "NO_OP" and not args.get("properties"):
            args = {"type": "object", "properties": {}, "additionalProperties": False}
        props: dict[str, Any] = {"action": {"const": action}, "args": args}
        if action in PROMISE_ACTIONS:
            props["commitment"] = {"type": "string", "minLength": 1, "maxLength": 200}
            props["fulfills_commitment"] = {"type": "boolean"}
        choices.append({"type": "object", "properties": props, "required": ["action", "args"],
                        "additionalProperties": False})
    return {
        "type": "object",
        "properties": {
            "actions": {"type": "array", "minItems": 1, "maxItems": MAX_ACTIONS, "items": {"anyOf": choices}},
            "reason_summary": {"type": "string", "maxLength": 300},
        },
        "required": ["actions"],
        "additionalProperties": False,
    }
