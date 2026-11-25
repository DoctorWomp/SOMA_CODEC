"""Finding a run folder from the command line (owner's checklists, 2026-11-25).

``latest`` means the newest run folder under ``runs/`` (the one with the newest run_manifest.json),
so the owner's checklists can say ``view_run.py latest`` instead of a placeholder to fill in.
Anything else is a path, made absolute.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "runs"


class RunPathError(ValueError):
    pass


def resolve_run(arg: str | Path, runs_root: Path | None = None) -> Path:
    """The run folder ``arg`` names: ``latest`` or a path."""
    if str(arg).strip().lower() == "latest":
        root = runs_root or RUNS
        manifests = sorted(root.glob("*/run_manifest.json"), key=lambda p: p.stat().st_mtime) if root.is_dir() else []
        if not manifests:
            raise RunPathError(f"no run folder with a run_manifest.json under {root}")
        return manifests[-1].parent.resolve()
    path = Path(arg).resolve()
    if not path.is_dir():
        raise RunPathError(f"{path} is not a folder: give a run folder (as printed after 'Run folder:') or 'latest'")
    return path
