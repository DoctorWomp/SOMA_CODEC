"""ΔP (D-11, Addendum v0.2 §2-§3, §13; Blueprint T19)."""

from __future__ import annotations

import math

import pytest

from range_service import contracts
from range_service.horizon import delta as dp

CLIP = 3.0
EPS = 0.1


def nd(x, b=0.5, s=1.0, *, validity="OBSERVED", quality=0.8, clip=CLIP, epsilon=EPS):
    return dp.normalized_delta(x, b, s, validity=validity, quality=quality, clip=clip, epsilon=epsilon)


def test_formula_matches_blueprint_example():
    r = nd(2.0, b=0.5, s=1.0)
    assert r.normalized_delta == pytest.approx(1.5)
    assert r.null_reason is None and not r.clipped


@pytest.mark.parametrize(
    "validity,reason",
    [("MISSING", "MISSING_VALUE"), ("EXPIRED", "EXPIRED"), ("OCCLUDED", "NOT_OBSERVED"),
     ("UNKNOWN_SOURCE", "UNKNOWN_SOURCE")],
)
def test_missing_kinds_give_null_with_reason_never_zero(validity, reason):
    # Even with a numeric value equal to the baseline (which would compute to 0),
    # a non-observed status must not produce a number.
    r = nd(0.5, b=0.5, s=1.0, validity=validity)
    assert r.normalized_delta is None
    assert r.normalized_delta != 0
    assert r.null_reason == reason


@pytest.mark.parametrize(
    "x,b,s,reason",
    [(None, 0.5, 1.0, "MISSING_VALUE"), (2.0, None, 1.0, "NO_BASELINE"), (2.0, 0.5, None, "NO_SCALE"),
     (2.0, 0.5, -1.0, "INVALID_SCALE"), (math.nan, 0.5, 1.0, "NON_FINITE_INPUT"),
     (math.inf, 0.5, 1.0, "NON_FINITE_INPUT")],
)
def test_unsupported_inputs_give_null_with_reason(x, b, s, reason):
    r = nd(x, b, s)
    assert r.normalized_delta is None and r.null_reason == reason


def test_degraded_needs_explicit_quality():
    assert nd(2.0, validity="DEGRADED", quality=None).null_reason == "DEGRADED_WITHOUT_QUALITY"
    assert nd(2.0, validity="DEGRADED", quality=0.0).null_reason == "DEGRADED_WITHOUT_QUALITY"
    r = nd(2.0, validity="DEGRADED", quality=0.4)
    assert r.normalized_delta == pytest.approx(1.5) and r.quality == 0.4


def test_quality_is_reported_not_multiplied():
    high = nd(2.0, quality=1.0)
    low = nd(2.0, quality=0.1)
    assert high.normalized_delta == low.normalized_delta == pytest.approx(1.5)
    assert (high.quality, low.quality) == (1.0, 0.1)


@pytest.mark.parametrize("x,expected", [(100.0, CLIP), (-100.0, -CLIP)])
def test_clipping(x, expected):
    r = nd(x, b=0.0, s=1.0)
    assert r.normalized_delta == expected and r.clipped


def test_scale_floor():
    # scale 0 or below epsilon is floored at epsilon: (0.7 - 0.5) / 0.1 = 2.0
    assert nd(0.7, b=0.5, s=0.0).normalized_delta == pytest.approx(2.0)
    assert nd(0.7, b=0.5, s=0.01).normalized_delta == pytest.approx(2.0)
    assert nd(0.7, b=0.5, s=0.2).normalized_delta == pytest.approx(1.0)


@pytest.mark.parametrize("value", ["RAISED_HAND", True, False])
def test_categorical_inputs_are_not_turned_into_numbers(value):
    r = nd(value)
    assert r.normalized_delta is None and r.null_reason == "CATEGORICAL_INPUT"


