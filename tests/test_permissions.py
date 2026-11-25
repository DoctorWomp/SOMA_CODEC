"""G4a (D-90, D-91): who may do what, without any UI.

The same table drives Godot's world dispatcher (tested headless in godot_app/tests and compared
case by case in tools/godot_check.py) and the viewer feed's filter tested here.
"""

from __future__ import annotations

import copy
import json

import pytest

from range_service.configs import load_and_check
from range_service.viewer import permissions as perm

CS, PROBLEMS = load_and_check()
TABLE = perm.load_table(CS)
VIEWS = ("VIEW_WORLD", "VIEW_SENSOR", "VIEW_LAYERS", "VIEW_EVALUATOR_TRUTH")


def test_configs_are_valid():
    assert not PROBLEMS, PROBLEMS[:3]


@pytest.mark.parametrize("seat", perm.SEATS)
def test_no_seat_acts_for_an_agent_or_edits_a_directive(seat):
    """A viewer seat can never send an action for an agent's body; only the Director intervenes (G4b)."""
    for target in ("robot_r", "visitor_x"):
        d = perm.check(TABLE, seat, "ACT_IN_WORLD", target, own_avatar=None)
        assert not d.ok, (seat, target, d)
    # G4b (D-97): only the Director may intervene, through every kind of intervention.
    for capability in ("EDIT_DIRECTIVE", "WORLD_CHANGE", "TRIGGER_EVENT", "INFLUENCE"):
        d = perm.check(TABLE, seat, capability, "robot_r")
        assert d.ok == (seat == "DIRECTOR"), (seat, capability, d)
        assert d.code == ("OK" if seat == "DIRECTOR" else "PERMISSION_DENIED")


def test_participant_acts_only_for_its_own_body():
    assert perm.check(TABLE, "PARTICIPANT", "ACT_IN_WORLD", "visitor_y", own_avatar="visitor_y").ok
    assert perm.check(TABLE, "PARTICIPANT", "ACT_IN_WORLD", "robot_r", own_avatar="visitor_y").code == "NOT_OWN_AVATAR"


def test_agents_act_only_for_controlled_avatars_and_never_view():
    assert perm.check(TABLE, "AGENT", "ACT_IN_WORLD", "robot_r", controlled=["robot_r"]).ok
    assert perm.check(TABLE, "AGENT", "ACT_IN_WORLD", "visitor_y", controlled=["robot_r"]).code == "NOT_CONTROLLED"
    for principal in perm.INTERNAL:
        for capability in TABLE["capabilities"]:
            if capability != "ACT_IN_WORLD":
                assert perm.check(TABLE, principal, capability, "robot_r", controlled=["robot_r"]).code == \
                    "PERMISSION_DENIED", (principal, capability)
        assert perm.audiences_for(TABLE, principal, "robot_r") == set()


def test_evaluator_truth_is_for_the_evaluator_seat_only():
    for principal in perm.PRINCIPALS:
        d = perm.check(TABLE, principal, "VIEW_EVALUATOR_TRUTH", "robot_r", own_avatar="robot_r")
        assert d.ok == (principal == "EVALUATOR"), principal
    assert perm.check(TABLE, "EVALUATOR", "VIEW_EVALUATOR_TRUTH", "robot_r").logged


def test_views_per_seat():
    for seat in ("SPECTATOR", "DIRECTOR", "EVALUATOR"):
        for view in ("VIEW_WORLD", "VIEW_SENSOR", "VIEW_LAYERS"):
            assert perm.check(TABLE, seat, view, "robot_r").ok
    # Participant: its own avatar's views only, and opening them is logged (INTERACTION_MODES §2.2).
    d = perm.check(TABLE, "PARTICIPANT", "VIEW_SENSOR", "visitor_y", own_avatar="visitor_y")
    assert d.ok and d.logged
    assert perm.check(TABLE, "PARTICIPANT", "VIEW_LAYERS", "robot_r", own_avatar="visitor_y").code == "NOT_OWN_AVATAR"


def test_not_built_names_its_gate():
    assert perm.check(TABLE, "DIRECTOR", "WORLD_CHANGE").ok          # built at G4b
    assert perm.check(TABLE, "DIRECTOR", "BYPASS_LAYER", "robot_r").gate == "G5"
    assert perm.check(TABLE, "SPECTATOR", "TIME_CONTROL").gate == "G4b"   # not built yet: time scale and step
    assert perm.check(TABLE, "DIRECTOR", "POSSESS", "visitor_x").gate == "G4c"


def test_audiences_and_readable_records():
    records = [{"audience": "OBSERVER", "observer": "robot_r", "lane": "sight"},
               {"audience": "EVALUATOR", "observer": "robot_r", "lane": "truth_tracks"}]
    assert [r["lane"] for r in perm.readable(TABLE, "SPECTATOR", records)] == ["sight"]
    assert [r["lane"] for r in perm.readable(TABLE, "DIRECTOR", records)] == ["sight"]
    assert [r["lane"] for r in perm.readable(TABLE, "EVALUATOR", records)] == ["sight", "truth_tracks"]
    assert perm.readable(TABLE, "PARTICIPANT", records, own_avatar="visitor_y") == []
    assert [r["lane"] for r in perm.readable(TABLE, "PARTICIPANT", records, own_avatar="robot_r")] == ["sight"]
    assert perm.readable(TABLE, "AGENT", records) == []


def test_table_problems_catch_a_widened_table():
    bad = copy.deepcopy(TABLE)
    bad["capabilities"]["VIEW_EVALUATOR_TRUTH"]["grants"]["SPECTATOR"] = "ANY"
    bad["capabilities"]["VIEW_LAYERS"]["grants"]["AGENT"] = "ANY"
    bad["capabilities"]["CAMERA_POV"]["grants"]["SPECTATOR"] = "OWN_AVATAR"
    found = perm.table_problems(bad)
    assert any("only the EVALUATOR seat" in p for p in found)
    assert any("AGENT is internal" in p for p in found)
    assert any("only PARTICIPANT has the OWN_AVATAR scope" in p for p in found)
    assert perm.table_problems(TABLE) == []


def test_godot_reads_the_same_table():
    from tools.export_godot_data import GODOT_DATA_DIR

    exported = json.loads((GODOT_DATA_DIR / "permissions" / "permissions.json").read_text(encoding="utf-8"))
    assert exported["data"] == TABLE


def test_matrix_covers_every_case():
    m = perm.matrix(TABLE)
    assert len(m) == len(perm.PRINCIPALS) * len(TABLE["capabilities"]) * 5
    assert m["SPECTATOR VIEW_EVALUATOR_TRUTH any"] == "PERMISSION_DENIED"
    assert m["EVALUATOR VIEW_EVALUATOR_TRUTH any"] == "OK"
    assert m["AGENT ACT_IN_WORLD controlled"] == "OK"
    assert m["AGENT ACT_IN_WORLD not_controlled"] == "NOT_CONTROLLED"
    assert set(m.values()) <= set(perm.CODES)
