"""Run the sidecar: ``python -m range_service.link --agent robot_legged=greeter``, or with agent
runtimes for a whole scenario cast: ``--scenario SB04_POLITE_BID --model fake``.

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
    parser.add_argument("--scenario", default=None, help="run an agent runtime for every cast member of this scenario")
    parser.add_argument("--model", default="none",
                        help="none, fake, fake-slow:MS, fake-malformed, replay:PATH, llama, llama:MODEL or llama-attach:PORT")
    parser.add_argument("--body", action="append", default=[], metavar="AVATAR=BODY", help="play AVATAR with another body")
    parser.add_argument("--jitter-ms", type=int, default=0, help="test: random extra delay before each answer")
    return parser.parse_args(argv)


async def runtimes_for(args: argparse.Namespace) -> tuple[dict, object]:
    """The scenario's agent runtimes and their (started) gateway, or ({}, None)."""
    if args.scenario is None:
        return {}, None
    from range_service.agents.factory import build_runtimes
    from range_service.agents.gateway import gateway_from_spec, tokenizer_for
    from range_service.configs import load_and_check

    config_set, problems = load_and_check()
    if problems:
        raise SystemExit("configs have problems; run tools/validate_configs.py")
    if args.scenario not in config_set.items["scenarios"]:
        raise SystemExit(f"unknown scenario {args.scenario!r}")
    overrides = dict(spec.split("=", 1) for spec in args.body)
    gateway = gateway_from_spec(args.model)
    if gateway is not None:
        await gateway.start()
    return build_runtimes(config_set.items["scenarios"][args.scenario], config_set, gateway=gateway,
                          body_overrides=overrides, tokenizer=tokenizer_for(gateway)), gateway


async def run(args: argparse.Namespace, token: str) -> None:
    agents = {}
    for spec in args.agent:
        agent_id, _, script = spec.partition("=")
        if script not in SCRIPTS:
            raise SystemExit(f"unknown script {script!r} for {agent_id}; choose from {', '.join(SCRIPTS)}")
        agents[agent_id] = script
    runtimes, gateway = await runtimes_for(args)
    sidecar = Sidecar(token, agents, args.record, args.delay_ms, args.drop_after, runtimes=runtimes,
                      jitter_ms=args.jitter_ms)
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
        if gateway is not None:
            await gateway.stop()   # stops a llama-server this process started, and only that


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
