"""The model gateway (Blueprint §10.3, INFERENCE_STRATEGY §2, D-21, D-50).

A provider-neutral interface between agents and models. Agents never call a model directly.

- **Providers** implement ``complete(request) -> response``. G3a has ``FakeModel`` (deterministic,
  scriptable: valid, malformed, slow) and ``ReplayModel`` (serves a recorded run). G3b adds
  ``LlamaProvider`` (llama-server on 127.0.0.1; agents/llama.py). A provider that runs a server
  has ``start()`` and ``stop()``; the gateway passes them on. Each request carries the JSON
  schema of the agent's allowed actions (agents/output_schema.py) for constrained output.
- **Output** is one JSON object ``{"actions": [{"action", "args"}], "reason_summary"}`` with 1–3
  actions. A SPEAK, GESTURE or EXPRESS may add ``"commitment"`` (what it promises) or
  ``"fulfills_commitment": true``. Each becomes an ``action_request`` checked against contracts/action_request and the
  agent's allowed actions. Model text is only ever parsed as data; nothing in it is executed.
- **Invalid output** gets exactly one repair request that quotes the problem; still invalid →
  ``WAIT`` with a machine-readable error (T26).
- **Timeouts:** each tier has a deadline; when it passes, the agent does ``WAIT`` and the late
  answer is discarded (T25).
- **Record and replay** (T20): every call is returned as a ``decision_record`` model-call entry
  with the prompt hash, response text and timings. ``ReplayModel`` serves those responses in
  order and reports a changed prompt as ``REPLAY_DIVERGED``: a rerun, never a replay.
- **One slot** (INFERENCE_STRATEGY Option A): calls queue on a semaphore; queue time is logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from range_service import contracts

DEADLINES_MS = {"FOCAL": 4000, "C2": 6000, "C1": 3000}
MAX_ACTIONS = 3
# Actions that can carry a promise: words, or a nod/expression toward someone (a nonverbal "I'll be with you").
PROMISE_ACTIONS = frozenset({"SPEAK", "GESTURE", "EXPRESS"})
FALLBACK_WAIT_MS = 1000
REPAIR_NOTE = ("Your previous answer could not be used: {error}. Answer again with one JSON object only, "
               "using only the listed actions.")
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class ReplayDiverged(Exception):
    """The prompt differs from the recorded one: this is a rerun, not a replay."""


class ProviderError(Exception):
    pass


@dataclass
class ModelRequest:
    agent_id: str
    call_id: str
    tier: str
    prompt: str
    prompt_sha256: str
    max_tokens: int
    attempt: int
    # What the Demo policy would do now, as JSON. Only FakeModel may read it (to stand in for a
    # model deterministically); it is never part of the prompt.
    demo_hint: str | None = None
    # JSON schema of a valid answer for this agent (constrained output, D-21); None = unconstrained.
    output_schema: dict[str, Any] | None = None


@dataclass
class ModelResponse:
    text: str
    model_id: str
    prefill_ms: int | None = None
    generation_ms: int | None = None
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    generated_tokens: int | None = None


class Provider(Protocol):
    name: str

    async def complete(self, request: ModelRequest) -> ModelResponse: ...


class FakeModel:
    """A deterministic stand-in for a model.

    ``responder(request) -> text`` decides the answer; by default it repeats the Demo policy's
    choice (``demo_hint``). ``delay_ms`` adds a real wait, to test slow models (T25).
    """

    name = "FAKE"

    def __init__(self, responder: Callable[[ModelRequest], str] | None = None, delay_ms: int = 0,
                 model_id: str = "fake-demo-v1") -> None:
        self.responder = responder or (lambda r: r.demo_hint or '{"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}]}')
        self.delay_ms = delay_ms
        self.model_id = model_id
        self.calls: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)
        return ModelResponse(self.responder(request), self.model_id, prompt_tokens=None)


def scripted_responses(texts: list[str]) -> Callable[[ModelRequest], str]:
    """A responder that answers with ``texts`` in order (the last one repeats)."""
    state = {"i": 0}

    def respond(_request: ModelRequest) -> str:
        text = texts[min(state["i"], len(texts) - 1)]
        state["i"] += 1
        return text
    return respond


class ReplayModel:
    """Serves the model responses recorded in a run's decision records, in order, per agent."""

    name = "REPLAY"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.queues: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            for call in record["model_calls"]:
                self.queues.setdefault(record["agent_id"], []).append(call)

    @classmethod
    def from_file(cls, path: Path) -> "ReplayModel":
        lines = path.read_text(encoding="utf-8").splitlines()
        return cls([json.loads(line) for line in lines if line.strip()])

    async def complete(self, request: ModelRequest) -> ModelResponse:
        queue = self.queues.get(request.agent_id, [])
        if not queue:
            raise ReplayDiverged("no recorded call left for this agent")
        call = queue.pop(0)
        if call["prompt_sha256"] != request.prompt_sha256:
            raise ReplayDiverged("the prompt differs from the recorded one")
        if call["outcome"] == "TIMEOUT":
            raise asyncio.TimeoutError()
        if call["outcome"] == "PROVIDER_ERROR" or call["response_text"] is None:
            raise ProviderError(call.get("error") or "recorded provider error")
        return ModelResponse(call["response_text"], call.get("model_id", "replay"))


