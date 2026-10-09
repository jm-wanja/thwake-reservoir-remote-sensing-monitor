"""Phase 1.5 validation: run the planned method on a reference reservoir (ADR 0009).

Write-up: docs/validation.md. Command: ``thwake validate reference --name masinga``.

The reference (Masinga, Tana River, Kenya; built 1981) has published gauge levels but no
published area or storage series, and no pre-dam DEM. The check is therefore of the step
Phase 2 relies on: **water area → level** through a DEM area–elevation curve, compared with
KenGen's published levels. Volume cannot be checked here (no pre-dam DEM).

Two stages:

1. **Earth Engine** (:func:`build_reference`): the max-extent mask (Copernicus GLO-30 flood
   fill from a seed, with a digitised closure line as barrier, as for Thwake), one
   area–elevation curve per DEM inside that mask, the water surface each DEM captured (its
   flat lake level), and the water area of every Sentinel-2 and Sentinel-1 scene in the
   window (:mod:`thwake.water_s2`, :mod:`thwake.water_s1`, :mod:`thwake.area`).
2. **Comparison** (:func:`compare_reference`, pure Python, reruns without Earth Engine):
   area → level per scene and DEM, scenes matched to each published date, absolute and
   relative agreement, the area-at-FSL side check and the figure.

**Absolute** agreement (our level − published level) contains every error, including a
constant offset between the gauge datum and the DEM's vertical datum. **Relative**
agreement (change between published dates, ours vs published) cancels any constant offset,
so it isolates errors that vary from date to date: water detection, DEM shape between the
two levels, timing. Low-confidence published figures are compared and shown but kept out of
the metrics. Nothing here is tuned to the reference: parameters come from
``config/thresholds.yaml`` and the results are reported as they are.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import ee
import shapely
from shapely.geometry.base import BaseGeometry

from thwake import area as area_mod
from thwake import volume, water_s1, water_s2
from thwake.baseline import (
    BaselineError,
    EarthEngineAEV,
    EarthEngineFill,
    ExtentSettings,
    _get_info,
    _lonlat,
    _number,
    _require,
    area_km2,
    check_excludes,
    check_inside,
    close_passes,
    extend_line,
    extent_settings,
    feature_collection,
    line_length_m,
    midpoint,
    polygonal,
    search_bounds,
    write_geojson,
)
from thwake.collections import DEM_LABELS, DEM_VERTICAL_DATUM
from thwake.config import REPO_ROOT, Config, ConfigError
from thwake.otsu import choose_threshold

METHOD_REF = "docs/validation.md"
METHOD_VERSION = "reference-v1"
HEADLINE_CONFIDENCE = ("high", "medium")
SENSORS = ("S2", "S1")
# Scenes per Earth Engine request (keeps each request well under the interactive time limit).
BATCH = 8
# Batches sent to Earth Engine at the same time, and retries when it reports too many
# concurrent requests (HTTP 429), waiting RETRY_WAIT_S, then twice as long each time.
WORKERS = 3
RETRIES = 6
RETRY_WAIT_S = 20
LonLat = tuple[float, float]


class ValidationError(Exception):
    """Raised when a validation input is missing or a check fails."""


# --- Settings ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceSettings:
    """Inputs for one reference reservoir, from ``config/validation.yaml`` and thresholds."""

    key: str
    name: str
    fsl_m: float
    mask_level_m: float
    closure_axis: tuple[LonLat, ...]
    closure_axis_source: str
    seed: LonLat
    downstream_point: LonLat
    search_radius_km: float
    crs: str
    scale_m: float
    scene_start: str
    scene_end: str
    altimetry_path: Path | None
    altimetry_label: str
    altimetry_citation: str
    paths: dict[str, Path]
    otsu_buffer_m: float
    match_window_days: int
    rapid_change_m_per_day: float
    dem_water_surface_min_share: float
    edge_fraction: float
    level_step_m: float
    dems: tuple[str, ...]


def reference_names(cfg: Config) -> list[str]:
    """Keys of the configured reference reservoirs."""
    return sorted((cfg.files.get("validation") or {}).get("reference_reservoirs") or {})


def _iso(value: Any, name: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ConfigError(f"'{name}' must be an ISO date, got {value!r}") from exc


def reference_settings(cfg: Config, name: str) -> ReferenceSettings:
    """Read and validate the settings for reference reservoir ``name``.

    Raises:
        ConfigError: If ``name`` is unknown or a value is missing or malformed.
    """
    v = cfg.files.get("validation") or {}
    reservoirs = v.get("reference_reservoirs") or {}
    if name not in reservoirs:
        raise ConfigError(
            f"Unknown reference reservoir {name!r}; configured: {', '.join(reference_names(cfg))}"
        )
    r = reservoirs[name]
    where = f"validation.yaml reference_reservoirs.{name}"
    paths_cfg = v.get("paths") or {}
    th = cfg.thresholds.get("validation") or {}
    where_th = "thresholds.yaml validation"
    base = cfg.thresholds.get("baseline") or {}
    unc = cfg.thresholds.get("uncertainty") or {}

    axis = _require(r, "closure_axis", where)
    if not isinstance(axis, list) or len(axis) < 2:
        raise ConfigError(f"'closure_axis' in {where} needs at least two points")
    window = _require(r, "scene_window", where)
    start = _iso(_require(window, "start", where), "scene_window.start")
    end = _iso(_require(window, "end", where), "scene_window.end")
    if end <= start:
        raise ConfigError(f"scene_window in {where} must end after it starts")
    fsl = _number(r, "full_supply_level_m_asl", where)
    mask_level = _number(r, "mask_level_m_asl", where)
    if mask_level < fsl:
        raise ConfigError(f"mask_level_m_asl in {where} must be at or above the FSL")
    keys = (
        "published_figures",
        "mask",
        "aev",
        "scenes",
        "scenes_metadata",
        "series",
        "comparison",
        "metrics",
        "figure",
    )
    paths = {
        k: REPO_ROOT / str(_require(paths_cfg, k, "validation.yaml paths")).format(name=name)
        for k in keys
    }
    altimetry = r.get("altimetry") or {}
    if not isinstance(altimetry, dict):
        raise ConfigError(f"'altimetry' in {where} must be a mapping (path, label, citation)")
    match_days = _number(th, "match_window_days", where_th)
    if match_days != int(match_days):
        raise ConfigError(f"'match_window_days' in {where_th} must be a whole number")
    return ReferenceSettings(
        key=name,
        name=str(r.get("name") or name),
        fsl_m=fsl,
        mask_level_m=mask_level,
        closure_axis=tuple(_lonlat(p, f"closure_axis[{i}]") for i, p in enumerate(axis)),
        closure_axis_source=str(r.get("closure_axis_source") or "not recorded"),
        seed=_lonlat(_require(r, "reservoir_seed", where), "reservoir_seed"),
        downstream_point=_lonlat(
            _require(r, "downstream_check_point", where), "downstream_check_point"
        ),
        search_radius_km=_number(r, "search_radius_km", where),
        crs=str(_require(r, "crs", where)),
        scale_m=_number(r, "scale_m", where),
        scene_start=start,
        scene_end=end,
        altimetry_path=REPO_ROOT / str(altimetry["path"]) if altimetry.get("path") else None,
        altimetry_label=str(altimetry.get("label") or ALTIMETRY_LABEL),
        altimetry_citation=str(altimetry.get("citation") or ""),
        paths=paths,
        otsu_buffer_m=_number(th, "otsu_buffer_m", where_th),
        match_window_days=int(match_days),
        rapid_change_m_per_day=_number(th, "rapid_change_m_per_day", where_th),
        dem_water_surface_min_share=_number(th, "dem_water_surface_min_share", where_th),
        edge_fraction=_number(unc, "edge_ring_pixels", "thresholds.yaml uncertainty"),
        level_step_m=_number(base, "aev_level_step_m", "thresholds.yaml baseline"),
        dems=tuple(_require(base, "aev_dems", "thresholds.yaml baseline")),
    )


def extent_inputs(cfg: Config, s: ReferenceSettings) -> ExtentSettings:
    """The Thwake extent settings with this reservoir's geometry, for :class:`EarthEngineFill`.

    Barrier, connectivity and pass-closure parameters stay those of the Thwake baseline, so
    the mask is built exactly as the Thwake one.
    """
    return replace(
        extent_settings(cfg),
        fsl_m=s.fsl_m,
        aoi_margin_m=s.mask_level_m - s.fsl_m,
        wall_axis=s.closure_axis,
        wall_axis_source=s.closure_axis_source,
        seed=s.seed,
        downstream_point=s.downstream_point,
        search_radius_km=s.search_radius_km,
    )


# --- Published figures (pure Python) ----------------------------------------------------


@dataclass(frozen=True)
class PublishedLevel:
    """A published water level for a date or a short date interval."""

    start: date
    end: date
    level_m: float
    confidence: str
    source: str
    source_url: str = ""
    error_m: float | None = None

    @property
    def headline(self) -> bool:
        """True if the figure is reliable enough for the headline metrics."""
        return self.confidence in HEADLINE_CONFIDENCE

    @property
    def mid(self) -> date:
        """Middle of the date interval (the date itself for a single day)."""
        return date.fromordinal((self.start.toordinal() + self.end.toordinal()) // 2)

    @property
    def label(self) -> str:
        """``YYYY-MM-DD`` or ``YYYY-MM-DD/YYYY-MM-DD``."""
        if self.start == self.end:
            return self.start.isoformat()
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


def parse_value_date(text: str) -> tuple[date, date]:
    """Parse ``YYYY-MM-DD`` or ``YYYY-MM-DD/YYYY-MM-DD`` into ``(start, end)``.

    Raises:
        ValueError: If the text is not one of those forms or the interval is reversed.
    """
    parts = text.strip().split("/")
    if len(parts) not in (1, 2):
        raise ValueError(f"Bad value_date {text!r}")
    start = date.fromisoformat(parts[0])
    end = date.fromisoformat(parts[-1])
    if end < start:
        raise ValueError(f"value_date interval {text!r} ends before it starts")
    return start, end


def read_published(path: Path, reservoir: str) -> list[dict[str, str]]:
    """Rows of ``reference_reservoirs.csv`` for one reservoir.

    Raises:
        ValidationError: If the file is missing.
    """
    if not Path(path).is_file():
        raise ValidationError(f"Published figures not found: {path}")
    with Path(path).open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("reservoir") == reservoir]


def published_levels(
    rows: Iterable[Mapping[str, str]], start: str, end: str
) -> tuple[list[PublishedLevel], list[PublishedLevel]]:
    """Split the published ``water_level`` rows into those inside and outside the window.

    Args:
        rows: Rows from :func:`read_published`.
        start: First date of the scene window (inclusive), ISO.
        end: End of the scene window (exclusive), ISO.

    Returns:
        ``(inside, outside)``, each sorted by date. Outside rows are context only.
    """
    lo, hi = date.fromisoformat(start), date.fromisoformat(end)
    inside: list[PublishedLevel] = []
    outside: list[PublishedLevel] = []
    for r in rows:
        if r.get("item") != "water_level" or not r.get("value_date"):
            continue
        d0, d1 = parse_value_date(r["value_date"])
        level = PublishedLevel(
            d0, d1, float(r["value"]), r.get("confidence", ""), "published", r.get("source_url", "")
        )
        (inside if lo <= d0 and d1 < hi else outside).append(level)
    return sorted(inside, key=lambda p: p.start), sorted(outside, key=lambda p: p.start)


def published_item(rows: Iterable[Mapping[str, str]], item: str) -> list[dict[str, Any]]:
    """Published constants (e.g. ``surface_area_at_fsl``) with value, confidence and source."""
    return [
        {
            "value": float(r["value"]),
            "unit": r.get("unit", ""),
            "confidence": r.get("confidence", ""),
            "source_url": r.get("source_url", ""),
        }
        for r in rows
        if r.get("item") == item
    ]


ALTIMETRY_COLUMNS = ("date", "level_m", "level_error_m")
DAHITI_COLUMNS = ("datetime", "wse", "wse_u")
ALTIMETRY_LABEL = "independent satellite altimetry, not gauge ground truth"


def read_altimetry(path: Path) -> list[PublishedLevel]:
    """Read a satellite-altimetry level series (e.g. DAHITI) as comparison targets.

    These are an **independent satellite product, not ground truth**: they are compared
    with our levels in their own block and never mixed into the gauge metrics.

    Two layouts are accepted, recognised by the header: the DAHITI download
    (semicolon-separated ``datetime;wse;wse_u``, water-surface elevation and its uncertainty
    in metres; the time of day is dropped) or a plain CSV ``date,level_m,level_error_m``.

    Raises:
        ValidationError: If the file is missing or the header is neither layout.
    """
    if not Path(path).is_file():
        raise ValidationError(f"Altimetry series not found: {path}")
    with Path(path).open(newline="", encoding="utf-8") as f:
        header = f.readline().strip()
        delimiter = ";" if ";" in header else ","
        names = tuple(h.strip() for h in header.split(delimiter))
        if names[:3] == DAHITI_COLUMNS:
            day, level, error = DAHITI_COLUMNS
        elif names[:3] == ALTIMETRY_COLUMNS:
            day, level, error = ALTIMETRY_COLUMNS
        else:
            raise ValidationError(
                f"{path}: expected columns {DAHITI_COLUMNS} (DAHITI) or {ALTIMETRY_COLUMNS}"
            )
        out = []
        for r in csv.DictReader(f, fieldnames=names, delimiter=delimiter):
            if not r.get(day):
                continue
            d = date.fromisoformat(r[day].strip()[:10])
            err = r.get(error)
            out.append(
                PublishedLevel(
                    d,
                    d,
                    float(r[level]),
                    "altimetry",
                    "altimetry",
                    error_m=float(err) if err not in (None, "") else None,
                )
            )
    return sorted(out, key=lambda p: p.start)


def change_rate(
    series: Sequence[PublishedLevel], start: date, end: date, window_days: int
) -> float | None:
    """Fastest level change (m/day) in ``series`` around ``[start, end]`` ± ``window_days``.

    The rate is the largest absolute slope between consecutive points of the series whose
    interval overlaps that period (the period a matched scene can come from).

    Returns:
        The rate, or ``None`` if no pair of points overlaps the period.
    """
    lo = start.toordinal() - window_days
    hi = end.toordinal() + window_days
    points = sorted(series, key=lambda p: p.mid)
    rates = []
    for a, b in zip(points, points[1:], strict=False):
        t0, t1 = a.mid.toordinal(), b.mid.toordinal()
        if t1 > t0 and t1 >= lo and t0 <= hi:
            rates.append(abs(b.level_m - a.level_m) / (t1 - t0))
    return max(rates) if rates else None


def cross_check(
    gauge: Sequence[PublishedLevel], altimetry: Sequence[PublishedLevel], window_days: int
) -> list[dict[str, Any]]:
    """Each gauge level with the nearest altimetry level within ``window_days`` (or none)."""
    rows = []
    for g in gauge:
        best: tuple[int, PublishedLevel] | None = None
        for a in altimetry:
            if g.start <= a.start <= g.end:
                gap = 0
            else:
                gap = min(abs((a.start - g.start).days), abs((a.start - g.end).days))
            if gap <= window_days and (best is None or gap < best[0]):
                best = (gap, a)
        if best is not None:
            gap, a = best
            rows.append(
                {
                    "gauge_date": g.label,
                    "gauge_level_m": g.level_m,
                    "confidence": g.confidence,
                    "headline": g.headline,
                    "altimetry_date": a.start.isoformat(),
                    "altimetry_level_m": a.level_m,
                    "gap_days": gap,
                    "difference_m": round(a.level_m - g.level_m, 2),
                }
            )
    return rows


# --- DEM water surface (pure Python) ----------------------------------------------------


@dataclass(frozen=True)
class WaterSurface:
    """The lake surface a post-dam DEM captured: flat at one elevation.

    ``level_m`` is ``None`` if no single elevation covers enough of the mask (no flat
    surface found); then every level on the curve can be estimated.
    """

    dem: str
    level_m: float | None
    area_km2: float
    share: float

    def convertible(self, level_m: float) -> bool:
        """True if a level above this surface (so visible on the DEM) can be estimated."""
        return self.level_m is None or level_m > self.level_m


def water_surface(
    dem: str, mode_m: float, mode_area_km2: float, mask_area_km2: float, min_share: float
) -> WaterSurface:
    """Classify a DEM's most common elevation in the mask as its flat water surface or not.

    Args:
        dem: DEM short name.
        mode_m: Most common elevation inside the mask.
        mode_area_km2: Area of the pixels at exactly that elevation.
        mask_area_km2: Mask area on the DEM grid.
        min_share: Share of the mask the mode must cover to count as a water surface.
    """
    share = mode_area_km2 / mask_area_km2 if mask_area_km2 > 0 else 0.0
    if share < min_share:
        return WaterSurface(dem, None, mode_area_km2, share)
    return WaterSurface(dem, mode_m, mode_area_km2, share)


# --- Scene areas ------------------------------------------------------------------------


SCENE_COLUMNS = (
    "date",
    "sensor",
    "orbit",
    "scene_id",
    "parts",
    "valid_fraction",
    "threshold",
    "threshold_method",
    "area_km2",
    "area_km2_low",
    "area_km2_high",
    "qa_flag",
)


@dataclass(frozen=True)
class SceneArea:
    """Water area measured on one scene (one day, one sensor, one orbit pass for S1)."""

    date: date
    sensor: str
    orbit: str
    scene_id: str
    parts: int
    valid_fraction: float
    threshold: float
    threshold_method: str
    area_km2: float
    area_km2_low: float
    area_km2_high: float
    qa_flag: str

    @property
    def usable(self) -> bool:
        """True if the scene passes QA (enough of the mask visible)."""
        return self.qa_flag == "ok"

    def row(self) -> list[str]:
        """CSV row in :data:`SCENE_COLUMNS` order."""
        return [
            self.date.isoformat(),
            self.sensor,
            self.orbit,
            self.scene_id,
            str(self.parts),
            f"{self.valid_fraction:.4f}",
            f"{self.threshold:.3f}",
            self.threshold_method,
            f"{self.area_km2:.4f}",
            f"{self.area_km2_low:.4f}",
            f"{self.area_km2_high:.4f}",
            self.qa_flag,
        ]


def qa_flag(valid_fraction: float, min_valid_fraction: float) -> str:
    """``ok`` or ``low_coverage`` (methodology §2.6)."""
    return "ok" if valid_fraction >= min_valid_fraction else "low_coverage"


def write_scenes_csv(path: Path, scenes: Iterable[SceneArea]) -> None:
    """Write scene areas, sorted by date then sensor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SCENE_COLUMNS)
        for s in sorted(scenes, key=lambda s: (s.date, s.sensor, s.orbit)):
            w.writerow(s.row())


