"""The disclosure gate (D-12): scopes against audiences; overheard is not told; WITHHOLD never hints."""

from __future__ import annotations

import pytest

from range_service.comms import disclosure as gate
from tests.test_link_sidecar import packet, presence, speech


def item(scope: str, shared_by: str | None = "anon_owner", group_id: str | None = None) -> dict:
    return {"scope": scope, "shared_by": shared_by, "group_id": group_id, "content": {"text": "x", "untrusted_text": True}}


ALONE_WITH_OWNER = gate.Audience(frozenset({"anon_owner"}), 0)
OWNER_AND_STRANGER = gate.Audience(frozenset({"anon_owner", "anon_stranger"}), 0)
STRANGER_ONLY = gate.Audience(frozenset({"anon_stranger"}), 0)
OWNER_AND_UNSEEN_VOICE = gate.Audience(frozenset({"anon_owner"}), 1)


@pytest.mark.parametrize("scope, audience, channel, group, expected", [
    ("PUBLIC", OWNER_AND_STRANGER, "LOCAL", None, gate.CLEAR),
    ("PUBLIC", STRANGER_ONLY, "PA", None, gate.CLEAR),
    ("SEALED", ALONE_WITH_OWNER, "LOCAL", None, gate.WITHHOLD),
    ("ONE_TO_ONE", ALONE_WITH_OWNER, "LOCAL", None, gate.CLEAR),
    ("ONE_TO_ONE", OWNER_AND_STRANGER, "LOCAL", None, gate.DEFER_TO_OWNER),
    ("ONE_TO_ONE", STRANGER_ONLY, "LOCAL", None, gate.WITHHOLD),
    ("ONE_TO_ONE", OWNER_AND_UNSEEN_VOICE, "LOCAL", None, gate.DEFER_TO_OWNER),   # an unplaced voice counts
    ("ONE_TO_ONE", ALONE_WITH_OWNER, "PA", None, gate.WITHHOLD),
    ("GROUP", ALONE_WITH_OWNER, "GROUP", "grp_000001", gate.CLEAR),
    ("GROUP", ALONE_WITH_OWNER, "GROUP", "grp_000002", gate.WITHHOLD),
    ("GROUP", ALONE_WITH_OWNER, "LOCAL", None, gate.WITHHOLD),
])
def test_scope_against_audience(scope, audience, channel, group, expected):
    decision = gate.check(item(scope, group_id="grp_000001" if scope == "GROUP" else None), audience, channel, group)
    assert decision.outcome == expected
    assert (decision.say is None) == (expected == gate.CLEAR)


def test_withheld_answers_never_hint():
    for line in gate.NEUTRAL_LINES:
        assert not any(hint in line.lower() for hint in gate.HINT_PHRASES), line
    for i in range(5):
        decision = gate.check(item("SEALED"), ALONE_WITH_OWNER, neutral_index=i)
        assert decision.say in gate.NEUTRAL_LINES
        assert "sealed" not in decision.say.lower()


def test_audience_comes_only_from_the_agents_own_packet():
    near, far = presence("anon_a", 1, 2.0), presence("anon_b", 2, 14.0)
    lost = dict(presence("anon_c", 3, 3.0), validity="OCCLUDED", quality=None)
    voice = speech("hello", None, track=None, n=4)
    audience = gate.audience_from_packet(packet("robot_legged", [near, far, lost, voice]))
    assert audience.tracks == frozenset({"anon_a"})   # the far one is out of earshot
    assert audience.unidentified == 2                 # the lost track and the unplaced voice


def test_overheard_is_not_stored_and_told_is():
    overheard = speech("The code is 4417.", False)
    assert gate.remember_speech("robot_legged", overheard, packet("robot_legged", [overheard]), 1) is None
    unaddressed = speech("Nice day.", None)
    assert gate.remember_speech("robot_legged", unaddressed, packet("robot_legged", [unaddressed]), 2) is None
    told = speech("The code is 4417.", True)
    public = gate.remember_speech("robot_legged", told,
                                  packet("robot_legged", [presence("anon_visitor0001"), presence("anon_other", 9), told]), 3)
    assert public["scope"] == "PUBLIC"               # said in front of someone else
    assert public["content"]["untrusted_text"] is True
