"""ΔP: typed per-channel normalized deviations (D-11, Addendum v0.2 §2-§3).

    normalized_delta = clip((x - b) / max(s, epsilon), -M, +M)

Rules this module enforces:

* Missing, expired, occluded, unattributed or unsupported inputs give
  ``normalized_delta = None`` with a ``null_reason``. Never 0, never "calm".
* Quality ``q`` is reported next to the delta and is **never multiplied in**.
* Categorical events (a raised hand, a yielded turn) stay events: they are not
  turned into numbers.
* The salience summary ``S`` and coverage ``Q`` are optional, for attention
  scheduling only. They carry no emotional, hostility or danger meaning.

In code this is ``normalized_delta``, never "pressure" (D-08).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence

# Validity values (contracts/common.schema.json#/$defs/validity).
OBSERVED = "OBSERVED"
DEGRADED = "DEGRADED"
OCCLUDED = "OCCLUDED"
MISSING = "MISSING"
EXPIRED = "EXPIRED"
UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
VALIDITIES = (OBSERVED, DEGRADED, OCCLUDED, MISSING, EXPIRED, UNKNOWN_SOURCE)

# Null reasons (contracts/delta_feature.schema.json).
MISSING_VALUE = "MISSING_VALUE"
NOT_OBSERVED = "NOT_OBSERVED"
EXPIRED_REASON = "EXPIRED"
UNKNOWN_SOURCE_REASON = "UNKNOWN_SOURCE"
DEGRADED_WITHOUT_QUALITY = "DEGRADED_WITHOUT_QUALITY"
NO_BASELINE = "NO_BASELINE"
NO_SCALE = "NO_SCALE"
INVALID_SCALE = "INVALID_SCALE"
NON_FINITE_INPUT = "NON_FINITE_INPUT"
CATEGORICAL_INPUT = "CATEGORICAL_INPUT"

_VALIDITY_NULL_REASON = {
    MISSING: MISSING_VALUE,
    EXPIRED: EXPIRED_REASON,
    OCCLUDED: NOT_OBSERVED,
    UNKNOWN_SOURCE: UNKNOWN_SOURCE_REASON,
}

# Robust scale: 1.4826 x median absolute deviation estimates a standard
# deviation for normally distributed data (Addendum §2).
MAD_TO_SIGMA = 1.4826

CONFIG_VERSION = "deltap.v1"


@dataclass(frozen=True)
class DeltaResult:
    """One channel's result. ``normalized_delta`` is None exactly when ``null_reason`` is set."""

    normalized_delta: float | None
    null_reason: str | None
    quality: float | None
    validity: str
    clipped: bool = False

    @property
    def is_null(self) -> bool:
        return self.normalized_delta is None


@dataclass(frozen=True)
class CategoricalEvent:
    """A categorical event passes through unchanged; it never becomes a number."""

    channel: str
    event: str
    validity: str
    quality: float | None


def _is_number(value: object) -> bool:
    # bool is a subclass of int in Python; a True/False flag is categorical, not numeric.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _null(reason: str, validity: str, quality: float | None) -> DeltaResult:
    return DeltaResult(normalized_delta=None, null_reason=reason, quality=quality, validity=validity)


def normalized_delta(
    x: float | None,
    baseline: float | None,
    scale: float | None,
    *,
    validity: str,
    quality: float | None,
    clip: float,
    epsilon: float,
) -> DeltaResult:
    """Compute ``clip((x - baseline) / max(scale, epsilon), -clip, +clip)`` or a null with a reason.

    ``clip`` (M) and ``epsilon`` are declared per channel and must be positive.
    A DEGRADED measurement is computed only when its quality is stated and > 0.
    """
    if not (_is_number(clip) and math.isfinite(clip) and clip > 0):
        raise ValueError(f"clip M must be a positive finite number, got {clip!r}")
    if not (_is_number(epsilon) and math.isfinite(epsilon) and epsilon > 0):
        raise ValueError(f"epsilon must be a positive finite number, got {epsilon!r}")
    if validity not in VALIDITIES:
        raise ValueError(f"unknown validity {validity!r}; expected one of {VALIDITIES}")
    if quality is not None and not (_is_number(quality) and 0.0 <= quality <= 1.0):
        raise ValueError(f"quality must be in [0, 1] or None, got {quality!r}")

    if validity in _VALIDITY_NULL_REASON:
        return _null(_VALIDITY_NULL_REASON[validity], validity, quality)
    if validity == DEGRADED and (quality is None or quality <= 0.0):
        return _null(DEGRADED_WITHOUT_QUALITY, validity, quality)

    if x is None:
        return _null(MISSING_VALUE, validity, quality)
    if not _is_number(x):
        return _null(CATEGORICAL_INPUT, validity, quality)
    if baseline is None:
        return _null(NO_BASELINE, validity, quality)
    if scale is None:
        return _null(NO_SCALE, validity, quality)
    if not (_is_number(baseline) and _is_number(scale)):
        return _null(NON_FINITE_INPUT, validity, quality)
    if not all(math.isfinite(v) for v in (x, baseline, scale)):
        return _null(NON_FINITE_INPUT, validity, quality)
    if scale < 0:
        return _null(INVALID_SCALE, validity, quality)

    raw = (x - baseline) / max(scale, epsilon)
    bounded = min(max(raw, -clip), clip)
    return DeltaResult(
        normalized_delta=bounded,
        null_reason=None,
        quality=quality,
        validity=validity,
        clipped=bounded != raw,
    )


