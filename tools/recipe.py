"""Save a run's Director interventions as a recipe, to schedule them identically in later runs (G4b, D-102).

    uv run python tools/recipe.py save runs/<run> --id my_recipe          # writes configs/recipes/my_recipe.yaml
    uv run python tools/recipe.py save runs/<run> --id my_recipe --out FILE
    uv run python tools/run_scenario.py <SCENARIO> --recipe my_recipe     # replay them, pre-scheduled
    uv run python tools/recipe.py show my_recipe                          # list a recipe's interventions

Only applied interventions are saved, in journal order, at the scenario tick they happened
(the run's tick_hz; the world tick counts from the run's start). A directive edit keeps its new text.
Props placed in the run are renamed for the recipe: a recipe numbers its interventions from 1, and
a prop is "prop_" + the id of the intervention that placed it, so a later move or removal of that
prop names it by its new id. Run tools/validate_configs.py after saving.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from range_service.configs import CONFIGS_DIR, load_and_check  # noqa: E402
from range_service.eval.runner import read_journal  # noqa: E402


def recipe_from_run(run_dir: Path, recipe_id: str, about: str | None = None) -> dict[str, Any]:
    journal = read_journal(run_dir / "journal.jsonl")
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    cs, _ = load_and_check()
    scenario = cs.items["scenarios"][manifest["scenario_id"]]
    per = 60 // int(scenario["tick_hz"])
    start = next(e["tick_id"] for e in journal if e["kind"] == "RUN_STARTED")
    items, renamed = [], {}
    for e in journal:
        if e["kind"] != "INTERVENTION" or e["payload"]["status"] != "APPLIED":
            continue
        req, rec = e["payload"]["request"], e["payload"]["intervention"]
        n = len(items) + 1
        args = dict(req["args"])
        target = req["target_id"]
        if req["operation"] == "PLACE_PROP":
            renamed[rec["target_id"]] = f"prop_dir_{n:04d}"
        elif req["operation"] in ("MOVE_PROP", "REMOVE_PROP"):
            target = renamed.get(target, target)
        elif req["operation"] == "EDIT_DIRECTIVE" and args.get("field") in ("directive", "goal"):
            args["value"] = rec["after"]
        items.append({"at_tick": max(0, round((req_tick(e) - start) / per)), "intervention_type": req["intervention_type"],
                      "operation": req["operation"], "target_id": target, "args": args})
    if not items:
        raise SystemExit(f"{run_dir}: no applied intervention to save")
    return {"schema_version": "1.0", "recipe_id": recipe_id,
            "about": about or f"Saved from {run_dir.name} ({len(items)} interventions).",
            "scenario": manifest["scenario_id"], "interventions": items}


def req_tick(entry: dict[str, Any]) -> int:
    rec = entry["payload"]["intervention"]
    return int(rec["tick_id"]) if rec else int(entry["tick_id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/recipe.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_save = sub.add_parser("save")
    p_save.add_argument("run", type=Path)
    p_save.add_argument("--id", required=True, help="recipe id: lowercase letters, digits, _")
    p_save.add_argument("--about", default=None)
    p_save.add_argument("--out", type=Path, default=None)
    p_show = sub.add_parser("show")
    p_show.add_argument("id")
    args = parser.parse_args(argv)
    if args.cmd == "show":
        data = yaml.safe_load((CONFIGS_DIR / "recipes" / f"{args.id}.yaml").read_text(encoding="utf-8"))
        for it in data["interventions"]:
            print(f"  tick {it['at_tick']:>5}  {it['intervention_type']:<24} {it['operation']:<16} {it['target_id'] or ''} {it['args']}")
        return 0
    recipe = recipe_from_run(args.run, args.id, args.about)
    out = args.out or (CONFIGS_DIR / "recipes" / f"{args.id}.yaml")
    header = (f"# Saved by tools/recipe.py from {args.run.name}: the run's applied Director interventions (G4b, D-102).\n"
              f"# Schedule with: uv run python tools/run_scenario.py {recipe['scenario']} --recipe {args.id}\n")
    out.write_text(header + yaml.safe_dump(recipe, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {out} ({len(recipe['interventions'])} interventions); check it: uv run python tools/validate_configs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
