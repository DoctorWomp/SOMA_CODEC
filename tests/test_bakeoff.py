"""Bake-off scoring and the committed prompt set (G3b-2; D-55). No model needed."""

from __future__ import annotations

import json
from pathlib import Path

from range_service.agents.gateway import GatewayResult
from range_service.eval import bakeoff as bk
from tools.bakeoff import PROMPT_SET, PROMPT_SET_V1, load_set
from tools.godot_check import is_own_goal, own_goal_owners, private_strings

ITEM = {"item_id": "x", "body_id": "quadruped", "gestures": ["HEAD_TILT", "SIT_IN_PLACE"],
        "expressions": ["greeting_light", "acknowledge_tilt"], "prompt": "A visitor anon_k3j9x2m1qa waves.",
        "reference": {"demo_fulfilled": True}}


def _result(actions, calls=1, fallback=None, outcome="VALID"):
    call = {"outcome": outcome, "prompt_tokens": 1000, "cached_tokens": 800, "generated_tokens": 50,
            "timings": {"prefill_ms": 100, "generation_ms": 1000, "total_ms": 1200}}
    return GatewayResult(actions, None, [call] * calls, fallback)


def test_committed_prompt_set_is_robot_r_in_every_body_with_nothing_private():
    items, sha = load_set(PROMPT_SET_V1)
    assert sha.startswith("ee2b7c03be96")                                # v1 is frozen: results stay comparable
    assert len(items) >= 30 and len(sha) == 64
    assert {i["body_id"] for i in items} == {"wheeled_humanoid", "legged_humanoid", "quadruped", "quadruped_arm"}
    assert any(i["reference"]["demo_fulfilled"] for i in items)          # promise situations are in it
    secrets = private_strings()
    for item in items:
        assert item["agent_id"] == "robot_r" and item["allowed_actions"] and item["prompt"].startswith("## GUARDRAILS")
        assert not [s for s in secrets if s in item["prompt"]], item["item_id"]   # T17


def test_prompt_set_hash_ignores_windows_line_endings(tmp_path):
    crlf = tmp_path / "set.jsonl"
    crlf.write_bytes(PROMPT_SET_V1.read_bytes().replace(b"\n", b"\r\n"))
    assert load_set(crlf)[1] == load_set(PROMPT_SET_V1)[1]


def test_prompt_set_v2_has_npc_prompts_and_enough_promise_situations():
    items, sha = load_set(PROMPT_SET)
    assert len(sha) == 64 and len({i["item_id"] for i in items}) == len(items)
    roles = {(i["role"], i["tier"]) for i in items}
    assert {("ROBOT_R", "FOCAL"), ("NPC", "C1"), ("NPC", "C2")} <= roles
    assert {i["agent_id"] for i in items if i["role"] == "NPC"} == {"visitor_x", "visitor_y"}
    assert {i["body_id"] for i in items if i["role"] == "ROBOT_R"} == {"wheeled_humanoid", "legged_humanoid",
                                                                       "quadruped", "quadruped_arm"}
    promises = [i for i in items if bk.promise_due(i)]
    assert len(promises) >= 16 and all(bk.promised_to(i) for i in promises)
    secrets, owners = private_strings(), own_goal_owners()
    for item in items:
        assert item["prompt"].startswith("## GUARDRAILS") and item["allowed_actions"]
        for secret in secrets:
            if secret in item["prompt"]:
                # D-51: only an NPC's own goal, in its own prompt, on its labelled line (T17).
                assert item["role"] == "NPC" and is_own_goal(item["prompt"], secret, owners), item["item_id"]
    npc_own = [i for i in items if i["role"] == "NPC" and "Your own private goal (known only to you): " in i["prompt"]]
    assert len(npc_own) == len([i for i in items if i["role"] == "NPC"])


def test_scores_split_by_role():
    npc = dict(ITEM, role="NPC", item_id="n")
    rows = [bk.score_item(ITEM, _result([{"action": "WAIT", "args": {"duration_ms": 1}}])),
            bk.score_item(npc, _result([{"action": "WAIT", "args": {"duration_ms": 1}}], fallback={"action": "WAIT", "reason": "INVALID_OUTPUT"}))]
    by = bk.summarize_by_role(rows)
    assert by["ROBOT_R"]["final_valid"] == 1.0 and by["NPC"]["final_valid"] == 0.0


