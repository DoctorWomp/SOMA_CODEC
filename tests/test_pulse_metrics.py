"""G3d fix 3 (D-65): pulse metrics measure real responses.

Before: any decision within 1 s cleared a relevant event, "already attending" meant only that the
last glance had been at that source (however long ago), and proposals counted as responses even
when the host refused them. No Godot, no model.
"""

from __future__ import annotations

from range_service.eval.pulse_metrics import LOOK_AT_HOLD_MS, _agent, gaze_intervals

from .agent_helpers import refuse
from .test_pulse import P, Q, Scene, robot, run

S, T = "anon_sourcesss1", "anon_otherrrrr2"


def _relevant(at, src=S, kind="speech"):
    return {"event": "RELEVANT", "at_ms": at, "source": src, "kind": kind}


def _glance(at, target=S, rid="g1", event="GLANCE"):
    return {"event": event, "at_ms": at, "target": target, "why": "speech", "request_id": rid}


def _result(at, rid, accepted=True):
    return {"event": "RESULT", "at_ms": at, "request_id": rid, "accepted": accepted,
            "reason_code": "OK" if accepted else "TARGET_UNKNOWN", "action": "GLANCE"}


def _decision(at, sources=(), actions=()):
    return {"event": "DECISION", "at_ms": at, "policy": "DEMO", "triggers": ["PERSON_NEAR"], "activity": "ATTEND",
            "source": "DERIVED", "waited_ms": 0, "tokens": None, "sources": list(sources), "targets": [],
            "actions": [list(a) for a in actions]}


def test_an_unrelated_decision_right_after_an_event_does_not_clear_it():
    log = [_relevant(10_000), _decision(10_200, sources=[T], actions=[("a1", "SPEAK", T)]), _result(10_300, "a1")]
    m = _agent(log, 60_000)
    assert m["zombie"]["events"] == 1 and m["zombie"]["ms"] == 10_000          # was 0: any decision counted
    assert m["zombie"]["cases"][0]["source"] == S


def test_a_decision_triggered_by_or_aimed_at_the_source_clears_it():
    for decision in (_decision(10_200, sources=[S], actions=[("a1", "WAIT", None)]),
                     _decision(10_200, sources=[T], actions=[("a1", "TURN_TO", S)])):
        m = _agent([_relevant(10_000), decision, _result(10_300, "a1")], 60_000)
        assert m["zombie"]["events"] == 0, decision


def test_an_expired_gaze_is_not_already_attending():
    # Looked at S at 0 s; the hold ended at 3 s. S speaks at 20 s and gets nothing.
    log = [_glance(0, rid="g0"), _result(16, "g0"), _relevant(20_000)]
    m = _agent(log, 60_000)
    assert m["zombie"]["events"] == 1                                            # was 0: "last gaze target" was S
    # Still inside the hold: already attending, no response needed.
    log = [_glance(0, rid="g0"), _result(16, "g0"), _relevant(2_000)]
    assert _agent(log, 60_000)["zombie"]["events"] == 0
    # A look elsewhere ends the gaze on S early.
    log = [_glance(0, rid="g0"), _result(16, "g0"), _glance(1_000, T, "g1"), _result(1_016, "g1"), _relevant(2_000)]
    assert _agent(log, 60_000)["zombie"]["events"] == 1


def test_a_glance_refused_by_the_host_is_a_proposal_not_a_response():
    log = [_relevant(10_000), _glance(10_000, rid="g1"), _result(10_016, "g1", accepted=False)]
    m = _agent(log, 60_000)
    assert m["zombie"]["events"] == 1 and m["glances_refused"] == 1 and m["glances_accepted"] == 0
    assert m["zombie_proposed"]["events"] == 0                                    # it was proposed in time
    assert m["glance_latency_ms"]["n"] == 0 and m["glance_latency_proposed_ms"]["max"] == 0


def test_gaze_intervals_have_a_start_and_an_end():
    looks = [(0, S, "GLANCE"), (1000, S, "GAZE_HOLD"), (2000, T, "GLANCE"), (9000, S, "GLANCE")]
    assert gaze_intervals(looks) == [(0, 2000, S), (1000, 2000, S), (2000, 2000 + LOOK_AT_HOLD_MS, T),
                                     (9000, 9000 + LOOK_AT_HOLD_MS, S)]


def test_the_runtime_links_glances_to_requests_and_host_results():
    rt = robot()
    s = Scene()
    run(rt, s.packet())
    _, out = run(rt, s.see(Q, 22, 14).packet(), world_accepts=False)            # someone appears 9 m away
    look = next(r for r in out if r["action"] == "LOOK_AT")
    refuse(rt, look, "TARGET_UNKNOWN")
    glance = next(e for e in rt.pulse_log if e["event"] == "GLANCE")
    assert glance["request_id"] == look["action_request_id"]
    assert any(e["event"] == "RESULT" and e["request_id"] == look["action_request_id"] and not e["accepted"]
               for e in rt.pulse_log)
    decision = next(e for e in rt.pulse_log if e["event"] == "DECISION")
    assert "sources" in decision and "actions" in decision
    assert P != Q


def test_presence_glances_again_once_the_world_gaze_hold_has_ended():
    """Found by the honest metric (D-65): the presence loop treated its last glance target as still
    looked at, long after the world's 3 s hold had ended, so a source it had glanced at once never
    got a glance again (SB-08: Y spoke 24 s after the glance and got none for 21 s)."""
    from range_service.agents.pulse import Presence
    from range_service.agents.working_set import WorkingSet

    from .test_pulse import CFG

    presence = Presence(CFG["presence"])
    ws = WorkingSet("robot_r")
    s = Scene()
    ws.update(s.see(Q, 22, 14).packet())
    first, _ = presence.step(now_ms=0, ws=ws, perceived=ws.update(s.see(Q, 22, 14).packet()),
                             heard=[{"track_id": Q}], partner=None, speaking_until_ms=0, activity=None,
                             can_look=True, expressions=[])
    assert first and first[0][0] == "LOOK_AT"
    soon, _ = presence.step(now_ms=1000, ws=ws, perceived=ws.update(s.see(Q, 22, 14).packet()),
                            heard=[{"track_id": Q}], partner=None, speaking_until_ms=0, activity=None,
                            can_look=True, expressions=[])
    assert soon == []                                                   # still held by the world: no repeat
    later, _ = presence.step(now_ms=24_000, ws=ws, perceived=ws.update(s.see(Q, 22, 14).packet()),
                             heard=[{"track_id": Q}], partner=None, speaking_until_ms=0, activity=None,
                             can_look=True, expressions=[])
    assert later and later[0] == ("LOOK_AT", {"target_id": Q})
