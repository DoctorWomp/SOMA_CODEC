"""The pulse protocol (G3c-2, D-61; PULSE_PROTOCOL; FIELD_NOTES FN-1, FN-2). No Godot, no model."""

from __future__ import annotations

import asyncio
import json
import math

import pytest
from jsonschema import Draft202012Validator

from range_service import contracts
from range_service.agents import activity as act
from range_service.agents.factory import public_persona
from range_service.agents.gateway import FakeModel, ModelGateway, parse_output, scripted_responses
from range_service.agents.output_schema import answer_schema, mixes_alternatives
from range_service.agents.pulse import IntentMonitor, Presence, Pulse, Survey, seeded_fraction, voice_key
from range_service.agents.runtime import AgentRuntime
from range_service.agents.working_set import Perceived, WorkingSet
from tests.agent_helpers import CONFIGS, Scene, accept

CFG = CONFIGS.items["pulse"]["pulse"]
P, Q = "anon_pppppppppp", "anon_qqqqqqqqqq"
AREA = {"x_min": 0.0, "x_max": 30.0, "z_min": 0.0, "z_max": 20.0}


def robot(gateway=None, task="Help visitors.", post_duty=True) -> AgentRuntime:
    from range_service import expressions as expression_rules

    body = CONFIGS.items["bodies"]["wheeled_humanoid"]
    return AgentRuntime("robot_r", persona=public_persona(CONFIGS.items["personas"]["robot_r"]), body=body,
                        directive="Help visitors.", expressions=expression_rules.available(body, CONFIGS.items["expressions"]),
                        setting=[], task=task, focal=True, controller="LLM_AGENT", gateway=gateway, pulse=CFG, seed=7,
                        post={"x": 15.0, "z": 10.0}, post_duty=post_duty, survey_area=AREA)


def run(rt: AgentRuntime, packet: dict, world_accepts: bool = True):
    """One packet; the world accepts what the agent sends unless ``world_accepts`` is False."""
    job = rt.observe(packet)
    out = rt.take_presence()
    if job is not None:
        out += asyncio.run(rt.decide(job)) if job.proposals is None else rt.decide_now(job)
    if world_accepts:
        accept(rt, out)
    return job, out


# ---------- activities ----------

def test_activity_parse_accepts_only_what_the_senses_can_check():
    ok, err = act.parse({"kind": "WAIT_FOR", "target_id": P, "review_after_s": 120,
                         "wake_if": [{"target_within_m": 2.0}, {"addressed": True}]},
                        now_ms=0, default_review_s=60, max_review_s=600, open_commitments=set(), perceived={P})
    assert err is None and ok.source == "CHOSEN" and ok.target_id == P
    for bad, why in (({"kind": "PACE"}, "not one of"),
                     ({"kind": "WAIT_FOR", "target_id": Q}, "not a track you perceive"),
                     ({"kind": "WAIT_FOR"}, "needs a target_id"),
                     ({"kind": "ATTEND", "wake_if": [{"horizon": "HAZE_RISES_ON_TARGET"}]}, "reserved for HORIZON"),
                     ({"kind": "ATTEND", "wake_if": [{"addressed": True, "new_track": True}]}, "one key"),
                     ({"kind": "ATTEND", "review_after_s": 2}, "review_after_s")):
        assert why in act.parse(bad, now_ms=0, default_review_s=60, max_review_s=600, open_commitments=set(),
                                perceived={P})[1], bad


def test_horizon_conditions_are_reserved_in_the_contract_but_never_offered():
    common = contracts.load_schema("common")
    assert "horizon" in common["$defs"]["wake_condition"]["properties"]          # a documented slot for G5
    schema = answer_schema(("SPEAK", "WAIT", "MOVE_TO"), (P,), ("LOCAL",), "FOCAL", None, None, 600)
    assert "horizon" not in json.dumps(schema["properties"]["activity"]) and not mixes_alternatives(schema)
    v = Draft202012Validator(schema)
    assert not list(v.iter_errors({"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}],
                                   "activity": {"kind": "WAIT_FOR", "target_id": P, "wake_if": [{"addressed": True}]}}))
    assert list(v.iter_errors({"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}],
                               "activity": {"kind": "ATTEND", "wake_if": [{"horizon": "FOCUS_NEW_TARGET"}]}}))


