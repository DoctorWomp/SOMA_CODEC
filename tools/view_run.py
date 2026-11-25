"""Open a finished run in the layer viewer (G4a, D-93): the 2D per-observer view of its logged data.

    uv run python tools/view_run.py runs/<run>                          # Spectator seat, Robot R
    uv run python tools/view_run.py runs/<run> --seat evaluator         # with EVALUATOR TRUTH (F4)
    uv run python tools/view_run.py runs/<run> --observer visitor_y     # another observer ([ ] cycles)
    uv run python tools/view_run.py runs/<run> --self-test              # headless: scrub every decision
    uv run python tools/view_run.py runs/<run> --screenshot shot.png --decision 3

The run's viewer feed (``viewer/observer_feed.jsonl`` and ``viewer/evaluator_truth.jsonl``) is
written at the end of every run since G4a; for an older run folder, or with ``--rebuild``, it is
rebuilt from the run's logs first (the same builder as a live run). In the viewer: , and . step 1 s
(Shift 10 s), N / P next / previous decision, click a pin or drag on the lanes to scrub, - and =
zoom, [ ] change observer, F3 hide or show, F4 the EVALUATOR TRUTH panel (Evaluator seat only).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.viewer import feed  # noqa: E402
from tools.godot_check import PROJECT_DIR, find_godot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/view_run.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", help="a run folder (as printed after 'Run folder:'), or 'latest' for the newest one")
    parser.add_argument("--seat", default="spectator", choices=["spectator", "director", "evaluator"])
    parser.add_argument("--observer", default="", help="the avatar to open on (default: the first observer)")
    parser.add_argument("--rebuild", action="store_true", help="rebuild the feed from the run's logs first")
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument("--renderer", default="gl_compatibility", help="Godot rendering method for the 2D viewer")
    parser.add_argument("--self-test", action="store_true", help="headless: scrub to every decision and check it")
    parser.add_argument("--screenshot", type=Path, default=None, help="save the window to a PNG and quit")
    parser.add_argument("--decision", type=int, default=-1, help="with --screenshot: select this decision first")
    args = parser.parse_args(argv)

    from range_service.eval.run_paths import RunPathError, resolve_run   # noqa: PLC0415
    try:
        run = resolve_run(args.run)
    except RunPathError as exc:
        print(f"FAIL  {exc}")
        return 2
    print(f"Run folder: {run}")
    viewer_dir = run / "viewer"
    if args.rebuild or not (viewer_dir / feed.OBSERVER_FILE).is_file():
        try:
            obs, ev = feed.build_run(run)
        except (OSError, KeyError, ValueError) as exc:
            print(f"FAIL  cannot build the viewer feed of {run}: {exc}")
            return 1
        print(f"built the viewer feed: {len(obs)} observer records, {len(ev)} evaluator records")
    godot = find_godot()
    if godot is None:
        print("Godot not found. Set GODOT_BIN, or run: uv run python tools/install_godot.py")
        return 2
    cmd = [godot, "--path", str(PROJECT_DIR), "--audio-driver", "Dummy"]
    if args.self_test:
        cmd.append("--headless")
    else:
        cmd += ["--resolution", args.resolution, "--rendering-method", args.renderer]
    cmd += ["res://scenes/main.tscn", "--", f"--replay={viewer_dir.as_posix()}", f"--seat={args.seat}",
            f"--operator-log={(run / 'operator_replay.jsonl').as_posix()}"]
    if args.observer:
        cmd.append(f"--observer={args.observer}")
    if args.self_test:
        cmd.append("--viewer-self-test")
    if args.screenshot is not None:
        cmd += [f"--screenshot={args.screenshot.resolve().as_posix()}", f"--decision={args.decision}"]
    proc = subprocess.run(cmd, capture_output=args.self_test, text=True)
    if args.self_test:
        lines = [x for x in proc.stdout.splitlines() if x.startswith(("VIEWER", "SCRIPT ERROR", "ERROR"))]
        print("\n".join(lines))
        print("OK" if proc.returncode == 0 else "FAIL")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
