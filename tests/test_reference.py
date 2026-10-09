"""Offline tests for the pre-filling reference layers (land cover, composite, river channel).

The Earth Engine parts (build_landcover, build_river, build_composite) need an authenticated
session and are not run here; they are checked by running `thwake baseline --step landcover`,
`--step river` and `--step composite`.
"""

import copy
import csv
import datetime as dt
from pathlib import Path

import pytest
from shapely.geometry import box

from thwake import baseline as b
from thwake import reference as r
from thwake.config import REPO_ROOT, Config, ConfigError, load_config

BASELINE_DIR = REPO_ROOT / "data" / "baseline"
MEDIA_DIR = REPO_ROOT / "media"


@pytest.fixture
def cfg() -> Config:
    return load_config(env_file=REPO_ROOT / "does-not-exist.env")


def with_changes(cfg: Config, file: str, section: str, **changes: object) -> Config:
    files = copy.deepcopy(cfg.files)
    files[file][section].update(changes)
    return Config(files=files, env=cfg.env, config_dir=cfg.config_dir)


# --- Settings ---------------------------------------------------------------------------


def test_repository_settings_load(cfg: Config) -> None:
    s = r.reference_settings(cfg)
    assert s.window == "2026-06-01/2026-10-01"
    assert 0 < s.cs_min < 1
    assert {"B2", "B3", "B4"} <= set(s.bands)
    assert s.landcover_path == BASELINE_DIR / "landcover_flood_zone.csv"
    assert s.landcover_metadata_path == BASELINE_DIR / "landcover_flood_zone.json"
    assert s.river_path == BASELINE_DIR / "river_channel.geojson"
    assert s.png_path == MEDIA_DIR / "before_composite.png"
    assert s.asset_id.startswith(cfg.settings["earth_engine"]["assets_folder"] + "/")
    assert s.asset_id.endswith("_v1")


def test_window_after_construction_and_before_impoundment_target(cfg: Config) -> None:
    # Pre-filling means after the dam was built (2018) and before the gates close
    # (target end of January 2027, open question 5).
    s = r.reference_settings(cfg)
    assert s.window_start > cfg.settings["dates"]["construction_start"].isoformat()
    assert s.window_end <= "2027-01-31"


def test_window_must_end_before_impoundment(cfg: Config) -> None:
    bad = with_changes(cfg, "settings", "dates", impoundment_start=dt.date(2026, 8, 1))
    with pytest.raises(ConfigError, match="after impoundment"):
        r.reference_settings(bad)


def test_window_before_impoundment_is_fine(cfg: Config) -> None:
    ok = with_changes(cfg, "settings", "dates", impoundment_start="2027-01-31")
    assert r.reference_settings(ok).window_end == "2026-10-01"


@pytest.mark.parametrize(
    "window, match",
    [
        ({"start": "2026-10-01", "end": "2026-06-01"}, "before it starts"),
        ({"start": "June", "end": "2026-10-01"}, "YYYY-MM-DD"),
        ("2026-06-01/2026-10-01", "'start' and 'end'"),
    ],
)
def test_bad_window_raises(cfg: Config, window: object, match: str) -> None:
    bad = with_changes(cfg, "settings", "dates", pre_filling_window=window)
    with pytest.raises(ConfigError, match=match):
        r.reference_settings(bad)


def test_composite_needs_true_colour_bands(cfg: Config) -> None:
    bad = with_changes(cfg, "thresholds", "baseline", composite_bands=["B8", "B11"])
    with pytest.raises(ConfigError, match="true-colour"):
        r.reference_settings(bad)


@pytest.mark.parametrize(
    "key, value",
    [
        ("composite_cloud_score_min", 1.5),
        ("river_occurrence_min_pct", 150),
        ("river_occurrence_sensitivity_pct", "25"),
        ("river_occurrence_sensitivity_pct", [25, "fifty"]),
    ],
)
def test_bad_thresholds_raise(cfg: Config, key: str, value: object) -> None:
    bad = with_changes(cfg, "thresholds", "baseline", **{key: value})
    with pytest.raises(ConfigError):
        r.reference_settings(bad)


# --- Class tables and area rows ---------------------------------------------------------


