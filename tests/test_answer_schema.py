"""The constrained answer schema (D-21, D-50; fixed at G3c-2, D-60).

Found in the owner's NPC bake-off (2026-11-17): llama.cpp b12443 reads oneOf/anyOf before
anything else in a schema node and ignores properties beside them, so MOVE_TO and LOOK_AT
arguments were never constrained. Reproduced on the pinned llama-server: asked for
{"target": "person_near"} it produced exactly that; with the fixed schema it cannot.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from range_service.agents.context import OUTPUT_CAPS
from range_service.agents.output_schema import answer_schema, mixes_alternatives
from range_service.agents.tokenizer import ApproxTokenizer

ALL = ("MOVE_TO", "LOOK_AT", "TURN_TO", "SPEAK", "GESTURE", "EXPRESS", "WAIT", "YIELD", "INTERACT",
       "REQUEST_CLARIFICATION", "NO_OP")
TRACK, OTHER = "anon_k3j9x2m1qa", "anon_zzzzzzzzzz"


def _ok(schema, answer) -> bool:
    return not list(Draft202012Validator(schema).iter_errors(answer))


@pytest.mark.parametrize("kw", [{}, {"targets": (TRACK,), "channels": ("LOCAL",), "tier": "C1"},
                                {"targets": (), "channels": ("LOCAL",), "tier": "C2"}])
def test_no_node_mixes_alternatives_with_other_keywords(kw):
    assert mixes_alternatives(answer_schema(ALL, **kw)) == []


def test_move_and_look_arguments_are_really_constrained():
    s = answer_schema(ALL)
    for bad in ({"action": "LOOK_AT", "args": {"target": "person_near"}},
                {"action": "MOVE_TO", "args": {"destination": "platform"}},
                {"action": "LOOK_AT", "args": {"point": [0.5, 1.2, 2.0]}},
                {"action": "LOOK_AT", "args": {}},
                {"action": "LOOK_AT", "args": {"target_id": TRACK, "point": {"x": 1, "y": 1, "z": 1}}}):
        assert not _ok(s, {"actions": [bad]}), bad
    assert _ok(s, {"actions": [{"action": "MOVE_TO", "args": {"destination": {"x": 1.0, "z": 2.0}}}]})
    assert _ok(s, {"actions": [{"action": "LOOK_AT", "args": {"target_id": TRACK}}]})


def test_only_perceived_tracks_and_allowed_channels_can_be_named():
    s = answer_schema(ALL, (TRACK,), ("LOCAL",), "C2")
    assert _ok(s, {"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi", "addressee_id": TRACK}}]})
    assert not _ok(s, {"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi", "addressee_id": OTHER}}]})
    assert not _ok(s, {"actions": [{"action": "SPEAK", "args": {"channel": "GROUP", "text": "Hi", "group_id": "g"}}]})
    assert not _ok(s, {"actions": [{"action": "TURN_TO", "args": {"target_id": OTHER}}]})
    nobody = answer_schema(ALL, (), ("LOCAL",), "C2")
    assert _ok(nobody, {"actions": [{"action": "TURN_TO", "args": {"yaw_rad": 1.0}}]})
    assert not _ok(nobody, {"actions": [{"action": "TURN_TO", "args": {"target_id": TRACK}}]})
    assert _ok(nobody, {"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "Hi", "addressee_id": None}}]})


def test_body_limits_gestures_and_expressions():
    s = answer_schema(ALL, (TRACK,), ("LOCAL",), "FOCAL", ("NOD", "HEAD_TILT"), ("acknowledge_tilt",))
    assert _ok(s, {"actions": [{"action": "GESTURE", "args": {"gesture": "NOD"}}]})
    assert not _ok(s, {"actions": [{"action": "GESTURE", "args": {"gesture": "WAVE"}}]})
    assert not _ok(s, {"actions": [{"action": "EXPRESS", "args": {"expression_id": "greeting"}}]})
    none = answer_schema(ALL, (TRACK,), ("LOCAL",), "FOCAL", (), ())
    offered = [c["properties"]["action"]["const"] for c in none["properties"]["actions"]["items"]["anyOf"]]
    assert "GESTURE" not in offered and "EXPRESS" not in offered


def test_npc_tiers_get_short_text_so_a_full_answer_fits_the_cap():
    c1 = answer_schema(ALL, (TRACK,), ("LOCAL",), "C1")
    three = [{"action": "WAIT", "args": {"duration_ms": 1000}}] * 3
    assert not _ok(c1, {"actions": three})                                   # C1: at most 2 actions
    assert not _ok(c1, {"actions": three[:1], "reason_summary": "x" * 81})
    # The longest answer the C1 schema allows, with indentation, still fits the C1 output cap.
    longest = {"actions": [{"action": "SPEAK", "args": {"channel": "LOCAL", "text": "w" * 160, "addressee_id": TRACK,
                                                        "disclosure_scope": "ONE_TO_ONE"}, "commitment": "c" * 40},
                           {"action": "LOOK_AT", "args": {"target_id": TRACK}}], "reason_summary": "r" * 80}
    assert _ok(c1, longest)
    text = json.dumps(longest, indent=1)
    assert ApproxTokenizer().count(text) <= OUTPUT_CAPS["C1"], ApproxTokenizer().count(text)
