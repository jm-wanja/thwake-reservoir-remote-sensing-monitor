# 12 — Phase 3: Water-quality indicators

**Requires:** Phase 2 done and a substantial water surface present.

```
Task: Add water-quality indicators (methodology §3).

Read first: .ai/docs/03-methodology.md §3, AGENTS.md rule 7,
.ai/docs/07-risks-and-limitations.md.

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
```
