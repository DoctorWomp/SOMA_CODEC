"""The agent runtime (G3a, D-49): event-driven decisions, one pending request, the Demo policy's
behavior, commitments, T27 replans, and determinism. No Godot needed: packets are synthetic."""

from __future__ import annotations

import asyncio

from range_service import contracts
from range_service.agents.gateway import FakeModel, ModelGateway
from range_service.agents.runtime import AgentRuntime

from .agent_helpers import Scene, accept, robot, scenario_runtimes

X, Y = "anon_visitorxx01", "anon_visitoryy02"


def step(rt: AgentRuntime, packet: dict, world_accepts: bool = True) -> list[dict]:
    """One packet; the world accepts what the agent sends unless ``world_accepts`` is False."""
    job = rt.observe(packet)
    if job is None:
        return []
    out = asyncio.run(rt.decide(job)) if job.proposals is None else rt.decide_now(job)
    return accept(rt, out) if world_accepts else out


def test_synthetic_packets_match_the_observation_contract():
    s = Scene().see(X, 15, 8.5).hear(X, "Hello?").wave(Y, 17, 8.3).hear(None, "Anyone?", addressed=None)
    assert contracts.problems("observation", s.packet()) == []


def test_every_request_and_record_matches_its_contract():
    rt = robot()
    s = Scene()
    out = step(rt, s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    out += step(rt, s.see(X, 15, 8.5).wave(Y, 17, 8.3).see(Y, 17, 8.3).packet())
    assert out
    for request in out:
        assert contracts.problems("action_request", request) == []
    for record in rt.records:
        assert contracts.problems("decision_record", record) == []
    for item in rt.memory.items:
        assert contracts.problems("memory_item", item) == []


def test_decisions_are_event_driven_not_per_tick():
    rt = robot()
    s = Scene()
    step(rt, s.packet())                                 # START
    for _ in range(50):                                  # X stands there for 5 s; nothing new happens
        step(rt, s.see(X, 15, 8.5).packet())
    assert rt.stats["decisions"] == 2                    # START, and the first time X was near: not 51


def test_answers_questions_and_says_when_it_does_not_know():
    rt = robot()
    s = Scene()
    out = step(rt, s.see(X, 15, 8.5).hear(X, "Where is the cafe?").packet())
    speak = [r for r in out if r["action"] == "SPEAK"]
    assert speak and speak[0]["args"]["addressee_id"] == X
    assert "don't know" in speak[0]["args"]["text"]
    lights = [r for r in out if r["action"] == "EXPRESS"]
    assert lights and speak, "a light is always paired with words (D-14)"


def test_polite_bid_promise_is_kept_after_the_conversation():
    """SB-04 in miniature: R talks with X; Y waves; R acknowledges without interrupting X, then
    keeps its promise to Y once X says goodbye (D-13 commitments)."""
    rt = robot()
    s = Scene()
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())
    s.tick += 30                                                            # past the 1/3 s light limit
    out = step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).wave(Y, 17, 8.3).packet())
    assert [r["action"] for r in out] == ["EXPRESS"]                       # a nod, no words to Y while X talks
    assert out[0]["args"] == {"expression_id": "acknowledge", "target_id": Y}
    assert [c["audience_present"] for c in rt.memory.open_commitments()] == [[Y]]
    step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(X, "Thanks, bye!").packet())
    out = step(rt, s.see(Y, 17, 8.3).packet())
    speak = [r for r in out if r["action"] == "SPEAK"]
    assert speak and speak[0]["args"]["addressee_id"] == Y and "waiting" in speak[0]["args"]["text"]
    assert rt.memory.open_commitments() == []
    card = [i for i in rt.memory.items if i["store"] == "EPISODIC_LEDGER" and "card" in rt.memory.tags[i["memory_id"]]]
    assert card and X in card[0]["content"]["text"]


def test_a_light_too_soon_falls_back_to_its_gesture_and_keeps_the_promise():
    rt = robot()
    s = Scene()
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())      # shows "listening"
    out = step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).wave(Y, 17, 8.3).packet())  # 6 ticks later
    assert [(r["action"], r["args"]) for r in out] == [("GESTURE", {"gesture": "NOD", "target_id": Y})]
    assert rt.memory.commitments_to(Y)


def test_a_bid_while_busy_speaks_briefly_to_the_other_person():
    rt = robot()
    s = Scene()
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())
    out = step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(Y, "Excuse me?", x=17, z=8.3).packet())
    assert [r["action"] for r in out] == ["SPEAK"] and out[0]["args"]["addressee_id"] == Y
    assert rt.memory.commitments_to(Y)


