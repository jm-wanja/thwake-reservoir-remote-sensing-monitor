"""Offline tests for the reference-reservoir validation (prompt 05a).

The Earth Engine stage (build_reference) needs an authenticated session and is checked by
running `thwake validate reference --name masinga`; the comparison stage is tested here end
to end on synthetic files.
"""

import copy
import csv
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from thwake import validation as v
from thwake import volume, water_s1, water_s2
from thwake.config import REPO_ROOT, Config, ConfigError, load_config


@pytest.fixture
def cfg() -> Config:
    return load_config(env_file=REPO_ROOT / "does-not-exist.env")


def changed(cfg: Config, file: str, path: list[str], **changes: object) -> Config:
    files = copy.deepcopy(cfg.files)
    section = files[file]
    for key in path:
        section = section[key]
    section.update(changes)
    return Config(files=files, env=cfg.env, config_dir=cfg.config_dir)


def level(
    day: str, value: float, confidence: str = "high", end: str | None = None
) -> v.PublishedLevel:
    d0 = date.fromisoformat(day)
    return v.PublishedLevel(
        d0, date.fromisoformat(end) if end else d0, value, confidence, "published"
    )


def scene(day: str, sensor: str, area: float, valid: float = 1.0, flag: str = "ok") -> v.SceneArea:
    return v.SceneArea(
        date.fromisoformat(day),
        sensor,
        "",
        f"id-{day}",
        1,
        valid,
        0.0,
        "otsu",
        area,
        area - 1,
        area + 1,
        flag,
    )


# A post-dam DEM: flat lake surface at 1004 m covering 50 km², then 5 km² per metre.
LEVELS = tuple(float(h) for h in range(1000, 1011))
AREAS = (0.0, 0.1, 0.2, 0.3, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0)
VOLUMES = tuple(float(i * i) for i in range(11))
CURVE = volume.AEVCurve(LEVELS, AREAS, VOLUMES, "copernicus_glo30")
SURFACE = v.WaterSurface("copernicus_glo30", 1004.0, 50.0, 0.6)


# --- Settings ---------------------------------------------------------------------------


def test_repository_settings_load(cfg: Config) -> None:
    s = v.reference_settings(cfg, "masinga")
    assert s.fsl_m == 1056.5 and s.mask_level_m >= s.fsl_m
    assert len(s.closure_axis) >= 2
    assert s.altimetry_path is not None and s.altimetry_path.parent.name == "dahiti"
    assert "not gauge ground truth" in s.altimetry_label
    assert "10.5194/hess-19-4345-2015" in s.altimetry_citation
    assert s.rapid_change_m_per_day > 0
    assert s.paths["figure"] == REPO_ROOT / "media" / "validation_reference.png"
    assert s.paths["scenes"].name == "reference_masinga_scenes.csv"
    assert v.reference_names(cfg) == ["masinga"]


def test_unknown_reservoir_is_rejected(cfg: Config) -> None:
    with pytest.raises(ConfigError, match="Unknown reference reservoir"):
        v.reference_settings(cfg, "kariba")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"mask_level_m_asl": 1050}, "at or above the FSL"),
        ({"scene_window": {"start": "2026-01-01", "end": "2025-01-01"}}, "end after"),
        ({"closure_axis": [{"lat": 0, "lon": 37}]}, "at least two"),
        ({"scene_window": {"start": "soon", "end": "2026-01-01"}}, "ISO date"),
    ],
)
def test_bad_settings_are_rejected(cfg: Config, changes: dict, message: str) -> None:
    bad = changed(cfg, "validation", ["reference_reservoirs", "masinga"], **changes)
    with pytest.raises(ConfigError, match=message):
        v.reference_settings(bad, "masinga")


def test_extent_inputs_keep_thwake_fill_parameters(cfg: Config) -> None:
    s = v.reference_settings(cfg, "masinga")
    e = v.extent_inputs(cfg, s)
    assert e.wall_axis == s.closure_axis and e.seed == s.seed
    assert e.aoi_level_m == s.mask_level_m
    assert e.barrier_half_width_m == cfg.thresholds["baseline"]["wall_barrier_half_width_m"]


