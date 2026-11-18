"""Activities with wake conditions (PULSE_PROTOCOL §3; G3c-2, D-61).

Every decision may now say not only what to do, but what the agent is doing from then on and
when to reconsider: ``{"kind": "WAIT_FOR", "target_id": track, "commitment_id": id,
"review_after_s": 120, "wake_if": [{"target_within_m": 2}, {"addressed": true}]}``. The
deterministic intent monitor (agents/pulse.py) watches the wake conditions on every packet; the
model is asked again only when one fires or the review time comes.

- Optional: an answer without an activity works exactly as before, and the runtime **derives**
  one from the actions (recorded ``DERIVED``, never passed off as chosen).
- Only conditions today's senses can check. ``horizon`` conditions (Focus, Prism, Haze) are
  reserved in the contract for G5 and refused here: nothing fakes a HORIZON layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PALETTE = ("CONVERSE", "WAIT_FOR", "ATTEND", "SURVEY", "TRAVEL_TO", "ASSIST", "OBSERVE", "RETURN_TO_POST",
           "RECHARGE", "REST")
WAKE_KINDS = ("target_within_m", "target_lost", "addressed", "speech_heard", "new_track", "commitment_due")
RESERVED_WAKE = ("horizon",)          # G5: Focus, Prism, Haze
IDLE_KINDS = frozenset({"WAIT_FOR", "ATTEND", "SURVEY", "OBSERVE", "RETURN_TO_POST", "REST", "RECHARGE"})
TARGETED = frozenset({"CONVERSE", "WAIT_FOR", "ASSIST", "OBSERVE"})
MAX_WAKE = 4


@dataclass
class Activity:
    kind: str
    target_id: str | None = None
    commitment_id: str | None = None
    review_after_s: int = 60
    wake_if: list[dict[str, Any]] = field(default_factory=list)
    source: str = "DERIVED"
    started_ms: int = 0
    destination: dict[str, float] | None = None     # TRAVEL_TO / RETURN_TO_POST / SURVEY (not recorded)

    def record(self) -> dict[str, Any]:
        return {"kind": self.kind, "target_id": self.target_id, "commitment_id": self.commitment_id,
                "review_after_s": int(self.review_after_s), "wake_if": [dict(w) for w in self.wake_if],
                "source": self.source}

    def wants(self, kind: str) -> Any:
        for w in self.wake_if:
            if kind in w:
                return w[kind]
        return None


def answer_schema_part(targets: tuple[str, ...] | None, max_review_s: int = 600) -> dict[str, Any]:
    """The optional ``activity`` in a constrained answer: short, with person ids limited to the
    perceived tracks, and only the wake conditions the senses can check (never ``horizon``)."""
    target = {"anyOf": [{"enum": list(targets)}, {"type": "null"}]} if targets else {"type": "null"}
    if targets is None:
        target = {"anyOf": [{"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"}, {"type": "null"}]}
    wake = [{"type": "object", "additionalProperties": False, "required": ["target_within_m"],
             "properties": {"target_within_m": {"type": "number", "minimum": 0.5, "maximum": 30}}}]
    wake += [{"type": "object", "additionalProperties": False, "required": [k], "properties": {k: {"const": True}}}
             for k in WAKE_KINDS if k != "target_within_m"]
    return {"type": "object", "additionalProperties": False, "required": ["kind"],
            "properties": {"kind": {"enum": list(PALETTE)}, "target_id": target,
                           "commitment_id": {"type": "string", "pattern": "^mem_[A-Za-z0-9_]{1,56}$"},
                           "review_after_s": {"type": "integer", "minimum": 5, "maximum": max_review_s},
                           "wake_if": {"type": "array", "maxItems": MAX_WAKE, "items": {"anyOf": wake}}}}


def parse(raw: Any, *, now_ms: int, default_review_s: int, max_review_s: int,
          open_commitments: set[str], perceived: set[str]) -> tuple[Activity | None, str | None]:
    """The model's activity, checked. Returns (activity, None) or (None, error)."""
    if not isinstance(raw, dict) or set(raw) - {"kind", "target_id", "commitment_id", "review_after_s", "wake_if"}:
        return None, '"activity" must be an object with "kind" and optional target_id, commitment_id, review_after_s, wake_if'
    kind = raw.get("kind")
    if kind not in PALETTE:
        return None, f'activity kind {str(kind)[:30]!r} is not one of {", ".join(PALETTE)}'
    target = raw.get("target_id")
    if target is not None and target not in perceived:
        return None, f"activity target {str(target)[:40]!r} is not a track you perceive"
    commitment = raw.get("commitment_id")
    if commitment is not None and commitment not in open_commitments:
        return None, f"activity commitment {str(commitment)[:40]!r} is not one of your open promises"
    review = raw.get("review_after_s", default_review_s)
    if not isinstance(review, int) or isinstance(review, bool) or not 5 <= review <= max_review_s:
        return None, f'"review_after_s" must be a whole number of seconds from 5 to {max_review_s}'
    wake = raw.get("wake_if", [])
    if not isinstance(wake, list) or len(wake) > MAX_WAKE:
        return None, f'"wake_if" must be a list of at most {MAX_WAKE} conditions'
    for cond in wake:
        if not isinstance(cond, dict) or len(cond) != 1:
            return None, "each wake condition is an object with one key"
        (key, value), = cond.items()
        if key in RESERVED_WAKE:
            return None, f'wake condition "{key}" is reserved for HORIZON layers (G5) and not available yet'
        if key not in WAKE_KINDS:
            return None, f'unknown wake condition "{str(key)[:30]}"'
        if key == "target_within_m":
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.5 <= value <= 30:
                return None, '"target_within_m" must be a distance from 0.5 to 30 m'
        elif value is not True:
            return None, f'"{key}" must be true'
    if kind in TARGETED and target is None and kind != "OBSERVE":
        return None, f"{kind} needs a target_id (someone you perceive)"
    return Activity(kind, target, commitment, review, [dict(c) for c in wake], "CHOSEN", now_ms), None