def read_scenes_csv(path: Path) -> list[SceneArea]:
    """Read scene areas written by :func:`write_scenes_csv`.

    Raises:
        ValidationError: If the file is missing or the header is wrong.
    """
    if not Path(path).is_file():
        raise ValidationError(
            f"{path} not found: run `thwake validate reference` without --compare-only first"
        )
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != SCENE_COLUMNS:
            raise ValidationError(f"{path}: expected columns {SCENE_COLUMNS}")
        return [_scene_from_row(r) for r in reader]


# --- Area → level (pure Python) ---------------------------------------------------------

OK = "ok"
NO_SCENE = "no_scene"
NOT_CONVERTIBLE = "not_convertible"
BELOW_SURFACE = "below_dem_water_surface"
ABOVE_CURVE = "above_curve"


@dataclass(frozen=True)
class LevelEstimate:
    """Water level from a measured area on one DEM curve, with its status."""

    best: float | None
    low: float | None
    high: float | None
    status: str


def _level(curve: volume.AEVCurve, area_km2: float) -> float | None:
    try:
        return curve.level_at_area(area_km2)
    except volume.AEVRangeError:
        return None


def level_from_area(
    curve: volume.AEVCurve, best: float, low: float, high: float, surface: WaterSurface
) -> LevelEstimate:
    """Area range → level range on one DEM curve.

    Below the DEM's water surface the curve is flat (the DEM shows the lake, not its bed):
    an area at or below the surface area only says the level was at or below that surface,
    so no estimate is given (``below_dem_water_surface``). Areas beyond the curve's top
    give ``above_curve``.
    """
    if surface.level_m is not None and best <= curve.area_at_level(surface.level_m):
        return LevelEstimate(None, None, None, BELOW_SURFACE)
    level = _level(curve, best)
    if level is None:
        return LevelEstimate(None, _level(curve, low), None, ABOVE_CURVE)
    return LevelEstimate(level, _level(curve, low), _level(curve, high), OK)