def test_one_pending_request_per_agent_and_queued_triggers():
    gate = asyncio.Event()

    async def slow(_request):
        await gate.wait()
        return '{"actions": [{"action": "WAIT", "args": {"duration_ms": 500}}]}'

    class Blocking(FakeModel):
        async def complete(self, request):
            from range_service.agents.gateway import ModelResponse
            return ModelResponse(await slow(request), "blocking")

    rt = robot(gateway=ModelGateway(Blocking()))
    s = Scene()

    async def go():
        job = rt.observe(s.see(X, 15, 8.5).hear(X, "Hi?").packet())
        task = asyncio.create_task(rt.decide(job))
        await asyncio.sleep(0)
        assert rt.pending
        assert rt.observe(s.see(X, 15, 8.5).hear(X, "Hello??").packet()) is None   # no second request
        gate.set()
        await task
        assert not rt.pending
        nxt = rt.observe(s.see(X, 15, 8.5).packet())
        assert nxt is not None and "ADDRESSED_SPEECH" in nxt.triggers               # the queued event is kept
    asyncio.run(go())
    assert rt.stats["skipped_pending"] == 1


def test_t27_stale_action_is_replanned_once_from_the_latest_observation():
    rt = robot()
    s = Scene()
    out = step(rt, s.see(X, 15, 8.5).hear(X, "Where is the demo?").packet(), world_accepts=False)
    for request in out:
        rt.on_result({"schema_version": "1.0", "action_request_id": request["action_request_id"], "agent_id": "robot_r",
                      "accepted": False, "executed": False, "reason_code": "STALE_OBSERVATION",
                      "resulting_event_ids": [], "resolved_at_tick_id": s.tick})
    job = rt.observe(s.see(X, 15, 8.5).packet())
    assert job is not None and "ACTION_REJECTED" in job.triggers and job.tick > out[0]["based_on_tick_id"]
    assert rt.stats["replans"] == 1                        # one per rejected decision, never a loop


def test_a_rejected_promise_is_released():
    rt = robot()
    s = Scene()
    step(rt, s.see(X, 15, 8.5).hear(X, "Tell me about the demo?").packet())
    out = step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).hear(Y, "Excuse me?", x=17, z=8.3).packet(), world_accepts=False)
    rt.on_result({"schema_version": "1.0", "action_request_id": out[0]["action_request_id"], "agent_id": "robot_r",
                  "accepted": False, "executed": False, "reason_code": "TARGET_UNKNOWN", "resulting_event_ids": [],
                  "resolved_at_tick_id": s.tick})
    assert rt.memory.open_commitments() == []


def test_expressions_come_only_from_what_the_body_can_show():
    rt = robot(body="quadruped")
    assert "greeting" not in rt.expressions and "greeting_light" in rt.expressions
    s = Scene()
    out = step(rt, s.see(X, 15, 8.5).wave(X, 15, 8.5).packet())
    expressed = [r["args"]["expression_id"] for r in out if r["action"] == "EXPRESS"]
    assert expressed == ["greeting_light"]
    assert all(r["action"] != "GESTURE" or r["args"]["gesture"] in ("HEAD_TILT", "SIT_IN_PLACE") for r in out)


def test_fake_model_path_gives_the_same_actions_as_the_demo_policy():
    demo, model = robot(), robot(gateway=ModelGateway(FakeModel()))
    a, b = Scene(), Scene()
    for scene in (a, b):
        scene.see(X, 15, 8.5).hear(X, "Where is the demo?", event_id="evt_q1")
    out_demo = step(demo, a.packet())
    out_model = step(model, b.packet())
    assert [(r["action"], r["args"]) for r in out_demo] == [(r["action"], r["args"]) for r in out_model]
    assert model.records[-1]["policy"] == "MODEL" and model.records[-1]["model_calls"][0]["outcome"] == "VALID"


def test_runtime_is_deterministic():
    def run_once():
        rt = robot()
        s = Scene()
        out = []
        out += step(rt, s.see(X, 15, 8.5).hear(X, "Where is the demo?", event_id="evt_1").packet())
        out += step(rt, s.see(X, 15, 8.5).see(Y, 17, 8.3).wave(Y, 17, 8.3, event_id="evt_2").packet())
        out += step(rt, s.see(X, 15, 8.5).hear(X, "Bye!", event_id="evt_3").packet())
        out += step(rt, s.see(Y, 17, 8.3).packet())
        return out, [r["context"]["prompt_sha256"] for r in rt.records if r["context"]]
    assert run_once() == run_once()


def test_sb05_robots_walk_to_their_task_goals_and_nothing_else():
    runtimes = scenario_runtimes("SB05_RAMP_VS_STAIRS")
    for agent_id, rt in runtimes.items():
        out = step(rt, Scene(observer=agent_id).packet())
        assert [r["action"] for r in out] == ["MOVE_TO"]
        assert out[0]["args"]["destination"] == rt.task_goal


def test_npcs_wave_back_once_per_person():
    runtimes = scenario_runtimes("SB04_POLITE_BID")
    npc = runtimes["visitor_x"]
    s = Scene(observer="visitor_x")
    step(npc, s.packet())
    out = step(npc, s.see("anon_robotrrr01", 15, 10).hear("anon_robotrrr01", "Hello!", z=10).packet())  # promoted to C1
    out = step(npc, s.see("anon_robotrrr01", 15, 10).wave("anon_robotrrr01", 15, 10, "WAVE").packet())
    assert [r["action"] for r in out] == ["GESTURE"]
    out = step(npc, s.see("anon_robotrrr01", 15, 10).wave("anon_robotrrr01", 15, 10, "WAVE").packet())
    assert out == []
