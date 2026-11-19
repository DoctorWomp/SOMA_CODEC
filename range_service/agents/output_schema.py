"""The JSON schema that constrains a model's answer (D-21, D-50; INFERENCE_STRATEGY T9).

Built from contracts/action_request for the agent's allowed actions: ``{"actions": [1-3 x one
of the allowed actions with its own args], "reason_summary"}``, plus the optional promise fields
on SPEAK, GESTURE and EXPRESS. References into other contract files are inlined, and only
keywords llama.cpp's schema-to-grammar converter understands are kept, so the server can turn
it into a grammar. The schema only guides generation: every answer is still checked against
the contracts afterwards (gateway.parse_output), which stay the authority.

G3c-2 (D-60), from the owner's NPC bake-off:

- **No ``oneOf`` beside properties.** llama.cpp b12443's converter (common/json-schema.cpp)
  reads ``oneOf``/``anyOf`` first and ignores ``properties`` and ``additionalProperties`` next to
  them, so MOVE_TO's and LOOK_AT's arguments were not constrained at all (answers such as
  ``"destination": "platform"``). Such nodes are rewritten as full alternatives
  (``_flatten_alternatives``); a test checks that no node mixes them again.
- **Context-aware choices:** ids of people (``target_id``, ``addressee_id``, ``to_id``) are limited to
  the tracks the agent perceives now, so a model cannot invent one; channels to those it may use
  (LOCAL, plus PA for a PA operator; GROUP only in a group).
- **Shorter text for NPC tiers**, so a full answer fits the output cap (cut-off answers were most
  of the NPC failures): see ``TIER_LIMITS``.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from range_service import contracts

from .activity import answer_schema_part as activity_part
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


TARGET_KEYS = ("target_id", "addressee_id", "to_id")
# Per tier: (max actions, reason_summary characters, SPEAK/clarification text characters).
TIER_LIMITS: dict[str, tuple[int, int, int]] = {"FOCAL": (MAX_ACTIONS, 300, 500), "C2": (MAX_ACTIONS, 120, 200),
                                                "C1": (2, 80, 160),
                                                # G3f (D-77): Robot R's SHORT answer condition. reason_summary is
                                                # logged only (never fed back, CONTEXT_MEMORY_STRATEGY §6).
                                                "FOCAL_SHORT": (MAX_ACTIONS, 60, 200)}
# How long a promise's own text may be, per limits key (FULL keeps the contract's 200).
COMMITMENT_MAX = {"FOCAL_SHORT": 80}
LIMIT_KEYS = tuple(TIER_LIMITS)
ALL_CHANNELS = ("LOCAL", "GROUP", "PA")
_ONLY_STRUCTURE = {"required"}


def _flatten_alternatives(node: Any) -> Any:
    """Rewrite ``{properties..., oneOf/anyOf: [...]}`` as ``{anyOf: [full object, ...]}``, the only
    shape llama.cpp turns into a grammar without dropping the properties."""
    if isinstance(node, list):
        return [_flatten_alternatives(n) for n in node]
    if not isinstance(node, dict):
        return node
    node = {k: _flatten_alternatives(v) for k, v in node.items()}
    key = "oneOf" if "oneOf" in node else ("anyOf" if "anyOf" in node else None)
    if key is None or set(node) == {key}:
        return node
    base = {k: v for k, v in node.items() if k != key}
    alts = node[key]
    out = []
    if all(isinstance(a, dict) and set(a) <= _ONLY_STRUCTURE for a in alts):
        # Mutually exclusive "one of these fields" (oneOf of required): each alternative keeps
        # only its own field among the ones the alternatives name.
        named = {f for a in alts for f in a.get("required", [])}
        for a in alts:
            mine = set(a.get("required", []))
            props = {k: v for k, v in base.get("properties", {}).items() if k not in named - mine}
            out.append(dict(base, properties=props, required=sorted(set(base.get("required", [])) | mine)))
    else:
        for a in alts:
            merged = dict(base)
            for k, v in a.items():
                if k == "properties":
                    merged["properties"] = dict(base.get("properties", {}), **v)
                elif k == "required":
                    merged["required"] = sorted(set(base.get("required", [])) | set(v))
                else:
                    merged[k] = v
            out.append(merged)
    return {"anyOf": out}


def _target_schema(old: dict[str, Any], targets: tuple[str, ...]) -> dict[str, Any] | None:
    """A person-id property limited to ``targets``; None when there is nobody to name and the
    property cannot be null."""
    nullable = any(isinstance(a, dict) and a.get("type") == "null" for a in old.get("oneOf", old.get("anyOf", [])))
    if targets:
        return {"anyOf": [{"enum": list(targets)}, {"type": "null"}]} if nullable else {"enum": list(targets)}
    return {"type": "null"} if nullable else None


def _restrict(node: Any, targets: tuple[str, ...], channels: tuple[str, ...], text_max: int) -> Any:
    """Limit person ids, channels and text length inside one action's args. Returns None for an
    alternative that cannot be used here (it needs a person or a channel that is not available)."""
    if isinstance(node, list):
        return [r for r in (_restrict(n, targets, channels, text_max) for n in node) if r is not None]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node and set(node) == {"anyOf"}:
        alts = _restrict(node["anyOf"], targets, channels, text_max)
        return {"anyOf": alts} if alts else None
    out = dict(node)
    if "properties" in node:
        props = {}
        for name, sub in node["properties"].items():
            if name in TARGET_KEYS:
                new = _target_schema(sub, targets)
                if new is None:
                    if name in node.get("required", []):
                        return None
                    continue
                props[name] = new
            elif name == "channel":
                allowed = [c for c in (sub.get("enum") or [sub.get("const")]) if c in channels]
                if not allowed:
                    return None
                props[name] = {"enum": allowed} if len(allowed) > 1 else {"const": allowed[0]}
            elif name == "text" and isinstance(sub, dict) and sub.get("type") == "string":
                props[name] = dict(sub, maxLength=min(sub.get("maxLength", text_max), text_max))
            else:
                props[name] = _restrict(sub, targets, channels, text_max)
        out["properties"] = props
    return out


def _limit_enums(node: Any, limits: dict[str, tuple[str, ...]]) -> Any:
    """Narrow enum properties (gesture, expression_id) to what this body can show."""
    if isinstance(node, list):
        return [_limit_enums(n, limits) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: _limit_enums(v, limits) for k, v in node.items()}
    for name, allowed in limits.items():
        sub = out.get("properties", {}).get(name)
        if isinstance(sub, dict) and allowed:
            keep = [v for v in sub["enum"] if v in allowed] if "enum" in sub else list(allowed)
            out["properties"][name] = {"enum": keep or list(allowed)}
    return out


@lru_cache(maxsize=256)
def answer_schema(allowed_actions: tuple[str, ...], targets: tuple[str, ...] | None = None,
                  channels: tuple[str, ...] = ALL_CHANNELS, tier: str = "FOCAL",
                  gestures: tuple[str, ...] | None = None, expressions: tuple[str, ...] | None = None,
                  activity_max_review_s: int = 0) -> dict[str, Any]:
    """The constrained answer for these actions. ``targets`` (G3c-2): the person ids the agent may
    name now (None = any id, as before); ``channels``: the speech channels it may use; ``tier``
    sets the length limits (TIER_LIMITS; ``FOCAL_SHORT`` is Robot R's SHORT condition, G3f)."""
    max_actions, reason_max, text_max = TIER_LIMITS.get(tier, TIER_LIMITS["FOCAL"])
    schemas = {"action_request": contracts.load_schema("action_request")}
    args_for = _args_refs()
    choices = []
    for action in allowed_actions:
        args = _flatten_alternatives(_resolve(args_for.get(action, {"type": "object"}), schemas, "action_request"))
        if action == "NO_OP" and not args.get("properties"):
            args = {"type": "object", "properties": {}, "additionalProperties": False}
        if targets is not None or channels != ALL_CHANNELS or text_max < 500:
            args = _restrict(args, targets if targets is not None else (), channels, text_max) \
                if targets is not None else _restrict_text_and_channels(args, channels, text_max)
            if args is None:
                continue          # e.g. TURN_TO with nobody perceived: not offered this time
        if action == "GESTURE" and gestures is not None and not gestures:
            continue              # a body with no gestures is not offered GESTURE
        if action == "EXPRESS" and expressions is not None and not expressions:
            continue
        limits = {k: v for k, v in (("gesture", gestures), ("expression_id", expressions)) if v is not None}
        if limits:
            args = _limit_enums(args, limits)
        props: dict[str, Any] = {"action": {"const": action}, "args": args}
        if action in PROMISE_ACTIONS:
            props["commitment"] = {"type": "string", "minLength": 1, "maxLength": COMMITMENT_MAX.get(tier, 200)}
            props["fulfills_commitment"] = {"type": "boolean"}
        choices.append({"type": "object", "properties": props, "required": ["action", "args"],
                        "additionalProperties": False})
    return {
        "type": "object",
        "properties": {
            "actions": {"type": "array", "minItems": 1, "maxItems": max_actions, "items": {"anyOf": choices}},
            "reason_summary": {"type": "string", "maxLength": reason_max},
            **({"activity": activity_part(targets, activity_max_review_s)} if activity_max_review_s else {}),
        },
        "required": ["actions"],
        "additionalProperties": False,
    }


def _restrict_text_and_channels(node: Any, channels: tuple[str, ...], text_max: int) -> Any:
    """``_restrict`` without touching person ids (when the caller gave no target list)."""
    if isinstance(node, list):
        return [r for r in (_restrict_text_and_channels(n, channels, text_max) for n in node) if r is not None]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node and set(node) == {"anyOf"}:
        alts = _restrict_text_and_channels(node["anyOf"], channels, text_max)
        return {"anyOf": alts} if alts else None
    out = dict(node)
    if "properties" in node:
        props = {}
        for name, sub in node["properties"].items():
            if name == "channel":
                allowed = [c for c in (sub.get("enum") or [sub.get("const")]) if c in channels]
                if not allowed:
                    return None
                props[name] = {"enum": allowed} if len(allowed) > 1 else {"const": allowed[0]}
            elif name == "text" and isinstance(sub, dict) and sub.get("type") == "string":
                props[name] = dict(sub, maxLength=min(sub.get("maxLength", text_max), text_max))
            else:
                props[name] = _restrict_text_and_channels(sub, channels, text_max)
        out["properties"] = props
    return out


def mixes_alternatives(node: Any, path: str = "$") -> list[str]:
    """Paths of nodes llama.cpp would mis-read: oneOf/anyOf next to other keywords (G3c-2)."""
    found = []
    if isinstance(node, dict):
        for key in ("oneOf", "anyOf"):
            if key in node and set(node) != {key}:
                found.append(f"{path} ({key} beside {sorted(set(node) - {key})})")
        for k, v in node.items():
            found += mixes_alternatives(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += mixes_alternatives(v, f"{path}[{i}]")
    return found
