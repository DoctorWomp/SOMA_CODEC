"""Pure offline adapter and canonical trace replay, not HORIZON inference."""
import hashlib
import json
from .contracts import Decision, Observation, PROTOCOL, integer


def decide(observation: Observation, arm: str) -> Decision:
    if arm not in ("A", "B"):
        raise ValueError("HORIZON arm must be A or B")
    # B intentionally uses the same stub until the experimental adapter exists.
    decision_id = hashlib.sha256(observation.trace_id.encode()).hexdigest()
    return Decision(PROTOCOL, decision_id, observation.tick,
                    observation.recipient_id, observation.trace_id,
                    "acknowledge" if observation.channel == "speech" else "wait",
                    observation.source_id, arm)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def replay(decisions: list[dict]) -> str:
    """Validate and hash recorded decisions without re-invoking the adapter."""
    previous = -1
    traces: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) != set(Decision.__dataclass_fields__):
            raise ValueError("invalid recorded decision fields")
        if item["protocol"] != PROTOCOL or item["action"] not in ("acknowledge", "wait"):
            raise ValueError("invalid recorded decision")
        if item["horizon_arm"] not in ("A", "B"):
            raise ValueError("invalid recorded arm")
        from .contracts import identifier
        for key in ("trace_id", "actor_id", "observation_trace_id"):
            identifier(item[key], key)
        if item["target_id"] is not None:
            identifier(item["target_id"], "target_id")
        tick = integer(item["tick"], "tick")
        if tick < previous or item["trace_id"] in traces:
            raise ValueError("replay needs ordered ticks and unique trace IDs")
        previous = tick
        traces.add(item["trace_id"])
    return hashlib.sha256(canonical(decisions).encode()).hexdigest()
