"""Run the sidecar: ``python -m range_service.link --agent robot_legged=greeter``.

The session token comes from the RANGE_SESSION_TOKEN environment variable (never the command
line, where other programs could read it). Prints ``LISTENING 127.0.0.1:<port>`` once ready.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

from range_service.link.agents import SCRIPTS
from range_service.link.sidecar import Sidecar

TOKEN_ENV = "RANGE_SESSION_TOKEN"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m range_service.link", description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="TCP port on 127.0.0.1 (0 picks a free one)")
    parser.add_argument("--agent", action="append", default=[], metavar="ID=SCRIPT",
                        help=f"control this agent with a script ({', '.join(SCRIPTS)}); repeatable")
    parser.add_argument("--record", type=Path, default=None, help="folder to record messages and memories in")
    parser.add_argument("--delay-ms", type=int, default=0, help="test: send agents' action requests this late")
    parser.add_argument("--drop-after", type=int, default=0, help="test: close the connection once after N observations")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, token: str) -> None:
    agents = {}
    for spec in args.agent:
        agent_id, _, script = spec.partition("=")
        if script not in SCRIPTS:
            raise SystemExit(f"unknown script {script!r} for {agent_id}; choose from {', '.join(SCRIPTS)}")
        agents[agent_id] = script
    sidecar = Sidecar(token, agents, args.record, args.delay_ms, args.drop_after)
    port = await sidecar.start(args.port)
    print(f"LISTENING 127.0.0.1:{port}", flush=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):   # Windows: Ctrl+C raises KeyboardInterrupt instead
            pass
    try:
        await stop.wait()
    finally:
        await sidecar.stop()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get(TOKEN_ENV, "")
    if len(token) < 16:
        print(f"error: set {TOKEN_ENV} to the session token (at least 16 characters)", file=sys.stderr)
        return 2
    try:
        asyncio.run(run(args, token))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
