"""G3g: lean answers. Salvage of a cut-off answer (D-86), the LEAN answer format (D-85), token
accounting per field (D-84), the GPU guard for real decisions only (D-89) and the target that
counts fallbacks (D-87). No Godot, no real model."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from range_service import contracts
from range_service.agents import lean
from range_service.agents.factory import build_runtimes
from range_service.agents.gateway import FakeModel, ModelGateway, ModelResponse, complete_fields, salvage
from range_service.agents.guardrails import ACTIVITY_FORMAT, OUTPUT_FORMAT
from range_service.agents.output_schema import answer_schema
from range_service.agents.scheduler import FocalGuard, SlotScheduler
from range_service.eval import bakeoff as bk
from range_service.eval import tokens
from tests.agent_helpers import CONFIGS, Scene

ALLOWED = ["SPEAK", "LOOK_AT", "WAIT", "GESTURE"]
X = "anon_xxxxxxxxx1"
SPEAK = {"action": "SPEAK", "args": {"channel": "LOCAL", "text": "The demo is on the platform.", "addressee_id": X}}
FULL_ANSWER = json.dumps({"actions": [SPEAK], "reason_summary": "The visitor asked where the demo is, so I answer and"})
SB04 = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
PULSE = CONFIGS.items["pulse"]["pulse"]
REPO = Path(__file__).resolve().parent.parent


class Cut(FakeModel):
    """A model whose answers stop at the output cap (finish_reason "length") after ``keep`` characters."""

    def __init__(self, text: str, keep: int, truncated: bool = True) -> None:
        super().__init__(responder=lambda r: text[:keep])
        self.truncated = truncated

    async def complete(self, request):
        r = await super().complete(request)
        return ModelResponse(r.text, r.model_id, truncated=self.truncated, generated_tokens=request.max_tokens)


def decide(gw: ModelGateway, **kw):
    args = dict(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=200,
                allowed_actions=ALLOWED, tick=60)
    args.update(kw)
    return asyncio.run(gw.decide(**args))


# ---------- salvage (D-86) ----------

def test_complete_fields_reads_only_whole_values():
    fields, cut = complete_fields(FULL_ANSWER[:-20])
    assert fields == {"actions": [SPEAK]} and cut == "reason_summary"
    fields, cut = complete_fields(FULL_ANSWER)
    assert set(fields) == {"actions", "reason_summary"} and cut is None
    fields, cut = complete_fields(FULL_ANSWER[:40])                    # inside the first action
    assert fields == {} and cut == "actions"


def test_a_cut_off_answer_with_complete_valid_actions_is_used():
    keep = FULL_ANSWER.index('"reason_summary"') + 30
    result = decide(ModelGateway(Cut(FULL_ANSWER, keep)))
    assert result.fallback is None and result.actions == [SPEAK] and result.reason_summary is None
    (call,) = result.model_calls
    assert call["outcome"] == "VALID" and call["salvaged"] == {"dropped": ["reason_summary"], "actions": 1}


@pytest.mark.parametrize("keep", [30, 80, len('{"actions": [') + len(json.dumps(SPEAK)) - 3])
def test_a_partial_action_is_never_salvaged(keep):
    """Cut inside an action, or with the actions list still open: one repair (also cut off), then WAIT."""
    two = json.dumps({"actions": [SPEAK, {"action": "WAIT", "args": {"duration_ms": 500}}]})
    for text in (FULL_ANSWER, two):
        result = decide(ModelGateway(Cut(text, keep)))
        assert result.fallback == {"action": "WAIT", "reason": "INVALID_OUTPUT"}
        assert all("salvaged" not in c for c in result.model_calls)
        assert "cut off at the 200-token limit" in result.model_calls[0]["error"]


def test_an_open_actions_list_is_not_salvaged_even_if_its_first_action_is_complete():
    two = json.dumps({"actions": [SPEAK, {"action": "WAIT", "args": {"duration_ms": 500}}]})
    keep = two.index('{"action": "WAIT"') + 5
    assert salvage(two[:keep]) is None
    assert decide(ModelGateway(Cut(two, keep))).fallback is not None


def test_salvage_needs_valid_actions_a_real_cut_and_can_be_switched_off():
    bad = json.dumps({"actions": [{"action": "FLY", "args": {}}], "reason_summary": "x" * 80})
    assert decide(ModelGateway(Cut(bad, len(bad) - 10))).fallback is not None          # invalid actions: no
    keep = FULL_ANSWER.index('"reason_summary"') + 30
    assert decide(ModelGateway(Cut(FULL_ANSWER, keep, truncated=False))).fallback is not None   # not at the cap: no
    gw = ModelGateway(Cut(FULL_ANSWER, keep))
    gw.salvage = False
    assert decide(gw).fallback is not None


def test_salvaged_decision_record_passes_its_contract_and_the_breakdown_counts_it():
    keep = FULL_ANSWER.index('"reason_summary"') + 30
    gw = ModelGateway(Cut(FULL_ANSWER, keep))
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    r = rts["robot_r"]
    scene = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    job = r.observe(scene.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    assert job is not None and job.proposals is None
    asyncio.run(r.decide(job))
    record = r.records[-1]
    assert contracts.problems("decision_record", record) == []
    call = record["model_calls"][0]
    assert call["salvaged"]["dropped"] == ["reason_summary"] and record["fallback"] is None
    assert record["activity"]["source"] == "DERIVED"              # the runtime derived one (D-61)
    from range_service.eval.live_diag import robot_breakdown
    b = robot_breakdown([record])
    assert b["salvaged"] == 1 and b["fallbacks"] == 0


# ---------- LEAN (D-85) ----------

def test_lean_schema_has_no_reason_no_grammar_text_limits_and_a_compact_activity():
    full = answer_schema(("SPEAK", "WAIT"), (X,), ("LOCAL",), "FOCAL", None, None, 600)
    lean_s = answer_schema(("SPEAK", "WAIT"), (X,), ("LOCAL",), "FOCAL_LEAN", None, None, 600)
    assert "reason_summary" in full["properties"] and "reason_summary" not in lean_s["properties"]
    assert '"maxLength"' in json.dumps(full)
    assert ('"maxLength"' in json.dumps(lean_s)) == lean.GRAMMAR_TEXT_LIMITS
    act = lean_s["properties"]["activity"]["properties"]
    assert set(act) == set(lean.LEAN_KEYS) and list(lean_s["properties"]) == ["actions", "activity"]


def test_expand_writes_a_compact_activity_in_full_and_defaults_its_target():
    text = json.dumps({"actions": [SPEAK], "activity": {"kind": "CONVERSE", "review_s": 30, "within_m": 2,
                                                         "wake": ["addressed", "target_lost"]}})
    data = json.loads(lean.expand(text))
    assert data["activity"] == {"kind": "CONVERSE", "target_id": X, "review_after_s": 30,
                                "wake_if": [{"target_within_m": 2}, {"addressed": True}, {"target_lost": True}]}
    assert lean.expand("not json") == "not json"
    untouched = json.dumps({"actions": [SPEAK], "activity": {"kind": "SURVEY", "wake_if": []}})
    assert json.loads(lean.expand(untouched))["activity"] == {"kind": "SURVEY", "wake_if": []}   # not compact: as given


def test_robot_r_under_lean_gets_lean_format_lines_and_its_activity_is_read_in_full():
    answer = json.dumps({"actions": [SPEAK], "activity": {"kind": "CONVERSE", "wake": ["addressed"]}})
    gw = ModelGateway(FakeModel(responder=lambda r: answer))
    gw.answer = "LEAN"
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=ModelGateway(FakeModel()), pulse=PULSE)
    r = rts["robot_r"]
    scene = Scene(observer="robot_r", pose={"x": 15.0, "y": 0.0, "z": 10.0, "yaw_rad": 0.0})
    job = r.observe(scene.see(X, 15, 8.5).hear(X, "Where is the demo?").packet())
    asyncio.run(r.decide(job))
    call = gw.provider.calls[0]
    assert lean.OUTPUT_FORMAT_LEAN in call.prompt and lean.ACTIVITY_FORMAT_LEAN in call.prompt
    assert OUTPUT_FORMAT not in call.prompt and ACTIVITY_FORMAT not in call.prompt
    assert call.prompt.startswith(r.persona_prefix("FOCAL")[1])
    assert "reason_summary" not in call.output_schema["properties"]
    rec = r.records[-1]
    assert rec["activity"]["source"] == "CHOSEN" and rec["activity"]["target_id"] == X
    assert rec["activity"]["wake_if"] == [{"addressed": True}]
    assert contracts.problems("decision_record", rec) == []


def test_a_cut_off_lean_answer_keeps_its_complete_compact_activity():
    """Salvage under LEAN: the actions and a complete compact activity are kept (written out in full);
    only the cut-off trailing part is dropped."""
    answer = json.dumps({"actions": [SPEAK], "activity": {"kind": "CONVERSE", "wake": ["addressed"]},
                         "extra": "x" * 40})
    keep = answer.index('"extra"') + 12
    gw = ModelGateway(Cut(answer, keep))
    gw.answer = "LEAN"
    result = decide(gw, choices={"targets": [X], "activity": 600})
    assert result.fallback is None and result.actions == [SPEAK]
    assert result.activity == {"kind": "CONVERSE", "target_id": X, "wake_if": [{"addressed": True}]}
    assert result.model_calls[0]["salvaged"] == {"dropped": ["extra"], "actions": 1}


def test_nobody_else_changes_under_lean():
    gw = ModelGateway(FakeModel())
    gw.answer = "LEAN"
    npc = ModelGateway(FakeModel())
    rts = build_runtimes(SB04, CONFIGS, gateway=gw, npc_gateway=npc, pulse=PULSE)
    assert lean.OUTPUT_FORMAT_LEAN not in rts["visitor_x"].persona_prefix("C2")[1]
    assert lean.OUTPUT_FORMAT_LEAN in rts["robot_r"].persona_prefix("FOCAL")[1]


def test_rewrite_prompt_changes_only_the_answer_format_lines():
    items = [json.loads(x) for x in (REPO / "bakeoff" / "prompts_v3.jsonl").read_text(encoding="utf-8").splitlines() if x]
    robot = [i for i in items if i["role"] == "ROBOT_R"]
    assert all(OUTPUT_FORMAT in i["prompt"] and ACTIVITY_FORMAT not in i["prompt"] for i in robot)
    p = robot[0]["prompt"]
    lean_p = lean.rewrite_prompt(p, "LEAN", activity=True)
    assert lean_p.replace(lean.OUTPUT_FORMAT_LEAN, OUTPUT_FORMAT).replace("\n" + lean.ACTIVITY_FORMAT_LEAN, "") == p
    full_act = lean.rewrite_prompt(p, "FULL", activity=True)
    assert full_act.replace("\n" + ACTIVITY_FORMAT, "") == p
    head = full_act.split("\n\n## IDENTITY")[0]
    assert head.endswith(ACTIVITY_FORMAT)                    # where the runtime puts it (guardrails_section)
    assert lean.rewrite_prompt(p, "FULL", activity=False) == p


def test_offline_pulse_review_limit_matches_the_pulse_config():
    from tools.bakeoff import PULSE_MAX_REVIEW_S
    assert PULSE_MAX_REVIEW_S == PULSE["pulse"]["max_review_after_s"]


# ---------- token accounting (D-84) ----------

def test_tokens_per_field_follow_the_answer_structure():
    text = json.dumps({"actions": [dict(SPEAK, fulfills_commitment=True)], "reason_summary": "because",
                       "activity": {"kind": "CONVERSE", "wake_if": [{"addressed": True}]}})
    pieces = [text[i:i + 3] for i in range(0, len(text), 3)]
    acc = tokens.account(text, pieces)
    assert acc["aligned"] and acc["tokens"] == len(pieces) == sum(acc["by_field"].values())
    for f in ("actions", "args", "speech", "promise", "activity", "wake", "reason"):
        assert acc["by_field"][f] > 0, f
    spaced = '{\n  "actions": [{"action": "WAIT", "args": {"duration_ms": 1}}]\n}'
    sp = tokens.account(spaced, ["{", "\n", " ", ' "', "actions", '":', ' [{"', "action", '":', ' "', "WAIT", '",', ' "',
                                 "args", '":', ' {"', "duration", "_ms", '":', " ", "1", "}}", "]", "\n", "}"])
    assert sp["aligned"] and sp["by_field"]["space"] == 4          # line breaks and indentation, apart
    assert tokens.category(("actions", 0, "args", "text")) == "speech"
    assert tokens.category(("activity", "wake", 0)) == "wake"
    s = tokens.summarize([acc, acc])
    assert s["n"] == 2 and abs(sum(v["share"] for v in s["by_field"].values()) - 1) < 0.01


def test_lean_targets_and_answer_cost_table():
    s = {"final_valid": 0.99, "commitments_kept_behavior": 0.95, "commitments_kept": 0.6, "generated_tokens_p50": 64,
         "cut_off": 0}
    assert bk.lean_target(s) == (True, [])
    met, missed = bk.lean_target(dict(s, generated_tokens_p50=90, cut_off=2))
    assert not met and len(missed) == 2
    row = {"label": "F3", "model": "Gemma 4 12B", "focal_answer": "LEAN", "focal_activity": True,
           "summary_by_role": {"ROBOT_R": dict(s, generated_tokens_p95=120, salvaged=0,
                                               fields=tokens.summarize([tokens.account("{}", ["{}"])]))}}
    lines = bk.answer_cost_lines([row])
    assert any("[LEAN, activity]" in x and "| met |" in x for x in lines)


def test_target_counts_fallback_decisions_not_only_timeouts():
    def live(npc, fallbacks, decisions, timeouts, p95=3000.0):
        return {"label": "F3 Gemma", "npc_label": npc, "mode": "LIVE", "p95_ms": p95, "timeouts": timeouts,
                "decisions": decisions, "npc_calls": 0, "npc_timeouts": 0, "harness": "g3f", "run_dir": f"r{npc}",
                "robot": {"fallbacks_by_reason": {"INVALID_OUTPUT": fallbacks - timeouts, "TIMEOUT": timeouts},
                          "decisions": decisions, "salvaged": 2}}
    lines = bk.target_lines([live("none", 6, 30, 0), live("N3", 3, 40, 1)], bk.fmt, {})
    alone = next(x for x in lines if "| none |" in x)
    with_npc = next(x for x in lines if "| N3 |" in x)
    assert "6/30 (20%)" in alone and "| NOT met | met |" in alone       # G3f's timeout target met, the new one not
    assert "3/40 (8%)" in with_npc and "| met | met |" in with_npc


# ---------- the guard for real decisions only (D-89) ----------

def test_guard_hold_decisions_lets_npc_calls_run_during_robot_rs_pulse_reviews():
    async def run(hold):
        guard = FocalGuard(npc_cap=0, hold=hold)
        npc = SlotScheduler(4, pinned_tiers=(), reserved=0)
        npc.set_guard(guard)
        far = asyncio.get_running_loop().time() + 60
        held = guard.focal_begin(background=True)          # Robot R's pulse review
        real = asyncio.create_task(npc.acquire("visitor_b", "C2", far))
        await asyncio.sleep(0.01)
        during_review = real.done()
        guard.focal_end(held)
        await asyncio.sleep(0.01)
        decision = guard.focal_begin(background=False)     # a real decision holds in both settings
        real2 = asyncio.create_task(npc.acquire("visitor_c", "C2", far))
        await asyncio.sleep(0.01)
        during_decision = real2.done()
        guard.focal_end(decision)
        await asyncio.sleep(0.01)
        assert real2.done() and guard.focal_in_flight == 0
        return during_review, during_decision, guard.stats
    review, decision, stats = asyncio.run(run("DECISIONS"))
    assert review and not decision and stats["focal_reviews_not_held"] == 1 and stats["focal_calls"] == 2
    review, decision, stats = asyncio.run(run("ALL"))
    assert not review and not decision and stats["focal_reviews_not_held"] == 0
    with pytest.raises(ValueError):
        FocalGuard(hold="SOMETIMES")


def test_robot_r_gateway_passes_background_to_the_guard():
    seen = []

    class Probe(FakeModel):
        async def complete(self, request):
            seen.append(guard.focal_in_flight)
            return await super().complete(request)
    guard = FocalGuard(hold="DECISIONS")
    focal = ModelGateway(Probe(), scheduler=SlotScheduler(2), server="focal")
    focal.guard = guard
    for background in (True, False):
        asyncio.run(focal.decide(agent_id="robot_r", tier="FOCAL", prompt="p", prompt_sha256="0" * 64, max_tokens=10,
                                 allowed_actions=["WAIT"], tick=1, background=background))
    assert seen == [0, 1] and guard.focal_in_flight == 0


def test_npc_table_rows_name_the_condition_of_their_run(tmp_path):
    """G3g display fix: the NPC-prompts table repeated F3 and F1 rows without their condition labels
    (the conditions change Robot R's prompts only, but the rows came from different runs)."""
    def summary(n):
        return {"n": n, "valid_before_repair": 1.0, "repair_rate": 0.0, "final_valid": 1.0, "valid_action_rate": 1.0,
                "commitments_kept": None, "commitments_kept_behavior": None, "prompt_tps_median": 1.0,
                "gen_tps_median": 1.0, "latency_ms_p50": 1.0}

    def cond(layout, answer):
        return {"label": "F3", "model": "Gemma 4 12B", "quant": "Q4_0", "qat": True, "kv": "q8_0", "vram_mib": 1,
                "vram_note": None, "focal_layout": layout, "focal_answer": answer, "summary": summary(96),
                "summary_by_role": {"ROBOT_R": summary(56), "NPC": summary(40)}, "agreement_precision": None,
                "agreement_kv": None}
    _, md = bk.write_report({"offline": [cond("ONE_MESSAGE", "FULL"), cond("SYSTEM_PREFIX", "SHORT")], "live": []},
                            tmp_path)
    text = md.read_text()
    npc = text[text.index("NPC prompts"):]
    assert "| F3 Gemma 4 12B | " in npc
    assert "| F3 Gemma 4 12B [run with Robot R SYSTEM_PREFIX, SHORT; NPC prompts unchanged] |" in npc
    robot = text[text.index("Robot R prompts"):text.index("NPC prompts")]
    assert "| F3 Gemma 4 12B [SYSTEM_PREFIX, SHORT] |" in robot
