# 13 — Phase 4: Regional change

**Requires:** Phase 2 (ideally a full season of Phase 3). H6 for irrigation boundaries.

```
Task: Analyse what the dam has changed (methodology §4).

Read first: .ai/docs/03-methodology.md §4, AGENTS.md rule 9.

Implement (module: regional):
- Flooded land: baseline land cover × max observed extent → hectares by class.
- Evaporation: ERA5-Land evaporation × reservoir area over time → MCM per month/season.
  State simplifications (open-water vs land evaporation) clearly.
- Downstream irrigation: dry-season NDVI in command areas (boundaries supplied by me or
  found with sources) vs pre-dam years.
- Seasonal shoreline min/max ("bathtub ring") map.
- Story page section "What has the dam changed?"; area-level only for social topics.

Acceptance criteria: methods and limitations documented; outputs reproducible via CLI.
Update roadmap. Stop.
```
