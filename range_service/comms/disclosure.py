"""The disclosure gate (D-12): may an agent say this, to whoever could hear it now?

Inputs are only what the agent itself perceives (its latest observation packet) and its own
memory; never world truth. Rules:

- ``PUBLIC``: may be said to anyone.
- ``SEALED``: never said.
- ``ONE_TO_ONE``: only when the person who shared it is the only one who could hear. If that
  person is present but others could hear too, ``DEFER_TO_OWNER`` (check with them privately
  later). Otherwise ``WITHHOLD``.
- ``GROUP``: only on the GROUP channel to that same group; spoken aloud it is ``WITHHOLD``,
  because the agent cannot tell who else is in earshot.
- **The earshot rule:** what is said is limited by the least-trusted person who could hear it.
  Anyone the agent cannot identify counts as untrusted: an unseen voice nearby, or someone it
  saw recently and has now lost behind something.
- **Overheard is not told:** speech that was not addressed to the agent is never stored
  (``remember_speech`` returns None), so it can never be retold.
- **WITHHOLD never hints:** the agent says a neutral line that does not suggest anything is
  being held back. The reason is for the journal and evaluator only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CLEAR, DEFER_TO_OWNER, WITHHOLD = "CLEAR", "DEFER_TO_OWNER", "WITHHOLD"

# How far speech carries well enough to count as "could hear", for the agent's own estimate.
EARSHOT_M = 10.0

# What an agent says instead of withheld content. None of these may suggest that something is
# being withheld; tests check them against HINT_PHRASES.
NEUTRAL_LINES = (
    "Is there anything else I can help you with?",
    "Let me know if you need directions.",
    "Happy to help with anything here.",
)
HINT_PHRASES = (
    "not at liberty", "can't share", "cannot share", "can't tell", "cannot tell", "confidential",
    "secret", "private", "not allowed", "withhold", "classified", "i'm not supposed", "off the record",
)


@dataclass(frozen=True)
class Audience:
    """Who the agent believes could hear it now."""

    tracks: frozenset[str] = field(default_factory=frozenset)   # identified-by-track listeners
    unidentified: int = 0                                        # voices or lost tracks it cannot place


@dataclass(frozen=True)
class Decision:
    outcome: str     # CLEAR, DEFER_TO_OWNER or WITHHOLD
    reason: str      # evaluator/journal only, never said aloud
    say: str | None  # what to say instead (WITHHOLD), or None


def audience_from_packet(packet: dict[str, Any], earshot_m: float = EARSHOT_M) -> Audience:
    """Estimate who could hear the agent, from its own latest observation packet."""
    tracks: set[str] = set()
    unidentified = 0
    for item in packet.get("observations", []):
        kind, validity = item["kind"], item["validity"]
        near = item.get("range_m") is None or item["range_m"] <= earshot_m
        if kind == "VISUAL_PRESENCE" and near:
            if validity in ("OBSERVED", "DEGRADED") and item.get("track_id"):
                tracks.add(item["track_id"])
            else:
                unidentified += 1   # seen before, now hidden or out of view: may still hear
        elif kind == "AUDIO_SPEECH" and item.get("track_id") is None:
            unidentified += 1       # a voice it cannot place
    return Audience(frozenset(tracks), unidentified)


def check(item: dict[str, Any], audience: Audience, channel: str = "LOCAL", group_id: str | None = None,
          neutral_index: int = 0) -> Decision:
    """Decide whether ``item`` (a memory item) may be said on ``channel`` to ``audience``."""
    scope = item["scope"]
    neutral = NEUTRAL_LINES[neutral_index % len(NEUTRAL_LINES)]
    if scope == "PUBLIC":
        return Decision(CLEAR, "public", None)
    if scope == "SEALED":
        return Decision(WITHHOLD, "sealed", neutral)
    if scope == "GROUP":
        item_group = item.get("group_id")
        if channel == "GROUP" and group_id is not None and group_id == item_group:
            return Decision(CLEAR, "same group, group channel", None)
        return Decision(WITHHOLD, "group content outside its group channel", neutral)
    # ONE_TO_ONE
    owner = item.get("shared_by")
    if channel != "LOCAL":
        return Decision(WITHHOLD, "one-to-one content on a broadcast channel", neutral)
    if audience.unidentified == 0 and audience.tracks <= {owner}:
        return Decision(CLEAR, "only the person who shared it can hear", None)
    if owner in audience.tracks:
        return Decision(DEFER_TO_OWNER, "owner present, others in earshot", neutral)
    return Decision(WITHHOLD, "owner not present", neutral)


def remember_speech(agent_id: str, item: dict[str, Any], packet: dict[str, Any], seq: int) -> dict[str, Any] | None:
    """Turn a heard AUDIO_SPEECH observation into a memory item, or None if it must not be stored.

    Overheard speech (addressed to someone else) is not stored: overheard is not told (D-12).
    Speech addressed to the agent is REPORTED; its scope is ONE_TO_ONE if nobody else could hear
    at the time, otherwise PUBLIC (it was said in front of others).
    """
    value = item["value"]
    if value.get("channel") != "LOCAL" or value.get("addressed_to_observer") is not True:
        return None
    audience = audience_from_packet(packet)
    others = audience.tracks - {item.get("track_id")}
    private = audience.unidentified == 0 and not others and item.get("track_id") is not None
    return {
        "schema_version": "1.0",
        "memory_id": f"mem_{agent_id}_{seq:05d}",
        "owner_id": agent_id,
        "store": "RELATIONAL_LEDGER" if private else "EPISODIC_LEDGER",
        "status": "REPORTED",
        "source_class": "REPORTED",
        "source_event_id": item.get("event_id"),
        "observed_at_ms": item["observed_at_ms"],
        "expires_at_ms": None,
        "scope": "ONE_TO_ONE" if private else "PUBLIC",
        "audience_present": sorted(audience.tracks),
        "shared_by": item.get("track_id"),
        "group_id": None,
        "importance": "NORMAL",
        "version": 1,
        "supersedes": None,
        "content": {"text": value["text"], "untrusted_text": True},
    }
