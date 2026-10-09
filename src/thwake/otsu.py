"""Otsu threshold from a histogram, shared by the Sentinel-1 and Sentinel-2 water masks.

Method: docs/methodology.md §2.1–2.2. Earth Engine computes a fixed-bin histogram of the
water index (S2 MNDWI) or backscatter (S1 VV, dB) over the histogram region; the threshold
is found here, client side, so the logic is plain Python and unit-tested.

Otsu's method picks the threshold that maximises the between-class variance of the two
classes it creates. It works when the histogram is bimodal (water and land both present). If
the histogram is degenerate, or the threshold falls outside a plausible range set in
``config/thresholds.yaml``, the configured fixed threshold is used instead and the choice is
recorded (``threshold_method``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

OTSU = "otsu"
FALLBACK = "fallback"


def otsu_threshold(counts: Sequence[float], lower_edges: Sequence[float]) -> float | None:
    """Otsu threshold of a fixed-bin histogram.

    The threshold is returned as the upper edge of the last bin of the lower class, so
    ``value > threshold`` puts a pixel in the upper class for any value in a higher bin.

    Args:
        counts: Pixel count (or area) in each bin.
        lower_edges: Lower edge of each bin, increasing and evenly spaced.

    Returns:
        The threshold, or ``None`` if fewer than two bins hold pixels (no split possible).

    Raises:
        ValueError: If the inputs differ in length, have fewer than two bins, or a count is
            negative.
    """
    n = len(counts)
    if n != len(lower_edges) or n < 2:
        raise ValueError("Histogram needs at least two bins and one lower edge per bin")
    if any(c < 0 for c in counts):
        raise ValueError("Histogram counts must be non-negative")
    width = lower_edges[1] - lower_edges[0]
    centres = [e + width / 2 for e in lower_edges]
    total = float(sum(counts))
    if sum(1 for c in counts if c > 0) < 2:
        return None
    total_mean = sum(c * x for c, x in zip(counts, centres, strict=True)) / total

    best_k, best_var = 0, -1.0
    weight = cum_mean = 0.0
    for k in range(n - 1):
        weight += counts[k]
        cum_mean += counts[k] * centres[k]
        if weight == 0 or weight == total:
            continue
        w0 = weight / total
        mu0 = cum_mean / weight
        mu1 = (total_mean * total - cum_mean) / (total - weight)
        between = w0 * (1 - w0) * (mu0 - mu1) ** 2
        if between > best_var:
            best_k, best_var = k, between
    return lower_edges[best_k] + width


@dataclass(frozen=True)
class Threshold:
    """A threshold and how it was chosen (``otsu`` or ``fallback``)."""

    value: float
    method: str


def choose_threshold(
    counts: Sequence[float],
    lower_edges: Sequence[float],
    fallback: float,
    valid_range: tuple[float, float],
) -> Threshold:
    """Otsu threshold if it exists and lies within ``valid_range``, else the fallback.

    Args:
        counts: Histogram counts (see :func:`otsu_threshold`).
        lower_edges: Histogram bin lower edges.
        fallback: Fixed threshold from ``config/thresholds.yaml``.
        valid_range: ``(low, high)`` plausible Otsu thresholds, inclusive.

    Returns:
        The threshold used and its method.
    """
    value = otsu_threshold(counts, lower_edges) if sum(counts) > 0 else None
    low, high = valid_range
    if value is None or not low <= value <= high:
        return Threshold(fallback, FALLBACK)
    return Threshold(value, OTSU)


def histogram_bins(low: float, high: float, width: float) -> list[float]:
    """Lower edges of evenly spaced bins covering ``[low, high)``.

    Raises:
        ValueError: If ``high <= low`` or ``width`` is not positive.
    """
    if width <= 0 or high <= low:
        raise ValueError(f"Invalid histogram range [{low}, {high}) or width {width}")
    n = round((high - low) / width)
    return [low + i * width for i in range(n)]