def test_categorical_event_passes_through_unchanged():
    ev = dp.categorical_event("GESTURE", "RAISED_HAND", validity="OBSERVED", quality=0.9)
    assert (ev.channel, ev.event, ev.validity, ev.quality) == ("GESTURE", "RAISED_HAND", "OBSERVED", 0.9)
    assert not hasattr(ev, "normalized_delta")


@pytest.mark.parametrize("kwargs", [{"clip": 0}, {"clip": -1}, {"epsilon": 0}, {"epsilon": -0.1},
                                    {"validity": "CALM"}, {"quality": 1.5}])
def test_bad_configuration_raises(kwargs):
    with pytest.raises(ValueError):
        nd(1.0, **kwargs)


def test_robust_scale():
    assert dp.robust_scale([1, 2, 3]) is None  # too few samples: no invented scale
    assert dp.robust_scale([1, 2, 3, 4, 5]) == pytest.approx(1.4826 * 1.0)
    assert dp.robust_scale([1, 1, 1, 1, 50]) == 0.0  # robust to the outlier


# ---- S / Q summary (Addendum §3 arithmetic check, §13 check 2) ----

def test_salience_arithmetic_check():
    s = dp.salience_summary([dp.ChannelInput("AUDIO", 2.0, 0.9), dp.ChannelInput("GESTURE", 1.0, 0.8)])
    assert s.salience == pytest.approx(math.sqrt((0.9 * 4 + 0.8 * 1) / 1.7))
    assert s.salience == pytest.approx(1.609, abs=1e-3)
    assert s.coverage == pytest.approx(1.7 / 2)


def test_adding_inactive_channel_changes_coverage_not_salience():
    base = [dp.ChannelInput("AUDIO", 2.0, 0.9), dp.ChannelInput("GESTURE", 1.0, 0.8)]
    with_missing = base + [dp.ChannelInput("HEAD_ORIENTATION", None, None)]
    a = dp.salience_summary(base)
    b = dp.salience_summary(with_missing)
    assert b.salience == pytest.approx(a.salience)
    assert b.coverage == pytest.approx(1.7 / 3)  # ≈ 0.567
    assert b.coverage < a.coverage
    assert b.missing_channels == ("HEAD_ORIENTATION",)


def test_zero_quality_channel_counts_as_inactive():
    a = dp.salience_summary([dp.ChannelInput("AUDIO", 2.0, 0.9)])
    b = dp.salience_summary([dp.ChannelInput("AUDIO", 2.0, 0.9), dp.ChannelInput("GESTURE", 5.0, 0.0)])
    assert b.salience == pytest.approx(a.salience) and b.coverage < a.coverage


def test_nothing_usable_gives_null_salience_and_zero_coverage():
    s = dp.salience_summary([dp.ChannelInput("AUDIO", None, None), dp.ChannelInput("GESTURE", None, 0.5)])
    assert s.salience is None and s.coverage == 0.0
    assert dp.salience_summary([]).salience is None


# ---- packaging as a contract message ----

def _feature(result, x, b, s, scope):
    return dp.to_delta_feature(
        result, feature_id="delta_1", channel="GESTURE_RATE", track_id="anon_abcd1234", x=x,
        units="events_per_10_s", baseline=b, baseline_scope=scope, scale=s,
        observed_at_ms=100, expires_at_ms=2100, provenance="testworld_visual_fov_los_v1",
    )


def test_computed_and_null_results_are_valid_delta_features():
    computed = _feature(nd(2.0), 2.0, 0.5, 1.0, "SESSION")
    contracts.validate("delta_feature", computed)
    missing = _feature(nd(None, None, None, validity="MISSING", quality=None), None, None, None, "NONE")
    contracts.validate("delta_feature", missing)
    assert missing["normalized_delta"] is None and missing["null_reason"] == "MISSING_VALUE"


def test_contract_rejects_missing_reported_as_zero():
    missing = _feature(nd(None, None, None, validity="MISSING", quality=None), None, None, None, "NONE")
    missing["normalized_delta"] = 0.0
    missing["null_reason"] = None
    assert not contracts.is_valid("delta_feature", missing)
