"""Area–elevation–volume (AEV) curve: build, interpolate, read and write.

Method: docs/methodology.md §1.3 (curve) and §2.4 (area → level → volume); ADR 0006.

The curve is built from per-bin pixel sums that Earth Engine computes over the max-extent
mask (``thwake baseline --step aev``). A pixel at elevation ``z`` goes into bin
``k = floor((top - z) / step)``, where ``top`` is the full supply level (FSL). It is under
water at every level ``h_j = top - j * step`` with ``j <= k``. For each bin, Earth Engine
returns ``Σ a`` and ``Σ a * (top - z)``, where ``a`` is pixel area. Then, exactly:

- ``area(h_j)   = Σ_{k >= j} Σ a``
- ``volume(h_j) = Σ_{k >= j} Σ a * (h_j - z) = Σ_{k >= j} Σ a * (top - z) - j * step * area(h_j)``

:func:`bin_sums` is the pure-Python reference of that reduction (used by the tests on
synthetic valleys). Between curve levels, area and volume are interpolated linearly. With
0.5 m steps, linear interpolation of volume is off by at most ``Δarea * step / 8``, which
is about 0.02 MCM at FSL for Thwake.
"""

from __future__ import annotations

import csv
import math
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

AEV_COLUMNS = ("level_m_asl", "area_km2", "volume_mcm", "dem_source")
M2_PER_KM2 = 1e6
M3_PER_MCM = 1e6
# Decimal places written to the CSV: 1 cm, 100 m², 100 m³.
LEVEL_DECIMALS, AREA_DECIMALS, VOLUME_DECIMALS = 2, 4, 4
# Values this close outside the curve's range (rounding) are clamped rather than rejected.
RANGE_TOLERANCE = 1e-9


class AEVRangeError(ValueError):
    """Raised when a value lies outside the range covered by the AEV curve."""


BinSum = tuple[int, float, float]
"""``(bin, Σ pixel area m², Σ pixel area × (top − z) m³)`` for one elevation bin."""


@dataclass(frozen=True)
class AEVCurve:
    """Area and volume of the reservoir at a series of water levels, for one DEM.

    Attributes:
        levels_m: Water levels (m a.s.l.), strictly increasing.
        areas_km2: Water area at each level, non-decreasing.
        volumes_mcm: Stored volume at each level (million m³), non-decreasing.
        dem_source: Short name of the DEM the curve comes from.
    """

    levels_m: tuple[float, ...]
    areas_km2: tuple[float, ...]
    volumes_mcm: tuple[float, ...]
    dem_source: str

    def __post_init__(self) -> None:
        """Check the curve is well formed."""
        n = len(self.levels_m)
        if n < 2 or len(self.areas_km2) != n or len(self.volumes_mcm) != n:
            raise ValueError("An AEV curve needs at least two levels and one area/volume each")
        if any(b <= a for a, b in zip(self.levels_m, self.levels_m[1:], strict=False)):
            raise ValueError("AEV levels must be strictly increasing")
        for name, values in (("area", self.areas_km2), ("volume", self.volumes_mcm)):
            if values[0] < 0 or any(b < a for a, b in zip(values, values[1:], strict=False)):
                raise ValueError(f"AEV {name} must be non-negative and non-decreasing")

    @property
    def top_level_m(self) -> float:
        """Highest level on the curve (the FSL for the Thwake baseline)."""
        return self.levels_m[-1]

    @property
    def top_area_km2(self) -> float:
        """Area at the highest level."""
        return self.areas_km2[-1]

    @property
    def top_volume_mcm(self) -> float:
        """Volume at the highest level."""
        return self.volumes_mcm[-1]

    def volume_at_level(self, level_m: float) -> float:
        """Volume (MCM) at a water level (m a.s.l.), interpolated linearly.

        Raises:
            AEVRangeError: If the level is outside the curve.
        """
        return _interpolate(self.levels_m, self.volumes_mcm, level_m, "level")

    def area_at_level(self, level_m: float) -> float:
        """Area (km²) at a water level (m a.s.l.), interpolated linearly.

        Raises:
            AEVRangeError: If the level is outside the curve.
        """
        return _interpolate(self.levels_m, self.areas_km2, level_m, "level")

    def level_at_area(self, area_km2: float) -> float:
        """Water level (m a.s.l.) at which the reservoir covers ``area_km2``.

        Where the area stays constant over several levels, the lowest such level is returned
        (the level at which that area is first reached).

        Raises:
            AEVRangeError: If the area is outside the curve.
        """
        areas, levels = _first_of_runs(self.areas_km2, self.levels_m)
        return _interpolate(areas, levels, area_km2, "area")

    def volume_at_area(self, area_km2: float) -> float:
        """Volume (MCM) for a water area (km²): area → level → volume.

        Raises:
            AEVRangeError: If the area is outside the curve.
        """
        return self.volume_at_level(self.level_at_area(area_km2))


