---
description: "Resolve open questions (research, no code)"
---

<!-- Prompt 01 — Resolve open questions (research, no code). Run in a fresh session: /01-resolve-open-questions -->

Prerequisites (human must have done these): an agent with web access (otherwise a human task).
If a prerequisite is not met, stop and tell the human.

Task: Research and resolve the "Blocking Phase 1" items in docs/open-questions.md.

Read first: docs/background-thwake.md, docs/open-questions.md.

For each item (dam-wall coordinates, full supply level (FSL), official storage capacity,
construction start date, impoundment status):
- Search official/primary sources first: AfDB project documents (appraisal, progress
  reports), Ministry of Water / National Water Harvesting and Storage Authority, the ESIA,
  contractor/engineer pages, Kenya News Agency. Then OpenStreetMap for the dam wall.
- Record value, source URL, source date, and confidence (high/medium/low).
- Where sources disagree, record all values; do not pick silently.
- Also verify the ⚠️ items in the Key facts table of background-thwake.md
  (purposes, funders, height).

Deliverables:
- Update background-thwake.md (table + Sources), removing ⚠️ only where verified.
- Update open-questions.md: strike resolved items, add any new questions.
- Create data/external/official_figures.csv with columns:
  item, value, unit, source_url, source_date, confidence, notes

Acceptance criteria:
- Every value has a source URL. Nothing is estimated without being labelled as an estimate.
- If FSL cannot be found, document a proposed fallback (crest elevation minus freeboard,
  from DEM + reported height) as an assumption and leave it ⚠️.

Stop and report; do not start coding.
