"""Phase 1 pre-filling reference layers: land cover, "before" composite, river channel.

Method: docs/methodology.md §1.4. All three are read inside the frozen max extent or AOI
(``thwake baseline --step extent``) and recorded before any filling data is analysed.

- **Land cover** in the max extent (the land the full reservoir will cover): ESA WorldCover
  (2021) and Dynamic World over the pre-filling dry-season window, as hectares per class.
  For Dynamic World each pixel takes its most frequent label in the window. The spread
  between the two products (different years, methods and class definitions) is the
  uncertainty. An "expected area" from mean class probabilities was tried and dropped: the
  probabilities are not calibrated, so it puts ~1 km² into snow and ice here.
- **"Before" composite:** Sentinel-2 L2A median of the pre-filling window, clouds masked
  with Cloud Score+, exported as an Earth Engine asset (with a clear-observation count
  band) and as a small true-colour PNG for the story page.
- **River channel:** JRC Global Surface Water occurrence ≥ threshold inside the AOI, so
  that water present before the dam is not counted as reservoir. Areas at neighbouring
  thresholds are reported as its sensitivity.

The pure-Python helpers (settings, class tables, area rows, checks) are unit-tested. The
Earth Engine steps need an authenticated session; check them by running
``thwake baseline --step landcover`` / ``--step river`` / ``--step composite``.
"""

from __future__ import annotations

import csv
import json
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import ee
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from thwake.baseline import (
    BASELINE_VERSION,
    MAX_PIXELS,
    BaselineError,
    _get_info,
    _number,
    _require,
    area_km2,
    feature_collection,
    polygonal,
    write_geojson,
)
from thwake.collections import sentinel2_clear
from thwake.config import REPO_ROOT, Config, ConfigError

METHOD_REF = "docs/methodology.md §1.4"
# Repository budget per output file (AGENTS.md §5.3).
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
M2_PER_HA = 1e4

# ESA WorldCover v200 class codes → the matching Dynamic World class, so the two products can
# be compared. Class names are read from the image's ``Map_class_names`` property.
WORLDCOVER_BAND = "Map"
WORLDCOVER_COMMON = {
    10: "trees",
    20: "shrub_and_scrub",
    30: "grass",
    40: "crops",
    50: "built",
    60: "bare",
    70: "snow_and_ice",
    80: "water",
    90: "flooded_vegetation",
    95: "flooded_vegetation",  # mangroves
    100: "bare",  # moss and lichen
}
# Dynamic World V1 probability bands, in the order of the ``label`` band values.
DW_CLASSES = (
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
)
DW_LABEL_BAND = "label"
LANDCOVER_COLUMNS = (
    "source",
    "collection",
    "period",
    "class_value",
    "class_name",
    "common_class",
    "area_ha",
    "area_pct",
)
# Values of the ``source`` column, in output order.
SOURCES = {
    "esa_worldcover": "ESA WorldCover v200 map class (10 m)",
    "dynamic_world_mode": "Dynamic World: most frequent label per pixel over the window",
}
# Published accuracies, cited in docs/baseline-v1.md (global figures, not local).
PUBLISHED_ACCURACY = {
    "esa_worldcover": "76.7% global overall accuracy (WorldCover 2021 v200 validation report)",
    "dynamic_world": "73.8% agreement with an expert-consensus test set (Brown et al. 2022)",
}
JRC_PERIOD = "1984-03/2021-12"  # GSW 1.4 observation period (dataset documentation)
# True-colour stretch for the PNG (reflectance ×10⁴), as in notebooks/01_aoi_max_extent.
TRUE_COLOUR_BANDS = ("B4", "B3", "B2")
TRUE_COLOUR: dict[str, Any] = {
    "bands": list(TRUE_COLOUR_BANDS),
    "min": 200,
    "max": 2500,
    "gamma": 1.2,
}


# --- Settings ---------------------------------------------------------------------------