def series_rows(
    scenes: Sequence[SceneArea],
    curves: Mapping[str, volume.AEVCurve],
    surfaces: Mapping[str, WaterSurface],
) -> list[dict[str, Any]]:
    """Every scene with its level on every DEM curve (for the series CSV and the figure)."""
    rows = []
    for s in sorted(scenes, key=lambda s: (s.date, s.sensor, s.orbit)):
        row: dict[str, Any] = dict(zip(SCENE_COLUMNS, s.row(), strict=True))
        for dem, curve in curves.items():
            est = level_from_area(curve, s.area_km2, s.area_km2_low, s.area_km2_high, surfaces[dem])
            row |= {
                f"level_m_{dem}": _fmt(est.best),
                f"level_m_low_{dem}": _fmt(est.low),
                f"level_m_high_{dem}": _fmt(est.high),
                f"level_status_{dem}": est.status,
            }
        rows.append(row)
    return rows


def _fmt(value: float | None, decimals: int = 2) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


# --- Matching and comparison (pure Python) ----------------------------------------------


def match_scene(
    target: PublishedLevel, scenes: Sequence[SceneArea], sensor: str, window_days: int
) -> tuple[SceneArea | None, int | None]:
    """The usable scene of ``sensor`` closest to the published date, within the window.

    The gap is 0 for a scene inside the published interval, else the days to its nearest
    end. Ties go to the scene with the larger valid fraction.

    Returns:
        ``(scene, gap in days)`` or ``(None, None)`` if no usable scene is close enough.
    """
    best: tuple[int, float, SceneArea] | None = None
    for s in scenes:
        if s.sensor != sensor or not s.usable:
            continue
        if target.start <= s.date <= target.end:
            gap = 0
        else:
            gap = min(abs((s.date - target.start).days), abs((s.date - target.end).days))
        if gap > window_days:
            continue
        key = (gap, -s.valid_fraction, s)
        if best is None or key[:2] < best[:2]:
            best = key
    return (best[2], best[0]) if best else (None, None)


COMPARISON_COLUMNS = (
    "target",
    "published_date",
    "published_level_m",
    "confidence",
    "headline",
    "sensor",
    "dem",
    "dem_water_surface_m",
    "convertible",
    "scene_date",
    "gap_days",
    "valid_fraction",
    "area_km2",
    "area_km2_low",
    "area_km2_high",
    "level_m",
    "level_m_low",
    "level_m_high",
    "difference_m",
    "status",
    "change_rate_m_per_day",
    "rapid_change",
)


