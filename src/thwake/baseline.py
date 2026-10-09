"""Phase 1 baseline: area of interest (AOI) and max-extent mask.

Method: docs/methodology.md §1.1–1.2 and ADR 0006.

- **Max extent:** Copernicus GLO-30 pixels at or below the full supply level (FSL) that are
  connected to the reservoir seed (Athi–Thwake confluence). The DEM predates the dam, so the
  digitised wall axis is burned in as a barrier; without it the fill would run downstream.
- **AOI:** the same fill at FSL + margin. The rim has low passes (saddles) between FSL and
  FSL + margin. Each pass found is closed with a small disk, as the saddle dams do on the
  ground, and recorded in the output metadata. The AOI is the union of that fill and the
  max extent, with islands filled in.

The pure-Python helpers (geometry, checks, provenance, pass search) are unit-tested. The
Earth Engine steps need an authenticated session; check them by running
``thwake baseline --step extent`` and ``notebooks/01_aoi_max_extent.ipynb``.
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

from thwake.collections import copernicus_dem
from thwake.config import REPO_ROOT, Config, ConfigError

LonLat = tuple[float, float]
GEOD = Geod(ellps="WGS84")
METHOD_VERSION = "extent-v1"
METHOD_REF = "docs/methodology.md §1.1–1.2"
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

    def __init__(self, cfg: Config, settings: ExtentSettings, bounds: tuple[float, ...]):
        """Prepare the DEM, search region, seed and barrier geometry."""
        self.settings = settings
        self.region = ee.Geometry.Rectangle(list(bounds), None, False)
        self.dem, self.tiles = copernicus_dem(cfg, self.region)
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

    def fill(self, level: float, closures: list[PassClosure]) -> ee.FeatureCollection:
        """Polygon of DEM pixels ≤ ``level`` connected to the seed, not crossing barriers."""
        mask = self.dem.lte(level).And(self.barrier(closures).Not()).selfMask()
        polygons = mask.reduceToVectors(
            geometry=self.region,
            crs=self.projection,
            geometryType="polygon",
            eightConnected=self.settings.eight_connected,
            maxPixels=MAX_PIXELS,
        )
        return polygons.filterBounds(self.seed)

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
