---
description: "Phase 2: Canonical time series and `update` CLI"
---

<!-- Prompt 08 — Phase 2: Canonical time series and `update` CLI. Run in a fresh session: /08-phase2-timeseries-cli -->

Prerequisites (human must have done these): prompt 07 done.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Build the canonical time series and an idempotent update command.

Read first: ARCHITECTURE §4 (data flow) and §6 (schema), AGENTS.md conventions.

Implement:
- `python -m thwake update [--since YYYY-MM-DD]`: finds scenes newer than the last date in
  data/processed/thwake_timeseries.csv (or --since), processes them, appends rows.
  Idempotent: re-running never duplicates rows (key: scene_id + method_version).
- `python -m thwake qa`: prints a QA summary and exits non-zero on schema violations.
- `python -m thwake media`: regenerates charts (area & volume over time with uncertainty
  band, rainfall bars) and a compressed time-lapse GIF/MP4 (<10 MB) into media/.
- Latest-shoreline GeoJSON into data/processed/outlines/.
- Backfill from baseline date (pre-impoundment) to today.

Tests: idempotency, schema validation.

- Provenance (engineering roadmap A5): every `update` run writes data/processed/run_metadata.json
  (run date, git commit, config hash, EE collection IDs/versions, scene IDs processed, method_version)
  and each time-series row can be traced to it. Document the schema in docs/architecture.md §6.

Acceptance criteria:
- Running `update` twice in a row produces no changes the second time.
- Chart shows uncertainty band and image dates. Update roadmap. Stop.