def comparison_rows(
    targets: Sequence[PublishedLevel],
    scenes: Sequence[SceneArea],
    curves: Mapping[str, volume.AEVCurve],
    surfaces: Mapping[str, WaterSurface],
    window_days: int,
    rate_series: Sequence[PublishedLevel] | None = None,
    rapid_change_m_per_day: float | None = None,
) -> list[dict[str, Any]]:
    """One row per published level × sensor × DEM: our level, the difference and a status.

    Status precedence: ``no_scene`` (no usable scene in the window), ``not_convertible``
    (the published level is at or below the DEM's water surface, so the DEM cannot show
    it), then the status of the area → level conversion (:func:`level_from_area`). A level
    is still computed for ``not_convertible`` rows where possible, for information only.

    ``change_rate_m_per_day`` is the fastest level change around the date in
    ``rate_series`` (default: the targets themselves; :func:`change_rate`). Rows at or above
    ``rapid_change_m_per_day`` are flagged ``rapid_change``: there, the days between scene
    and reading alone can move the level by more than the comparison resolves.
    """
    series = rate_series if rate_series else targets
    rows = []
    for t in targets:
        rate = change_rate(series, t.start, t.end, window_days)
        rapid = (
            rate is not None
            and rapid_change_m_per_day is not None
            and rate >= rapid_change_m_per_day
        )
        for sensor in SENSORS:
            scene, gap = match_scene(t, scenes, sensor, window_days)
            for dem, curve in curves.items():
                surface = surfaces[dem]
                convertible = surface.convertible(t.level_m)
                row: dict[str, Any] = {
                    "target": t.source,
                    "published_date": t.label,
                    "published_level_m": t.level_m,
                    "confidence": t.confidence,
                    "headline": t.headline,
                    "sensor": sensor,
                    "dem": dem,
                    "dem_water_surface_m": surface.level_m,
                    "convertible": convertible,
                    "scene_date": None,
                    "gap_days": gap,
                    "valid_fraction": None,
                    "area_km2": None,
                    "area_km2_low": None,
                    "area_km2_high": None,
                    "level_m": None,
                    "level_m_low": None,
                    "level_m_high": None,
                    "difference_m": None,
                    "status": NO_SCENE,
                    "change_rate_m_per_day": None if rate is None else round(rate, 3),
                    "rapid_change": rapid,
                }
                if scene is not None:
                    est = level_from_area(
                        curve, scene.area_km2, scene.area_km2_low, scene.area_km2_high, surface
                    )
                    row |= {
                        "scene_date": scene.date.isoformat(),
                        "valid_fraction": scene.valid_fraction,
                        "area_km2": scene.area_km2,
                        "area_km2_low": scene.area_km2_low,
                        "area_km2_high": scene.area_km2_high,
                        "level_m": est.best,
                        "level_m_low": est.low,
                        "level_m_high": est.high,
                        "difference_m": None if est.best is None else est.best - t.level_m,
                        "status": est.status if convertible else NOT_CONVERTIBLE,
                    }
                rows.append(row)
    return rows


def absolute_metrics(differences: Sequence[float]) -> dict[str, Any]:
    """Agreement of levels: n, bias (mean), RMSE, MAE, SD (RMSE with the bias removed), max.

    ``RMSE² = bias² + SD²``: the bias is any constant offset (e.g. between the gauge datum
    and the DEM datum); the SD is the date-to-date scatter around it.
    """
    n = len(differences)
    if n == 0:
        return {"n": 0}
    bias = sum(differences) / n
    rmse = math.sqrt(sum(d * d for d in differences) / n)
    sd = math.sqrt(sum((d - bias) ** 2 for d in differences) / n)
    return {
        "n": n,
        "bias_m": round(bias, 2),
        "rmse_m": round(rmse, 2),
        "mae_m": round(sum(abs(d) for d in differences) / n, 2),
        "sd_m": round(sd, 2),
        "max_abs_m": round(max(abs(d) for d in differences), 2),
    }


def relative_metrics(pairs: Sequence[tuple[str, float, float, str]]) -> dict[str, Any]:
    """Agreement of level *changes* between consecutive published dates.

    Args:
        pairs: ``(date label, published level, our level, scene date)``, sorted by date.

    Returns:
        n, RMSE, MAE and max of (our change − published change), and the changes. A
        constant offset between the two level series cancels out here. Consecutive dates
        matched to the same scene are skipped (our change would be zero by construction,
        not a measurement) and counted in ``skipped_same_scene``.
    """
    changes: list[dict[str, Any]] = []
    skipped = 0
    for (d0, p0, o0, s0), (d1, p1, o1, s1) in zip(pairs, pairs[1:], strict=False):
        if s0 == s1:
            skipped += 1
            continue
        dp, do = p1 - p0, o1 - o0
        changes.append(
            {
                "from": d0,
                "to": d1,
                "published_change_m": round(dp, 2),
                "our_change_m": round(do, 2),
                "error_m": round(do - dp, 2),
            }
        )
    if not changes:
        return {"n": 0, "changes": [], "skipped_same_scene": skipped}
    errors = [float(c["error_m"]) for c in changes]
    n = len(errors)
    return {
        "n": n,
        "rmse_m": round(math.sqrt(sum(e * e for e in errors) / n), 2),
        "mae_m": round(sum(abs(e) for e in errors) / n, 2),
        "max_abs_m": round(max(abs(e) for e in errors), 2),
        "changes": changes,
        "skipped_same_scene": skipped,
    }


def summarise(
    rows: Sequence[Mapping[str, Any]], target: str, headline_only: bool = True
) -> dict[str, Any]:
    """Metrics per sensor/DEM for rows of one target kind (``published`` or ``altimetry``).

    Only rows with status ``ok`` (and, with ``headline_only``, a headline-confidence
    figure) enter the metrics; the other rows are counted by status. Altimetry rows carry
    no confidence grade, so they are summarised with ``headline_only=False``.
    """
    out: dict[str, Any] = {}
    for sensor in SENSORS:
        dems = dict.fromkeys(r["dem"] for r in rows)
        for dem in dems:
            group = [
                r
                for r in rows
                if r["target"] == target and r["sensor"] == sensor and r["dem"] == dem
            ]
            used = [r for r in group if r["status"] == OK and (r["headline"] or not headline_only)]
            counts: dict[str, int] = {}
            for r in group:
                key = r["status"] if r["headline"] or not headline_only else "low_confidence"
                counts[key] = counts.get(key, 0) + 1
            pairs = [
                (r["published_date"], r["published_level_m"], r["level_m"], r["scene_date"])
                for r in used
            ]
            calm = [r for r in used if not r.get("rapid_change")]
            out[f"{sensor}/{dem}"] = {
                "absolute": absolute_metrics([r["difference_m"] for r in used]),
                "relative": relative_metrics(pairs),
                "rows_by_status": counts,
                "rapid_change_rows": len(used) - len(calm),
                "absolute_without_rapid_change": absolute_metrics(
                    [r["difference_m"] for r in calm]
                ),
            }
    return out


def area_at_fsl_check(
    rows: Sequence[Mapping[str, Any]],
    published_areas: Sequence[Mapping[str, Any]],
    curves: Mapping[str, volume.AEVCurve],
    fsl_m: float,
    tolerance_m: float = 0.5,
) -> dict[str, Any]:
    """Side check (low confidence): our area when the gauge was at FSL vs published areas.

    Uses the matched scene of the published level closest to FSL (within ``tolerance_m``),
    per sensor, and each DEM curve's area at FSL. Never part of the headline metrics.
    """
    near = [
        r
        for r in rows
        if r["target"] == "published"
        and r["headline"]
        and r["area_km2"] is not None
        and abs(r["published_level_m"] - fsl_m) <= tolerance_m
    ]
    measured = {}
    for sensor in SENSORS:
        cand = [r for r in near if r["sensor"] == sensor]
        if cand:
            r = min(cand, key=lambda r: abs(r["published_level_m"] - fsl_m))
            measured[sensor] = {
                "published_date": r["published_date"],
                "published_level_m": r["published_level_m"],
                "scene_date": r["scene_date"],
                "area_km2": round(r["area_km2"], 2),
                "area_km2_low": round(r["area_km2_low"], 2),
                "area_km2_high": round(r["area_km2_high"], 2),
            }
    dem_areas: dict[str, float | None] = {}
    for dem, c in curves.items():
        try:
            dem_areas[dem] = round(c.area_at_level(fsl_m), 2)
        except volume.AEVRangeError:
            dem_areas[dem] = None
    comparisons = []
    for p in published_areas:
        entry: dict[str, Any] = {
            "published_km2": p["value"],
            "confidence": p["confidence"],
            "source_url": p["source_url"],
        }
        for sensor, m in measured.items():
            entry[f"{sensor}_pct_difference"] = round(
                volume.percent_difference(m["area_km2"], p["value"]), 1
            )
        for dem, a in dem_areas.items():
            if a is not None:
                entry[f"{dem}_curve_pct_difference"] = round(
                    volume.percent_difference(a, p["value"]), 1
                )
        comparisons.append(entry)
    return {
        "note": "Low-confidence published areas (design values, unverified); not a headline "
        "metric. The design area dates from 1981; sedimentation and the 2024–26 shoreline "
        "differ from it.",
        "fsl_m_asl": fsl_m,
        "measured_near_fsl": measured,
        "dem_curve_area_at_fsl_km2": dem_areas,
        "comparisons": comparisons,
    }


