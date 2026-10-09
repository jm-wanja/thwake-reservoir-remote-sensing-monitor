"""Tests for the AEV curve on synthetic valleys with known geometry.

Two shapes with closed-form answers (levels relative to the valley floor, h >= 0):

- **Cone** (bowl): radius r(h) = h / s, so area A(h) = π (h/s)² and volume V(h) = π h³ / (3 s²).
- **V-valley** (triangular trough of length L, side slope s, flat floor along its length):
  width w(h) = 2h / s, so A(h) = L · 2h / s and V(h) = L · h² / s.

Interpolation is tested on exact curve nodes, and the full build (pixel binning → cumulative
sums, the same arithmetic Earth Engine does) on 30 m pixel grids of the same shapes.
"""

import math
from pathlib import Path

import pytest

from thwake import volume as v

FLOOR, TOP, STEP = 840.0, 912.0, 0.5
CONE_SLOPE = 0.012  # rise per metre: radius at 72 m depth = 6 km (Thwake-sized)
TROUGH_LENGTH, TROUGH_SLOPE = 12_000.0, 0.03


def cone_area_km2(h: float) -> float:
    return math.pi * (max(h, 0.0) / CONE_SLOPE) ** 2 / 1e6


def cone_volume_mcm(h: float) -> float:
    return math.pi * max(h, 0.0) ** 3 / (3 * CONE_SLOPE**2) / 1e6


def trough_area_km2(h: float) -> float:
    return TROUGH_LENGTH * 2 * max(h, 0.0) / TROUGH_SLOPE / 1e6


def trough_volume_mcm(h: float) -> float:
    return TROUGH_LENGTH * max(h, 0.0) ** 2 / TROUGH_SLOPE / 1e6


def analytic_curve(area, vol, name: str) -> v.AEVCurve:
    n = round((TOP - FLOOR) / STEP)
    levels = tuple(FLOOR + i * STEP for i in range(n + 1))
    return v.AEVCurve(
        levels,
        tuple(area(h - FLOOR) for h in levels),
        tuple(vol(h - FLOOR) for h in levels),
        name,
    )


@pytest.fixture
def cone() -> v.AEVCurve:
    return analytic_curve(cone_area_km2, cone_volume_mcm, "cone")


@pytest.fixture
def trough() -> v.AEVCurve:
    return analytic_curve(trough_area_km2, trough_volume_mcm, "trough")


# --- Interpolation on exact nodes -------------------------------------------------------

# Linear interpolation between 0.5 m nodes: volume error ≤ ΔA·Δh/8 (≈0.03 MCM here, <0.01%
# of a mid-depth volume); level from area ≤ a few mm. Tolerances below are stated per test.
INTERMEDIATE_LEVELS = [850.3, 875.25, 899.9, 911.8]


def linear_volume_bound_mcm(area, h: float) -> float:
    """Max error of linear volume interpolation in the step containing ``h``: ΔA·Δh/8."""
    h0 = FLOOR + math.floor((h - FLOOR) / STEP) * STEP
    return (area(h0 + STEP - FLOOR) - area(h0 - FLOOR)) * 1e6 * STEP / 8 / 1e6


@pytest.mark.parametrize("h", INTERMEDIATE_LEVELS)
def test_cone_level_to_volume(cone: v.AEVCurve, h: float) -> None:
    bound = linear_volume_bound_mcm(cone_area_km2, h)
    assert abs(cone.volume_at_level(h) - cone_volume_mcm(h - FLOOR)) <= bound * 1.01


@pytest.mark.parametrize("h", INTERMEDIATE_LEVELS)
def test_cone_area_to_level(cone: v.AEVCurve, h: float) -> None:
    assert cone.level_at_area(cone_area_km2(h - FLOOR)) == pytest.approx(h, abs=0.01)


@pytest.mark.parametrize("h", INTERMEDIATE_LEVELS)
def test_cone_area_to_volume(cone: v.AEVCurve, h: float) -> None:
    area = cone_area_km2(h - FLOOR)
    # Level is off by a few mm (area is quadratic in level), adding ≤ A·δh to the volume bound.
    tol = linear_volume_bound_mcm(cone_area_km2, h) + area * 0.01
    assert abs(cone.volume_at_area(area) - cone_volume_mcm(h - FLOOR)) <= tol


