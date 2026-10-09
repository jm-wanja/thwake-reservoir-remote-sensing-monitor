# 04 — Phase 1: Area–Elevation–Volume curve

**Requires:** prompt 03 done.

```
Task: Build the AEV curve (methodology §1.3, ADR 0006).

Read first: .ai/docs/03-methodology.md §1.3 and §2.5, ADR 0006, ARCHITECTURE §6.

Implement (module: volume, plus baseline step):
- For levels from riverbed minimum to FSL in steps from config (default 0.5 m):
  area(h) and volume(h) within the max-extent mask, computed server-side in Earth Engine.
- Do it for Copernicus GLO-30 AND SRTM.
- Output data/baseline/aev_curve_v1.csv with columns:
  level_m_asl, area_km2, volume_mcm, dem_source
- Interpolation functions: area→level, level→volume, area→volume (pure Python, unit-tested
  on a synthetic cone/V-valley where the true answer is known).
- Plot both curves (media/aev_curve_v1.png) and add a short notebook.
- CLI: `python -m thwake baseline --step aev`.

Acceptance criteria:
- Tests pass, including the synthetic-geometry test within a stated tolerance.
- Summary reports volume at FSL for both DEMs vs the official capacity (681–688 MCM)
  and the % difference. If >20% off, investigate (FSL, mask, DEM artefacts near the wall)
  and report — do not "fix" by tuning to match.
- Do NOT freeze yet (that's prompt 05). Update roadmap. Stop.
```
