"""Run every check with one command.

    uv run python tools/check.py                  # everything; Godot is skipped (and says so) if not found
    uv run python tools/check.py --require-godot  # CI: a missing Godot is a failure, not a skip

Steps, in order:
  1. Contracts:   each schema is valid JSON Schema 2020-12; each example passes or fails as declared.
  2. Configs:     every file in configs/ matches its contract and its references exist.
  3. Godot data:  the JSON copies in godot_app/data/ match configs/ (D-30).
  4. Tests:       the full pytest suite.
  5. Godot:       import the Godot project and run its headless tests (tools/godot_check.py).

All steps run even if an earlier one fails, so you see every problem at once.
Exit code 0 means everything that ran passed. A skipped step is printed as SKIP, never PASS.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from jsonschema import Draft202012Validator  # noqa: E402
from jsonschema.exceptions import SchemaError  # noqa: E402

from range_service import contracts  # noqa: E402


def check_contracts() -> bool:
    ok = True
    names = contracts.schema_names()
    for name in names:
        try:
            schema = contracts.load_schema(name)
            Draft202012Validator.check_schema(schema)
            contracts.validator(name)
        except (SchemaError, json.JSONDecodeError, KeyError) as exc:
            print(f"  FAIL  contracts/{name}.schema.json: {exc}")
            ok = False
            continue
        if schema.get("x-audience") not in contracts.AUDIENCES:
            print(f"  FAIL  contracts/{name}.schema.json: missing or unknown x-audience")
            ok = False

    counts = {"valid": 0, "invalid": 0}
    for folder in sorted(p for p in contracts.EXAMPLES_DIR.iterdir() if p.is_dir()):
        name = folder.name
        if name not in names:
            print(f"  FAIL  examples/{name}: no contract named {name!r}")
            ok = False
            continue
        for path in sorted((folder / "valid").glob("*.json")):
            counts["valid"] += 1
            for problem in contracts.problems(name, json.loads(path.read_text(encoding="utf-8"))):
                print(f"  FAIL  {path.relative_to(REPO).as_posix()} should be valid: {problem}")
                ok = False
        expect_path = folder / "invalid" / "_expect.json"
        expect = json.loads(expect_path.read_text(encoding="utf-8")) if expect_path.is_file() else {}
        for path in sorted((folder / "invalid").glob("*.json")):
            if path.name.startswith("_"):
                continue
            counts["invalid"] += 1
            rel = path.relative_to(REPO).as_posix()
            keywords = contracts.failing_keywords(name, json.loads(path.read_text(encoding="utf-8")))
            if not keywords:
                print(f"  FAIL  {rel} should be rejected but passed")
                ok = False
            elif expect.get(path.stem) not in keywords:
                print(f"  FAIL  {rel} rejected, but not for its stated reason {expect.get(path.stem)!r}")
                ok = False
    print(f"  {len(names)} contracts, {counts['valid']} valid and {counts['invalid']} invalid examples checked")
    return ok


def check_configs() -> bool:
    from tools.validate_configs import main as validate_configs_main

    return validate_configs_main([]) == 0


def check_godot_data() -> bool:
    from tools.export_godot_data import main as export_main

    return export_main(["--check"]) == 0


def run_tests() -> bool:
    result = subprocess.run([sys.executable, "-m", "pytest"], cwd=REPO)
    return result.returncode == 0


PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    require_godot = "--require-godot" in args

    def run_godot() -> str:
        from tools.godot_check import EXIT_PASSED, EXIT_SKIPPED
        from tools.godot_check import main as godot_main

        code = godot_main(["--require"] if require_godot else [])
        return PASS if code == EXIT_PASSED else SKIP if code == EXIT_SKIPPED else FAIL

    steps = [
        ("Contracts", check_contracts),
        ("Configs", check_configs),
        ("Godot data", check_godot_data),
        ("Tests", run_tests),
        ("Godot", run_godot),
    ]
    results = []
    for title, step in steps:
        print(f"\n== {title} ==")
        start = time.monotonic()
        outcome = step()
        if isinstance(outcome, bool):
            outcome = PASS if outcome else FAIL
        results.append((title, outcome, time.monotonic() - start))

    print("\n== Summary ==")
    for title, outcome, seconds in results:
        print(f"  {outcome}  {title:<10} ({seconds:.1f}s)")
    failed = [t for t, o, _ in results if o == FAIL]
    skipped = [t for t, o, _ in results if o == SKIP]
    if failed:
        print("\nSome checks FAILED (see above).")
        return 1
    if skipped:
        print(f"\nAll checks that ran passed. SKIPPED: {', '.join(skipped)} (see above for how to enable).")
        return 0
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