@pytest.mark.parametrize("h", INTERMEDIATE_LEVELS)
def test_trough_round_trip(trough: v.AEVCurve, h: float) -> None:
    # Area is linear in level, so area → level is exact up to float error.
    area = trough_area_km2(h - FLOOR)
    assert trough.level_at_area(area) == pytest.approx(h, abs=1e-9)
    assert trough.area_at_level(h) == pytest.approx(area, rel=1e-12)
    tol = linear_volume_bound_mcm(trough_area_km2, h) * 1.01
    assert abs(trough.volume_at_area(area) - trough_volume_mcm(h - FLOOR)) <= tol


def test_nodes_are_returned_exactly(cone: v.AEVCurve) -> None:
    assert cone.volume_at_level(TOP) == cone.top_volume_mcm
    assert cone.volume_at_level(FLOOR) == 0
    assert cone.level_at_area(cone.top_area_km2) == TOP


def test_out_of_range_raises(cone: v.AEVCurve) -> None:
    for bad in (FLOOR - 1, TOP + 0.01, math.nan):
        with pytest.raises(v.AEVRangeError):
            cone.volume_at_level(bad)
    with pytest.raises(v.AEVRangeError):
        cone.level_at_area(cone.top_area_km2 * 1.01)
    with pytest.raises(v.AEVRangeError):
        cone.volume_at_area(-0.1)
    # AEVRangeError is a ValueError, so generic handlers catch it.
    assert issubclass(v.AEVRangeError, ValueError)


def test_flat_area_maps_to_lowest_level() -> None:
    curve = v.AEVCurve((1.0, 2.0, 3.0, 4.0), (0.0, 0.0, 5.0, 5.0), (0.0, 0.0, 2.5, 7.5), "x")
    assert curve.level_at_area(0.0) == 1.0
    assert curve.level_at_area(5.0) == 3.0
    # Interpolates between the first levels of each run: (1.0, 0) and (3.0, 5).
    assert curve.level_at_area(2.5) == pytest.approx(2.0)


@pytest.mark.parametrize(
    "levels, areas, volumes",
    [
        ((1.0,), (0.0,), (0.0,)),
        ((1.0, 1.0), (0.0, 1.0), (0.0, 1.0)),
        ((1.0, 2.0), (1.0, 0.5), (0.0, 1.0)),
        ((1.0, 2.0), (0.0, 1.0), (1.0, 0.5)),
        ((1.0, 2.0), (-1.0, 1.0), (0.0, 1.0)),
        ((1.0, 2.0), (0.0, 1.0), (0.0,)),
    ],
)
def test_malformed_curve_raises(levels, areas, volumes) -> None:
    with pytest.raises(ValueError):
        v.AEVCurve(levels, areas, volumes, "bad")


# --- Building from pixels (the Earth Engine arithmetic) ---------------------------------

PIXEL_M = 30.0


def cone_pixels() -> list[tuple[float, float]]:
    """30 m grid over a cone; pixel elevation at the centre, flat beyond the FSL radius."""
    radius = (TOP - FLOOR) / CONE_SLOPE
    n = math.ceil(radius / PIXEL_M) + 1
    pixels = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            r = math.hypot(i * PIXEL_M, j * PIXEL_M)
            if r <= radius + PIXEL_M:  # include a ring just above TOP (dry, bin < 0)
                pixels.append((FLOOR + r * CONE_SLOPE, PIXEL_M**2))
    return pixels


def trough_pixels() -> list[tuple[float, float]]:
    """30 m grid across a V-trough; every row along the valley is identical."""
    half_width = (TOP - FLOOR) / TROUGH_SLOPE
    rows = round(TROUGH_LENGTH / PIXEL_M)
    pixels = []
    x = -half_width - PIXEL_M / 2
    while x <= half_width + PIXEL_M:
        pixels += [(FLOOR + abs(x) * TROUGH_SLOPE, PIXEL_M**2)] * rows
        x += PIXEL_M
    return pixels


