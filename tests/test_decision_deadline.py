"""G3d fix 1 (D-63): one deadline per decision, and a relevance check before an answer is sent.

Reproduces the review finding: the repair attempt used to get a fresh tier deadline, so a FOCAL
decision could take ~8 s against the world's 6.5 s stale window. No Godot, no model.
"""

from __future__ import annotations

import asyncio
import time

from range_service.agents.gateway import (FakeModel, ModelGateway, ModelRequest, ModelResponse,
                                          scripted_responses)
from range_service.agents.runtime import AgentRuntime

from .agent_helpers import Scene, robot

ALLOWED = ["MOVE_TO", "SPEAK", "GESTURE", "EXPRESS", "WAIT", "NO_OP", "LOOK_AT", "TURN_TO"]
X, Y = "anon_visitorxx01", "anon_visitoryy02"
INVALID = "not json at all"
VALID_WAIT = '{"actions": [{"action": "WAIT", "args": {"duration_ms": 200}}]}'


def _decide(gateway: ModelGateway, **kw):
    args = dict(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=200,
                allowed_actions=ALLOWED, tick=60)
    args.update(kw)
    return asyncio.run(gateway.decide(**args))


# ---------- the gateway: one deadline covers queue, generation and repair ----------

def test_repair_never_gets_a_fresh_deadline():
    """An invalid first answer near the deadline: no repair, WAIT, and the whole decision ends in time."""
    fake = FakeModel(responder=scripted_responses([INVALID, VALID_WAIT]), delay_ms=300)
    started = time.monotonic()
    result = _decide(ModelGateway(fake, deadlines_ms={"FOCAL": 500}))
    took_ms = (time.monotonic() - started) * 1000
    assert took_ms < 500 + 50, took_ms                                  # was ~600 ms (300 + a fresh repair)
    assert len(fake.calls) == 1                                          # no repair without time for it
    assert result.fallback == {"action": "WAIT", "reason": "INVALID_OUTPUT"}
    assert "not repaired" in result.model_calls[0]["error"]
    assert result.model_calls[0]["deadline_ms"] == 500


def test_repair_uses_only_the_time_that_is_left():
    fake = FakeModel(responder=scripted_responses([INVALID, VALID_WAIT]), delay_ms=200)
    result = _decide(ModelGateway(fake, deadlines_ms={"FOCAL": 2000}))
    assert result.fallback is None and result.actions[0]["action"] == "WAIT"
    first, repair = result.model_calls
    assert first["deadline_ms"] == 2000
    assert repair["deadline_ms"] <= 2000 - 200 + 20                      # what was left, never a fresh 2000
    assert first["timings"]["total_ms"] + repair["timings"]["total_ms"] <= 2000


def test_a_repair_that_would_run_past_the_deadline_times_out_within_it():
    """Enough time for a repair by the estimate, but the repair is slower: it is cut at the decision deadline."""
    class Slower(FakeModel):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls.append(request)
            await asyncio.sleep(0.05 if request.attempt == 0 else 2.0)
            return ModelResponse(INVALID if request.attempt == 0 else VALID_WAIT, "slower")
    started = time.monotonic()
    result = _decide(ModelGateway(Slower(), deadlines_ms={"FOCAL": 800}))
    assert (time.monotonic() - started) * 1000 < 800 + 60
    assert result.fallback == {"action": "WAIT", "reason": "TIMEOUT"}
    assert result.model_calls[1]["deadline_ms"] < 800


def test_the_runtime_passes_its_decision_deadline_to_the_gateway():
    """The clock starts when the decision starts (queue included), not per call."""
    fake = FakeModel(responder=scripted_responses([INVALID, VALID_WAIT]), delay_ms=50)
    gw = ModelGateway(fake, deadlines_ms={"FOCAL": 4000})
    rt = robot(gateway=gw)
    job = rt.observe(Scene().see(X, 15, 8.5).hear(X, "Hello?").packet())
    asyncio.run(rt.decide(job))
    calls = rt.records[-1]["model_calls"]
    assert calls[0]["deadline_ms"] <= 4000 and calls[1]["deadline_ms"] < calls[0]["deadline_ms"]



# ---------- before sending: is the answer still relevant? Traced observation -> queue -> answer -> host ----------

class Gated(FakeModel):
    """A model that thinks until the test lets it answer (so the world can change meanwhile)."""

    def __init__(self, texts: list[str] | None = None) -> None:
        super().__init__(responder=scripted_responses(texts) if texts else None)
        self.go = asyncio.Event()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        await self.go.wait()
        return ModelResponse(self.responder(request), "gated")


def _think_while(rt: AgentRuntime, model: Gated, first: dict, during: list[dict]) -> tuple[list[dict], list[dict]]:
    """Observation ``first`` starts a decision; ``during`` arrive while the model thinks; then the
    answer comes and is rechecked just before sending. Returns (answered, sent)."""
    async def go():
        job = rt.observe(first)
        assert job is not None and job.policy == "MODEL"
        task = asyncio.create_task(rt.decide(job))
        await asyncio.sleep(0)
        for packet in during:
            assert rt.observe(packet) is None                      # one pending decision; events are queued
        model.go.set()
        answered = await task
        return answered, rt.recheck(answered, live=True)
    return asyncio.run(go())