@dataclass
class GatewayResult:
    actions: list[dict[str, Any]]                 # [{"action", "args"}] ready to become requests
    reason_summary: str | None
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    fallback: dict[str, str] | None = None


def parse_output(text: str, allowed_actions: list[str], agent_id: str, tick: int) -> tuple[list[dict[str, Any]] | None, str | None, str | None]:
    """Parse model text into actions. Returns (actions, reason_summary, error)."""
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except ValueError:
        return None, None, "the answer is not valid JSON"
    if not isinstance(data, dict) or set(data) - {"actions", "reason_summary"} or "actions" not in data:
        return None, None, 'the answer must be an object with "actions" and optionally "reason_summary"'
    actions = data["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        return None, None, f'"actions" must be a list of 1 to {MAX_ACTIONS} actions'
    reason = data.get("reason_summary")
    if reason is not None and (not isinstance(reason, str) or len(reason) > 300):
        return None, None, '"reason_summary" must be text of at most 300 characters'
    out = []
    for i, entry in enumerate(actions):
        if not isinstance(entry, dict) or not {"action", "args"} <= set(entry) \
                or set(entry) - {"action", "args", "commitment", "fulfills_commitment"}:
            return None, None, f'action {i + 1} must have "action" and "args" (and optionally "commitment")'
        extra = set(entry) - {"action", "args"}
        if extra and entry["action"] not in PROMISE_ACTIONS:
            return None, None, f'action {i + 1}: only SPEAK, GESTURE or EXPRESS may carry "commitment" or "fulfills_commitment"'
        if "commitment" in entry and (not isinstance(entry["commitment"], str) or not 1 <= len(entry["commitment"]) <= 200):
            return None, None, f'action {i + 1}: "commitment" must be text of 1 to 200 characters'
        if "fulfills_commitment" in entry and not isinstance(entry["fulfills_commitment"], bool):
            return None, None, f'action {i + 1}: "fulfills_commitment" must be true or false'
        if entry["action"] not in allowed_actions:
            return None, None, f"action {i + 1}: {str(entry['action'])[:40]!r} is not one of your actions"
        probe = {"schema_version": "1.0", "action_request_id": "act_probe", "agent_id": agent_id,
                 "based_on_tick_id": tick, "action": entry["action"], "args": entry["args"]}
        found = contracts.problems("action_request", probe)
        if found:
            return None, None, f"action {i + 1} ({entry['action']}): {str(found[0])[:200]}"
        out.append({k: entry[k] for k in ("action", "args", "commitment", "fulfills_commitment") if k in entry})
    return out, reason, None


class ModelGateway:
    def __init__(self, provider: Provider, deadlines_ms: dict[str, int] | None = None, max_concurrent: int = 1) -> None:
        self.provider = provider
        self.deadlines_ms = dict(DEADLINES_MS, **(deadlines_ms or {}))
        self._slots = asyncio.Semaphore(max_concurrent)
        self._calls = 0

    async def start(self) -> None:
        if hasattr(self.provider, "start"):
            await self.provider.start()

    async def stop(self) -> None:
        if hasattr(self.provider, "stop"):
            await self.provider.stop()

    def _call_id(self, agent_id: str) -> str:
        self._calls += 1
        return f"call_{agent_id}_{self._calls:06d}"[:64]

    async def _one(self, request: ModelRequest, deadline_ms: int) -> tuple[ModelResponse | None, dict[str, Any]]:
        started = time.perf_counter()
        response: ModelResponse | None = None
        outcome, error = "VALID", None
        queue_ms = 0
        try:
            async with asyncio.timeout(deadline_ms / 1000):
                async with self._slots:
                    queue_ms = round((time.perf_counter() - started) * 1000)
                    response = await self.provider.complete(request)
        except TimeoutError:
            outcome, error = "TIMEOUT", f"no answer within {deadline_ms} ms"
        except ReplayDiverged as exc:
            outcome, error = "REPLAY_DIVERGED", str(exc)[:300]
        except ProviderError as exc:
            outcome, error = "PROVIDER_ERROR", str(exc)[:300]
        total_ms = round((time.perf_counter() - started) * 1000)
        call = {
            "call_id": request.call_id, "attempt": request.attempt, "provider": self.provider.name,
            "model_id": response.model_id if response else getattr(self.provider, "model_id", self.provider.name.lower()),
            "prompt_sha256": request.prompt_sha256, "response_text": response.text[:8000] if response else None,
            "outcome": outcome, "error": error, "deadline_ms": deadline_ms,
            "timings": {"queue_ms": queue_ms, "prefill_ms": response.prefill_ms if response else None,
                        "generation_ms": response.generation_ms if response else None, "total_ms": total_ms},
            "prompt_tokens": response.prompt_tokens if response else None,
            "cached_tokens": response.cached_tokens if response else None,
            "generated_tokens": response.generated_tokens if response else None,
        }
        return response, call

    async def decide(self, *, agent_id: str, tier: str, prompt: str, prompt_sha256: str, max_tokens: int,
                     allowed_actions: list[str], tick: int, demo_hint: str | None = None) -> GatewayResult:
        from .output_schema import answer_schema   # noqa: PLC0415 (it imports this module)

        deadline_ms = self.deadlines_ms[tier]
        calls: list[dict[str, Any]] = []
        schema = answer_schema(tuple(allowed_actions))
        request = ModelRequest(agent_id, self._call_id(agent_id), tier, prompt, prompt_sha256, max_tokens, 0, demo_hint,
                               schema)
        for attempt in (0, 1):
            response, call = await self._one(request, deadline_ms)
            calls.append(call)
            if response is None:
                reason = {"TIMEOUT": "TIMEOUT", "REPLAY_DIVERGED": "REPLAY_DIVERGED"}.get(call["outcome"], "PROVIDER_ERROR")
                return GatewayResult(fallback_actions(), None, calls, {"action": "WAIT", "reason": reason})
            actions, reason_summary, error = parse_output(response.text, allowed_actions, agent_id, tick)
            if error is None:
                return GatewayResult(actions or [], reason_summary, calls)
            call["outcome"], call["error"] = "INVALID_OUTPUT", error[:300]
            if attempt == 0:
                repaired = prompt + "\n\n## REPAIR\n" + REPAIR_NOTE.format(error=error)
                request = ModelRequest(agent_id, self._call_id(agent_id), tier, repaired,
                                       hashlib.sha256(repaired.encode("utf-8")).hexdigest(), max_tokens, 1, demo_hint,
                                       schema)
        return GatewayResult(fallback_actions(), None, calls, {"action": "WAIT", "reason": "INVALID_OUTPUT"})


def tokenizer_for(gateway: ModelGateway | None):
    """The model's own tokenizer when the gateway talks to llama-server (D-51 re-measured at
    G3b), else None (the runtime keeps the estimate). Call after ``await gateway.start()``."""
    from .llama import LlamaProvider, ServerTokenizer   # noqa: PLC0415

    if gateway is None or not isinstance(gateway.provider, LlamaProvider):
        return None
    p = gateway.provider
    return ServerTokenizer(p.port, p.api_key, p.model_id)


def fallback_actions() -> list[dict[str, Any]]:
    return [{"action": "WAIT", "args": {"duration_ms": FALLBACK_WAIT_MS}}]


MALFORMED_SAMPLES = [
    "Sure! I'll wave at them now.",                                              # not JSON
    '{"actions": [{"action": "RUN_SHELL", "args": {"command": "rm -rf /"}}]}',     # not an action: nothing runs
]


def gateway_from_spec(spec: str, *, log_path: Path | None = None, seed: int | None = None) -> ModelGateway | None:
    """Model choice from the command line: ``none``, ``fake``, ``fake-slow:MS``, ``fake-malformed``,
    ``replay:PATH`` (G3a); ``llama`` (configs/inference.yaml as it is), ``llama:MODEL`` (another
    catalog id, label or local id) or ``llama-attach:PORT`` (a server already running on
    127.0.0.1:PORT, key in RANGE_LLAMA_API_KEY) (G3b). A llama gateway must be started
    (``await gateway.start()``) and stopped; its ``setup`` describes the model for the manifest."""
    if spec == "none":
        return None
    if spec == "fake":
        return ModelGateway(FakeModel())
    if spec.startswith("fake-slow:"):
        return ModelGateway(FakeModel(delay_ms=int(spec.split(":", 1)[1]), model_id="fake-slow-v1"))
    if spec == "fake-malformed":
        return ModelGateway(FakeModel(responder=scripted_responses(MALFORMED_SAMPLES), model_id="fake-malformed-v1"))
    if spec.startswith("replay:"):
        return ModelGateway(ReplayModel.from_file(Path(spec.split(":", 1)[1])))
    if spec == "llama" or spec.startswith("llama:"):
        from .inference import build_llama   # noqa: PLC0415

        setup = build_llama(spec.split(":", 1)[1] if ":" in spec else None, log_path=log_path, seed=seed)
        setup.gateway.setup = setup   # type: ignore[attr-defined]
        return setup.gateway
    if spec.startswith("llama-attach:"):
        from .inference import load_inference   # noqa: PLC0415
        from .llama import LlamaProvider   # noqa: PLC0415

        inf = load_inference()
        provider = LlamaProvider.attach(int(spec.split(":", 1)[1]), sampling=inf["sampling"],
                                        structured_output=inf["structured_output"], thinking=inf["thinking"],
                                        warm_up=False)
        return ModelGateway(provider, deadlines_ms={t: s["deadline_ms"] for t, s in inf["tiers"].items()})
    raise ValueError(f"unknown model {spec!r}: use none, fake, fake-slow:MS, fake-malformed, replay:PATH, "
                     "llama, llama:MODEL or llama-attach:PORT")
