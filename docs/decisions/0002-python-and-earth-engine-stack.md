# 0002 — Python + Google Earth Engine as the analysis stack

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
Analysis needs years of Sentinel-1/2 imagery, DEMs and climate data over a ~100 km² area, run repeatedly. The owner works in Python and has GIS/geospatial experience. Budget is zero.

## Decision
Use **Python 3.11** with **`earthengine-api`** and **`geemap`** for the pipeline; `pandas`/`geopandas` for tabular/vector outputs. Heavy raster work stays server-side in Earth Engine; only small aggregates are downloaded.

## Alternatives considered
- **Local processing (rasterio/xarray) with downloaded scenes** — full control but large downloads, storage and compute; hard to run in free CI.
- **Microsoft Planetary Computer / Copernicus Data Space (STAC + odc-stac)** — fully open and a good fallback, but more plumbing; kept as the documented exit route if EE access changes.
- **R** — capable but not the owner's main language.

## Consequences
- Requires Earth Engine non-commercial registration and a Google Cloud project.
- CI needs a service account (secret management).
- Vendor dependency on Google — mitigated by documenting methods independent of EE and keeping a STAC fallback in mind.
