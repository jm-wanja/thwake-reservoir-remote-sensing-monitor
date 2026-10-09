"""Fetch and filter S1, S2, CHIRPS and ERA5 for the AOI and date range.

Also applies Sentinel-2 cloud masking. So far the baseline DEMs (Copernicus GLO-30, SRTM)
and Cloud Score+ masked Sentinel-2 scenes (for the pre-filling composite) are implemented;
the Phase 2 scene filters follow in prompt 06. See docs/architecture.md §3B and
docs/methodology.md §2.1–2.2.
"""

from __future__ import annotations

import ee

from thwake.config import Config

DEM_BAND = "DEM"
SRTM_BAND = "elevation"
# Short DEM names (used as ``dem_source`` in the AEV curve) → keys in ee_collections.yaml.
DEM_COLLECTION_KEYS = {"copernicus_glo30": "copernicus_dem_glo30", "srtm": "srtm"}
DEM_LABELS = {"copernicus_glo30": "Copernicus GLO-30", "srtm": "SRTM"}
# Vertical reference of each DEM's heights, from the dataset documentation.
DEM_VERTICAL_DATUM = {"copernicus_glo30": "EGM2008", "srtm": "EGM96"}


def copernicus_dem(cfg: Config, region: ee.Geometry) -> tuple[ee.Image, ee.ImageCollection]:
    """Copernicus GLO-30 elevation (m) over ``region``, in the tiles' native projection.

    The collection is a set of 1°×1° tiles; the mosaic is given the first tile's projection
    (EPSG:4326, 1 arc-second) so that pixel-based operations run on the native grid.

    Args:
        cfg: Loaded configuration (collection ID from ``ee_collections.yaml``).
        region: Area the DEM must cover.

    Returns:
        The single-band ``DEM`` image and the filtered tile collection (for metadata such as
        acquisition dates).
    """
    tiles = (
        ee.ImageCollection(cfg.ee_collections["copernicus_dem_glo30"])
        .filterBounds(region)
        .select(DEM_BAND)
    )
    projection = tiles.first().projection()
    dem = tiles.mosaic().setDefaultProjection(projection).reproject(projection)
    return dem, tiles


def srtm_dem(cfg: Config) -> tuple[ee.Image, ee.ImageCollection]:
    """SRTM 1 arc-second elevation (m), band renamed ``DEM``, in its native projection.

    SRTM is a single global image (acquired Feb 2000). Its dates are stored in a
    ``date_range`` property rather than ``system:time_start/end``; they are copied there and
    the image is wrapped in a one-image collection, so callers read acquisition dates the
    same way as for GLO-30.

    Args:
        cfg: Loaded configuration (image ID from ``ee_collections.yaml``).

    Returns:
        The single-band ``DEM`` image and a one-image collection holding it.
    """
    image = ee.Image(cfg.ee_collections["srtm"])
    dates = ee.List(image.get("date_range"))
    image = image.set({"system:time_start": dates.get(0), "system:time_end": dates.get(1)})
    projection = image.select(SRTM_BAND).projection()
    dem = image.select([SRTM_BAND], [DEM_BAND]).reproject(projection)
    return dem, ee.ImageCollection([image])


def dem_by_name(cfg: Config, name: str, region: ee.Geometry) -> tuple[ee.Image, ee.ImageCollection]:
    """Pre-dam DEM by short name (a key of :data:`DEM_COLLECTION_KEYS`).

    Raises:
        KeyError: If the name is unknown.
    """
    if name == "copernicus_glo30":
        return copernicus_dem(cfg, region)
    if name == "srtm":
        return srtm_dem(cfg)
    raise KeyError(f"Unknown DEM {name!r}; expected one of {sorted(DEM_COLLECTION_KEYS)}")


def sentinel2_clear(
    cfg: Config, region: ee.Geometry, start: str, end: str, cs_min: float
) -> ee.ImageCollection:
    """Sentinel-2 L2A scenes over ``region`` with cloudy pixels masked by Cloud Score+.

    Each scene is linked to its Cloud Score+ image; pixels with ``cs`` below ``cs_min`` are
    masked in every band.

    Args:
        cfg: Loaded configuration (collection IDs from ``ee_collections.yaml``).
        region: Area the scenes must intersect.
        start: First date (inclusive), ``YYYY-MM-DD``.
        end: Last date (exclusive), ``YYYY-MM-DD``.
        cs_min: Minimum Cloud Score+ ``cs`` (0–1) for a pixel to count as clear.

    Returns:
        The masked scenes, with the ``cs`` band dropped.
    """

    def mask(image: ee.Image) -> ee.Image:
        clear = image.updateMask(image.select("cs").gte(cs_min))
        return clear.select(image.bandNames().remove("cs"))

    return (
        ee.ImageCollection(cfg.ee_collections["sentinel2_sr"])
        .filterBounds(region)
        .filterDate(start, end)
        .linkCollection(ee.ImageCollection(cfg.ee_collections["cloud_score_plus"]), ["cs"])
        .map(mask)
    )
