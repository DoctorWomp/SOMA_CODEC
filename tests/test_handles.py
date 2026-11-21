"""G3h: short, observer-local handles for people (D-111) and LEAN's argument defaults (D-112).
No Godot, no real model."""

from __future__ import annotations

import asyncio
import json

from range_service import contracts
from range_service.agents import lean
from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import FakeModel, ModelGateway
from range_service.agents.handles import TRACK, HandleMap
from range_service.agents.output_schema import answer_schema
from tests.agent_helpers import CONFIGS, Scene

SB04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
PULSE = CONFIGS.items["pulse"]["pulse"]
X, Y, Z = "anon_xxxxxxxxx1", "anon_yyyyyyyyy2", "anon_zzzzzzzzz3"


def test_handles_map_both_ways_in_order_of_first_appearance_and_are_never_reused():
    hm = HandleMap()
    assert hm.rename(f"- {Y}: OBSERVED; - {X}: OBSERVED; {Y} speaks") == "- P1: OBSERVED; - P2: OBSERVED; P1 speaks"
    assert hm.track("P1") == Y and hm.track("P2") == X and hm.handle(X) == "P2"
    assert hm.handle(Z) == "P3"                                  # a new track: a new handle
    assert hm.handle(Y) == "P1"                                  # stable while it lives, and after
    assert len(set(hm.snapshot())) == len(set(hm.snapshot().values())) == 3
    text, error = hm.answer_to_ids(json.dumps({"actions": [
        {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi P1", "addressee_id": "P1"}},
        {"action": "LOOK_AT", "args": {"target_id": "P3"}}], "activity": {"kind": "CONVERSE", "target_id": "P2"}}))
    data = json.loads(text)
    assert error is None
    assert data["actions"][0]["args"]["addressee_id"] == Y and data["actions"][1]["args"]["target_id"] == Z
    assert data["actions"][0]["args"]["text"] == "Hi P1"         # words are the model's own: not rewritten
    assert data["activity"]["target_id"] == X


def test_an_unknown_handle_is_refused_like_an_unknown_target():
    hm = HandleMap()
    hm.handle(X)
    _, error = hm.answer_to_ids(json.dumps({"actions": [{"action": "LOOK_AT", "args": {"target_id": "P7"}}]}))
    assert error == "action 1: target_id P7 is not a track you perceive"
    # In the activity it is left for the activity check, which drops the activity alone (D-110).
    text, error = hm.answer_to_ids(json.dumps({"actions": [{"action": "WAIT", "args": {"duration_ms": 1}}],
                                               "activity": {"kind": "CONVERSE", "target_id": "P7"}}))
    assert error is None and json.loads(text)["activity"]["target_id"] == "P7"


def _robot_lean(answer=None):
    gw = ModelGateway(FakeModel(responder=(lambda r: answer) if answer else None))
    gw.answer = "LEAN"
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    return rts["robot_r"], gw


def test_robot_r_under_lean_sees_handles_and_its_requests_carry_anonymous_ids():
    r, gw = _robot_lean()
    scene = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    job = r.observe(scene.see(X, 15, 8.5).see(Y, 17, 9).hear(X, "Where is the demo?").packet())
    requests = asyncio.run(r.decide(job))
    call = gw.provider.calls[0]
    assert not TRACK.search(call.prompt)                              # no anonymous id in what the model sees
    assert "P1" in call.prompt and "P2" in call.prompt
    assert "anon_" not in json.dumps(call.output_schema)            # the choices name handles
    assert not TRACK.search(call.demo_hint or "")                    # the stand-in answers in handles too
    assert requests and all(not str(q["args"].get(k, "")).startswith("P") for q in requests
                            for k in ("target_id", "addressee_id", "to_id"))
    assert any(q["args"].get("addressee_id") == X or q["args"].get("target_id") == X for q in requests)
    entry = r.prompts[-1]
    assert entry["handles"] == {"P1": X, "P2": Y} and not TRACK.search(json.dumps(entry["choices"]))
    rec = r.records[-1]
    assert contracts.problems("decision_record", rec) == []
    for q in requests:
        assert contracts.problems("action_request", q) == []


def test_handles_stay_stable_across_decisions_and_never_reused_when_a_track_leaves():
    r, gw = _robot_lean()
    s = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    for packet in (s.see(X, 15, 8.5).hear(X, "Hello?").packet(), s.see(Y, 17, 9).hear(Y, "Excuse me?").packet()):
        job = r.observe(packet)
        if job is not None:
            asyncio.run(r.decide(job)) if job.proposals is None else r.decide_now(job)
    maps = [e["handles"] for e in r.prompts if "handles" in e]
    assert maps and all(m.items() <= maps[-1].items() for m in maps)     # only ever grows; never reassigned
    assert len(set(maps[-1].values())) == len(maps[-1])


def test_nobody_else_gets_handles_and_full_keeps_anonymous_ids():
    gw = ModelGateway(FakeModel())
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    r = rts["robot_r"]
    job = r.observe(Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
                    .see(X, 15, 8.5).hear(X, "Where?").packet())
    asyncio.run(r.decide(job))
    assert X in gw.provider.calls[0].prompt and "handles" not in r.prompts[-1]


def test_lean_answers_leave_out_defaults_and_the_runtime_fills_them():
    """D-112: SPEAK without channel is LOCAL; ids that would be null are left out; coordinates kept to one decimal."""
    s = answer_schema(("SPEAK", "GESTURE", "MOVE_TO", "WAIT"), (X,), ("LOCAL",), "FOCAL_LEAN", ("WAVE",), None, 600)
    text = json.dumps(s)
    assert '{"type": "null"}' not in text                            # no "or null" ids offered
    speak = next(c for c in s["properties"]["actions"]["items"]["anyOf"] if c["properties"]["action"]["const"] == "SPEAK")
    alts = speak["properties"]["args"]["anyOf"]
    assert alts and all("channel" not in a.get("required", []) for a in alts)
    full = answer_schema(("SPEAK",), (X,), ("LOCAL",), "FOCAL", None, None, 600)
    falts = full["properties"]["actions"]["items"]["anyOf"][0]["properties"]["args"]["anyOf"]
    assert all("channel" in a["required"] for a in falts)            # FULL unchanged
    out = json.loads(lean.expand(json.dumps({"actions": [
        {"action": "SPEAK", "args": {"text": "Hi", "addressee_id": X}},
        {"action": "MOVE_TO", "args": {"destination": {"x": 15.0432, "z": 8.4499}}},
        {"action": "GESTURE", "args": {"gesture": "WAVE"}}]})))
    assert out["actions"][0]["args"] == {"text": "Hi", "addressee_id": X, "channel": "LOCAL"}
    assert out["actions"][1]["args"]["destination"] == {"x": 15.0, "z": 8.4}
    assert out["actions"][2]["args"] == {"gesture": "WAVE"}          # absent means nobody, as null does
    for a in out["actions"]:
        probe = {"schema_version": "1.0", "action_request_id": "act_p", "agent_id": "robot_r", "based_on_tick_id": 1,
                 "action": a["action"], "args": a["args"]}
        assert contracts.problems("action_request", probe) == []


def test_lean_prompt_shows_the_compact_shapes():
    r, _ = _robot_lean()
    prefix = r.persona_prefix("FOCAL")[1]
    assert 'SPEAK {"text": "...", "addressee_id": track}' in prefix and "or null" not in prefix
    assert "People are named by handles" in prefix