def _iso_date(value: Any, name: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ConfigError(f"{name} must be a YYYY-MM-DD date, got {value!r}") from exc


@dataclass(frozen=True)
class ReferenceSettings:
    """Inputs for the pre-filling reference layers, read from ``config/*.yaml``."""

    window_start: str
    window_end: str
    cs_min: float
    bands: tuple[str, ...]
    scale_m: float
    buffer_m: float
    png_px: int
    river_min_pct: float
    river_sensitivity_pct: tuple[float, ...]
    area_tolerance_pct: float
    asset_id: str
    collections: dict[str, str]
    aoi_path: Path
    max_extent_path: Path
    landcover_path: Path
    landcover_metadata_path: Path
    river_path: Path
    png_path: Path
    composite_metadata_path: Path

    @property
    def window(self) -> str:
        """The pre-filling window as an ISO 8601 interval (end exclusive)."""
        return f"{self.window_start}/{self.window_end}"


def reference_settings(cfg: Config) -> ReferenceSettings:
    """Read and validate the reference-layer inputs from the loaded configuration.

    Raises:
        ConfigError: If a value is missing or malformed, or the pre-filling window does not
            end before impoundment.
    """
    dates = cfg.settings.get("dates") or {}
    paths = cfg.settings.get("paths") or {}
    ee_cfg = cfg.settings.get("earth_engine") or {}
    base = cfg.thresholds.get("baseline") or {}
    where_dates, where_base, where_paths = (
        "settings.yaml dates",
        "thresholds.yaml baseline",
        "settings.yaml paths",
    )

    window = _require(dates, "pre_filling_window", where_dates)
    if not isinstance(window, dict):
        raise ConfigError(f"'pre_filling_window' in {where_dates} needs 'start' and 'end'")
    start = _iso_date(window.get("start"), "pre_filling_window.start")
    end = _iso_date(window.get("end"), "pre_filling_window.end")
    if end <= start:
        raise ConfigError(f"pre_filling_window ends ({end}) before it starts ({start})")
    impoundment = dates.get("impoundment_start")
    if impoundment is not None and end > _iso_date(impoundment, "impoundment_start"):
        raise ConfigError(
            f"pre_filling_window ends {end}, after impoundment started ({impoundment}): "
            "the reference layers must show the valley before filling"
        )

    bands = _require(base, "composite_bands", where_base)
    if not isinstance(bands, list) or not bands or not all(isinstance(b, str) for b in bands):
        raise ConfigError(f"'composite_bands' in {where_base} must be a list of band names")
    missing_tc = [b for b in TRUE_COLOUR_BANDS if b not in bands]
    if missing_tc:
        raise ConfigError(f"'composite_bands' must include the true-colour bands {missing_tc}")
    sensitivity = _require(base, "river_occurrence_sensitivity_pct", where_base)
    if not isinstance(sensitivity, list):
        raise ConfigError(f"'river_occurrence_sensitivity_pct' in {where_base} must be a list")
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in sensitivity):
        raise ConfigError(f"'river_occurrence_sensitivity_pct' in {where_base} must be numbers")
    sens_values = tuple(float(v) for v in sensitivity)
    cs_min = _number(base, "composite_cloud_score_min", where_base)
    river_min = _number(base, "river_occurrence_min_pct", where_base)
    if not 0 < cs_min < 1:
        raise ConfigError(f"'composite_cloud_score_min' must be between 0 and 1, got {cs_min}")
    if not all(0 < v <= 100 for v in (river_min, *sens_values)):
        raise ConfigError("River occurrence thresholds must be percentages in (0, 100]")

    keys = (
        "esa_worldcover",
        "dynamic_world",
        "jrc_global_surface_water",
        "sentinel2_sr",
        "cloud_score_plus",
        "chirps_daily",
    )
    return ReferenceSettings(
        window_start=start,
        window_end=end,
        cs_min=cs_min,
        bands=tuple(bands),
        scale_m=_number(base, "composite_scale_m", where_base),
        buffer_m=_number(base, "composite_buffer_m", where_base, positive=False),
        png_px=int(_number(base, "composite_png_px", where_base)),
        river_min_pct=river_min,
        river_sensitivity_pct=sens_values,
        area_tolerance_pct=_number(base, "landcover_area_tolerance_pct", where_base),
        asset_id=str(_require(ee_cfg, "before_composite_asset", "settings.yaml earth_engine")),
        collections={k: str(_require(cfg.ee_collections, k, "ee_collections")) for k in keys},
        aoi_path=REPO_ROOT / _require(paths, "aoi", where_paths),
        max_extent_path=REPO_ROOT / _require(paths, "max_extent", where_paths),
        landcover_path=REPO_ROOT / _require(paths, "landcover", where_paths),
        landcover_metadata_path=REPO_ROOT / _require(paths, "landcover_metadata", where_paths),
        river_path=REPO_ROOT / _require(paths, "river_channel", where_paths),
        png_path=REPO_ROOT / _require(paths, "before_composite_png", where_paths),
        composite_metadata_path=REPO_ROOT
        / _require(paths, "before_composite_metadata", where_paths),
    )


