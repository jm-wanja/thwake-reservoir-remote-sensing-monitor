"""Sentinel-2 water mask: MNDWI, Otsu threshold with a fixed fallback.

Method: docs/methodology.md §2.1; ADR 0005. Built for the reference-reservoir validation
(prompt 05a) and extended, not rewritten, by Phase 2 (prompt 06).

1. Scenes: Sentinel-2 L2A, Cloud Score+ masked (``sentinel2.cloud_score_plus_threshold``),
   all granules of one day mosaicked into one image (:func:`daily_mosaics`).
2. Index: MNDWI = (Green − SWIR1) / (Green + SWIR1) = (B3 − B11) / (B3 + B11). NDWI (B3, B8)
   is available for comparison.
3. Threshold: Otsu on a fixed-bin MNDWI histogram over the histogram region (the max extent
   plus a land ring, so both classes are present), computed by :func:`index_histogram` and
   solved client side by :func:`thwake.otsu.choose_threshold`. Falls back to
   ``sentinel2.fallback_threshold`` when Otsu fails or is implausible.
4. Water = MNDWI > threshold (:func:`water_mask`). Cloud-masked pixels stay masked so their
   area enters the uncertainty range (:mod:`thwake.area`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import ee

from thwake.baseline import _number, _require
from thwake.collections import sentinel2_clear
from thwake.config import Config, ConfigError
from thwake.otsu import histogram_bins

GREEN, NIR, SWIR1 = "B3", "B8", "B11"
INDEX_BAND = "MNDWI"
DAY_MS = 86_400_000


@dataclass(frozen=True)
class S2Settings:
    """Sentinel-2 water-mask parameters, from ``config/thresholds.yaml`` ``sentinel2``."""

    cloud_score_min: float
    fallback_threshold: float
    otsu_valid_range: tuple[float, float]
    histogram_range: tuple[float, float]
    histogram_bin_width: float
    histogram_scale_m: float
    min_valid_fraction: float

    @property
    def bins(self) -> list[float]:
        """Lower edges of the MNDWI histogram bins."""
        return histogram_bins(*self.histogram_range, self.histogram_bin_width)


def _pair(section: dict, key: str, where: str) -> tuple[float, float]:
    value = _require(section, key, where)
    if not isinstance(value, list) or len(value) != 2 or not value[0] < value[1]:
        raise ConfigError(f"'{key}' in {where} must be [low, high] with low < high")
    return float(value[0]), float(value[1])


def s2_settings(cfg: Config) -> S2Settings:
    """Read and validate the Sentinel-2 water-mask parameters.

    Raises:
        ConfigError: If a value is missing or malformed, or the index is not MNDWI.
    """
    s2 = cfg.thresholds.get("sentinel2") or {}
    where = "thresholds.yaml sentinel2"
    if s2.get("water_index") != INDEX_BAND or s2.get("threshold_method") != "otsu":
        raise ConfigError(f"{where}: only water_index MNDWI with threshold_method otsu exist")
    return S2Settings(
        cloud_score_min=_number(s2, "cloud_score_plus_threshold", where),
        fallback_threshold=_number(s2, "fallback_threshold", where, positive=False),
        otsu_valid_range=_pair(s2, "otsu_valid_range", where),
        histogram_range=_pair(s2, "histogram_range", where),
        histogram_bin_width=_number(s2, "histogram_bin_width", where),
        histogram_scale_m=_number(s2, "histogram_scale_m", where),
        min_valid_fraction=_number(s2, "min_valid_fraction", where),
    )


def mndwi(image: ee.Image) -> ee.Image:
    """MNDWI = (B3 − B11) / (B3 + B11), band ``MNDWI``."""
    return image.normalizedDifference([GREEN, SWIR1]).rename(INDEX_BAND)


def ndwi(image: ee.Image) -> ee.Image:
    """NDWI = (B3 − B8) / (B3 + B8), band ``NDWI`` (for comparison only)."""
    return image.normalizedDifference([GREEN, NIR]).rename("NDWI")


def water_mask(index: ee.Image, threshold: float | ee.Number) -> ee.Image:
    """1 where the index exceeds ``threshold``, else 0; masked where the index is masked."""
    return index.gt(ee.Number(threshold)).rename("water")


def daily_mosaics(
    cfg: Config, region: ee.Geometry, start: str, end: str, cloud_score_min: float
) -> ee.ImageCollection:
    """One cloud-masked Sentinel-2 mosaic per acquisition day, as MNDWI.

    Each image keeps ``system:time_start`` (start of the UTC day), ``date`` (``YYYY-MM-dd``),
    ``granules`` (number of granules mosaicked) and ``scene_id`` (the first granule's ID).
    """
    scenes = sentinel2_clear(cfg, region, start, end, cloud_score_min)
    days = scenes.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd")
    )

    def mosaic(day: ee.String) -> ee.Image:
        start_day = ee.Date(day)
        same_day = scenes.filterDate(start_day, start_day.advance(1, "day"))
        return ee.Image(
            mndwi(same_day.mosaic())
            .set("system:time_start", start_day.millis())
            .set("date", day)
            .set("granules", same_day.size())
            .set("scene_id", same_day.first().get("system:index"))
        )

    return ee.ImageCollection(days.distinct().map(mosaic))


def scene_keys(cfg: Config, region: ee.Geometry, start: str, end: str) -> list[str]:
    """Acquisition days (``YYYY-MM-dd``) with Sentinel-2 L2A granules over ``region``.

    Read from granule metadata only (no mosaics are built), so it stays cheap over years.
    These are the keys of :func:`daily_mosaics`.
    """
    times = (
        ee.ImageCollection(cfg.ee_collections["sentinel2_sr"])
        .filterBounds(region)
        .filterDate(start, end)
        .aggregate_array("system:time_start")
        .getInfo()
    )
    return sorted({datetime.fromtimestamp(t / 1000, UTC).date().isoformat() for t in times or []})


def index_histogram(index: ee.Image, region: ee.Geometry, settings: S2Settings) -> ee.List:
    """Fixed-bin MNDWI histogram over ``region``: a list of ``[lower edge, count]``."""
    low, high = settings.histogram_range
    n = len(settings.bins)
    hist = index.reduceRegion(
        reducer=ee.Reducer.fixedHistogram(low, high, n),
        geometry=region,
        scale=settings.histogram_scale_m,
        maxPixels=1_000_000_000,
    )
    return ee.List(ee.Algorithms.If(hist.get(INDEX_BAND), hist.get(INDEX_BAND), ee.List([])))
