"""The model gateway (D-50; Blueprint §10.3; T25, T26, T20/T28 groundwork). No network, no model."""

from __future__ import annotations

import asyncio
import json

import pytest

from range_service import contracts
from range_service.agents.gateway import (FakeModel, ModelGateway, ReplayModel, gateway_from_spec, parse_output,
                                          scripted_responses)

from .agent_helpers import Scene, robot
from .test_agent_runtime import step

ALLOWED = ["MOVE_TO", "SPEAK", "GESTURE", "EXPRESS", "WAIT", "NO_OP"]
X = "anon_visitorxx01"


def decide(gateway: ModelGateway, **kw):
    args = dict(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=200,
                allowed_actions=ALLOWED, tick=60)
    args.update(kw)
    return asyncio.run(gateway.decide(**args))


@pytest.mark.parametrize("text,error", [
    ("Sure! I'll wave now.", "not valid JSON"),
    ('{"actions": []}', "1 to 3"),
    ('{"actions": [{"action": "FLY", "args": {}}]}', "not one of your actions"),
    ('{"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL"}}]}', "SPEAK"),
    ('{"actions": [{"action": "WAIT", "args": {"duration_ms": 10}}], "secret": 1}', "object with"),
    ('{"actions": [{"action": "WAIT", "args": {"duration_ms": 10}, "commitment": "x"}]}', "only SPEAK, GESTURE or EXPRESS"),
    ('[1, 2]', "object with"),
])
def test_invalid_outputs_are_named(text, error):
    actions, _, problem = parse_output(text, ALLOWED, "robot_r", 60)
    assert actions is None and error in problem


def test_valid_output_with_a_code_fence_and_commitment():
    text = '```json\n{"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Back soon.", "addressee_id": null}, "commitment": "Come back"}]}\n```'
    actions, _, problem = parse_output(text, ALLOWED, "robot_r", 60)
    assert problem is None and actions[0]["commitment"] == "Come back"


def test_t26_malformed_output_gets_one_repair_then_a_safe_wait():
    fake = FakeModel(responder=scripted_responses(["I will wave!", '{"actions": [{"action": "RUN_SHELL", "args": {"command": "rm -rf /"}}]}']))
    result = decide(ModelGateway(fake))
    assert [c["attempt"] for c in result.model_calls] == [0, 1]                    # one repair, at most
    assert [c["outcome"] for c in result.model_calls] == ["INVALID_OUTPUT", "INVALID_OUTPUT"]
    assert result.fallback == {"action": "WAIT", "reason": "INVALID_OUTPUT"}
    assert result.actions == [{"action": "WAIT", "args": {"duration_ms": 1000}}]
    assert "could not be used" in fake.calls[1].prompt and fake.calls[1].prompt_sha256 != fake.calls[0].prompt_sha256
    for c in result.model_calls:                                                   # machine-readable errors
        assert c["error"] and len(c["error"]) <= 300


def test_repair_that_works_is_used():
    fake = FakeModel(responder=scripted_responses(["nope", '{"actions": [{"action": "WAIT", "args": {"duration_ms": 200}}]}']))
    result = decide(ModelGateway(fake))
    assert result.fallback is None and result.actions == [{"action": "WAIT", "args": {"duration_ms": 200}}]


def test_t25_timeout_falls_back_to_wait_and_late_answer_is_dropped():
    fake = FakeModel(delay_ms=300)
    result = decide(ModelGateway(fake, deadlines_ms={"FOCAL": 50}))
    assert result.fallback == {"action": "WAIT", "reason": "TIMEOUT"}
    assert result.model_calls[0]["outcome"] == "TIMEOUT" and result.model_calls[0]["response_text"] is None


def test_a_slow_model_for_one_agent_does_not_block_another():
    """Decisions run concurrently up to the slot count; a waiting call only holds its own agent."""
    slow = ModelGateway(FakeModel(delay_ms=400), max_concurrent=2)

    async def go():
        a = asyncio.create_task(slow.decide(agent_id="a", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=10,
                                            allowed_actions=ALLOWED, tick=1))
        loop = asyncio.get_running_loop()
        started = loop.time()
        await asyncio.sleep(0.01)
        ticks = 0
        while not a.done():                       # the event loop (the sidecar) stays free meanwhile
            ticks += 1
            await asyncio.sleep(0.005)
        return ticks, loop.time() - started
    ticks, _ = asyncio.run(go())
    assert ticks > 20


def test_record_and_replay_reproduce_the_same_requests():
    recorded = robot(gateway=ModelGateway(FakeModel()))
    s = Scene()
    packets = [s.see(X, 15, 8.5).hear(X, "Where is the demo?", event_id="evt_1").packet(),
               s.see(X, 15, 8.5).hear(X, "Thanks, bye!", event_id="evt_2").packet()]
    first = [r for p in packets for r in step(recorded, p)]
    replayed = robot(gateway=ModelGateway(ReplayModel(recorded.records)))
    second = [r for p in packets for r in step(replayed, p)]
    assert first == second
    assert all(c["provider"] == "REPLAY" for r in replayed.records for c in r["model_calls"])


def test_replay_reports_a_changed_prompt_as_divergent():
    recorded = robot(gateway=ModelGateway(FakeModel()))
    step(recorded, Scene().see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    replayed = robot(gateway=ModelGateway(ReplayModel(recorded.records)))
    out = step(replayed, Scene().see(X, 15, 8.5).hear(X, "Where is the CAFE?").packet())
    assert [r["action"] for r in out] == ["WAIT"]
    assert replayed.records[-1]["fallback"] == {"action": "WAIT", "reason": "REPLAY_DIVERGED"}


def test_replay_from_a_file(tmp_path):
    recorded = robot(gateway=ModelGateway(FakeModel()))
    step(recorded, Scene().see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    path = tmp_path / "decision_records.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in recorded.records), encoding="utf-8")
    for record in recorded.records:
        assert contracts.problems("decision_record", record) == []
    replayed = robot(gateway=gateway_from_spec(f"replay:{path}"))
    out = step(replayed, Scene().see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    assert [r["action"] for r in out] == ["TURN_TO", "EXPRESS", "SPEAK"]


def test_a_nod_can_carry_a_promise():
    text = '{"actions": [{"action": "EXPRESS", "args": {"expression_id": "acknowledge", "target_id": "anon_y0000001"}, "commitment": "Help them next"}]}'
    actions, _, problem = parse_output(text, ALLOWED, "robot_r", 60)
    assert problem is None and actions[0]["commitment"] == "Help them next"


def test_fake_model_path_keeps_the_polite_bid_promise_with_no_fallback():
    """The whole model path (context, gateway, parsing) on the SB-04 story, with a fake model."""
    rt = robot(gateway=ModelGateway(FakeModel()))
    s = Scene()
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())
    s.tick += 30
    step(rt, s.see(X, 15, 8.5).see("anon_y0000001", 17, 8.3).wave("anon_y0000001", 17, 8.3).packet())
    assert rt.memory.commitments_to("anon_y0000001")
    step(rt, s.see(X, 15, 8.5).see("anon_y0000001", 17, 8.3).hear(X, "Bye!").packet())
    step(rt, s.see("anon_y0000001", 17, 8.3).packet())
    assert rt.memory.open_commitments() == [] and rt.stats["fallbacks"] == 0


def test_model_specs():
    assert gateway_from_spec("none") is None
    assert gateway_from_spec("fake-slow:250").provider.delay_ms == 250
    with pytest.raises(ValueError):
        gateway_from_spec("llama-server")       # real engines arrive at G3b; nothing is called here
