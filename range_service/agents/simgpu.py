"""A fake model on a simulated shared GPU (G3f, D-75 to D-78): a stand-in for measuring contention.

In Option C two llama-server processes share one GPU. Nothing in the cloud has that GPU, so the
G3f conditions (focal prompt layout, short answers, the focal-first GPU guard) are measured here
against a stand-in whose *only* job is to reproduce the mechanism, with numbers taken from the
owner's bake-off:

- **One GPU, shared between servers; slots batched within a server.** Each server with work in
  flight gets an equal share of the GPU (two processes time-slice one GPU). Within a server,
  llama-server batches its busy slots: each of k calls runs at 1 / (1 + ``batch_cost`` x (k - 1))
  of the server's speed (``batch_cost`` 0.3: batching is cheap, not free). A call alone runs at its
  model's full speed. Work is prefill (uncached prompt tokens / prompt tok/s) then generation
  (generated tokens / gen tok/s). Checked against the owner's numbers: N3's generation p50 was
  984 ms in LIVE and 2040 ms in LIVE_LOAD (three more NPC streams and Robot R): about 2x.
- **Speeds per model** from the owner's offline bake-off (RTX 4070 Ti SUPER, KV q8_0, G3b result):
  F3 2480 / 66.3 tok/s, F1 4220 / 94.7, N3 5857 / 139.6, N1 4238 / 127.7, S1 9165 / 208.8.
- **Cache reuse like llama-server b12443 on sliding-window and hybrid models**: a slot reuses its
  previous prompt only up to a message start (context checkpoints, D-59). One-message prompts
  reuse nothing; a system-message prefix is reused whole when the slot last held the same one.
- **Answers**: the Demo policy's choice (as ``FakeModel``), plus a ``reason_summary`` as long as
  the model's verbosity and the answer schema allow (so the SHORT condition shortens it, as it
  would a real model's), plus a fixed overhead for the whitespace and fields real models add.
  Calibrated so Robot R's answer is ~135 tokens, about what the owner's F1 timings imply
  (p50 1894 ms alone: ~0.5 s prefill + ~1.4 s at 94.7 tok/s).

This is a model of the mechanism, not a measurement of the owner's GPU: it says whether a
condition helps and roughly how much under these assumptions. The owner's PC measures each
condition for real (docs/gates/G3f_OWNER_CHECKLIST.md). Cancellation: a call whose client gives up
leaves the GPU at once (``cancel_lag_s``, default 0); llama-server notices a closed connection
within its polling interval, so the real cost of a timed-out call is somewhat higher.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from .gateway import ModelRequest, ModelResponse

# Owner's offline bake-off, KV q8_0 (G3b result, prompts_v1): prompt tok/s, generation tok/s.
PROFILES: dict[str, tuple[float, float]] = {
    "F3": (2480.0, 66.3), "F1": (4220.0, 94.7), "N3": (5857.0, 139.6), "N1": (4238.0, 127.7), "S1": (9165.0, 208.8),
}
CHARS_PER_TOKEN = 4
ANSWER_OVERHEAD_TOKENS = 30        # whitespace, field names and quoting real models add
REASON_VERBOSITY_CHARS = 250       # how long a reason a model writes when the schema lets it


class SimGpu:
    """One GPU shared by every call in flight (processor sharing), in wall-clock time."""

    def __init__(self, time_scale: float = 1.0, cancel_lag_s: float = 0.0, batch_cost: float = 0.3) -> None:
        self.time_scale = time_scale              # < 1 runs the simulation faster than real time
        self.cancel_lag_s = cancel_lag_s
        self.batch_cost = batch_cost
        self._jobs: dict[int, list[Any]] = {}     # id -> [remaining work in seconds at full speed, future, server]
        self._seq = 0
        self._last = time.monotonic()
        self._timer: asyncio.TimerHandle | None = None
        self.busy_s = 0.0
        self.peak_concurrency = 0

    @property
    def in_flight(self) -> int:
        return len(self._jobs)

    def _rates(self) -> dict[int, float]:
        """Each job's share of full speed now: 1 / servers busy x 1 / (1 + batch_cost x (k - 1))."""
        per_server: dict[str, int] = {}
        for job in self._jobs.values():
            per_server[job[2]] = per_server.get(job[2], 0) + 1
        m = len(per_server)
        return {key: 1.0 / m / (1.0 + self.batch_cost * (per_server[job[2]] - 1)) for key, job in self._jobs.items()}

    def _advance(self) -> None:
        now = time.monotonic()
        dt = (now - self._last) / self.time_scale
        self._last = now
        if self._jobs and dt > 0:
            self.busy_s += dt
            for key, rate in self._rates().items():
                self._jobs[key][0] -= dt * rate

    def _reschedule(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        for key, job in list(self._jobs.items()):
            if job[0] <= 1e-9:
                del self._jobs[key]
                if not job[1].done():
                    job[1].set_result(None)
        if not self._jobs:
            return
        rates = self._rates()
        nxt = min(job[0] / rates[key] for key, job in self._jobs.items()) * self.time_scale
        self._timer = asyncio.get_running_loop().call_later(max(0.0, nxt), self._tick)

    def _tick(self) -> None:
        self._timer = None
        self._advance()
        self._reschedule()

    async def run(self, work_s: float, server: str = "focal") -> None:
        """Do ``work_s`` seconds of full-speed GPU work on ``server``, shared with everything else in flight."""
        if work_s <= 0:
            return
        self._advance()
        self._seq += 1
        key = self._seq
        fut = asyncio.get_running_loop().create_future()
        self._jobs[key] = [work_s, fut, server]
        self.peak_concurrency = max(self.peak_concurrency, len(self._jobs))
        self._reschedule()
        try:
            await fut
        except asyncio.CancelledError:
            if self.cancel_lag_s > 0 and key in self._jobs:
                asyncio.get_running_loop().call_later(self.cancel_lag_s * self.time_scale, self._drop, key)
            else:
                self._drop(key)
            raise

    def _drop(self, key: int) -> None:
        self._advance()
        self._jobs.pop(key, None)
        self._reschedule()


def _reason_max(schema: dict[str, Any] | None) -> int:
    """How long a reason the answer may carry: the schema's limit; none when the schema has no
    reason_summary (LEAN, G3g D-85); 300 without a schema."""
    props = schema.get("properties") if isinstance(schema, dict) else None
    if isinstance(props, dict) and "reason_summary" not in props:
        return 0
    try:
        return int(schema["properties"]["reason_summary"]["maxLength"])   # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return 300


@dataclass
class SimGpuModel:
    """A gateway provider on a ``SimGpu``. ``profile`` names the model's speeds (PROFILES)."""

    gpu: SimGpu
    profile: str = "F3"
    system_prefix: bool = True
    server: str = "focal"
    reason_chars: int = REASON_VERBOSITY_CHARS
    name: str = "SIMGPU"
    calls: list[ModelRequest] = field(default_factory=list)
    _slot_system: dict[Any, str | None] = field(default_factory=dict)

    @property
    def model_id(self) -> str:
        return f"simgpu-{self.profile.lower()}-v1"

    def _messages(self, request: ModelRequest) -> tuple[str | None, str]:
        p = request.prefix
        if p and self.system_prefix and request.prompt.startswith(p) and len(request.prompt) > len(p):
            return p, request.prompt[len(p):]
        return None, request.prompt

    def answer(self, request: ModelRequest) -> str:
        base = request.demo_hint or '{"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}]}'
        data = json.loads(base)
        n = min(self.reason_chars, _reason_max(request.output_schema))
        if n > 0:
            data["reason_summary"] = ("Answering the person who spoke to me, as my task says. " * 8)[:n].rstrip()
        return json.dumps(data, sort_keys=True)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        prompt_tps, gen_tps = PROFILES[self.profile]
        system, _user = self._messages(request)
        slot = request.slot if request.slot >= 0 else request.agent_id
        prompt_tokens = len(request.prompt) // CHARS_PER_TOKEN
        # Context checkpoints only at message starts (D-59): the system prefix is reused whole if
        # this slot's last prompt had the same one; a one-message prompt reuses nothing.
        cached = len(system) // CHARS_PER_TOKEN if system is not None and self._slot_system.get(slot) == system else 0
        self._slot_system[slot] = system
        text = self.answer(request)
        gen_tokens = min(request.max_tokens, len(text) // CHARS_PER_TOKEN + ANSWER_OVERHEAD_TOKENS)
        t0 = time.perf_counter()
        await self.gpu.run((prompt_tokens - cached) / prompt_tps, self.server)
        t1 = time.perf_counter()
        await self.gpu.run(gen_tokens / gen_tps, self.server)
        t2 = time.perf_counter()
        return ModelResponse(text, self.model_id, prefill_ms=round((t1 - t0) * 1000), generation_ms=round((t2 - t1) * 1000),
                             prompt_tokens=prompt_tokens, cached_tokens=cached, generated_tokens=gen_tokens,
                             slot=request.slot if request.slot >= 0 else None)
