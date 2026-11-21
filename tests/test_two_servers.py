"""Option C: Robot R's server and the NPC server, both as stand-ins (G3c-1, D-59).

The stand-in (range_service/agents/standin.py) plays llama-server behind a fake binary that
takes llama-server's flags, so the real process code runs: 127.0.0.1 only, a free port and a
fresh API key per server, started and stopped together, the fallback to Option B, persona
snapshots with slot save/restore, and pre-warming. No model, no GPU, no network.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

from range_service.agents import inference as infmod
from range_service.agents.gateway import ModelRequest
from range_service.agents.inference import ResolvedModel, build_inference, load_inference
from range_service.agents.output_schema import answer_schema
from range_service.models import gguf

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake server binary is a POSIX script")

FAKE_SERVER = """#!{python}
# A stand-in "llama-server": takes llama-server's flags and serves the stand-in API.
import os, sys
sys.path.insert(0, {repo!r})
args = sys.argv[1:]
port = args[args.index("--port") + 1]
assert args[args.index("--host") + 1] == "127.0.0.1"
model = args[args.index("--model") + 1]
print("fake llama-server", port, args, flush=True)
if "broken" in model:
    print("error: failed to load model", flush=True)
    sys.exit(3)
os.environ["RANGE_STANDIN_API_KEY"] = os.environ["LLAMA_API_KEY"]
from range_service.agents import standin
extra = ["--prefix-cache"] + (["--slot-save"] if "--slot-save-path" in args else [])
sys.exit(standin.main(["--port", port] + extra))
"""

ACTIONS = ["SPEAK", "GESTURE", "WAIT", "NO_OP"]
PREFIX = "## GUARDRAILS\nYou control one embodied agent. Rules here.\n\n## IDENTITY\nYou are Visitor Y. Your id: visitor_y."
PROMPT = PREFIX + "\n\n## COMMITMENTS\n(none open)\n\n## DECISION\nTime now: 12s. Choose your next action(s)."


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    repo = str(Path(__file__).resolve().parent.parent)
    binary = tmp_path / "llama-server"
    binary.write_text(FAKE_SERVER.format(python=sys.executable, repo=repo), encoding="utf-8")
    binary.chmod(0o755)
    files = {}
    for name in ("focal_model", "npc_model", "broken_npc"):
        path = tmp_path / f"{name}.gguf"
        gguf.write_minimal(path, {"general.architecture": "llama", "llama.block_count": 4,
                                  "llama.attention.head_count_kv": 2, "llama.attention.head_count": 8,
                                  "llama.embedding_length": 256}, [("w", [16, 16])])
        files[name] = path

    def fake_resolve(name, registry=None, catalog=None):
        key = {"F3": "focal_model", "N3": "npc_model", "BROKEN": "broken_npc"}[name]
        return ResolvedModel(key, files[key], "0" * 64, "Q4_0", name)
    monkeypatch.setattr(infmod, "resolve_model", fake_resolve)
    monkeypatch.setattr(infmod, "VRAM_STORE", tmp_path / "vram.local.yaml")   # never the real store
    inf = copy.deepcopy(load_inference())
    inf["servers"]["focal"]["model"] = "F3"
    inf["servers"]["npc"]["model"] = "N3"
    inf["engine"]["startup_timeout_s"] = 20
    return tmp_path, binary, inf


def _request(agent, tier, prompt=PROMPT, key=None):
    return dict(agent_id=agent, tier=tier, prompt=prompt, prompt_sha256="0" * 64, max_tokens=64,
                allowed_actions=ACTIONS, tick=10, prefix_key=key)


def test_option_c_two_servers_robot_on_focal_npcs_on_npc_server(setup_env):
    tmp, binary, inf = setup_env
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary)

    async def run():
        await iset.start()
        try:
            assert iset.option == "C"
            f, n = iset.focal.provider, iset.npc.provider
            assert f.port != n.port and f.api_key != n.api_key and len(n.api_key) >= 32
            for proc in (iset.focal.provider.server.process, iset.npc.provider.server.process):
                assert proc.poll() is None
                assert f.api_key not in " ".join(proc.args) and n.api_key not in " ".join(proc.args)
            robot = await iset.focal.gateway.decide(**_request("robot_r", "FOCAL"))
            npc = await iset.npc_gateway.decide(**_request("visitor_y", "C2"))
            assert robot.model_calls[0]["server"] == "focal" and robot.model_calls[0]["slot"] == 0   # pinned slot
            assert npc.model_calls[0]["server"] == "npc"
            with pytest.raises(ValueError, match="does not serve FOCAL"):
                await iset.npc_gateway.decide(**_request("robot_r", "FOCAL"))
            # the NPC server has no pinned slot: all four are shared
            assert iset.npc.gateway.scheduler.reserved == 0 and iset.npc.settings["parallel_slots"] == 4
            procs = (iset.focal.provider.server.process, iset.npc.provider.server.process)
        finally:
            await iset.stop()
        assert all(p.poll() is not None for p in procs)            # stopped together
        assert iset.npc.provider.server.process is None and iset.focal.provider.server.process is None

    asyncio.run(run())
    assert [e["event"] for e in iset.events] == ["OPTION_C_STARTED"]
    settings = iset.manifest_settings()
    assert settings["inference.option"] == "C" and settings["npc_model.catalog_label"] == "N3"
    assert settings["vram.estimate_total_mib"] > 0
    # Both server logs exist, and neither holds a key.
    for name in ("focal", "npc"):
        log = (tmp / "run" / f"llama_server_{name}.log").read_text(encoding="utf-8")
        assert "--slot-save-path" in log if name == "npc" else "--slot-save-path" not in log
        assert iset.focal.provider.api_key not in log


def test_npc_server_that_fails_to_start_falls_back_to_option_b_and_says_so(setup_env):
    tmp, binary, inf = setup_env
    inf["servers"]["npc"]["model"] = "BROKEN"
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary)

    async def run():
        await iset.start()
        try:
            assert iset.option == "B" and iset.npc is None
            assert iset.npc_gateway is iset.focal.gateway            # NPCs share the focal server's shared slot
            npc = await iset.npc_gateway.decide(**_request("visitor_y", "C2"))
            robot = await iset.focal.gateway.decide(**_request("robot_r", "FOCAL"))
            assert npc.model_calls[0]["slot"] == 1 and robot.model_calls[0]["slot"] == 0   # never Robot R's slot
        finally:
            await iset.stop()

    asyncio.run(run())
    fallback = [e for e in iset.events if e["event"] == "OPTION_C_FALLBACK"]
    assert len(fallback) == 1 and "did not start" in fallback[0]["reason"]
    assert iset.manifest_settings()["inference.option"] == "B"
    assert "did not start" in iset.manifest_settings()["inference.fallback_reason"]


def test_over_budget_estimate_falls_back_before_starting_the_npc_server(setup_env):
    tmp, binary, inf = setup_env
    inf["vram"] = {"budget_mib": 1024, "reserve_mib": 1000, "compute_buffer_mib": 512, "over_budget": "FALLBACK"}
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary)

    async def run():
        await iset.start()
        await iset.stop()

    asyncio.run(run())
    assert iset.option == "B"
    reason = next(e["reason"] for e in iset.events if e["event"] == "OPTION_C_FALLBACK")
    assert "over the 1024 MiB budget" in reason and "focal" in reason
    est = iset.vram["estimate"]
    assert est["npc"]["kv_source"].startswith("header, layer by layer") and est["npc"]["kv_mib"] >= 0
    # Measured VRAM is null with a reason without a GPU, never 0.
    assert iset.vram["measured"]["focal"]["mib"] is None and iset.vram["measured"]["focal"]["note"]


def test_measured_focal_vram_replaces_its_estimate_in_the_fit_check(setup_env, monkeypatch):
    """Owner's PC, 2026-11-17: Gemma 4 12B's header estimate (16957 MiB, an upper bound that
    ignores sliding-window layers) sent every run to Option B, although Robot R's server was
    already running and measured. Once the focal server runs, its measured use counts instead."""
    from range_service.eval import bakeoff as bakeoff_mod

    tmp, binary, inf = setup_env
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary)
    est_focal = infmod.estimate_server_mib(iset.focal.model, iset.focal.settings, infmod.DEFAULT_VRAM)["total_mib"]
    est_npc = infmod.estimate_server_mib(iset.npc.model, iset.npc.settings, infmod.DEFAULT_VRAM)["total_mib"]
    reserve, measured_focal = 100, 50
    assert measured_focal < est_focal                         # the estimate alone would not fit the budget below
    iset.inference["vram"] = {"budget_mib": est_npc + reserve + measured_focal + 10, "reserve_mib": reserve,
                              "compute_buffer_mib": 512, "over_budget": "FALLBACK"}
    monkeypatch.setattr(bakeoff_mod, "vram_mib", lambda pid, before=None: (measured_focal, None))

    async def run():
        await iset.start()
        await iset.stop()

    asyncio.run(run())
    assert iset.option == "C", iset.events
    assert iset.vram["fit_check_basis"] == "focal measured + NPC estimate"
    assert iset.vram["fit_check_mib"] == measured_focal + est_npc + reserve


def test_kv_estimate_from_the_header():
    meta = {"general.architecture": "qwen", "qwen.block_count": 36, "qwen.attention.head_count_kv": 8,
            "qwen.attention.key_length": 128, "qwen.attention.value_length": 128}
    f16, src = gguf.kv_bytes_per_token(meta, "f16")
    assert f16 == 36 * 8 * 256 * 2 and src == "header (upper bound)"
    q8, _ = gguf.kv_bytes_per_token(meta, "q8_0")
    assert q8 == pytest.approx(f16 * 34 / 64)
    assert gguf.kv_bytes_per_token({"general.architecture": "qwen"}, "f16")[0] is None


def test_persona_snapshot_restore_and_prewarm_make_the_first_call_warm(setup_env):
    tmp, binary, inf = setup_env
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary)
    key = "visitor_y:C2:abc123abc123"

    async def run():
        await iset.start()
        gw = iset.npc_gateway
        try:
            snap = await gw.prepare_personas([("visitor_y", "C2", key, PREFIX)])
            assert snap[0]["method"] == "SLOT_SAVE" and snap[0]["slot"] in range(4)
            # Other NPCs fill every slot, so the persona prefix is gone from all of them ...
            for i in range(4):
                gw.scheduler.affinity.pop("visitor_y", None)
                await gw.decide(**_request(f"crowd_{i}", "C1", prompt=f"crowd {i} " + "x " * 20))
            gw.scheduler.affinity.pop("visitor_y", None)
            cold = await gw.decide(**_request("visitor_y", "C2", key="visitor_y:C2:other"))
            assert cold.model_calls[0]["prefix_state"] == "COLD" and cold.model_calls[0]["cached_tokens"] == 0
            # ... a pre-warm restores the snapshot into a free slot, and the first call lands there warm.
            gw.scheduler.affinity.pop("visitor_y", None)
            warm_event = await gw.prewarm("visitor_y", "C2", key, PREFIX)
            assert warm_event["method"] == "SLOT_RESTORE"
            warm = await gw.decide(**_request("visitor_y", "C2", key=key))
            call = warm.model_calls[0]
            assert call["slot"] == warm_event["slot"] and call["prefix_state"] == "WARM"
            assert call["cached_tokens"] >= len(PREFIX.split()) - 1
            # A slot that another NPC used in between gets the snapshot restored before the call (T5).
            other = call["slot"]
            gw.scheduler.affinity["crowd_x"] = other
            await gw.decide(**_request("crowd_x", "C1", prompt="crowd x " + "y " * 20))
            restored = await gw.decide(**_request("visitor_y", "C2", key=key))
            assert restored.model_calls[0]["prefix_state"] == "RESTORED"
            assert restored.model_calls[0]["cached_tokens"] >= len(PREFIX.split()) - 1
        finally:
            await iset.stop()

    asyncio.run(run())
    actions = [e["event"] for e in iset.npc_gateway.persona_events] if iset.npc else []
    assert actions == ["PERSONA_SNAPSHOT", "PREWARM"]


def test_without_slot_save_prewarm_sends_the_prefix_alone(setup_env):
    tmp, binary, inf = setup_env
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary, snapshots=False)
    key = "visitor_x:C1:abc123abc123"

    async def run():
        await iset.start()
        try:
            snap = await iset.npc_gateway.prepare_personas([("visitor_x", "C1", key, PREFIX)])
            assert snap[0]["method"] == "PREFIX_ONLY"                  # server has no --slot-save-path: 501
            assert iset.npc.provider.snapshot_support is False
            iset.npc.provider.slot_holds.clear()
            pw = await iset.npc_gateway.prewarm("visitor_x", "C1", key, PREFIX)
            assert pw["method"] == "PREFIX_REQUEST"
            first = await iset.npc_gateway.decide(**_request("visitor_x", "C1", key=key))
            assert first.model_calls[0]["prefix_state"] == "WARM"
            assert first.model_calls[0]["cached_tokens"] >= len(PREFIX.split()) - 1
        finally:
            await iset.stop()

    asyncio.run(run())


def test_prewarm_never_waits_or_takes_robot_rs_slot(setup_env):
    tmp, binary, inf = setup_env
    iset = build_inference(run_dir=tmp / "run", inference=inf, binary=binary, npc_model="none")

    async def run():
        await iset.start()
        try:
            gw = iset.npc_gateway                  # Option B: the focal server
            assert iset.option == "B"
            # G3c-2 (D-60): a pre-warm must leave a free slot for a real call. Option B has one
            # shared slot, so it never pre-warms during a run; it still never touches slot 0.
            pw = await gw.prewarm("visitor_y", "C2", "k", PREFIX)
            assert pw["method"] == "SKIPPED" and "free slot for a real call" in pw["note"]
            assert 0 not in gw.scheduler.busy and not gw.scheduler.busy
            snap = await gw.prepare_personas([("visitor_y", "C2", "k", PREFIX)])   # scene load: no real calls yet
            assert snap[0]["slot"] == 1                                           # never slot 0, Robot R's
        finally:
            await iset.stop()

    asyncio.run(run())
    assert any(e["event"] == "OPTION_C_FALLBACK" for e in iset.events)


def test_request_carries_prefix_key_to_the_provider():
    r = ModelRequest("a", "c", "C2", "p", "0" * 64, 10, 0, None, answer_schema(tuple(ACTIONS)), prefix_key="k")
    assert r.prefix_key == "k" and json.dumps(r.output_schema)


def test_npc_persona_prefix_goes_as_a_system_message_robot_r_stays_one_message():
    from range_service.agents.llama import LlamaProvider

    p = LlamaProvider(port=1, api_key="k" * 20, warm_up=False)
    npc = p._body(PROMPT, 64, None, 2, PREFIX)["messages"]
    assert [m["role"] for m in npc] == ["system", "user"] and npc[0]["content"] == PREFIX
    assert npc[1]["content"].startswith("## COMMITMENTS") and PREFIX + "\n\n" + npc[1]["content"] == PROMPT
    assert [m["role"] for m in p._body(PROMPT, 64, None, 0)["messages"]] == ["user"]            # Robot R
    assert [m["role"] for m in p._body("other text", 64, None, 0, PREFIX)["messages"]] == ["user"]   # not a prefix
    off = LlamaProvider(port=1, api_key="k" * 20, warm_up=False, system_prefix=False)
    assert [m["role"] for m in off._body(PROMPT, 64, None, 2, PREFIX)["messages"]] == ["user"]


def test_kv_estimate_counts_sliding_window_shared_and_linear_layers():
    """G3c-2 (D-60): the owner's F3 + N3 measured 12944 MiB with the reserve; the old estimate
    (every layer at full context) said 22779 MiB. Layer by layer as llama.cpp b12443 sizes it."""
    full = {"general.architecture": "g", "g.block_count": 6, "g.attention.head_count_kv": 2,
            "g.attention.key_length": 128, "g.attention.value_length": 128}
    base, _ = gguf.kv_cache_bytes(full, "f16", 4, 2048)
    assert base == 6 * 2 * 256 * 2 * 4 * 2048
    swa = dict(full, **{"g.attention.sliding_window": 512, "g.attention.sliding_window_pattern": [1, 1, 1, 1, 1, 0]})
    with_swa, note = gguf.kv_cache_bytes(swa, "f16", 4, 2048)
    swa_cells = -(-(512 * 4 + 512) // 256) * 256                      # 2560 cells instead of 8192
    assert with_swa == 5 * 2 * 256 * 2 * swa_cells + 1 * 2 * 256 * 2 * 8192 and "5 sliding-window layers" in note
    shared, _ = gguf.kv_cache_bytes(dict(swa, **{"g.attention.shared_kv_layers": 2}), "f16", 4, 2048)
    assert shared == 4 * 2 * 256 * 2 * swa_cells                      # the last two layers keep no cache
    hybrid, note = gguf.kv_cache_bytes(dict(full, **{"g.full_attention_interval": 3}), "f16", 4, 2048)
    assert hybrid == base / 3 and "1 of 3" in note
    per_layer, _ = gguf.kv_cache_bytes(dict(full, **{"g.attention.head_count_kv": [2, 2, 2, 2, 0, 0]}), "f16", 4, 2048)
    assert per_layer == base * 4 / 6


def test_a_measured_server_replaces_the_estimate_next_time(tmp_path, setup_env):
    _, _, inf = setup_env
    from range_service.agents.inference import estimate_server_mib, load_measured, record_measured

    store = tmp_path / "vram.local.yaml"
    model = ResolvedModel("n3", Path(__file__), "a" * 64, "Q4_K_M", "N3")
    server = inf["servers"]["npc"]
    record_measured(model, server, 3271, "measured as the change in total GPU memory", store)
    est = estimate_server_mib(model, server, inf["vram"], load_measured(store))
    assert est["total_mib"] == 3271 and est["basis"] == "measured"
    other = dict(server, kv_cache_type="f16")                          # other settings: not reused
    assert estimate_server_mib(model, other, inf["vram"], load_measured(store))["basis"] == "estimate"
