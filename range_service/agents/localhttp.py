"""A minimal async HTTP/1.1 client for servers on this machine (127.0.0.1 only).

Used to talk to llama-server (G3b). Standard library only, so it adds no dependency, and fully
cancellable: when a deadline passes, the task is cancelled and the connection closed (T25).
It refuses any host other than the loopback address: model traffic never leaves the PC.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

LOOPBACK = "127.0.0.1"
MAX_BODY = 32 * 1024 * 1024


class HttpError(Exception):
    """The connection failed, closed early, or the reply was not valid HTTP."""


@dataclass
class HttpReply:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HttpError(f"the reply is not valid JSON ({exc})") from exc


async def request(port: int, method: str, path: str, payload: Any = None, api_key: str | None = None,
                  host: str = LOOPBACK) -> HttpReply:
    """One request on a fresh connection (``Connection: close``)."""
    if host != LOOPBACK:
        raise HttpError("model servers are reached on 127.0.0.1 only")
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    head = [f"{method} {path} HTTP/1.1", f"Host: {host}:{port}", "Connection: close", "Accept: application/json"]
    if payload is not None:
        head += ["Content-Type: application/json", f"Content-Length: {len(body)}"]
    if api_key:
        head.append(f"Authorization: Bearer {api_key}")
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except OSError as exc:
        raise HttpError(f"cannot connect to {host}:{port} ({exc.strerror or exc})") from exc
    try:
        writer.write(("\r\n".join(head) + "\r\n\r\n").encode("ascii") + body)
        await writer.drain()
        return await _read_reply(reader)
    except (ConnectionError, asyncio.IncompleteReadError) as exc:
        raise HttpError(f"the server closed the connection early ({exc.__class__.__name__})") from exc
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def _read_reply(reader: asyncio.StreamReader) -> HttpReply:
    status_line = await reader.readline()
    if not status_line:
        raise HttpError("the server closed the connection without answering")
    parts = status_line.decode("latin-1").split(" ", 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/") or not parts[1].isdigit():
        raise HttpError(f"not an HTTP reply: {status_line[:60]!r}")
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n"):
            break
        if not line:
            raise HttpError("the server closed the connection inside the reply headers")
        key, _, value = line.decode("latin-1").partition(":")
        headers[key.strip().lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        chunks = bytearray()
        while True:
            size_line = await reader.readline()
            size = int(size_line.split(b";")[0].strip() or b"0", 16)
            if size == 0:
                await reader.readline()
                break
            chunks += await reader.readexactly(size)
            await reader.readexactly(2)
            if len(chunks) > MAX_BODY:
                raise HttpError("the reply is too large")
        body = bytes(chunks)
    elif "content-length" in headers:
        length = int(headers["content-length"])
        if length > MAX_BODY:
            raise HttpError("the reply is too large")
        body = await reader.readexactly(length)
    else:
        body = await reader.read(MAX_BODY)
    return HttpReply(int(parts[1]), headers, body)