def test_sensor_settings_load_and_validate(cfg: Config) -> None:
    s2, s1 = water_s2.s2_settings(cfg), water_s1.s1_settings(cfg)
    assert s2.cloud_score_min == 0.6 and len(s2.bins) == 200
    assert s1.fixed_threshold_db == -18.0 and len(s1.bins) == 400
    bad = changed(cfg, "thresholds", ["sentinel1"], speckle_filter="refined_lee")
    with pytest.raises(ConfigError, match="speckle_filter"):
        water_s1.s1_settings(bad)
    bad = changed(cfg, "thresholds", ["sentinel2"], otsu_valid_range=[0.5, -0.5])
    with pytest.raises(ConfigError, match="low < high"):
        water_s2.s2_settings(bad)
    bad = changed(cfg, "thresholds", ["sentinel2"], water_index="NDWI")
    with pytest.raises(ConfigError, match="MNDWI"):
        water_s2.s2_settings(bad)


# --- Published figures ------------------------------------------------------------------


def test_parse_value_date() -> None:
    assert v.parse_value_date("2024-05-02") == (date(2024, 5, 2), date(2024, 5, 2))
    assert v.parse_value_date("2025-05-21/2025-05-28") == (date(2025, 5, 21), date(2025, 5, 28))
    with pytest.raises(ValueError):
        v.parse_value_date("2025-05-28/2025-05-21")


def test_repository_published_figures_have_sources(cfg: Config) -> None:
    s = v.reference_settings(cfg, "masinga")
    rows = v.read_published(s.paths["published_figures"], "masinga")
    assert rows and all(r["source_url"].startswith("http") for r in rows)
    assert all(r["confidence"] in ("high", "medium", "low") for r in rows)
    inside, outside = v.published_levels(rows, s.scene_start, s.scene_end)
    assert len(inside) >= 4 and all(p.start.year >= 2023 for p in inside)
    assert [p.start.year for p in outside] == [2009]
    assert any(not p.headline for p in inside)  # the rounded Feb 2024 level


def test_published_level_properties() -> None:
    p = level("2025-05-21", 1056.97, "medium", end="2025-05-27")
    assert p.headline and p.mid == date(2025, 5, 24)
    assert p.label == "2025-05-21/2025-05-27"
    assert not level("2024-02-05", 1056, "low").headline


def test_published_item_reads_constants(tmp_path: Path) -> None:
    path = tmp_path / "ref.csv"
    path.write_text(
        "reservoir,item,value,unit,value_date,source_url,source_date,confidence,notes\n"
        "x,surface_area_at_fsl,120,km2,,https://a,2026,low,\n"
        "y,surface_area_at_fsl,99,km2,,https://b,2026,low,\n",
        encoding="utf-8",
    )
    items = v.published_item(v.read_published(path, "x"), "surface_area_at_fsl")
    assert items == [
        {"value": 120.0, "unit": "km2", "confidence": "low", "source_url": "https://a"}
    ]
    with pytest.raises(v.ValidationError):
        v.read_published(tmp_path / "missing.csv", "x")


def test_read_altimetry_plain_csv(tmp_path: Path) -> None:
    path = tmp_path / "alt.csv"
    path.write_text("date,level_m,level_error_m\n2024-03-01,1050.2,0.3\n2024-01-01,1048,0.4\n")
    series = v.read_altimetry(path)
    assert [p.start for p in series] == [date(2024, 1, 1), date(2024, 3, 1)]
    assert all(p.source == "altimetry" and not p.headline for p in series)
    assert series[0].error_m == 0.4
    path.write_text("day,height\n")
    with pytest.raises(v.ValidationError, match="expected columns"):
        v.read_altimetry(path)


def test_read_altimetry_dahiti_download(tmp_path: Path) -> None:
    path = tmp_path / "dahiti.csv"
    path.write_text(
        "datetime;wse;wse_u\n2019-01-24 07:29:46;1051.402;0.001\n"
        "2018-12-28 07:29:44;1052.389;0.003\n\n"
    )
    series = v.read_altimetry(path)
    assert [(p.start, p.level_m, p.error_m) for p in series] == [
        (date(2018, 12, 28), 1052.389, 0.003),
        (date(2019, 1, 24), 1051.402, 0.001),
    ]
    with pytest.raises(v.ValidationError):
        v.read_altimetry(tmp_path / "missing.csv")


