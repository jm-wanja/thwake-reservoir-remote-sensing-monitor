"""Fetch and filter S1, S2, CHIRPS and ERA5 for the AOI and date range.

Also applies Sentinel-2 cloud masking. So far only the baseline DEM is implemented; the
scene collections follow in prompt 06. See .ai/ARCHITECTURE.md §3B and
.ai/docs/03-methodology.md §2.1–2.2.
"""

from __future__ import annotations

import ee

from thwake.config import Config

DEM_BAND = "DEM"


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
