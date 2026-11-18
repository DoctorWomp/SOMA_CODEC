"""G3d fix 2 (D-64): memory follows what the world accepted.

Before: a kept promise, the agent's own speech turn and a conversation start were written when
the request was sent, and a host rejection only released a newly made promise. Now each change is
staged by action_request_id and applied once, on acceptance; a rejection leaves memory as it was.
No Godot, no model.
"""

from __future__ import annotations

import asyncio
import copy

from range_service.agents.gateway import FakeModel, ModelGateway, ModelRequest, ModelResponse

from .agent_helpers import Scene, accept, refuse, robot
from .test_agent_runtime import step

X, Y = "anon_visitorxx01", "anon_visitoryy02"


def _snapshot(rt):
    return (copy.deepcopy(rt.memory.items), [(t.speaker, t.text) for t in rt.ws.turns], rt.conversation.partner,
            rt.conversation.last_exchange_ms)


def _promise_to_y(rt, s):
    """X is talking with Robot R; Y asks for help: the Demo policy promises Y to help later."""
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())
    return step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(Y, "Excuse me?", x=17, z=8.3).packet(), world_accepts=False)


def test_rejected_speech_leaves_no_turn_and_starts_no_conversation():
    rt = robot()
    s = Scene()
    before = _snapshot(rt)
    out = step(rt, s.see(X, 15, 8.5).hear(X, "Where is the cafe?").packet(), world_accepts=False)
    speak = next(r for r in out if r["action"] == "SPEAK")
    refuse(rt, speak, "PRIVACY_SCOPE_DENIED")
    after = _snapshot(rt)
    assert [t for t in after[1] if t[0] == "me"] == []                  # no own turn the world never heard
    assert after[0] == before[0] + [i for i in after[0] if i["store"] != "COMMITMENTS_AND_REFUSALS"][len(before[0]):]
    assert not [i for i in rt.memory.items if i["store"] == "COMMITMENTS_AND_REFUSALS"]


def test_rejected_new_promise_is_never_recorded():
    rt = robot()
    s = Scene()
    out = _promise_to_y(rt, s)
    promise = next(r for r in out if rt._sent[r["action_request_id"]]["commitment_id"])
    commitments_before = [i for i in rt.memory.items if i["store"] == "COMMITMENTS_AND_REFUSALS"]
    refuse(rt, promise, "TARGET_UNKNOWN")
    assert [i for i in rt.memory.items if i["store"] == "COMMITMENTS_AND_REFUSALS"] == commitments_before == []
    assert rt.activity is None or rt.activity.commitment_id is None


def test_rejected_promise_fulfilling_action_keeps_the_promise_open():
    rt = robot()
    s = Scene()
    accept(rt, _promise_to_y(rt, s))
    assert len(rt.memory.commitments_to(Y)) == 1
    step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(X, "Thanks, bye!").packet())
    out = step(rt, s.see(Y, 17, 8.3).packet(), world_accepts=False)    # COMMITMENT_DUE: "Thanks for waiting..."
    keeping = [r for r in out if r["action"] == "SPEAK"]
    assert keeping and rt._staged[keeping[0]["action_request_id"]].get("fulfill")
    for r in out:
        refuse(rt, r, "RATE_LIMITED")
    assert len(rt.memory.commitments_to(Y)) == 1                        # still open: the world never heard it kept
    out = step(rt, s.see(Y, 17, 8.3).hear(Y, "Hello? Can you help me now?", x=17, z=8.3).packet(), world_accepts=False)
    assert any(rt._staged.get(r["action_request_id"], {}).get("fulfill") for r in out)
    accept(rt, out)
    assert rt.memory.commitments_to(Y) == []                            # kept once it was accepted


def test_acceptance_after_the_next_decision_started_applies_once_and_shows_as_pending_meanwhile():
    gate = asyncio.Event()

    class Slow(FakeModel):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls.append(request)
            if len(self.calls) > 2:                                       # the third decision thinks
                await gate.wait()
            return ModelResponse(self.responder(request), "slow")

    model = Slow()
    rt = robot(gateway=ModelGateway(model))
    s = Scene()

    async def go():
        job = rt.observe(s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(X, "Tell me about the demo?").packet())
        first = await rt.decide(job)
        accept(rt, first)
        job = rt.observe(s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(Y, "Excuse me?", x=17, z=8.3).packet())
        promise = await rt.decide(job)                                    # sent; the world has not answered yet
        assert rt.memory.commitments_to(Y) == []
        nxt = rt.observe(s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(X, "And the robot arm?").packet())
        assert nxt is not None
        assert "Sent, not yet confirmed by the world" in nxt.assembled.prompt and "promise" in nxt.assembled.prompt
        task = asyncio.create_task(rt.decide(nxt))                        # the next decision has started
        await asyncio.sleep(0)
        accept(rt, promise)                                               # ... and now the acceptance arrives
        accept(rt, promise)                                               # a duplicate changes nothing
        gate.set()
        accept(rt, await task)
    asyncio.run(go())
    assert len(rt.memory.commitments_to(Y)) == 1                         # applied exactly once
    assert rt.pending_line() is None
