"""Pulse protocol metrics per run (PULSE_PROTOCOL §10; G3c-2, D-61; G3d, D-65). Evaluator only.

Computed from each agent's pulse log (simulated time, so stepped runs give the same numbers):

- **wake latency**: from the first trigger of a decision (a wake condition, being addressed, a
  promise coming due) to the decision being made;
- **zombie time** (G3d, D-65): something relevant within sensing range (a new person, speech, an
  unseen voice) that got no **source-linked** response within 1 s, and was not already being
  looked at. A response is linked to the source only if it is a glance, turn or gaze at that
  source (LOOK_AT / TURN_TO with it as target), or a decision whose triggers or action targets
  include it; an unrelated decision does not count. "Already attending" means a gaze interval on
  that source covered the event time: a LOOK_AT holds the head on its target for
  ``LOOK_AT_HOLD_MS`` (the world's 3 s, avatar.gd GAZE_HOLD_TICKS), ending sooner if the next
  LOOK_AT goes elsewhere. Each zombie event counts its delay, capped at 10 s;
- every response measure twice: **accepted** (what the host accepted; the headline) and
  **proposed** (what the agent sent, whatever the host did with it);
- **idle model calls per minute**, minute by minute, and **CONTINUE versus review** counts;
- **context size** of the reviews over time (should stay flat);
- **FN-1**: answers that walked away from an open conversation without a closing line
  (``FN1_VIOLATION``, must be 0), those held (``FN1_HELD``) and those that stayed because the
  closing line was refused (``FN1_STAYED``).
"""

from __future__ import annotations

from typing import Any

ZOMBIE_AFTER_MS = 1000
ZOMBIE_CAP_MS = 10_000
LOOK_AT_HOLD_MS = 3000          # the world holds a LOOK_AT for 180 ticks (avatar.gd GAZE_HOLD_TICKS)
PRESENCE_GAZE = ("GLANCE", "GAZE_PARTNER", "GAZE_RETURN", "GAZE_HOLD", "ARRIVAL_LOOK")   # ARRIVAL_LOOK: G3f, SB-10
LOOKING = ("LOOK_AT", "TURN_TO")


def _responses(log: list[dict[str, Any]], accepted_only: bool) -> tuple[list[tuple[int, str, str]], list[tuple[int, set[str]]]]:
    """(time, target, kind) of every look at someone, and (time, linked sources) of every decision.
    With ``accepted_only``, only requests the host accepted, timed when the result came back."""
    results = {e["request_id"]: e for e in log if e["event"] == "RESULT"}

    def when(request_id: str | None, proposed_ms: int) -> int | None:
        if request_id is None:
            return None                                             # never sent
        if not accepted_only:
            return proposed_ms
        r = results.get(request_id)
        return max(proposed_ms, r["at_ms"]) if r is not None and r["accepted"] else None

    looks: list[tuple[int, str, str]] = []
    decisions: list[tuple[int, set[str]]] = []
    for e in log:
        if e["event"] in PRESENCE_GAZE and e.get("target"):
            t = when(e.get("request_id"), e["at_ms"])
            if t is not None:
                looks.append((t, e["target"], e["event"]))
        elif e["event"] in ("DECISION", "REVIEW"):
            linked = set(e.get("sources") or [])
            times = []
            for request_id, action, target in e.get("actions") or []:
                t = when(request_id, e["at_ms"])
                if t is None:
                    continue
                times.append(t)
                if target:
                    linked.add(target)
                    if action in LOOKING:
                        looks.append((t, target, action))
            if accepted_only and not times:
                continue                                            # nothing of it reached the world
            if linked:
                decisions.append((min(times) if times else e["at_ms"], linked))
    looks.sort()
    return looks, decisions


def gaze_intervals(looks: list[tuple[int, str, str]]) -> list[tuple[int, int, str]]:
    """[start, end) on a target: each LOOK_AT holds LOOK_AT_HOLD_MS, cut short by the next look elsewhere."""
    gaze = [(t, target) for t, target, kind in looks if kind != "TURN_TO"]
    out = []
    for i, (t, target) in enumerate(gaze):
        end = t + LOOK_AT_HOLD_MS
        for t2, target2 in gaze[i + 1:]:
            if t2 >= end:
                break
            if target2 != target:
                end = t2
                break
        out.append((t, end, target))
    return out