def test_change_rate_takes_fastest_overlapping_segment() -> None:
    series = [level("2023-10-01", 1040.0), level("2023-10-28", 1041.0), level("2023-11-24", 1052.0)]
    # Segment Oct 28 → Nov 24 rises 11 m in 27 days.
    assert v.change_rate(series, date(2023, 11, 20), date(2023, 11, 20), 6) == pytest.approx(
        11 / 27
    )
    assert v.change_rate(series, date(2023, 10, 5), date(2023, 10, 5), 6) == pytest.approx(1 / 27)
    assert v.change_rate(series, date(2024, 6, 1), date(2024, 6, 1), 6) is None


def test_cross_check_pairs_gauge_with_nearest_altimetry() -> None:
    gauge = [level("2025-12-08", 1054.49), level("2025-05-21", 1056.97, "medium", end="2025-05-28")]
    alt = [level("2025-12-09", 1055.0), level("2025-12-30", 1054.0), level("2025-06-03", 1057.4)]
    rows = v.cross_check(gauge, alt, 6)
    assert [(r["altimetry_date"], r["gap_days"], r["difference_m"]) for r in rows] == [
        ("2025-12-09", 1, 0.51),
        ("2025-06-03", 6, 0.43),
    ]
    assert v.cross_check(gauge, alt, 0) == []


def test_eecu_seconds_sums_first_column() -> None:
    text = (
        " EECU·s PeakMem Count  Description\n  0.072     47k    44  (plumbing)\n"
        "  1.500    124k    14  Algorithm Image.reduceRegion\n   -        59k    12  Loading\n"
    )
    assert v.eecu_seconds(text) == pytest.approx(1.572)
    assert v.eecu_seconds("") == 0


# --- DEM water surface and area → level -------------------------------------------------


def test_water_surface_needs_a_large_flat_share() -> None:
    flat = v.water_surface("srtm", 1046, 70.7, 135.4, 0.1)
    assert flat.level_m == 1046 and flat.share == pytest.approx(0.522, abs=1e-3)
    assert flat.convertible(1054.49) and not flat.convertible(1039.42)
    assert not flat.convertible(1046)
    none = v.water_surface("srtm", 1046, 5, 135.4, 0.1)
    assert none.level_m is None and none.convertible(900)


def test_level_from_area_above_surface() -> None:
    est = v.level_from_area(CURVE, 62.5, 60.0, 65.0, SURFACE)
    assert est.status == v.OK
    assert (est.best, est.low, est.high) == pytest.approx((1006.5, 1006.0, 1007.0))


def test_level_from_area_at_or_below_surface_is_not_estimated() -> None:
    for area in (50.0, 20.0):
        est = v.level_from_area(CURVE, area, area - 1, area + 1, SURFACE)
        assert est == v.LevelEstimate(None, None, None, v.BELOW_SURFACE)


def test_level_from_area_beyond_curve() -> None:
    est = v.level_from_area(CURVE, 85.0, 79.0, 90.0, SURFACE)
    assert est.status == v.ABOVE_CURVE and est.best is None
    assert est.low == pytest.approx(1009.8)


# --- Matching, comparison and metrics ---------------------------------------------------


def test_match_prefers_inside_interval_then_closest_then_coverage() -> None:
    target = level("2025-05-21", 1056.97, "medium", end="2025-05-28")
    scenes = [
        scene("2025-05-18", "S1", 100),
        scene("2025-05-25", "S1", 101, valid=0.8),
        scene("2025-05-26", "S1", 102, valid=0.95),
        scene("2025-05-24", "S2", 103, valid=0.5, flag="low_coverage"),
    ]
    best, gap = v.match_scene(target, scenes, "S1", 6)
    assert best is not None and best.area_km2 == 102 and gap == 0
    assert v.match_scene(target, scenes, "S2", 6) == (None, None)
    outside = level("2025-06-10", 1056.0)
    assert v.match_scene(outside, scenes, "S1", 6) == (None, None)
    best, gap = v.match_scene(level("2025-05-30", 1056.0), scenes, "S1", 6)
    assert best is not None and best.area_km2 == 102 and gap == 4


