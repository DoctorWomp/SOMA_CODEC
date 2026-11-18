"""G3e (D-73, D-74): the ambient state display and the presence dial, Python side. No Godot, no model.

The ambient display shows the agent's own state with no model call: one gated EXPRESS per change of
state, a chosen EXPRESS overrides it for its hold time, a refused change is asked again later, and
models are never offered ambient expressions.
"""

from __future__ import annotations

import asyncio

import pytest

from range_service import expressions as expression_rules
from range_service.agents import presence_dial
from range_service.agents.factory import build_runtimes, public_persona
from range_service.agents.gateway import FakeModel, ModelGateway, ModelRequest, ModelResponse
from range_service.agents.runtime import EXPRESSION_MIN_GAP_TICKS, AgentRuntime

from .agent_helpers import CONFIGS, Scene, accept, refuse

CATALOG = CONFIGS.items["expressions"]
PULSE = CONFIGS.items["pulse"]["pulse"]
P, Q = "anon_pppppppppp", "anon_qqqqqqqqqq"


def robot(gateway=None, body_id="wheeled_humanoid") -> AgentRuntime:
    body = CONFIGS.items["bodies"][body_id]
    return AgentRuntime("robot_r", persona=public_persona(CONFIGS.items["personas"]["robot_r"]), body=body,
                        directive="Help visitors.", expressions=expression_rules.available(body, CATALOG),
                        setting=[], task="Help visitors.", focal=True, controller="LLM_AGENT", gateway=gateway,
                        pulse=PULSE, seed=7, post={"x": 15.0, "z": 10.0}, post_duty=True,
                        survey_area={"x_min": 0.0, "x_max": 30.0, "z_min": 0.0, "z_max": 20.0},
                        ambient=expression_rules.ambient_for(body, CATALOG),
                        expression_holds={eid: e["hold_ms"] for eid, e in CATALOG.items()})


def _ambient_sent(out):
    return [r["args"]["expression_id"] for r in out if r["action"] == "EXPRESS" and r["args"]["expression_id"].startswith("ambient_")]


def step(rt, packet, world_accepts=True):
    job = rt.observe(packet)
    out = rt.take_presence()
    if job is not None:
        out += asyncio.run(rt.decide(job)) if job.proposals is None else rt.decide_now(job)
    if world_accepts:
        accept(rt, out)
    return out


def test_models_never_see_ambient_expressions():
    rt = robot()
    assert not any(e.startswith("ambient_") for e in rt.expressions)          # the model-facing list
    assert set(rt.ambient.by_state) == {"WAITING", "THINKING", "CONSIDERING", "LISTENING", "ATTENDING"}
    assert rt.presence.idle_expression is None                                 # the ambient display replaces it


def test_the_display_yields_to_a_decision_made_from_the_same_packet():
    rt = robot()
    s = Scene()
    first = step(rt, s.packet())                            # START decides from this packet
    assert _ambient_sent(first) == [] and _ambient_sent(step(rt, s.packet())) == ["ambient_attending"]


def test_one_gated_change_per_state_change_and_nothing_while_it_holds():
    rt = robot()
    s = Scene()
    sent = []
    for _ in range(10):
        sent += _ambient_sent(step(rt, s.packet()))
    assert sent == ["ambient_attending"]                                         # once, not every packet
    s.tick += EXPRESSION_MIN_GAP_TICKS
    sent = []
    for _ in range(3):
        sent += _ambient_sent(step(rt, s.see(P, 15, 8.5).hear(P, "Hello! Where is the demo?").packet()))
    for _ in range(12):                                     # past its own answer (no listening while speaking)
        sent += _ambient_sent(step(rt, s.see(P, 15, 8.5).packet(advance=60)))
    assert "ambient_listening" in sent and sent.count("ambient_listening") == 1    # the state changed: one change


def test_gated_changes_respect_the_light_change_limit():
    rt = robot()
    s = Scene()
    ticks = []
    for i in range(40):
        p = s.see(P, 15, 8.5).hear(P, "Hi?") if i % 2 else s.see(P, 15, 8.5)
        out = step(rt, p.packet(advance=1))
        ticks += [r["based_on_tick_id"] for r in out if r["action"] == "EXPRESS"]
    assert all(b - a >= EXPRESSION_MIN_GAP_TICKS for a, b in zip(ticks, ticks[1:]))


def test_waiting_for_a_promise_shows_waiting():
    rt = robot()
    rt.activity = None
    s = Scene()
    step(rt, s.packet())
    from range_service.agents.activity import Activity
    rt.activity = Activity("WAIT_FOR", P, None, 120, [{"addressed": True}], "DERIVED", s.ms)
    s.tick += EXPRESSION_MIN_GAP_TICKS
    assert rt.ambient_state() == "WAITING"
    assert _ambient_sent(step(rt, s.see(P, 20, 15).packet())) == ["ambient_waiting"]


