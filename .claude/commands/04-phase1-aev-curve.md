---
description: "Phase 1: Area–Elevation–Volume curve"
---

<!-- Prompt 04 — Phase 1: Area–Elevation–Volume curve. Run in a fresh session: /04-phase1-aev-curve -->

Prerequisites (human must have done these): prompt 03 done.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Build the AEV curve (methodology §1.3, ADR 0006).

Read first: docs/methodology.md §1.1–1.3 and §2.5, ADR 0006, ADR 0008 (max-extent method),
docs/architecture.md §6, docs/open-questions.md #15, #17, #20–21.

Context from prompt 03: the reservoir rim is only ~1 m above FSL (first overflow ≈913 m),
while DEM vertical error is a few metres. In SRTM the basin may leak at 912 m.

Implement (module: volume, plus baseline step):
- For levels from riverbed minimum to FSL in steps from config (default 0.5 m):
  area(h) and volume(h) within the max-extent mask, computed server-side in Earth Engine.
- Do it for Copernicus GLO-30 AND SRTM. Use the same frozen max-extent mask (from
  Copernicus, prompt 03) for both, so differences reflect valley shape only; report any
  SRTM rim leakage separately rather than silently re-masking.
- Output data/baseline/aev_curve_v1.csv with columns:
  level_m_asl, area_km2, volume_mcm, dem_source
- Interpolation functions: area→level, level→volume, area→volume (pure Python, unit-tested
  on a synthetic cone/V-valley where the true answer is known).
- Plot both curves (media/aev_curve_v1.png) and add a short notebook.
- CLI: `python -m thwake baseline --step aev`.

Acceptance criteria:
- Tests pass, including the synthetic-geometry test within a stated tolerance.
- Summary reports volume at FSL for both DEMs vs the current design capacity (688 MCM)
  and the design-history range at the same FSL (681–825 MCM), with % differences. If >20% off, investigate (FSL, mask, DEM artefacts near the wall)
  and report — do not "fix" by tuning to match.
- Do NOT freeze yet (that's prompt 05). Update roadmap. Stop.
