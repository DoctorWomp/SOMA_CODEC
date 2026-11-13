"""Example configs validate; broken configs fail with a clear message."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from range_service.configs import CONFIGS_DIR, load_and_check

REPO = CONFIGS_DIR.parent
TOOL = REPO / "tools" / "validate_configs.py"


@pytest.fixture
def config_copy(tmp_path):
    target = tmp_path / "configs"
    shutil.copytree(CONFIGS_DIR, target)
    return target


def _messages(config_dir):
    _, problems = load_and_check(config_dir)
    return [str(p) for p in problems]


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"test setup: {old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_example_configs_are_valid():
    config_set, problems = load_and_check()
    assert not problems, "\n".join(map(str, problems))
    assert set(config_set.items["maps"]) == {"sandbox_flats"}
    assert {"robot_r", "visitor_y"} <= set(config_set.items["personas"])
    assert "robot_r" in config_set.items["bodies"]
    assert set(config_set.items["scenarios"]) == {"SB04_POLITE_BID"}
    assert "H0" in config_set.items["presets"]


def test_robot_r_cannot_use_stairs_but_can_use_ramp():
    config_set, _ = load_and_check()
    caps = config_set.items["bodies"]["robot_r"]["capabilities"]
    assert caps["can_use_stairs"] is False and caps["can_use_ramp"] is True


def test_slider_out_of_range_names_file_field_and_limit(config_copy):
    _edit(config_copy / "personas" / "visitor_y.yaml", "patience: 85", "patience: 120")
    msgs = _messages(config_copy)
    assert msgs == ["configs/personas/visitor_y.yaml: $.style.patience: 120 is greater than the maximum of 100"]


def test_unknown_field_is_named(config_copy):
    _edit(config_copy / "bodies" / "robot_r.yaml", "reach_m: 0.6", "reach_m: 0.6\nlaser_eyes: true")
    [msg] = _messages(config_copy)
    assert msg.startswith("configs/bodies/robot_r.yaml: $: unknown field(s) 'laser_eyes' are not allowed.")


def test_duplicate_key_is_rejected(config_copy):
    _edit(config_copy / "presets" / "H0.yaml", "question:", "preset_id: H1\nquestion:")
    [msg] = _messages(config_copy)
    assert "configs/presets/H0.yaml: not valid YAML" in msg and "duplicate key 'preset_id'" in msg


def test_broken_yaml_is_reported_not_crashing(config_copy):
    (config_copy / "maps" / "sandbox_flats.yaml").write_text("zones: [unclosed\n", encoding="utf-8")
    msgs = _messages(config_copy)
    assert len(msgs) == 1 and msgs[0].startswith("configs/maps/sandbox_flats.yaml: not valid YAML")
    # Only the root cause is reported, not a second "map not found" from the scenario that uses it.


def test_genuinely_missing_file_is_reported(config_copy):
    (config_copy / "personas" / "visitor_x.yaml").unlink()
    assert _messages(config_copy) == [
        "configs/scenarios/SB04_POLITE_BID.yaml: cast.visitor_x.persona 'visitor_x' not found in configs/personas/"
    ]


def test_missing_reference_is_reported(config_copy):
    _edit(config_copy / "scenarios" / "SB04_POLITE_BID.yaml", "preset: H0", "preset: H9")
    assert _messages(config_copy) == [
        "configs/scenarios/SB04_POLITE_BID.yaml: cast.robot_r.preset 'H9' not found in configs/presets/"
    ]


def test_id_must_match_file_name(config_copy):
    (config_copy / "presets" / "H0.yaml").rename(config_copy / "presets" / "H0_copy.yaml")
    msgs = _messages(config_copy)
    assert "configs/presets/H0_copy.yaml: preset_id is 'H0' but the file is named 'H0_copy.yaml'; they must match" in msgs


def test_l0_cannot_be_bypassed_in_a_preset(config_copy):
    _edit(config_copy / "presets" / "H0.yaml", "L0: true", "L0: false")
    assert _messages(config_copy) == ["configs/presets/H0.yaml: $.layers.L0: must be true, got false"]


def test_spawn_outside_map_is_reported(config_copy):
    _edit(config_copy / "maps" / "sandbox_flats.yaml", "position: {x: 15, z: 19}", "position: {x: 15, z: 25}")
    assert _messages(config_copy) == [
        "configs/maps/sandbox_flats.yaml: spawn point 'spawn_entrance' is outside the map bounds"
    ]


def test_command_line_exit_codes(config_copy):
    ok = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, cwd=REPO)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "All 8 config file(s) are valid." in ok.stdout
    _edit(config_copy / "personas" / "visitor_y.yaml", "patience: 85", "patience: 120")
    bad = subprocess.run([sys.executable, str(TOOL), str(config_copy)], capture_output=True, text=True, cwd=REPO)
    assert bad.returncode == 1
    assert "FAIL  configs/personas/visitor_y.yaml: $.style.patience: 120 is greater than the maximum of 100" in bad.stdout
