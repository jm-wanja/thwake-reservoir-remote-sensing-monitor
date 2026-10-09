# 0005 — Detect water with both Sentinel-1 and Sentinel-2

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
Filling happens during rainy seasons, when optical images are often cloudy. Radar sees through cloud but has its own errors (wind roughening, shadow).

## Decision
Use **Sentinel-2** (MNDWI + Otsu, cloud-masked) and **Sentinel-1** (VV backscatter + speckle filter + Otsu, ~−18 dB reference) independently, store both in the time series with a `sensor` column, and cross-check them in QA.

## Alternatives considered
- **Sentinel-2 only** — gaps during exactly the period of fastest change.
- **Sentinel-1 only** — fewer artefacts from clouds but misses water-quality and visual context.
- **Landsat 8/9** — 30 m, 16-day; useful for long history but coarser; may add later.

## Consequences
- More frequent observations and an internal consistency check.
- Slightly more code and QA logic.
