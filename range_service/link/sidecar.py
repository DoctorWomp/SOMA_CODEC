"""The Python end of the Godot ↔ Python link (D-05, D-43).

A WebSocket server bound to 127.0.0.1 only. Godot connects with the session token in the
``X-Range-Session-Token`` handshake header. A missing or wrong token is refused before any
message flows: the connection is closed at once with close code 4401 (a second client while
one is connected: 4409). Close codes are used rather than an HTTP 401 because Godot reports a
failed HTTP handshake as an engine error. The token never appears in an envelope or a log
(D-29). One client at a time. Every message is a versioned envelope checked against contracts/;
invalid or unknown messages are recorded and ignored, never acted on. Messages larger than
MAX_MESSAGE_BYTES close the connection.

Godot sends ``link.hello`` (which agents this session controls), ``world.observation`` packets
(one per agent per sample) and ``world.action_result``; the sidecar answers ``link.hello`` with the
agents it runs, then ``agent.action_request`` messages, and heartbeats.

Agents are either the G2b scripted agents (``agents.py``) or G3a agent runtimes
(``range_service/agents``). Run modes (D-48):

- **LIVE** (default): a runtime's decision runs as a background task, so a slow model never holds
  up the link, the heartbeat or other agents (T25). One pending decision per agent.
- **STEPPED**: after a sample's packets Godot sends ``link.step`` ``SAMPLE_SENT`` and holds the
  world. The sidecar answers every agent for that sample, sends their requests in agent-id
  order, then ``link.step`` ``AGENTS_DONE``. Same seed, same journal, however slow the agents.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import random
from pathlib import Path
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from range_service import contracts
from range_service.agents.runtime import AgentRuntime, DecisionJob
from range_service.link.agents import SCRIPTS, ScriptedAgent

HOST = "127.0.0.1"
TOKEN_HEADER = "X-Range-Session-Token"
MAX_MESSAGE_BYTES = 64 * 1024
CLOSE_UNAUTHORIZED = 4401
CLOSE_BUSY = 4409


class Sidecar:
    def __init__(self, token: str, agents: dict[str, str], record_dir: Path | None = None,
                 delay_ms: int = 0, drop_after: int = 0, runtimes: dict[str, AgentRuntime] | None = None,
                 jitter_ms: int = 0) -> None:
        if len(token) < 16:
            raise ValueError("the session token must be at least 16 characters")
        self._token = token
        self.agent_scripts = agents          # agent id -> script name
        self.agents: dict[str, ScriptedAgent | AgentRuntime] = {}
        self.runtimes = runtimes or {}       # agent id -> AgentRuntime (G3a)
        self.jitter_ms = jitter_ms           # test: random extra delay before answering (determinism checks)
        self.run_mode = "LIVE"
        self._step_jobs: list[tuple[AgentRuntime, DecisionJob]] = []
        self._step_presence: dict[str, list[dict[str, Any]]] = {}     # stepped: presence actions per agent
        self._live_tasks: dict[str, asyncio.Task] = {}                 # live: each agent's decision task
        self._tasks: set[asyncio.Task] = set()
        self.loop_lags: list[float] = []
        self._records_written = 0
        self.record_dir = record_dir
        self.delay_ms = delay_ms
        self.drop_after = drop_after         # close the connection once after this many observations
        self.connections = 0
        self.refused = 0
        self.problems: list[str] = []
        self.received: list[dict[str, Any]] = []
        self._observations = 0
        self._dropped_once = False
        self._client: ServerConnection | None = None
        self._server = None
        self._seq = 0
        self._last_tick = 0
        self.port = 0

    async def start(self, port: int = 0) -> int:
        self._server = await serve(self._handler, HOST, port, max_size=MAX_MESSAGE_BYTES, ping_interval=None)
        self.port = self._server.sockets[0].getsockname()[1]
        lag = asyncio.create_task(self._watch_loop_lag())
        self._tasks.add(lag)
        lag.add_done_callback(self._tasks.discard)
        return self.port

    async def _watch_loop_lag(self, every_s: float = 0.05) -> None:
        """How late the event loop wakes up (G3c-2, D-60): a busy loop delays every model answer,
        heartbeat and link message, so live runs report it (``summary.json`` event_loop_lag_ms)."""
        loop = asyncio.get_running_loop()
        while True:
            planned = loop.time() + every_s
            await asyncio.sleep(every_s)
            lag = max(0.0, (loop.time() - planned) * 1000)
            self.loop_lags.append(lag)
            if len(self.loop_lags) > 20000:
                del self.loop_lags[:10000]

    def loop_lag_summary(self) -> dict[str, float | None]:
        lags = sorted(self.loop_lags)
        if not lags:
            return {"p50": None, "p95": None, "max": None}
        return {"p50": round(lags[len(lags) // 2], 1), "p95": round(lags[int(0.95 * (len(lags) - 1))], 1),
                "max": round(lags[-1], 1)}

    async def stop(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.write_memory()
        self.write_records()

    def bound_hosts(self) -> list[str]:
        return [s.getsockname()[0] for s in self._server.sockets] if self._server else []

    async def _handler(self, ws: ServerConnection) -> None:
        sent = ws.request.headers.get(TOKEN_HEADER, "") if ws.request is not None else ""
        if not hmac.compare_digest(sent.encode(), self._token.encode()):
            self.refused += 1
            await ws.close(code=CLOSE_UNAUTHORIZED, reason="session token required")
            return
        if self._client is not None:
            await ws.close(code=CLOSE_BUSY, reason="another client is connected")
            return
        self._client = ws
        self.connections += 1
        try:
            async for raw in ws:
                await self._on_message(ws, raw)
        except ConnectionClosed:
            pass
        finally:
            self._client = None

    def _record(self, name: str, obj: Any) -> None:
        if self.record_dir is None:
            return
        self.record_dir.mkdir(parents=True, exist_ok=True)
        with (self.record_dir / name).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, sort_keys=True) + "\n")

    def _problem(self, text: str) -> None:
        self.problems.append(text)
        self._record("sidecar_problems.jsonl", {"problem": text})

    def _envelope(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._seq += 1
        return {"schema_version": "1.0", "message_id": f"py_{self._seq:06d}", "type": kind,
                "tick_id": self._last_tick, "sim_time_ms": self._last_tick * 1000 // 60,
                "source": "range_service", "payload": payload}

    async def _send(self, ws: ServerConnection, kind: str, payload: dict[str, Any], check: bool = True) -> None:
        env = self._envelope(kind, payload)
        if check:
            found = contracts.problems("envelope", env)
            if found:
                self._problem(f"refused to send an invalid {kind}: {found[0]}")
                return
            self._record("sidecar_sent.jsonl", env)
        else:
            self._record("sidecar_probes_deliberately_invalid.jsonl", env)
        await ws.send(json.dumps(env))

    async def _on_message(self, ws: ServerConnection, raw: Any) -> None:
        try:
            env = json.loads(raw)
        except (TypeError, ValueError):
            self._problem("message is not JSON")
            return
        found = contracts.problems("envelope", env) if isinstance(env, dict) else ["not an object"]
        if found:
            self._problem(f"invalid envelope ignored: {found[0]}")
            return
        self.received.append(env)
        self._record("sidecar_received.jsonl", env)
        self._last_tick = env["tick_id"]
        kind, payload = env["type"], env["payload"]
        if kind == "link.hello":
            self.run_mode = payload.get("run_mode", "LIVE")
            for agent_id in payload["agents"]:
                if agent_id in self.agents:
                    continue
                if agent_id in self.runtimes:
                    self.agents[agent_id] = self.runtimes[agent_id]
                elif self.agent_scripts.get(agent_id) is not None:
                    self.agents[agent_id] = SCRIPTS[self.agent_scripts[agent_id]](agent_id)
            reply = dict(payload, agents=sorted(a for a in payload["agents"] if a in self.agents))
            await self._send(ws, "link.hello", reply)
        elif kind == "world.observation":
            agent = self.agents.get(payload["observer_id"])
            if agent is None:
                return
            if isinstance(agent, AgentRuntime):
                await self._runtime_observation(ws, agent, payload)
            else:
                await self._scripted_observation(ws, agent, payload)
            self._observations += 1
            if self.drop_after and not self._dropped_once and self._observations >= self.drop_after:
                self._dropped_once = True
                await ws.close(code=1001, reason="sidecar test: dropping the connection once")
        elif kind == "link.step":
            if payload["phase"] == "SAMPLE_SENT":
                await self._finish_step(ws, payload["sample_tick_id"])
        elif kind == "world.action_result":
            agent = self.agents.get(payload["agent_id"])
            if agent is not None:
                agent.on_result(payload)
            self._record("sidecar_results.jsonl", payload)
        elif kind == "link.heartbeat":
            await self._send(ws, "link.heartbeat", {})
        # Other valid types are not for the sidecar; they are ignored.

    async def _scripted_observation(self, ws: ServerConnection, agent: ScriptedAgent, payload: dict[str, Any]) -> None:
        remembered = len(agent.memory)
        requests = agent.on_observation(payload)
        if len(agent.memory) != remembered:
            self.write_memory()   # kept current, so a hard stop (Windows) loses nothing
        if requests and self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)   # test: a slow agent answers late
        for request in requests:
            deliberate = request["action_request_id"] in getattr(agent, "raw_ids", set()) \
                or request["agent_id"] != agent.agent_id
            await self._send(ws, "agent.action_request", request, check=not deliberate)

    async def _runtime_observation(self, ws: ServerConnection, runtime: AgentRuntime, payload: dict[str, Any]) -> None:
        job = runtime.observe(payload)
        presence = runtime.take_presence()
        if presence:
            # Loop 2 (G3c-2): glances and survey moves need no model. Stepped: sent with the sample's
            # answers, in agent-id order; live: at once.
            if self.run_mode == "STEPPED":
                self._step_presence.setdefault(runtime.agent_id, []).extend(presence)
            else:
                await self._send_requests(ws, presence)
        if runtime.preempt_requested:
            runtime.preempt_requested = False
            task = self._live_tasks.get(runtime.agent_id)
            if task is not None and not task.done():
                task.cancel()                     # a pulse review gives way to a real event (D-61)
                runtime.pulse_log.append({"event": "PREEMPTED", "at_ms": runtime.ws.now_ms})
        for tier, key, prefix in runtime.take_prewarms():
            # T6: a promotion looks likely. Warm the persona prefix in the background; it never
            # holds up an answer, and in stepped runs it cannot change what the world sees.
            if runtime.gateway is not None:
                task = asyncio.create_task(runtime.gateway.prewarm(runtime.agent_id, tier, key, prefix))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        if job is None:
            return
        if self.run_mode == "STEPPED":
            self._step_jobs.append((runtime, job))
            return
        if job.proposals is not None and not self.delay_ms and not self.jitter_ms:
            await self._send_requests(ws, runtime.decide_now(job))
            return
        task = asyncio.create_task(self._answer_live(ws, runtime, job))
        self._tasks.add(task)
        self._live_tasks[runtime.agent_id] = task
        task.add_done_callback(self._tasks.discard)

    async def _answer_live(self, ws: ServerConnection, runtime: AgentRuntime, job: DecisionJob) -> None:
        try:
            requests = await runtime.decide(job)
        except asyncio.CancelledError:
            if runtime.pending_kind is None and self._server is not None:
                return                            # pre-empted pulse review: nothing to send
            raise
        await self._pause()
        try:
            await self._send_requests(ws, requests)
        except ConnectionClosed:
            pass

    async def _finish_step(self, ws: ServerConnection, sample_tick: int) -> None:
        jobs, self._step_jobs = sorted(self._step_jobs, key=lambda j: j[0].agent_id), []
        presence, self._step_presence = self._step_presence, {}
        answers = await asyncio.gather(*(runtime.decide(job) for runtime, job in jobs))
        await self._pause()
        for agent_id in sorted(presence):
            await self._send_requests(ws, presence[agent_id])
        for requests in answers:
            await self._send_requests(ws, requests)
        await self._send(ws, "link.step", {"sample_tick_id": sample_tick, "phase": "AGENTS_DONE"})

    async def _pause(self) -> None:
        delay = self.delay_ms + (random.randint(0, self.jitter_ms) if self.jitter_ms else 0)
        if delay:
            await asyncio.sleep(delay / 1000)

    async def _send_requests(self, ws: ServerConnection, requests: list[dict[str, Any]]) -> None:
        for request in requests:
            await self._send(ws, "agent.action_request", request)
        self.write_records()

    def write_records(self) -> None:
        """Append new decision records (one JSON line each) for every runtime, in agent-id order."""
        if self.record_dir is None:
            return
        new, prompts = [], []
        for agent_id in sorted(self.runtimes):
            runtime = self.runtimes[agent_id]
            done = getattr(runtime, "_records_flushed", 0)
            new += runtime.records[done:]
            runtime._records_flushed = len(runtime.records)
            done = getattr(runtime, "_prompts_flushed", 0)
            prompts += [dict(p, agent_id=agent_id) for p in runtime.prompts[done:]]
            runtime._prompts_flushed = len(runtime.prompts)
        if new or prompts:
            self.record_dir.mkdir(parents=True, exist_ok=True)
        if new:
            with (self.record_dir / "decision_records.jsonl").open("a", encoding="utf-8") as fh:
                for record in new:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
        if prompts:
            # Evaluator view of what each agent was shown (CONTEXT_MEMORY_STRATEGY §9); never sent anywhere.
            with (self.record_dir / "prompts.jsonl").open("a", encoding="utf-8") as fh:
                for entry in prompts:
                    fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")

    def write_memory(self) -> None:
        if self.record_dir is None:
            return
        self.record_dir.mkdir(parents=True, exist_ok=True)
        memory = {agent_id: (agent.memory.items if isinstance(agent, AgentRuntime) else agent.memory)
                  for agent_id, agent in self.agents.items()}
        (self.record_dir / "agent_memory.json").write_text(json.dumps(memory, indent=2, sort_keys=True), encoding="utf-8")