def test_comparison_rows_statuses() -> None:
    targets = [
        level("2024-01-10", 1006.4),  # convertible, matched
        level("2024-02-10", 1002.0),  # below the DEM water surface
        level("2024-03-10", 1007.0),  # no scene
        level("2024-04-10", 1008.0, "low"),  # low confidence
    ]
    scenes = [
        scene("2024-01-12", "S2", 62.5),
        scene("2024-02-10", "S2", 51.0),
        scene("2024-04-10", "S2", 70.0),
    ]
    rows = v.comparison_rows(
        targets, scenes, {"copernicus_glo30": CURVE}, {"copernicus_glo30": SURFACE}, 6
    )
    assert all(not r["rapid_change"] for r in rows)
    s2 = [r for r in rows if r["sensor"] == "S2"]
    assert [r["status"] for r in s2] == [v.OK, v.NOT_CONVERTIBLE, v.NO_SCENE, v.OK]
    assert s2[0]["difference_m"] == pytest.approx(0.1) and s2[0]["gap_days"] == 2
    assert s2[1]["level_m"] == pytest.approx(1004.2)  # informative only
    assert all(r["status"] == v.NO_SCENE for r in rows if r["sensor"] == "S1")

    summary = v.summarise(rows, "published")["S2/copernicus_glo30"]
    assert summary["absolute"]["n"] == 1
    assert summary["rows_by_status"] == {
        v.OK: 1,
        v.NOT_CONVERTIBLE: 1,
        v.NO_SCENE: 1,
        "low_confidence": 1,
    }


def test_absolute_metrics_split_bias_and_scatter() -> None:
    m = v.absolute_metrics([1.0, 2.0, 3.0])
    assert m["bias_m"] == 2.0 and m["sd_m"] == pytest.approx(0.82)
    assert m["rmse_m"] ** 2 == pytest.approx(m["bias_m"] ** 2 + m["sd_m"] ** 2, abs=0.05)
    assert m["max_abs_m"] == 3.0
    assert v.absolute_metrics([]) == {"n": 0}


def test_relative_metrics_cancel_a_constant_offset() -> None:
    pairs = [
        ("a", 1050.0, 1052.0, "s1"),
        ("b", 1054.0, 1056.0, "s2"),
        ("c", 1053.0, 1055.5, "s3"),
    ]
    m = v.relative_metrics(pairs)
    assert m["n"] == 2 and m["skipped_same_scene"] == 0
    assert [c["error_m"] for c in m["changes"]] == [0.0, 0.5]
    assert m["rmse_m"] == pytest.approx(0.35)
    assert v.relative_metrics(pairs[:1]) == {"n": 0, "changes": [], "skipped_same_scene": 0}


def test_relative_metrics_skip_dates_matched_to_one_scene() -> None:
    pairs = [("a", 1056.54, 1056.68, "s1"), ("b", 1057.43, 1056.68, "s1")]
    assert v.relative_metrics(pairs) == {"n": 0, "changes": [], "skipped_same_scene": 1}


def test_area_at_fsl_check_uses_scene_nearest_fsl() -> None:
    targets = [level("2024-01-10", 1006.4), level("2024-02-10", 1007.9)]
    scenes = [scene("2024-01-10", "S1", 62.0), scene("2024-02-10", "S1", 70.0)]
    rows = v.comparison_rows(
        targets, scenes, {"copernicus_glo30": CURVE}, {"copernicus_glo30": SURFACE}, 6
    )
    check = v.area_at_fsl_check(
        rows,
        [{"value": 80.0, "confidence": "low", "source_url": "u"}],
        {"copernicus_glo30": CURVE},
        1008.0,
    )
    assert check["measured_near_fsl"]["S1"]["published_date"] == "2024-02-10"
    assert "S2" not in check["measured_near_fsl"]
    assert check["comparisons"][0]["S1_pct_difference"] == -12.5
    assert check["comparisons"][0]["copernicus_glo30_curve_pct_difference"] == -12.5


