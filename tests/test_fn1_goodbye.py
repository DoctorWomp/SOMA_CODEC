"""G3d fix 4 (D-66): FN-1 means a goodbye the partner could hear, before leaving.

Before: any SPEAK with a closing word anywhere in the answer let the agent walk away, even one
said to someone else or after the MOVE_TO, and the MOVE_TO went out with it whether or not the
world accepted the line. No Godot, no model.
"""

from __future__ import annotations

import json

from range_service.agents.gateway import FakeModel, ModelGateway, scripted_responses

from .agent_helpers import refuse
from .test_pulse import P, Q, _in_conversation, robot, run

AWAY = {"action": "MOVE_TO", "args": {"destination": {"x": 2.0, "z": 2.0}}}


def _say(text: str, to: str | None) -> dict:
    return {"action": "SPEAK", "args": {"channel": "LOCAL", "text": text, "addressee_id": to}}


def _answer(*actions: dict) -> str:
    return json.dumps({"actions": list(actions)})


def _leave_with(first_try: str, repair: str):
    fake = FakeModel()
    rt = robot(ModelGateway(fake))
    s = _in_conversation(rt)
    fake.responder = scripted_responses([first_try, repair])
    _, out = run(rt, s.see(P, 15, 8.5).see(Q, 18, 8.5).hear(P, "So, anything else?").packet(), world_accepts=False)
    return rt, s, out, rt.records[-1]


def test_a_closing_line_to_someone_else_does_not_count():
    rt, _, out, rec = _leave_with(_answer(_say("Excuse me, I need to go.", Q), AWAY),
                                  _answer(_say("Excuse me, I need to go.", Q), AWAY))
    assert [c["outcome"] for c in rec["model_calls"]] == ["INVALID_OUTPUT", "INVALID_OUTPUT"]
    assert "said to" in rec["model_calls"][0]["error"]
    assert "MOVE_TO" not in [r["action"] for r in out]                   # held: stays engaged
    assert any(e["event"] == "FN1_HELD" for e in rt.pulse_log)


def test_the_closing_line_must_come_before_the_departure():
    rt, _, out, rec = _leave_with(_answer(AWAY, _say("Excuse me, I need to go.", P)),
                                  _answer(_say("Excuse me, I need to go.", P), AWAY))
    assert [c["outcome"] for c in rec["model_calls"]] == ["INVALID_OUTPUT", "VALID"]
    assert "closing line first" in rec["model_calls"][0]["error"]


def test_local_speech_within_earshot_counts_as_a_closing_line():
    rt, _, out, rec = _leave_with(_answer(_say("Sorry, I have to go now.", None), AWAY), _answer(AWAY))
    assert [c["outcome"] for c in rec["model_calls"]] == ["VALID"]        # P is 1.5 m away: within earshot


def test_departure_waits_until_the_closing_line_is_accepted():
    rt, s, out, rec = _leave_with(_answer(_say("Excuse me, I need to go.", P), AWAY), _answer(AWAY))
    assert [r["action"] for r in out if r["action_request_id"] in rec["action_request_ids"]] == ["SPEAK"]
    move_id = rec["action_request_ids"][-1]
    assert [e["event"] for e in rt.delivery_log] == ["HELD_FOR_CLOSING"]
    _, nxt = run(rt, s.see(P, 15, 8.5).packet(), world_accepts=False)
    assert move_id not in [r["action_request_id"] for r in nxt]           # not before the host accepted the line
    speak = next(r for r in out if r["action"] == "SPEAK")
    rt.on_result({"schema_version": "1.0", "action_request_id": speak["action_request_id"], "agent_id": "robot_r",
                  "accepted": True, "executed": True, "reason_code": "OK", "resulting_event_ids": [],
                  "resolved_at_tick_id": s.tick})
    _, nxt = run(rt, s.see(P, 15, 8.5).packet(), world_accepts=False)
    released = [r for r in nxt if r["action_request_id"] == move_id]
    assert released and released[0]["action"] == "MOVE_TO"
    assert released[0]["based_on_tick_id"] == s.tick - 6                 # rechecked against the latest observation
    assert rt.delivery_log[-1]["event"] == "RELEASED"


def test_if_the_closing_line_is_refused_the_agent_stays():
    rt, s, out, rec = _leave_with(_answer(_say("Excuse me, I need to go.", P), AWAY), _answer(AWAY))
    speak = next(r for r in out if r["action"] == "SPEAK")
    refuse(rt, speak, "RATE_LIMITED")
    for _ in range(3):
        _, nxt = run(rt, s.see(P, 15, 8.5).packet(), world_accepts=False)
        assert "MOVE_TO" not in [r["action"] for r in nxt if r["action_request_id"] in rec["action_request_ids"]]
    assert any(e["event"] == "FN1_STAYED" for e in rt.pulse_log)
    assert rt.delivery_log[-1]["event"] == "DROPPED"
    assert rt.activity is not None and rt.activity.kind == "CONVERSE" and rt.activity.target_id == P