def test_thinking_while_a_model_call_is_in_flight():
    gate = asyncio.Event()

    class Slow(FakeModel):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls.append(request)
            if len(self.calls) > 1:
                await gate.wait()
            return ModelResponse(self.responder(request), "slow")

    rt = robot(ModelGateway(Slow()))
    s = Scene()

    async def go():
        job = rt.observe(s.packet())
        accept(rt, rt.take_presence() + await rt.decide(job))
        s.tick += EXPRESSION_MIN_GAP_TICKS
        job = rt.observe(s.see(P, 15, 8.5).hear(P, "Where is the cafe?").packet())
        accept(rt, rt.take_presence())
        task = asyncio.create_task(rt.decide(job))
        await asyncio.sleep(0)
        s.tick += EXPRESSION_MIN_GAP_TICKS
        assert rt.observe(s.see(P, 15, 8.5).packet()) is None
        during = _ambient_sent(rt.take_presence())
        gate.set()
        accept(rt, await task)
        return during
    assert asyncio.run(go()) == ["ambient_thinking"]


def test_a_chosen_expression_overrides_for_its_hold_then_the_display_returns():
    rt = robot()
    s = Scene()
    step(rt, s.packet())                                    # START
    step(rt, s.packet())
    assert rt.ambient.shown == "ambient_attending"
    s.tick += EXPRESSION_MIN_GAP_TICKS
    out = step(rt, s.see(P, 15, 8.5).wave(P, 15, 8.5).packet())               # the Demo policy greets: EXPRESS greeting
    chosen = [r["args"]["expression_id"] for r in out if r["action"] == "EXPRESS" and not r["args"]["expression_id"].startswith("ambient_")]
    assert chosen and rt.ambient.override_until_ms > s.ms and rt.ambient.shown is None
    held = []
    for _ in range(int(CATALOG[chosen[0]]["hold_ms"] / 100) - 2):
        held += _ambient_sent(step(rt, s.see(P, 15, 8.5).packet()))
    assert held == []                                                            # not during the chosen expression's hold
    after = []
    for _ in range(20):
        after += _ambient_sent(step(rt, s.see(P, 15, 8.5).packet()))
    assert len(after) == 1                                                       # then the display comes back, once


def test_a_refused_change_is_asked_again_later_not_every_packet():
    rt = robot()
    s = Scene()
    step(rt, s.packet())                                    # START: a decision, so the display waits a packet
    out = step(rt, s.packet(), world_accepts=False)
    (req,) = [r for r in out if r["action"] == "EXPRESS"]
    refuse(rt, req, "RATE_LIMITED")
    soon = []
    for _ in range(5):
        s.tick += 1
        soon += _ambient_sent(step(rt, s.packet(advance=1), world_accepts=False))
    assert soon == []                                                            # not hammering the gate
    s.tick += 60
    assert _ambient_sent(step(rt, s.packet())) == ["ambient_attending"]


def test_people_get_no_ambient_display():
    rts = build_runtimes(CONFIGS.items["scenarios"]["SB06_LONG_WAIT"], CONFIGS, pulse=PULSE)
    assert rts["robot_r"].ambient is not None
    assert rts["visitor_y"].ambient is None and rts["visitor_z"].ambient is None


# ---------- the presence dial (D-74) ----------

def test_dial_baseline_comes_from_directive_then_persona_then_default():
    directives = CONFIGS.items["directives"]
    entry = CONFIGS.items["scenarios"]["SB06_LONG_WAIT"]["cast"]["robot_r"]
    persona = dict(CONFIGS.items["personas"]["robot_r"])
    assert presence_dial.baseline(entry, persona, directives, PULSE) == PULSE["presence"]["amplitude"]["default"]
    assert presence_dial.baseline(entry, dict(persona, presence_amplitude=0.3), directives, PULSE) == 0.3
    d = {k: dict(v) for k, v in directives.items()}
    d[entry["directive"]]["presence_amplitude"] = 0.8
    assert presence_dial.baseline(entry, dict(persona, presence_amplitude=0.3), d, PULSE) == 0.8
    assert presence_dial.adapt(0.4) == 0.4                                       # G5 hook: unchanged today


def test_dial_presets_and_validation():
    assert presence_dial.resolve("subtle", PULSE) < presence_dial.resolve("default", PULSE) < presence_dial.resolve("performative", PULSE)
    assert presence_dial.resolve("0.35", PULSE) == 0.35 and presence_dial.resolve(None, PULSE) is None
    for bad in ("loud", "1.5", "-0.1"):
        with pytest.raises(ValueError):
            presence_dial.resolve(bad, PULSE)
    from range_service import contracts
    zone = dict(CONFIGS.items["maps"]["sandbox_flats"]["zones"][0], presence_amplitude=1.2)
    game_map = dict(CONFIGS.items["maps"]["sandbox_flats"], zones=[zone])
    assert contracts.problems("map", game_map)                                   # out of range is refused
    assert not contracts.problems("map", dict(game_map, zones=[dict(zone, presence_amplitude=0.1)]))