def test_signature_ignores_wording_but_not_the_decision():
    a = {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hello!", "addressee_id": "anon_k3j9x2m1qa"}}
    b = {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi there", "addressee_id": "anon_k3j9x2m1qa"}}
    c = {"action": "EXPRESS", "args": {"expression_id": "greeting_light"}}
    assert bk.signature(a) == bk.signature(b) != bk.signature(c)


def test_offline_gate_catches_what_the_world_would_refuse():
    bad = [{"action": "GESTURE", "args": {"gesture": "WAVE"}},
           {"action": "EXPRESS", "args": {"expression_id": "greeting"}},
           {"action": "SPEAK", "args": {"channel": "GROUP", "text": "x", "group_id": "g"}},
           {"action": "TURN_TO", "args": {"target_id": "anon_zzzzzzzzzz"}}]
    assert len(bk.offline_gate(bad, ITEM)) == 4
    good = [{"action": "GESTURE", "args": {"gesture": "HEAD_TILT", "target_id": "anon_k3j9x2m1qa"}}]
    assert bk.offline_gate(good, ITEM) == []


def test_scores_and_summary():
    kept = bk.score_item(ITEM, _result([{"action": "EXPRESS", "args": {"expression_id": "acknowledge_tilt"},
                                         "fulfills_commitment": True}]))
    repaired = bk.score_item(ITEM, _result([{"action": "WAIT", "args": {"duration_ms": 1000}}], calls=2,
                                           outcome="INVALID_OUTPUT"))
    failed = bk.score_item(ITEM, _result([{"action": "WAIT", "args": {"duration_ms": 1000}}], calls=2,
                                         fallback={"action": "WAIT", "reason": "INVALID_OUTPUT"}, outcome="INVALID_OUTPUT"))
    assert kept["first_valid"] and kept["kept"] is True and kept["gate_ok"]
    assert kept["prompt_tps"] == 2000.0 and kept["gen_tps"] == 50.0
    assert repaired["repaired"] and not repaired["first_valid"] and repaired["kept"] is False
    assert not failed["final_valid"] and failed["fallback"] == "INVALID_OUTPUT" and failed["signature"] == []
    s = bk.summarize_condition([kept, repaired, failed])
    assert s["valid_before_repair"] == 0.333 and s["repair_rate"] == 0.333 and s["final_valid"] == 0.667
    assert s["commitments_kept"] == 0.333     # a failed answer in a promise situation is a promise not kept


def test_no_promise_situation_is_null_with_a_reason_not_zero():
    item = dict(ITEM, reference={"demo_fulfilled": False})
    s = bk.summarize_condition([bk.score_item(item, _result([{"action": "WAIT", "args": {"duration_ms": 1}}]))])
    assert s["commitments_kept"] is None and "no prompt" in s["commitments_note"]


def test_agreement_and_reference_model():
    one = [{"item_id": "a", "final_valid": True, "signature": ["SPEAK:LOCAL:to"]},
           {"item_id": "b", "final_valid": True, "signature": ["WAIT", "EXPRESS:x"]}]
    two = [{"item_id": "a", "final_valid": True, "signature": ["SPEAK:LOCAL:to"]},
           {"item_id": "b", "final_valid": True, "signature": ["WAIT"]}]
    assert bk.agreement(one, two) == {"n": 2, "first_action": 1.0, "all_actions": 0.5}
    f1 = {"model": "Qwen3.5-9B", "quant": "Q4_K_M", "qat": False, "label": "F1"}
    f2 = {"model": "Qwen3.5-9B", "quant": "Q6_K", "qat": False, "label": "F2"}
    f3 = {"model": "Gemma 4 12B", "quant": "Q4_0", "qat": True, "label": "F3"}
    assert bk.reference_for(f1, [f1, f2, f3]) is f2
    assert bk.reference_for(f2, [f1, f2, f3]) is None and bk.reference_for(f3, [f1, f2, f3]) is None


def test_vram_is_unknown_with_a_reason_without_a_gpu(monkeypatch):
    monkeypatch.setattr(bk.shutil, "which", lambda _name: None)
    assert bk.vram_mib(1234) == (None, "nvidia-smi not found (no NVIDIA GPU or driver)")


def test_report_writes_markdown_and_json(tmp_path):
    item = bk.score_item(ITEM, _result([{"action": "WAIT", "args": {"duration_ms": 1}}]))
    npc = bk.score_item(dict(ITEM, role="NPC", item_id="n"), _result([{"action": "WAIT", "args": {"duration_ms": 1}}]))
    results = {"created": "now", "engine": "llama.cpp b12443", "prompt_set": "prompts_v2.jsonl", "prompt_set_sha256": "0" * 64,
               "offline": [{"label": "N3", "model": "Qwen3.5-4B", "quant": "Q4_K_M", "qat": False, "kv": "q8_0",
                            "summary": bk.summarize_condition([item, npc]), "summary_by_role": bk.summarize_by_role([item, npc]),
                            "agreement_precision": None, "agreement_kv": None,
                            "vram_mib": 3100, "vram_note": bk.VRAM_DELTA_NOTE, "items": [item, npc]}],
               "live": [{"label": "F3 Gemma 4 12B Q4_0", "npc_label": "N3", "mode": "LIVE_LOAD", "option": "C", "ok": True,
                         "decisions": 9, "timeouts": 0, "fallbacks": 0, "p50_ms": 900.0, "p95_ms": 1500, "npc_calls": 30,
                         "npc_p50_ms": 700.0, "promotion_warm_p50_ms": 650.0, "promotion_warm_n": 2,
                         "promotion_cold_p50_ms": 1200.0, "promotion_cold_n": 1, "vram_focal_mib": 8700,
                         "vram_npc_mib": 3600, "journal": "abc"}]}
    j, m = bk.write_report(results, tmp_path)
    text = m.read_text()
    assert "## Offline prompt set: Robot R prompts" in text and "## Offline prompt set: NPC prompts" in text
    assert "| N3 Qwen3.5-4B | Q4_K_M | q8_0 | 1 | 100% |" in text and "3100" in text
    assert "| F3 Gemma 4 12B Q4_0 | N3 | LIVE_LOAD | C | yes | 9 | 0 | 0 | 900.0 | 1500 | 30 | 700.0 | 650.0 (2) | " \
           "1200.0 (1) | 8700 / 3600 |" in text
    assert json.loads(Path(j).read_text())["offline"][0]["vram_mib"] == 3100


# ---------- regression tests for the measurement bugs found in the first bake-off (2026-11-17, D-58) ----------

class _Smi:
    """A fake nvidia-smi: per-process memory as Windows reports it (N/A), and total memory that grows."""

    def __init__(self, per_process: str, totals: list[int]) -> None:
        self.per_process = per_process
        self.totals = list(totals)

    def __call__(self, cmd, **_kw):
        out = self.per_process if "--query-compute-apps=pid,used_memory" in cmd else f"{self.totals.pop(0)}\n"
        return type("R", (), {"stdout": out})()


def test_vram_falls_back_to_the_change_in_total_gpu_memory_on_windows(monkeypatch):
    monkeypatch.setattr(bk.shutil, "which", lambda _name: "nvidia-smi")
    monkeypatch.setattr(bk.subprocess, "run", _Smi("4242, [N/A]\n", [1200, 8300]))
    before = bk.gpu_memory_used_mib()
    mib, note = bk.vram_mib(4242, before)
    assert mib == 7100 and "change in total GPU memory" in note
    assert "CPU" not in note                    # the old message blamed a CPU build


def test_vram_never_blames_a_cpu_build_when_it_cannot_measure(monkeypatch):
    monkeypatch.setattr(bk.shutil, "which", lambda _name: "nvidia-smi")
    monkeypatch.setattr(bk.subprocess, "run", _Smi("4242, [N/A]\n", []))
    mib, note = bk.vram_mib(4242)
    assert mib is None and "N/A" in note and "CPU" not in note
    monkeypatch.setattr(bk.subprocess, "run", _Smi("4242, 6100\n", []))
    assert bk.vram_mib(4242) == (6100, None)    # per-process memory still wins where it is reported


PROMISE = dict(ITEM, prompt="## COMMITMENTS\n- OPEN mem_robot_r_00012 -40s to anon_k3j9x2m1qa: Help them after "
                            "the current conversation.\n## OBSERVATIONS\n- anon_k3j9x2m1qa: OBSERVED")


def test_promise_kept_in_behavior_is_scored_apart_from_the_flag():
    spoke = bk.score_item(PROMISE, _result([{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Thanks for waiting!",
                                                                         "addressee_id": "anon_k3j9x2m1qa"}}]))
    assert spoke["kept"] is False and spoke["kept_behavior"] is True          # what F3 did: kept, not flagged
    walked = bk.score_item(PROMISE, _result([{"action": "MOVE_TO", "args": {"target_id": "anon_k3j9x2m1qa"}}]))
    assert walked["kept_behavior"] is True                                   # what F1 did: approached
    waited = bk.score_item(PROMISE, _result([{"action": "WAIT", "args": {"duration_ms": 1000}}]))
    assert waited["kept"] is False and waited["kept_behavior"] is False
    s = bk.summarize_condition([spoke, walked, waited])
    assert s["commitments_kept"] == 0.0 and s["commitments_kept_behavior"] == 0.667
    assert bk.promised_to(PROMISE) == {"anon_k3j9x2m1qa"}
    assert bk.promised_to(dict(PROMISE, reference={"demo_fulfilled": True, "promised_to": ["anon_aaaaaaaaaa"]})) \
        == {"anon_aaaaaaaaaa"}


def test_the_prompt_shows_promise_ids_and_when_to_set_the_flag():
    from range_service.agents import guardrails
    from tests.agent_helpers import CONFIGS, Scene, robot

    body = CONFIGS.items["bodies"]["wheeled_humanoid"]
    text = guardrails.guardrails_section("FOCAL", ["SPEAK", "WAIT"], body, [])
    assert "OPEN promises are listed under COMMITMENTS with an id" in text and '"fulfills_commitment": true' in text
    rt = robot()
    memory_id = rt.memory.commit("Help them after the current conversation.", "anon_k3j9x2m1qa", now_ms=0)["memory_id"]
    job = rt.observe(Scene().see("anon_k3j9x2m1qa", 16, 9).packet())
    assert f"- OPEN {memory_id} " in job.assembled.prompt
    assert bk.promised_to({"reference": {}, "prompt": job.assembled.prompt}) == {"anon_k3j9x2m1qa"}


def test_every_unusable_answer_is_kept_raw_with_its_error():
    calls = [{"attempt": 0, "outcome": "INVALID_OUTPUT", "error": "the answer is not valid JSON",
              "response_text": "Sure! I'll wave.", "prompt_tokens": 9, "cached_tokens": 0, "generated_tokens": 5,
              "timings": {"prefill_ms": 1, "generation_ms": 1, "total_ms": 2}},
             {"attempt": 1, "outcome": "INVALID_OUTPUT", "error": "action 1: 'FLY' is not one of your actions",
              "response_text": '{"actions": [{"action": "FLY", "args": {}}]}', "prompt_tokens": 9, "cached_tokens": 0,
              "generated_tokens": 5, "timings": {"prefill_ms": 1, "generation_ms": 1, "total_ms": 2}}]
    s = bk.score_item(ITEM, GatewayResult([{"action": "WAIT", "args": {"duration_ms": 1000}}], None, calls,
                                          {"action": "WAIT", "reason": "INVALID_OUTPUT"}))
    assert [a["response_text"] for a in s["invalid_answers"]] == ["Sure! I'll wave.", '{"actions": [{"action": "FLY", "args": {}}]}']
    assert s["invalid_answers"][1]["error"].startswith("action 1") and s["invalid_answers"][0]["attempt"] == 0
    assert bk.summarize_condition([s])["invalid_answers"] == 2
    ok = bk.score_item(ITEM, _result([{"action": "WAIT", "args": {"duration_ms": 1}}]))
    assert ok["invalid_answers"] == []


def test_progress_line_never_leaves_old_text_behind():
    import io

    out = io.StringIO()
    p = bk.Progress(out)
    p.update("  F1 f16: 9/40 (PROVIDER_ERROR)")
    p.update("  F1 f16: 10/40 (ok)")
    p.done()
    last = out.getvalue().split("\r")[-1]
    assert last.rstrip("\n").rstrip() == "  F1 f16: 10/40 (ok)"
    assert len(last.rstrip("\n")) >= len("  F1 f16: 9/40 (PROVIDER_ERROR)")   # padded over the longer line