def test_worldcover_classes_map_to_dynamic_world() -> None:
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
    names = ["Tree cover", "Shrubland", "Grassland", "Cropland", "Built-up", "Bare", "Snow"]
    names += ["Permanent water bodies", "Herbaceous wetland", "Mangroves", "Moss and lichen"]
    classes = r.worldcover_classes(values, names)
    assert classes[40] == ("Cropland", "crops")
    assert classes[80] == ("Permanent water bodies", "water")
    assert {common for _, common in classes.values()} <= set(r.DW_CLASSES)


def test_worldcover_unknown_class_raises() -> None:
    with pytest.raises(b.BaselineError, match="no Dynamic World equivalent"):
        r.worldcover_classes([10, 99], ["Tree cover", "New class"])


def test_dynamic_world_classes_follow_label_order() -> None:
    classes = r.dynamic_world_classes()
    assert classes[0] == ("water", "water")
    assert classes[4] == ("crops", "crops")
    assert len(classes) == 9


def test_class_area_rows_convert_and_skip_empty() -> None:
    classes = {10: ("Tree cover", "trees"), 40: ("Cropland", "crops"), 80: ("Water", "water")}
    rows = r.class_area_rows(
        "esa_worldcover", "ESA/WorldCover/v200", "2021-01-01/2022-01-01", classes,
        {40: 2_500_000.0, 10: 500_000.0, 80: 0.0}, 3_000_000.0,
    )  # fmt: skip
    assert [row["class_value"] for row in rows] == [10, 40]
    assert rows[1]["area_ha"] == 250.0
    assert rows[1]["area_pct"] == pytest.approx(83.33)
    assert set(rows[0]) == set(r.LANDCOVER_COLUMNS)


def test_class_area_rows_reject_unknown_class_and_source() -> None:
    classes = {10: ("Tree cover", "trees")}
    with pytest.raises(b.BaselineError, match=r"\[20\]"):
        r.class_area_rows("esa_worldcover", "c", "p", classes, {20: 1.0}, 1.0)
    with pytest.raises(ValueError, match="Unknown"):
        r.class_area_rows("modis", "c", "p", classes, {10: 1.0}, 1.0)


def rows_for(source: str, hectares: dict[str, float]) -> list[dict]:
    return [
        {"source": source, "common_class": c, "area_ha": ha, "class_value": i}
        for i, (c, ha) in enumerate(hectares.items())
    ]


def test_check_area_totals_passes_within_tolerance() -> None:
    rows = rows_for("esa_worldcover", {"trees": 1000.0, "crops": 2030.0})
    rows += rows_for("dynamic_world_mode", {"trees": 1500.0, "crops": 1540.0})
    totals = r.check_area_totals(rows, 30.36, 2)
    assert totals == {"esa_worldcover": 30.3, "dynamic_world_mode": 30.4}


def test_check_area_totals_flags_gaps() -> None:
    rows = rows_for("dynamic_world_mode", {"trees": 1000.0, "crops": 1000.0})
    with pytest.raises(b.BaselineError, match="dynamic_world_mode"):
        r.check_area_totals(rows, 30.36, 2)


def test_common_class_table_fills_missing_and_sorts_by_worldcover() -> None:
    rows = rows_for("esa_worldcover", {"crops": 800.0, "shrub_and_scrub": 1200.0})
    rows += rows_for("dynamic_world_mode", {"crops": 900.0, "bare": 50.0})
    table = r.common_class_table(rows)
    assert list(table) == ["shrub_and_scrub", "crops", "bare"]
    assert table["crops"] == {"esa_worldcover": 800.0, "dynamic_world_mode": 900.0}
    assert table["bare"]["esa_worldcover"] == 0.0


def test_write_landcover_csv_round_trip(tmp_path: Path) -> None:
    rows = r.class_area_rows(
        "dynamic_world_mode", "GOOGLE/DYNAMICWORLD/V1", "2026-06-01/2026-10-01",
        r.dynamic_world_classes(), {4: 1e6, 5: 2e6}, 3e6,
    )  # fmt: skip
    path = tmp_path / "lc.csv"
    r.write_landcover_csv(path, rows)
    with path.open(newline="", encoding="utf-8") as f:
        read = list(csv.DictReader(f))
    assert tuple(read[0]) == r.LANDCOVER_COLUMNS
    assert read[1]["class_name"] == "shrub_and_scrub" and read[1]["area_ha"] == "200.0"