def test_convertibility_table_lists_context_dates() -> None:
    table = v.convertibility_table(
        [level("2025-12-08", 1054.49)],
        [level("2009-06-26", 1035.5)],
        {
            "copernicus_glo30": v.WaterSurface("copernicus_glo30", 1054.5, 100, 0.7),
            "srtm": v.WaterSurface("srtm", 1046, 70, 0.5),
        },
    )
    assert [r["published_date"] for r in table] == ["2009-06-26", "2025-12-08"]
    assert table[1]["convertible_srtm"] and not table[1]["convertible_copernicus_glo30"]
    assert not table[0]["in_scene_window"]


def test_scenes_csv_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "s.csv"
    scenes = [scene("2024-01-02", "S1", 60.0), scene("2024-01-01", "S2", 61.5, 0.5, "low_coverage")]
    v.write_scenes_csv(path, scenes)
    back = v.read_scenes_csv(path)
    assert [s.date for s in back] == [date(2024, 1, 1), date(2024, 1, 2)]
    assert back[0].area_km2 == 61.5 and not back[0].usable
    with pytest.raises(v.ValidationError):
        v.read_scenes_csv(tmp_path / "none.csv")


def test_qa_flag() -> None:
    assert v.qa_flag(0.7, 0.7) == "ok" and v.qa_flag(0.69, 0.7) == "low_coverage"


# --- Comparison stage end to end --------------------------------------------------------


def test_compare_reference_end_to_end(cfg: Config, tmp_path: Path) -> None:
    paths = {
        k: str(tmp_path / f"{k}.out")
        for k in ("mask", "aev", "scenes", "scenes_metadata", "series", "comparison", "metrics")
    }
    paths["aev"] = str(tmp_path / "aev.csv")
    paths["figure"] = str(tmp_path / "figure.png")
    published = tmp_path / "published.csv"
    published.write_text(
        "reservoir,item,value,unit,value_date,source_url,source_date,confidence,notes\n"
        "masinga,water_level,1006.4,m a.s.l.,2024-01-10,https://a,2024,high,\n"
        "masinga,water_level,1007.2,m a.s.l.,2024-02-10,https://b,2024,medium,\n"
        "masinga,water_level,1008,m a.s.l.,2024-03-01/2024-03-03,https://c,2024,low,\n"
        "masinga,water_level,1001,m a.s.l.,2009-06-26,https://d,2009,high,\n"
        "masinga,surface_area_at_fsl,80,km2,,https://e,2026,low,\n",
        encoding="utf-8",
    )
    paths["published_figures"] = str(published)
    altimetry = tmp_path / "alt.csv"
    altimetry.write_text(
        "date,level_m,level_error_m\n2024-01-11,1006.0,0.3\n2024-02-09,1006.9,0.3\n"
    )
    c = changed(cfg, "validation", ["paths"], **paths)
    c = changed(
        c,
        "validation",
        ["reference_reservoirs", "masinga"],
        full_supply_level_m_asl=1008.0,
        mask_level_m_asl=1010.0,
        scene_window={"start": "2024-01-01", "end": "2024-04-01"},
        altimetry={"path": str(altimetry), "label": "test altimetry", "citation": "cite"},
    )
    srtm = volume.AEVCurve(LEVELS, AREAS, VOLUMES, "srtm")
    volume.write_aev_csv(Path(paths["aev"]), [CURVE, srtm])
    meta = {
        "dems": {
            dem: {
                "water_surface_m": 1004.0,
                "water_surface_area_km2": 50.0,
                "water_surface_share_of_mask": 0.6,
                "acquired": "2000-02-11/2000-02-22",
                "vertical_datum": "EGM96",
            }
            for dem in ("copernicus_glo30", "srtm")
        }
    }
    Path(paths["scenes_metadata"]).write_text(json.dumps(meta))
    v.write_scenes_csv(
        Path(paths["scenes"]),
        [
            scene("2024-01-10", "S2", 62.0),
            scene("2024-01-12", "S1", 63.0),
            scene("2024-02-11", "S1", 66.5),
            scene("2024-03-02", "S1", 70.5),
            scene("2024-02-20", "S2", 10.0, 0.1, "low_coverage"),
        ],
    )
    result = v.compare_reference(c, "masinga", log=lambda _: None)

    gauge = result.metrics["gauge"]["S1/srtm"]
    assert gauge["absolute"]["n"] == 2 and gauge["relative"]["n"] == 1
    assert gauge["rows_by_status"]["low_confidence"] == 1
    alt = result.metrics["altimetry"]
    assert alt["our_levels_vs_altimetry"]["S1/srtm"]["absolute"]["n"] == 2
    assert alt["label"] == "test altimetry" and alt["points"] == 2
    assert alt["altimetry_vs_gauge"]["metrics"]["n"] == 2
    assert alt["altimetry_vs_gauge"]["pairs"][0]["difference_m"] == -0.4
    # 1006.0 → 1006.9 over 29 days is slow: nothing flagged.
    assert gauge["rapid_change_rows"] == 0
    assert [r["published_date"] for r in result.metrics["convertibility"]][0] == "2009-06-26"
    assert result.metrics["area_at_fsl"]["comparisons"][0]["published_km2"] == 80.0
    assert result.metrics["scene_counts"]["S2"] == {
        "total": 2,
        "usable": 1,
        "fallback_threshold": 0,
    }
    assert "S1/srtm: n=2" in v.comparison_summary(result)

    with Path(paths["comparison"]).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == (3 + 2) * 2 * 2  # (gauge + altimetry targets) × sensors × DEMs
    assert {r["target"] for r in rows} == {"published", "altimetry"}
    with Path(paths["series"]).open(encoding="utf-8") as f:
        series = list(csv.DictReader(f))
    assert len(series) == 5 and "level_m_srtm" in series[0]
    assert Path(paths["figure"]).stat().st_size > 10_000
    assert json.loads(Path(paths["metrics"]).read_text())["reservoir"] == "masinga"


