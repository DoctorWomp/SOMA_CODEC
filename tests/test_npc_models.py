"""Model-driven NPCs (G3c-1, D-51, D-59): routing, own private goal, persona prefixes,
pre-warming signals, promotion records and the canary scanner. No Godot, no model."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from range_service.agents.cognition import CognitionLevel, Signals
from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import FakeModel, ModelGateway
from range_service.agents.runmodels import models_from_specs, resolve_npc_spec
from range_service.eval import canary
from tests.agent_helpers import CONFIGS, Scene

SB04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
ROBOT_TRACK, X_TRACK = "anon_r0b0tr0b0t", "anon_xxxxxxxxx1"


class Recorder(FakeModel):
    """A fake model that keeps every request (to check what each agent was sent)."""


def _runtimes(npc=True):
    focal, npcgw = ModelGateway(Recorder()), ModelGateway(Recorder()) if npc else None
    return build_runtimes(SB04, CONFIGS, gateway=focal, npc_gateway=npcgw), focal, npcgw


def test_robot_r_gets_the_focal_gateway_and_npcs_the_npc_gateway():
    rts, focal, npc = _runtimes()
    assert rts["robot_r"].gateway is focal and not rts["robot_r"].npc_model
    assert rts["visitor_x"].gateway is npc and rts["visitor_y"].gateway is npc
    assert rts["visitor_x"].npc_model and rts["visitor_y"].npc_model


def test_own_private_goal_only_in_its_own_identity():
    rts, _, _ = _runtimes()
    goals = {p["persona_id"]: p.get("private_goal") for p in CONFIGS.items["personas"].values()}
    assert rts["visitor_x"].identity.own_private_goal == goals["visitor_x"]
    assert rts["visitor_y"].identity.own_private_goal == goals["visitor_y"]
    assert rts["robot_r"].identity.own_private_goal is None
    # Without an NPC model nobody's prompt carries a private goal (G3a behavior kept).
    plain, _, _ = _runtimes(npc=False)
    assert all(rt.identity.own_private_goal is None for rt in plain.values())


def test_own_goal_without_a_model_is_refused():
    from range_service.agents.runtime import AgentRuntime   # noqa: PLC0415

    rts, _, _ = _runtimes(npc=False)
    rt = rts["visitor_x"]
    with pytest.raises(ValueError, match="D-51"):
        AgentRuntime("visitor_x", persona={"display_name": "X", "role": "r", "public_goal": "g", "cognition_level": "C2",
                                           "allowed_actions": ["WAIT"]}, body=rt.body, directive="d", expressions=[],
                     setting=[], own_private_goal="secret plan")


def _drive(rt, scene, packets=1):
    jobs = []
    for _ in range(packets):
        job = rt.observe(scene.packet())
        if job is not None:
            jobs.append(job)
            if job.proposals is None:
                asyncio.run(rt.decide(job))
            else:
                rt.decide_now(job)
    return jobs


def test_c1_and_c2_npcs_decide_through_the_model_c0_stays_a_routine():
    rts, _, npc = _runtimes()
    x = rts["visitor_x"]
    s = Scene(observer="visitor_x", pose={"x": 15.0, "y": 0.0, "z": 8.5, "yaw_rad": 0.0})
    jobs = _drive(x, s.see(ROBOT_TRACK, 15, 10))                 # START, robot within 3 m: C0 -> C1
    assert x.cognition.level == "C1" and jobs[0].policy == "MODEL" and jobs[0].tier == "C1"
    for i in range(2):
        jobs = _drive(x, s.see(ROBOT_TRACK, 15, 10).hear(ROBOT_TRACK, f"Hello {i}?"))
    assert x.cognition.level == "C2" and jobs[-1].policy == "MODEL" and jobs[-1].tier == "C2"
    sent = [r.prompt for r in npc.provider.calls]
    assert sent and all(p.startswith(x.persona_prefix(t)[1]) for p, t in
                        zip(sent, [c.tier for c in npc.provider.calls]))
    assert all(r.prefix_key == x.persona_prefix(r.tier)[0] for r in npc.provider.calls)
    y = rts["visitor_y"]
    far = Scene(observer="visitor_y", pose={"x": 2.0, "y": 0.0, "z": 2.0, "yaw_rad": 0.0})
    jobs = _drive(y, far.see(ROBOT_TRACK, 20, 20))                # nobody near: C0 routine
    assert y.cognition.level == "C0" and all(j.policy == "ROUTINE" for j in jobs)


def test_persona_prefix_is_stable_from_call_to_call():
    rts, _, npc = _runtimes()
    x = rts["visitor_x"]
    first = x.persona_prefix("C2")
    s = Scene(observer="visitor_x", pose={"x": 15.0, "y": 0.0, "z": 8.5, "yaw_rad": 0.0})
    for i in range(4):
        _drive(x, s.see(ROBOT_TRACK, 15, 10).hear(ROBOT_TRACK, f"Question {i} about the demo?"))
    assert x.persona_prefix("C2") == first
    c2 = [r for r in npc.provider.calls if r.tier == "C2"]
    assert len(c2) >= 2 and all(r.prompt.startswith(first[1]) for r in c2)
    assert "Your own private goal (known only to you): " in first[1]
    assert x.persona_prefix("C1")[0] != first[0]                 # C1 has its own (shorter) prefix


def test_likely_promotion_asks_for_a_prewarm_once():
    c = CognitionLevel("C2")
    assert c.likely_next(Signals(now_ms=0, focal_within_far=True)) == "C1"
    assert c.likely_next(Signals(now_ms=0, focal_within_far=True, near_focal=True)) is None   # promotes at once
    c.update(Signals(now_ms=0, addressed=True))
    assert c.level == "C1" and c.likely_next(Signals(now_ms=100)) == "C2"                      # addressed once
    assert CognitionLevel("C1").likely_next(Signals(now_ms=0, focal_within_far=True)) == "C1"
    assert CognitionLevel("C0").likely_next(Signals(now_ms=0, focal_within_far=True)) is None  # ceiling C0
    rts, _, _ = _runtimes()
    y = rts["visitor_y"]
    s = Scene(observer="visitor_y", pose={"x": 15.0, "y": 0.0, "z": 5.0, "yaw_rad": 0.0})
    _drive(y, s.see(ROBOT_TRACK, 15, 10))                         # 5 m away: C1 likely
    wanted = y.take_prewarms()
    assert [(t, k) for t, k, _ in wanted] == [("C1", y.persona_prefix("C1")[0])]
    _drive(y, s.see(ROBOT_TRACK, 15, 10))
    assert y.take_prewarms() == []                                # asked once only
    off, _, _ = build_runtimes(SB04, CONFIGS, npc_gateway=ModelGateway(FakeModel()), prewarm=False), None, None
    _drive(off["visitor_y"], Scene(observer="visitor_y", pose={"x": 15.0, "y": 0.0, "z": 5.0, "yaw_rad": 0.0})
           .see(ROBOT_TRACK, 15, 10))
    assert off["visitor_y"].take_prewarms() == []


def test_promotion_record_runs_to_the_first_validated_action():
    rts, _, _ = _runtimes()
    x = rts["visitor_x"]
    s = Scene(observer="visitor_x", pose={"x": 15.0, "y": 0.0, "z": 8.5, "yaw_rad": 0.0})
    job = x.observe(s.see(ROBOT_TRACK, 15, 10).packet())
    requests = asyncio.run(x.decide(job))
    rec = x.promotions[0]
    assert rec["from"] == "C0" and rec["to"] == "C1" and rec["status"] == "OPEN" and rec["first_decision_tick"] == job.tick
    assert rec["first_model_call"]["outcome"] == "VALID"
    x.on_result({"action_request_id": requests[0]["action_request_id"], "accepted": True, "reason_code": "OK",
                 "resolved_at_tick_id": job.tick + 1})
    done = x.promotion_records()[0]
    assert done["status"] == "VALIDATED" and isinstance(done["first_validated_action_ms"], int)
    assert "_t0" not in done and "_requests" not in done
    assert json.dumps(done)


def test_npc_spec_follows_the_robot_model():
    assert resolve_npc_spec("none", "auto") == "none"
    assert resolve_npc_spec("fake-slow:2000", "auto") == "fake"
    assert resolve_npc_spec("replay:runs/x.jsonl", "auto") == "replay:runs/x.jsonl"
    assert resolve_npc_spec("llama:F3", "auto") == "llama:F3"
    assert resolve_npc_spec("fake", "none") == "none"
    m = models_from_specs("fake", "auto")
    assert m.focal is not None and m.npc is not None and m.npc is not m.focal and m.option == "SEPARATE"
    assert models_from_specs("none").npc is None
    attached = models_from_specs("llama-attach:9", "auto")
    assert attached.npc is attached.focal and attached.option == "B"
    with pytest.raises(ValueError):
        models_from_specs("llama", "fake")


def test_llama_npc_model_choice(monkeypatch):
    from range_service.agents import inference as infmod   # noqa: PLC0415
    from range_service.agents import runmodels   # noqa: PLC0415

    seen = []
    monkeypatch.setattr(infmod, "build_inference", lambda focal, npc, **kw: seen.append((focal, npc)) or
                        type("I", (), {"focal": type("S", (), {"gateway": ModelGateway(FakeModel())})()})())
    monkeypatch.setattr(runmodels, "_is_llama", runmodels._is_llama)
    for npc_model, want in (("auto", ("T1", None)), ("llama", ("T1", None)), ("llama:T1", ("T1", "T1")),
                            ("llama:N1", ("T1", "N1")), ("none", ("T1", "none"))):
        seen.clear()
        models_from_specs("llama:T1", npc_model)
        assert seen == [want], npc_model


# ---------- the canary scanner itself: it must catch a planted leak ----------

def _run_dir(tmp: Path, prompts: list[dict], extra: dict[str, str] | None = None) -> Path:
    side = tmp / "sidecar"
    side.mkdir(parents=True)
    (side / "prompts.jsonl").write_text("".join(json.dumps(p) + "\n" for p in prompts))
    for name, text in (extra or {}).items():
        (tmp / name).write_text(text)
    return tmp


def test_canary_scanner_catches_leaks_and_needs_the_positive_control(tmp_path):
    marked, goals, labels = canary.marked_configs(CONFIGS)
    gx, gy, lab = goals["visitor_x"], goals["visitor_y"], labels["SB04_POLITE_BID"]
    assert gx in marked.items["personas"]["visitor_x"]["private_goal"] and gx not in str(CONFIGS.items["personas"])
    personas = {"robot_r": "robot_r", "visitor_x": "visitor_x", "visitor_y": "visitor_y"}
    npcs = {"visitor_x", "visitor_y"}
    own = lambda g: f"## IDENTITY\nYou are V.\n{canary.OWN_GOAL_LABEL}Wait. ({g})\n## DECISION\n"   # noqa: E731
    clean = _run_dir(tmp_path / "clean", [{"agent_id": "visitor_x", "prompt": own(gx)},
                                          {"agent_id": "visitor_y", "prompt": own(gy)},
                                          {"agent_id": "robot_r", "prompt": "## IDENTITY\nYou are Robot R."}])
    assert canary.scan_run(clean, personas, goals, labels, npcs) == []
    leaks = _run_dir(tmp_path / "leak", [{"agent_id": "visitor_x", "prompt": own(gx) + f"heard: {gy}"},
                                         {"agent_id": "visitor_y", "prompt": own(gy)},
                                         {"agent_id": "robot_r", "prompt": f"## FACTS\n{gx}"}],
                     {"journal.jsonl": json.dumps({"text": lab}) + "\n"})
    found = canary.scan_run(leaks, personas, goals, labels, npcs)
    assert any("visitor_x's context holds the marker of visitor_y" in f for f in found)
    assert any("robot_r's context holds the marker of visitor_x" in f for f in found)
    assert any(f.startswith("journal.jsonl") for f in found)
    missing = _run_dir(tmp_path / "missing", [{"agent_id": "visitor_x", "prompt": "## IDENTITY\nno goal"}])
    assert any("proves nothing" in f for f in canary.scan_run(missing, personas, goals, labels, npcs))


def test_observer_filter_check_catches_tracks_an_agent_never_perceived(tmp_path):
    run = _run_dir(tmp_path, [{"agent_id": "visitor_x", "prompt": f"- {X_TRACK}: OBSERVED\n- anon_zzzzzzzzzz: OBSERVED"},
                              {"agent_id": "visitor_y", "prompt": "robot_r is over there"}])
    packet = {"type": "world.observation", "payload": {"observer_id": "visitor_x",
                                                       "observations": [{"track_id": X_TRACK}]}}
    (run / "sidecar" / "sidecar_received.jsonl").write_text(json.dumps(packet) + "\n")
    found = canary.observer_filter_problems(run, ["robot_r", "visitor_x", "visitor_y"])
    assert any("never perceived" in f and "anon_zzzzzzzzzz" in f for f in found)
    assert any("names robot_r by its real id" in f for f in found)


def test_c1_prompt_has_argument_formats_observations_and_real_choices():
    """G3c-2 (D-60): a C1 NPC sees how to write each action and who is near (its own senses only),
    and its answer can only name tracks it perceives."""
    rts, _, npc = _runtimes()
    x = rts["visitor_x"]
    s = Scene(observer="visitor_x", pose={"x": 15.0, "y": 0.0, "z": 8.5, "yaw_rad": 0.0})
    job = x.observe(s.see(ROBOT_TRACK, 15, 10).packet())
    assert job.tier == "C1"
    prompt = job.assembled.prompt
    assert 'MOVE_TO {"destination"' in prompt and "## OBSERVATIONS" in prompt and ROBOT_TRACK in prompt
    assert job.choices["targets"] == [ROBOT_TRACK] and job.choices["channels"] == ["LOCAL"]
    asyncio.run(x.decide(job))
    assert x.prompts[-1]["choices"] == job.choices
    assert job.assembled.record["total_tokens"] <= job.assembled.record["budget_tokens"]


def test_other_server_busy_time_is_measured_per_call():
    import time

    from range_service.agents.gateway import ServerActivity

    a = ServerActivity()
    t0 = time.perf_counter()
    focal = a.begin("focal")
    time.sleep(0.05)
    npc_start = time.perf_counter()
    time.sleep(0.05)
    a.end(focal)
    time.sleep(0.03)
    busy = a.other_busy_ms("npc", npc_start, time.perf_counter())
    assert 40 <= busy <= 70                                  # only the overlap with Robot R's call
    assert a.other_busy_ms("focal", t0, time.perf_counter()) == 0