def test_an_answer_without_an_activity_still_works_exactly_as_before():
    text = '{"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}]}'
    assert parse_output(text, ["WAIT"], "robot_r", 1) == parse_output(text, ["WAIT"], "robot_r", 1, allow_activity=True)
    with_activity = '{"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}], "activity": {"kind": "ATTEND"}}'
    assert parse_output(with_activity, ["WAIT"], "robot_r", 1)[2] is not None          # pulse off: not part of the answer
    assert parse_output(with_activity, ["WAIT"], "robot_r", 1, allow_activity=True)[2] is None


def test_derived_activities_are_marked_derived():
    d = lambda actions, **kw: act.derive(actions, now_ms=5, current=kw.get("current"), partner=kw.get("partner"),   # noqa: E731
                                         promised=kw.get("promised", {}), default_review_s=60,
                                         has_task_goal=kw.get("task", False), post_duty=False)
    speak = {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi", "addressee_id": P}}
    assert (d([speak]).kind, d([speak]).target_id, d([speak]).source) == ("CONVERSE", P, "DERIVED")
    promise = dict(speak, commitment="Help them later.")
    w = d([promise], promised={P: "mem_robot_r_00003"})
    assert (w.kind, w.commitment_id) == ("WAIT_FOR", "mem_robot_r_00003")
    assert d([{"action": "MOVE_TO", "args": {"destination": {"x": 1, "z": 2}}}]).kind == "TRAVEL_TO"
    assert d([]).kind == "SURVEY" and d([], task=True).kind == "ATTEND"
    converse = d([speak])
    assert d([], current=converse, partner=P).source == "CONTINUED"
    assert d([], current=converse, partner=None).kind == "SURVEY"            # an ended conversation is not continued


# ---------- loop 3 and loop 4 ----------

def test_monitor_fires_on_change_with_cooldowns():
    m = IntentMonitor(CFG["pulse"]["cooldowns_s"])
    a = act.Activity("WAIT_FOR", P, wake_if=[{"speech_heard": True}, {"target_within_m": 2.0}], started_ms=0)
    ws = WorkingSet("robot_r")
    s = Scene()
    ws.update(s.see(P, 15, 14).packet())
    kw = dict(perceived=Perceived(), ws=ws, addressed=False, new_tracks=[], due_commitment=False)
    assert m.check(a, now_ms=1000, heard_tracks=[P], **kw) == ["speech_heard"]
    assert m.check(a, now_ms=2000, heard_tracks=[P], **kw) == []                   # 5 s cooldown
    assert m.check(a, now_ms=7000, heard_tracks=[P], **kw) == ["speech_heard"]
    ws.update(s.see(P, 15, 11).packet())                                          # comes within 2 m
    assert m.check(a, now_ms=8000, heard_tracks=[], **kw) == ["target_within_m"]
    assert m.check(a, now_ms=9000, heard_tracks=[], **kw) == []                    # already near: once


def test_pulse_backs_off_resets_and_jitter_is_seeded():
    p = Pulse(dict(CFG["pulse"], jitter_frac=0.0), "robot_r", 1)
    a = act.Activity("ATTEND", review_after_s=45)
    gaps = []
    p.schedule(0, a, reset=True)
    for _ in range(4):
        gaps.append(p.next_ms)
        p.step += 1
        p.schedule(0, a, reset=False)
    assert gaps == [15_000, 30_000, 45_000, 45_000]                               # 15 -> 30 -> capped at 45 s
    p.schedule(0, a, reset=True)
    assert p.next_ms == 15_000                                                     # a change starts again
    assert seeded_fraction(4204, "robot_r", 3) == seeded_fraction(4204, "robot_r", 3) != seeded_fraction(4205, "robot_r", 3)


# ---------- loop 2: presence (FN-2) ----------

def test_presence_glances_rate_limited_and_return_to_partner():
    pr = Presence(CFG["presence"])
    ws = WorkingSet("robot_r")
    s = Scene()
    seen = ws.update(s.see(P, 15, 8.5).see(Q, 18, 12).packet())
    kw = dict(ws=ws, perceived=seen, heard=[], activity=None, can_look=True, expressions=[])
    out, ev = pr.step(now_ms=1000, partner=P, speaking_until_ms=0, **kw)
    assert ("LOOK_AT", {"target_id": P}) in out or ("LOOK_AT", {"target_id": Q}) in out
    later = Perceived()
    out, _ = pr.step(now_ms=1500, partner=P, speaking_until_ms=0, ws=ws, perceived=later,
                     heard=[{"track_id": Q}], activity=None, can_look=True, expressions=[])
    out2, _ = pr.step(now_ms=2600, partner=P, speaking_until_ms=0, ws=ws, perceived=later, heard=[],
                      activity=None, can_look=True, expressions=[])
    assert ("LOOK_AT", {"target_id": P}) in out + out2                              # back on the partner within ~1 s
    # Movement is rate limited per source; a new utterance is a discrete event and is glanced at even
    # within the cooldown, also while it speaks itself (G4b, D-107; it used to be "never while speaking").
    moved = Perceived(new_tracks=[Q])
    again, _ = pr.step(now_ms=3000, partner=None, speaking_until_ms=0, ws=ws, perceived=moved, heard=[],
                       activity=None, can_look=True, expressions=[])
    assert again == []                                                             # movement: cooldown
    talking, _ = pr.step(now_ms=4000, partner=None, speaking_until_ms=9000, ws=ws, perceived=later,
                         heard=[{"track_id": Q}], activity=None, can_look=True, expressions=[])
    assert talking == [("LOOK_AT", {"target_id": Q})]


def test_speaker_keeps_its_partner_in_gaze_and_glances_at_others_d107():
    """The owner's live SB-04 (F3): Robot R's long answers silenced the presence loop, so the gaze
    hold on its partner lapsed and the partner's next question got no look until the model answered."""
    pr = Presence(CFG["presence"])
    ws = WorkingSet("robot_r")
    seen = ws.update(Scene().see(P, 15, 8.5).see(Q, 18, 12).packet())
    kw = dict(ws=ws, heard=[], activity=None, can_look=True, expressions=[], partner=P)
    pr.step(now_ms=0, perceived=Perceived(), speaking_until_ms=0, **kw)           # gaze on the partner
    assert pr.gaze_target == P
    out, ev = pr.step(now_ms=5000, perceived=Perceived(), speaking_until_ms=11000, **kw)
    assert out == [("LOOK_AT", {"target_id": P})] and ev[0].kind == "GAZE_HOLD"     # held while speaking
    out, ev = pr.step(now_ms=5100, perceived=Perceived(), speaking_until_ms=11000, ws=ws,
                      heard=[{"track_id": P}, {"track_id": Q}], activity=None, can_look=True, expressions=[],
                      partner=P)
    assert out == [("LOOK_AT", {"target_id": Q})]                                  # someone else: a glance
    del seen


def test_two_people_arriving_together_both_get_a_glance_within_a_second_d107():
    pr = Presence(CFG["presence"])
    ws = WorkingSet("visitor_x")
    seen = ws.update(Scene().see(P, 15, 8.5).see(Q, 16, 9).packet())
    kw = dict(ws=ws, heard=[], activity=None, can_look=True, expressions=[], partner=None, speaking_until_ms=0)
    first, _ = pr.step(now_ms=200, perceived=seen, **kw)
    second, _ = pr.step(now_ms=300, perceived=Perceived(), **kw)
    targets = [a[1]["target_id"] for a in first + second]
    assert sorted(targets) == sorted([P, Q])                                       # one per packet, both within 1 s
    late, _ = pr.step(now_ms=1500, perceived=Perceived(), **kw)
    assert late == []                                                              # nothing left pending


def test_glance_toward_an_unseen_voice_points_where_it_came_from():
    pr = Presence(CFG["presence"])
    ws = WorkingSet("robot_r")
    ws.update(Scene().packet())                                                    # pose (15, 10), facing -z
    out, ev = pr.step(now_ms=100, ws=ws, perceived=Perceived(), heard=[{"track_id": None, "bearing_rad": -math.pi / 2}],
                      partner=None, speaking_until_ms=0, activity=None, can_look=True, expressions=[])
    (action, args), = out
    assert action == "LOOK_AT" and args["point"]["x"] == pytest.approx(18.0) and args["point"]["z"] == pytest.approx(10.0)
    assert ev[0].data["target"] == voice_key(-math.pi / 2)                         # bearing right = +x


# ---------- SURVEY / RETURN_TO_POST ----------

def test_survey_goes_where_it_saw_least_recently_never_paces_and_returns_to_post():
    sv = Survey(dict(CFG["survey"], dwell_s=0, return_to_post_s=60), AREA, {"x": 15.0, "z": 10.0})
    pose = {"x": 15.0, "z": 10.0, "yaw_rad": 0.0}
    sv.observe(0, pose)
    why, dest = sv.next_move(0, pose, people=[(2.5, 2.5)])
    assert why == "SURVEY" and math.hypot(dest["x"] - 2.5, dest["z"] - 2.5) >= CFG["survey"]["people_clearance_m"]
    visited = []
    t = 0
    for _ in range(10):
        pose = {"x": dest["x"], "z": dest["z"], "yaw_rad": 0.0}
        t += 9_000
        sv.observe(t, pose)
        move = sv.next_move(t, pose, people=[])
        if move is None:
            continue
        why, dest = move
        visited.append((why, (dest["x"], dest["z"])))
    cells = [c for w, c in visited[:visited.index(("RETURN_TO_POST", (15.0, 10.0)))] if w == "SURVEY"] \
        if ("RETURN_TO_POST", (15.0, 10.0)) in visited else [c for w, c in visited if w == "SURVEY"]
    assert len(cells) == len(set(cells))                                           # no pacing back and forth
    assert ("RETURN_TO_POST", (15.0, 10.0)) in visited


# ---------- FN-1: holding a conversation ----------

def _in_conversation(rt):
    s = Scene()
    run(rt, s.see(P, 15, 8.5).packet())
    run(rt, s.see(P, 15, 8.5).hear(P, "Hi! Where is the demo?").packet())
    return s


WALK_AWAY = '{"actions": [{"action": "MOVE_TO", "args": {"destination": {"x": 2.0, "z": 2.0}}}]}'
EXCUSED = ('{"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Excuse me, I need to go.", '
           '"addressee_id": "%s"}}, {"action": "MOVE_TO", "args": {"destination": {"x": 2.0, "z": 2.0}}}]}' % P)


def test_fn1_walking_away_mid_conversation_is_repaired_once_then_held():
    fake = FakeModel(responder=lambda r: r.demo_hint if "## REPAIR" not in r.prompt and r.attempt == 0 and
                     "Where is the demo" not in r.prompt else WALK_AWAY)
    rt = robot(ModelGateway(fake))
    s = _in_conversation(rt)
    fake.responder = scripted_responses([WALK_AWAY, WALK_AWAY])
    job, out = run(rt, s.see(P, 15, 8.5).hear(P, "And then?").packet())
    rec = rt.records[-1]
    assert [c["outcome"] for c in rec["model_calls"]] == ["INVALID_OUTPUT", "INVALID_OUTPUT"]
    assert "conversation with" in rec["model_calls"][0]["error"]
    assert "## REPAIR" in fake.calls[-1].prompt
    actions = [r["action"] for r in out if r["action_request_id"] in rec["action_request_ids"]]
    assert "MOVE_TO" not in actions and "LOOK_AT" in actions                       # stayed engaged
    assert any(e["event"] == "FN1_HELD" for e in rt.pulse_log)


def test_fn1_a_closing_line_lets_it_leave():
    fake = FakeModel()
    rt = robot(ModelGateway(fake))
    s = _in_conversation(rt)
    fake.responder = scripted_responses([EXCUSED])
    run(rt, s.see(P, 15, 8.5).hear(P, "Thanks.").packet())
    rec = rt.records[-1]
    assert [c["outcome"] for c in rec["model_calls"]] == ["VALID"]
    assert not any(e["event"] in ("FN1_HELD", "FN1_VIOLATION") for e in rt.pulse_log)


# ---------- the pulse over time: few calls while quiet, recover on change, flat context ----------

def test_idle_reviews_fall_while_quiet_recover_on_change_and_context_stays_flat():
    fake = FakeModel()
    rt = robot(ModelGateway(fake), task=None, post_duty=True)
    s = Scene()
    s.pose = {"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0}
    calls_per_min = []
    for minute in range(30):
        before = len(fake.calls)
        for second in range(60):
            if minute in (12, 25) and second == 10:
                s.see(Q, 25, 18)                                                  # someone passes far away
            elif minute in (12, 25) and 10 < second < 20:
                s.see(Q, 25, 18)
            run(rt, s.packet(advance=60))
        calls_per_min.append(len(fake.calls) - before)
    assert calls_per_min[0] >= 1                                                   # the start
    assert sum(calls_per_min[2:12]) == 0                                           # quiet: CONTINUE, no model call
    assert calls_per_min[12] + calls_per_min[13] >= 1                              # a change: it reviews again
    assert max(calls_per_min) <= CFG["pulse"]["idle_budget_per_min"] + 3           # budget (+ real triggers)
    continues = [e for e in rt.pulse_log if e["event"] == "CONTINUE"]
    assert len(continues) >= 20
    tokens = [r["context"]["total_tokens"] for r in rt.records if r["context"]]
    assert max(tokens) - min(tokens) < 200                                          # flat, however long the run
    sitrep = rt.sitrep()
    assert sitrep.count("\n") <= 6 and "quiet checks since" in sitrep              # one line, not a log