def test_compare_reference_needs_the_earth_engine_outputs(cfg: Config, tmp_path: Path) -> None:
    c = changed(cfg, "validation", ["paths"], aev=str(tmp_path / "none.csv"))
    with pytest.raises(v.ValidationError, match="without --compare-only"):
        v.compare_reference(c, "masinga", log=lambda _: None)


def test_rapid_change_flag_uses_rate_series() -> None:
    targets = [level("2023-11-06", 1006.0)]
    rates = [level("2023-10-28", 1004.5), level("2023-11-24", 1008.5)]  # 4 m / 27 days
    scenes = [scene("2023-11-04", "S1", 62.0)]
    rows = v.comparison_rows(
        targets, scenes, {"copernicus_glo30": CURVE}, {"copernicus_glo30": SURFACE}, 6, rates, 0.04
    )
    assert all(r["rapid_change"] for r in rows)
    assert rows[0]["change_rate_m_per_day"] == pytest.approx(0.148)
    summary = v.summarise(rows, "published")["S1/copernicus_glo30"]
    assert summary["rapid_change_rows"] == 1
    assert summary["absolute_without_rapid_change"] == {"n": 0}


def test_missing_altimetry_file_is_skipped(cfg: Config, tmp_path: Path) -> None:
    s = v.reference_settings(cfg, "masinga")
    block = v.altimetry_block(
        replace(s, altimetry_path=tmp_path / "gone.csv"), [], [], [], {}, missing=True
    )
    assert "not present" in block["note"]


def test_checkpoint_round_trip_and_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / ".scenes_S1.checkpoint.json"
    scenes = [scene("2024-01-02", "S1", 60.0), scene("2024-01-14", "S1", 61.25)]
    v.write_checkpoint(path, "abc", scenes, {"scenes_found": 2})
    back = v.read_checkpoint(path, "abc")
    assert back is not None
    assert [s.area_km2 for s in back[0]] == [60.0, 61.25] and back[1] == {"scenes_found": 2}
    assert v.read_checkpoint(path, "different") is None
    assert v.read_checkpoint(tmp_path / "none.json", "abc") is None
