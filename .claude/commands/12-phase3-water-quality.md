---
description: "Phase 3: Water-quality indicators"
---

<!-- Prompt 12 — Phase 3: Water-quality indicators. Run in a fresh session: /12-phase3-water-quality -->

Prerequisites (human must have done these): Phase 2 done and a substantial water surface present.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Add water-quality indicators (methodology §3).

Read first: docs/methodology.md §3, AGENTS.md rule 7,
docs/risks-and-limitations.md.

Implement (module: quality):
- Over water pixels only, excluding a shoreline buffer (config): NDTI / red reflectance
  (turbidity proxy), NDCI (chlorophyll proxy); optional Forel-Ule water colour class.
- Zones: Athi inflow arm, Thwake inflow arm, central basin, near-dam — define as
  GeoJSON in data/baseline/quality_zones.geojson (document how drawn).
- Add per-zone median/percentiles to a new file data/processed/thwake_quality.csv
  (propose the schema via ADR first — schema changes need an ADR).
- Charts vs rainfall; seasonal maps (PNG) for the story page; EE App layer.
- Story page section "Is the water clean?" with careful wording and limitations.
- Search for any in-situ data for validation; record in data/external/ with provenance.

Acceptance criteria:
- No absolute concentration claims without in-situ calibration.
- Language uses "signal"/"indicator". Update roadmap. Stop.
