"""Portable check entry point. Run from any working directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, godot: bool = False, marker: str = "") -> None:
    result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=120)
    print(result.stdout, end="")
    if result.returncode or (marker and marker not in result.stdout) or (
            godot and any(error in result.stdout for error in ("SCRIPT ERROR:", "ERROR:"))):
        raise SystemExit(result.returncode or 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-godot", action="store_true")
    args = parser.parse_args()
    os.environ["PYTHONPATH"] = str(ROOT / "sidecar")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    executable = os.environ.get("GODOT_BIN") or shutil.which("godot") or shutil.which("godot4")
    if not executable:
        print("SKIP: Godot missing. Set GODOT_BIN to Godot 4.5.1 console executable.")
        raise SystemExit(1 if args.require_godot else 0)
    run([executable, "--headless", "--path", "godot", "--import"], godot=True)
    sys.path.insert(0, str(ROOT / "sidecar"))
    from soma_range.server import Handler
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        os.environ["RANGE_TEST_PORT"] = str(server.server_port)
        try:
            run([executable, "--headless", "--path", "godot", "--script", "res://smoke.gd"],
                godot=True, marker="RANGE_GODOT_SMOKE_OK")
        finally:
            server.shutdown()
            worker.join(timeout=5)


if __name__ == "__main__":
    main()