def convertibility_table(
    targets: Sequence[PublishedLevel],
    context: Sequence[PublishedLevel],
    surfaces: Mapping[str, WaterSurface],
) -> list[dict[str, Any]]:
    """Every published level, in or out of the scene window, and whether each DEM can show it."""
    table = []
    for t in sorted([*targets, *context], key=lambda t: t.start):
        table.append(
            {
                "published_date": t.label,
                "published_level_m": t.level_m,
                "confidence": t.confidence,
                "in_scene_window": t in targets,
                **{f"convertible_{dem}": s.convertible(t.level_m) for dem, s in surfaces.items()},
            }
        )
    return table


def write_rows_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    """Write dict rows with fixed columns; floats to 4 decimals, ``None`` as empty."""

    def cell(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, bool):
            return str(v).lower()
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow([cell(r.get(c)) for c in columns])


def write_json(path: Path, content: Mapping[str, Any]) -> None:
    """Write indented JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# --- Earth Engine stage -----------------------------------------------------------------

# Profile IDs are resolved in groups of this size (one request each).
PROFILE_CHUNK = 50


def eecu_seconds(profile_text: str) -> float:
    """Total EECU-seconds in an Earth Engine profile table (sum of its first column).

    The table (from ``Profile.getProfiles``) has one row per algorithm with its EECU·s
    first; rows whose first column is ``-`` used no measurable compute.
    """
    total = 0.0
    for line in profile_text.splitlines()[1:]:
        first = line.split()[0] if line.split() else ""
        try:
            total += float(first)
        except ValueError:
            continue
    return total


def profile_cost(profile_ids: Sequence[str]) -> tuple[float, int]:
    """EECU-seconds of the Earth Engine requests behind ``profile_ids``.

    Profiles expire on the server after a while, so call this soon after the requests.
    Cost is reporting only: a chunk that cannot be resolved is counted, never raised.

    Returns:
        ``(EECU-seconds, number of profile IDs that could not be resolved)``.
    """
    get_profiles = ee.ApiFunction.lookup("Profile.getProfiles").call
    total, unresolved = 0.0, 0
    for i in range(0, len(profile_ids), PROFILE_CHUNK):
        chunk = list(profile_ids[i : i + PROFILE_CHUNK])
        try:
            total += eecu_seconds(str(get_profiles(ids=chunk).getInfo()))
        except ee.EEException:
            unresolved += len(chunk)
    return total, unresolved


class CostMeter:
    """EECU-seconds and request count of a run, resolved as it goes (thread-safe)."""

    def __init__(self) -> None:
        """Start at zero."""
        self.eecu_s = 0.0
        self.requests = 0
        self.unresolved = 0
        self._lock = threading.Lock()

    def add(self, profile_ids: Sequence[str]) -> None:
        """Resolve and add the cost of these requests."""
        eecu, unresolved = profile_cost(profile_ids)
        with self._lock:
            self.eecu_s += eecu
            self.requests += len(profile_ids)
            self.unresolved += unresolved


def buffer_metres(geom: BaseGeometry, metres: float, crs: str) -> BaseGeometry:
    """Buffer a WGS84 geometry by ``metres`` in a projected CRS, simplified to ~1/4 of that."""
    import geopandas as gpd

    projected = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(crs)
    grown = projected.buffer(metres).simplify(metres / 4)
    return grown.to_crs("EPSG:4326").iloc[0]


def _ee_geometry(geom: BaseGeometry) -> ee.Geometry:
    return ee.Geometry(json.loads(shapely.to_geojson(geom)), None, False)


def write_checkpoint(
    path: Path, fingerprint: str, scenes: Sequence[SceneArea], info: Mapping[str, Any]
) -> None:
    """Save one sensor's scene areas so a failed run can resume without recomputing them."""
    write_json(
        path,
        {
            "fingerprint": fingerprint,
            "info": dict(info),
            "scenes": [dict(zip(SCENE_COLUMNS, s.row(), strict=True)) for s in scenes],
        },
    )


def read_checkpoint(path: Path, fingerprint: str) -> tuple[list[SceneArea], dict[str, Any]] | None:
    """Scene areas from a checkpoint written with the same ``fingerprint``, else ``None``."""
    if not path.is_file():
        return None
    content = json.loads(path.read_text(encoding="utf-8"))
    if content.get("fingerprint") != fingerprint:
        return None
    return [_scene_from_row(r) for r in content["scenes"]], content["info"]


def _scene_from_row(r: Mapping[str, str]) -> SceneArea:
    return SceneArea(
        date=date.fromisoformat(r["date"]),
        sensor=r["sensor"],
        orbit=r["orbit"],
        scene_id=r["scene_id"],
        parts=int(r["parts"]),
        valid_fraction=float(r["valid_fraction"]),
        threshold=float(r["threshold"]),
        threshold_method=r["threshold_method"],
        area_km2=float(r["area_km2"]),
        area_km2_low=float(r["area_km2_low"]),
        area_km2_high=float(r["area_km2_high"]),
        qa_flag=r["qa_flag"],
    )


def dem_tiles_with_data(tiles: ee.ImageCollection, region: ee.Geometry) -> ee.ImageCollection:
    """DEM tiles with at least one pixel in ``region``.

    ``filterBounds`` on Copernicus GLO-30 also returns polar tiles (``S90_*``) whose
    footprints span all longitudes; their dates must not enter the acquisition window.
    """
    first_band = ee.String(ee.Image(tiles.first()).bandNames().get(0))

    def count(tile: ee.Image) -> ee.Image:
        n = tile.select([first_band]).reduceRegion(ee.Reducer.count(), region, 1000).values()
        return ee.Image(tile.set("pixels_in_region", ee.List(n).get(0)))

    return tiles.map(count).filter(ee.Filter.gt("pixels_in_region", 0))


