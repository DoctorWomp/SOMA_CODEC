"""G4a (D-93): the viewer feed. What an observer panel may show, what only the Evaluator sees.

The end-to-end checks (a real SB-04 run: the live feed equals the rebuilt one, the journal is
unchanged, the canary run's observer feed holds no marker, the Godot replay scrubs to every
decision) are in tools/godot_check.py; these test the builder and the committed Godot fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

from range_service import contracts
from range_service.configs import load_and_check
from range_service.viewer import feed, permissions

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "godot_app" / "tests" / "fixtures" / "viewer_sb04"
CS, _ = load_and_check()
SB04 = CS.items["scenarios"]["SB04_POLITE_BID"]
CAST = sorted(SB04["cast"])


def _packet(observer, ms, items, yaw=0.0, head=None):
    pose = {"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": yaw}
    if head is not None:
        pose.update(head_yaw_rad=head, head_pitch_rad=0.0)
    return {"schema_version": "1.0", "observer_id": observer, "based_on_tick_id": ms * 60 // 1000,
            "sim_time_ms": ms, "coordinate_frame": "world_meters_xyz", "observer_pose": pose, "observations": items}


def _presence(track, validity="OBSERVED", reason=None):
    item = {"kind": "VISUAL_PRESENCE", "track_id": track, "validity": validity, "bearing_rad": 0.1, "range_m": 1.4,
            "position_estimate": {"x": 15.0, "y": 0.0, "z": 8.5}, "visible_parts": ["HEAD"], "quality": 0.9}
    if reason:
        item["validity_reason"] = reason
    return item


def _record(agent, decision_id, response, calls_extra=None):
    call = {"call_id": f"call_{decision_id}", "attempt": 0, "outcome": "VALID", "deadline_ms": 3990,
            "timings": {"queue_ms": 5, "prefill_ms": 200, "generation_ms": 800, "total_ms": 1005},
            "prompt_tokens": 1200, "generated_tokens": 80, "cached_tokens": 900, "response_text": response,
            "error": None, **(calls_extra or {})}
    return {"agent_id": agent, "decision_id": decision_id, "tier": "FOCAL" if agent == "robot_r" else "C1",
            "policy": "MODEL", "cognition_level": "C2", "triggers": ["ADDRESSED_SPEECH"], "based_on_tick_id": 120,
            "activity": {"kind": "CONVERSE", "target_id": "anon_aaaaaaaaaa", "source": "MODEL",
                         "review_after_s": 20, "wake_if": [{"addressed": True}]},
            "fallback": None, "action_request_ids": ["act_1"], "model_calls": [call],
            "context": {"total_tokens": 1200, "budget_tokens": 3750, "tokenizer": "approx", "compression_steps": [],
                        "sections": [{"section": "GUARDRAILS", "tokens": 700, "budget": 650, "items": 1, "cut_items": 0,
                                      "never_cut": True}]}}


def test_tracks_new_lost_back_and_hearing():
    b = feed.FeedBuilder()
    b.packet(_packet("robot_r", 100, [_presence("anon_aaaaaaaaaa")], head=0.5))
    b.packet(_packet("robot_r", 200, [_presence("anon_aaaaaaaaaa", "MISSING", "LEFT_FIELD_OF_VIEW")]))
    speech = {"kind": "AUDIO_SPEECH", "track_id": "anon_aaaaaaaaaa", "validity": "OBSERVED", "bearing_rad": -0.4,
              "range_m": 2.0, "observed_at_ms": 300, "value": {"text": "Hello?", "channel": "LOCAL",
                                                              "addressed_to_observer": True}}
    b.packet(_packet("robot_r", 300, [_presence("anon_aaaaaaaaaa"), speech]))
    obs, ev = b.take()
    assert ev == []
    tracks = [(r["data"]["event"], r["data"].get("reason")) for r in obs if r["lane"] == "tracks"]
    assert tracks == [("NEW", None), ("LOST", "LEFT_FIELD_OF_VIEW"), ("BACK", None)]
    sight = [r for r in obs if r["lane"] == "sight"]
    assert sight[0]["data"]["pose"]["head_yaw"] == 0.5 and "head_yaw" not in sight[1]["data"]["pose"]
    heard = [r for r in obs if r["lane"] == "hearing"][0]
    assert heard["data"]["text"] == "Hello?" and heard["data"]["addressed"] is True and heard["data"]["bearing"] == -0.4


def test_actions_results_drops_and_beacon():
    b = feed.FeedBuilder(expressions=CS.items["expressions"])
    b.sent({"action_request_id": "act_1", "agent_id": "robot_r", "action": "EXPRESS", "based_on_tick_id": 6,
            "args": {"expression_id": "ambient_waiting"}}, 12)
    b.result({"action_request_id": "act_1", "agent_id": "robot_r", "accepted": True, "reason_code": "OK",
              "resolved_at_tick_id": 12})
    b.sent({"action_request_id": "act_2", "agent_id": "robot_r", "action": "SPEAK", "based_on_tick_id": 12,
            "args": {"text": "Hi", "addressee_id": "anon_aaaaaaaaaa"}}, 18)
    b.result({"action_request_id": "act_2", "agent_id": "robot_r", "accepted": False,
              "reason_code": "STALE_OBSERVATION", "resolved_at_tick_id": 18})
    b.delivery("robot_r", {"event": "DROPPED", "at_ms": 500, "decision_id": "dec_1", "action_request_id": "act_3",
                           "action": "MOVE_TO", "target": "anon_aaaaaaaaaa", "reason": "TARGET_NOT_PERCEIVED"})
    obs, _ = b.take()
    beacon = [r for r in obs if r["lane"] == "beacon"]
    assert len(beacon) == 1 and beacon[0]["data"]["ambient_state"] == "WAITING"   # only the accepted one
    assert [r["data"]["reason_code"] for r in obs if r["lane"] == "result"] == ["OK", "STALE_OBSERVATION"]
    drop = [r for r in obs if r["lane"] == "delivery"][0]["data"]
    assert drop["reason"] == "TARGET_NOT_PERCEIVED" and drop["action_request_id"] == "act_3"


def test_decision_calls_salvaged_activity_dropped_and_lean_has_no_words():
    b = feed.FeedBuilder(words_evaluator_only={"visitor_x"})
    lean = '{"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}]}'
    b.decision(_record("robot_r", "dec_1", lean, {"salvaged": {"dropped": ["activity"], "actions": 1},
                                                  "activity_dropped": {"rule": "KIND", "detail": "kind ZIGZAG"}}))
    obs, ev = b.take()
    d = obs[0]["data"]
    call = d["calls"][0]
    assert call["salvaged"] == {"dropped": ["activity"], "actions": 1}
    assert call["activity_dropped"] == {"rule": "KIND"}           # the rule only; its detail is evaluator text
    assert call["queue_ms"] == 5 and call["generated_tokens"] == 80 and call["error"] is False
    assert "reason_summary" not in d                              # LEAN has none (D-85)
    assert d["context"]["sections"] == [{"section": "GUARDRAILS", "tokens": 700, "budget": 650, "items": 1, "cut_items": 0}]
    assert ev[0]["lane"] == "answer" and ev[0]["data"]["answers"][0]["response_text"] == lean
    assert "response_text" not in json.dumps(obs)


def test_reason_summary_labelled_for_robot_r_and_evaluator_only_for_an_npc_with_a_goal():
    full = json.dumps({"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}],
                       "reason_summary": "X is mid-question; waiting."})
    b = feed.FeedBuilder(words_evaluator_only=feed.words_evaluator_only(SB04, CS.items["personas"]))
    b.decision(_record("robot_r", "dec_r", full))
    b.decision(_record("visitor_x", "dec_x", full.replace("X is", "My goal: keep asking; X is")))
    obs, ev = b.take()
    r = next(x for x in obs if x["observer"] == "robot_r")["data"]
    assert r["reason_summary"] == {"text": "X is mid-question; waiting.", "label": "the model's own words"}
    x = next(x for x in obs if x["observer"] == "visitor_x")["data"]
    assert "reason_summary" not in x
    assert any(e["observer"] == "visitor_x" and "My goal" in e["data"]["reason_summary"] for e in ev)
    assert feed.words_evaluator_only(SB04, CS.items["personas"]) == {"visitor_x", "visitor_y"}


def test_prompts_give_handles_to_the_observer_and_text_to_the_evaluator_only():
    b = feed.FeedBuilder()
    entry = {"agent_id": "robot_r", "decision_id": "dec_1", "prompt": "## GUARDRAILS\nsecret prompt text",
             "handles": {"P1": "anon_aaaaaaaaaa"}}
    b.prompt(entry, 100)
    b.prompt(dict(entry, decision_id="dec_2"), 200)          # same map: no new handles record
    obs, ev = b.take()
    assert [r["lane"] for r in obs] == ["handles"] and obs[0]["data"]["handles"] == {"P1": "anon_aaaaaaaaaa"}
    assert "secret prompt text" not in json.dumps(obs)
    assert [r["lane"] for r in ev] == ["prompt", "prompt"]


def test_truth_records_are_evaluator_only():
    b = feed.FeedBuilder()
    b.truth(SB04, CS.items["personas"])
    b.truth_tracks({"robot_r": {"anon_aaaaaaaaaa": "visitor_x"}}, 90000)
    obs, ev = b.take()
    assert obs == []
    goals = next(r for r in ev if r["lane"] == "truth_goals")["data"]["goals"]
    assert goals["visitor_x"]["private_goal"] == CS.items["personas"]["visitor_x"]["private_goal"]
    labels = next(r for r in ev if r["lane"] == "truth_labels")["data"]
    assert labels["evaluator_only"] == SB04["evaluator_only"] and labels["measure"] == SB04["measure"]
    table = permissions.load_table(CS)
    assert permissions.readable(table, "SPECTATOR", ev) == []
    assert permissions.readable(table, "EVALUATOR", ev) == ev


def test_observer_leaks_catches_a_real_id_a_secret_and_shared_tracks():
    good = {"schema_version": "1.0", "audience": "OBSERVER", "observer": "robot_r", "lane": "sight", "t_ms": 0,
            "data": {"pose": {"x": 0, "z": 0, "yaw": 0}, "items": [{"track": "anon_aaaaaaaaaa", "validity": "OBSERVED"}]}}
    assert feed.observer_leaks([good], CAST) == []
    named = json.loads(json.dumps(good))
    named["data"]["items"][0]["note"] = "this is visitor_x"
    shared = dict(good, observer="visitor_y")
    found = feed.observer_leaks([named, shared], CAST, ["Keep asking follow-up questions"])
    assert any("names visitor_x" in p for p in found)
    assert any("share track ids" in p for p in found)
    secret = json.loads(json.dumps(good))
    secret["data"]["items"][0]["note"] = "Keep asking follow-up questions for about a minute"
    assert any("evaluator-only text" in p for p in feed.observer_leaks([secret], CAST, ["Keep asking follow-up questions"]))


def test_compare_finds_a_difference():
    a = [{"lane": "sight", "t_ms": 1}, {"lane": "pulse", "t_ms": 2}]
    assert feed.compare(a, list(reversed(a)))["match"] is True
    diff = feed.compare(a, a[:1])
    assert diff["match"] is False and diff["lanes"] == ["pulse"]


def _fixture(name):
    return [json.loads(x) for x in (FIXTURE / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def test_godot_fixture_matches_the_contract_and_leaks_nothing():
    obs, ev = _fixture(feed.OBSERVER_FILE), _fixture(feed.EVALUATOR_FILE)
    assert obs and ev
    for rec in obs + ev:
        found = contracts.problems("viewer_record", rec)
        assert not found, (rec["lane"], found[:2])
    secrets = [p["private_goal"] for p in CS.items["personas"].values() if p.get("private_goal")]
    secrets += [str(v) for v in SB04["evaluator_only"].values() if isinstance(v, str)]
    secrets += [r["data"]["prompt"][:60] for r in ev if r["lane"] == "prompt"]
    assert feed.observer_leaks(obs, CAST, secrets) == []
    # The fixture exercises what the Godot tests check: a drop before sending, a salvaged call, a
    # dropped activity, a labelled reason_summary, handles, evaluator prompts and real track ids.
    lanes = {r["lane"] for r in obs}
    assert {"delivery", "decision", "handles", "beacon", "sight", "hearing", "tracks", "pulse"} <= lanes
    calls = [c for r in obs if r["lane"] == "decision" for c in r["data"]["calls"]]
    assert any("salvaged" in c for c in calls) and any("activity_dropped" in c for c in calls)
    assert any("reason_summary" in r["data"] for r in obs if r["lane"] == "decision")
    assert {r["lane"] for r in ev} >= {"prompt", "answer", "truth_tracks", "truth_goals", "truth_labels"}
