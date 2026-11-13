"""Load and check the editable content files in ``configs/`` (RANGE_V0_SCOPE §2.6).

Each folder has a contract in ``contracts/``. A config is accepted only if:

1. it is valid YAML with no duplicate keys (plain YAML silently keeps the last one),
2. it matches its JSON Schema,
3. its id matches its file name, and
4. everything it refers to (map, persona, body, preset, spawn point) exists.

Problems are reported as ``file: location: what is wrong`` so the owner can fix
them without reading code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import contracts

CONFIGS_DIR = contracts.REPO_ROOT / "configs"

# folder -> (contract name, id field)
KINDS: dict[str, tuple[str, str]] = {
    "maps": ("map", "map_id"),
    "bodies": ("body", "body_id"),
    "personas": ("persona", "persona_id"),
    "presets": ("preset", "preset_id"),
    "scenarios": ("scenario", "scenario_id"),
}


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys instead of keeping the last one."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    seen: dict[Any, int] = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None,
                f"duplicate key {key!r} (first defined on line {seen[key] + 1})",
                key_node.start_mark,
            )
        seen[key] = key_node.start_mark.line
    return loader.construct_mapping(node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_StrictLoader)  # noqa: S506 - SafeLoader subclass


@dataclass(frozen=True)
class ConfigProblem:
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


@dataclass
class ConfigSet:
    """All configs found, keyed by folder then id.

    ``broken`` holds (folder, file stem) of files that exist but failed to load,
    so references to them are not reported a second time as "not found".
    """

    items: dict[str, dict[str, dict[str, Any]]]
    files: dict[tuple[str, str], str]
    broken: set[tuple[str, str]]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root.parent).as_posix()
    except ValueError:
        return path.as_posix()


def load_and_check(config_dir: Path = CONFIGS_DIR) -> tuple[ConfigSet, list[ConfigProblem]]:
    """Load every config under ``config_dir`` and return what loaded plus all problems."""
    found: list[ConfigProblem] = []
    items: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in KINDS}
    files: dict[tuple[str, str], str] = {}
    broken: set[tuple[str, str]] = set()

    for kind, (contract, id_field) in KINDS.items():
        folder = config_dir / kind
        if not folder.is_dir():
            continue
        for path in sorted([*folder.glob("*.yaml"), *folder.glob("*.yml")]):
            rel = _rel(path, config_dir)
            broken.add((kind, path.stem))  # removed again once the file loads cleanly
            try:
                data = load_yaml(path)
            except yaml.YAMLError as exc:
                found.append(ConfigProblem(rel, f"not valid YAML: {exc}".replace("\n", " ")))
                continue
            if not isinstance(data, dict):
                found.append(ConfigProblem(rel, "the file must contain a mapping of fields (key: value), not "
                                                f"{type(data).__name__}"))
                continue
            schema_problems = contracts.problems(contract, data)
            for p in schema_problems:
                found.append(ConfigProblem(rel, str(p)))
            if schema_problems:
                continue
            config_id = data[id_field]
            if config_id != path.stem:
                found.append(ConfigProblem(rel, f"{id_field} is {config_id!r} but the file is named "
                                                f"{path.name!r}; they must match"))
                continue
            if config_id in items[kind]:
                found.append(ConfigProblem(rel, f"{id_field} {config_id!r} is defined twice"))
                continue
            items[kind][config_id] = data
            files[(kind, config_id)] = rel
            broken.discard((kind, path.stem))

    config_set = ConfigSet(items=items, files=files, broken=broken)
    found.extend(_cross_checks(config_set))
    return config_set, found


def _inside(bounds: dict, point: dict) -> bool:
    return 0 <= point["x"] <= bounds["width_m"] and 0 <= point["z"] <= bounds["depth_m"]


def _cross_checks(cs: ConfigSet) -> list[ConfigProblem]:
    found: list[ConfigProblem] = []

    def missing(kind: str, ref: str) -> bool:
        """True if ``ref`` is absent and not merely broken (a broken file is already reported)."""
        return ref not in cs.items[kind] and (kind, ref) not in cs.broken

    maps, personas, scenarios = cs.items["maps"], cs.items["personas"], cs.items["scenarios"]

    for map_id, m in maps.items():
        f = cs.files[("maps", map_id)]
        for sp in m["spawn_points"]:
            if not _inside(m["bounds"], sp["position"]):
                found.append(ConfigProblem(f, f"spawn point {sp['spawn_id']!r} is outside the map bounds"))
        for collection, key in (("zones", "zone_id"), ("walls", "wall_id"), ("spawn_points", "spawn_id"),
                                ("props", "prop_id"), ("platforms", "platform_id"), ("nav_links", "link_id")):
            ids = [entry[key] for entry in m.get(collection, [])]
            for dup in sorted({i for i in ids if ids.count(i) > 1}):
                found.append(ConfigProblem(f, f"{collection}: id {dup!r} is used more than once"))

    for persona_id, p in personas.items():
        if missing("bodies", p["default_body"]):
            found.append(ConfigProblem(cs.files[("personas", persona_id)],
                                       f"default_body {p['default_body']!r} not found in configs/bodies/"))

    for scenario_id, s in scenarios.items():
        f = cs.files[("scenarios", scenario_id)]
        game_map = maps.get(s["map"])
        if missing("maps", s["map"]):
            found.append(ConfigProblem(f, f"map {s['map']!r} not found in configs/maps/"))
        spawn_ids = {sp["spawn_id"] for sp in game_map["spawn_points"]} if game_map else set()
        place_ids = spawn_ids | ({z["zone_id"] for z in game_map["zones"]} if game_map else set())
        for avatar_id, entry in s["cast"].items():
            where = f"cast.{avatar_id}"
            if missing("personas", entry["persona"]):
                found.append(ConfigProblem(f, f"{where}.persona {entry['persona']!r} not found in configs/personas/"))
            if missing("bodies", entry["body"]):
                found.append(ConfigProblem(f, f"{where}.body {entry['body']!r} not found in configs/bodies/"))
            if missing("presets", entry["preset"]):
                found.append(ConfigProblem(f, f"{where}.preset {entry['preset']!r} not found in configs/presets/"))
            if game_map is not None and entry["spawn"] not in spawn_ids:
                found.append(ConfigProblem(f, f"{where}.spawn {entry['spawn']!r} is not a spawn point of map "
                                              f"{s['map']!r}"))
        for i, event in enumerate(s["events"]):
            if event["at_tick"] >= s["duration_ticks"]:
                found.append(ConfigProblem(f, f"events[{i}] at_tick {event['at_tick']} is after the scenario ends "
                                              f"(duration_ticks {s['duration_ticks']})"))
            if "actor" in event and event["actor"] not in s["cast"]:
                found.append(ConfigProblem(f, f"events[{i}].actor {event['actor']!r} is not in the cast"))
            if game_map is not None and "where" in event and event["where"] not in place_ids:
                found.append(ConfigProblem(f, f"events[{i}].where {event['where']!r} is not a zone or spawn point "
                                              f"of map {s['map']!r}"))
    return found
