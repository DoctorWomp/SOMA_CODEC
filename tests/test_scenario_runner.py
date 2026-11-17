"""The scenario runner's Python side (G3a, D-48): options, the Godot command line and the run
manifest. The end-to-end runs (with Godot) are step 6 of tools/godot_check.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from range_service import contracts
from range_service.eval.runner import RunError, RunOptions, check_options, godot_command, manifest

from .agent_helpers import CONFIGS


def opts(**kw) -> RunOptions:
    return RunOptions(kw.pop("scenario_id", "SB04_POLITE_BID"), "godot", **kw)


def test_manifest_matches_its_contract_and_records_the_setup():
    o = opts(body_overrides={"robot_r": "quadruped"}, model="fake")
    scenario = check_options(o, CONFIGS)
    m = manifest(o, CONFIGS, scenario, 4204, "run_sb04_test", [], {})
    assert contracts.problems("run_manifest", m) == []
    robot = next(a for a in m["avatars"] if a["avatar_id"] == "robot_r")
    assert robot["body_id"] == "quadruped" and robot["model"]["model_id"] == "fake"
    assert m["simulation"] == {"tick_hz": 10, "mode": "STEPPED", "world_authority": "GODOT"}
    assert m["resolved_settings"]["body_override.robot_r"] == "quadruped" and not m["tainted"]


def test_manifest_with_no_model_says_demo_policy():
    o = opts()
    m = manifest(o, CONFIGS, check_options(o, CONFIGS), 1, "run_x", [], {})
    robot = next(a for a in m["avatars"] if a["avatar_id"] == "robot_r")
    assert "Demo policy" in robot["capability_card"] and robot["model"]["model_id"] is None


@pytest.mark.parametrize("kw,error", [
    ({"scenario_id": "NOPE"}, "unknown scenario"),
    ({"mode": "FAST"}, "STEPPED or LIVE"),
    ({"body_overrides": {"robot_r": "jetpack"}}, "unknown body"),
    ({"body_overrides": {"stranger": "quadruped"}}, "not in the cast"),
])
def test_bad_options_are_refused(kw, error):
    with pytest.raises(RunError, match=error):
        check_options(opts(**kw), CONFIGS)


def test_godot_command_never_carries_the_token_or_evaluator_data():
    o = opts(body_overrides={"robot_r": "quadruped"})
    scenario = check_options(o, CONFIGS)
    cmd = " ".join(godot_command(o, scenario, Path("/tmp/run"), 4242, 4204))
    assert "--scenario=SB04_POLITE_BID" in cmd and "--run-mode=STEPPED" in cmd and "--bodies=robot_r:quadruped" in cmd
    assert "--link-agents=robot_r,visitor_x,visitor_y" in cmd and "--headless" in cmd
    assert "token" not in cmd.lower() and "evaluator" not in cmd and "y_wants_help" not in cmd


def test_live_runs_in_real_time_stepped_as_fast_as_it_can():
    """G3c-2 (D-60): with --fixed-fps a headless LIVE world ran ~15x faster than the clock, so every
    answer from a 2 s model was refused as stale and Robot R made 1-3 decisions per run."""
    scenario = CONFIGS.items["scenarios"]["SB04_POLITE_BID"]
    live = godot_command(opts(mode="LIVE"), scenario, Path("/tmp/run"), 4242, 4204)
    stepped = godot_command(opts(mode="STEPPED"), scenario, Path("/tmp/run"), 4242, 4204)
    assert "--headless" in live and "--fixed-fps" not in live
    assert "--headless" in stepped and stepped[stepped.index("--fixed-fps") + 1] == "60"
