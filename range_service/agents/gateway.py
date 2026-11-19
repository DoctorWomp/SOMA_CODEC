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
  answer is discarded (T25). **One deadline per decision** (G3d, D-63): it covers queue,
  generation and the repair. A repair gets only the time that is left, and only if that is at
  least ``max(REPAIR_MIN_MS, the first attempt's model time)``; otherwise the decision falls back
  to ``WAIT`` at once, saying why. The world's stale window is derived from this (D-63).
- **Record and replay** (T20): every call is returned as a ``decision_record`` model-call entry
  with the prompt hash, response text and timings. ``ReplayModel`` serves those responses in
  order and reports a changed prompt as ``REPLAY_DIVERGED``: a rerun, never a replay.
- **Scheduling**: without a scheduler, calls queue on a semaphore in arrival order (INFERENCE_STRATEGY
  Option A). With a ``SlotScheduler`` (agents/scheduler.py; Option B, G3b-2) focal agents own a
  pinned slot, others are served by priority with aging, and calls that could only answer late
  are dropped before they reach the model. Queue time is logged either way.
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
# A repair is only tried if at least this much of the decision's deadline is left (and at least
# as long as the first attempt took at the model): the scheduler's min_service_ms (G3d, D-63).
REPAIR_MIN_MS = 300
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
    # The engine slot the scheduler granted (-1 = none: the provider chooses).
    slot: int = -1
    # The agent's stable persona prefix (guardrails + identity) and its key (G3c-1, T5/T6): the
    # provider uses them to tell whether the slot already holds the prefix, or to restore it.
    prefix_key: str | None = None
    # The prefix text itself, for NPC calls (G3c-1): a provider may send it as a separate system
    # message, so a hybrid or sliding-window model can reuse it (llama-server makes its context
    # checkpoints at message starts). The prompt hash is the whole prompt's either way.
    prefix: str | None = None


@dataclass
class ModelResponse:
    text: str
    model_id: str
    prefill_ms: int | None = None
    generation_ms: int | None = None
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    generated_tokens: int | None = None
    slot: int | None = None
    prefix_state: str | None = None   # WARM, RESTORED, COLD or UNKNOWN (G3c-1); None if no persona prefix
    truncated: bool = False           # the engine stopped at the token limit (finish_reason "length")


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
    activity: dict[str, Any] | None = None        # the answer's optional activity, as given (G3c-2)
    fallback_error: str | None = None             # why the last answer could not be used


def answer_activity(text: str) -> dict[str, Any] | None:
    """The optional ``activity`` of an answer that parse_output accepted (G3c-2)."""
    body = text.strip()
    fenced = _FENCE.match(body)
    data = json.loads(fenced.group(1) if fenced else body)
    return data.get("activity") if isinstance(data, dict) else None


def parse_output(text: str, allowed_actions: list[str], agent_id: str, tick: int,
                 allow_activity: bool = False) -> tuple[list[dict[str, Any]] | None, str | None, str | None]:
    """Parse model text into actions. Returns (actions, reason_summary, error). With
    ``allow_activity`` (G3c-2) the answer may also carry an ``activity``, checked by the runtime."""
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except ValueError:
        return None, None, "the answer is not valid JSON"
    keys = {"actions", "reason_summary"} | ({"activity"} if allow_activity else set())
    if not isinstance(data, dict) or set(data) - keys or "actions" not in data:
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


class ServerActivity:
    """When each model server is computing (G3c-2, D-60). Two llama-server processes share one GPU
    in Option C, so a call's time can depend on the other server's work: each model call records
    how long the other server was busy during it (``other_server_busy_ms``)."""

    KEEP = 400

    def __init__(self) -> None:
        self.intervals: dict[str, list[list[float | None]]] = {}

    def begin(self, server: str) -> list[float | None]:
        iv: list[float | None] = [time.perf_counter(), None]
        rows = self.intervals.setdefault(server, [])
        rows.append(iv)
        if len(rows) > self.KEEP:
            del rows[: len(rows) - self.KEEP]
        return iv

    @staticmethod
    def end(iv: list[float | None]) -> None:
        iv[1] = time.perf_counter()

    def other_busy_ms(self, server: str, start: float, end: float) -> int:
        """Milliseconds of [start, end] during which any other server had a call in flight."""
        spans = sorted((max(s, start), min(e if e is not None else end, end))
                       for other, rows in self.intervals.items() if other != server
                       for s, e in rows if (e is None or e > start) and s < end)
        total, cur_s, cur_e = 0.0, None, None
        for s, e in spans:
            if e <= s:
                continue
            if cur_e is None or s > cur_e:
                if cur_e is not None:
                    total += cur_e - cur_s
                cur_s, cur_e = s, e
            else:
                cur_e = max(cur_e, e)
        if cur_e is not None:
            total += cur_e - cur_s
        return round(total * 1000)


class ModelGateway:
    def __init__(self, provider: Provider, deadlines_ms: dict[str, int] | None = None, max_concurrent: int = 1,
                 scheduler: Any = None, server: str | None = None) -> None:
        self.provider = provider
        self.deadlines_ms = dict(DEADLINES_MS, **(deadlines_ms or {}))
        self._slots = asyncio.Semaphore(max_concurrent)
        self.scheduler = scheduler
        self.server = server              # which server this gateway talks to (focal / npc), for records
        self.refuse_tiers: frozenset[str] = frozenset()   # Option C: the NPC server never serves FOCAL
        self.activity: ServerActivity | None = None       # shared by both servers in Option C (G3c-2)
        self.persona_events: list[dict[str, Any]] = []
        self.recent_totals: dict[str, list[int]] = {}      # tier -> last call times (pulse: is this server busy?)
        self._calls = 0
        # G3f conditions (configs/inference.yaml ``focal``, D-76, D-77): how FOCAL calls are sent.
        self.prompt_layout = "ONE_MESSAGE"                 # or SYSTEM_PREFIX: the runtime passes Robot R's prefix
        self.answer = "FULL"                               # or SHORT: shorter text limits for FOCAL answers
        # G3f (D-78): the focal-first GPU guard. On Robot R's gateway, every call marks the guard busy.
        self.guard: Any = None

    async def start(self) -> None:
        if hasattr(self.provider, "start"):
            await self.provider.start()

    async def stop(self) -> None:
        if hasattr(self.provider, "stop"):
            await self.provider.stop()

    def _call_id(self, agent_id: str) -> str:
        self._calls += 1
        return f"call_{agent_id}_{self._calls:06d}"[:64]

    # ---------- persona snapshots (T5) and pre-warming (T6), G3c-1 ----------

    def supports_personas(self) -> bool:
        return hasattr(self.provider, "prewarm") and hasattr(self.provider, "snapshot")

    async def prepare_personas(self, personas: list[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
        """T5 at scene load: (agent_id, tier, key, prefix) for every model-driven NPC level. Each is
        warmed into a free shared slot and saved where the server supports it. Never waits for a slot."""
        out = []
        for agent_id, tier, key, prefix in personas:
            out.append(await self._persona_op("snapshot", agent_id, tier, key, prefix))
        return out

    async def prewarm(self, agent_id: str, tier: str, key: str, prefix: str) -> dict[str, Any]:
        """T6: a promotion looks likely; put the persona prefix in a free slot before the first call."""
        return await self._persona_op("prewarm", agent_id, tier, key, prefix)

    async def _persona_op(self, op: str, agent_id: str, tier: str, key: str, prefix: str) -> dict[str, Any]:
        base = {"event": "PERSONA_SNAPSHOT" if op == "snapshot" else "PREWARM", "agent_id": agent_id, "tier": tier,
                "key": key, "server": self.server}
        if not self.supports_personas():
            entry = dict(base, method="NONE", note=f"provider {self.provider.name} has no slots")
        elif self.scheduler is None:
            entry = dict(base, method="SKIPPED", note="no slot scheduler (FIFO): the slot cannot be chosen")
        else:
            # Snapshots run at scene load, before any real call; a pre-warm during the run must
            # leave a slot free for a real call that may arrive meanwhile (G3c-2, D-60).
            slot = self.scheduler.try_acquire(agent_id, keep_free=0 if op == "snapshot" else 1)
            if slot is None:
                entry = dict(base, method="SKIPPED", note="no free slot" if op == "snapshot" else
                             "would leave no free slot for a real call")
            else:
                try:
                    result = await getattr(self.provider, op)(key, prefix, slot)
                    entry = dict(base, **{k: v for k, v in result.items() if k not in ("event", "key")})
                except ProviderError as exc:
                    entry = dict(base, method="FAILED", slot=slot, note=str(exc)[:200])
                finally:
                    self.scheduler.release(slot)
        self.persona_events.append(entry)
        return entry

    async def _one(self, request: ModelRequest, deadline_ms: int, background: bool = False,
                   label: dict[str, Any] | None = None) -> tuple[ModelResponse | None, dict[str, Any]]:
        started = time.perf_counter()
        response: ModelResponse | None = None
        outcome, error = "VALID", None
        queue_ms = 0
        from .scheduler import Dropped   # noqa: PLC0415

        try:
            async with asyncio.timeout(deadline_ms / 1000):
                if self.scheduler is not None:
                    slot = await self.scheduler.acquire(request.agent_id, request.tier,
                                                        time.monotonic() + deadline_ms / 1000, background=background,
                                                        label=dict(label or {}, deadline_ms=deadline_ms,
                                                                   est_cost_tokens=len(request.prompt) // 4))
                    queue_ms = round((time.perf_counter() - started) * 1000)
                    request.slot = slot
                    busy = self.activity.begin(self.server or "?") if self.activity is not None else None
                    if self.guard is not None:
                        self.guard.focal_begin()
                    try:
                        response = await self.provider.complete(request)
                    finally:
                        if self.guard is not None:
                            self.guard.focal_end()
                        if busy is not None:
                            self.activity.end(busy)
                        self.scheduler.release(slot)
                else:
                    async with self._slots:
                        queue_ms = round((time.perf_counter() - started) * 1000)
                        if self.guard is not None:
                            self.guard.focal_begin()
                        try:
                            response = await self.provider.complete(request)
                        finally:
                            if self.guard is not None:
                                self.guard.focal_end()
        except TimeoutError:
            outcome, error = "TIMEOUT", f"no answer within {deadline_ms} ms"
        except Dropped as exc:
            queue_ms = round((time.perf_counter() - started) * 1000)
            outcome, error = "TIMEOUT", f"dropped before reaching the model: {exc}"[:300]
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
        # G3c-1 instrumentation (INFERENCE_STRATEGY §7): which server and slot, and whether the
        # persona prefix was already in the slot. Optional fields: absent for fake and replay.
        if self.server is not None:
            call["server"] = self.server
        if response is not None and response.slot is not None:
            call["slot"] = response.slot
        if response is not None and response.prefix_state is not None:
            call["prefix_state"] = response.prefix_state
        if self.activity is not None:
            call["other_server_busy_ms"] = self.activity.other_busy_ms(self.server or "?", started, time.perf_counter())
        recent = self.recent_totals.setdefault(request.tier, [])
        recent.append(total_ms)
        del recent[:-8]
        return response, call

    def busy_share(self, tier: str) -> float:
        """Median of the last calls' time as a share of the tier deadline (G3c-2: pulse reviews
        are skipped for NPCs while their calls are already near the deadline)."""
        recent = sorted(self.recent_totals.get(tier, []))
        if not recent:
            return 0.0
        return recent[len(recent) // 2] / self.deadlines_ms.get(tier, 1)

    async def decide(self, *, agent_id: str, tier: str, prompt: str, prompt_sha256: str, max_tokens: int,
                     allowed_actions: list[str], tick: int, demo_hint: str | None = None,
                     prefix_key: str | None = None, prefix: str | None = None,
                     choices: dict[str, Any] | None = None, background: bool = False,
                     check: Callable[[list[dict[str, Any]], dict[str, Any] | None], str | None] | None = None,
                     started_at: float | None = None, evidence_ms: int | None = None) -> GatewayResult:
        """``choices`` (G3c-2, D-60): what the agent may name now, for the constrained answer:
        ``targets`` (perceived track ids), ``channels``, ``gestures``, ``expressions``, and
        ``activity`` (G3c-2: the answer may carry an activity; its value is the longest review time).
        Absent keys keep the contract's full range. ``background``: a pulse review, scheduled after
        every real call. ``check(actions, activity)`` is the runtime's policy check (activity rules,
        FN-1): an error gets the same one repair as invalid output. ``started_at``: when the decision
        started (``time.monotonic()``); the tier deadline counts from then (G3d, D-63)."""
        from .output_schema import ALL_CHANNELS, answer_schema   # noqa: PLC0415 (it imports this module)

        if tier in self.refuse_tiers:
            raise ValueError(f"the {self.server} server does not serve {tier} calls (Option C routing)")
        deadline_ms = self.deadlines_ms[tier]
        calls: list[dict[str, Any]] = []
        c = choices or {}
        limits = tier if tier in ("FOCAL", "C2", "C1") else "C1"
        if limits == "FOCAL" and self.answer == "SHORT":
            limits = "FOCAL_SHORT"                         # G3f (D-77)
        schema = answer_schema(tuple(allowed_actions), tuple(c["targets"]) if c.get("targets") is not None else None,
                               tuple(c.get("channels", ALL_CHANNELS)), limits,
                               tuple(c["gestures"]) if c.get("gestures") is not None else None,
                               tuple(c["expressions"]) if c.get("expressions") is not None else None,
                               int(c["activity"]) if c.get("activity") else 0)
        allow_activity = bool(c.get("activity"))
        # One deadline for the whole decision (G3d, D-63): queue, generation and repair. The caller
        # may pass when the decision started (the runtime does); else it starts now.
        deadline_at = (started_at if started_at is not None else time.monotonic()) + deadline_ms / 1000
        request = ModelRequest(agent_id, self._call_id(agent_id), tier, prompt, prompt_sha256, max_tokens, 0, demo_hint,
                               schema, prefix_key=prefix_key, prefix=prefix)
        first_model_ms = 0
        for attempt in (0, 1):
            left_ms = round((deadline_at - time.monotonic()) * 1000)
            if attempt == 1:
                needed_ms = max(REPAIR_MIN_MS, first_model_ms)
                if left_ms < needed_ms:
                    note = f"; not repaired: {max(0, left_ms)} ms of the decision deadline left, a repair needs about {needed_ms} ms"
                    calls[-1]["error"] = (calls[-1]["error"] or "")[:300 - len(note)] + note
                    return GatewayResult(fallback_actions(), None, calls, {"action": "WAIT", "reason": "INVALID_OUTPUT"},
                                         fallback_error=calls[-1]["error"])
            if left_ms < 1:
                left_ms = 1
            response, call = await self._one(request, left_ms, background,
                                             {"layer": "DELIBERATION", "evidence_ms": evidence_ms})
            calls.append(call)
            first_model_ms = max(first_model_ms, call["timings"]["total_ms"] - call["timings"]["queue_ms"])
            if response is None:
                reason = {"TIMEOUT": "TIMEOUT", "REPLAY_DIVERGED": "REPLAY_DIVERGED"}.get(call["outcome"], "PROVIDER_ERROR")
                return GatewayResult(fallback_actions(), None, calls, {"action": "WAIT", "reason": reason})
            actions, reason_summary, error = parse_output(response.text, allowed_actions, agent_id, tick, allow_activity)
            activity = answer_activity(response.text) if error is None and allow_activity else None
            if error is None and check is not None:
                error = check(actions or [], activity)
            if error is None:
                return GatewayResult(actions or [], reason_summary, calls, activity=activity)
            if response.truncated:
                error = f"the answer was cut off at the {max_tokens}-token limit ({error})"
            call["outcome"], call["error"] = "INVALID_OUTPUT", error[:300]
            if attempt == 0:
                repaired = prompt + "\n\n## REPAIR\n" + REPAIR_NOTE.format(error=error)
                request = ModelRequest(agent_id, self._call_id(agent_id), tier, repaired,
                                       hashlib.sha256(repaired.encode("utf-8")).hexdigest(), max_tokens, 1, demo_hint,
                                       schema, prefix_key=prefix_key, prefix=prefix)
        return GatewayResult(fallback_actions(), None, calls, {"action": "WAIT", "reason": "INVALID_OUTPUT"},
                             fallback_error=calls[-1]["error"])


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
        from .inference import make_scheduler   # noqa: PLC0415

        slots = inf["servers"]["focal"]["parallel_slots"]
        provider = LlamaProvider.attach(int(spec.split(":", 1)[1]), sampling=inf["sampling"],
                                        structured_output=inf["structured_output"], thinking=inf["thinking"],
                                        warm_up=False, parallel_slots=slots)
        return ModelGateway(provider, deadlines_ms={t: s["deadline_ms"] for t, s in inf["tiers"].items()},
                            max_concurrent=slots, scheduler=make_scheduler(inf))
    raise ValueError(f"unknown model {spec!r}: use none, fake, fake-slow:MS, fake-malformed, replay:PATH, "
                     "llama, llama:MODEL or llama-attach:PORT")
