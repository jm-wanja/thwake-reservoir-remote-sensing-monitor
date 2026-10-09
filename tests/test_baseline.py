"""Offline tests for the AOI / max-extent step.

The Earth Engine parts (EarthEngineFill, build_extent) need an authenticated session and
are not run here; they are checked by running `thwake baseline --step extent` and the
notebook notebooks/01_aoi_max_extent.ipynb.
"""

import copy
import json
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Polygon, box

from thwake import baseline as b
from thwake.config import REPO_ROOT, Config, ConfigError, load_config

OFFICIAL = REPO_ROOT / "data" / "external" / "official_figures.csv"


@pytest.fixture
def cfg() -> Config:
    return load_config(env_file=REPO_ROOT / "does-not-exist.env")


def with_changes(cfg: Config, file: str, section: str, **changes: object) -> Config:
    files = copy.deepcopy(cfg.files)
    files[file][section].update(changes)
    return Config(files=files, env=cfg.env, config_dir=cfg.config_dir)


# --- Settings ---------------------------------------------------------------------------


def test_repository_settings_load(cfg: Config) -> None:
    s = b.extent_settings(cfg)
    assert s.fsl_m == 912
    assert s.aoi_level_m == 917
    assert len(s.wall_axis) == 2
    assert all(-2 < lat < -1.5 and 37.5 < lon < 38 for lon, lat in s.wall_axis)
    assert s.max_extent_path == REPO_ROOT / "data" / "baseline" / "max_extent.geojson"
    assert s.aoi_path == REPO_ROOT / "data" / "baseline" / "aoi.geojson"


def test_repository_wall_axis_matches_official_crest_length(cfg: Config) -> None:
    # ESIA 2025: crest 1,500 m (axis 1,560 m). Digitised ends should be within ~10%.
    length = b.line_length_m(b.extent_settings(cfg).wall_axis)
    assert 1350 < length < 1700


def test_missing_wall_axis_raises(cfg: Config) -> None:
    with pytest.raises(ConfigError, match="wall_axis"):
        b.extent_settings(with_changes(cfg, "settings", "dam", wall_axis=None))


def test_single_point_wall_axis_raises(cfg: Config) -> None:
    bad = with_changes(cfg, "settings", "dam", wall_axis=[{"lat": -1.79, "lon": 37.84}])
    with pytest.raises(ConfigError, match="two points"):
        b.extent_settings(bad)


def test_out_of_range_point_raises(cfg: Config) -> None:
    bad = with_changes(cfg, "settings", "dam", reservoir_seed={"lat": 95, "lon": 37.8})
    with pytest.raises(ConfigError, match="out of range"):
        b.extent_settings(bad)


@pytest.mark.parametrize("value", [0, -5, "five", True])
def test_bad_margin_raises(cfg: Config, value: object) -> None:
    bad = with_changes(cfg, "thresholds", "baseline", aoi_buffer_above_fsl_m=value)
    with pytest.raises(ConfigError, match="aoi_buffer_above_fsl_m"):
        b.extent_settings(bad)


# --- Geometry ---------------------------------------------------------------------------


def test_extend_line_adds_length_at_both_ends() -> None:
    line = [(37.84005, -1.79363), (37.85021, -1.78505)]
    extended = b.extend_line(line, 300)
    assert len(extended) == 4
    assert extended[1:3] == line
    assert b.line_length_m(extended) == pytest.approx(b.line_length_m(line) + 600, abs=0.5)
    # Extensions continue in the same direction (collinear within a few cm).
    az_line, _, _ = b.GEOD.inv(*line[0], *line[1])
    az_start, _, _ = b.GEOD.inv(*extended[0], *extended[1])
    assert az_start == pytest.approx(az_line, abs=0.01)


def test_extend_line_zero_is_identity() -> None:
    line = [(37.0, -1.0), (37.1, -1.1)]
    assert b.extend_line(line, 0) == line


def test_extend_line_needs_two_points() -> None:
    with pytest.raises(ValueError):
        b.extend_line([(37.0, -1.0)], 10)


def test_search_bounds_extend_radius_each_way() -> None:
    center = (37.845, -1.789)
    west, south, east, north = b.search_bounds(center, 20)
    assert b.GEOD.inv(*center, center[0], north)[2] == pytest.approx(20_000, rel=1e-6)
    assert b.GEOD.inv(*center, east, center[1])[2] == pytest.approx(20_000, rel=1e-3)
    assert west < center[0] < east and south < center[1] < north


def test_midpoint_is_equidistant() -> None:
    a, c = (37.84005, -1.79363), (37.85021, -1.78505)
    m = b.midpoint(a, c)
    assert b.GEOD.inv(*a, *m)[2] == pytest.approx(b.GEOD.inv(*m, *c)[2], abs=0.01)


def test_area_km2_of_one_km_square() -> None:
    lon0, lat0 = 37.8, -1.8
    east = b.GEOD.fwd(lon0, lat0, 90, 1000)[0]
    north = b.GEOD.fwd(lon0, lat0, 0, 1000)[1]
    square = box(lon0, lat0, east, north)
    assert b.area_km2(square) == pytest.approx(1.0, rel=1e-3)
    # Orientation and holes are handled.
    assert b.area_km2(shapely.geometry.polygon.orient(square, -1)) == pytest.approx(1.0, rel=1e-3)
    holed = Polygon(square.exterior, [box(37.801, -1.799, 37.802, -1.798).exterior])
    assert b.area_km2(holed) < b.area_km2(square)


