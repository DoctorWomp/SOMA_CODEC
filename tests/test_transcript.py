"""tools/transcript.py: a run told in order, readable afterwards (owner, 2026-11-27: live runs go by
too fast to read)."""

from __future__ import annotations

import json

from tools import transcript


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _run(tmp_path):
    run = tmp_path / "sb04_test"
    _write(run / "journal.jsonl", [
        {"kind": "RUN_STARTED", "sim_time_ms": 0, "actor_id": None, "payload": {}},
        {"kind": "SPEECH_EMITTED", "sim_time_ms": 2100, "actor_id": "visitor_x",
         "payload": {"avatar_id": "visitor_x", "addressee_id": "robot_r", "channel": "LOCAL", "text": "Where is the demo?"}},
        {"kind": "ACTION_RESOLVED", "sim_time_ms": 3000, "actor_id": "robot_r",
         "payload": {"request": {"agent_id": "robot_r", "action": "MOVE_TO", "args": {"target_id": "anon_aaaaaaaaaa"}},
                     "result": {"accepted": True, "reason_code": "OK"}}},
        {"kind": "ACTION_RESOLVED", "sim_time_ms": 3500, "actor_id": "robot_r",
         "payload": {"request": {"agent_id": "robot_r", "action": "GESTURE", "args": {"gesture": "WAVE"}},
                     "result": {"accepted": False, "reason_code": "RATE_LIMITED"}}},
        {"kind": "INTERVENTION", "sim_time_ms": 4000, "actor_id": None,
         "payload": {"status": "APPLIED", "reason": None, "intervention": {
             "operation": "EDIT_DIRECTIVE", "target_id": "robot_r", "args": {"field": "directive"}, "after": "Stay at your post."}}},
        {"kind": "EXPRESSION_SHOWN", "sim_time_ms": 4500, "actor_id": "robot_r",
         "payload": {"avatar_id": "robot_r", "expression_id": "ambient_waiting"}},
        {"kind": "RUN_ENDED", "sim_time_ms": 90000, "actor_id": None, "payload": {}},
    ])
    _write(run / "sidecar" / "decision_records.jsonl", [
        {"decision_id": "d1", "agent_id": "robot_r", "based_on_tick_id": 300,
         "fallback": {"action": "WAIT", "reason": "TIMEOUT"}, "model_calls": [{"outcome": "TIMEOUT"}]},
        {"decision_id": "d2", "agent_id": "robot_r", "based_on_tick_id": 600,
         "fallback": {"action": "WAIT", "reason": "FN1_HELD"},
         "model_calls": [{"outcome": "INVALID_OUTPUT", "error": "you are in a conversation with anon_aaaaaaaaaa",
                          "response_text": json.dumps({"actions": [
                              {"action": "SPEAK", "args": {"addressee_id": "P1", "text": "Follow me to the platform."}},
                              {"action": "MOVE_TO", "args": {"destination": {"x": 22.0, "z": 7.0}}}]})}]},
        {"decision_id": "d3", "agent_id": "robot_r", "based_on_tick_id": 700, "fallback": None, "model_calls": []},
    ])
    _write(run / "sidecar" / "prompts.jsonl", [{"decision_id": "d2", "prompt": "...", "handles": {"P1": "anon_aaaaaaaaaa"}}])
    (run / "viewer").mkdir(parents=True)
    (run / "viewer" / "truth_tracks.json").write_text(json.dumps({"robot_r": {"anon_aaaaaaaaaa": "visitor_x"}}),
                                                      encoding="utf-8")
    return run


def test_the_run_reads_in_order_with_real_names(tmp_path):
    lines = transcript.build(_run(tmp_path))
    body = [ln for ln in lines if " s  " in ln]
    text = "\n".join(body)
    assert "visitor_x → robot_r [LOCAL]: “Where is the demo?”" in text
    assert "robot_r walks toward visitor_x" in text                       # an anonymous track named by truth
    assert "robot_r: GESTURE refused (RATE_LIMITED)" in text
    assert "[DIRECTOR] APPLIED: robot_r's directive is now “Stay at your post.”" in text
    assert "robot_r took too long to decide (deadline missed) → waited" in text
    # The held decision says what the robot wanted, with its P1 handle named.
    assert "held. It wanted: SPEAK visitor_x “Follow me to the platform.”; MOVE_TO to (22.0, 7.0)" in text
    assert "ambient_waiting" not in text                                  # ambient displays only with --all
    times = [float(ln.split(" s ")[0]) for ln in body]
    assert times == sorted(times)


def test_all_and_agent_filters(tmp_path):
    run = _run(tmp_path)
    assert any("ambient_waiting" in ln for ln in transcript.build(run, show_all=True))
    only_x = "\n".join(transcript.build(run, only="visitor_x"))
    assert "Where is the demo?" in only_x and "took too long" not in only_x and "[DIRECTOR]" in only_x


def test_main_writes_the_file(tmp_path, capsys):
    run = _run(tmp_path)
    assert transcript.main([str(run)]) == 0
    assert (run / "transcript.md").is_file() and "Where is the demo?" in capsys.readouterr().out
