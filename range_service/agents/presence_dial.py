"""The presence dial (G3e, D-74; EXPRESSION_PRINCIPLES §5, §9; FIELD_NOTES FN-7).

One amplitude, from 0 (subtle) to 1 (performative), scales every ambient and presence channel of
a robot: blink and eye-shift size, light breathing and pulse depth, small head adjustments. Too
subtle and nobody notices; too performative and it reads as patronizing or overstimulating.

**Baseline from configuration** (no adaptation yet): the scenario's directive
(``presence_amplitude``), else the persona's, else ``configs/pulse.yaml`` presence.amplitude.default.
A map zone may override it for robots inside the zone (Godot applies that, from the map data).
``tools/run_scenario.py --presence subtle|default|performative|0.35`` overrides everything for a
watched comparison.

**G5 hook:** ``adapt(baseline, context)`` is where HORIZON readings will move the dial by the §5
rules (start small, gauge, back off fast, warm up slowly; inferred preferences stay within the
interaction and decay, D-13). Today it returns the baseline unchanged, and nothing calls it with
a context. Presentation only: the dial never changes what the world simulates.
"""

from __future__ import annotations

from typing import Any


def directive_entry(entry: dict[str, Any], persona: dict[str, Any], directives: dict[str, Any]) -> dict[str, Any] | None:
    """The directive config that applies to a cast entry (the same rule as factory.directive_for)."""
    if "directive" in entry:
        return directives[entry["directive"]]
    for d in sorted(directives.values(), key=lambda d: d["directive_id"]):
        if persona["role"] in d.get("default_for_roles", []):
            return d
    return None


def baseline(entry: dict[str, Any], persona: dict[str, Any], directives: dict[str, Any],
             pulse_cfg: dict[str, Any]) -> float:
    directive = directive_entry(entry, persona, directives)
    if directive is not None and "presence_amplitude" in directive:
        return float(directive["presence_amplitude"])
    if "presence_amplitude" in persona:
        return float(persona["presence_amplitude"])
    return float(pulse_cfg["presence"]["amplitude"]["default"])


def resolve(spec: str | None, pulse_cfg: dict[str, Any]) -> float | None:
    """A command-line override: a preset name or a number from 0 to 1; None = no override."""
    if spec is None:
        return None
    presets = pulse_cfg["presence"]["amplitude"]["presets"]
    if spec in presets:
        return float(presets[spec])
    try:
        value = float(spec)
    except ValueError:
        raise ValueError(f"--presence must be one of {', '.join(presets)} or a number from 0 to 1") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError("--presence must be from 0 (subtle) to 1 (performative)")
    return value


def adapt(base: float, context: Any = None) -> float:
    """G5 hook (EXPRESSION_PRINCIPLES §5): HORIZON-informed adaptation. Not built: returns the baseline."""
    return base
