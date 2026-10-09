"""Water area in km² from pixel-area sums, with a sensitivity range.

Method: docs/methodology.md §2.4–2.5. Two sources of area uncertainty are covered so far
(threshold sensitivity is added in prompt 07):

- **Obscured pixels** (clouds, no data) inside the mask: the low end counts none of them as
  water and the high end counts all of them. The best estimate assumes they hold water in
  the same proportion as the clear part of the mask.
- **Edge (mixed) pixels:** ± ``edge_ring_pixels`` (half a pixel ring by default) along the
  shoreline, i.e. the edge-pixel area times that fraction.

:func:`water_pixel_sums` computes the pixel sums in Earth Engine; :func:`area_range` turns
them into the range and is unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass

import ee

M2_PER_KM2 = 1e6


@dataclass(frozen=True)
class AreaRange:
    """Water area (km²): best estimate and sensitivity range, with the valid share."""

    best_km2: float
    low_km2: float
    high_km2: float
    valid_fraction: float


def area_range(
    water_m2: float, valid_m2: float, mask_m2: float, edge_m2: float, edge_fraction: float
) -> AreaRange:
    """Area range from pixel sums inside the mask.

    Args:
        water_m2: Area of water pixels among the valid (clear) pixels.
        valid_m2: Area of valid pixels inside the mask.
        mask_m2: Area of the mask.
        edge_m2: Area of water pixels on the shoreline (next to a non-water pixel).
        edge_fraction: Share of each edge pixel that is uncertain (e.g. 0.5).

    Returns:
        The range, clamped to ``[0, mask]``.

    Raises:
        ValueError: If the sums are inconsistent (negative, water > valid, valid > mask).
    """
    tol = 1e-6 * max(mask_m2, 1.0)
    if min(water_m2, valid_m2, mask_m2, edge_m2, edge_fraction) < 0:
        raise ValueError("Pixel sums and edge fraction must be non-negative")
    if water_m2 > valid_m2 + tol or valid_m2 > mask_m2 + tol or edge_m2 > water_m2 + tol:
        raise ValueError(
            f"Inconsistent pixel sums: water {water_m2}, valid {valid_m2}, mask {mask_m2}, "
            f"edge {edge_m2} (need edge ≤ water ≤ valid ≤ mask)"
        )
    valid_m2 = min(valid_m2, mask_m2)
    obscured = mask_m2 - valid_m2
    share = water_m2 / valid_m2 if valid_m2 > 0 else 0.0
    edge = edge_m2 * edge_fraction
    best = water_m2 + obscured * share
    low = max(water_m2 - edge, 0.0)
    high = min(water_m2 + obscured + edge, mask_m2)
    return AreaRange(
        best_km2=best / M2_PER_KM2,
        low_km2=low / M2_PER_KM2,
        high_km2=high / M2_PER_KM2,
        valid_fraction=valid_m2 / mask_m2 if mask_m2 > 0 else 0.0,
    )


def water_pixel_sums(
    water: ee.Image, mask: ee.Image, region: ee.Geometry, projection: ee.Projection
) -> ee.Dictionary:
    """Pixel-area sums for :func:`area_range`, computed in Earth Engine.

    Args:
        water: 1 = water, 0 = not water; masked where the scene has no valid data.
        mask: 1 inside the area where water may be counted (max extent), else 0.
        region: Bounds of the mask (reduction region).
        projection: Analysis grid (crs and scale); focal operations run on it.

    Returns:
        A dictionary with ``water_m2``, ``valid_m2``, ``mask_m2`` and ``edge_m2``. An edge
        pixel is a water pixel with a non-water or obscured 4-neighbour.
    """
    area = ee.Image.pixelArea()
    inside = mask.reproject(projection).selfMask()
    filled = water.unmask(0).reproject(projection)
    edge = filled.And(filled.focalMin(1, "plus", "pixels").Not())
    stack = ee.Image.cat(
        area.updateMask(water.mask().reduce(ee.Reducer.min())).rename("valid_m2"),
        area.updateMask(water.unmask(0).eq(1)).rename("water_m2"),
        area.updateMask(edge).rename("edge_m2"),
        area.rename("mask_m2"),
    ).updateMask(inside)
    return stack.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=region, crs=projection, maxPixels=1_000_000_000
    )
