"""The llama-server provider against a stand-in server (G3b; D-21, D-50; T25-T27).

Everything here runs on 127.0.0.1 with no model and no network: the stand-in
(range_service/agents/standin.py) speaks llama-server's API and answers by rule.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from range_service.agents import standin
from range_service.agents.gateway import ModelGateway, ModelRequest, ProviderError
from range_service.agents.llama import LlamaProvider, LlamaServer, ServerSettings, ServerTokenizer
from range_service.agents.output_schema import answer_schema

ACTIONS = ["SPEAK", "GESTURE", "EXPRESS", "TURN_TO", "MOVE_TO", "WAIT", "NO_OP"]


class StandIn:
    """The stand-in server on its own thread and event loop (so blocking clients work too)."""

    def __init__(self, mode: str = "normal", delay_ms: int = 0, answers: list[str] | None = None) -> None:
        self.key = secrets.token_urlsafe(24)
        self.b = standin.Behaviour(mode, delay_ms, list(answers or []), self.key)
        self.loop = asyncio.new_event_loop()
        self.port = 0
        ready = threading.Event()

        def run() -> None:
            asyncio.set_event_loop(self.loop)
            self.server = self.loop.run_until_complete(standin.serve(self.b))
            self.port = self.server.sockets[0].getsockname()[1]
            ready.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        ready.wait(5)

    def close(self) -> None:
        async def shut() -> None:
            self.server.close()
            await self.server.wait_closed()
            await asyncio.sleep(0.05)       # let closing connections finish
        asyncio.run_coroutine_threadsafe(shut(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()


@pytest.fixture
def stand_in():
    servers: list[StandIn] = []

    def make(**kw) -> StandIn:
        s = StandIn(**kw)
        servers.append(s)
        return s
    yield make
    for s in servers:
        s.close()


def decide(gateway: ModelGateway, agent_id: str = "robot_r", tier: str = "FOCAL", prompt: str = "## RULES\nBe kind.\n## NOW\nHello"):
    return asyncio.run(gateway.decide(agent_id=agent_id, tier=tier, prompt=prompt, prompt_sha256="0" * 64,
                                      max_tokens=128, allowed_actions=ACTIONS, tick=100))


def test_normal_answer_with_constraints_and_server_timings(stand_in):
    s = stand_in()
    provider = LlamaProvider.attach(s.port, s.key, warm_up=False)
    result = decide(ModelGateway(provider))
    assert result.fallback is None
    assert result.actions == [{"action": "WAIT", "args": {"duration_ms": 1000}}]
    call = result.model_calls[0]
    assert call["provider"] == "LLAMA_SERVER" and call["outcome"] == "VALID"
    # Timings and token counts come from the server's reply, not from estimates.
    assert call["timings"]["prefill_ms"] == round(12.5) and call["timings"]["generation_ms"] == 40
    assert call["prompt_tokens"] == 7 and call["cached_tokens"] == 3 and call["generated_tokens"] >= 1
    body = s.b.requests[0]
    assert body["cache_prompt"] is True                                  # T3: prefix caching
    assert body["chat_template_kwargs"] == {"enable_thinking": False}    # D-20: thinking off
    assert body["temperature"] == 0.0
    schema = body["response_format"]["schema"]                            # D-21: constrained output
    allowed = [c["properties"]["action"]["const"] for c in schema["properties"]["actions"]["items"]["anyOf"]]
    assert allowed == ACTIONS


def test_slow_server_times_out_and_the_late_answer_is_dropped_t25(stand_in):
    s = stand_in(mode="slow", delay_ms=1500)
    gateway = ModelGateway(LlamaProvider.attach(s.port, s.key, warm_up=False), deadlines_ms={"FOCAL": 300})
    started = time.perf_counter()
    result = decide(gateway)
    took = time.perf_counter() - started
    assert result.fallback == {"action": "WAIT", "reason": "TIMEOUT"}
    assert result.actions == [{"action": "WAIT", "args": {"duration_ms": 1000}}]
    assert result.model_calls[0]["outcome"] == "TIMEOUT"
    assert took < 1.0, f"the deadline was not kept ({took:.2f} s)"


def test_malformed_answer_gets_one_repair_then_waits_t26(stand_in):
    s = stand_in(mode="malformed")
    result = decide(ModelGateway(LlamaProvider.attach(s.port, s.key, warm_up=False)))
    assert result.fallback == {"action": "WAIT", "reason": "INVALID_OUTPUT"}
    assert [c["outcome"] for c in result.model_calls] == ["INVALID_OUTPUT", "INVALID_OUTPUT"]
    assert len(s.b.requests) == 2
    assert "## REPAIR" in s.b.requests[1]["messages"][0]["content"]


def test_hostile_answer_is_data_not_an_action(stand_in):
    s = stand_in(answers=['{"actions": [{"action": "RUN_SHELL", "args": {"command": "rm -rf /"}}]}'])
    result = decide(ModelGateway(LlamaProvider.attach(s.port, s.key, warm_up=False)))
    assert result.fallback == {"action": "WAIT", "reason": "INVALID_OUTPUT"}


def test_disconnecting_server_is_a_provider_error(stand_in):
    s = stand_in(mode="disconnect")
    result = decide(ModelGateway(LlamaProvider.attach(s.port, s.key, warm_up=False)))
    assert result.fallback == {"action": "WAIT", "reason": "PROVIDER_ERROR"}
    assert "closed the connection" in result.model_calls[0]["error"]


def test_wrong_key_is_refused(stand_in):
    s = stand_in()
    result = decide(ModelGateway(LlamaProvider.attach(s.port, "not-the-key-" + "x" * 20, warm_up=False)))
    assert result.fallback == {"action": "WAIT", "reason": "PROVIDER_ERROR"}
    assert "rejected the API key" in result.model_calls[0]["error"]
    assert s.b.unauthorized == 1 and not s.b.requests


def test_no_server_is_a_provider_error_not_a_crash():
    with __import__("socket").socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = decide(ModelGateway(LlamaProvider.attach(port, "k" * 20, warm_up=False)))
    assert result.fallback == {"action": "WAIT", "reason": "PROVIDER_ERROR"}


def test_focal_agent_keeps_its_slot_t4(stand_in):
    s = stand_in()
    provider = LlamaProvider.attach(s.port, s.key, parallel_slots=2, warm_up=False)
    gateway = ModelGateway(provider)
    for _ in range(3):
        decide(gateway, agent_id="robot_r")
    decide(gateway, agent_id="robot_2")            # a second focal agent: only one slot is pinned
    decide(gateway, agent_id="visitor_x", tier="C2")
    slots = [r["id_slot"] for r in s.b.requests]
    assert slots == [0, 0, 0, -1, -1]


def test_model_tokenizer_counts_and_falls_back_visibly(stand_in):
    s = stand_in()
    tok = ServerTokenizer(s.port, s.key, "standin")
    assert tok.count("one two three") == 3 and tok.count("") == 0
    assert tok.name == "llama_tokenize:standin"
    dead = ServerTokenizer(1, s.key, "standin")
    assert dead.count("a b c d e f g") == 4            # the approx estimate (13 chars / 3.5, rounded up)
    assert dead.name.endswith("+approx_fallback")


def test_answer_schema_accepts_valid_answers_and_rejects_others():
    schema = answer_schema(tuple(ACTIONS))
    assert "$ref" not in json.dumps(schema)
    v = Draft202012Validator(schema)
    ok = {"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hello!", "addressee_id": None},
                       "commitment": "Help them next."},
                      {"action": "EXPRESS", "args": {"expression_id": "greeting", "target_id": "anon_k3j9x2m1qa"}}],
          "reason_summary": "greet"}
    assert not list(v.iter_errors(ok))
    for bad in ({"actions": []},
                {"actions": [{"action": "RUN_SHELL", "args": {}}]},
                {"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}, "commitment": "x"}]},
                {"actions": [{"action": "WAIT", "args": {"duration_ms": 1}}] * 4}):
        assert list(v.iter_errors(bad)), bad


# ---------- the server process: 127.0.0.1, free port, key never logged, stop only ours ----------

FAKE_SERVER = """#!{python}
# A stand-in "llama-server" binary for tests: takes the same flags, serves the stand-in API.
import os, sys
sys.path.insert(0, {repo!r})
port = sys.argv[sys.argv.index("--port") + 1]
assert sys.argv[sys.argv.index("--host") + 1] == "127.0.0.1"
os.environ["RANGE_STANDIN_API_KEY"] = os.environ["LLAMA_API_KEY"]
print("fake llama-server starting on", port, "args", sys.argv[1:], flush=True)
from range_service.agents import standin
sys.exit(standin.main(["--port", port]))
"""


@pytest.mark.skipif(sys.platform == "win32", reason="the fake server binary is a POSIX script")
def test_server_process_lifecycle_and_key_hygiene(tmp_path):
    repo = str(Path(__file__).resolve().parent.parent)
    binary = tmp_path / "llama-server"
    binary.write_text(FAKE_SERVER.format(python=sys.executable, repo=repo))
    binary.chmod(0o755)
    model = tmp_path / "m.gguf"
    model.write_bytes(b"GGUF")
    settings = ServerSettings("focal", model, "m@000000000000", "0" * 64, 2, 2048, "q8_0", "auto", "all")
    log = tmp_path / "llama_server.log"
    server = LlamaServer(binary, settings, log, startup_timeout_s=20)
    provider = LlamaProvider(server=server, warm_up=True)

    async def run() -> None:
        await provider.start()
        assert server.process is not None and server.process.poll() is None
        assert server.port > 0 and len(server.api_key) >= 32
        assert server.api_key not in " ".join(server.process.args)        # never on the command line
        assert server.api_key not in repr(server) and server.api_key not in repr(provider)
        request = ModelRequest("robot_r", "call_1", "FOCAL", "hi", "0" * 64, 32, 0, None,
                               answer_schema(tuple(ACTIONS)))
        response = await provider.complete(request)
        assert json.loads(response.text)["actions"][0]["action"] == "WAIT"
        proc = server.process
        await provider.stop()
        assert proc.poll() is not None and server.process is None
        await provider.stop()                                               # idempotent: stops only ours

    asyncio.run(run())
    text = log.read_text()
    assert "'--cache-type-k', 'q8_0'" in text and "'--reasoning', 'off'" in text and "'--host', '127.0.0.1'" in text
    assert server.api_key not in text                                       # never in the log


@pytest.mark.skipif(sys.platform == "win32", reason="the fake server binary is a POSIX script")
def test_server_that_dies_while_loading_is_reported(tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_text(f"#!{sys.executable}\nimport sys\nprint('error: model file is damaged')\nsys.exit(3)\n")
    binary.chmod(0o755)
    settings = ServerSettings("focal", tmp_path / "m.gguf", "m", "0" * 64, 1, 1024, "f16", "auto", "all")
    server = LlamaServer(binary, settings, tmp_path / "log.txt", startup_timeout_s=20)
    with pytest.raises(ProviderError, match="exited while loading"):
        asyncio.run(server.start())


def test_missing_binary_tells_how_to_install(tmp_path):
    settings = ServerSettings("focal", tmp_path / "m.gguf", "m", "0" * 64, 1, 1024, "f16", "auto", "all")
    with pytest.raises(ProviderError, match="install_llama.py"):
        asyncio.run(LlamaServer(tmp_path / "nope", settings).start())


def test_stand_in_command_line_needs_a_key(monkeypatch, capsys):
    monkeypatch.setenv(standin.KEY_ENV, "short")
    assert standin.main([]) == 2
    assert os.environ[standin.KEY_ENV] == "short"
