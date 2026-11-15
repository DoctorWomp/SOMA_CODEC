"""Cognition levels C0/C1/C2 with hysteresis (D-08, INFERENCE_STRATEGY §3.2, D-49)."""

from __future__ import annotations

from range_service.agents.cognition import (C1_IDLE_DEMOTE_MS, C2_IDLE_DEMOTE_MS, MIN_DWELL_MS, REPROMOTE_COOLDOWN_MS,
                                            CognitionLevel, Signals)


def test_addressed_promotes_and_addressed_twice_reaches_c2():
    c = CognitionLevel("C2")
    assert c.level == "C0"
    c.update(Signals(1000, addressed=True))
    assert c.level == "C1"
    c.update(Signals(5000, addressed=True))
    assert c.level == "C2" and c.changes[-1]["reason"] == "ADDRESSED_TWICE"


def test_never_above_the_persona_ceiling():
    c = CognitionLevel("C1")
    for t in range(0, 20_000, 1000):
        c.update(Signals(t, addressed=True, invited_to_group=True))
    assert c.level == "C1"


def test_demotion_needs_idle_time_and_dwell():
    c = CognitionLevel("C2")
    c.update(Signals(0, addressed=True))
    c.update(Signals(1000, addressed=True))
    assert c.level == "C2"
    c.update(Signals(1000 + C2_IDLE_DEMOTE_MS - 1, focal_within_far=True))
    assert c.level == "C2"
    c.update(Signals(1000 + C2_IDLE_DEMOTE_MS, focal_within_far=True))
    assert c.level == "C1" and c.changes[-1]["reason"] == "IDLE"
    c.update(Signals(1000 + C2_IDLE_DEMOTE_MS + C1_IDLE_DEMOTE_MS, focal_within_far=True))
    assert c.level == "C1"                          # a focal agent is still near: stays reactive
    c.update(Signals(1000 + C2_IDLE_DEMOTE_MS + C1_IDLE_DEMOTE_MS + 1))
    assert c.level == "C0" and c.changes[-1]["reason"] == "OUT_OF_INTERACTION"


def test_no_flapping_near_the_boundary():
    """Walking in and out of 'near' every second must not flip the level every second."""
    c = CognitionLevel("C2")
    for t in range(0, 120_000, 1000):
        c.update(Signals(t, near_focal=(t // 1000) % 2 == 0, focal_within_far=True))
    assert len(c.changes) <= 1


def test_cooldown_after_demotion_but_addressing_always_promotes():
    c = CognitionLevel("C2")
    c.update(Signals(0, near_focal=True))
    assert c.level == "C1"
    t = MIN_DWELL_MS + C1_IDLE_DEMOTE_MS
    c.update(Signals(t))
    assert c.level == "C0"
    c.update(Signals(t + 1000, near_focal=True))
    assert c.level == "C0"                          # cooling down: proximity alone does not promote
    c.update(Signals(t + 2000, addressed=True))
    assert c.level == "C1"                          # being addressed always does
    assert REPROMOTE_COOLDOWN_MS > 2000


def test_pinned_and_focal_agents_never_change():
    c = CognitionLevel("C2", pinned=True)
    assert c.level == "C2"
    for t in range(0, 200_000, 5000):
        assert c.update(Signals(t)) is None
    assert c.level == "C2" and c.changes == []
