# 0006 — Estimate volume from a frozen pre-dam DEM curve

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
Satellites measure water **area**, not depth. No bathymetry or official level data is available. The valley's shape before the dam is captured by global DEMs.

## Decision
Build an **Area–Elevation–Volume curve** from **Copernicus GLO-30** (primary) and **SRTM** (cross-check), within a max-extent mask below FSL. Convert measured area → level → volume by interpolation. **Freeze** the curve (`aev_curve_v1.csv`) before analysing filling data; changes need a new ADR and version.

## Alternatives considered
- **Satellite altimetry (SWOT, Sentinel-3/6)** — direct water heights, but track coverage over a new, mid-size reservoir is uncertain; consider as validation later.
- **Report area only** — simpler but less meaningful to the public ("how much water?").

## Consequences
- Volume carries DEM-driven uncertainty, reported as ranges.
- Requires FSL and dam location (open questions 1–3).
- Freezing prevents tuning the curve to fit results, which improves credibility.
