"""The Demo policy: rule-based behavior that works with no model (D-21, Blueprint §20 G3 "Demo policy").

It is an honest stand-in, not a model imitation: short fixed rules, fixed lines, and "I don't
know" when it doesn't. It uses only what the runtime perceived and remembered.

Robot (expo assistant) rules, in priority order:

1. **Start:** walk to the cast entry's ``task_goal`` if it has one.
2. **Addressed by the current partner (or by anyone when free):** turn to them, show
   ``listening``, answer from known topics. A farewell ends the conversation.
3. **Addressed by someone else while busy:** a brief "I'll be with you in a moment", recorded as
   a **commitment** (Blueprint §12.3 example).
4. **A wave toward it while free:** greet back (wave if the body can, else a light and glyph) and
   ask how it can help. **While busy:** acknowledge with a nod (or head tilt) and promise to come
   back, without interrupting the partner.
5. **Free again with an open promise to someone still in view:** turn to them, thank them for
   waiting, and keep the promise.

Conversation state (who the partner is, when a conversation ends) is kept by the runtime from
perception, so this policy only reads it. Every light is paired with words or a gesture (D-14). Expressions are picked from what the body
can show; a body that cannot show any variant simply skips the expression.

NPC rules (C1 templates): wave back at a robot that waves at them, if the body can. Speech for
scripted NPCs comes from the scenario's event tape, so they do not improvise lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import AgentRuntime

FAREWELLS = ("bye", "goodbye", "see you", "that's all")
# "Give me a moment": the person will come back to it (G3c-2, SB-06).
WAIT_PHRASES = ("one moment", "just a moment", "give me a minute", "hold on", "one second")

# Topic keywords -> answer. "I don't know" answers are deliberate: unknown stays unknown.
ANSWERS: list[tuple[tuple[str, ...], str]] = [
    (("cafe", "café", "coffee"), "I don't know of a cafe in this sandbox. There are chairs in the corner if you'd like to sit."),
    (("start", "when", "schedule", "soon"), "I don't know the demo schedule, sorry."),
    (("anyone", "go up", "allowed", "can i"), "Yes, anyone can go up: the ramp works for wheels, the stairs for walking."),
    (("demo", "platform"), "The demo area is on the raised platform. You can reach it by the ramp or the stairs."),
    (("chair", "sit", "rest"), "There are chairs in the corner of the hall."),
]
DEFAULT_ANSWER = "I'm not sure about that. I can help with directions around the sandbox."


def answer_for(text: str) -> str:
    lowered = text.lower()
    for keys, answer in ANSWERS:
        if any(k in lowered for k in keys):
            return answer
    return DEFAULT_ANSWER


def asks_to_wait(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in WAIT_PHRASES)


def is_farewell(text: str) -> bool:
    lowered = text.lower()
    return any(f in lowered for f in FAREWELLS)


@dataclass
class Proposal:
    action: str
    args: dict[str, Any]
    commitment: str | None = None          # what this utterance promises (a SPEAK)
    fulfills: list[str] = field(default_factory=list)   # commitment ids this action keeps

    def as_dict(self) -> dict[str, Any]:
        return {"action": self.action, "args": self.args}


class RobotDemoPolicy:
    name = "DEMO"

    def decide(self, rt: "AgentRuntime", triggers: list[str]) -> list[Proposal]:
        conv = rt.conversation
        out: list[Proposal] = []

        if "START" in triggers and rt.task_goal is not None:
            return [Proposal("MOVE_TO", {"destination": rt.task_goal})]

        for item in rt.perceived.addressed:
            speaker = item.get("track_id")
            text = item["value"]["text"]
            if conv.partner is None or speaker == conv.partner:
                if speaker is not None:
                    # While walking, attention goes with the head and the stride is kept (G3f, SB-10;
                    # D-72: the body turns only once it stands, or for a target beyond the neck).
                    out.append(Proposal("LOOK_AT" if rt.en_route() else "TURN_TO", {"target_id": speaker}))
                if is_farewell(text):
                    out += self._expressed("thank_you", speaker, rt)
                    out.append(Proposal("SPEAK", {"channel": "LOCAL", "text": "You're welcome. Enjoy the expo!",
                                                  "addressee_id": speaker}))
                elif asks_to_wait(text) and speaker is not None and not rt.memory.commitments_to(speaker):
                    # They asked it to wait: say so, and keep the promise when they come back (SB-06).
                    out.append(Proposal("SPEAK", {"channel": "LOCAL", "text": "Of course, take your time. I'll be here.",
                                                  "addressee_id": speaker},
                                        commitment="Help them when they are ready."))
                else:
                    # Answering someone it promised to help keeps that promise.
                    kept = [c["memory_id"] for c in rt.memory.commitments_to(speaker)] if speaker else []
                    out += self._expressed("listening", speaker, rt)
                    out.append(Proposal("SPEAK", {"channel": "LOCAL", "text": answer_for(text), "addressee_id": speaker},
                                        fulfills=kept))
                return out[:3]
            if speaker is not None and not rt.memory.commitments_to(speaker):
                return [Proposal("SPEAK", {"channel": "LOCAL", "text": "I'll be with you in a moment.", "addressee_id": speaker},
                                 commitment="Help them after the current conversation.")]

        for item in rt.perceived.greetings:
            waver = item["track_id"]
            if conv.partner is None:
                out += self._expressed("greeting", waver, rt, prefer_gesture=True)
                out.append(Proposal("SPEAK", {"channel": "LOCAL", "text": "Hello! How can I help?", "addressee_id": waver}))
                return out[:3]
            if waver != conv.partner and not rt.memory.commitments_to(waver):
                acknowledged = self._expressed("acknowledge", waver, rt, prefer_gesture=True)
                if acknowledged:
                    acknowledged[0].commitment = "Help them after the current conversation."
                    return acknowledged
                return [Proposal("GESTURE", {"gesture": "NOD", "target_id": waver},
                                 commitment="Help them after the current conversation.")] \
                    if rt.body_supports_gesture("NOD") else []

        if "COMMITMENT_DUE" in triggers and conv.partner is None:
            for c in rt.memory.open_commitments():
                for track in c["audience_present"]:
                    if rt.ws.visible(track):
                        out.append(Proposal("LOOK_AT" if rt.en_route() else "TURN_TO", {"target_id": track}))
                        out += self._expressed("greeting", track, rt, prefer_gesture=False)
                        out.append(Proposal("SPEAK", {"channel": "LOCAL", "text": "Thanks for waiting. How can I help?",
                                                      "addressee_id": track}, fulfills=[c["memory_id"]]))
                        return out[:3]
        return out

    @staticmethod
    def _expressed(intent: str, target: str | None, rt: "AgentRuntime", prefer_gesture: bool = True) -> list[Proposal]:
        """One EXPRESS for this intent, from the variants this body can show (or none)."""
        variants = {
            "greeting": ["greeting", "greeting_light"] if prefer_gesture else ["greeting_light", "greeting"],
            "listening": ["listening"],
            "acknowledge": ["acknowledge", "acknowledge_tilt"],
            "thank_you": ["thank_you", "thank_you_light"],
        }[intent]
        for expression_id in variants:
            if expression_id in rt.expressions:
                return [Proposal("EXPRESS", {"expression_id": expression_id, "target_id": target})]
        return []


class NpcTemplatePolicy:
    """C1 reactive templates for scripted NPCs: wave back, once per person, at someone who waves at
    them. Once per person, so two NPCs never wave at each other forever."""

    name = "TEMPLATE"

    def decide(self, rt: "AgentRuntime", triggers: list[str]) -> list[Proposal]:
        for item in rt.perceived.greetings:
            if item["track_id"] in rt.waved_back:
                continue
            for gesture in ("SMALL_WAVE", "WAVE"):
                if rt.body_supports_gesture(gesture):
                    rt.waved_back.add(item["track_id"])
                    return [Proposal("GESTURE", {"gesture": gesture, "target_id": item["track_id"]})]
        return []


class RoutinePolicy:
    """C0: the scripted routine. Scripted NPCs move by the scenario's event tape, so nothing here."""

    name = "ROUTINE"

    def decide(self, rt: "AgentRuntime", triggers: list[str]) -> list[Proposal]:
        if "START" in triggers and rt.task_goal is not None:
            return [Proposal("MOVE_TO", {"destination": rt.task_goal})]
        return []
