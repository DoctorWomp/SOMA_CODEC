"""Strict v1 wire types. JSON numbers for ticks must be integers (not bool)."""
from dataclasses import asdict, dataclass
from typing import Literal

PROTOCOL = "soma-range/1"
Visibility = Literal["public", "private"]


def integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{name} must be a nonempty string of at most 128 characters")
    return value


@dataclass(frozen=True)
class Observation:
    protocol: str
    trace_id: str
    tick: int
    recipient_id: str
    source_id: str | None
    channel: Literal["speech", "gesture", "environment"]
    visibility: Visibility
    content: str

    @classmethod
    def parse(cls, data: object) -> "Observation":
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("observation fields must match v1 exactly")
        if data["protocol"] != PROTOCOL:
            raise ValueError("unsupported protocol")
        for key in ("trace_id", "recipient_id"):
            identifier(data[key], key)
        integer(data["tick"], "tick")
        if data["source_id"] is not None:
            identifier(data["source_id"], "source_id")
        if data["channel"] not in ("speech", "gesture", "environment"):
            raise ValueError("unsupported channel")
        if data["visibility"] not in ("public", "private"):
            raise ValueError("unsupported visibility")
        if not isinstance(data["content"], str) or len(data["content"]) > 4096:
            raise ValueError("content must be a string of at most 4096 characters")
        return cls(**data)


@dataclass(frozen=True)
class Decision:
    protocol: str
    trace_id: str
    tick: int
    actor_id: str
    observation_trace_id: str
    action: Literal["acknowledge", "wait"]
    target_id: str | None
    horizon_arm: Literal["A", "B"]

    def wire(self) -> dict:
        return asdict(self)


class Memory:
    """Only owner-scoped reads; no global context accessor."""
    def __init__(self) -> None:
        self._items: dict[str, list[Observation]] = {}

    def remember(self, owner: str, observation: Observation) -> None:
        if owner != observation.recipient_id:
            raise ValueError("memory owner must be observation recipient")
        self._items.setdefault(owner, []).append(observation)

    def recall(self, owner: str) -> tuple[Observation, ...]:
        return tuple(self._items.get(owner, ()))


@dataclass(frozen=True)
class Communication:
    """Proposed send event; world routing must produce eligible observations."""
    protocol: str
    trace_id: str
    tick: int
    sender_id: str
    recipient_id: str | None
    channel: Literal["speech", "gesture"]
    visibility: Visibility
    content: str

    @classmethod
    def parse(cls, data: object) -> "Communication":
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("communication fields must match v1 exactly")
        identifier(data["sender_id"], "sender_id")
        if data["recipient_id"] is not None:
            identifier(data["recipient_id"], "recipient_id")
        if data["channel"] not in ("speech", "gesture"):
            raise ValueError("unsupported communication channel")
        if data["visibility"] == "private" and data["recipient_id"] is None:
            raise ValueError("private communication requires an addressed recipient")
        Observation.parse({key: value for key, value in dict(
            data, source_id=data["sender_id"],
            recipient_id=data["recipient_id"] or data["sender_id"]).items()
                           if key != "sender_id"})
        return cls(**data)