def _first_of_runs(
    xs: Sequence[float], ys: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Drop repeated ``xs`` values, keeping the first ``y`` of each run."""
    kept_x, kept_y = [xs[0]], [ys[0]]
    for x, y in zip(xs[1:], ys[1:], strict=True):
        if x > kept_x[-1]:
            kept_x.append(x)
            kept_y.append(y)
    return tuple(kept_x), tuple(kept_y)


def _interpolate(xs: Sequence[float], ys: Sequence[float], x: float, name: str) -> float:
    """Piecewise-linear ``y(x)`` for strictly increasing ``xs``."""
    if not math.isfinite(x):
        raise AEVRangeError(f"{name} must be a finite number, got {x}")
    lo, hi = xs[0], xs[-1]
    tol = RANGE_TOLERANCE * max(1.0, abs(lo), abs(hi))
    if x < lo - tol or x > hi + tol:
        raise AEVRangeError(f"{name} {x:g} is outside the AEV curve range [{lo:g}, {hi:g}]")
    if len(xs) == 1 or x <= lo:
        return ys[0]
    if x >= hi:
        return ys[-1]
    i = bisect_right(xs, x)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# --- Building the curve -----------------------------------------------------------------


def bin_index(elevation_m: float, top_m: float, step_m: float) -> int:
    """Elevation bin of a pixel: under water at levels ``top - j * step`` for ``j <= bin``.

    Negative for pixels above ``top`` (dry at every level on the curve).
    """
    return math.floor((top_m - elevation_m) / step_m)


def bin_sums(pixels: Iterable[tuple[float, float]], top_m: float, step_m: float) -> list[BinSum]:
    """Pure-Python reference of the Earth Engine per-bin reduction.

    Args:
        pixels: ``(elevation m, pixel area m²)`` for each pixel inside the mask.
        top_m: Highest level of the curve (FSL).
        step_m: Level spacing.

    Returns:
        ``(bin, Σ area, Σ area × (top − elevation))`` per non-empty bin, sorted by bin.
    """
    area: dict[int, float] = defaultdict(float)
    depth_area: dict[int, float] = defaultdict(float)
    for z, a in pixels:
        k = bin_index(z, top_m, step_m)
        area[k] += a
        depth_area[k] += a * (top_m - z)
    return [(k, area[k], depth_area[k]) for k in sorted(area)]


def curve_from_bins(
    bins: Iterable[BinSum], top_m: float, step_m: float, dem_source: str
) -> AEVCurve:
    """Build the AEV curve from per-bin sums (see the module docstring for the formulas).

    Bins below zero (pixels above ``top``) are ignored. The curve runs from one step below
    the lowest pixel (area 0, volume 0) up to ``top``.

    Args:
        bins: Output of :func:`bin_sums` or of the Earth Engine reduction.
        top_m: Highest level (FSL), m a.s.l.
        step_m: Level spacing, m (positive).
        dem_source: Short DEM name stored with the curve.

    Returns:
        The curve, levels increasing.

    Raises:
        ValueError: If no pixel lies at or below ``top`` or the step is not positive.
    """
    if step_m <= 0:
        raise ValueError(f"Level step must be positive, got {step_m}")
    area: dict[int, float] = defaultdict(float)
    depth_area: dict[int, float] = defaultdict(float)
    for k, a, d in bins:
        if k >= 0:
            area[int(k)] += a
            depth_area[int(k)] += d
    if not area:
        raise ValueError(f"No pixels at or below {top_m:g} m: the curve would be empty")

    deepest = max(area)
    levels, areas, volumes = [], [], []
    cum_area = cum_depth_area = 0.0
    # j runs from one step below the lowest pixel (empty) up to the top (j = 0).
    for j in range(deepest + 1, -1, -1):
        cum_area += area.get(j, 0.0)
        cum_depth_area += depth_area.get(j, 0.0)
        volume_m3 = max(cum_depth_area - j * step_m * cum_area, 0.0)
        levels.append(top_m - j * step_m)
        areas.append(cum_area / M2_PER_KM2)
        volumes.append(volume_m3 / M3_PER_MCM)
    return AEVCurve(tuple(levels), tuple(areas), tuple(_monotone(volumes)), dem_source)


def _monotone(values: list[float]) -> list[float]:
    """Remove floating-point dips (~1e-9) so the sequence is non-decreasing."""
    out: list[float] = []
    for v in values:
        out.append(max(v, out[-1]) if out else v)
    return out


# --- CSV --------------------------------------------------------------------------------


def write_aev_csv(path: Path, curves: Iterable[AEVCurve]) -> None:
    """Write curves to one CSV (``level_m_asl, area_km2, volume_mcm, dem_source``).

    Rows are grouped by DEM in the given order, levels increasing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(AEV_COLUMNS)
        for c in curves:
            for h, a, v in zip(c.levels_m, c.areas_km2, c.volumes_mcm, strict=True):
                writer.writerow(
                    [
                        f"{h:.{LEVEL_DECIMALS}f}",
                        f"{a:.{AREA_DECIMALS}f}",
                        f"{v:.{VOLUME_DECIMALS}f}",
                        c.dem_source,
                    ]
                )


def read_aev_csv(path: Path) -> dict[str, AEVCurve]:
    """Read an AEV CSV into one curve per ``dem_source`` (in file order).

    Raises:
        ValueError: If the header is wrong or a curve is malformed.
    """
    rows: dict[str, list[tuple[float, float, float]]] = {}
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != AEV_COLUMNS:
            raise ValueError(f"{path}: expected columns {AEV_COLUMNS}, got {reader.fieldnames}")
        for r in reader:
            rows.setdefault(r["dem_source"], []).append(
                (float(r["level_m_asl"]), float(r["area_km2"]), float(r["volume_mcm"]))
            )
    curves = {}
    for source, values in rows.items():
        values.sort()
        levels, areas, volumes = zip(*values, strict=True)
        curves[source] = AEVCurve(levels, areas, volumes, source)
    return curves


def percent_difference(value: float, reference: float) -> float:
    """``(value − reference) / reference × 100``."""
    return (value - reference) / reference * 100
