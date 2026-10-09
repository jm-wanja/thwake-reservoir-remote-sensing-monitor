---
description: "Phase 1: AOI and max-extent mask"
---

<!-- Prompt 03 — Phase 1: AOI and max-extent mask. Run in a fresh session: /03-phase1-aoi-max-extent -->

Prerequisites (human must have done these): H2 (Earth Engine authenticated, EE_PROJECT in .env), prompt 01 done (dam location, FSL or documented fallback).
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Implement the AOI and max-extent mask (methodology §1.1–1.2).

Read first: docs/methodology.md §1, docs/architecture.md §3A, ADR 0006,
data/external/official_figures.csv.

Implement in src/thwake/ (modules: ee_auth, collections, a new or existing baseline module):
- Dam-wall location and FSL read from config — never hard-coded.
- AOI: upstream valley polygon, buffered above FSL (+ margin from config).
- Max-extent mask: DEM (Copernicus GLO-30) pixels ≤ FSL, hydrologically connected to the
  dam site (connected-component / flood-fill from the dam location), within AOI.
- Exclude areas downstream of the dam wall.
- Export small vector outputs: data/baseline/aoi.geojson, data/baseline/max_extent.geojson.
- Wire to CLI: `python -m thwake baseline --step extent`.
- Notebook notebooks/01_aoi_max_extent.ipynb that visualises outputs with geemap
  (exploration only; logic stays in src/).

Tests: unit-test any pure-Python geometry/config logic; document what can't be tested
offline.

Acceptance criteria:
- Outputs exist and look plausible on a map (upstream valley, ends at the wall).
- Report max-extent area in km² and compare to any official reservoir surface area found.
- If FSL is a fallback assumption, say so prominently in the output metadata and summary.
- Update roadmap. Stop.
