---
description: "Phase 1.5: build a hand-labelled shoreline test set and accuracy metrics"
---

<!-- Prompt 05b — Phase 1.5 Validation (ADR 0009). Run in a fresh session: /05b-validation-labelled-set -->

Prerequisites (human must have done these): 05a done and committed.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Create the infrastructure for a labelled water/land test set; the human does the labelling.

Read first: docs/decisions/0009-validation-phase.md, docs/validation.md, docs/engineering-roadmap.md A2.

Do:
1. Select ~25 scenes (reference reservoir now; Thwake scenes added after filling): mix of
   Sentinel-1/2, dry/wet season, clear/partly cloudy. Write the list to
   data/validation/scenes.csv (scene_id, sensor, date, site, reason chosen).
2. Export small true-colour (S2) / VV (S1) PNG or GeoTIFF previews (<1 MB each, git-ignored if
   GeoTIFF) and document how the human digitises shorelines (QGIS or geojson.io) into
   data/validation/labels/<scene_id>.geojson. Write the guide in docs/validation.md.
3. Implement metrics (pure Python, unit-tested): IoU, precision, recall, F1 between a predicted
   mask polygon and a label polygon, plus an area-difference %.
4. STOP and hand over to the human for labelling (HUMAN step). List exactly what to label.
After labels exist (a later run of this command): compute metrics per scene and per sensor,
write the table into docs/validation.md and a summary line in the README.

Acceptance criteria:
- Metric functions tested on synthetic polygons with known answers.
- No large files committed; labels are small GeoJSON.
- `make check` passes. CHANGELOG + roadmap updated. Suggest commit message. Stop.
