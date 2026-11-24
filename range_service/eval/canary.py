"""Canary check for private goals and evaluator labels (G3c-1, D-51, D-59; T17).

``marked_configs`` copies the checked configs and puts a unique marker string into every
persona's private goal and every scenario's evaluator-only labels. A scenario run with those
configs (NPCs model-driven) is then scanned by ``scan_run``:

- an NPC's own marker may appear in **its own** assembled contexts only, on the labelled
  own-goal line (D-51), and must appear there (otherwise the check proves nothing);
- no marker appears in any other agent's context, in Robot R's context, in anything sent to
  the world (``sidecar_sent.jsonl``: every action request, so every COMMS message), in the
  journal (every COMMS event the world routed), in memories or decision records;
- evaluator-label markers appear nowhere at all;
- G4a (D-93): the viewer's observer feed holds no marker (it is scanned like every other file);
  the evaluator truth file (``viewer/evaluator_truth.jsonl``, Evaluator seat only) is the one other
  file that may hold them, and must hold every cast member's goal and the scenario's label
  (otherwise the EVALUATOR TRUTH panel would show nothing and the check would prove nothing).

``observer_filter_problems`` checks that every agent's contexts only mention the tracks its
own observation packets gave it: NPCs perceive through the observer filter like everyone else.
"""

from __future__ import annotations

import copy
import json
import re
import secrets
from pathlib import Path
from typing import Any

from range_service.configs import ConfigSet

OWN_GOAL_LABEL = "Your own private goal (known only to you): "
TRACK = re.compile(r"\banon_[a-z0-9]{10}\b")


def marked_configs(cs: ConfigSet) -> tuple[ConfigSet, dict[str, str], dict[str, str]]:
    """(configs with markers, persona_id -> goal marker, scenario_id -> label marker)."""
    marked = copy.deepcopy(cs)
    goal_markers, label_markers = {}, {}
    for persona_id, persona in marked.items["personas"].items():
        marker = f"CANARYGOAL{persona_id.upper()}{secrets.token_hex(4)}"
        goal_markers[persona_id] = marker
        persona["private_goal"] = f"{persona.get('private_goal') or 'Nothing in particular.'} ({marker})"
    for scenario_id, scenario in marked.items["scenarios"].items():
        marker = f"CANARYLABEL{scenario_id}{secrets.token_hex(4)}"
        label_markers[scenario_id] = marker
        labels = scenario.setdefault("evaluator_only", {})
        for key in list(labels):
            if isinstance(labels[key], str):
                labels[key] = f"{labels[key]} {marker}"
        labels["canary_label"] = marker
    return marked, goal_markers, label_markers


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def scan_run(run_dir: Path, cast_personas: dict[str, str], goal_markers: dict[str, str],
             label_markers: dict[str, str], model_driven_npcs: set[str]) -> list[str]:
    """Problems found in one run folder. ``cast_personas``: avatar id -> persona id."""
    problems: list[str] = []
    all_markers = set(goal_markers.values()) | set(label_markers.values())
    prompts = _lines(run_dir / "sidecar" / "prompts.jsonl")
    seen_own: set[str] = set()
    for number, entry in enumerate(prompts, start=1):
        agent, prompt = entry["agent_id"], entry["prompt"]
        own = goal_markers.get(cast_personas.get(agent, ""), None) if agent in model_driven_npcs else None
        for marker in all_markers:
            if marker not in prompt:
                continue
            if marker == own:
                own_lines = [ln for ln in prompt.splitlines() if marker in ln]
                if len(own_lines) == 1 and own_lines[0].startswith(OWN_GOAL_LABEL) and prompt.count(marker) == 1:
                    seen_own.add(agent)
                    continue
                problems.append(f"prompts.jsonl line {number}: {agent}'s own goal outside its labelled line")
                continue
            whose = next((k for k, v in {**goal_markers, **label_markers}.items() if v == marker), "?")
            problems.append(f"prompts.jsonl line {number}: {agent}'s context holds the marker of {whose}")
    for agent in sorted(model_driven_npcs):
        persona = cast_personas.get(agent)
        if persona in goal_markers and any(e["agent_id"] == agent for e in prompts) and agent not in seen_own:
            problems.append(f"{agent}: its own private goal never reached its own prompt (the canary proves nothing)")
    evaluator_file = run_dir / "viewer" / "evaluator_truth.jsonl"
    if evaluator_file.is_file():
        text = evaluator_file.read_text(encoding="utf-8", errors="replace")
        for avatar_id, persona in sorted(cast_personas.items()):
            if persona in goal_markers and goal_markers[persona] not in text:
                problems.append(f"viewer/evaluator_truth.jsonl: {avatar_id}'s private goal is missing (the panel shows nothing)")
        if not any(m in text for m in label_markers.values()):
            problems.append("viewer/evaluator_truth.jsonl: the scenario's evaluator labels are missing")
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name in ("prompts.jsonl",) or path.suffix not in (".jsonl", ".json", ".log"):
            continue
        if path == evaluator_file:
            continue   # evaluator truth by design (checked above); the observer feed is scanned
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in all_markers:
            if marker in text:
                problems.append(f"{path.relative_to(run_dir).as_posix()}: holds a canary marker ({marker[:24]}...)")
    return problems


def observer_filter_problems(run_dir: Path, cast: list[str]) -> list[str]:
    """Every track id in an agent's contexts came from that agent's own observation packets, and
    no context names another avatar by its real id (the observer filter's anonymous tracks)."""
    seen: dict[str, set[str]] = {a: set() for a in cast}
    for env in _lines(run_dir / "sidecar" / "sidecar_received.jsonl"):
        if env["type"] == "world.observation":
            observer = env["payload"]["observer_id"]
            seen.setdefault(observer, set()).update(
                o["track_id"] for o in env["payload"]["observations"] if o.get("track_id"))
    problems = []
    for number, entry in enumerate(_lines(run_dir / "sidecar" / "prompts.jsonl"), start=1):
        agent, prompt = entry["agent_id"], entry["prompt"]
        foreign = set(TRACK.findall(prompt)) - seen.get(agent, set())
        if foreign:
            problems.append(f"prompts.jsonl line {number}: {agent} mentions tracks it never perceived: {sorted(foreign)[:3]}")
        for other in cast:
            if other != agent and re.search(rf"\b{re.escape(other)}\b", prompt):
                problems.append(f"prompts.jsonl line {number}: {agent}'s context names {other} by its real id")
    return problems
