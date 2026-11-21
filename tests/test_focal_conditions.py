"""G3f (D-75 to D-78): Robot R on time under load. The persona prefix with the pulse on, Robot R's
prompt-layout and answer conditions, the focal-first GPU guard, and the bake-off's run folders.
No Godot, no real model."""

from __future__ import annotations

import asyncio

from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import FakeModel, ModelGateway
from tests.agent_helpers import CONFIGS, Scene

SB04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
ROBOT_TRACK, X_TRACK = "anon_r0b0tr0b0t", "anon_xxxxxxxxx1"
PULSE = CONFIGS.items["pulse"]["pulse"]


class Recorder(FakeModel):
    """A fake model that keeps every request."""


def _drive(rt, scene, packets=1):
    for _ in range(packets):
        job = rt.observe(scene.packet())
        if job is not None:
            if job.proposals is None:
                asyncio.run(rt.decide(job))
            else:
                rt.decide_now(job)


def test_with_the_pulse_on_every_prompt_starts_with_its_persona_prefix():
    """Reproduced on main: with the pulse on (every run with a model), the prompt's guardrails carry
    the activity format but the persona prefix did not, so no prompt started with its prefix. NPC
    prompts then went as one message (not system + user), and snapshots and pre-warms cached a
    prefix the real prompts never used (G3f, D-76)."""
    focal, npc = ModelGateway(Recorder()), ModelGateway(Recorder())
    rts = build_runtimes(SB04, CONFIGS, gateway=focal, npc_gateway=npc, pulse=PULSE)
    x, r = rts["visitor_x"], rts["robot_r"]
    s = Scene(observer="visitor_x", pose={"x": 15.0, "y": 0.0, "z": 8.5, "yaw_rad": 0.0})
    for i in range(3):
        _drive(x, s.see(ROBOT_TRACK, 15, 10).hear(ROBOT_TRACK, f"Hello {i}, where is the demo?"))
    rs = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    for i in range(2):
        _drive(r, rs.see(X_TRACK, 15, 8.5).hear(X_TRACK, f"Question {i} about the demo?"))
    assert npc.provider.calls and focal.provider.calls
    for call in npc.provider.calls:
        assert call.prompt.startswith(x.persona_prefix(call.tier)[1]), call.tier
        assert call.prefix is not None and call.prompt.startswith(call.prefix)
    for call in focal.provider.calls:
        assert call.prompt.startswith(r.persona_prefix("FOCAL")[1])
        assert call.prefix is None                       # Robot R: one message unless SYSTEM_PREFIX


# ---------- the bake-off harness (D-75) ----------

import json   # noqa: E402
from pathlib import Path   # noqa: E402

import pytest   # noqa: E402

from range_service.eval import bakeoff as bk   # noqa: E402
from range_service.eval import live_diag   # noqa: E402
from range_service.eval.runner import RunError, clear_previous_run   # noqa: E402


def _call(outcome="VALID", attempt=0, error=None, total=2000, prefill=500, gen=1400, prompt=2000, cached=0, generated=130,
          busy=None):
    c = {"outcome": outcome, "attempt": attempt, "error": error, "response_text": "{}" if outcome != "TIMEOUT" else None,
         "timings": {"queue_ms": 0, "prefill_ms": prefill if outcome != "TIMEOUT" else None,
                     "generation_ms": gen if outcome != "TIMEOUT" else None, "total_ms": total},
         "prompt_tokens": prompt if outcome != "TIMEOUT" else None, "cached_tokens": cached if outcome != "TIMEOUT" else None,
         "generated_tokens": generated if outcome != "TIMEOUT" else None}
    if busy is not None:
        c["other_server_busy_ms"] = busy
    return c


def _rec(agent, n, calls, fallback=None, triggers=("ADDRESSED_SPEECH",), tokens=1900):
    return {"decision_id": f"dec_{agent}_{n:06d}", "agent_id": agent, "triggers": list(triggers), "model_calls": calls,
            "fallback": fallback, "context": {"total_tokens": tokens}}


def test_appended_runs_are_split_and_counted_apart():
    """The owner's 2026-11-19 baseline rows: a second run into the same folder appended its records
    (F3 alone LIVE = 69 calls = the earlier F3+N3 run's 36 + its own 33). split_runs finds the restart."""
    first = [_rec("robot_r", i, [_call()]) for i in range(1, 4)] + [_rec("visitor_x", 1, [_call()])]
    second = [_rec("robot_r", i, [_call("TIMEOUT", total=4010)]) for i in range(1, 3)]
    segs = live_diag.split_runs(first + second)
    assert [len(s) for s in segs] == [4, 2] and live_diag.pooled(first + second) and not live_diag.pooled(first)
    assert live_diag.robot_breakdown(segs[1])["outcomes"]["TIMEOUT_AT_MODEL"] == 2


