"""A stand-in for llama-server, for tests (G3b). No model: it answers by rule.

    uv run python -m range_service.agents.standin [--mode normal|slow|malformed|disconnect]
                                                  [--delay-ms N] [--answers FILE]

Speaks the part of llama-server's API that RANGE uses, on 127.0.0.1 only: ``GET /health``,
``POST /v1/chat/completions`` (with ``timings`` and ``usage`` as llama-server reports them),
``POST /tokenize`` (one token per word) and ``GET /props``. Every endpoint except ``/health``
needs the API key from the environment variable ``RANGE_STANDIN_API_KEY`` (as
``Authorization: Bearer ...``); a wrong key gets 401, as llama-server answers.

G3c-1: ``--slot-save`` answers ``POST /slots/{id}?action=save|restore`` as a server started with
``--slot-save-path`` does (without it: 501, as llama-server); ``--prefix-cache`` reports
``cache_n`` as the words a slot's previous prompt shares with the new one (a slot remembers its
last prompt; a restore puts the saved prompt back), so warm and cold calls can be told apart.

Modes: ``normal`` answers at once; ``slow`` waits ``--delay-ms`` first; ``malformed`` answers
text that is not JSON; ``disconnect`` closes the connection without answering. The answer is
the next line of ``--answers`` if given, else a WAIT (or NO_OP) chosen from the request's JSON
schema, so it is always one of the agent's allowed actions. Prints ``LISTENING 127.0.0.1:PORT``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

KEY_ENV = "RANGE_STANDIN_API_KEY"
HOST = "127.0.0.1"


@dataclass
class Behaviour:
    mode: str = "normal"
    delay_ms: int = 0
    answers: list[str] = field(default_factory=list)
    api_key: str = ""
    requests: list[dict[str, Any]] = field(default_factory=list)   # chat bodies received (tests read them)
    unauthorized: int = 0
    slot_save: bool = False                  # like llama-server --slot-save-path
    prefix_cache: bool = False               # report cache_n from each slot's previous prompt
    slot_words: dict[int, list[str]] = field(default_factory=dict)
    saved: dict[str, list[str]] = field(default_factory=dict)
    slot_actions: list[tuple[str, int, str]] = field(default_factory=list)
    _next: int = 0

    def answer_for(self, body: dict[str, Any]) -> str:
        if self.answers:
            text = self.answers[min(self._next, len(self.answers) - 1)]
            self._next += 1
            return text
        if self.mode == "malformed":
            return "Sure! I would wave at them now."
        choices = (((body.get("response_format") or {}).get("schema") or {}).get("properties", {})
                   .get("actions", {}).get("items", {}).get("anyOf", []))
        allowed = [c["properties"]["action"]["const"] for c in choices]
        if "WAIT" in allowed or not allowed:
            return json.dumps({"actions": [{"action": "WAIT", "args": {"duration_ms": 1000}}],
                               "reason_summary": "stand-in server"})
        return json.dumps({"actions": [{"action": "NO_OP", "args": {}}], "reason_summary": "stand-in server"})


def _reply(status: int, payload: Any) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    reason = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found"}.get(status, "OK")
    head = (f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n")
    return head.encode("ascii") + body


async def _handle(b: Behaviour, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = (await reader.readline()).decode("latin-1").split()
        headers: dict[str, str] = {}
        while (line := await reader.readline()) not in (b"\r\n", b"\n", b""):
            k, _, v = line.decode("latin-1").partition(":")
            headers[k.strip().lower()] = v.strip()
        raw = await reader.readexactly(int(headers.get("content-length", "0") or 0))
        if len(request_line) < 2:
            return
        method, path = request_line[0], request_line[1]
        if path == "/health":
            writer.write(_reply(200, {"status": "ok"}))
            return
        if headers.get("authorization", "") != f"Bearer {b.api_key}":
            b.unauthorized += 1
            writer.write(_reply(401, {"error": {"code": 401, "message": "Invalid API Key", "type": "authentication_error"}}))
            return
        body = json.loads(raw.decode("utf-8")) if raw else {}
        if method == "POST" and path.startswith("/slots/"):
            slot_part, _, query = path[len("/slots/"):].partition("?")
            action = dict(q.split("=", 1) for q in query.split("&") if "=" in q).get("action", "")
            if not b.slot_save:
                writer.write(_reply(501, {"error": {"code": 501, "type": "not_supported_error", "message":
                                                    "This server does not support slots action. Start it with `--slot-save-path`"}}))
                return
            slot, filename = int(slot_part), str(body.get("filename", ""))
            b.slot_actions.append((action, slot, filename))
            if action == "save":
                b.saved[filename] = list(b.slot_words.get(slot, []))
                writer.write(_reply(200, {"id_slot": slot, "filename": filename, "n_saved": len(b.saved[filename]),
                                          "n_written": 4 * len(b.saved[filename]), "timings": {"save_ms": 1.0}}))
            elif action == "restore" and filename in b.saved:
                b.slot_words[slot] = list(b.saved[filename])
                writer.write(_reply(200, {"id_slot": slot, "filename": filename, "n_restored": len(b.saved[filename]),
                                          "n_read": 4 * len(b.saved[filename]), "timings": {"restore_ms": 0.5}}))
            else:
                writer.write(_reply(400, {"error": {"code": 400, "message": "Unable to restore slot, no available space in KV cache or invalid slot save file"}}))
            return
        if method == "GET" and path == "/props":
            writer.write(_reply(200, {"model_path": "standin.gguf", "build_info": "standin"}))
        elif method == "POST" and path == "/tokenize":
            words = str(body.get("content", "")).split()
            writer.write(_reply(200, {"tokens": list(range(len(words)))}))
        elif method == "POST" and path == "/v1/chat/completions":
            b.requests.append(body)
            if b.mode == "disconnect":
                return                                    # close without a word
            if b.mode == "slow" and b.delay_ms:
                await asyncio.sleep(b.delay_ms / 1000)
            text = b.answer_for(body)
            prompt = " ".join(m.get("content", "") for m in body.get("messages", []))
            words = prompt.split()
            n_prompt = len(words)
            n_gen = len(text.split())
            cache_n = n_prompt // 2
            slot = body.get("id_slot", -1)
            if b.prefix_cache:
                held = b.slot_words.get(slot, []) if isinstance(slot, int) and slot >= 0 else []
                cache_n = 0
                while cache_n < min(len(held), n_prompt) and held[cache_n] == words[cache_n]:
                    cache_n += 1
                if isinstance(slot, int) and slot >= 0:
                    b.slot_words[slot] = words
            writer.write(_reply(200, {
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": n_prompt, "completion_tokens": n_gen, "total_tokens": n_prompt + n_gen},
                "timings": {"cache_n": cache_n, "prompt_n": n_prompt - cache_n, "prompt_ms": 12.5,
                            "predicted_n": n_gen, "predicted_ms": 40.0 + b.delay_ms},
                "id_slot": body.get("id_slot", -1),
            }))
        else:
            writer.write(_reply(404, {"error": {"code": 404, "message": "not found"}}))
    except (asyncio.IncompleteReadError, ConnectionError, ValueError):
        pass
    finally:
        try:
            await writer.drain()
        except ConnectionError:
            pass
        writer.close()


async def serve(b: Behaviour, port: int = 0) -> asyncio.Server:
    return await asyncio.start_server(lambda r, w: _handle(b, r, w), HOST, port)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m range_service.agents.standin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", default="normal", choices=["normal", "slow", "malformed", "disconnect"])
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--answers", default=None, help="a file with one answer per line, served in order")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--slot-save", action="store_true", help="answer slot save/restore (like --slot-save-path)")
    parser.add_argument("--prefix-cache", action="store_true", help="report cache_n from each slot's last prompt")
    args = parser.parse_args(argv)
    key = os.environ.get(KEY_ENV, "")
    if len(key) < 16:
        print(f"error: set {KEY_ENV} (at least 16 characters)", file=sys.stderr)
        return 2
    answers = []
    if args.answers:
        with open(args.answers, encoding="utf-8") as fh:
            answers = [line.rstrip("\n") for line in fh if line.strip()]
    b = Behaviour(args.mode, args.delay_ms, answers, key, slot_save=args.slot_save, prefix_cache=args.prefix_cache)

    async def run() -> None:
        server = await serve(b, args.port)
        print(f"LISTENING {HOST}:{server.sockets[0].getsockname()[1]}", flush=True)
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