def categorical_event(channel: str, event: str, *, validity: str, quality: float | None) -> CategoricalEvent:
    """Record a categorical event as-is (Addendum §2: categorical events stay categorical)."""
    if validity not in VALIDITIES:
        raise ValueError(f"unknown validity {validity!r}")
    return CategoricalEvent(channel=channel, event=event, validity=validity, quality=quality)


def robust_scale(samples: Iterable[float], *, min_samples: int = 5) -> float | None:
    """1.4826 x median absolute deviation, or None if there are too few samples.

    None means "no scale yet": callers then get ``NO_SCALE`` rather than an invented value.
    """
    values = [float(v) for v in samples if _is_number(v) and math.isfinite(v)]
    if len(values) < min_samples:
        return None
    center = median(values)
    return MAD_TO_SIGMA * median(abs(v - center) for v in values)


@dataclass(frozen=True)
class ChannelInput:
    """One expected channel for the S/Q summary. ``z`` is None when the channel has no valid delta."""

    channel: str
    z: float | None
    quality: float | None
    weight: float = 1.0


@dataclass(frozen=True)
class SalienceSummary:
    """Optional summary for attention scheduling (Addendum §3). Not an emotion or danger score.

    ``salience`` (S) is None when no channel is usable. ``coverage`` (Q) is the
    weighted share of expected channels that were actually usable.
    """

    salience: float | None
    coverage: float
    used_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]


def salience_summary(channels: Sequence[ChannelInput]) -> SalienceSummary:
    """S = sqrt(sum w q z^2 / sum w q) over usable channels; Q = sum w q (usable) / sum w (all expected).

    A channel is usable when ``z`` is a number and its quality is > 0. Adding an
    expected but inactive channel lowers Q and leaves S unchanged.
    """
    for ch in channels:
        if not (_is_number(ch.weight) and ch.weight >= 0):
            raise ValueError(f"channel {ch.channel!r}: weight must be >= 0")
        if ch.quality is not None and not (0.0 <= ch.quality <= 1.0):
            raise ValueError(f"channel {ch.channel!r}: quality must be in [0, 1]")

    usable = [ch for ch in channels if ch.z is not None and ch.quality is not None and ch.quality > 0]
    missing = tuple(ch.channel for ch in channels if ch not in usable)
    total_weight = sum(ch.weight for ch in channels)
    used_weight = sum(ch.weight * ch.quality for ch in usable)  # type: ignore[operator]

    if used_weight == 0:
        return SalienceSummary(salience=None, coverage=0.0, used_channels=(), missing_channels=missing)

    weighted_sq = sum(ch.weight * ch.quality * ch.z * ch.z for ch in usable)  # type: ignore[operator]
    return SalienceSummary(
        salience=math.sqrt(weighted_sq / used_weight),
        coverage=used_weight / total_weight,
        used_channels=tuple(ch.channel for ch in usable),
        missing_channels=missing,
    )


def to_delta_feature(
    result: DeltaResult,
    *,
    feature_id: str,
    channel: str,
    track_id: str | None,
    x: float | None,
    units: str,
    baseline: float | None,
    baseline_scope: str,
    scale: float | None,
    observed_at_ms: int,
    expires_at_ms: int,
    provenance: str,
    config_version: str = CONFIG_VERSION,
) -> dict:
    """Package a result as a ``delta_feature`` message (contracts/delta_feature.schema.json)."""
    return {
        "schema_version": "1.0",
        "feature_id": feature_id,
        "channel": channel,
        "track_id": track_id,
        "value": x if _is_number(x) else None,
        "units": units,
        "baseline": baseline,
        "baseline_scope": baseline_scope,
        "scale": scale,
        "normalized_delta": result.normalized_delta,
        "null_reason": result.null_reason,
        "quality": result.quality,
        "validity": result.validity,
        "observed_at_ms": observed_at_ms,
        "expires_at_ms": expires_at_ms,
        "provenance": provenance,
        "config_version": config_version,
    }