def test_cone_curve_from_pixels_matches_geometry() -> None:
    curve = v.curve_from_bins(v.bin_sums(cone_pixels(), TOP, STEP), TOP, STEP, "cone")
    assert curve.levels_m[0] < FLOOR + STEP and curve.areas_km2[0] == 0
    assert curve.top_level_m == TOP
    # 30 m pixels on a 6 km-radius cone: the disc is resolved to well within 0.5%.
    assert curve.top_area_km2 == pytest.approx(cone_area_km2(TOP - FLOOR), rel=5e-3)
    assert curve.top_volume_mcm == pytest.approx(cone_volume_mcm(TOP - FLOOR), rel=5e-3)
    # Halfway up: smaller disc, coarser relative pixelation → 2%.
    mid = FLOOR + 36
    assert curve.volume_at_level(mid) == pytest.approx(cone_volume_mcm(36), rel=2e-2)


def test_trough_curve_from_pixels_matches_geometry() -> None:
    curve = v.curve_from_bins(v.bin_sums(trough_pixels(), TOP, STEP), TOP, STEP, "trough")
    # Width is quantised to whole pixels: allow one 30 m column along the valley, i.e.
    # L·30 m of area and L·30 m·h of volume (2% of the width at 20 m depth, <1% at FSL).
    for depth in (20.0, 50.0, TOP - FLOOR):
        h = FLOOR + depth
        column_km2 = TROUGH_LENGTH * PIXEL_M / 1e6
        assert abs(curve.area_at_level(h) - trough_area_km2(depth)) <= column_km2
        assert abs(curve.volume_at_level(h) - trough_volume_mcm(depth)) <= column_km2 * depth


def test_volume_is_exact_sum_over_pixels() -> None:
    # Hand-checkable: 3 pixels of 100 m² at 10.0, 10.2, 11.0 m; top 11, step 0.5.
    pixels = [(10.0, 100.0), (10.2, 100.0), (11.0, 100.0), (11.3, 100.0)]
    bins = v.bin_sums(pixels, 11.0, 0.5)
    assert bins == [
        (-1, 100.0, pytest.approx(-30.0)),
        (0, 100.0, 0.0),
        (1, 100.0, pytest.approx(80.0)),
        (2, 100.0, pytest.approx(100.0)),
    ]
    curve = v.curve_from_bins(bins, 11.0, 0.5, "hand")
    assert curve.levels_m == (9.5, 10.0, 10.5, 11.0)
    assert curve.areas_km2 == pytest.approx((0, 100e-6, 200e-6, 300e-6))
    # At 10.5: (0.5 + 0.3) × 100 = 80 m³. At 11.0: (1.0 + 0.8 + 0) × 100 = 180 m³.
    assert curve.volumes_mcm == pytest.approx((0, 0, 80e-6, 180e-6))


def test_curve_ignores_pixels_above_top_and_needs_some_below() -> None:
    with pytest.raises(ValueError, match="No pixels"):
        v.curve_from_bins([(-3, 1.0, -1.0)], 912, 0.5, "dry")
    with pytest.raises(ValueError, match="step"):
        v.curve_from_bins([(0, 1.0, 0.0)], 912, 0, "x")


def test_bin_index() -> None:
    assert v.bin_index(912.0, 912, 0.5) == 0
    assert v.bin_index(911.5, 912, 0.5) == 1
    assert v.bin_index(911.49, 912, 0.5) == 1
    assert v.bin_index(911.51, 912, 0.5) == 0
    assert v.bin_index(912.01, 912, 0.5) == -1


# --- CSV --------------------------------------------------------------------------------


def test_csv_round_trip(tmp_path: Path, cone: v.AEVCurve, trough: v.AEVCurve) -> None:
    path = tmp_path / "baseline" / "aev.csv"
    v.write_aev_csv(path, [cone, trough])
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "level_m_asl,area_km2,volume_mcm,dem_source"
    curves = v.read_aev_csv(path)
    assert list(curves) == ["cone", "trough"]
    back = curves["cone"]
    assert back.levels_m == cone.levels_m
    assert back.areas_km2 == pytest.approx(cone.areas_km2, abs=5e-5)
    assert back.volumes_mcm == pytest.approx(cone.volumes_mcm, abs=5e-5)


def test_csv_wrong_header_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("level,area,volume\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected columns"):
        v.read_aev_csv(path)


def test_percent_difference() -> None:
    assert v.percent_difference(743.4, 688) == pytest.approx(8.05, abs=0.01)
    assert v.percent_difference(681, 825) == pytest.approx(-17.45, abs=0.01)
