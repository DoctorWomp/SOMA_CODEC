"""Copy the map and body configs into the Godot project as JSON (D-30).

Godot cannot read YAML, so the configs it needs are exported to
``godot_app/data/<folder>/<id>.json`` after they pass every check in
``tools/validate_configs.py``. The JSON files are committed, so the Godot
project opens without running Python first.

Usage (from the repository folder):

    uv run python tools/export_godot_data.py          # write the JSON files
    uv run python tools/export_godot_data.py --check  # only report stale files (used by tools/check.py)

Run it after editing a map or body YAML file, then commit both.
Exit code 0 means the JSON files are (now) up to date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from range_service.configs import CONFIGS_DIR, load_and_check  # noqa: E402

GODOT_DATA_DIR = REPO / "godot_app" / "data"

# Config folders Godot reads at G1. Others (personas, scenarios, presets) are
# Python-side until the transport arrives (G2-G3).
EXPORTED_KINDS = ("maps", "bodies")


def render(kind: str, source_rel: str, data: dict[str, Any]) -> str:
    """The exact text of one exported file. Deterministic: same input, same bytes."""
    wrapper = {
        "_generated": "Do not edit. Made by tools/export_godot_data.py from the source file below.",
        "source": source_rel,
        "kind": kind,
        "data": data,
    }
    return json.dumps(wrapper, indent=2, ensure_ascii=False) + "\n"


def expected_files(config_dir: Path = CONFIGS_DIR) -> tuple[dict[Path, str], list[str]]:
    """Map of output path -> text, plus any config problems that block the export."""
    config_set, found = load_and_check(config_dir)
    if found:
        return {}, [str(p) for p in found]
    out: dict[Path, str] = {}
    for kind in EXPORTED_KINDS:
        for config_id, data in sorted(config_set.items[kind].items()):
            source_rel = config_set.files[(kind, config_id)]
            out[GODOT_DATA_DIR / kind / f"{config_id}.json"] = render(kind, source_rel, data)
    return out, []


def stale_files(expected: dict[Path, str], data_dir: Path = GODOT_DATA_DIR) -> list[str]:
    """Human-readable list of files that are missing, different or no longer produced."""
    stale: list[str] = []
    for path, text in sorted(expected.items()):
        rel = path.relative_to(REPO).as_posix()
        if not path.is_file():
            stale.append(f"{rel} is missing")
        elif path.read_text(encoding="utf-8") != text:
            stale.append(f"{rel} is out of date")
    for kind in EXPORTED_KINDS:
        folder = data_dir / kind
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                if path not in expected:
                    stale.append(f"{path.relative_to(REPO).as_posix()} has no source config any more")
    return stale


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check_only = "--check" in args

    expected, blocking = expected_files()
    if blocking:
        print("Cannot export: fix these config problems first.")
        for problem in blocking:
            print(f"  FAIL  {problem}")
        return 1

    stale = stale_files(expected)
    if check_only:
        if stale:
            for item in stale:
                print(f"  FAIL  {item}")
            print("  Run: uv run python tools/export_godot_data.py   (then commit the changed files)")
            return 1
        print(f"  {len(expected)} exported file(s) in godot_app/data/ match configs/")
        return 0

    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    for kind in EXPORTED_KINDS:
        folder = GODOT_DATA_DIR / kind
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            if path not in expected:
                path.unlink()
                print(f"  removed  {path.relative_to(REPO).as_posix()}")
    for path in sorted(expected):
        print(f"  wrote  {path.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
