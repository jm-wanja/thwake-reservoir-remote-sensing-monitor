# Roadmap

Ongoing project. Phases are sequential in priority but Phase 1 is the most time-sensitive (pre-filling conditions).

## Phase 0 — Planning ✅ (in progress)
- [x] Project brief, architecture, agent rules, ADRs
- [ ] Resolve blocking open questions (FSL, dam coordinates, capacity) — see [08-open-questions.md](08-open-questions.md)
  - [x] FSL (912 m a.s.l.), capacity (688 MCM), construction start (27 Mar 2018) — sourced 2026-10-09, awaiting human check (H6)
  - [x] Dam-wall coordinates — axis digitised on Sentinel-2 (prompt 03, 2026-10-09), awaiting human check (H6)
  - [ ] Impoundment start — not started as of 2026-10-09; target end Jan 2027
- [x] Repository scaffold: package stubs, CLI, config loader + tests, CI (prompt 02, 2026-10-09)
- [x] Earth Engine account registered for non-commercial use with a Google Cloud project (H2 done 2026-10-09: `thwake-monitor`, Community tier)
- [ ] GitHub repo created (public)

## Phase 1 — Baseline (now, before/at start of filling)
- [x] AOI + max-extent mask (prompt 03, 2026-10-09): max extent 30.36 km² vs official ~29 km²; awaiting human review
- [ ] AEV curve from Copernicus DEM, cross-checked with SRTM; sanity-checked vs official capacity
- [ ] Pre-filling land cover of flood zone; "before" composite; historic river channel
- [ ] Freeze baseline v1 (tag release `baseline-v1`)
- **Exit:** baseline files committed + method written up

## Phase 2 — Filling tracker (from first impoundment, currently targeted for early 2027)
- [ ] S2 and S1 water-mask pipelines + post-processing
- [ ] Area → level → volume → % full with uncertainty
- [ ] QA checks
- [ ] Canonical `thwake_timeseries.csv`
- [ ] Earth Engine App v1 published (link in README)
- [ ] Story page v1 on GitHub Pages (link in README)
- [ ] Scheduled GitHub Action for monthly updates
- **Exit:** both public links live and showing data up to the latest image

## Phase 3 — Water quality (once there is a substantial water surface)
- [ ] Turbidity & chlorophyll proxies by zone
- [ ] Water-colour map for the public
- [ ] Search for in-situ data for validation
- [ ] Story page chapter "Is the water clean?"
- **Exit:** one full season of indicator maps + interpretation

## Phase 4 — Regional change (2027+)
- [ ] Flooded land-cover summary
- [ ] Evaporation estimates
- [ ] Downstream irrigation NDVI analysis
- [ ] Story page chapter "What has the dam changed?"

## Ongoing cadence
| When | What |
|------|------|
| Monthly (automated) | Export new scenes, QA, update CSV, rebuild site |
| After each rainy season (Jun, Jan) | Human review: inspect masks, write a short seasonal update on the story page |
| Yearly | Review methods, dependencies, EE collection versions; update docs |
