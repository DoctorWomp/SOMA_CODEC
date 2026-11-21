"""G3h: an invalid activity never costs the actions (D-110); FN-1 holds are counted apart.

The owner's G3g run: with LEAN, ACTIVITY_RULE failures turned valid answers into WAITs (8 of 56
calls with N3; 5 of 40 alone, where every fallback was a rule failure and none a timeout). The
activity is optional (D-61): when it breaks a rule, the actions stand and the runtime derives an
activity as when none is given. No Godot, no real model."""

from __future__ import annotations

import asyncio
import json

import pytest

from range_service import contracts
from range_service.agents import activity as activities
from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import FakeModel, ModelGateway
from range_service.eval import bakeoff as bk
from range_service.eval import live_diag
from tests.agent_helpers import CONFIGS, Scene

SB04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
PULSE = CONFIGS.items["pulse"]["pulse"]
X = "anon_xxxxxxxxx1"
SPEAK = {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "The demo is on the platform.", "addressee_id": X}}


def _robot(answer: str, lean: bool = False):
    gw = ModelGateway(FakeModel(responder=lambda r: answer))
    if lean:
        gw.answer = "LEAN"
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    r = rts["robot_r"]
    scene = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    job = r.observe(scene.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    assert job is not None and job.proposals is None
    requests = asyncio.run(r.decide(job))
    return r, requests, gw


@pytest.mark.parametrize("bad,rule", [
    ({"kind": "CONVERSE", "target_id": "anon_nobodyhere"}, "TARGET_NOT_PERCEIVED"),
    ({"kind": "WAIT_FOR"}, "NEEDS_TARGET"),
    ({"kind": "CONVERSE", "target_id": X, "commitment_id": "mem_nothing_open"}, "COMMITMENT_NOT_OPEN"),
    ({"kind": "CONVERSE", "target_id": X, "wake_if": [{"horizon": True}]}, "WAKE_RESERVED"),
    ({"kind": "DANCE", "target_id": X}, "KIND"),
])
def test_an_invalid_activity_is_dropped_and_the_actions_kept(bad, rule):
    """Reproduced on main: the same answer was repaired, failed again and became a WAIT fallback."""
    r, requests, gw = _robot(json.dumps({"actions": [SPEAK], "activity": bad}))
    rec = r.records[-1]
    assert rec["fallback"] is None
    assert [q["action"] for q in requests] == ["SPEAK"]
    assert len(gw.provider.calls) == 1                                   # no repair spent on it
    call = rec["model_calls"][0]
    assert call["outcome"] == "VALID" and call["activity_dropped"]["rule"] == rule
    assert rec["activity"]["source"] == "DERIVED" and rec["activity"]["kind"] == "CONVERSE"
    assert contracts.problems("decision_record", rec) == []
    assert any(e["event"] == "ACTIVITY_DROPPED" and e["rule"] == rule for e in r.pulse_log)


def test_a_compact_lean_activity_that_breaks_a_rule_is_dropped_too():
    answer = json.dumps({"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}], "activity": {"kind": "ASSIST"}})
    r, requests, _ = _robot(answer, lean=True)
    rec = r.records[-1]
    assert rec["fallback"] is None and rec["model_calls"][0]["activity_dropped"]["rule"] == "NEEDS_TARGET"


def test_fn1_is_still_a_rejection_and_is_counted_as_held():
    """Leaving a conversation without a closing line stays a rejection: the runtime holds Robot R with
    its partner. The decision is recorded as held by FN-1, apart from failures (D-110)."""
    gw = ModelGateway(FakeModel(responder=lambda r: json.dumps(
        {"actions": [{"action": "MOVE_TO", "args": {"destination": {"x": 3.0, "z": 3.0}}}]})))
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    r = rts["robot_r"]
    scene = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    for text in ("Hello, where is the demo?", "And the ramp?"):
        job = r.observe(scene.see(X, 15, 8.5).hear(X, text).packet())
        if job is not None:
            asyncio.run(r.decide(job)) if job.proposals is None else r.decide_now(job)
    held = [rec for rec in r.records if rec["fallback"] and rec["fallback"]["reason"] == "FN1_HELD"]
    assert held, [rec["fallback"] for rec in r.records]
    assert all(contracts.problems("decision_record", rec) == [] for rec in held)
    b = live_diag.robot_breakdown(r.records)
    assert b["held_by_fn1"] == len(held) and b["fallbacks"] == sum(1 for x in r.records if x["fallback"]) - len(held)


def test_target_table_counts_fn1_holds_apart_and_judges_live_only():
    def live(mode, fallbacks, held, decisions):
        return {"label": "F3 Gemma", "npc_label": "N3", "mode": mode, "p95_ms": 3000.0, "timeouts": 0,
                "decisions": decisions, "npc_calls": 0, "npc_timeouts": 0, "harness": "g3f", "run_dir": f"r{mode}",
                "robot": {"fallbacks_by_reason": {"INVALID_OUTPUT": fallbacks, "FN1_HELD": held},
                          "decisions": decisions, "salvaged": 0, "held_by_fn1": held}}
    lines = bk.target_lines([live("LIVE", 3, 4, 40), live("LIVE_LOAD", 30, 0, 40)], bk.fmt, {})
    row = next(x for x in lines if "| LIVE |" in x)
    assert "| 3/40 (8%) |" in row and "| 4 |" in row and "| met |" in row          # 4 holds are not failures
    stress = next(x for x in lines if "| LIVE_LOAD |" in x)
    assert "stress: reported" in stress and "NOT met" not in stress


def test_activity_rule_kinds_cover_every_parse_error():
    """Every message activity.parse can give maps to a rule kind (diagnose reports the kind only)."""
    cases = [{"kind": "X"}, {"kind": "CONVERSE"}, {"kind": "CONVERSE", "target_id": "anon_q"},
             {"kind": "SURVEY", "commitment_id": "mem_x"}, {"kind": "SURVEY", "review_after_s": 1},
             {"kind": "SURVEY", "wake_if": "x"}, {"kind": "SURVEY", "wake_if": [{"a": 1, "b": 2}]},
             {"kind": "SURVEY", "wake_if": [{"horizon": True}]}, {"kind": "SURVEY", "wake_if": [{"nope": True}]},
             {"kind": "SURVEY", "wake_if": [{"target_within_m": 99}]}, {"kind": "SURVEY", "wake_if": [{"addressed": 1}]},
             "not an object"]
    kinds = set()
    for raw in cases:
        _, error = activities.parse(raw, now_ms=0, default_review_s=60, max_review_s=600, open_commitments=set(),
                                    perceived=set())
        assert error is not None
        kinds.add(activities.rule_of(error))
    assert "OTHER" not in kinds and len(kinds) == 12
    assert live_diag.classify_error("activity target 'anon_q' is not a track you perceive") == "ACTIVITY_RULE"
    assert live_diag.activity_rule("activity target 'anon_q' is not a track you perceive") == "TARGET_NOT_PERCEIVED"


def test_diagnose_reports_the_activity_rule_kind_only(tmp_path):
    """Old run folders hold rejected activities (the error names a track): diagnose shows the rule kind."""
    run = tmp_path / "run_F3_n3_live_lean_1"
    (run / "sidecar").mkdir(parents=True)
    call = {"call_id": "c1", "attempt": 0, "outcome": "INVALID_OUTPUT", "timings": {"queue_ms": 0, "total_ms": 900},
            "error": "activity target 'anon_secret0001' is not a track you perceive", "response_text": "{...}"}
    rec = {"agent_id": "robot_r", "decision_id": "dec_robot_r_000001", "based_on_tick_id": 60, "tier": "FOCAL",
           "triggers": ["ADDRESSED_SPEECH"], "model_calls": [call], "fallback": {"action": "WAIT", "reason": "INVALID_OUTPUT"},
           "context": {"total_tokens": 1500}}
    (run / "sidecar" / "decision_records.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    rows = live_diag.diagnose_folder(run)
    assert rows[0]["activity_rules_rejected"] == {"TARGET_NOT_PERCEIVED": 1}
    text = "\n".join(bk.diagnosis_lines([dict(rows[0], model="F3", npc_model="N3")]))
    assert "TARGET_NOT_PERCEIVED 1 / –" in text and "anon_secret0001" not in text