# --- Other helpers ----------------------------------------------------------------------


def test_sensitivity_levels_sorted_unique() -> None:
    assert r.sensitivity_levels(10, [50, 5, 10, 25]) == [5.0, 10.0, 25.0, 50.0]


def test_check_size(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(b"x" * 100)
    assert r.check_size(path) == 100
    with pytest.raises(b.BaselineError, match="budget"):
        r.check_size(path, max_bytes=10)


def test_load_feature_missing_file_points_to_extent_step(tmp_path: Path) -> None:
    with pytest.raises(b.BaselineError, match="--step extent"):
        r.load_feature(tmp_path / "aoi.geojson")


def test_load_feature_reads_geometry_and_properties(tmp_path: Path) -> None:
    path = tmp_path / "zone.geojson"
    b.write_geojson(path, b.feature_collection(box(37.8, -1.8, 37.81, -1.79), {"level": 912}))
    geom, props = r.load_feature(path)
    assert props == {"level": 912}
    assert geom.bounds == pytest.approx((37.8, -1.8, 37.81, -1.79))


# --- Summaries --------------------------------------------------------------------------


def test_landcover_summary() -> None:
    rows = rows_for("esa_worldcover", {"shrub_and_scrub": 1182.2, "crops": 853.8})
    meta = {
        "zone": {"area_km2": 30.36},
        "worldcover": {"period": "2021-01-01/2021-12-31"},
        "dynamic_world": {"window": "2026-06-01/2026-10-01", "scenes": 18},
        "by_common_class_ha": r.common_class_table(rows),
        "totals_km2": {"esa_worldcover": 20.36},
    }
    text = r.landcover_summary(r.LandcoverResult(rows, meta, BASELINE_DIR / "lc.csv", Path()))
    assert "18 scenes" in text and "1182.2" in text and "WorldCover 20.36" in text


def test_river_summary() -> None:
    props = {
        "occurrence_min_pct": 10.0,
        "area_km2": 0.355,
        "polygons": 50,
        "area_in_max_extent_km2": 0.2,
        "max_occurrence_in_aoi_pct": 60,
        "sensitivity_area_km2_by_occurrence_pct": {"5": 0.428, "10": 0.355, "50": 0.017},
        "ever_water_area_km2": 0.467,
    }
    collection = b.feature_collection(box(0, 0, 1, 1), props)
    text = r.river_summary(r.RiverResult(collection, BASELINE_DIR / "river_channel.geojson"))
    assert "0.355 km² in 50 pieces" in text and "≥50%: 0.017" in text


def test_composite_summary() -> None:
    meta = {
        "granules": 74,
        "acquisition_dates": 25,
        "first_image": "2026-06-02",
        "last_image": "2026-09-30",
        "tiles": ["37MCU"],
        "cloud_score_min": 0.6,
        "clear_obs_per_pixel": {"min": 20, "p5": 25, "median": 31},
        "window": "2026-06-01/2026-10-01",
        "chirps_rain_in_window": {"mean_over_aoi_mm": 4.2, "days_available": 122, "last_day": "x"},
        "png": {"path": "media/before_composite.png"},
        "asset_id": "projects/p/assets/a",
        "export_task_id": "TASK",
    }
    text = r.composite_summary(r.CompositeResult(meta, Path(), BASELINE_DIR / "c.json"))
    assert (
        "74 Sentinel-2 granules on 25 dates, 2026-06-02 to 2026-09-30" in text and "4.2 mm" in text
    )


# --- Committed outputs ------------------------------------------------------------------


@pytest.mark.parametrize("folder", [BASELINE_DIR, MEDIA_DIR])
def test_committed_outputs_are_within_size_budget(folder: Path) -> None:
    for path in folder.iterdir():
        if path.is_file():
            assert path.stat().st_size <= r.MAX_OUTPUT_BYTES, path.name
