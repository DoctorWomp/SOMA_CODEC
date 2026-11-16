"""Bake-off scoring and the committed prompt set (G3b-2; D-55). No model needed."""

from __future__ import annotations

import json
from pathlib import Path

from range_service.agents.gateway import GatewayResult
from range_service.eval import bakeoff as bk
from tools.bakeoff import PROMPT_SET, load_set
from tools.godot_check import private_strings

ITEM = {"item_id": "x", "body_id": "quadruped", "gestures": ["HEAD_TILT", "SIT_IN_PLACE"],
        "expressions": ["greeting_light", "acknowledge_tilt"], "prompt": "A visitor anon_k3j9x2m1qa waves.",
        "reference": {"demo_fulfilled": True}}


def _result(actions, calls=1, fallback=None, outcome="VALID"):
    call = {"outcome": outcome, "prompt_tokens": 1000, "cached_tokens": 800, "generated_tokens": 50,
            "timings": {"prefill_ms": 100, "generation_ms": 1000, "total_ms": 1200}}
    return GatewayResult(actions, None, [call] * calls, fallback)


def test_committed_prompt_set_is_robot_r_in_every_body_with_nothing_private():
    items, sha = load_set(PROMPT_SET)
    assert len(items) >= 30 and len(sha) == 64
    assert {i["body_id"] for i in items} == {"wheeled_humanoid", "legged_humanoid", "quadruped", "quadruped_arm"}
    assert any(i["reference"]["demo_fulfilled"] for i in items)          # promise situations are in it
    secrets = private_strings()
    for item in items:
        assert item["agent_id"] == "robot_r" and item["allowed_actions"] and item["prompt"].startswith("## GUARDRAILS")
        assert not [s for s in secrets if s in item["prompt"]], item["item_id"]   # T17


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
    results = {"created": "now", "engine": "llama.cpp b12443", "prompt_set": "prompts_v1.jsonl", "prompt_set_sha256": "0" * 64,
               "offline": [{"label": "F1", "model": "Qwen3.5-9B", "quant": "Q4_K_M", "qat": False, "kv": "f16",
                            "summary": bk.summarize_condition([item]), "agreement_precision": None, "agreement_kv": None,
                            "vram_mib": 6100, "vram_note": None, "items": [item]}],
               "live": [{"label": "F1 Qwen3.5-9B Q4_K_M", "mode": "LIVE", "ok": True, "decisions": 9, "timeouts": 0,
                         "fallbacks": 0, "p50_ms": 900.0, "p95_ms": 1500, "journal": "abc"}]}
    j, m = bk.write_report(results, tmp_path)
    text = m.read_text()
    assert "| F1 Qwen3.5-9B | Q4_K_M | f16 | 1 | 100% |" in text and "6100" in text and "| LIVE | yes |" in text
    assert json.loads(Path(j).read_text())["offline"][0]["vram_mib"] == 6100