def test_robot_breakdown_by_outcome_and_cost():
    recs = [
        _rec("robot_r", 1, [_call(cached=1200, busy=1000)]),
        _rec("robot_r", 2, [_call("INVALID_OUTPUT", error="the answer was cut off at the 200-token limit (x)", generated=200),
                            _call(attempt=1)]),
        _rec("robot_r", 3, [_call("INVALID_OUTPUT", error="you are in a conversation with anon_x: say the closing line first; "
                                  "not repaired: 100 ms of the decision deadline left, a repair needs about 2000 ms")],
             fallback={"action": "WAIT", "reason": "INVALID_OUTPUT"}),
        _rec("robot_r", 4, [_call("TIMEOUT", error="no answer within 4000 ms", total=4005, busy=3000)],
             fallback={"action": "WAIT", "reason": "TIMEOUT"}, triggers=("PULSE_REVIEW",), tokens=2400),
        _rec("robot_r", 5, [_call("TIMEOUT", error="dropped before reaching the model: stale", total=3800)],
             fallback={"action": "WAIT", "reason": "TIMEOUT"}),
        _rec("visitor_x", 1, [_call("TIMEOUT")]),
    ]
    b = live_diag.robot_breakdown(recs, [{"agent_id": "robot_r", "event": "DISCARDED"}, {"agent_id": "visitor_x", "event": "DISCARDED"}])
    assert b["calls"] == 6 and b["decisions"] == 5 and b["decisions_pulse_review"] == 1
    assert b["outcomes"] == {"VALID_FIRST_TRY": 1, "VALID_AFTER_REPAIR": 1, "TIMEOUT_IN_QUEUE": 1, "TIMEOUT_AT_MODEL": 1,
                             "INVALID_OUTPUT": 2, "PROVIDER_ERROR": 0, "OTHER": 0}
    assert b["invalid_kinds"] == {"FN1_RULE": 1, "TRUNCATED": 1} and b["invalid_not_repaired"] == 1
    assert b["fallbacks_by_reason"] == {"INVALID_OUTPUT": 1, "TIMEOUT": 2} and b["timeouts_on_pulse_reviews"] == 1
    assert b["dropped_before_send"] == 1 and b["at_output_cap"] == 1 and b["context_tokens_p95"] == 2400
    assert b["cache_share"] == round(1200 / 8000, 2) and b["other_server_busy_share_timeouts"] == round(3000 / 4005, 2)


@pytest.mark.parametrize("error,kind", [
    ('activity target "anon_q" is not a track you perceive', "ACTIVITY_RULE"),
    ('"review_after_s" must be a whole number of seconds from 5 to 120', "ACTIVITY_RULE"),
    ("the answer is not valid JSON", "FORMAT"), ("action 1 (MOVE_TO): bad", "ARGS"), ("TRAVEL_TO needs a target_id (someone)", "ACTIVITY_RULE"),
])
def test_invalid_kinds(error, kind):
    assert live_diag.classify_error(error) == kind


def test_a_run_folder_is_cleared_of_an_earlier_run_and_only_of_what_a_run_writes(tmp_path):
    run = tmp_path / "run_F3_live_1"
    (run / "sidecar").mkdir(parents=True)
    (run / "sidecar" / "decision_records.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    (run / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    (run / "godot.log").write_text("x", encoding="utf-8")
    (run / "notes.txt").write_text("mine", encoding="utf-8")
    removed = clear_previous_run(run)
    assert sorted(removed) == ["godot.log", "journal.jsonl", "sidecar"]
    assert (run / "notes.txt").read_text(encoding="utf-8") == "mine" and not (run / "sidecar").exists()
    assert clear_previous_run(run) == [] and clear_previous_run(tmp_path / "missing") == []


def test_a_replay_source_inside_the_run_folder_is_never_cleared(tmp_path):
    run = tmp_path / "r"
    (run / "sidecar").mkdir(parents=True)
    src = run / "sidecar" / "decision_records.jsonl"
    src.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RunError, match="replay from a copy"):
        clear_previous_run(run, keep=(src,))
    assert src.is_file()


def _live(label, npc, mode, run_dir, harness=None, **kw):
    row = {"label": label, "npc_label": npc, "mode": mode, "repeats": 3, "option": "C", "ok": True, "decisions": 30,
           "timeouts": 1, "fallbacks": 2, "p50_ms": 2000.0, "p95_ms": 3500.0, "run_dir": run_dir}
    if harness:
        row["harness"] = harness
    row.update(kw)
    return row


