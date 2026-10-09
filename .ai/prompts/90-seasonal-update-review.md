# 90 — Seasonal update review (recurring: ~June and ~January)

```
Task: Review the latest rainy season's results and write a seasonal update.

Read first: data/processed/thwake_timeseries.csv (and thwake_quality.csv if present),
.ai/docs/07-risks-and-limitations.md.

Do:
1. Run `python -m thwake update` and `python -m thwake qa`; summarise new rows and flags.
2. Inspect flagged scenes (jump, sensor_disagree, low_coverage) — explain each; propose
   fixes only via config or ADR, never by editing the frozen AEV curve.
3. Check for new official figures/news (impoundment level, commissioning, water quality)
   and update data/external/official_figures.csv with sources.
4. Draft a short "Season update — <season> <year>" section for the story page (≤200 words,
   plain language, numbers with ranges and dates). Show me before publishing.
5. Check EE collection IDs/versions still valid; note any deprecations.
6. Update roadmap "Ongoing cadence" with the review date.
Stop after drafting; I approve the wording.
```
