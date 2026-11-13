"""Check every content file in configs/ against its contract and cross-references.

Usage (from the repository folder):

    uv run python tools/validate_configs.py              # check configs/
    uv run python tools/validate_configs.py path/to/dir  # check another folder laid out like configs/

Exit code 0 means every file is valid; 1 means at least one problem was found.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.configs import CONFIGS_DIR, KINDS, load_and_check  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    config_dir = Path(args[0]) if args else CONFIGS_DIR
    if not config_dir.is_dir():
        print(f"error: {config_dir} is not a folder")
        return 1

    config_set, found = load_and_check(config_dir)
    total = sum(len(v) for v in config_set.items.values())
    for kind in KINDS:
        for config_id in sorted(config_set.items[kind]):
            print(f"  loaded  {config_set.files[(kind, config_id)]}")

    if found:
        print(f"\n{len(found)} problem(s) found:")
        for problem in found:
            print(f"  FAIL  {problem}")
        return 1
    print(f"\nAll {total} config file(s) are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