def test_report_leaves_out_void_rows_and_marks_pooled_ones(tmp_path):
    results = {"offline": [], "live": [
        {"label": "F3 old", "mode": "LIVE", "decisions": 2, "timeouts": 0, "fallbacks": 0, "p50_ms": 1, "p95_ms": 2,
         "ok": True, "run_dir": "G:\\x\\run_F3_live"},                                   # pre-G3c-2: no repeats
        _live("F3 a", "N3", "LIVE", "G:\\x\\run_F3_live_1"),
        _live("F3 b", "none", "LIVE", "G:\\x\\run_F3_live_1"),                           # same folder: pooled
        _live("F3 c", "N3", "LIVE_LOAD", "G:\\x\\run_F3_n3_live_load_1", harness="g3f", timeouts=0, p95_ms=3900.0,
              conditions={"prompt_layout": "SYSTEM_PREFIX", "answer": "SHORT", "gpu_guard": True, "npc_cap": 0},
              robot=live_diag.robot_breakdown([_rec("robot_r", 1, [_call()])]))]}
    _, m = bk.write_report(results, tmp_path)
    text = m.read_text(encoding="utf-8")
    assert "F3 old" not in text and "1 live row(s) from the pre-G3c-2 harness are left out" in text
    assert "| F3 b (POOLED: with F3+N3 LIVE) |" in text and "| F3 a | N3 | LIVE |" in text
    assert "F3 c [SYSTEM_PREFIX, answer SHORT, GPU guard cap 0]" in text
    assert "### Robot R's calls: outcomes and where the time goes (G3f)" in text
    # G3g (D-87): the target table counts fallback decisions; G3f's timeout target stays as a column.
    # G3h (D-110, owner 2026-11-21): LIVE is judged; LIVE_LOAD is a stress test, reported, not judged;
    # decisions held by FN-1 and activities dropped with the actions kept have their own columns.
    target = text[text.index("### Target (D-87, D-110)"):]
    assert "F3 b" not in target
    assert "| 3900.0 | 0/1 (0%) | 0 | 0 | 0/30 (0%) | 0 | stress: reported, not judged | – |" in target
    assert "| 3500.0 | – | – | – | 1/30 (3%) | – | – | met |" in target           # no breakdown: not judged


def test_numbers_are_not_printed_as_percentages():
    """Before G3f any float <= 1 printed as a percentage: a 0.0 ms queue read "0%", 0.03 ms frames "3%"."""
    assert bk.fmt(0.0) == "0.0" and bk.fmt(0.03) == "0.03" and bk.pct(0.43) == "43%" and bk.fmt(None) == "–"


# ---------- the focal-first GPU guard (D-78) ----------

from range_service.agents.scheduler import FocalGuard, SlotScheduler   # noqa: E402


def test_guard_holds_npc_calls_while_robot_r_thinks_background_first():
    async def run():
        guard = FocalGuard(npc_cap=1)
        npc = SlotScheduler(4, pinned_tiers=(), reserved=0)
        npc.set_guard(guard)
        far = asyncio.get_running_loop().time() + 60
        guard.focal_begin()                                   # Robot R's call is in flight
        bg = asyncio.create_task(npc.acquire("visitor_a", "C2", far, background=True))
        real1 = asyncio.create_task(npc.acquire("visitor_b", "C2", far))
        real2 = asyncio.create_task(npc.acquire("visitor_c", "C1", far))
        await asyncio.sleep(0.01)
        assert real1.done() and not real2.done() and not bg.done()   # one real call (the cap); background held
        assert guard.stats["deferred"] >= 2 and guard.stats["deferred_background"] == 1
        assert npc.try_acquire("visitor_d") is None                  # no pre-warm while Robot R thinks
        guard.focal_end()                                            # Robot R done: the queue is served
        await asyncio.sleep(0.01)
        assert real2.done() and bg.done()
        assert real2.result() != bg.result()
    asyncio.run(run())


def test_a_held_npc_call_still_times_out_at_its_own_deadline():
    """The guard never makes an NPC call wait past its deadline: the gateway's timeout cancels it
    in the queue and the agent WAITs, as for any late call (T25)."""
    async def run():
        guard = FocalGuard(npc_cap=0)
        npc = ModelGateway(FakeModel(), deadlines_ms={"C2": 150}, scheduler=SlotScheduler(4, pinned_tiers=(), reserved=0),
                           server="npc")
        npc.scheduler.set_guard(guard)
        guard.focal_begin()
        result = await npc.decide(agent_id="visitor_a", tier="C2", prompt="p", prompt_sha256="0" * 64, max_tokens=10,
                                  allowed_actions=["WAIT"], tick=1)
        assert result.fallback == {"action": "WAIT", "reason": "TIMEOUT"} and npc.scheduler.waiting == []
        guard.focal_end()
    asyncio.run(run())


