"""Shared helpers for tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from range_service import contracts

EXAMPLES = contracts.EXAMPLES_DIR


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def example_files(name: str, kind: str) -> list[Path]:
    """kind is 'valid' or 'invalid' (excluding the _expect.json index)."""
    folder = EXAMPLES / name / kind
    return sorted(p for p in folder.glob("*.json") if not p.name.startswith("_"))


def all_examples(kind: str) -> list[tuple[str, Path]]:
    return [(d.name, p) for d in sorted(EXAMPLES.iterdir()) if d.is_dir() for p in example_files(d.name, kind)]


def object_paths(value: Any, path: tuple = ()) -> Iterator[tuple]:
    """Yield the path of every JSON object (dict) inside ``value``, including the root."""
    if isinstance(value, dict):
        yield path
        for key, child in value.items():
            yield from object_paths(child, path + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from object_paths(child, path + (i,))


def get_at(value: Any, path: tuple) -> Any:
    for part in path:
        value = value[part]
    return value
