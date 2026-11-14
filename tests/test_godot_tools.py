"""Tests for the G1 Python tools that connect configs/ and the checks to Godot (D-30, D-34)."""

from __future__ import annotations

import json

import pytest

from tools import export_godot_data, godot_check


# ---------- export_godot_data ----------

def test_exported_godot_data_is_up_to_date():
    expected, blocking = export_godot_data.expected_files()
    assert blocking == []
    assert export_godot_data.stale_files(expected) == []


def test_export_covers_the_map_and_every_body():
    expected, _ = export_godot_data.expected_files()
    names = sorted(p.relative_to(export_godot_data.GODOT_DATA_DIR).as_posix() for p in expected)
    assert names == ["bodies/human_walker.json", "bodies/legged_humanoid.json", "bodies/quadruped.json",
                     "bodies/quadruped_arm.json", "bodies/wheeled_humanoid.json", "maps/sandbox_flats.json"]


def test_export_is_deterministic_and_wraps_the_config_unchanged():
    from range_service.configs import load_yaml

    source = export_godot_data.REPO / "configs" / "maps" / "sandbox_flats.yaml"
    data = load_yaml(source)
    first = export_godot_data.render("maps", "configs/maps/sandbox_flats.yaml", data)
    second = export_godot_data.render("maps", "configs/maps/sandbox_flats.yaml", data)
    assert first == second
    wrapper = json.loads(first)
    assert wrapper["kind"] == "maps"
    assert wrapper["source"] == "configs/maps/sandbox_flats.yaml"
    assert wrapper["data"] == data


def test_stale_and_orphaned_exports_are_reported(tmp_path):
    folder = tmp_path / "maps"
    folder.mkdir()
    current = folder / "current.json"
    current.write_text("same\n", encoding="utf-8")
    changed = folder / "changed.json"
    changed.write_text("old\n", encoding="utf-8")
    (folder / "orphan.json").write_text("{}\n", encoding="utf-8")
    missing = folder / "missing.json"

    # stale_files reports paths relative to the repository; point it at tmp files via REPO.
    original_repo = export_godot_data.REPO
    export_godot_data.REPO = tmp_path
    try:
        stale = export_godot_data.stale_files(
            {current: "same\n", changed: "new\n", missing: "x\n"}, data_dir=tmp_path)
    finally:
        export_godot_data.REPO = original_repo
    assert "maps/changed.json is out of date" in stale
    assert "maps/missing.json is missing" in stale
    assert "maps/orphan.json has no source config any more" in stale
    assert not any("current.json" in s for s in stale)


# ---------- godot_check output analysis ----------

GOOD_RUN = """Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org

PASS test_project_settings (3 ms)
PASS test_fixed_tick (40 ms)
G1 TESTS DONE passed=2 failed=0
"""


def test_a_clean_run_is_ok():
    report = godot_check.analyze(GOOD_RUN)
    assert report.passed == ["test_project_settings", "test_fixed_tick"]
    assert report.summary == (2, 0)
    assert report.ok


def test_an_error_line_fails_the_run_even_if_every_test_passed():
    output = GOOD_RUN.replace("PASS test_fixed_tick", "SCRIPT ERROR: Invalid call.\n   at: foo\nPASS test_fixed_tick")
    report = godot_check.analyze(output)
    assert report.errors == ["SCRIPT ERROR: Invalid call."]
    assert not report.ok


def test_engine_errors_count_and_warnings_do_not():
    output = GOOD_RUN + "ERROR: Parameter \"map\" is null.\nWARNING: something odd\n"
    report = godot_check.analyze(output)
    assert len(report.errors) == 1 and len(report.warnings) == 1
    assert not report.ok
    assert godot_check.analyze(GOOD_RUN + "WARNING: something odd\n").ok


@pytest.mark.parametrize("output", [
    "PASS test_a (1 ms)\n",                                        # never finished
    "PASS test_a (1 ms)\nFAIL test_b: wrong\nG1 TESTS DONE passed=1 failed=1\n",
    "G1 TESTS DONE passed=0 failed=0\n",                           # ran nothing
    "PASS test_a (1 ms)\nG1 TESTS DONE passed=2 failed=0\n",       # summary disagrees
])
def test_incomplete_or_failed_runs_are_not_ok(output):
    assert not godot_check.analyze(output).ok


def test_missing_godot_is_a_skip_unless_required(monkeypatch, capsys):
    monkeypatch.setattr(godot_check, "find_godot", lambda: None)
    assert godot_check.main([]) == godot_check.EXIT_SKIPPED
    assert godot_check.main(["--require"]) == godot_check.EXIT_FAILED
    assert "GODOT_BIN" in capsys.readouterr().out


def test_a_wrong_godot_bin_path_fails_instead_of_skipping(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GODOT_BIN", str(tmp_path / "no_such_godot.exe"))
    assert godot_check.main([]) == godot_check.EXIT_FAILED
    assert "no such file" in capsys.readouterr().out


def test_compile_report_finds_broken_scripts():
    good = "COMPILE DONE scripts=21 failed=0\n"
    assert godot_check.compile_report(good) == (21, [])
    bad = ("SCRIPT ERROR: Parse Error: Integer division. Decimal part will be discarded. (Warning treated as error.)\n"
           "COMPILE FAIL res://scripts/x.gd\nCOMPILE DONE scripts=21 failed=1\n")
    scripts, problems = godot_check.compile_report(bad)
    assert scripts == 21 and len(problems) == 2
    assert godot_check.compile_report("crashed\n")[0] == -1


def test_godot_outputs_are_checked_against_the_contracts(tmp_path):
    good = {"schema_version": "1.0", "seq": 0, "tick_id": 0, "sim_time_ms": 0, "kind": "RUN_ENDED",
            "actor_id": None, "payload": {"ticks_run": 0}}
    leak = dict(good, seq=1, kind="SPEECH_EMITTED", payload={"avatar_id": "x", "event_id": "evt_1",
                "channel": "LOCAL", "text": "hi", "addressee_id": None, "level_db": 62, "duration_ms": 1000,
                "private_goal": "secret"})
    (tmp_path / "run.jsonl").write_text(json.dumps(good) + "\n" + json.dumps(leak) + "\n", encoding="utf-8")
    packet = {"schema_version": "1.0", "observer_id": "a", "based_on_tick_id": 6, "sim_time_ms": 100,
              "coordinate_frame": "world_meters_xyz", "observer_pose": {"x": 0, "y": 0, "z": 0, "yaw_rad": 0},
              "observations": [], "scenario_label": "SB05"}
    (tmp_path / "x.observations.json").write_text(json.dumps([packet]), encoding="utf-8")
    checked, problems = godot_check.validate_artifacts(tmp_path, require_all=True)
    assert checked == 3
    assert any("run.jsonl line 2" in p and "private_goal" in p for p in problems)
    assert any("x.observations.json packet 0" in p for p in problems)
    assert any("sampling.jsonl was not written" in p for p in problems)