# --- Pure helpers -----------------------------------------------------------------------


def load_feature(path: Path) -> tuple[BaseGeometry, dict[str, Any]]:
    """Geometry and properties of a one-feature baseline GeoJSON (AOI or max extent).

    Raises:
        BaselineError: If the file does not exist yet.
    """
    if not path.is_file():
        raise BaselineError(
            f"{_display(path)} not found: run `thwake baseline --step extent` first"
        )
    feature = json.loads(path.read_text(encoding="utf-8"))["features"][0]
    return polygonal(shape(feature["geometry"])), feature["properties"]


def class_area_rows(
    source: str,
    collection: str,
    period: str,
    classes: Mapping[int, tuple[str, str]],
    areas_m2: Mapping[int, float],
    total_m2: float,
) -> list[dict[str, Any]]:
    """Land-cover CSV rows for one estimate, one per class with non-zero area.

    Args:
        source: Key of :data:`SOURCES`.
        collection: Earth Engine collection ID.
        period: ISO 8601 interval the estimate represents.
        classes: Class value → ``(class_name, common_class)``.
        areas_m2: Class value → area in m² (values not in ``classes`` raise).
        total_m2: Area the percentages refer to (the max-extent polygon).

    Returns:
        Rows (keys :data:`LANDCOVER_COLUMNS`), ordered by class value.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown land-cover source {source!r}")
    unknown = sorted(set(areas_m2) - set(classes))
    if unknown:
        raise BaselineError(f"{source}: class values {unknown} are not in the class table")
    rows = []
    for value in sorted(areas_m2):
        area = areas_m2[value]
        if area <= 0:
            continue
        name, common = classes[value]
        rows.append(
            {
                "source": source,
                "collection": collection,
                "period": period,
                "class_value": value,
                "class_name": name,
                "common_class": common,
                "area_ha": round(area / M2_PER_HA, 1),
                "area_pct": round(area / total_m2 * 100, 2),
            }
        )
    return rows


def worldcover_classes(values: Sequence[int], names: Sequence[str]) -> dict[int, tuple[str, str]]:
    """WorldCover class table from the image's ``Map_class_values`` / ``Map_class_names``."""
    if len(values) != len(names):
        raise BaselineError("WorldCover class values and names differ in length")
    missing = [v for v in values if v not in WORLDCOVER_COMMON]
    if missing:
        raise BaselineError(f"WorldCover classes {missing} have no Dynamic World equivalent")
    return {int(v): (str(n), WORLDCOVER_COMMON[int(v)]) for v, n in zip(values, names, strict=True)}


def dynamic_world_classes() -> dict[int, tuple[str, str]]:
    """Dynamic World class table: label value → ``(name, name)``."""
    return {i: (name, name) for i, name in enumerate(DW_CLASSES)}


def check_area_totals(
    rows: Sequence[Mapping[str, Any]], expected_km2: float, tolerance_pct: float
) -> dict[str, float]:
    """Sum each source's class areas and check it against the max-extent area.

    Returns:
        Total area (km²) per source.

    Raises:
        BaselineError: If a source's total differs from ``expected_km2`` by more than
            ``tolerance_pct`` (pixels missing from the product, or the wrong mask).
    """
    totals: dict[str, float] = {}
    for r in rows:
        totals[r["source"]] = totals.get(r["source"], 0.0) + r["area_ha"] / 100
    for source, total in totals.items():
        diff = (total - expected_km2) / expected_km2 * 100
        if abs(diff) > tolerance_pct:
            raise BaselineError(
                f"{source}: class areas sum to {total:.2f} km², {diff:+.1f}% from the max "
                f"extent ({expected_km2:.2f} km²); more than the {tolerance_pct:g}% tolerance"
            )
    return {s: round(t, 2) for s, t in totals.items()}


