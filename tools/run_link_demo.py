"""Open the Godot demo connected to the Python sidecar (G2b; D-05, D-43).

    uv run python tools/run_link_demo.py

Starts the sidecar on 127.0.0.1 with a fresh random session token (passed to both programs
through the RANGE_SESSION_TOKEN environment variable, never shown), then opens the Godot demo
(GODOT_BIN, as for the checks) connected to it. Robot_legged and robot_quadruped are driven by
scripted Python agents that wave back and say hello when someone waves at them; the world
refuses what a body cannot do (the quadruped has no arm to wave with). Close the Godot window
to finish; a short summary of what crossed the link is printed.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.godot_check import find_godot  # noqa: E402

AGENTS = ("robot_legged", "robot_quadruped")


def main() -> int:
    godot = find_godot()
    if godot is None:
        print("Godot not found: set GODOT_BIN (see docs/BUILD_AND_RUN.md).")
        return 1
    record = Path(tempfile.mkdtemp(prefix="range_link_demo_"))
    env = dict(os.environ, RANGE_SESSION_TOKEN=secrets.token_hex(24))
    cmd = [sys.executable, "-m", "range_service.link", "--record", str(record)]
    for agent in AGENTS:
        cmd += ["--agent", f"{agent}=greeter"]
    sidecar = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE, text=True)
    try:
        line = sidecar.stdout.readline().strip()
        if not line.startswith("LISTENING "):
            print(f"The sidecar did not start: {line!r}")
            return 1
        port = line.rsplit(":", 1)[1]
        print(f"Sidecar listening on 127.0.0.1:{port}. Opening Godot; close its window to finish.")
        subprocess.run([godot, "--path", str(REPO / "godot_app"), "--",
                        f"--link-port={port}", f"--link-agents={','.join(AGENTS)}"], cwd=REPO, env=env)
    finally:
        sidecar.terminate()
        sidecar.wait(timeout=10)
    received = record / "sidecar_received.jsonl"
    results = record / "sidecar_results.jsonl"
    count = len(received.read_text(encoding="utf-8").splitlines()) if received.is_file() else 0
    print(f"Python received {count} messages from Godot.")
    if results.is_file():
        for line in results.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            print(f"  {r['agent_id']}: {r['action_request_id']} -> {r['reason_code']}")
    print(f"Everything that crossed the link is recorded in {record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
