"""llama-server behind the model gateway (G3b; D-20, D-21, D-50; INFERENCE_STRATEGY T1, T3, T4, T9).

Two parts:

- ``LlamaServer``: a llama-server child process that RANGE starts and stops. It listens on
  127.0.0.1 only, on a free port, and accepts only a fresh random API key made for this session.
  The key is handed over in the child's environment (``LLAMA_API_KEY``), never on the command
  line, and is never written to a log or a record. ``stop()`` stops only the process it started.
- ``LlamaProvider``: the gateway provider. It sends each decision as one chat request with the
  JSON schema of the agent's allowed actions (valid action JSON by construction), thinking off
  (D-20), prompt caching on, and a pinned slot per focal agent (T4); and it reads the server's
  own timings and token counts back into the decision record.

``ServerTokenizer`` counts tokens with the model's own tokenizer (``/tokenize``) instead of the
G3a estimate. The same provider can also attach to a server it did not start (``attach``), for
tests against a stand-in and for an owner who runs llama-server by hand.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import platform
import secrets
import socket
import subprocess
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import localhttp
from .gateway import ModelRequest, ModelResponse, ProviderError

LOOPBACK = localhttp.LOOPBACK
KEY_ENV = "LLAMA_API_KEY"            # read by llama-server (its --api-key environment variable)
ATTACH_KEY_ENV = "RANGE_LLAMA_API_KEY"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((LOOPBACK, 0))
        return s.getsockname()[1]


def default_binary() -> Path | None:
    from tools.install_llama import installed_binary   # noqa: PLC0415 (tools/ is on the path from the repo)
    return installed_binary()


@dataclass
class ServerSettings:
    """One entry of configs/inference.yaml ``servers`` with its model resolved to a file."""
    name: str
    model_path: Path
    model_id: str
    model_sha256: str
    parallel_slots: int
    context_per_slot: int
    kv_cache_type: str
    flash_attention: str
    gpu_layers: Any
    thinking: bool = False
    extra_args: list[str] = field(default_factory=list)
    slot_save_path: Path | None = None    # persona snapshots (T5): llama-server --slot-save-path

    def command(self, binary: Path, port: int) -> list[str]:
        cmd = [str(binary), "--model", str(self.model_path), "--host", LOOPBACK, "--port", str(port),
               "--parallel", str(self.parallel_slots), "--ctx-size", str(self.parallel_slots * self.context_per_slot),
               "--cache-type-k", self.kv_cache_type, "--cache-type-v", self.kv_cache_type,
               "--flash-attn", self.flash_attention, "--n-gpu-layers", str(self.gpu_layers),
               "--reasoning", "on" if self.thinking else "off", "--no-webui"]
        if self.slot_save_path is not None:
            cmd += ["--slot-save-path", str(self.slot_save_path)]
        return cmd + self.extra_args


class LlamaServer:
    """A llama-server child process (T1: loaded once, warmed up, resident for the whole run)."""

    def __init__(self, binary: Path, settings: ServerSettings, log_path: Path | None = None,
                 startup_timeout_s: float = 300.0) -> None:
        self.binary = binary
        self.settings = settings
        self.log_path = log_path
        self.startup_timeout_s = startup_timeout_s
        self.port = 0
        self.api_key = ""
        self.process: subprocess.Popen[bytes] | None = None
        self._log = None

    def __repr__(self) -> str:   # never show the key
        return f"LlamaServer({self.settings.model_id!r}, port={self.port})"

    async def start(self) -> None:
        if not self.binary.is_file():
            raise ProviderError(f"llama-server not found at {self.binary}; run: uv run python tools/install_llama.py")
        self.port = free_port()
        self.api_key = secrets.token_urlsafe(32)
        env = dict(os.environ)
        env[KEY_ENV] = self.api_key
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = self.log_path.open("wb")
        if self.settings.slot_save_path is not None:
            self.settings.slot_save_path.mkdir(parents=True, exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0   # type: ignore[attr-defined]
        self.process = subprocess.Popen(self.settings.command(self.binary, self.port), env=env,
                                        stdout=self._log or subprocess.DEVNULL, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, creationflags=flags)
        deadline = time.monotonic() + self.startup_timeout_s
        while True:
            if self.process.poll() is not None:
                raise ProviderError(f"llama-server exited while loading (code {self.process.returncode})"
                                    + (f"; see {self.log_path}" if self.log_path else ""))
            try:
                reply = await localhttp.request(self.port, "GET", "/health")
                if reply.status == 200:
                    return
            except localhttp.HttpError:
                pass
            if time.monotonic() > deadline:
                await self.stop()
                raise ProviderError(f"llama-server did not become ready within {self.startup_timeout_s:.0f} s")
            await asyncio.sleep(0.25)

    async def stop(self) -> None:
        """Stop the process this object started, and nothing else."""
        proc, self.process = self.process, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                await asyncio.to_thread(proc.wait, 15)
            except subprocess.TimeoutExpired:
                proc.kill()
                await asyncio.to_thread(proc.wait, 15)
        if self._log:
            self._log.close()
            self._log = None


class LlamaProvider:
    """Gateway provider for llama-server (OpenAI-compatible chat API)."""

    name = "LLAMA_SERVER"

    def __init__(self, *, server: LlamaServer | None = None, port: int = 0, api_key: str = "",
                 model_id: str = "llama", parallel_slots: int = 1, pinned_tiers: tuple[str, ...] = ("FOCAL",),
                 sampling: dict[str, Any] | None = None, thinking: bool = False, structured_output: bool = True,
                 warm_up: bool = True, system_prefix: bool = True) -> None:
        self.server = server
        self._port = port
        self._key = api_key
        self.model_id = server.settings.model_id if server else model_id
        self.parallel_slots = server.settings.parallel_slots if server else parallel_slots
        self.pinned_tiers = pinned_tiers
        self.sampling = dict(sampling or {"temperature": 0.0, "top_p": 1.0, "seed": 0})
        self.thinking = server.settings.thinking if server else thinking
        self.structured_output = structured_output
        self.warm_up = warm_up
        # G3c-1: send an NPC's persona prefix as a system message (configs/inference.yaml
        # personas.system_prefix). llama-server b12443 checkpoints hybrid and sliding-window
        # models at message starts, so only then can the whole prefix be reused.
        self.system_prefix = system_prefix
        self.pins: dict[str, int] = {}
        self.requests = 0
        # Persona snapshots and pre-warming (T5, T6; G3c-1). What each slot holds, as far as this
        # provider knows (it is the only client of its server): the persona prefix key last sent.
        self.slot_holds: dict[int, str | None] = {}
        self.snapshots: dict[str, str] = {}             # prefix key -> snapshot file name on the server
        self.snapshot_support: bool | None = None       # None: not tried; False: no --slot-save-path
        self.persona_log: list[dict[str, Any]] = []

    def __repr__(self) -> str:
        return f"LlamaProvider({self.model_id!r})"

    @classmethod
    def attach(cls, port: int, api_key: str | None = None, **kw: Any) -> "LlamaProvider":
        """Use a server already running on 127.0.0.1:port (key from RANGE_LLAMA_API_KEY)."""
        return cls(port=port, api_key=api_key if api_key is not None else os.environ.get(ATTACH_KEY_ENV, ""), **kw)

    @property
    def port(self) -> int:
        return self.server.port if self.server else self._port

    @property
    def api_key(self) -> str:
        return self.server.api_key if self.server else self._key

    async def start(self) -> None:
        if self.server:
            await self.server.start()
        if self.warm_up:
            body = self._body("Reply with the word ready.", 8, None, -1)
            await self._post(body)

    async def stop(self) -> None:
        if self.server:
            await self.server.stop()

    def slot_for(self, request: ModelRequest) -> int:
        """The slot a scheduler granted, if any (G3b-2). Otherwise the pinned slot (T4): each
        agent of a pinned tier keeps the same slot, slot 0 first; the last slot stays free for
        everyone else, so -1 (any free slot) for the rest."""
        if request.slot >= 0:
            return request.slot
        if request.tier not in self.pinned_tiers or self.parallel_slots < 2:
            return -1
        if request.agent_id not in self.pins and len(self.pins) < self.parallel_slots - 1:
            self.pins[request.agent_id] = len(self.pins)
        return self.pins.get(request.agent_id, -1)

    def _messages(self, prompt: str, prefix: str | None) -> list[dict[str, str]]:
        if prefix and self.system_prefix and prompt.startswith(prefix) and len(prompt) > len(prefix):
            return [{"role": "system", "content": prefix},
                    {"role": "user", "content": prompt[len(prefix):].lstrip("\n")}]
        return [{"role": "user", "content": prompt}]

    def _body(self, prompt: str, max_tokens: int, schema: dict[str, Any] | None, slot: int,
              prefix: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messages": self._messages(prompt, prefix),
            "max_tokens": max_tokens,
            "temperature": self.sampling.get("temperature", 0.0),
            "top_p": self.sampling.get("top_p", 1.0),
            "cache_prompt": True,                                    # T3: reuse the stable prefix
            "id_slot": slot,
            "chat_template_kwargs": {"enable_thinking": self.thinking},
        }
        if self.sampling.get("seed"):
            body["seed"] = int(self.sampling["seed"])
        if schema is not None and self.structured_output:
            body["response_format"] = {"type": "json_object", "schema": schema}
        return body

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            reply = await localhttp.request(self.port, "POST", "/v1/chat/completions", body, self.api_key)
        except localhttp.HttpError as exc:
            raise ProviderError(f"llama-server: {exc}") from exc
        if reply.status == 401:
            raise ProviderError("llama-server rejected the API key (401)")
        if reply.status != 200:
            raise ProviderError(f"llama-server answered HTTP {reply.status}: {reply.body[:200].decode('utf-8', 'replace')}")
        try:
            data = reply.json()
        except localhttp.HttpError as exc:
            raise ProviderError(f"llama-server: {exc}") from exc
        if not isinstance(data, dict):
            raise ProviderError("llama-server: the reply is not a JSON object")
        return data

    # ---------- persona snapshots (T5) and pre-warming (T6) ----------

    async def _slot_action(self, slot: int, action: str, filename: str) -> dict[str, Any] | None:
        """POST /slots/{slot}?action=save|restore. None when the server does not support slot
        actions (started without --slot-save-path); ProviderError on other failures."""
        try:
            reply = await localhttp.request(self.port, "POST", f"/slots/{slot}?action={action}",
                                            {"filename": filename}, self.api_key)
        except localhttp.HttpError as exc:
            raise ProviderError(f"llama-server slot {action}: {exc}") from exc
        if reply.status == 501:
            self.snapshot_support = False
            return None
        if reply.status != 200:
            raise ProviderError(f"llama-server slot {action} answered HTTP {reply.status}: "
                                f"{reply.body[:200].decode('utf-8', 'replace')}")
        self.snapshot_support = True
        try:
            data = reply.json()
        except localhttp.HttpError:
            return {}
        return data if isinstance(data, dict) else {}

    async def _warm_prefix(self, prefix: str, slot: int) -> None:
        """Process the prefix alone in ``slot`` (one token generated), so the engine's prefix cache
        holds it: the real prompt starts with exactly this text (INFERENCE_STRATEGY T3). With
        ``system_prefix`` the prefix goes in a system message followed by a placeholder user turn,
        exactly as the real call will send it."""
        if self.system_prefix:
            body = self._body("", 1, None, slot)
            body["messages"] = [{"role": "system", "content": prefix}, {"role": "user", "content": "(waiting)"}]
        else:
            body = self._body(prefix, 1, None, slot)
        await self._post(body)

    @staticmethod
    def snapshot_name(key: str) -> str:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in key)
        return f"persona_{safe[:100]}.bin"

    async def snapshot(self, key: str, prefix: str, slot: int) -> dict[str, Any]:
        """T5 at scene load: warm a persona prefix into ``slot`` and save that slot's state to a
        file, so a later promotion can restore it into whichever slot it gets."""
        started = time.perf_counter()
        await self._warm_prefix(prefix, slot)
        self.slot_holds[slot] = key
        method = "PREFIX_ONLY"
        if self.snapshot_support is not False:
            name = self.snapshot_name(key)
            if await self._slot_action(slot, "save", name) is not None:
                self.snapshots[key] = name
                method = "SLOT_SAVE"
        entry = {"event": "PERSONA_SNAPSHOT", "key": key, "slot": slot, "method": method,
                 "ms": round((time.perf_counter() - started) * 1000)}
        self.persona_log.append(entry)
        return entry

    async def prewarm(self, key: str, prefix: str, slot: int) -> dict[str, Any]:
        """T6: before a likely promotion, put the persona prefix into ``slot``: restore its
        snapshot where the server supports it, else send the prefix alone."""
        started = time.perf_counter()
        if self.slot_holds.get(slot) == key:
            method = "ALREADY_WARM"
        elif key in self.snapshots and await self._slot_action(slot, "restore", self.snapshots[key]) is not None:
            method = "SLOT_RESTORE"
        else:
            await self._warm_prefix(prefix, slot)
            method = "PREFIX_REQUEST"
        self.slot_holds[slot] = key
        entry = {"event": "PREWARM", "key": key, "slot": slot, "method": method,
                 "ms": round((time.perf_counter() - started) * 1000)}
        self.persona_log.append(entry)
        return entry

    async def _prepare_slot(self, request: ModelRequest, slot: int) -> str | None:
        """Before a call: is the agent's persona prefix already in this slot (WARM)? If not, restore
        its snapshot (RESTORED, T5) where there is one; else the call starts COLD."""
        if slot < 0:
            return "UNKNOWN" if request.prefix_key else None
        held = self.slot_holds.get(slot)
        self.slot_holds[slot] = request.prefix_key
        if request.prefix_key is None:
            return None
        if held == request.prefix_key:
            return "WARM"
        name = self.snapshots.get(request.prefix_key)
        if name is not None:
            try:
                if await self._slot_action(slot, "restore", name) is not None:
                    return "RESTORED"
            except ProviderError:
                pass
        return "COLD"

    # ---------- decisions ----------

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests += 1
        slot = self.slot_for(request)
        prefix_state = await self._prepare_slot(request, slot)
        data = await self._post(self._body(request.prompt, request.max_tokens, request.output_schema, slot,
                                           request.prefix))
        try:
            text = data["choices"][0]["message"]["content"]
            finish = data["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("llama-server: the reply has no choices[0].message.content") from exc
        if not isinstance(text, str):
            raise ProviderError("llama-server: the answer is not text")
        timings = data.get("timings") if isinstance(data.get("timings"), dict) else {}
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}

        def num(value: Any) -> int | None:
            return round(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None

        cached = num(timings.get("cache_n"))
        processed = num(timings.get("prompt_n"))
        prompt_tokens = num(usage.get("prompt_tokens"))
        if prompt_tokens is None and processed is not None:
            prompt_tokens = processed + (cached or 0)
        return ModelResponse(
            text=text, model_id=self.model_id,
            prefill_ms=num(timings.get("prompt_ms")), generation_ms=num(timings.get("predicted_ms")),
            prompt_tokens=prompt_tokens, cached_tokens=cached,
            generated_tokens=num(timings.get("predicted_n")) if "predicted_n" in timings else num(usage.get("completion_tokens")),
            slot=slot if slot >= 0 else None, prefix_state=prefix_state, truncated=finish == "length",
        )


class ServerTokenizer:
    """Token counts from the model's own tokenizer (llama-server ``/tokenize``), replacing the
    G3a estimate (D-51). Counts are cached per text. If the server cannot be reached, the
    estimate is used for that text and the tokenizer's name says so in every log."""

    def __init__(self, port: int, api_key: str, model_id: str, cache_size: int = 4096) -> None:
        from .tokenizer import ApproxTokenizer   # noqa: PLC0415

        self.port = port
        self._key = api_key
        self.model_id = model_id
        self._cache: OrderedDict[str, int] = OrderedDict()
        self._cache_size = cache_size
        self._approx = ApproxTokenizer()
        self.fallbacks = 0

    @property
    def name(self) -> str:
        base = f"llama_tokenize:{self.model_id}"[:60]
        return base + "+approx_fallback" if self.fallbacks else base

    def count(self, text: str) -> int:
        if not text:
            return 0
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        try:
            conn = http.client.HTTPConnection(LOOPBACK, self.port, timeout=5)
            conn.request("POST", "/tokenize", json.dumps({"content": text, "add_special": False}),
                         {"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"})
            reply = conn.getresponse()
            data = json.loads(reply.read().decode("utf-8")) if reply.status == 200 else None
            conn.close()
            n = len(data["tokens"]) if isinstance(data, dict) and isinstance(data.get("tokens"), list) else None
        except (OSError, ValueError, http.client.HTTPException):
            n = None
        if n is None:
            self.fallbacks += 1
            return self._approx.count(text)
        self._cache[text] = n
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return n