def _result(rt, request, accepted=True, reason="OK"):
    rt.on_result({"schema_version": "1.0", "action_request_id": request["action_request_id"], "agent_id": rt.agent_id,
                  "accepted": accepted, "executed": accepted, "reason_code": reason, "resulting_event_ids": [],
                  "resolved_at_tick_id": request["based_on_tick_id"] + 6})


def _my_turns(rt):
    return [t for t in rt.ws.turns if t.speaker == "me"]


def test_still_relevant_the_answer_is_sent_and_applied_once():
    model = Gated()
    rt = robot(gateway=ModelGateway(model))
    s = Scene()
    answered, sent = _think_while(rt, model, s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet(),
                                  [s.see(X, 15, 8.5).packet()])
    assert sent == answered and any(r["action"] == "SPEAK" for r in sent)
    assert _my_turns(rt) == []                                       # nothing applied before the host accepts
    speak = next(r for r in sent if r["action"] == "SPEAK")
    _result(rt, speak)
    _result(rt, speak)                                               # a duplicate result changes nothing
    assert len(_my_turns(rt)) == 1 and rt.conversation.partner == X
    assert rt.delivery_log == []


def test_target_leaves_while_the_model_thinks():
    model = Gated()
    rt = robot(gateway=ModelGateway(model))
    s = Scene()
    answered, sent = _think_while(rt, model, s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet(),
                                  [s.packet(), s.packet()])         # X no longer perceived
    assert any(r["action"] == "SPEAK" for r in answered)
    assert not any(r["action"] == "SPEAK" for r in sent)            # dropped before sending
    dropped = [e for e in rt.delivery_log if e["event"] == "DISCARDED"]
    assert dropped and {e["reason"] for e in dropped} == {"TARGET_NOT_PERCEIVED"}
    assert _my_turns(rt) == [] and rt.conversation.partner is None   # memory as it was
    job = rt.observe(s.packet())
    assert job is not None and "ACTION_REJECTED" in job.triggers     # the single replan
    assert rt.stats["replans"] == 1


def test_a_new_speaker_takes_over_while_the_model_thinks():
    model = Gated()
    rt = robot(gateway=ModelGateway(model))
    s = Scene()
    answered, sent = _think_while(rt, model, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(X, "Where is the demo?").packet(),
                                  [s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(Y, "Excuse me, is this the cafe?", x=17, z=8.3).packet()])
    assert not any(r["action"] == "SPEAK" for r in sent)
    assert {e["reason"] for e in rt.delivery_log if e["event"] == "DISCARDED"} == {"SOMEONE_ELSE_ADDRESSING"}
    job = rt.observe(s.see(X, 15, 8.5).see(Y, 17, 8.3).packet())
    assert job is not None and "ADDRESSED_SPEECH" in job.triggers and Y in job.sources   # Y's question is decided next


def test_an_invalid_first_answer_near_the_deadline_is_a_wait_traced_to_the_host():
    fake = FakeModel(responder=scripted_responses([INVALID, VALID_WAIT]), delay_ms=430)
    rt = robot(gateway=ModelGateway(fake, deadlines_ms={"FOCAL": 500}))
    s = Scene()
    job = rt.observe(s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    started = time.monotonic()
    answered = asyncio.run(rt.decide(job))
    assert (time.monotonic() - started) * 1000 < 560
    record = rt.records[-1]
    assert record["fallback"] == {"action": "WAIT", "reason": "INVALID_OUTPUT"} and len(record["model_calls"]) == 1
    sent = rt.recheck(answered, live=True)
    assert [r["action"] for r in sent] == ["WAIT"]
    _result(rt, sent[0])
    assert rt.results[sent[0]["action_request_id"]]["accepted"]


def test_a_model_answer_sent_after_its_decision_deadline_is_dropped():
    rt = robot(gateway=ModelGateway(FakeModel(), deadlines_ms={"FOCAL": 100}))
    s = Scene()
    job = rt.observe(s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    answered = asyncio.run(rt.decide(job))
    job.started_at -= 1.0                                           # as if it had taken a second to get here
    for info in rt._sent.values():
        info["started_at"] -= 1.0
    assert rt.recheck(answered, live=True) == []
    assert {e["reason"] for e in rt.delivery_log} == {"DECISION_DEADLINE_PASSED"}
    assert rt.recheck([], live=False) == []


def test_the_world_stale_window_is_derived_from_the_longest_decision_deadline():
    """D-63: STALE_AFTER_TICKS = longest total decision deadline + the delivery margin, in ticks.
    Since a repair can no longer extend a decision, no accepted answer can be older than this."""
    import math
    import re

    from range_service.agents.inference import load_inference
    from range_service.agents.runtime import DELIVERY_MARGIN_MS, SEND_GRACE_MS
    from range_service.contracts import REPO_ROOT

    gate = (REPO_ROOT / "godot_app" / "scripts" / "comms" / "action_gate.gd").read_text(encoding="utf-8")
    ticks = int(re.search(r"const STALE_AFTER_TICKS := (\d+)", gate).group(1))
    longest = max(t["deadline_ms"] for t in load_inference()["tiers"].values())
    assert ticks == math.ceil((longest + DELIVERY_MARGIN_MS) * 60 / 1000)
    assert SEND_GRACE_MS < DELIVERY_MARGIN_MS                     # the rest covers the link and one world tick
