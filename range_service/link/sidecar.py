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
(one per agent per sample) and ``world.action_result``; the sidecar answers with
``agent.action_request`` from its scripted agents, and heartbeats.
"""

from __future__ import annotations

import asyncio
import hmac
import json
from pathlib import Path
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from range_service import contracts
from range_service.link.agents import SCRIPTS, ScriptedAgent

HOST = "127.0.0.1"
TOKEN_HEADER = "X-Range-Session-Token"
MAX_MESSAGE_BYTES = 64 * 1024
CLOSE_UNAUTHORIZED = 4401
CLOSE_BUSY = 4409


class Sidecar:
    def __init__(self, token: str, agents: dict[str, str], record_dir: Path | None = None,
                 delay_ms: int = 0, drop_after: int = 0) -> None:
        if len(token) < 16:
            raise ValueError("the session token must be at least 16 characters")
        self._token = token
        self.agent_scripts = agents          # agent id -> script name
        self.agents: dict[str, ScriptedAgent] = {}
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
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.write_memory()

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
            for agent_id in payload["agents"]:
                script = self.agent_scripts.get(agent_id)
                if script is not None and agent_id not in self.agents:
                    self.agents[agent_id] = SCRIPTS[script](agent_id)
        elif kind == "world.observation":
            agent = self.agents.get(payload["observer_id"])
            if agent is None:
                return
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
            self._observations += 1
            if self.drop_after and not self._dropped_once and self._observations >= self.drop_after:
                self._dropped_once = True
                await ws.close(code=1001, reason="sidecar test: dropping the connection once")
        elif kind == "world.action_result":
            agent = self.agents.get(payload["agent_id"])
            if agent is not None:
                agent.on_result(payload)
            self._record("sidecar_results.jsonl", payload)
        elif kind == "link.heartbeat":
            await self._send(ws, "link.heartbeat", {})
        # Other valid types are not for the sidecar; they are ignored.

    def write_memory(self) -> None:
        if self.record_dir is None:
            return
        self.record_dir.mkdir(parents=True, exist_ok=True)
        memory = {agent_id: agent.memory for agent_id, agent in self.agents.items()}
        (self.record_dir / "agent_memory.json").write_text(json.dumps(memory, indent=2, sort_keys=True), encoding="utf-8")