def derive(actions: list[dict[str, Any]], *, now_ms: int, current: Activity | None, partner: str | None,
           promised: dict[str, str], default_review_s: int, has_task_goal: bool, post_duty: bool) -> Activity:
    """The activity implied by the actions when the answer names none (recorded DERIVED).

    - a promise to someone (in this answer, or still open and nothing else happening) → WAIT_FOR them;
    - SPEAK to someone, or turning/looking at a conversation partner → CONVERSE with them;
    - MOVE_TO a point → TRAVEL_TO it; MOVE_TO a person → ASSIST them;
    - nothing that changes the situation (WAIT, NO_OP, a glance) → keep the current activity
      (CONTINUED); with none, ATTEND (post duty or any task) or SURVEY (no task at all).
    """
    def make(kind: str, target: str | None = None, commitment: str | None = None, wake: list | None = None,
             review: int | None = None, destination: dict | None = None) -> Activity:
        return Activity(kind, target, commitment, review or default_review_s, wake or [], "DERIVED", now_ms, destination)

    for a in actions:
        if a.get("commitment"):
            target = a["args"].get("addressee_id", a["args"].get("target_id"))
            if target:
                return make("WAIT_FOR", target, promised.get(target), [{"addressed": True}, {"target_within_m": 2.0},
                                                                         {"target_lost": True}], 120)
    for a in actions:
        target = a["args"].get("addressee_id") if a["action"] == "SPEAK" else None
        if target:
            return make("CONVERSE", target, None, [{"addressed": True}, {"target_lost": True}], 20)
    for a in actions:
        if a["action"] == "MOVE_TO":
            if a["args"].get("target_id"):
                return make("ASSIST", a["args"]["target_id"], None, [{"addressed": True}, {"target_lost": True}], 30)
            return make("TRAVEL_TO", None, None, [{"addressed": True}, {"new_track": True}], 30,
                        destination=a["args"].get("destination"))
    still_valid = current is not None and not (
        (current.kind == "CONVERSE" and current.target_id != partner)                    # the conversation is over
        or (current.kind == "WAIT_FOR" and current.target_id not in promised))         # the promise is kept or gone
    if current is not None and still_valid:
        return Activity(current.kind, current.target_id, current.commitment_id, current.review_after_s,
                        list(current.wake_if), "CONTINUED", current.started_ms, current.destination)
    if partner is not None:
        return make("CONVERSE", partner, None, [{"addressed": True}, {"target_lost": True}], 20)
    if promised:
        target = sorted(promised)[0]
        return make("WAIT_FOR", target, promised[target], [{"addressed": True}, {"target_within_m": 2.0},
                                                           {"target_lost": True}], 120)
    if post_duty or has_task_goal:
        return make("ATTEND", None, None, [{"addressed": True}, {"new_track": True}, {"speech_heard": True}])
    return make("SURVEY", None, None, [{"addressed": True}, {"new_track": True}, {"speech_heard": True}])
