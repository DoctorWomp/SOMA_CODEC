"""The ambient state display (G3e, D-73; EXPRESSION_PRINCIPLES §9; FIELD_NOTES FN-5).

Between model decisions a robot shows what it is doing, deterministically, from its own state:
waiting, thinking, considering, listening or attending (``AgentRuntime.ambient_state``). Each state
has one catalog entry (``configs/expressions/ambient_*.yaml``) with a short glyph loop; the world
sees **one** gated expression change per change of state (through the action gate, with its 1/3 s
light-change limit), and the frames are rendering only. A chosen EXPRESS (the model's or the Demo
policy's) overrides the display for its hold time; then the display comes back.

This class only keeps track of what was asked and what the world accepted. It never calls a model
and never reads anything but the agent's own state.
"""

from __future__ import annotations

RETRY_MS = 1000          # a refused or unanswered change is asked again after this long


class AmbientDisplay:
    def __init__(self, by_state: dict[str, str], holds: dict[str, int]) -> None:
        self.by_state = dict(by_state)          # state -> expression id this body can show
        self.holds = dict(holds)                # expression id -> hold_ms (for overrides)
        self.shown: str | None = None           # the ambient expression the world last accepted
        self._sent: tuple[str, int] | None = None
        self.override_until_ms = -1
        self.changes = 0                        # accepted ambient changes (evaluator)

    def want(self, state: str, now_ms: int) -> str | None:
        """The expression to ask for now, or None (nothing to change, an override showing, or a
        request for it still unanswered)."""
        eid = self.by_state.get(state)
        if eid is None or now_ms < self.override_until_ms or eid == self.shown:
            return None
        if self._sent is not None and self._sent[0] == eid and now_ms - self._sent[1] < RETRY_MS:
            return None
        return eid

    def sent(self, eid: str, now_ms: int) -> None:
        self._sent = (eid, now_ms)

    def result(self, eid: str, accepted: bool) -> None:
        if self._sent is not None and self._sent[0] == eid:
            self._sent = None
        if accepted:
            self.shown = eid
            self.changes += 1

    def override(self, expression_id: str | None, now_ms: int) -> None:
        """A chosen expression replaced the display: hold off for its hold time, then show the state again."""
        if expression_id is None or expression_id in self.by_state.values():
            return
        self.override_until_ms = now_ms + int(self.holds.get(expression_id, 0))
        self.shown = None
