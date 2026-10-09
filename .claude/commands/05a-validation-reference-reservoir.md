---
description: "Phase 1.5: validate the method on a reference reservoir with published figures"
---

<!-- Prompt 05a — Phase 1.5 Validation (ADR 0009). Run in a fresh session: /05a-validation-reference-reservoir -->

Prerequisites (human must have done these): baseline-v1 frozen (prompt 05) and committed.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Show the planned method is accurate on a reservoir that already exists, before trusting it on Thwake.

Read first: docs/decisions/0009-validation-phase.md, docs/methodology.md §1–2, docs/engineering-roadmap.md A1,
docs/decisions/0005-dual-sensor-water-detection.md, docs/decisions/0006-dem-based-volume-estimation.md.

Do:
1. Propose 1–2 reference reservoirs (candidate: Masinga Dam, Kenya) with **published** area,
   level and/or storage figures over time. Record sources (URL, date, confidence) in
   data/external/reference_reservoirs.csv. If no credible published series exists, say so and
   propose reproducing a published GERD Sentinel-1 result instead. Do not invent figures.
   STOP and ask the human to approve the choice before step 2.
2. Implement the minimum water-detection needed (Sentinel-2 MNDWI + Otsu, Sentinel-1 VV + Otsu)
   in src/thwake/water_s2.py and water_s1.py so Phase 2 can extend it (not rewrite it).
   Thresholds from config/thresholds.yaml.
3. For the reference reservoir: water area over time from both sensors; where a DEM-based
   AEV curve is possible (pre-dam DEM available), estimate volume too.
4. Compare with published figures: table of date, our area/volume (range), published value,
   % difference. Plot to media/validation_reference.png.
5. Write docs/validation.md (new): method, results table, discussion of differences, limits.
   Link it from docs/README.md and docs/methodology.md (§5 Validation strategy).

Acceptance criteria:
- Every published figure has a source; no tuning of thresholds to match the reference (report as-is).
- Tests for any pure-Python logic; Earth Engine steps reproducible via a CLI command
  (e.g. `python -m thwake validate reference --name masinga`).
- `make check` passes. CHANGELOG + roadmap updated. Suggest commit message. Stop.
