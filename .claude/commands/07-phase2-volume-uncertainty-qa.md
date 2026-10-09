---
description: "Phase 2: Area, volume, uncertainty, QA"
---

<!-- Prompt 07 — Phase 2: Area, volume, uncertainty, QA. Run in a fresh session: /07-phase2-volume-uncertainty-qa -->

Prerequisites (human must have done these): prompt 06 done.
If a prerequisite is not met, stop and tell the human.

Task: Turn water masks into area, level, volume and % full with uncertainty and QA flags
(methodology §2.4–2.6).

Read first: docs/methodology.md §2.4–2.6, ARCHITECTURE §6, AGENTS.md rule 4, ADR 0006.

Implement:
- area: pixel-area sum (km²); low/high from threshold sensitivity (± margin from config)
  and shoreline edge ring.
- volume: frozen aev_curve_v1.csv → level & volume; low/high combine area range and
  Copernicus-vs-SRTM spread. Document the combination method in a docstring and in
  methodology.md if it differs.
- pct_full using the capacity in config (note which official figure).
- Optional DEM gap-fill for partly cloudy S2 scenes (methodology §2.3) → method tag.
- qa: flags low_coverage, sensor_disagree, jump, exceeds_max_extent; flag, never drop.
- climate: CHIRPS catchment rainfall (catchment from HydroBASINS) → rain_mm_prev7d.

Tests: uncertainty propagation on synthetic inputs; each QA rule.

Acceptance criteria:
- A function returns one row matching the ARCHITECTURE §6 schema for a given scene.
- Every row has low/best/high values and a qa_flag. Update roadmap. Stop.
