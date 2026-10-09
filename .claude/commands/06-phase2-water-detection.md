---
description: "Phase 2: Water detection (Sentinel-2 and Sentinel-1)"
---

<!-- Prompt 06 — Phase 2: Water detection (Sentinel-2 and Sentinel-1). Run in a fresh session: /06-phase2-water-detection -->

Prerequisites (human must have done these): baseline-v1 frozen and Phase 1.5 (05a–05c) done.
If a prerequisite is not met, stop and tell the human.

Task: Extend the water-detection code built in Phase 1.5 (05a) into the full per-scene pipeline for
Sentinel-2 and Sentinel-1 — extend, do not rewrite; `thwake evaluate` must still pass
(methodology §2.1–2.3, ADR 0005).

Read first: docs/methodology.md §2, ADR 0005, config/thresholds.yaml.

Implement:
- collections: filter S2 (with Cloud Score+ masking) and S1 GRD (IW, VV/VH) over AOI and
  date range; compute valid_fraction over the max-extent.
- water_s2: MNDWI (and NDWI), Otsu threshold within a shoreline buffer, fallback fixed
  threshold from config.
- water_s1: speckle filter, VV Otsu threshold, reference −18 dB from config, steep-slope /
  radar-shadow mask from DEM.
- postprocess: clip to max-extent, keep components connected to the dam wall, remove
  specks below min size, separate pre-existing river channel area.
- Every threshold comes from config; record the threshold actually used per scene.
- Notebook notebooks/02_water_masks.ipynb showing sample scenes from both sensors,
  including at least one cloudy/rainy date.

Tests: Otsu on synthetic bimodal arrays; post-processing logic where testable offline.

Acceptance criteria:
- Masks look right on visual inspection for ≥5 dates per sensor (screenshots in notebook).
- Where S1 and S2 dates are within ±2 days, report area agreement.
- No volume yet (prompt 07). Update roadmap. Stop.
