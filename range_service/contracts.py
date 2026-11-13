"""Load the JSON Schema contracts in ``contracts/`` and validate data against them.

The schemas are the single source of truth (D-27). Cross-file ``$ref`` links are
resolved from the local files only; nothing is ever fetched from the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"
SCHEMA_SUFFIX = ".schema.json"

# Who each contract is for. "agent" contracts may reach an agent's context and
# must never carry evaluator-only fields.
AUDIENCES = ("agent", "evaluator", "config", "transport", "shared")


@dataclass(frozen=True)
class Problem:
    """One validation failure, in words a person can act on."""

    path: str
    message: str
    keyword: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def schema_names() -> list[str]:
    """Names of all contracts, e.g. ``["action_request", "body", ...]``."""
    return sorted(p.name[: -len(SCHEMA_SUFFIX)] for p in CONTRACTS_DIR.glob(f"*{SCHEMA_SUFFIX}"))


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    path = CONTRACTS_DIR / f"{name}{SCHEMA_SUFFIX}"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for name in schema_names():
        schema = load_schema(name)
        resources.append((schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), registry=_registry())


def audience(name: str) -> str:
    return load_schema(name)["x-audience"]


def evaluator_only_fields() -> list[str]:
    """The shared list of evaluator-only field names (contracts/common.schema.json)."""
    return list(load_schema("common")["$defs"]["evaluator_only_field"]["enum"])


def _format_path(error: ValidationError) -> str:
    parts = ["$"]
    for part in error.absolute_path:
        parts.append(f"[{part}]" if isinstance(part, int) else f".{part}")
    return "".join(parts)


def _leaf_errors(error: ValidationError) -> Iterable[ValidationError]:
    """Descend into oneOf/anyOf/allOf/if-then wrappers to the specific failures."""
    if error.context:
        for sub in error.context:
            yield from _leaf_errors(sub)
    else:
        yield error


def _message(error: ValidationError) -> str:
    if error.validator == "additionalProperties":
        allowed = sorted(error.schema.get("properties", {}))
        extra = sorted(set(error.instance) - set(allowed)) if isinstance(error.instance, dict) else []
        hint = f" Allowed fields: {', '.join(allowed)}." if allowed else ""
        return f"unknown field(s) {', '.join(map(repr, extra))} are not allowed.{hint}"
    if error.validator == "required":
        return error.message.replace("is a required property", "is required but missing")
    if error.validator == "const":
        return f"must be {json.dumps(error.validator_value)}, got {json.dumps(error.instance)}"
    return error.message


def problems(name: str, instance: Any) -> list[Problem]:
    """All validation problems for ``instance`` against contract ``name`` (empty if valid)."""
    found: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for error in sorted(validator(name).iter_errors(instance), key=lambda e: list(map(str, e.absolute_path))):
        for leaf in _leaf_errors(error):
            item = Problem(_format_path(leaf), _message(leaf), str(leaf.validator))
            key = (item.path, item.message)
            if key not in seen:
                seen.add(key)
                found.append(item)
    return found


def failing_keywords(name: str, instance: Any) -> set[str]:
    """Every JSON Schema keyword that failed, including inside combinators."""
    keywords: set[str] = set()

    def walk(error: ValidationError) -> None:
        keywords.add(str(error.validator))
        for sub in error.context or ():
            walk(sub)

    for error in validator(name).iter_errors(instance):
        walk(error)
    return keywords


def is_valid(name: str, instance: Any) -> bool:
    return validator(name).is_valid(instance)


def validate(name: str, instance: Any) -> None:
    """Raise ``ContractError`` listing every problem if ``instance`` is invalid."""
    found = problems(name, instance)
    if found:
        raise ContractError(name, found)


class ContractError(ValueError):
    def __init__(self, name: str, found: list[Problem]):
        self.name = name
        self.problems = found
        lines = "\n".join(f"  - {p}" for p in found)
        super().__init__(f"does not match contract '{name}':\n{lines}")
