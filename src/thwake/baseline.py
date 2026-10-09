"""Phase 1 baseline: area of interest (AOI), max-extent mask and AEV curve.

Method: docs/methodology.md §1.1–1.3, ADRs 0006 and 0008.

- **Max extent:** Copernicus GLO-30 pixels at or below the full supply level (FSL) that are
  connected to the reservoir seed (Athi–Thwake confluence). The DEM predates the dam, so the
  digitised wall axis is burned in as a barrier; without it the fill would run downstream.
- **AOI:** the same fill at FSL + margin. The rim has low passes (saddles) between FSL and
  FSL + margin. Each pass found is closed with a small disk, as the saddle dams do on the
  ground, and recorded in the output metadata. The AOI is the union of that fill and the
  max extent, with islands filled in.
- **AEV curve:** area and volume below each level from the riverbed to the FSL, inside the
  max-extent mask, for each DEM in ``baseline.aev_dems`` (Copernicus GLO-30 and SRTM). Both
  DEMs use the same (GLO-30) mask, so differences reflect valley shape only. Each DEM's own
  rim is checked separately (wall barrier only) and reported, never used to re-mask.

The pure-Python helpers (geometry, checks, provenance, pass search) are unit-tested. The
Earth Engine steps need an authenticated session; check them by running
``thwake baseline --step extent`` / ``--step aev`` and the notebooks in ``notebooks/``.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import ee
import shapely
from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from thwake import export, volume
from thwake.collections import (
    DEM_COLLECTION_KEYS,
    DEM_LABELS,
    DEM_VERTICAL_DATUM,
    copernicus_dem,
    dem_by_name,
)
from thwake.config import REPO_ROOT, Config, ConfigError

LonLat = tuple[float, float]
GEOD = Geod(ellps="WGS84")
METHOD_VERSION = "extent-v1"
METHOD_REF = "docs/methodology.md §1.1–1.2"
AEV_METHOD_VERSION = "aev-v1"
AEV_METHOD_REF = "docs/methodology.md §1.3"
# Output coordinates are rounded to this grid (~0.1 m), far finer than the 30 m DEM.
COORD_PRECISION_DEG = 1e-6
# An output this close to the search-area edge (~110 m, 3–4 DEM pixels) counts as touching.
EDGE_MARGIN_DEG = 0.001


class BaselineError(Exception):
    """Raised when a baseline output fails a sanity check."""


# Earth Engine caps per-request pixel counts; generous for a ~100 km² region at 30 m.
MAX_PIXELS = 1_000_000_000


def _get_info(obj: Any) -> Any:
    """Evaluate an Earth Engine object client-side, failing loudly on an empty response."""
    value = obj.getInfo()
    if value is None:
        raise BaselineError("Earth Engine returned no data for a required request")
    return value


# --- Settings ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtentSettings:
    """Inputs for the AOI and max-extent step, read from ``config/*.yaml``."""

    fsl_m: float
    aoi_margin_m: float
    wall_axis: tuple[LonLat, ...]
    wall_axis_source: str
    seed: LonLat
    downstream_point: LonLat
    search_radius_km: float
    eight_connected: bool
    barrier_half_width_m: float
    abutment_extension_m: float
    pass_closure_radius_m: float
    pass_level_tolerance_m: float
    max_pass_closures: int
    dem_collection: str
    aoi_path: Path
    max_extent_path: Path
    official_figures_path: Path

    @property
    def aoi_level_m(self) -> float:
        """Water level the AOI is delineated at: FSL plus the margin."""
        return self.fsl_m + self.aoi_margin_m


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if mapping.get(key) is None:
        raise ConfigError(f"Missing '{key}' in {where}")
    return mapping[key]


def _number(mapping: dict[str, Any], key: str, where: str, positive: bool = True) -> float:
    value = _require(mapping, key, where)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"'{key}' in {where} must be a number, got {value!r}")
    if positive and value <= 0:
        raise ConfigError(f"'{key}' in {where} must be positive, got {value}")
    return float(value)


def _lonlat(value: Any, name: str) -> LonLat:
    if not isinstance(value, dict) or value.get("lat") is None or value.get("lon") is None:
        raise ConfigError(f"{name} must be a mapping with 'lat' and 'lon'")
    lat, lon = float(value["lat"]), float(value["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ConfigError(f"{name} is out of range: lat={lat}, lon={lon}")
    return lon, lat


def extent_settings(cfg: Config) -> ExtentSettings:
    """Read and validate the AOI / max-extent inputs from the loaded configuration.

    Args:
        cfg: Loaded configuration.

    Returns:
        Validated settings, with output paths resolved against the repository root.

    Raises:
        ConfigError: If a value is missing or malformed.
    """
    dam = cfg.settings.get("dam") or {}
    paths = cfg.settings.get("paths") or {}
    base = cfg.thresholds.get("baseline") or {}
    where_dam, where_base = "settings.yaml dam", "thresholds.yaml baseline"

    axis = _require(dam, "wall_axis", where_dam)
    if not isinstance(axis, list) or len(axis) < 2:
        raise ConfigError(f"'wall_axis' in {where_dam} needs at least two points")
    eight = _require(base, "eight_connected", where_base)
    if not isinstance(eight, bool):
        raise ConfigError(f"'eight_connected' in {where_base} must be true or false")

    return ExtentSettings(
        fsl_m=_number(dam, "full_supply_level_m_asl", where_dam),
        aoi_margin_m=_number(base, "aoi_buffer_above_fsl_m", where_base),
        wall_axis=tuple(_lonlat(p, f"wall_axis[{i}]") for i, p in enumerate(axis)),
        wall_axis_source=str(dam.get("wall_axis_source") or "not recorded"),
        seed=_lonlat(_require(dam, "reservoir_seed", where_dam), "reservoir_seed"),
        downstream_point=_lonlat(
            _require(dam, "downstream_check_point", where_dam), "downstream_check_point"
        ),
        search_radius_km=_number(base, "search_radius_km", where_base),
        eight_connected=eight,
        barrier_half_width_m=_number(base, "wall_barrier_half_width_m", where_base),
        abutment_extension_m=_number(base, "abutment_extension_m", where_base, positive=False),
        pass_closure_radius_m=_number(base, "pass_closure_radius_m", where_base),
        pass_level_tolerance_m=_number(base, "pass_level_tolerance_m", where_base),
        max_pass_closures=int(_number(base, "max_pass_closures", where_base)),
        dem_collection=str(_require(cfg.ee_collections, "copernicus_dem_glo30", "ee_collections")),
        aoi_path=REPO_ROOT / _require(paths, "aoi", "settings.yaml paths"),
        max_extent_path=REPO_ROOT / _require(paths, "max_extent", "settings.yaml paths"),
        official_figures_path=REPO_ROOT
        / _require(paths, "official_figures", "settings.yaml paths"),
    )


# --- Geometry helpers (pure Python) -----------------------------------------------------


def extend_line(coords: Sequence[LonLat], metres: float) -> list[LonLat]:
    """Extend a polyline at both ends by ``metres`` along its end segments (geodesic).

    Args:
        coords: At least two ``(lon, lat)`` points.
        metres: Extension at each end; 0 returns the line unchanged.

    Returns:
        The extended polyline.
    """
    if len(coords) < 2:
        raise ValueError("A line needs at least two points")
    points = [(float(c[0]), float(c[1])) for c in coords]
    if metres == 0:
        return points
    (x0, y0), (x1, y1) = points[0], points[1]
    azimuth, _, _ = GEOD.inv(x0, y0, x1, y1)
    start_lon, start_lat, _ = GEOD.fwd(x0, y0, azimuth + 180, metres)
    (xa, ya), (xb, yb) = points[-2], points[-1]
    _, back_azimuth, _ = GEOD.inv(xa, ya, xb, yb)
    end_lon, end_lat, _ = GEOD.fwd(xb, yb, back_azimuth + 180, metres)
    return [(start_lon, start_lat), *points, (end_lon, end_lat)]


def line_length_m(coords: Sequence[LonLat]) -> float:
    """Geodesic length of a ``(lon, lat)`` polyline in metres."""
    lons, lats = zip(*coords, strict=True)
    return float(GEOD.line_length(lons, lats))


def midpoint(a: LonLat, b: LonLat) -> LonLat:
    """Geodesic midpoint of two ``(lon, lat)`` points."""
    azimuth, _, distance = GEOD.inv(a[0], a[1], b[0], b[1])
    lon, lat, _ = GEOD.fwd(a[0], a[1], azimuth, distance / 2)
    return lon, lat


def search_bounds(center: LonLat, radius_km: float) -> tuple[float, float, float, float]:
    """``(west, south, east, north)`` of a square extending ``radius_km`` from ``center``."""
    lon, lat = center
    distance = radius_km * 1000
    north = GEOD.fwd(lon, lat, 0, distance)[1]
    south = GEOD.fwd(lon, lat, 180, distance)[1]
    east = GEOD.fwd(lon, lat, 90, distance)[0]
    west = GEOD.fwd(lon, lat, 270, distance)[0]
    return west, south, east, north


def _polygons(geom: BaseGeometry) -> Iterator[Polygon]:
    if isinstance(geom, Polygon):
        yield geom
    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from _polygons(part)


def polygonal(geom: BaseGeometry) -> BaseGeometry:
    """Repair a geometry and keep only its polygon parts (drops stray lines and points)."""
    parts = list(_polygons(shapely.make_valid(geom)))
    if not parts:
        raise BaselineError("Geometry has no polygon parts")
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def fill_holes(geom: BaseGeometry) -> BaseGeometry:
    """Remove interior rings (islands) from every polygon part."""
    return shapely.union_all([Polygon(p.exterior) for p in _polygons(geom)])


def area_km2(geom: BaseGeometry) -> float:
    """Geodesic area on the WGS84 ellipsoid, in km² (holes subtracted)."""
    total = 0.0
    for part in _polygons(geom):
        area, _ = GEOD.geometry_area_perimeter(orient(part, sign=1.0))
        total += area
    return total / 1e6


def check_inside(geom: BaseGeometry, bounds: tuple[float, ...], name: str) -> None:
    """Raise if ``geom`` reaches the edge of the search area (a leak or too small an area)."""
    west, south, east, north = bounds
    g_west, g_south, g_east, g_north = geom.bounds
    if (
        g_west <= west + EDGE_MARGIN_DEG
        or g_south <= south + EDGE_MARGIN_DEG
        or g_east >= east - EDGE_MARGIN_DEG
        or g_north >= north - EDGE_MARGIN_DEG
    ):
        raise BaselineError(
            f"{name} reaches the edge of the search area {bounds}: it may be leaking around "
            "the dam wall, or baseline.search_radius_km is too small"
        )


def check_excludes(geom: BaseGeometry, point: LonLat, name: str) -> None:
    """Raise if ``geom`` contains the downstream check point (it leaks past the wall)."""
    if geom.covers(shapely.Point(point)):
        raise BaselineError(
            f"{name} contains the downstream check point {point}: it leaks past the dam wall"
        )


# --- Rim overflow passes (pure logic; Earth Engine supplies the callables) ---------------


@dataclass(frozen=True)
class PassClosure:
    """A rim overflow pass closed for the AOI fill."""

    lon: float
    lat: float
    overflow_level_m: float

    def as_dict(self) -> dict[str, float]:
        """Rounded values for output metadata."""
        return {
            "lat": round(self.lat, 5),
            "lon": round(self.lon, 5),
            "overflow_level_m_asl": round(self.overflow_level_m, 1),
        }


LeakTest = Callable[[float, list[PassClosure]], bool]
PassLocator = Callable[[float, float, list[PassClosure]], list[LonLat]]


def bisect_level(leaks: Callable[[float], bool], lo: float, hi: float, tol: float) -> LonLat:
    """Narrow ``[lo, hi]`` to the lowest level at which ``leaks`` becomes true.

    Assumes ``leaks(lo)`` is false, ``leaks(hi)`` is true, and leaking is monotonic in level.

    Returns:
        ``(below, above)`` with ``above - below <= tol``: no leak at ``below``, leak at ``above``.
    """
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if leaks(mid):
            hi = mid
        else:
            lo = mid
    return lo, hi


def close_passes(
    leaks: LeakTest,
    locate: PassLocator,
    lo: float,
    hi: float,
    tol: float,
    max_closures: int,
) -> list[PassClosure]:
    """Find and close rim overflow passes, lowest first, until a fill at ``hi`` stays closed.

    Args:
        leaks: ``leaks(level, closures)`` is true if the fill reaches downstream.
        locate: ``locate(below, above, closures)`` returns the pass point(s) that open
            between the two levels.
        lo: A level known not to leak (the FSL).
        hi: The level that must not leak once passes are closed (FSL + margin).
        tol: Precision of the overflow level, in metres.
        max_closures: Give up with an error after this many closures.

    Returns:
        The closures, in the order found.

    Raises:
        BaselineError: If too many passes are needed or a pass cannot be located.
    """
    closures: list[PassClosure] = []
    while leaks(hi, closures):
        if len(closures) >= max_closures:
            raise BaselineError(
                f"Still leaking at {hi} m after {len(closures)} pass closures; check the "
                "wall axis and downstream check point, or raise baseline.max_pass_closures"
            )
        below, above = bisect_level(lambda level: leaks(level, closures), lo, hi, tol)
        points = locate(below, above, closures)
        if not points:
            raise BaselineError(f"Rim overflow at {below:.2f}–{above:.2f} m but no pass found")
        closures.extend(PassClosure(lon, lat, above) for lon, lat in points)
        lo = below
    return closures


# --- Provenance -------------------------------------------------------------------------


def read_official_figures(path: Path) -> list[dict[str, str]]:
    """Rows of ``data/external/official_figures.csv``."""
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def fsl_provenance(fsl_m: float, rows: list[dict[str, str]]) -> dict[str, Any]:
    """Whether the configured FSL is a sourced value or a fallback assumption."""
    matches = [
        r for r in rows if r["item"] == "full_supply_level" and _as_float(r["value"]) == fsl_m
    ]
    if matches:
        return {
            "fsl_is_fallback": False,
            "fsl_note": "Design value from official documents (data/external/"
            "official_figures.csv); awaiting human verification (human-steps.md H6).",
            "fsl_sources": [r["source_url"] for r in matches],
        }
    return {
        "fsl_is_fallback": True,
        "fsl_note": "FALLBACK ASSUMPTION: the FSL in config/settings.yaml matches no "
        "full_supply_level in data/external/official_figures.csv.",
        "fsl_sources": [],
    }


def official_area(rows: list[dict[str, str]]) -> dict[str, Any] | None:
    """The first ``reservoir_area_at_fsl`` row, or ``None`` if there is none."""
    for r in rows:
        if r["item"] == "reservoir_area_at_fsl" and _as_float(r["value"]) is not None:
            return {
                "official_area_km2": float(r["value"]),
                "official_area_source": r["source_url"],
                "official_area_confidence": r["confidence"],
                "official_area_note": r["notes"],
            }
    return None


# --- Output -----------------------------------------------------------------------------


def feature_collection(geom: BaseGeometry, properties: dict[str, Any]) -> dict[str, Any]:
    """A one-feature GeoJSON FeatureCollection, coordinates rounded to ~0.1 m."""
    rounded = shapely.set_precision(geom, COORD_PRECISION_DEG)
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": properties, "geometry": mapping(rounded)}],
    }


def write_geojson(path: Path, collection: dict[str, Any]) -> None:
    """Write GeoJSON compactly (one line) with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False) + "\n", encoding="utf-8")


# --- Earth Engine -----------------------------------------------------------------------


class EarthEngineFill:
    """Flood fills on the pre-dam DEM, run server side in Earth Engine."""

    def __init__(
        self,
        cfg: Config,
        settings: ExtentSettings,
        bounds: tuple[float, ...],
        dem: tuple[ee.Image, ee.ImageCollection] | None = None,
    ):
        """Prepare the DEM, search region, seed and barrier geometry.

        ``dem`` defaults to Copernicus GLO-30; pass another ``(image, tiles)`` pair (e.g.
        SRTM) to run the same fills on it.
        """
        self.settings = settings
        self.region = ee.Geometry.Rectangle(list(bounds), None, False)
        self.dem, self.tiles = dem if dem is not None else copernicus_dem(cfg, self.region)
        self.projection = self.dem.projection()
        self.seed = ee.Geometry.Point(list(settings.seed))
        self.probe = ee.Geometry.Point(list(settings.downstream_point))
        self.wall = extend_line(settings.wall_axis, settings.abutment_extension_m)

    def _raster(self, features: ee.FeatureCollection) -> ee.Image:
        return ee.Image(0).byte().paint(features, 1).reproject(self.projection)

    def barrier(self, closures: list[PassClosure]) -> ee.Image:
        """1 on the wall strip and pass-closure disks, else 0."""
        s = self.settings
        line = ee.Geometry.LineString([list(p) for p in self.wall])
        features = [ee.Feature(line.buffer(s.barrier_half_width_m))]
        features += [
            ee.Feature(ee.Geometry.Point([c.lon, c.lat]).buffer(s.pass_closure_radius_m))
            for c in closures
        ]
        return self._raster(ee.FeatureCollection(features))

    def _components(self, level: float, closures: list[PassClosure]) -> ee.FeatureCollection:
        """Connected polygons of DEM pixels ≤ ``level``, not crossing barriers."""
        mask = self.dem.lte(level).And(self.barrier(closures).Not()).selfMask()
        return mask.reduceToVectors(
            geometry=self.region,
            crs=self.projection,
            geometryType="polygon",
            eightConnected=self.settings.eight_connected,
            maxPixels=MAX_PIXELS,
        )

    def fill(self, level: float, closures: list[PassClosure]) -> ee.FeatureCollection:
        """Polygon of DEM pixels ≤ ``level`` connected to the seed, not crossing barriers."""
        return self._components(level, closures).filterBounds(self.seed)

    def leaks(self, level: float, closures: list[PassClosure]) -> bool:
        """True if the fill at ``level`` reaches the downstream check point."""
        return int(_get_info(self.fill(level, closures).filterBounds(self.probe).size())) > 0

    def locate_pass(self, below: float, above: float, closures: list[PassClosure]) -> list[LonLat]:
        """Centroids of rim pixels that join the reservoir to outside between two levels.

        A pass pixel lies in ``(below, above]`` and within two pixels of both the fill at
        ``below`` and the newly connected outside ground (≤ ``below``) of the fill at ``above``.
        """
        inside = self._raster(self.fill(below, closures))
        after = self._raster(self.fill(above, closures))
        outside = after.And(inside.Not()).And(self.dem.lte(below))
        rim = self.dem.gt(below).And(self.dem.lte(above)).And(after)
        candidates = rim.And(inside.focalMax(2)).And(outside.focalMax(2)).selfMask()
        points = candidates.reduceToVectors(
            geometry=self.region,
            crs=self.projection,
            geometryType="centroid",
            eightConnected=True,
            maxPixels=MAX_PIXELS,
        )
        return [
            (float(f["geometry"]["coordinates"][0]), float(f["geometry"]["coordinates"][1]))
            for f in _get_info(points)["features"]
        ]

    def locate_leak(self, below: float, above: float) -> list[LonLat]:
        """Centroids of rim pixels joining the reservoir to the downstream basin.

        Like :meth:`locate_pass` (no closures), but the outside ground must be the polygon
        ≤ ``below`` that contains the downstream check point. Internal pockets that merge
        with the fill at the same level are therefore not reported.
        """
        inside = self._raster(self.fill(below, []))
        downstream = self._raster(self._components(below, []).filterBounds(self.probe))
        rim = self.dem.gt(below).And(self.dem.lte(above))
        candidates = rim.And(inside.focalMax(2)).And(downstream.focalMax(2)).selfMask()
        points = candidates.reduceToVectors(
            geometry=self.region,
            crs=self.projection,
            geometryType="centroid",
            eightConnected=True,
            maxPixels=MAX_PIXELS,
        )
        return [
            (float(f["geometry"]["coordinates"][0]), float(f["geometry"]["coordinates"][1]))
            for f in _get_info(points)["features"]
        ]

    def geometry(self, fill: ee.FeatureCollection, name: str) -> BaseGeometry:
        """Download a fill as a valid shapely geometry (exactly one polygon expected)."""
        info = _get_info(ee.Dictionary({"n": fill.size(), "geometry": fill.geometry()}))
        if info["n"] != 1:
            raise BaselineError(
                f"{name}: expected one polygon at the reservoir seed, got {info['n']}; "
                "check reservoir_seed lies on the valley floor below the fill level"
            )
        return polygonal(shape(info["geometry"]))

    def elevations(self, points: Sequence[LonLat]) -> list[float | None]:
        """DEM elevation (m) at each point."""
        features = ee.FeatureCollection([ee.Feature(ee.Geometry.Point(list(p))) for p in points])
        sampled = self.dem.reduceRegions(
            collection=features, reducer=ee.Reducer.first(), crs=self.projection
        )
        return list(_get_info(sampled.aggregate_array("first")))

    def acquisition_window(self) -> str:
        """``start/end`` dates of the DEM tiles used (ISO 8601 interval)."""
        start = ee.Date(self.tiles.aggregate_min("system:time_start")).format("YYYY-MM-dd")
        end = ee.Date(self.tiles.aggregate_max("system:time_end")).format("YYYY-MM-dd")
        return "/".join(_get_info(ee.List([start, end])))


# --- Step -------------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtentResult:
    """Outputs of the AOI / max-extent step."""

    max_extent: dict[str, Any]
    aoi: dict[str, Any]
    max_extent_path: Path
    aoi_path: Path

    @property
    def max_extent_properties(self) -> dict[str, Any]:
        """Metadata of the max-extent feature."""
        return self.max_extent["features"][0]["properties"]

    @property
    def aoi_properties(self) -> dict[str, Any]:
        """Metadata of the AOI feature."""
        return self.aoi["features"][0]["properties"]


def build_extent(
    cfg: Config, write: bool = True, log: Callable[[str], None] = print
) -> ExtentResult:
    """Build the max-extent mask and AOI and (by default) write them as GeoJSON.

    Earth Engine must already be initialised (:func:`thwake.ee_auth.initialize`).

    Args:
        cfg: Loaded configuration.
        write: Write ``data/baseline/max_extent.geojson`` and ``aoi.geojson``.
        log: Progress messages go here.

    Returns:
        The two feature collections and their paths.

    Raises:
        BaselineError: If an output fails a sanity check (leak, edge contact, no seed polygon).
    """
    s = extent_settings(cfg)
    rows = read_official_figures(s.official_figures_path)
    bounds = search_bounds(midpoint(s.wall_axis[0], s.wall_axis[-1]), s.search_radius_km)
    engine = EarthEngineFill(cfg, s, bounds)

    log(f"Max extent: filling the pre-dam DEM to FSL {s.fsl_m:g} m a.s.l. ...")
    if engine.leaks(s.fsl_m, []):
        raise BaselineError(
            f"The fill at FSL {s.fsl_m:g} m reaches the downstream check point: the wall "
            "barrier does not close the valley. Check wall_axis and abutment_extension_m."
        )
    max_extent = engine.geometry(engine.fill(s.fsl_m, []), "Max extent")
    check_excludes(max_extent, s.downstream_point, "Max extent")
    check_inside(max_extent, bounds, "Max extent")

    log(f"AOI: closing rim overflow passes up to {s.aoi_level_m:g} m a.s.l. ...")
    closures = close_passes(
        engine.leaks,
        engine.locate_pass,
        s.fsl_m,
        s.aoi_level_m,
        s.pass_level_tolerance_m,
        s.max_pass_closures,
    )
    for c in closures:
        log(f"  pass at {c.lat:.5f}, {c.lon:.5f} overflows at ~{c.overflow_level_m:.1f} m")
    aoi_fill = engine.geometry(engine.fill(s.aoi_level_m, closures), "AOI")
    aoi = fill_holes(shapely.union(aoi_fill, max_extent))
    check_excludes(aoi, s.downstream_point, "AOI")
    check_inside(aoi, bounds, "AOI")

    wall = extend_line(s.wall_axis, s.abutment_extension_m)
    end_elevations = engine.elevations([wall[0], wall[-1]])
    common = {
        "full_supply_level_m_asl": s.fsl_m,
        **fsl_provenance(s.fsl_m, rows),
        "dem": s.dem_collection,
        "dem_acquired": engine.acquisition_window(),
        "wall_axis": [[round(x, 5), round(y, 5)] for x, y in s.wall_axis],
        "wall_axis_length_m": round(line_length_m(s.wall_axis)),
        "wall_axis_source": s.wall_axis_source,
        "wall_barrier": {
            "half_width_m": s.barrier_half_width_m,
            "abutment_extension_m": s.abutment_extension_m,
            "end_elevations_m": [None if e is None else round(e, 1) for e in end_elevations],
        },
        "reservoir_seed": [s.seed[0], s.seed[1]],
        "downstream_check_point": [s.downstream_point[0], s.downstream_point[1]],
        "eight_connected": s.eight_connected,
        "search_bounds": [round(b, 5) for b in bounds],
        "method": METHOD_REF,
        "method_version": METHOD_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
    }
    max_props = {
        "name": "Thwake reservoir max extent",
        "description": "Pre-dam DEM pixels at or below FSL, connected to the reservoir seed "
        "upstream of the dam wall. Water outside this mask is never counted.",
        "level_m_asl": s.fsl_m,
        "area_km2": round(area_km2(max_extent), 2),
        **(official_area(rows) or {}),
        **common,
    }
    aoi_props = {
        "name": "Thwake reservoir area of interest (AOI)",
        "description": "Upstream valley at or below FSL + margin, with rim overflow passes "
        "closed, merged with the max extent; islands filled.",
        "level_m_asl": s.aoi_level_m,
        "aoi_buffer_above_fsl_m": s.aoi_margin_m,
        "area_km2": round(area_km2(aoi), 2),
        "pass_closures": [c.as_dict() for c in closures],
        "pass_closure_radius_m": s.pass_closure_radius_m,
        **common,
    }
    if max_props["fsl_is_fallback"]:
        for props in (max_props, aoi_props):
            props["name"] = "FALLBACK FSL — " + props["name"]

    result = ExtentResult(
        max_extent=feature_collection(max_extent, max_props),
        aoi=feature_collection(aoi, aoi_props),
        max_extent_path=s.max_extent_path,
        aoi_path=s.aoi_path,
    )
    if write:
        write_geojson(s.max_extent_path, result.max_extent)
        write_geojson(s.aoi_path, result.aoi)
    return result


def summary(result: ExtentResult) -> str:
    """Plain-text report of the step for the terminal."""
    m, a = result.max_extent_properties, result.aoi_properties
    lines = []
    if m["fsl_is_fallback"]:
        lines += ["!" * 72, "WARNING: " + m["fsl_note"], "!" * 72]
    lines.append(
        f"Max extent (≤ {m['level_m_asl']:g} m a.s.l.): {m['area_km2']:.2f} km²"
        f" -> {result.max_extent_path.relative_to(REPO_ROOT)}"
    )
    if "official_area_km2" in m:
        official = m["official_area_km2"]
        diff = (m["area_km2"] - official) / official * 100
        lines.append(
            f"  Official reservoir area at FSL: {official:g} km² "
            f"({m['official_area_confidence']} confidence) -> difference {diff:+.1f}%"
        )
    lines.append(
        f"AOI (≤ {a['level_m_asl']:g} m a.s.l., FSL + {a['aoi_buffer_above_fsl_m']:g} m): "
        f"{a['area_km2']:.2f} km² -> {result.aoi_path.relative_to(REPO_ROOT)}"
    )
    lines.append(f"  Rim overflow passes closed for the AOI: {len(a['pass_closures'])}")
    lines += [
        f"    {p['lat']:.5f}, {p['lon']:.5f} overflows at ~{p['overflow_level_m_asl']:.1f} m"
        for p in a["pass_closures"]
    ]
    lines.append(f"DEM: {m['dem']} (acquired {m['dem_acquired']})")
    lines.append(
        f"Wall barrier end elevations: {m['wall_barrier']['end_elevations_m']} m "
        f"(axis {m['wall_axis_length_m']} m + {m['wall_barrier']['abutment_extension_m']:g} m "
        "each end)"
    )
    lines.append(f"FSL {m['full_supply_level_m_asl']:g} m: {m['fsl_note']}")
    return "\n".join(lines)


# --- AEV curve: settings and pure helpers -----------------------------------------------


@dataclass(frozen=True)
class AEVSettings:
    """Inputs for the AEV-curve step, read from ``config/*.yaml``."""

    fsl_m: float
    step_m: float
    dems: tuple[str, ...]
    dem_collections: dict[str, str]
    design_capacity_mcm: float
    capacity_check_pct: float
    wall_zone_m: float
    aev_path: Path
    metadata_path: Path
    figure_path: Path


def aev_settings(cfg: Config) -> AEVSettings:
    """Read and validate the AEV-curve inputs from the loaded configuration.

    Raises:
        ConfigError: If a value is missing or malformed, or a DEM name is unknown.
    """
    dam = cfg.settings.get("dam") or {}
    paths = cfg.settings.get("paths") or {}
    base = cfg.thresholds.get("baseline") or {}
    where_dam, where_base, where_paths = (
        "settings.yaml dam",
        "thresholds.yaml baseline",
        "settings.yaml paths",
    )
    dems = _require(base, "aev_dems", where_base)
    if not isinstance(dems, list) or not dems:
        raise ConfigError(f"'aev_dems' in {where_base} must be a non-empty list")
    unknown = [d for d in dems if d not in DEM_COLLECTION_KEYS]
    if unknown or len(set(dems)) != len(dems):
        raise ConfigError(
            f"'aev_dems' in {where_base} must list distinct names from "
            f"{sorted(DEM_COLLECTION_KEYS)}, got {dems}"
        )
    collections = {
        d: str(_require(cfg.ee_collections, DEM_COLLECTION_KEYS[d], "ee_collections")) for d in dems
    }
    return AEVSettings(
        fsl_m=_number(dam, "full_supply_level_m_asl", where_dam),
        step_m=_number(base, "aev_level_step_m", where_base),
        dems=tuple(dems),
        dem_collections=collections,
        design_capacity_mcm=_number(dam, "design_capacity_mcm", where_dam),
        capacity_check_pct=_number(base, "aev_capacity_check_pct", where_base),
        wall_zone_m=_number(base, "aev_wall_zone_m", where_base),
        aev_path=REPO_ROOT / _require(paths, "aev_curve", where_paths),
        metadata_path=REPO_ROOT / _require(paths, "aev_metadata", where_paths),
        figure_path=REPO_ROOT / _require(paths, "aev_figure", where_paths),
    )


def capacity_history(rows: list[dict[str, str]]) -> list[float]:
    """Distinct ``storage_capacity_at_fsl`` values in the official figures, ascending.

    These are the design capacities at the same FSL across design stages (open question 15).
    """
    values = {
        v
        for r in rows
        if r["item"] == "storage_capacity_at_fsl" and (v := _as_float(r["value"])) is not None
    }
    return sorted(values)


def capacity_comparison(
    volume_mcm: float, design_mcm: float, history_mcm: Sequence[float], check_pct: float
) -> dict[str, Any]:
    """Compare a volume at FSL with the design capacity and the design-history range.

    Args:
        volume_mcm: DEM volume at FSL.
        design_mcm: Current design capacity (config ``dam.design_capacity_mcm``).
        history_mcm: All design capacities at the same FSL (includes the current one).
        check_pct: Differences from the design capacity beyond this need investigation.

    Returns:
        Rounded figures and flags for the metadata and the terminal summary.
    """
    low, high = min(history_mcm), max(history_mcm)
    vs_design = volume.percent_difference(volume_mcm, design_mcm)
    return {
        "volume_at_fsl_mcm": round(volume_mcm, 1),
        "design_capacity_mcm": design_mcm,
        "vs_design_pct": round(vs_design, 1),
        "design_history_mcm": [low, high],
        "vs_history_low_pct": round(volume.percent_difference(volume_mcm, low), 1),
        "vs_history_high_pct": round(volume.percent_difference(volume_mcm, high), 1),
        "within_design_history": low <= volume_mcm <= high,
        "needs_investigation": abs(vs_design) > check_pct,
    }


def rim_overflow(
    leaks: Callable[[float], bool], lo: float, hi: float, tol: float
) -> tuple[float, float] | None:
    """Bracket the level at which the fill first overflows the rim, searching ``[lo, hi]``.

    Args:
        leaks: ``leaks(level)`` is true if the fill at ``level`` reaches downstream.
        lo: Lowest level searched.
        hi: Highest level searched.
        tol: Precision of the overflow level, in metres.

    Returns:
        ``(below, above)`` around the overflow level, ``(lo, lo)`` if the fill already
        leaks at ``lo``, or ``None`` if it does not leak at ``hi``.
    """
    if leaks(lo):
        return lo, lo
    if not leaks(hi):
        return None
    return bisect_level(leaks, lo, hi, tol)


# --- AEV curve: Earth Engine ------------------------------------------------------------


class EarthEngineAEV:
    """Per-bin pixel sums of one DEM inside the max-extent mask, computed in Earth Engine."""

    def __init__(self, cfg: Config, name: str, mask: BaseGeometry):
        """Load the DEM and rasterise the mask on its native grid (pixel centres inside)."""
        self.name = name
        geometry = ee.Geometry(json.loads(shapely.to_geojson(mask)), None, False)
        self.region = geometry.bounds(None, None).buffer(200, None, None)
        self.dem, self.tiles = dem_by_name(cfg, name, self.region)
        self.projection = self.dem.projection()
        self.mask = (
            ee.Image(0)
            .byte()
            .paint(ee.FeatureCollection([ee.Feature(geometry)]), 1)
            .reproject(self.projection)
        )

    def _reduce(self, image: ee.Image, reducer: ee.Reducer) -> ee.Dictionary:
        return image.updateMask(self.mask).reduceRegion(
            reducer=reducer, geometry=self.region, crs=self.projection, maxPixels=MAX_PIXELS
        )

    def bins_and_stats(self, top_m: float, step_m: float) -> tuple[list[volume.BinSum], dict]:
        """``(bin sums, stats)``: the inputs of :func:`thwake.volume.curve_from_bins`.

        Bins follow :func:`thwake.volume.bin_index`. Stats: mask area on this DEM's grid,
        minimum and maximum elevation in the mask, and the DEM's grid transform.
        """
        area = ee.Image.pixelArea().toDouble()
        depth = ee.Image.constant(top_m).toDouble().subtract(self.dem.toDouble())
        stack = ee.Image.cat(area, area.multiply(depth), depth.divide(step_m).floor().int())
        grouped = ee.Reducer.sum().unweighted().repeat(2).group(groupField=2, groupName="bin")
        info = _get_info(
            ee.Dictionary(
                {
                    "bins": self._reduce(stack, grouped).get("groups"),
                    "mask_m2": self._reduce(area, ee.Reducer.sum().unweighted()).get("area"),
                    "elev": self._reduce(self.dem, ee.Reducer.minMax()),
                    "transform": self.projection.transform(),
                }
            )
        )
        bins = [(int(g["bin"]), float(g["sum"][0]), float(g["sum"][1])) for g in info["bins"]]
        stats = {
            "mask_area_km2": info["mask_m2"] / volume.M2_PER_KM2,
            "min_elevation_m": info["elev"]["DEM_min"],
            "max_elevation_m": info["elev"]["DEM_max"],
            "grid_transform": info["transform"],
        }
        return bins, stats

    def difference_stats(self, other: EarthEngineAEV, zone: ee.Geometry | None) -> dict:
        """Statistics of ``other − self`` elevation (m) inside the mask (and ``zone``)."""
        diff = other.dem.subtract(self.dem).rename("diff")
        if zone is not None:
            diff = diff.clip(zone)
        reducer = (
            ee.Reducer.mean()
            .combine(ee.Reducer.stdDev(), None, True)
            .combine(ee.Reducer.percentile([5, 50, 95]), None, True)
            .combine(ee.Reducer.count(), None, True)
        )
        info = _get_info(self._reduce(diff, reducer))
        return {
            "pixels": info["diff_count"],
            "mean_m": round(info["diff_mean"], 2),
            "std_m": round(info["diff_stdDev"], 2),
            "p5_m": round(info["diff_p5"], 2),
            "median_m": round(info["diff_p50"], 2),
            "p95_m": round(info["diff_p95"], 2),
        }

    def acquisition_window(self) -> str:
        """``start/end`` dates of the DEM data used (ISO 8601 interval)."""
        start = ee.Date(self.tiles.aggregate_min("system:time_start")).format("YYYY-MM-dd")
        end = ee.Date(self.tiles.aggregate_max("system:time_end")).format("YYYY-MM-dd")
        return "/".join(_get_info(ee.List([start, end])))


def rim_check(
    cfg: Config,
    extent: ExtentSettings,
    aev: EarthEngineAEV,
    mask: BaseGeometry,
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Flood-fill one DEM with the wall barrier only and report how its rim behaves.

    Nothing here changes the mask: it reports (a) the level at which this DEM's basin first
    overflows (searched within FSL ± the AOI margin) and the rim pixels joining it to the
    downstream basin there, and (b) if it holds at FSL, how its own fill at FSL differs from
    the max-extent mask.
    """
    s = extent
    bounds = search_bounds(midpoint(s.wall_axis[0], s.wall_axis[-1]), s.search_radius_km)
    engine = EarthEngineFill(cfg, s, bounds, dem=(aev.dem, aev.tiles))
    lo, hi = s.fsl_m - s.aoi_margin_m, s.fsl_m + s.aoi_margin_m
    log(f"  {DEM_LABELS[aev.name]}: searching for the first rim overflow in {lo:g}–{hi:g} m ...")
    bracket = rim_overflow(lambda level: engine.leaks(level, []), lo, hi, s.pass_level_tolerance_m)
    report: dict[str, Any] = {"searched_m_asl": [lo, hi], "barrier": "dam wall only"}
    if bracket is None:
        report |= {"first_overflow_m_asl": None, "leaks_at_fsl": False}
    elif bracket[0] == bracket[1]:
        report |= {"first_overflow_m_asl": f"< {lo:g}", "leaks_at_fsl": True}
    else:
        below, above = bracket
        passes = engine.locate_leak(below, above)
        report |= {
            "first_overflow_m_asl": round(above, 1),
            "leaks_at_fsl": above <= s.fsl_m,
            "rim_margin_above_fsl_m": round(above - s.fsl_m, 1),
            "overflow_passes": [{"lat": round(y, 5), "lon": round(x, 5)} for x, y in passes],
        }
    if not report["leaks_at_fsl"]:
        own = engine.geometry(engine.fill(s.fsl_m, []), f"{aev.name} fill at FSL")
        report |= {
            "own_fill_at_fsl_km2": round(area_km2(own), 2),
            "own_fill_outside_mask_km2": round(area_km2(shapely.difference(own, mask)), 2),
            "mask_outside_own_fill_km2": round(area_km2(shapely.difference(mask, own)), 2),
        }
    return report


# --- AEV curve: step --------------------------------------------------------------------


@dataclass(frozen=True)
class AEVResult:
    """Outputs of the AEV-curve step."""

    curves: dict[str, volume.AEVCurve]
    metadata: dict[str, Any]
    aev_path: Path
    metadata_path: Path
    figure_path: Path


def build_aev(cfg: Config, write: bool = True, log: Callable[[str], None] = print) -> AEVResult:
    """Build the AEV curve for each configured DEM and (by default) write CSV, JSON and figure.

    Earth Engine must already be initialised. The max extent must exist (``--step extent``).

    Args:
        cfg: Loaded configuration.
        write: Write ``aev_curve_v1.csv``, its ``.json`` metadata and the PNG figure.
        log: Progress messages go here.

    Returns:
        The curves, metadata and output paths.

    Raises:
        BaselineError: If the max extent is missing or a curve cannot be built.
    """
    s = aev_settings(cfg)
    extent = extent_settings(cfg)
    if not extent.max_extent_path.is_file():
        raise BaselineError(
            f"{extent.max_extent_path.relative_to(REPO_ROOT)} not found: "
            "run `thwake baseline --step extent` first"
        )
    max_extent = json.loads(extent.max_extent_path.read_text(encoding="utf-8"))
    mask_feature = max_extent["features"][0]
    mask = polygonal(shape(mask_feature["geometry"]))
    mask_props = mask_feature["properties"]
    if mask_props.get("level_m_asl") != s.fsl_m:
        raise BaselineError(
            f"The max extent was built at {mask_props.get('level_m_asl')} m but the FSL is "
            f"{s.fsl_m:g} m: rebuild it with `thwake baseline --step extent`"
        )
    rows = read_official_figures(extent.official_figures_path)
    history = capacity_history(rows)
    if s.design_capacity_mcm not in history:
        history = sorted({*history, s.design_capacity_mcm})

    curves: dict[str, volume.AEVCurve] = {}
    engines: dict[str, EarthEngineAEV] = {}
    dem_meta: dict[str, Any] = {}
    for name in s.dems:
        log(f"AEV: {DEM_LABELS[name]} levels up to FSL {s.fsl_m:g} m every {s.step_m:g} m ...")
        engine = EarthEngineAEV(cfg, name, mask)
        bins, stats = engine.bins_and_stats(s.fsl_m, s.step_m)
        try:
            curve = volume.curve_from_bins(bins, s.fsl_m, s.step_m, name)
        except ValueError as exc:
            raise BaselineError(f"{DEM_LABELS[name]}: {exc}") from exc
        above_fsl_m2 = sum(a for k, a, _ in bins if k < 0)
        dh = curve.levels_m[-1] - curve.levels_m[-2]
        curves[name], engines[name] = curve, engine
        dem_meta[name] = {
            "label": DEM_LABELS[name],
            "collection": s.dem_collections[name],
            "acquired": engine.acquisition_window(),
            "vertical_datum": DEM_VERTICAL_DATUM[name],
            "grid_transform": stats["grid_transform"],
            "mask_area_on_grid_km2": round(stats["mask_area_km2"], 3),
            "mask_area_above_fsl_km2": round(above_fsl_m2 / volume.M2_PER_KM2, 3),
            "min_elevation_in_mask_m": round(stats["min_elevation_m"], 1),
            "max_elevation_in_mask_m": round(stats["max_elevation_m"], 1),
            "curve_start_m_asl": curve.levels_m[0],
            "area_at_fsl_km2": round(curve.top_area_km2, 2),
            "volume_at_fsl_mcm": round(curve.top_volume_mcm, 1),
            # Sensitivity: MCM per metre of level (≈ area at FSL); also the effect of a
            # uniform 1 m DEM bias or FSL error on the volume at FSL.
            "dvolume_dlevel_at_fsl_mcm_per_m": round(
                (curve.volumes_mcm[-1] - curve.volumes_mcm[-2]) / dh, 1
            ),
            "capacity_check": capacity_comparison(
                curve.top_volume_mcm, s.design_capacity_mcm, history, s.capacity_check_pct
            ),
        }

    log("Rim check: each DEM flood-filled with the wall barrier only (no re-masking) ...")
    for name in s.dems:
        dem_meta[name]["rim"] = rim_check(cfg, extent, engines[name], mask, log)

    comparison: dict[str, Any] = {}
    if len(s.dems) > 1:
        primary, secondary = engines[s.dems[0]], engines[s.dems[1]]
        log(f"DEM difference: {DEM_LABELS[secondary.name]} − {DEM_LABELS[primary.name]} ...")
        wall = ee.Geometry.LineString([list(p) for p in extent.wall_axis])
        comparison = {
            "difference": f"{secondary.name} minus {primary.name} (m), inside the mask",
            "whole_mask": primary.difference_stats(secondary, None),
            f"within_{s.wall_zone_m:g}m_of_wall": primary.difference_stats(
                secondary, wall.buffer(s.wall_zone_m)
            ),
        }

    metadata = {
        "name": "Thwake reservoir area–elevation–volume curve v1",
        "status": "DRAFT — not frozen. The baseline freeze is prompt 05 (AGENTS.md rule 8).",
        "csv": str(s.aev_path.relative_to(REPO_ROOT)),
        "columns": {
            "level_m_asl": "water level, m above sea level (each DEM's own vertical datum)",
            "area_km2": "water area at or below the level inside the max-extent mask, km²",
            "volume_mcm": "stored volume below the level, million m³",
            "dem_source": "DEM short name (key of 'dems' below)",
        },
        "full_supply_level_m_asl": s.fsl_m,
        **fsl_provenance(s.fsl_m, rows),
        "level_step_m": s.step_m,
        "max_extent": {
            "path": str(extent.max_extent_path.relative_to(REPO_ROOT)),
            "area_km2": mask_props.get("area_km2"),
            "official_area_km2": mask_props.get("official_area_km2"),
            "dem": mask_props.get("dem"),
            "method_version": mask_props.get("method_version"),
            "note": "The same GLO-30 mask is used for every DEM, so curve differences "
            "reflect valley shape only. Pixels are in the mask if their centre is inside it.",
        },
        "design_capacity_sources": [
            {k: r[k] for k in ("value", "source_url", "source_date", "confidence", "notes")}
            for r in rows
            if r["item"] == "storage_capacity_at_fsl"
        ],
        "dems": dem_meta,
        "dem_comparison": comparison,
        "method": AEV_METHOD_REF,
        "method_version": AEV_METHOD_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
    }
    result = AEVResult(curves, metadata, s.aev_path, s.metadata_path, s.figure_path)
    if write:
        volume.write_aev_csv(s.aev_path, [curves[d] for d in s.dems])
        s.metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        export.plot_aev_curve(curves, metadata, s.figure_path)
    return result


def _display_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def aev_summary(result: AEVResult) -> str:
    """Plain-text report of the AEV step for the terminal."""
    meta, dems = result.metadata, result.metadata["dems"]
    names = list(dems)
    width = 24

    def row(label: str, values: list[str]) -> str:
        return f"  {label:<34}" + "".join(f"{v:>{width}}" for v in values)

    def pct(x: float) -> str:
        return f"{x:+.1f}%"

    checks = [dems[n]["capacity_check"] for n in names]
    low, high = checks[0]["design_history_mcm"]
    design = checks[0]["design_capacity_mcm"]
    lines = []
    if meta["fsl_is_fallback"]:
        lines += ["!" * 72, "WARNING: " + meta["fsl_note"], "!" * 72]
    lines += [
        f"AEV curve v1 (DRAFT, not frozen) -> {_display_path(result.aev_path)}",
        f"  metadata -> {_display_path(result.metadata_path)}; "
        f"figure -> {_display_path(result.figure_path)}",
        f"  FSL {meta['full_supply_level_m_asl']:g} m a.s.l., step {meta['level_step_m']:g} m; "
        f"same max-extent mask for all DEMs ({meta['max_extent']['area_km2']} km², GLO-30)",
        row("", [dems[n]["label"] for n in names]),
        row("DEM acquired", [dems[n]["acquired"] for n in names]),
        row(
            "Lowest elevation in mask (m)",
            [f"{dems[n]['min_elevation_in_mask_m']:.1f}" for n in names],
        ),
        row(
            "Mask area above FSL in DEM (km²)",
            [f"{dems[n]['mask_area_above_fsl_km2']:.2f}" for n in names],
        ),
        row("Area at FSL (km²)", [f"{dems[n]['area_at_fsl_km2']:.2f}" for n in names]),
        row("Volume at FSL (MCM)", [f"{c['volume_at_fsl_mcm']:.1f}" for c in checks]),
        row(f"  vs design capacity {design:g} MCM", [pct(c["vs_design_pct"]) for c in checks]),
        row(f"  vs design history low {low:g}", [pct(c["vs_history_low_pct"]) for c in checks]),
        row(f"  vs design history high {high:g}", [pct(c["vs_history_high_pct"]) for c in checks]),
        row(
            f"  within {low:g}–{high:g} MCM",
            ["yes" if c["within_design_history"] else "NO" for c in checks],
        ),
        row(
            "dV/dh at FSL (MCM per m)",
            [f"{dems[n]['dvolume_dlevel_at_fsl_mcm_per_m']:.1f}" for n in names],
        ),
    ]
    for n in names:
        if dems[n]["capacity_check"]["needs_investigation"]:
            lines.append(
                f"  WARNING: {dems[n]['label']} volume at FSL is more than the configured "
                "threshold away from the design capacity: investigate FSL, mask and DEM "
                "artefacts near the wall (do not tune the curve)."
            )
    lines.append("Rim check (wall barrier only; reported, not used to re-mask):")
    for n in names:
        rim = dems[n]["rim"]
        first = rim["first_overflow_m_asl"]
        if first is None:
            text = f"no overflow up to {rim['searched_m_asl'][1]:g} m"
        else:
            text = f"first overflow ≈{first} m" + (" — LEAKS AT FSL" if rim["leaks_at_fsl"] else "")
            if rim.get("overflow_passes"):
                p = rim["overflow_passes"][0]
                text += f" at {p['lat']:.5f}, {p['lon']:.5f}"
        lines.append(f"  {dems[n]['label']}: {text}")
        if "own_fill_at_fsl_km2" in rim:
            lines.append(
                f"    own fill at FSL {rim['own_fill_at_fsl_km2']:.2f} km² "
                f"(outside mask {rim['own_fill_outside_mask_km2']:.2f} km², "
                f"mask not reached {rim['mask_outside_own_fill_km2']:.2f} km²)"
            )
    comparison = meta.get("dem_comparison") or {}
    for key, stats in comparison.items():
        if isinstance(stats, dict):
            lines.append(
                f"DEM difference ({comparison['difference']}), {key.replace('_', ' ')}: "
                f"mean {stats['mean_m']:+.2f} m, median {stats['median_m']:+.2f} m, "
                f"5–95% {stats['p5_m']:+.1f} to {stats['p95_m']:+.1f} m ({stats['pixels']} px)"
            )
    return "\n".join(lines)