class EarthEngineReference:
    """Mask, curves and scene areas for one reference reservoir, computed in Earth Engine."""

    def __init__(self, cfg: Config, s: ReferenceSettings, log: Callable[[str], None]):
        """Prepare the flood-fill engine (Copernicus GLO-30) and sensor settings."""
        self.cfg, self.s, self.log = cfg, s, log
        self.extent = extent_inputs(cfg, s)
        self.bounds = search_bounds(
            midpoint(s.closure_axis[0], s.closure_axis[-1]), s.search_radius_km
        )
        self.fill = EarthEngineFill(cfg, self.extent, self.bounds)
        self.s2 = water_s2.s2_settings(cfg)
        self.s1 = water_s1.s1_settings(cfg)
        self.projection = ee.Projection(s.crs).atScale(s.scale_m)
        # Earth Engine cost: profile IDs of each step or batch are resolved right after it
        # (profiles expire); the hook is per thread, so each worker sets its own.
        self.cost = CostMeter()

    # Mask --------------------------------------------------------------------------------

    def build_mask(self) -> tuple[BaseGeometry, list[dict[str, float]]]:
        """Fill the DEM to the mask level from the seed; close rim passes as for the Thwake AOI.

        Raises:
            ValidationError: If the closure line does not hold the reservoir at FSL, or the
                mask reaches the downstream point or the edge of the search square.
        """
        s, e = self.s, self.extent
        if self.fill.leaks(s.fsl_m, []):
            raise ValidationError(
                f"The fill at FSL {s.fsl_m:g} m reaches the downstream check point: the "
                "closure line does not close the reservoir. Check closure_axis."
            )
        closures = close_passes(
            self.fill.leaks,
            self.fill.locate_pass,
            s.fsl_m,
            s.mask_level_m,
            e.pass_level_tolerance_m,
            e.max_pass_closures,
        )
        for c in closures:
            self.log(f"  pass at {c.lat:.5f}, {c.lon:.5f} overflows at ~{c.overflow_level_m:.1f} m")
        geom = self.fill.geometry(self.fill.fill(s.mask_level_m, closures), "Reference mask")
        try:
            check_excludes(geom, s.downstream_point, "Reference mask")
            check_inside(geom, self.bounds, "Reference mask")
        except BaselineError as exc:
            raise ValidationError(str(exc)) from exc
        return geom, [c.as_dict() for c in closures]

    def acquisition_window(self, tiles: ee.ImageCollection, region: ee.Geometry) -> str:
        """``start/end`` dates of the DEM tiles that have data in ``region``."""
        used = dem_tiles_with_data(tiles, region)
        start = ee.Date(used.aggregate_min("system:time_start")).format("YYYY-MM-dd")
        end = ee.Date(used.aggregate_max("system:time_end")).format("YYYY-MM-dd")
        return "/".join(_get_info(ee.List([start, end])))

    # Curves and water surfaces -----------------------------------------------------------

    def curves(
        self, mask: BaseGeometry
    ) -> tuple[dict[str, volume.AEVCurve], dict[str, WaterSurface], dict[str, Any]]:
        """Area–elevation curve, water surface and provenance for each configured DEM."""
        s = self.s
        curves, surfaces, info = {}, {}, {}
        for dem in s.dems:
            self.log(f"  {DEM_LABELS[dem]}: area–elevation curve and water surface ...")
            aev = EarthEngineAEV(self.cfg, dem, mask)
            bins, stats = aev.bins_and_stats(s.mask_level_m, s.level_step_m)
            curves[dem] = volume.curve_from_bins(bins, s.mask_level_m, s.level_step_m, dem)
            mode = _get_info(aev._reduce(aev.dem, ee.Reducer.mode(maxRaw=1_000_000)))["DEM"]
            mode_area = _get_info(
                aev._reduce(
                    ee.Image.pixelArea().updateMask(aev.dem.eq(mode)), ee.Reducer.sum()
                ).get("area")
            )
            surfaces[dem] = water_surface(
                dem,
                float(mode),
                float(mode_area) / volume.M2_PER_KM2,
                stats["mask_area_km2"],
                s.dem_water_surface_min_share,
            )
            info[dem] = {
                "label": DEM_LABELS[dem],
                "collection": self.cfg.ee_collections[
                    {"copernicus_glo30": "copernicus_dem_glo30", "srtm": "srtm"}[dem]
                ],
                "vertical_datum": DEM_VERTICAL_DATUM[dem],
                "acquired": self.acquisition_window(aev.tiles, aev.region),
                "mask_area_km2": round(stats["mask_area_km2"], 2),
                "min_elevation_m": stats["min_elevation_m"],
                "water_surface_m": surfaces[dem].level_m,
                "water_surface_area_km2": round(surfaces[dem].area_km2, 2),
                "water_surface_share_of_mask": round(surfaces[dem].share, 3),
            }
        return curves, surfaces, info

    # Scenes ------------------------------------------------------------------------------

    def _collections(
        self, region: ee.Geometry, start: str, end: str
    ) -> dict[str, ee.ImageCollection]:
        s2 = water_s2.daily_mosaics(self.cfg, region, start, end, self.s2.cloud_score_min)
        s1 = water_s1.daily_mosaics(self.cfg, region, start, end, self.s1)
        return {
            "S2": s2.map(lambda im: im.set("key", im.get("date")).set("orbit", "")),
            "S1": s1.map(
                lambda im: im.set("key", ee.String(im.get("date")).cat("_").cat(im.get("orbit")))
            ),
        }

    def scene_areas(self, mask: BaseGeometry) -> tuple[list[SceneArea], dict[str, Any]]:
        """Water area of every scene of both sensors in the window.

        Scenes are processed in batches of consecutive days; each batch builds the mosaics
        of its own date range only (filtering one collection of all mosaics by key makes
        Earth Engine rebuild every mosaic per request). Batches run in parallel.
        """
        s = self.s
        mask_ee = _ee_geometry(mask)
        region = ee.Geometry.Rectangle(list(mask.bounds), None, False)
        hist_region = _ee_geometry(buffer_metres(mask, s.otsu_buffer_m, s.crs))
        mask_img = ee.Image(0).byte().paint(ee.FeatureCollection([ee.Feature(mask_ee)]), 1)
        out: list[SceneArea] = []
        info: dict[str, Any] = {}
        fingerprint = self.fingerprint(mask)
        for sensor in SENSORS:
            if sensor == "S2":
                keys = water_s2.scene_keys(self.cfg, region, s.scene_start, s.scene_end)
            else:
                keys = water_s1.scene_keys(self.cfg, region, s.scene_start, s.scene_end, self.s1)
            checkpoint = self.checkpoint_path(sensor)
            saved = read_checkpoint(checkpoint, fingerprint)
            if saved is not None:
                scenes, saved_info = saved
                self.log(f"  {sensor}: {len(scenes)} scenes reused from {_display(checkpoint)}")
                out.extend(scenes)
                info[sensor] = saved_info | {"reused_from_checkpoint": True}
                continue
            self.log(f"  {sensor}: {len(keys)} scenes ...")
            sensor_out: list[SceneArea] = []
            batches = [keys[i : i + BATCH] for i in range(0, len(keys), BATCH)]
            done = 0
            no_data = 0
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                jobs = [
                    pool.submit(self._retrying_batch, sensor, b, mask_img, region, hist_region)
                    for b in batches
                ]
                for job in as_completed(jobs):
                    scenes, missing = job.result()
                    sensor_out.extend(scenes)
                    no_data += missing
                    done += 1
                    self.log(f"    batch {done}/{len(batches)}")
            info[sensor] = {"scenes_found": len(keys), "scenes_without_valid_pixels": no_data}
            write_checkpoint(checkpoint, fingerprint, sensor_out, info[sensor])
            out.extend(sensor_out)
        return out, info

    def fingerprint(self, mask: BaseGeometry) -> str:
        """Hash of everything that determines the scene areas (for reusing checkpoints)."""
        s = self.s
        content = {
            "window": [s.scene_start, s.scene_end],
            "mask_area_km2": round(area_km2(mask), 4),
            "grid": [s.crs, s.scale_m],
            "otsu_buffer_m": s.otsu_buffer_m,
            "edge_fraction": s.edge_fraction,
            "s2": vars(self.s2),
            "s1": vars(self.s1),
            "collections": [
                self.cfg.ee_collections[k]
                for k in ("sentinel2_sr", "cloud_score_plus", "sentinel1_grd")
            ],
            "method_version": METHOD_VERSION,
        }
        text = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def checkpoint_path(self, sensor: str) -> Path:
        """Per-sensor checkpoint next to the scenes CSV (git-ignored, deleted after a run)."""
        scenes = self.s.paths["scenes"]
        return scenes.with_name(f".{scenes.stem}_{sensor}.checkpoint.json")

    def _retrying_batch(self, *args: Any) -> tuple[list[SceneArea], int]:
        """:meth:`_batch`, retried with backoff when Earth Engine reports too many requests."""
        for attempt in range(RETRIES):
            ids: list[str] = []
            try:
                with ee.data.profiling(ids.append):
                    result = self._batch(*args)
                self.cost.add(ids)
                return result
            except ee.EEException as exc:
                self.cost.add(ids)
                if "Too many" not in str(exc) or attempt == RETRIES - 1:
                    raise
                time.sleep(RETRY_WAIT_S * 2**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _batch(
        self,
        sensor: str,
        batch: list[str],
        mask_img: ee.Image,
        region: ee.Geometry,
        hist_region: ee.Geometry,
    ) -> tuple[list[SceneArea], int]:
        """Areas of the scenes in one batch of keys (consecutive days)."""
        end = date.fromisoformat(batch[-1][:10]).toordinal() + 1
        coll = self._collections(region, batch[0][:10], date.fromordinal(end).isoformat())
        part = coll[sensor].filter(ee.Filter.inList("key", batch))
        settings = self.s2 if sensor == "S2" else self.s1
        fallback = self.s2.fallback_threshold if sensor == "S2" else self.s1.fixed_threshold_db
        thresholds = {}
        for key, h in self._histograms(part, hist_region, sensor).items():
            if not h or sum(c for _, c in h) == 0:
                continue
            counts, edges = [c for _, c in h], [e for e, _ in h]
            thresholds[key] = choose_threshold(counts, edges, fallback, settings.otsu_valid_range)
        out = []
        missing = len(batch) - len(thresholds)
        for key, (meta, d) in self._sums(part, thresholds, mask_img, region, sensor).items():
            if d["mask_m2"] <= 0 or d["valid_m2"] <= 0:
                missing += 1
                continue
            r = area_mod.area_range(
                min(d["water_m2"], d["valid_m2"]),
                d["valid_m2"],
                d["mask_m2"],
                min(d["edge_m2"], d["water_m2"]),
                self.s.edge_fraction,
            )
            t = thresholds[key]
            out.append(
                SceneArea(
                    date=date.fromisoformat(meta["date"]),
                    sensor=sensor,
                    orbit=meta.get("orbit") or "",
                    scene_id=str(meta["scene_id"]),
                    parts=int(meta["parts"]),
                    valid_fraction=r.valid_fraction,
                    threshold=t.value,
                    threshold_method=t.method,
                    area_km2=r.best_km2,
                    area_km2_low=r.low_km2,
                    area_km2_high=r.high_km2,
                    qa_flag=qa_flag(r.valid_fraction, self.s2.min_valid_fraction),
                )
            )
        return out, missing

    def _histograms(
        self, part: ee.ImageCollection, region: ee.Geometry, sensor: str
    ) -> dict[str, list[list[float]]]:
        if sensor == "S2":
            fn = lambda im: water_s2.index_histogram(im, region, self.s2)  # noqa: E731
        else:
            fn = lambda im: water_s1.vv_histogram(im, region, self.s1)  # noqa: E731
        fc = part.map(lambda im: ee.Feature(None, {"key": im.get("key"), "hist": fn(im)}))
        return {f["properties"]["key"]: f["properties"]["hist"] for f in _get_info(fc)["features"]}

    def _sums(
        self,
        part: ee.ImageCollection,
        thresholds: Mapping[str, Any],
        mask_img: ee.Image,
        region: ee.Geometry,
        sensor: str,
    ) -> dict[str, tuple[dict[str, Any], dict[str, float]]]:
        if not thresholds:
            return {}
        values = ee.Dictionary({k: t.value for k, t in thresholds.items()})
        part = part.filter(ee.Filter.inList("key", list(thresholds)))
        to_water = water_s2.water_mask if sensor == "S2" else water_s1.water_mask

        def reduce(im: ee.Image) -> ee.Feature:
            water = to_water(im, ee.Number(values.get(im.get("key"))))
            sums = area_mod.water_pixel_sums(water, mask_img, region, self.projection)
            parts = im.get("granules") if sensor == "S2" else im.get("slices")
            return ee.Feature(
                None,
                {
                    "key": im.get("key"),
                    "date": im.get("date"),
                    "orbit": im.get("orbit"),
                    "scene_id": im.get("scene_id"),
                    "parts": parts,
                    "sums": sums,
                },
            )

        out = {}
        for f in _get_info(part.map(reduce))["features"]:
            p = f["properties"]
            sums = {
                k: float(p["sums"].get(k) or 0.0)
                for k in ("water_m2", "valid_m2", "mask_m2", "edge_m2")
            }
            out[p["key"]] = (p, sums)
        return out


@dataclass(frozen=True)
class ReferenceResult:
    """Outputs of the Earth Engine stage."""

    mask_area_km2: float
    scenes: list[SceneArea]
    metadata: dict[str, Any]


def build_reference(cfg: Config, name: str, log: Callable[[str], None] = print) -> ReferenceResult:
    """Earth Engine stage: mask, curves, water surfaces and scene areas; writes their files.

    Earth Engine must already be initialised.

    Raises:
        ValidationError: If a check fails (see :meth:`EarthEngineReference.build_mask`).
        ConfigError: If the configuration is incomplete.
    """
    s = reference_settings(cfg, name)
    engine = EarthEngineReference(cfg, s, log)
    started = time.monotonic()
    ids: list[str] = []
    with ee.data.profiling(ids.append):
        log(f"{s.name}: max-extent mask at {s.mask_level_m:g} m (GLO-30 fill from the seed) ...")
        mask, closures = engine.build_mask()
        mask_area = area_km2(mask)
        log(f"  mask {mask_area:.2f} km²")
        curves, surfaces, dem_info = engine.curves(mask)
    engine.cost.add(ids)
    log("Scenes: water masks and areas (this takes a while) ...")
    ids = []
    with ee.data.profiling(ids.append):
        scenes, scene_info = engine.scene_areas(mask)
    engine.cost.add(ids)
    wall_s = time.monotonic() - started
    eecu = engine.cost.eecu_s
    log(
        f"Cost: {eecu:,.0f} EECU-seconds ({eecu / 3600:.2f} EECU-hours) over "
        f"{engine.cost.requests} requests ({engine.cost.unresolved} unresolved), "
        f"wall time {wall_s / 60:.0f} min"
    )

    generated = datetime.now(UTC).date().isoformat()
    wall = extend_line(s.closure_axis, engine.extent.abutment_extension_m)
    mask_props = {
        "name": f"{s.name} max extent (validation)",
        "description": "Copernicus GLO-30 pixels at or below the mask level, connected to the "
        "reservoir seed, behind the digitised closure line. Water outside this mask is never "
        "counted. The DEM postdates the dam: below its flat lake surface it shows water, not "
        "the reservoir bed.",
        "level_m_asl": s.mask_level_m,
        "area_km2": round(mask_area, 2),
        "closure_axis": [[round(x, 5), round(y, 5)] for x, y in s.closure_axis],
        "closure_axis_length_m": round(line_length_m(s.closure_axis)),
        "closure_axis_source": s.closure_axis_source,
        "closure_barrier": {
            "half_width_m": engine.extent.barrier_half_width_m,
            "abutment_extension_m": engine.extent.abutment_extension_m,
            "ends": [[round(x, 5), round(y, 5)] for x, y in (wall[0], wall[-1])],
        },
        "pass_closures": closures,
        "reservoir_seed": list(s.seed),
        "downstream_check_point": list(s.downstream_point),
        "dem": cfg.ee_collections["copernicus_dem_glo30"],
        "method": METHOD_REF,
        "method_version": METHOD_VERSION,
        "generated": generated,
    }
    write_geojson(s.paths["mask"], feature_collection(polygonal(mask), mask_props))
    volume.write_aev_csv(s.paths["aev"], curves.values())
    write_scenes_csv(s.paths["scenes"], scenes)
    metadata = {
        "reservoir": s.key,
        "name": s.name,
        "method": METHOD_REF,
        "method_version": METHOD_VERSION,
        "generated": generated,
        "mask_level_m_asl": s.mask_level_m,
        "mask_area_km2": round(mask_area, 2),
        "dems": dem_info,
        "scene_window": {"start": s.scene_start, "end_exclusive": s.scene_end},
        "scenes": scene_info,
        "cost": {
            "eecu_seconds": round(eecu),
            "eecu_hours": round(eecu / 3600, 2),
            "wall_time_min": round(wall_s / 60, 1),
            "requests_profiled": engine.cost.requests,
            "requests_unresolved": engine.cost.unresolved,
            "note": "Sum of the Earth Engine profiles of every request of this run "
            "(interactive compute, not batch tasks). Scenes reused from a checkpoint "
            "(scenes.<sensor>.reused_from_checkpoint) were computed, and paid for, in an "
            "earlier run.",
        },
        "analysis_grid": {"crs": s.crs, "scale_m": s.scale_m},
        "otsu_histogram_region": f"mask + {s.otsu_buffer_m:g} m ring",
        "parameters": {
            "sentinel2": {k: v for k, v in vars(engine.s2).items() if not k.startswith("_")},
            "sentinel1": {k: v for k, v in vars(engine.s1).items() if not k.startswith("_")},
            "edge_ring_pixels": s.edge_fraction,
            "min_valid_fraction": engine.s2.min_valid_fraction,
        },
        "collections": {
            k: cfg.ee_collections[k] for k in ("sentinel2_sr", "cloud_score_plus", "sentinel1_grd")
        },
    }
    write_json(s.paths["scenes_metadata"], metadata)
    for sensor in SENSORS:
        engine.checkpoint_path(sensor).unlink(missing_ok=True)
    for key in ("mask", "aev", "scenes", "scenes_metadata"):
        log(f"  -> {_display(s.paths[key])}")
    return ReferenceResult(mask_area, scenes, metadata)


# --- Comparison stage -------------------------------------------------------------------


@dataclass(frozen=True)
class ComparisonResult:
    """Outputs of the comparison stage."""

    rows: list[dict[str, Any]]
    metrics: dict[str, Any]


def _surfaces_from_metadata(meta: Mapping[str, Any]) -> dict[str, WaterSurface]:
    out = {}
    for dem, d in meta["dems"].items():
        out[dem] = WaterSurface(
            dem,
            d["water_surface_m"],
            d["water_surface_area_km2"],
            d["water_surface_share_of_mask"],
        )
    return out


def compare_reference(
    cfg: Config, name: str, log: Callable[[str], None] = print, plot: bool = True
) -> ComparisonResult:
    """Comparison stage (no Earth Engine): levels, matching, metrics, CSV/JSON and figure.

    Reads the files written by :func:`build_reference`.

    Raises:
        ValidationError: If an input file is missing or malformed.
    """
    s = reference_settings(cfg, name)
    for key in ("aev", "scenes_metadata"):
        if not s.paths[key].is_file():
            raise ValidationError(
                f"{_display(s.paths[key])} not found: run `thwake validate reference --name "
                f"{name}` without --compare-only first"
            )
    meta = json.loads(s.paths["scenes_metadata"].read_text(encoding="utf-8"))
    curves = volume.read_aev_csv(s.paths["aev"])
    surfaces = _surfaces_from_metadata(meta)
    scenes = read_scenes_csv(s.paths["scenes"])
    published = read_published(s.paths["published_figures"], name)
    targets, context = published_levels(published, s.scene_start, s.scene_end)
    altimetry: list[PublishedLevel] = []
    alt_path = s.altimetry_path
    altimetry_missing = alt_path is not None and not alt_path.is_file()
    if alt_path is not None and not altimetry_missing:
        altimetry = read_altimetry(alt_path)
    elif alt_path is not None:
        log(f"  altimetry series configured but not found ({_display(alt_path)}): skipped")
    rated = altimetry or None

    series = series_rows(scenes, curves, surfaces)
    rows = comparison_rows(
        targets, scenes, curves, surfaces, s.match_window_days, rated, s.rapid_change_m_per_day
    )
    alt_rows = comparison_rows(
        altimetry, scenes, curves, surfaces, s.match_window_days, rated, s.rapid_change_m_per_day
    )
    series_cols = list(SCENE_COLUMNS) + [
        f"{p}_{dem}"
        for dem in curves
        for p in ("level_m", "level_m_low", "level_m_high", "level_status")
    ]
    write_rows_csv(s.paths["series"], series_cols, series)
    write_rows_csv(s.paths["comparison"], COMPARISON_COLUMNS, rows + alt_rows)

    low_conf = [
        {"item": r["item"], "value": r["value"], "value_date": r.get("value_date", "")}
        for r in published
        if r.get("confidence") not in HEADLINE_CONFIDENCE
    ]
    metrics = {
        "reservoir": s.key,
        "name": s.name,
        "method": METHOD_REF,
        "method_version": METHOD_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
        "headline_rule": "Rows with status 'ok' and a high/medium-confidence published level. "
        f"A scene is matched if within {s.match_window_days} days of the published date.",
        "published_figures": _display(s.paths["published_figures"]),
        "dem_water_surfaces": {
            dem: {
                "level_m": surf.level_m,
                "area_km2": round(surf.area_km2, 2),
                "acquired": meta["dems"][dem]["acquired"],
                "vertical_datum": meta["dems"][dem]["vertical_datum"],
            }
            for dem, surf in surfaces.items()
        },
        "convertibility": convertibility_table(targets, context, surfaces),
        "gauge": summarise(rows, "published"),
        "rapid_change_rule": "Rows where the level changed by ≥ "
        f"{s.rapid_change_m_per_day:g} m/day around the date (from the altimetry series if "
        "configured, else from the targets) are "
        "flagged rapid_change; metrics are also given without them.",
        "altimetry": altimetry_block(s, altimetry, alt_rows, targets, surfaces, altimetry_missing),
        "area_at_fsl": area_at_fsl_check(
            rows, published_item(published, "surface_area_at_fsl"), curves, s.fsl_m
        ),
        "volume": "Not compared: the reservoir predates both DEMs (no pre-dam DEM), so "
        "storage below each DEM's water surface is unknown.",
        "low_confidence_figures": low_conf,
        "scene_counts": {
            sensor: {
                "total": sum(1 for x in scenes if x.sensor == sensor),
                "usable": sum(1 for x in scenes if x.sensor == sensor and x.usable),
                "fallback_threshold": sum(
                    1 for x in scenes if x.sensor == sensor and x.threshold_method == "fallback"
                ),
            }
            for sensor in SENSORS
        },
    }
    write_json(s.paths["metrics"], metrics)
    if plot:
        from thwake import export

        export.plot_validation_reference(
            series, rows, alt_rows, targets, surfaces, list(curves), s, s.paths["figure"]
        )
    for key in ("series", "comparison", "metrics", *(("figure",) if plot else ())):
        log(f"  -> {_display(s.paths[key])}")
    return ComparisonResult(rows + alt_rows, metrics)


def altimetry_block(
    s: ReferenceSettings,
    altimetry: Sequence[PublishedLevel],
    alt_rows: Sequence[Mapping[str, Any]],
    gauge: Sequence[PublishedLevel],
    surfaces: Mapping[str, WaterSurface],
    missing: bool,
) -> dict[str, Any]:
    """Metrics entry for the altimetry series: label, coverage, our agreement, gauge check."""
    if not altimetry:
        return {
            "source": _display(s.altimetry_path) if s.altimetry_path else None,
            "note": (
                "Configured but the file is not present (raw downloads are not committed)."
                if missing
                else "Not configured. Set reference_reservoirs.<name>.altimetry.path in "
                "config/validation.yaml (DAHITI download or date,level_m,level_error_m)."
            ),
        }
    lo, hi = date.fromisoformat(s.scene_start), date.fromisoformat(s.scene_end)
    in_window = [a for a in altimetry if lo <= a.start < hi]
    vs_gauge = cross_check(gauge, altimetry, s.match_window_days)
    return {
        "label": s.altimetry_label,
        "citation": s.altimetry_citation,
        "source": f"{_display(s.altimetry_path or Path())} (raw file not committed)",
        "points": len(altimetry),
        "period": f"{altimetry[0].start.isoformat()}/{altimetry[-1].start.isoformat()}",
        "points_in_scene_window": len(in_window),
        "points_convertible": {
            dem: sum(1 for a in in_window if surf.convertible(a.level_m))
            for dem, surf in surfaces.items()
        },
        "our_levels_vs_altimetry": summarise(alt_rows, "altimetry", headline_only=False),
        "altimetry_vs_gauge": {
            "note": f"Nearest altimetry point within {s.match_window_days} days of each "
            "published gauge level; difference = altimetry − gauge. Neither is corrected for "
            "datum.",
            "pairs": vs_gauge,
            "metrics": absolute_metrics([r["difference_m"] for r in vs_gauge if r["headline"]]),
        },
    }


def comparison_summary(result: ComparisonResult) -> str:
    """Terminal report: the headline metrics per sensor and DEM."""
    lines = ["Agreement with published gauge levels (ours − published):"]
    for key, m in result.metrics["gauge"].items():
        a, r = m["absolute"], m["relative"]
        if a["n"] == 0:
            lines.append(f"  {key}: no comparable dates ({m['rows_by_status']})")
            continue
        rel = f"changes RMSE {r['rmse_m']} m (n={r['n']})" if r["n"] else "no changes"
        lines.append(
            f"  {key}: n={a['n']}, bias {a['bias_m']:+} m, RMSE {a['rmse_m']} m, "
            f"SD {a['sd_m']} m; {rel}"
        )
    return "\n".join(lines)