def common_class_table(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """Hectares per common class and source (missing = 0), classes by largest WorldCover area.

    The min–max across sources is the land-cover uncertainty reported in the docs.
    """
    table: dict[str, dict[str, float]] = {}
    for r in rows:
        by_source = table.setdefault(r["common_class"], dict.fromkeys(SOURCES, 0.0))
        by_source[r["source"]] = round(by_source[r["source"]] + r["area_ha"], 1)
    return dict(
        sorted(table.items(), key=lambda kv: (-kv[1]["esa_worldcover"], -max(kv[1].values())))
    )


def write_landcover_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Write the land-cover rows (columns :data:`LANDCOVER_COLUMNS`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LANDCOVER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, content: Mapping[str, Any]) -> None:
    """Write indented JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def check_size(path: Path, max_bytes: int = MAX_OUTPUT_BYTES) -> int:
    """Size of ``path`` in bytes.

    Raises:
        BaselineError: If the file is over the repository budget.
    """
    size = path.stat().st_size
    if size > max_bytes:
        raise BaselineError(
            f"{_display(path)} is {size / 1e6:.1f} MB, over the {max_bytes / 1e6:.0f} MB budget"
        )
    return size


def sensitivity_levels(chosen: float, others: Sequence[float]) -> list[float]:
    """The chosen threshold and the sensitivity thresholds, ascending, without repeats."""
    return sorted({float(chosen), *(float(v) for v in others)})


def _display(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def _generated() -> str:
    return datetime.now(UTC).date().isoformat()


def _ee_geometry(geom: BaseGeometry) -> ee.Geometry:
    return ee.Geometry(json.loads(shapely.to_geojson(geom)), None, False)


def _date_range(collection: ee.ImageCollection) -> ee.List:
    return (
        collection.aggregate_array("system:time_start")
        .map(lambda t: ee.Date(t).format("YYYY-MM-dd"))
        .distinct()
        .sort()
    )


# --- Land cover -------------------------------------------------------------------------


@dataclass(frozen=True)
class LandcoverResult:
    """Outputs of the land-cover step."""

    rows: list[dict[str, Any]]
    metadata: dict[str, Any]
    path: Path
    metadata_path: Path


def _grouped_areas(image: ee.Image, mask: ee.Geometry, crs: ee.Projection) -> ee.List:
    """``[{class, sum}]``: pixel area (m²) per class value, pixel centres inside ``mask``."""
    stack = ee.Image.pixelArea().addBands(image)
    reducer = ee.Reducer.sum().unweighted().group(groupField=1, groupName="class")
    return stack.reduceRegion(reducer=reducer, geometry=mask, crs=crs, maxPixels=MAX_PIXELS).get(
        "groups"
    )


def build_landcover(
    cfg: Config, write: bool = True, log: Callable[[str], None] = print
) -> LandcoverResult:
    """Hectares per land-cover class inside the max extent (WorldCover and Dynamic World).

    Earth Engine must already be initialised. The max extent must exist.

    Raises:
        BaselineError: If inputs are missing, there are no Dynamic World scenes, or the class
            areas do not add up to the max-extent area.
    """
    s = reference_settings(cfg)
    mask_geom, mask_props = load_feature(s.max_extent_path)
    mask = _ee_geometry(mask_geom)
    total_m2 = area_km2(mask_geom) * 1e6

    log("Land cover: ESA WorldCover inside the max extent ...")
    wc = ee.ImageCollection(s.collections["esa_worldcover"]).first()
    wc_map = wc.select(WORLDCOVER_BAND)
    wc_info = _get_info(
        ee.Dictionary(
            {
                "groups": _grouped_areas(wc_map, mask, wc_map.projection()),
                "values": wc.get("Map_class_values"),
                "names": wc.get("Map_class_names"),
                "start": ee.Date(wc.get("system:time_start")).format("YYYY-MM-dd"),
                "end": ee.Date(wc.get("system:time_end")).format("YYYY-MM-dd"),
                "id": wc.get("system:id"),
            }
        )
    )
    wc_period = f"{wc_info['start']}/{wc_info['end']}"
    rows = class_area_rows(
        "esa_worldcover",
        s.collections["esa_worldcover"],
        wc_period,
        worldcover_classes(wc_info["values"], wc_info["names"]),
        {int(g["class"]): g["sum"] for g in wc_info["groups"]},
        total_m2,
    )

    log(f"Land cover: Dynamic World {s.window} inside the max extent ...")
    dw = (
        ee.ImageCollection(s.collections["dynamic_world"])
        .filterBounds(mask)
        .filterDate(s.window_start, s.window_end)
    )
    n_scenes = int(_get_info(dw.size()))
    if n_scenes == 0:
        raise BaselineError(f"No Dynamic World scenes over the max extent in {s.window}")
    dw_proj = dw.first().select(DW_LABEL_BAND).projection()
    dw_info = _get_info(
        ee.Dictionary(
            {
                "groups": _grouped_areas(dw.select(DW_LABEL_BAND).mode(), mask, dw_proj),
                "dates": _date_range(dw),
                "crs": dw_proj.crs(),
            }
        )
    )
    rows += class_area_rows(
        "dynamic_world_mode",
        s.collections["dynamic_world"],
        s.window,
        dynamic_world_classes(),
        {int(g["class"]): g["sum"] for g in dw_info["groups"]},
        total_m2,
    )
    totals = check_area_totals(rows, total_m2 / 1e6, s.area_tolerance_pct)

    metadata = {
        "name": "Thwake flood zone land cover before filling",
        "baseline_version": BASELINE_VERSION,
        "csv": _display(s.landcover_path),
        "columns": {
            "source": "estimate (see 'sources')",
            "collection": "Earth Engine collection ID",
            "period": "ISO 8601 interval the estimate represents (end exclusive for DW)",
            "class_value": "class code in the source product",
            "class_name": "class name in the source product",
            "common_class": "matching Dynamic World class, to compare products",
            "area_ha": "hectares inside the max extent (pixel centres inside, geodesic area)",
            "area_pct": "percentage of the max-extent polygon area",
        },
        "sources": SOURCES,
        "published_accuracy": PUBLISHED_ACCURACY,
        "uncertainty": "Per common class, the min–max across the two products (different "
        "years, methods and class definitions), plus their published accuracies. Not checked "
        "on the ground.",
        "known_issues": [
            "WorldCover is 2021, three years into construction; Dynamic World is the 2026 dry "
            "season. Differences mix real change (clearing, construction) with product "
            "differences (e.g. Dynamic World rarely labels dryland grass).",
            "Dynamic World labels the dry sandy Thwake riverbed and the Athi channel as water; "
            "its water class here is river channel, not impounded water.",
        ],
        "zone": {
            "path": _display(s.max_extent_path),
            "area_km2": round(total_m2 / 1e6, 2),
            "level_m_asl": mask_props.get("level_m_asl"),
        },
        "totals_km2": totals,
        "worldcover": {"image": wc_info["id"], "period": wc_period},
        "dynamic_world": {
            "window": s.window,
            "scenes": n_scenes,
            "scene_dates": dw_info["dates"],
            "crs": dw_info["crs"],
        },
        "by_common_class_ha": common_class_table(rows),
        "method": METHOD_REF,
        "generated": _generated(),
    }
    result = LandcoverResult(rows, metadata, s.landcover_path, s.landcover_metadata_path)
    if write:
        write_landcover_csv(s.landcover_path, rows)
        write_json(s.landcover_metadata_path, metadata)
        check_size(s.landcover_path)
    return result


def landcover_summary(result: LandcoverResult) -> str:
    """Plain-text report of the land-cover step for the terminal."""
    meta = result.metadata
    width = 14
    labels = {
        "esa_worldcover": "WorldCover",
        "dynamic_world_mode": "DW mode",
    }
    dw = meta["dynamic_world"]
    lines = [
        f"Land cover in the max extent ({meta['zone']['area_km2']} km²) -> {_display(result.path)}",
        f"  WorldCover {meta['worldcover']['period']}; Dynamic World {dw['window']}"
        f" ({dw['scenes']} scenes)",
        "  " + f"{'class (ha)':<20}" + "".join(f"{labels[s]:>{width}}" for s in SOURCES),
    ]
    for common, by_source in meta["by_common_class_ha"].items():
        lines.append(
            "  " + f"{common:<20}" + "".join(f"{by_source[s]:>{width}.1f}" for s in SOURCES)
        )
    lines.append(
        "  totals (km²): "
        + ", ".join(f"{labels[s]} {v:.2f}" for s, v in meta["totals_km2"].items())
    )
    return "\n".join(lines)


# --- River channel ----------------------------------------------------------------------


@dataclass(frozen=True)
class RiverResult:
    """Outputs of the river-channel step."""

    collection: dict[str, Any]
    path: Path

    @property
    def properties(self) -> dict[str, Any]:
        """Metadata of the river-channel feature."""
        return self.collection["features"][0]["properties"]


def build_river(cfg: Config, write: bool = True, log: Callable[[str], None] = print) -> RiverResult:
    """Historic river channel: JRC occurrence ≥ threshold inside the AOI, as GeoJSON.

    Earth Engine must already be initialised. The AOI and max extent must exist.

    Raises:
        BaselineError: If inputs are missing or no pixel reaches the threshold.
    """
    s = reference_settings(cfg)
    aoi_geom, _ = load_feature(s.aoi_path)
    mask_geom, _ = load_feature(s.max_extent_path)
    aoi = _ee_geometry(aoi_geom)

    log(f"River channel: JRC occurrence ≥ {s.river_min_pct:g}% inside the AOI ...")
    gsw = ee.Image(s.collections["jrc_global_surface_water"])
    occurrence = gsw.select("occurrence")
    proj = occurrence.projection()
    vectors = (
        occurrence.gte(s.river_min_pct)
        .selfMask()
        .reduceToVectors(
            geometry=aoi,
            crs=proj,
            geometryType="polygon",
            eightConnected=True,
            maxPixels=MAX_PIXELS,
        )
    )
    levels = sensitivity_levels(s.river_min_pct, s.river_sensitivity_pct)
    area = ee.Image.pixelArea()
    stack = ee.Image.cat(
        [area.updateMask(occurrence.gte(t)).rename(f"occ_{t:g}") for t in levels]
        + [area.updateMask(gsw.select("max_extent")).rename("ever_water")]
    )
    info = _get_info(
        ee.Dictionary(
            {
                "n": vectors.size(),
                "geometry": vectors.geometry(),
                "areas": stack.reduceRegion(
                    reducer=ee.Reducer.sum().unweighted(),
                    geometry=aoi,
                    crs=proj,
                    maxPixels=MAX_PIXELS,
                ),
                "max_occurrence": occurrence.reduceRegion(
                    reducer=ee.Reducer.max(), geometry=aoi, crs=proj, maxPixels=MAX_PIXELS
                ).get("occurrence"),
            }
        )
    )
    if info["n"] == 0:
        raise BaselineError(
            f"No JRC pixels with occurrence ≥ {s.river_min_pct:g}% in the AOI; lower "
            "baseline.river_occurrence_min_pct"
        )
    channel = polygonal(shape(info["geometry"]))
    by_level = {f"{t:g}": round(info["areas"][f"occ_{t:g}"] / 1e6, 3) for t in levels}
    props = {
        "name": "Thwake historic river channel (pre-dam surface water)",
        "description": f"Pixels inside the AOI where JRC Global Surface Water saw water in at "
        f"least {s.river_min_pct:g}% of valid observations, {JRC_PERIOD}. Water detected "
        "here before impoundment is the river, not the reservoir.",
        "baseline_version": BASELINE_VERSION,
        "collection": s.collections["jrc_global_surface_water"],
        "observation_period": JRC_PERIOD,
        "occurrence_min_pct": s.river_min_pct,
        "area_km2": round(area_km2(channel), 3),
        "area_in_max_extent_km2": round(area_km2(shapely.intersection(channel, mask_geom)), 3),
        "polygons": info["n"],
        "max_occurrence_in_aoi_pct": info["max_occurrence"],
        "sensitivity_area_km2_by_occurrence_pct": by_level,
        "ever_water_area_km2": round(info["areas"]["ever_water"] / 1e6, 3),
        "uncertainty": "Area range across the sensitivity thresholds. The Athi here is narrow "
        "and seasonal, so 30 m pixels are mixed and the channel is broken into pieces.",
        "note": "The record includes 2018–2021, after construction started (2018-03-27); "
        "those 4 of ~38 years carry little weight in the occurrence.",
        "aoi": _display(s.aoi_path),
        "method": METHOD_REF,
        "generated": _generated(),
    }
    result = RiverResult(feature_collection(channel, props), s.river_path)
    if write:
        write_geojson(s.river_path, result.collection)
        check_size(s.river_path)
    return result


def river_summary(result: RiverResult) -> str:
    """Plain-text report of the river-channel step for the terminal."""
    p = result.properties
    sens = ", ".join(
        f"≥{t}%: {a:.3f}" for t, a in p["sensitivity_area_km2_by_occurrence_pct"].items()
    )
    return "\n".join(
        [
            f"River channel (JRC occurrence ≥ {p['occurrence_min_pct']:g}%): "
            f"{p['area_km2']:.3f} km² in {p['polygons']} pieces -> {_display(result.path)}",
            f"  inside the max extent: {p['area_in_max_extent_km2']:.3f} km²; "
            f"max occurrence in AOI {p['max_occurrence_in_aoi_pct']}%",
            f"  sensitivity (km²): {sens}; ever water {p['ever_water_area_km2']:.3f}",
        ]
    )


# --- "Before" composite -----------------------------------------------------------------


@dataclass(frozen=True)
class CompositeResult:
    """Outputs of the composite step."""

    metadata: dict[str, Any]
    png_path: Path
    metadata_path: Path


def download(url: str, path: Path, timeout_s: int = 300) -> None:
    """Fetch ``url`` (an Earth Engine thumbnail) to ``path``."""
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        content = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_composite(
    cfg: Config, write: bool = True, log: Callable[[str], None] = print
) -> CompositeResult:
    """Sentinel-2 dry-season median of the AOI before impoundment: EE asset, PNG, metadata.

    The asset export runs as an Earth Engine task (overwriting the versioned asset); this
    function starts it and records the task ID, it does not wait for it to finish.

    Raises:
        BaselineError: If inputs are missing, there are no clear scenes, or the PNG is over
            the size budget.
    """
    s = reference_settings(cfg)
    aoi_geom, _ = load_feature(s.aoi_path)
    west, south, east, north = aoi_geom.bounds
    region = (
        ee.Geometry.Rectangle([west, south, east, north], None, False)
        .buffer(s.buffer_m, 1)
        .bounds(1)
    )

    log(f"Before composite: Sentinel-2 {s.window}, Cloud Score+ ≥ {s.cs_min:g} ...")
    scenes = sentinel2_clear(cfg, region, s.window_start, s.window_end, s.cs_min)
    n_scenes = int(_get_info(scenes.size()))
    if n_scenes == 0:
        raise BaselineError(f"No Sentinel-2 granules over the AOI in {s.window}")
    proj = scenes.first().select("B4").projection().atScale(s.scale_m)
    clear = scenes.select("B4").count().rename("clear_obs")
    properties = {
        "baseline_version": BASELINE_VERSION,
        "window": s.window,
        "cloud_score_min": s.cs_min,
        "granules": n_scenes,
        "source": s.collections["sentinel2_sr"],
        "reflectance_scale": 10000,
        "generated": _generated(),
    }
    composite = (
        scenes.select(list(s.bands)).median().round().addBands(clear).toUint16().set(properties)
    )
    chirps = ee.ImageCollection(s.collections["chirps_daily"]).filterDate(
        s.window_start, s.window_end
    )
    info = _get_info(
        ee.Dictionary(
            {
                "dates": _date_range(scenes),
                "tiles": scenes.aggregate_array("MGRS_TILE").distinct(),
                "crs": proj.crs(),
                "region": region.coordinates(),
                "clear": clear.reduceRegion(
                    reducer=ee.Reducer.percentile([0, 5, 50]),
                    geometry=region,
                    crs=proj,
                    maxPixels=MAX_PIXELS,
                ),
                "rain_days": chirps.size(),
                "rain_last": ee.Date(chirps.aggregate_max("system:time_start")).format(
                    "YYYY-MM-dd"
                ),
                "rain_mm": chirps.sum()
                .reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=_ee_geometry(aoi_geom), scale=5566
                )
                .get("precipitation"),
            }
        )
    )
    if info["clear"]["clear_obs_p0"] == 0:
        raise BaselineError("Some composite pixels have no clear observation; widen the window")

    metadata: dict[str, Any] = {
        "name": "Thwake valley before filling: Sentinel-2 dry-season median composite",
        "baseline_version": BASELINE_VERSION,
        "asset_id": s.asset_id,
        "export_task_id": None,
        "bands": [*s.bands, "clear_obs"],
        "band_notes": f"{', '.join(s.bands)}: median surface reflectance ×10⁴ (uint16); "
        "clear_obs: number of clear observations per pixel",
        "scale_m": s.scale_m,
        "crs": info["crs"],
        "region": info["region"],
        "window": s.window,
        "granules": n_scenes,
        "acquisition_dates": len(info["dates"]),
        "scene_dates": info["dates"],
        "first_image": info["dates"][0],
        "last_image": info["dates"][-1],
        "tiles": info["tiles"],
        "cloud_score_min": s.cs_min,
        "clear_obs_per_pixel": {
            "min": round(info["clear"]["clear_obs_p0"]),
            "p5": round(info["clear"]["clear_obs_p5"]),
            "median": round(info["clear"]["clear_obs_p50"]),
        },
        "chirps_rain_in_window": {
            "mean_over_aoi_mm": None if info["rain_mm"] is None else round(info["rain_mm"], 1),
            "days_available": info["rain_days"],
            "last_day": info["rain_last"],
            "collection": s.collections["chirps_daily"],
        },
        "collections": {
            "sentinel2_sr": s.collections["sentinel2_sr"],
            "cloud_score_plus": s.collections["cloud_score_plus"],
        },
        "png": {
            "path": _display(s.png_path),
            "longest_side_px": s.png_px,
            "visualisation": TRUE_COLOUR,
        },
        "method": METHOD_REF,
        "generated": properties["generated"],
    }
    if write:
        log(f"  PNG ({s.png_px} px) -> {_display(s.png_path)}")
        url = composite.visualize(**TRUE_COLOUR).getThumbURL(
            {"region": region, "dimensions": s.png_px, "format": "png", "crs": info["crs"]}
        )
        download(url, s.png_path)
        metadata["png"]["bytes"] = check_size(s.png_path)
        log(f"  Export to asset {s.asset_id} (Earth Engine task, runs in the background) ...")
        task = ee.batch.Export.image.toAsset(
            image=composite,
            description=s.asset_id.rsplit("/", 1)[-1],
            assetId=s.asset_id,
            region=region,
            scale=s.scale_m,
            crs=info["crs"],
            maxPixels=MAX_PIXELS,
            overwrite=True,
        )
        task.start()
        metadata["export_task_id"] = task.id
        write_json(s.composite_metadata_path, metadata)
    return CompositeResult(metadata, s.png_path, s.composite_metadata_path)


def composite_summary(result: CompositeResult) -> str:
    """Plain-text report of the composite step for the terminal."""
    m = result.metadata
    rain = m["chirps_rain_in_window"]
    clear = m["clear_obs_per_pixel"]
    return "\n".join(
        [
            f"Before composite: {m['granules']} Sentinel-2 granules on {m['acquisition_dates']} "
            f"dates, {m['first_image']} to {m['last_image']} (tiles {', '.join(m['tiles'])}), "
            "Cloud Score+ ≥ "
            f"{m['cloud_score_min']:g}",
            f"  clear observations per pixel: min {clear['min']}, 5th pct {clear['p5']}, "
            f"median {clear['median']}",
            f"  CHIRPS rain over the AOI in {m['window']}: {rain['mean_over_aoi_mm']} mm "
            f"({rain['days_available']} days, to {rain['last_day']})",
            f"  PNG -> {m['png']['path']}; metadata -> {_display(result.metadata_path)}",
            f"  asset {m['asset_id']} (task {m['export_task_id']}; check the Tasks tab or "
            "`earthengine task list`)",
        ]
    )
