"""Sentinel-1 water mask: speckle filter, VV backscatter, Otsu or fixed dB threshold.

Method: docs/methodology.md §2.2; ADR 0005. Built for the reference-reservoir validation
(prompt 05a) and extended, not rewritten, by Phase 2 (prompt 06).

1. Scenes: Sentinel-1 GRD, IW mode, VV (Earth Engine serves it as calibrated,
   terrain-corrected backscatter in dB). Both orbit directions are used; slices of the same
   day and orbit pass are mosaicked (:func:`daily_mosaics`).
2. Speckle filter: focal median (``sentinel1.speckle_filter_radius_m``).
3. Threshold: Otsu on a fixed-bin VV histogram over the histogram region (see
   :mod:`thwake.water_s2`), falling back to ``sentinel1.fixed_threshold_db`` (−18 dB, the
   value used in GERD studies) when Otsu fails or is implausible.
4. Water = VV < threshold (calm water reflects the radar away from the sensor).

Not yet handled (Phase 2): wind-roughened water (missed water) and radar shadow on steep
slopes (false water; ``sentinel1.max_slope_deg``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import ee

from thwake.baseline import _number, _require
from thwake.config import Config, ConfigError
from thwake.otsu import histogram_bins
from thwake.water_s2 import _pair

BAND = "VV"
SPECKLE_FILTERS = ("focal_median",)


@dataclass(frozen=True)
class S1Settings:
    """Sentinel-1 water-mask parameters, from ``config/thresholds.yaml`` ``sentinel1``."""

    instrument_mode: str
    fixed_threshold_db: float
    speckle_filter: str
    speckle_filter_radius_m: float
    otsu_valid_range: tuple[float, float]
    histogram_range: tuple[float, float]
    histogram_bin_width: float
    histogram_scale_m: float

    @property
    def bins(self) -> list[float]:
        """Lower edges of the VV histogram bins (dB)."""
        return histogram_bins(*self.histogram_range, self.histogram_bin_width)


def s1_settings(cfg: Config) -> S1Settings:
    """Read and validate the Sentinel-1 water-mask parameters.

    Raises:
        ConfigError: If a value is missing or malformed, or an option is not implemented.
    """
    s1 = cfg.thresholds.get("sentinel1") or {}
    where = "thresholds.yaml sentinel1"
    if s1.get("polarisation") != BAND or s1.get("threshold_method") != "otsu":
        raise ConfigError(f"{where}: only polarisation VV with threshold_method otsu exist")
    speckle = _require(s1, "speckle_filter", where)
    if speckle not in SPECKLE_FILTERS:
        raise ConfigError(f"{where}: speckle_filter must be one of {SPECKLE_FILTERS}")
    return S1Settings(
        instrument_mode=str(_require(s1, "instrument_mode", where)),
        fixed_threshold_db=_number(s1, "fixed_threshold_db", where, positive=False),
        speckle_filter=str(speckle),
        speckle_filter_radius_m=_number(s1, "speckle_filter_radius_m", where),
        otsu_valid_range=_pair(s1, "otsu_valid_range", where),
        histogram_range=_pair(s1, "histogram_range", where),
        histogram_bin_width=_number(s1, "histogram_bin_width", where),
        histogram_scale_m=_number(s1, "histogram_scale_m", where),
    )


def speckle_filter(image: ee.Image, radius_m: float) -> ee.Image:
    """Focal median of VV over a circle of ``radius_m``."""
    return image.focalMedian(radius_m, "circle", "meters").rename(BAND)


def water_mask(vv: ee.Image, threshold_db: float | ee.Number) -> ee.Image:
    """1 where VV is below ``threshold_db``, else 0; masked where VV is masked."""
    return vv.lt(ee.Number(threshold_db)).rename("water")


def daily_mosaics(
    cfg: Config, region: ee.Geometry, start: str, end: str, settings: S1Settings
) -> ee.ImageCollection:
    """One speckle-filtered VV mosaic per day and orbit pass.

    Each image keeps ``system:time_start`` (start of the UTC day), ``date``, ``orbit``
    (``ASCENDING`` / ``DESCENDING``), ``slices`` (number mosaicked) and ``scene_id``.
    """
    scenes = (
        ee.ImageCollection(cfg.ee_collections["sentinel1_grd"])
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", settings.instrument_mode))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", BAND))
        .select(BAND)
    )
    keys = scenes.map(
        lambda im: im.set(
            "day_orbit",
            ee.Date(im.get("system:time_start"))
            .format("YYYY-MM-dd")
            .cat("_")
            .cat(im.get("orbitProperties_pass")),
        )
    )

    def mosaic(key: ee.String) -> ee.Image:
        parts = ee.String(key).split("_")
        group = keys.filter(ee.Filter.eq("day_orbit", key))
        # Filter each slice before mosaicking, so the median never mixes slices.
        filtered = group.map(lambda im: speckle_filter(im, settings.speckle_filter_radius_m))
        return ee.Image(
            filtered.mosaic()
            .set("system:time_start", ee.Date(parts.get(0)).millis())
            .set("date", parts.get(0))
            .set("orbit", parts.get(1))
            .set("slices", group.size())
            .set("scene_id", group.first().get("system:index"))
        )

    return ee.ImageCollection(keys.aggregate_array("day_orbit").distinct().map(mosaic))


def scene_keys(
    cfg: Config, region: ee.Geometry, start: str, end: str, settings: S1Settings
) -> list[str]:
    """Day-and-pass keys (``YYYY-MM-dd_ASCENDING``) of Sentinel-1 VV scenes over ``region``.

    Read from scene metadata only (no mosaics are built), so it stays cheap over years.
    These are the keys of :func:`daily_mosaics`, with ``_`` joining day and pass.
    """
    scenes = (
        ee.ImageCollection(cfg.ee_collections["sentinel1_grd"])
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", settings.instrument_mode))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", BAND))
    )
    info = ee.Dictionary(
        {
            "t": scenes.aggregate_array("system:time_start"),
            "pass": scenes.aggregate_array("orbitProperties_pass"),
        }
    ).getInfo() or {"t": [], "pass": []}
    return sorted(
        {
            f"{datetime.fromtimestamp(t / 1000, UTC).date().isoformat()}_{orbit}"
            for t, orbit in zip(info["t"], info["pass"], strict=True)
        }
    )


def vv_histogram(vv: ee.Image, region: ee.Geometry, settings: S1Settings) -> ee.List:
    """Fixed-bin VV histogram (dB) over ``region``: a list of ``[lower edge, count]``."""
    low, high = settings.histogram_range
    hist = vv.reduceRegion(
        reducer=ee.Reducer.fixedHistogram(low, high, len(settings.bins)),
        geometry=region,
        scale=settings.histogram_scale_m,
        maxPixels=1_000_000_000,
    )
    return ee.List(ee.Algorithms.If(hist.get(BAND), hist.get(BAND), ee.List([])))