def test_fill_holes_removes_islands() -> None:
    holed = Polygon(box(0, 0, 10, 10).exterior, [box(4, 4, 6, 6).exterior])
    filled = b.fill_holes(holed)
    assert filled.area == 100
    assert len(filled.interiors) == 0


def test_fill_holes_multipolygon() -> None:
    parts = shapely.MultiPolygon(
        [Polygon(box(0, 0, 4, 4).exterior, [box(1, 1, 2, 2).exterior]), box(10, 10, 11, 11)]
    )
    assert b.fill_holes(parts).area == 17


def test_polygonal_repairs_bowtie_and_drops_lines() -> None:
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid
    fixed = b.polygonal(bowtie)
    assert fixed.is_valid and fixed.area == pytest.approx(2)
    mixed = shapely.GeometryCollection([box(0, 0, 1, 1), shapely.LineString([(5, 5), (6, 6)])])
    assert b.polygonal(mixed).geom_type == "Polygon"


def test_check_inside() -> None:
    bounds = (37.6, -2.0, 38.0, -1.6)
    b.check_inside(box(37.7, -1.9, 37.9, -1.7), bounds, "inner")
    with pytest.raises(b.BaselineError, match="edge"):
        b.check_inside(box(37.6, -1.9, 37.9, -1.7), bounds, "touching")


def test_check_excludes() -> None:
    geom = box(0, 0, 1, 1)
    b.check_excludes(geom, (2, 2), "x")
    with pytest.raises(b.BaselineError, match="downstream"):
        b.check_excludes(geom, (0.5, 0.5), "x")


# --- Pass search ------------------------------------------------------------------------


def test_bisect_level_finds_threshold() -> None:
    below, above = b.bisect_level(lambda h: h >= 913.37, 912, 917, 0.1)
    assert below < 913.37 <= above
    assert above - below <= 0.1


class FakeRim:
    """Reservoir with rim passes at given levels; a pass leaks once the level reaches it."""

    def __init__(self, passes: dict[tuple[float, float], float]):
        self.passes = passes

    def _open(self, level: float, closures: list[b.PassClosure]) -> list[tuple[float, float]]:
        closed = {(c.lon, c.lat) for c in closures}
        return [p for p, h in self.passes.items() if h <= level and p not in closed]

    def leaks(self, level: float, closures: list[b.PassClosure]) -> bool:
        return bool(self._open(level, closures))

    def locate(self, below: float, above: float, closures: list[b.PassClosure]):
        return [p for p in self._open(above, closures) if self.passes[p] > below]


def test_close_passes_lowest_first() -> None:
    rim = FakeRim({(37.83, -1.80): 912.95, (37.85, -1.78): 915.2, (37.9, -1.7): 918.0})
    closures = b.close_passes(rim.leaks, rim.locate, 912, 917, 0.1, 10)
    assert [(c.lon, c.lat) for c in closures] == [(37.83, -1.80), (37.85, -1.78)]
    assert closures[0].overflow_level_m == pytest.approx(912.95, abs=0.1)
    assert closures[1].overflow_level_m == pytest.approx(915.2, abs=0.1)
    assert not rim.leaks(917, closures)


def test_close_passes_none_needed() -> None:
    rim = FakeRim({(37.9, -1.7): 920.0})
    assert b.close_passes(rim.leaks, rim.locate, 912, 917, 0.1, 10) == []


def test_close_passes_gives_up() -> None:
    rim = FakeRim({(37.0 + i / 100, -1.8): 912.5 + i / 10 for i in range(5)})
    with pytest.raises(b.BaselineError, match="max_pass_closures"):
        b.close_passes(rim.leaks, rim.locate, 912, 917, 0.1, 3)


def test_close_passes_unlocated_pass_raises() -> None:
    rim = FakeRim({(37.83, -1.80): 913.0})
    with pytest.raises(b.BaselineError, match="no pass found"):
        b.close_passes(rim.leaks, lambda *_: [], 912, 917, 0.1, 10)


# --- Provenance and output --------------------------------------------------------------


def test_fsl_from_official_figures_is_not_fallback() -> None:
    rows = b.read_official_figures(OFFICIAL)
    prov = b.fsl_provenance(912, rows)
    assert prov["fsl_is_fallback"] is False
    assert prov["fsl_sources"]


def test_unsourced_fsl_is_flagged_as_fallback() -> None:
    prov = b.fsl_provenance(900, b.read_official_figures(OFFICIAL))
    assert prov["fsl_is_fallback"] is True
    assert "FALLBACK" in prov["fsl_note"]


def test_official_area() -> None:
    area = b.official_area(b.read_official_figures(OFFICIAL))
    assert area is not None
    assert area["official_area_km2"] == 29
    assert b.official_area([]) is None


def test_feature_collection_round_trip(tmp_path: Path) -> None:
    geom = box(37.123456789, -1.987654321, 37.2, -1.9)
    fc = b.feature_collection(geom, {"name": "test", "area_km2": 1.5})
    path = tmp_path / "out" / "test.geojson"
    b.write_geojson(path, fc)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    feature = loaded["features"][0]
    assert feature["properties"] == {"name": "test", "area_km2": 1.5}
    xs = [x for x, _ in feature["geometry"]["coordinates"][0]]
    assert all(round(x, 6) == x for x in xs)
    loaded_geom = shapely.geometry.shape(feature["geometry"]).normalize()
    assert loaded_geom.equals_exact(geom.normalize(), 1e-6)


def test_pass_closure_as_dict() -> None:
    c = b.PassClosure(37.829171234, -1.796671234, 912.9876)
    assert c.as_dict() == {"lat": -1.79667, "lon": 37.82917, "overflow_level_m_asl": 913.0}
