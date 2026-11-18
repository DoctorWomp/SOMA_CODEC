"""Pulse protocol metrics per run (PULSE_PROTOCOL §10; G3c-2, D-61). Evaluator only.

Computed from each agent's pulse log (simulated time, so stepped runs give the same numbers):

- **wake latency**: from the first trigger of a decision (a wake condition, being addressed, a
  promise coming due) to the decision being made;
- **zombie time**: something relevant within sensing range (a new person, speech) that got no
  presence response (a glance, or the gaze already on it) and no decision within 1 s; each such
  event counts its delay, capped at 10 s;
- **idle model calls per minute**, minute by minute (should fall over a quiet period and
  recover on change), and **CONTINUE versus review** counts;
- **context size** of the reviews over time (should stay flat);
- **FN-1**: answers that walked away from an open conversation without a closing line
  (``FN1_VIOLATION``, must be 0) and those held (``FN1_HELD``).
"""

from __future__ import annotations

from typing import Any

ZOMBIE_AFTER_MS = 1000
ZOMBIE_CAP_MS = 10_000


def _agent(log: list[dict[str, Any]], end_ms: int) -> dict[str, Any]:
    by = lambda k: [e for e in log if e["event"] == k]   # noqa: E731
    decisions = by("DECISION") + by("REVIEW")
    waits = sorted(e.get("waited_ms", 0) for e in decisions if e.get("triggers") and "PULSE_REVIEW" not in e["triggers"])
    responses = [(e["at_ms"], e.get("target")) for e in log if e["event"] in ("GLANCE", "GAZE_PARTNER", "GAZE_RETURN")]
    decided = [e["at_ms"] for e in decisions]
    zombie_ms, zombies = 0, 0
    glance_lat = []
    for e in by("RELEVANT"):
        t0, src = e["at_ms"], e["source"]
        after = [t for t, target in responses if target == src and t >= t0] + [t for t in decided if t >= t0]
        before = [(t, target) for t, target in responses if t < t0]
        attending = bool(before) and max(before)[1] == src          # the gaze was already on it
        delay = (min(after) - t0) if after else min(ZOMBIE_CAP_MS, end_ms - t0)
        glanced = [t - t0 for t, target in responses if target == src and t >= t0]
        if glanced and not attending:
            glance_lat.append(min(glanced))
        if delay > ZOMBIE_AFTER_MS and not attending:
            zombies += 1
            zombie_ms += min(delay, ZOMBIE_CAP_MS)
    idle_reviews = [e for e in by("REVIEW") if e.get("policy") == "MODEL"]
    minutes = max(1, end_ms // 60_000 + (1 if end_ms % 60_000 else 0))
    per_minute = [0] * minutes
    for e in idle_reviews:
        per_minute[min(minutes - 1, e["at_ms"] // 60_000)] += 1
    tokens = [e["tokens"] for e in by("REVIEW") if e.get("tokens") is not None]
    return {
        "decisions": len(decisions), "reviews": len(by("REVIEW")), "continues": len(by("CONTINUE")),
        "wakes": len(by("WAKE")), "glances": len(by("GLANCE")), "preempted": len(by("PREEMPTED")),
        "survey_moves": len(by("SURVEY")), "returns_to_post": len(by("RETURN_TO_POST")),
        "fn1_held": len(by("FN1_HELD")), "fn1_violations": len(by("FN1_VIOLATION")),
        "wake_latency_ms": {"p50": waits[len(waits) // 2] if waits else None, "max": waits[-1] if waits else None,
                            "n": len(waits)},
        "zombie": {"events": zombies, "ms": zombie_ms, "relevant": len(by("RELEVANT"))},
        # FN-2: from hearing or seeing something new to the glance (simulated time).
        "glance_latency_ms": {"max": max(glance_lat) if glance_lat else None, "n": len(glance_lat)},
        "model_reviews_per_minute": per_minute,
        "review_tokens": {"first": tokens[0] if tokens else None, "last": tokens[-1] if tokens else None,
                          "max": max(tokens) if tokens else None, "n": len(tokens)},
    }


def pulse_summary(runtimes: dict[str, Any], journal: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    end_ms = scenario["duration_ticks"] * 1000 // scenario["tick_hz"]
    return {aid: _agent(rt.pulse_log, end_ms) for aid, rt in sorted(runtimes.items()) if rt.pulse is not None}