def test_robot_r_gateway_marks_the_guard_busy_only_during_its_calls():
    seen = []

    class Probe(FakeModel):
        async def complete(self, request):
            seen.append(guard.focal_in_flight)
            return await super().complete(request)
    guard = FocalGuard()
    focal = ModelGateway(Probe(), scheduler=SlotScheduler(2), server="focal")
    focal.guard = guard
    asyncio.run(focal.decide(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=10,
                             allowed_actions=["WAIT"], tick=1))
    assert seen == [1] and guard.focal_in_flight == 0 and guard.stats["focal_calls"] == 1


def test_short_answer_condition_limits_robot_rs_text_and_layout_sends_the_prefix():
    from range_service.agents.output_schema import answer_schema

    full = answer_schema(("SPEAK", "WAIT"), None, ("LOCAL",), "FOCAL")
    short = answer_schema(("SPEAK", "WAIT"), None, ("LOCAL",), "FOCAL_SHORT")
    assert full["properties"]["reason_summary"]["maxLength"] == 300 and short["properties"]["reason_summary"]["maxLength"] == 60
    assert '"maxLength": 200' in json.dumps(short) and '"maxLength": 500' not in json.dumps(short)
    focal = ModelGateway(Recorder())
    focal.answer = "SHORT"
    asyncio.run(focal.decide(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=10,
                             allowed_actions=["SPEAK", "WAIT"], tick=1))
    assert focal.provider.calls[0].output_schema["properties"]["reason_summary"]["maxLength"] == 60
    # SYSTEM_PREFIX: Robot R's runtime passes its persona prefix; the prompt text is unchanged.
    gw = ModelGateway(Recorder())
    gw.prompt_layout = "SYSTEM_PREFIX"
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(Recorder()), pulse=PULSE)
    r = rts["robot_r"]
    _drive(r, Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
           .see(X_TRACK, 15, 8.5).hear(X_TRACK, "Where is the demo?"))
    call = gw.provider.calls[0]
    assert call.prefix == r.persona_prefix("FOCAL")[1] and call.prompt.startswith(call.prefix)


def test_llama_provider_sends_robot_rs_prefix_as_a_system_message_only_in_that_condition():
    from range_service.agents.llama import LlamaProvider

    p = LlamaProvider(port=1, api_key="k" * 20, warm_up=False)
    prefix, prompt = "## GUARDRAILS\nrules\n\n## IDENTITY\nme", "## GUARDRAILS\nrules\n\n## IDENTITY\nme\n\n## COMMITMENTS\n-"
    assert [m["role"] for m in p._body(prompt, 10, None, 0, prefix)["messages"]] == ["system", "user"]
    assert [m["role"] for m in p._body(prompt, 10, None, 0, None)["messages"]] == ["user"]


def test_simulated_gpu_shares_between_servers_and_batches_within_one():
    from range_service.agents.simgpu import SimGpu

    async def run():
        gpu = SimGpu(time_scale=0.05)
        t0 = asyncio.get_running_loop().time()
        await asyncio.gather(gpu.run(1.0, "focal"), gpu.run(1.0, "npc"))     # two servers: half speed each
        two_servers = (asyncio.get_running_loop().time() - t0) / 0.05
        t0 = asyncio.get_running_loop().time()
        await asyncio.gather(gpu.run(1.0, "npc"), gpu.run(1.0, "npc"))       # one server batching two slots
        batched = (asyncio.get_running_loop().time() - t0) / 0.05
        return two_servers, batched
    two_servers, batched = asyncio.run(run())
    assert 1.8 < two_servers < 2.4 and 1.15 < batched < 1.6


def test_a_guard_that_cannot_apply_is_recorded_as_off():
    from range_service.agents.runmodels import Conditions, models_from_specs

    rm = models_from_specs("fake", "fake", conditions=Conditions(gpu_guard=True))   # no schedulers: nothing to guard
    asyncio.run(rm.start())
    assert rm.guard is None and rm.conditions["gpu_guard"] is False
    assert any(e["event"] == "GPU_GUARD_NOT_APPLIED" for e in rm.events)
    sim = models_from_specs("fake-gpu", "auto", conditions=Conditions(gpu_guard=True, answer="SHORT"))
    asyncio.run(sim.start())
    assert sim.guard is not None and sim.focal.guard is sim.guard and sim.npc.scheduler.guard is sim.guard
    assert sim.focal.answer == "SHORT" and sim.option == "C_SIM"
    assert sim.manifest_settings()["gpu_guard.enabled"] is True
