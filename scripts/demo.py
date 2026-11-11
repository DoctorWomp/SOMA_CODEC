"""Run matched offline A/B fixtures, emit synthetic trace (stdout only)."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sidecar"))
from soma_range.contracts import Observation
from soma_range.runtime import decide, replay

scenario = json.loads((ROOT / "configs/expo_demo.json").read_text())
for arm in ("A", "B"):
    decisions = [decide(Observation.parse(item), arm).wire() for item in scenario["observations"]]
    print(json.dumps({"scenario": scenario["scenario_id"], "seed": scenario["seed"],
                      "arm": arm, "adapter": "offline-stub", "decisions": decisions,
                      "replay_sha256": replay(decisions)}, sort_keys=True))