def _zombie(log: list[dict[str, Any]], end_ms: int, accepted_only: bool) -> dict[str, Any]:
    looks, decisions = _responses(log, accepted_only)
    intervals = gaze_intervals(looks)
    zombie_ms, zombies, cases, glance_lat = 0, 0, [], []
    relevant = [e for e in log if e["event"] == "RELEVANT"]
    for e in relevant:
        t0, src = e["at_ms"], e["source"]
        attending = any(start < t0 < end and target == src for start, end, target in intervals)
        linked = [t for t, target, _ in looks if target == src and t >= t0] + \
                 [t for t, sources in decisions if src in sources and t >= t0]
        delay = (min(linked) - t0) if linked else min(ZOMBIE_CAP_MS, end_ms - t0)
        glanced = [t - t0 for t, target, kind in looks if target == src and t >= t0 and kind == "GLANCE"]
        if glanced and not attending:
            glance_lat.append(min(glanced))
        if delay > ZOMBIE_AFTER_MS and not attending:
            zombies += 1
            zombie_ms += min(delay, ZOMBIE_CAP_MS)
            if len(cases) < 10:
                cases.append({"at_ms": t0, "source": src, "kind": e.get("kind"),
                              "responded_after_ms": (min(linked) - t0) if linked else None})
    return {"events": zombies, "ms": zombie_ms, "relevant": len(relevant), "cases": cases,
            "glance_latency_ms": {"max": max(glance_lat) if glance_lat else None, "n": len(glance_lat)}}


def _agent(log: list[dict[str, Any]], end_ms: int) -> dict[str, Any]:
    by = lambda k: [e for e in log if e["event"] == k]   # noqa: E731
    decisions = by("DECISION") + by("REVIEW")
    waits = sorted(e.get("waited_ms", 0) for e in decisions if e.get("triggers") and "PULSE_REVIEW" not in e["triggers"])
    accepted = _zombie(log, end_ms, accepted_only=True)
    proposed = _zombie(log, end_ms, accepted_only=False)
    results = {e["request_id"]: e for e in by("RESULT")}
    glance_ids = [e.get("request_id") for e in by("GLANCE") if e.get("request_id")]
    idle_reviews = [e for e in by("REVIEW") if e.get("policy") == "MODEL"]
    minutes = max(1, end_ms // 60_000 + (1 if end_ms % 60_000 else 0))
    per_minute = [0] * minutes
    for e in idle_reviews:
        per_minute[min(minutes - 1, e["at_ms"] // 60_000)] += 1
    tokens = [e["tokens"] for e in by("REVIEW") if e.get("tokens") is not None]
    sent = [r for e in decisions for r in (e.get("actions") or [])]
    return {
        "decisions": len(decisions), "reviews": len(by("REVIEW")), "continues": len(by("CONTINUE")),
        "wakes": len(by("WAKE")), "glances": len(by("GLANCE")), "preempted": len(by("PREEMPTED")),
        "glances_accepted": sum(1 for i in glance_ids if results.get(i, {}).get("accepted")),
        "glances_refused": sum(1 for i in glance_ids if i in results and not results[i]["accepted"]),
        "decision_actions": {"proposed": len(sent),
                             "accepted": sum(1 for r in sent if results.get(r[0], {}).get("accepted")),
                             "refused": sum(1 for r in sent if r[0] in results and not results[r[0]]["accepted"])},
        "discarded_before_send": sum(1 for e in by("DELIVERY") if e.get("what") == "DISCARDED"),
        "idle_debits": len(by("IDLE_DEBIT")),
        "survey_moves": len(by("SURVEY")), "returns_to_post": len(by("RETURN_TO_POST")),
        "fn1_held": len(by("FN1_HELD")), "fn1_violations": len(by("FN1_VIOLATION")), "fn1_stayed": len(by("FN1_STAYED")),
        "wake_latency_ms": {"p50": waits[len(waits) // 2] if waits else None, "max": waits[-1] if waits else None,
                            "n": len(waits)},
        # Headline: what the world accepted. "proposed" counts what the agent sent, accepted or not.
        "zombie": {k: accepted[k] for k in ("events", "ms", "relevant", "cases")},
        "zombie_proposed": {k: proposed[k] for k in ("events", "ms", "relevant", "cases")},
        # FN-2: from hearing or seeing something new to the glance (simulated time).
        "glance_latency_ms": accepted["glance_latency_ms"],
        "glance_latency_proposed_ms": proposed["glance_latency_ms"],
        "model_reviews_per_minute": per_minute,
        "review_tokens": {"first": tokens[0] if tokens else None, "last": tokens[-1] if tokens else None,
                          "max": max(tokens) if tokens else None, "n": len(tokens)},
    }


def pulse_summary(runtimes: dict[str, Any], journal: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    end_ms = scenario["duration_ticks"] * 1000 // scenario["tick_hz"]
    return {aid: _agent(rt.pulse_log, end_ms) for aid, rt in sorted(runtimes.items()) if rt.pulse is not None}
