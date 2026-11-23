"""G3d measurement tooling (D-69): frame pacing, peak VRAM, the per-run report, the bake-off's
render-tax and pulse on/off tables, and the command lines. No Godot, no GPU."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from range_service.eval import bakeoff as bk
from range_service.eval.run_report import FRAME_TARGET_MS, VramSampler, frame_summary, run_report
from range_service.eval.runner import RunOptions, godot_command

SCEN = {"cast": {"robot_r": {}, "visitor_x": {}}}


def _frames(tmp: Path, frame_ms: list[float], server: str = "X11") -> Path:
    path = tmp / "frames.json"
    path.write_text(json.dumps({"frame_ms": frame_ms, "display_server": server, "rendering_method": "forward_plus",
                                "window_size": [1920, 1080], "max_fps": 60, "vsync_mode": 1,
                                "godot_video_mem_peak_mib": 812.5}), encoding="utf-8")
    return path


def test_frame_summary_reports_tails_and_spikes_against_the_target(tmp_path):
    frames = [500.0] + [16.6] * 900 + [17.5] * 80 + [40.0] * 20         # first second is loading: skipped
    s = frame_summary(_frames(tmp_path, frames))
    assert s["available"] and s["skipped_start_frames"] == 32           # 500 ms + 31 frames = the first second
    assert s["p50_ms"] == 16.6 and s["p95_ms"] == 17.5 and s["p99_ms"] == 40.0 and s["spikes"] == 20
    assert s["meets_target"] is False and s["target_p95_ms"] == round(FRAME_TARGET_MS, 1)
    assert frame_summary(_frames(tmp_path, [16.0] * 200))["meets_target"] is True
    assert frame_summary(_frames(tmp_path, [1.0] * 2000, "headless"))["meets_target"] is None   # headless: no claim
    assert frame_summary(tmp_path / "none.json")["available"] is False


def test_vram_sampler_says_why_when_nothing_can_be_read():
    async def go():
        v = VramSampler(every_s=0.01)
        v.start()
        await asyncio.sleep(0.05)
        await v.stop()
        return v.summary()
    s = asyncio.run(go())
    assert (s["peak_mib"] is None and s["reason"]) or (s["peak_mib"] is not None and s["samples"] >= 1)


def _ev(kind, t, actor, payload):
    return {"kind": kind, "sim_time_ms": t, "actor_id": actor, "payload": payload}


def _resolved(t, rid, action, accepted=True):
    return _ev("ACTION_RESOLVED", t, "robot_r", {"request": {"action": action, "action_request_id": rid, "args": {}},
                                                 "result": {"action_request_id": rid, "agent_id": "robot_r",
                                                            "accepted": accepted, "reason_code": "OK" if accepted else "STALE_OBSERVATION"}})


def _say(t, who, to, text):
    return _ev("SPEECH_EMITTED", t, who, {"avatar_id": who, "addressee_id": to, "text": text})


def test_run_report_counts_offered_accepted_latency_and_fn1(tmp_path):
    (tmp_path / "sidecar").mkdir()
    rec = {"agent_id": "robot_r", "fallback": {"action": "WAIT", "reason": "TIMEOUT"},
           "model_calls": [{"outcome": "TIMEOUT", "timings": {"total_ms": 4000}}]}
    (tmp_path / "sidecar" / "decision_records.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    (tmp_path / "sidecar" / "delivery.jsonl").write_text(
        json.dumps({"agent_id": "robot_r", "event": "DISCARDED", "reason": "TARGET_NOT_PERCEIVED"}) + "\n", encoding="utf-8")
    journal = [_say(1000, "visitor_x", "robot_r", "Where is the demo?"), _resolved(1200, "a1", "SPEAK"),
               _say(1200, "robot_r", "visitor_x", "On the platform."), _resolved(1300, "a2", "LOOK_AT"),
               _resolved(5000, "a3", "MOVE_TO"),                                        # left without a goodbye
               _say(9000, "robot_r", "visitor_x", "Excuse me, I need to go."), _resolved(9100, "a4", "MOVE_TO"),
               _resolved(9200, "a5", "SPEAK", accepted=False)]
    r = run_report(tmp_path, journal, ["robot_r"])["robot_r"]
    assert r["actions"] == {"offered": 5, "accepted": 4, "refused": 1, "dropped_before_send": 1,
                            "dropped_before_send_by_reason": {"TARGET_NOT_PERCEIVED": 1}}
    assert r["response_latency_ms"]["p50"] == 200 and r["response_latency_ms"]["unanswered"] == 0
    assert r["model_calls"] == 1 and r["timeouts"] == 1 and r["fallbacks"] == {"TIMEOUT": 1}
    assert r["glances_accepted"] == 1
    assert r["fn1"] == {"departures_mid_conversation": 2, "with_goodbye_first": 1, "without_goodbye": 1}


def test_rendered_runs_declare_resolution_and_preset_and_record_frames(tmp_path):
    opts = RunOptions("SB04_POLITE_BID", "godot", mode="LIVE", headless=False, resolution="2560x1440",
                      render_preset="v0_compat")
    cmd = godot_command(opts, SCEN, tmp_path, 1234, 7)
    assert cmd[cmd.index("--resolution") + 1] == "2560x1440" and cmd[cmd.index("--max-fps") + 1] == "60"
    assert "gl_compatibility" in cmd and any(a.startswith("--frame-stats=") for a in cmd)
    headless = godot_command(RunOptions("SB04_POLITE_BID", "godot"), SCEN, tmp_path, 1234, 7)
    assert "--resolution" not in headless and not any(a.startswith("--frame-stats=") for a in headless)


def _row(mode, p50, p95, npm, pulse=True, render=None):
    return {"label": "F3 gemma Q4", "npc_label": "N3", "mode": mode, "pulse": pulse, "render": render, "decisions": 9,
            "p50_ms": p50, "p95_ms": p95, "npc_calls_per_min": npm, "timeouts": 0, "robot_actions_accepted": 20,
            "frame_p95_ms": 15.0 if render else None}


def test_bakeoff_tables_compare_headless_with_rendered_and_pulse_on_with_off():
    f = lambda v: "–" if v is None else str(v)   # noqa: E731
    tax = bk.render_tax_lines([_row("LIVE", 2000, 3000, 10.0), _row("LIVE_RENDERED", 2200, 3300, 9.0, render="1920x1080 v0")], f)
    assert any("+10%" in line and "-10%" in line for line in tax)
    ab = bk.pulse_ab_lines([_row("LIVE", 2000, 3000, 10.0), _row("LIVE", 2100, 2900, 10.0, pulse=False)], f)
    assert len(ab) == 6 and "2000 / 3000 | 2100 / 2900" in ab[-1]
