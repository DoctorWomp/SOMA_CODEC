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


# ---------- D-70 (owner 2026-11-19): raw heard speech is bounded ----------

def _heard(mem, who, text, at_ms):
    item = {"track_id": who, "event_id": f"ev_{at_ms}", "observed_at_ms": at_ms,
            "value": {"text": text, "channel": "LOCAL", "addressed_to_observer": True}}
    return mem.remember_heard(item, {"observations": []}, set())


def test_raw_heard_items_expire_ten_minutes_after_their_card_except_a_promise():
    from range_service.agents.memory import RAW_HEARD_RETENTION_MS, AgentMemory

    mem = AgentMemory("robot_r")
    a = _heard(mem, "anon_x", "Where is the demo?", 1000)
    b = _heard(mem, "anon_y", "Can you help me after this?", 2000)
    assert a is not None and b is not None and a["expires_at_ms"] is None
    mem.commit("help Y after this", "anon_y", now_ms=2500, ttl_ms=10**7)   # still open at the check
    done = mem.summarized({"anon_x", "anon_y"}, 0, now_ms=60_000)
    assert set(done) == {a["memory_id"], b["memory_id"]}
    mem.expire(60_000 + RAW_HEARD_RETENTION_MS - 1)
    assert a["status"] == "REPORTED" and b["status"] == "REPORTED"
    mem.expire(60_000 + RAW_HEARD_RETENTION_MS)
    assert a["status"] == "EXPIRED"                                  # summarized, nothing open: gone
    assert b["status"] == "REPORTED" and b["expires_at_ms"] is None  # Y still has an open promise: kept
    assert a not in mem.active(now_ms=10**9) and b in mem.active(now_ms=10**9)


def test_a_correction_is_never_expired_by_the_retention_window():
    from range_service.agents.memory import RAW_HEARD_RETENTION_MS, AgentMemory

    mem = AgentMemory("robot_r")
    old = _heard(mem, "anon_x", "My name is Sam.", 1000)
    new = mem.correct(old["memory_id"], "Actually my name is Sasha.", now_ms=2000, shared_by="anon_x")
    mem.summarized({"anon_x"}, 0, now_ms=3000)
    mem.expire(3000 + RAW_HEARD_RETENTION_MS + 1)
    assert new["status"] == "REPORTED" and new in mem.active(now_ms=10**9)


def test_raw_heard_items_are_capped_oldest_normal_first_promises_kept():
    from range_service.agents.memory import MAX_RAW_HEARD, AgentMemory

    mem = AgentMemory("robot_r")
    kept = _heard(mem, "anon_y", "Please help me later.", 0)
    mem.commit("help Y later", "anon_y", now_ms=1)
    items = [_heard(mem, "anon_x", f"Question {i}?", 10 + i) for i in range(MAX_RAW_HEARD + 5)]
    active = [i for i in mem.active(now_ms=10**6) if AgentMemory.is_raw_heard(i)]
    assert len(active) == MAX_RAW_HEARD
    assert kept in active                                            # tied to an open promise
    assert all(i["status"] == "EXPIRED" for i in items[:6]) and all(i in active for i in items[6:])
    assert sum(e["event"] == "RAW_HEARD_CAP" for e in mem.events) == 6
