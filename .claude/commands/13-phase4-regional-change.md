---
description: "Phase 4: Regional change"
---

<!-- Prompt 13 — Phase 4: Regional change. Run in a fresh session: /13-phase4-regional-change -->

Prerequisites (human must have done these): Phase 2 (ideally a full season of Phase 3). H6 for irrigation boundaries.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Analyse what the dam has changed (methodology §4).

Read first: docs/methodology.md §4, AGENTS.md rule 9.

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
