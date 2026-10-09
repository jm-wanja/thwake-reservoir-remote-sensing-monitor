# Roadmap

Ongoing project. Phases are sequential in priority but Phase 1 is the most time-sensitive (pre-filling conditions).

## Phase 0 — Planning ✅
- [x] Project brief, architecture, agent rules, ADRs
- [ ] Resolve blocking open questions (FSL, dam coordinates, capacity) — see [open-questions.md](open-questions.md)
  - [x] FSL (912 m a.s.l.), capacity (688 MCM), construction start (27 Mar 2018) — sourced 2026-10-09, awaiting human check (H6)
  - [x] Dam-wall coordinates — axis digitised on Sentinel-2 (prompt 03) and human-verified on Google Earth (2026-10-09)
  - [ ] Impoundment start — not started as of 2026-10-09; target end Jan 2027
- [x] Repository scaffold: package stubs, CLI, config loader + tests, CI (prompt 02, 2026-10-09)
- [x] Earth Engine account registered for non-commercial use with a Google Cloud project (H2 done 2026-10-09: `thwake-monitor`, Community tier)
- [x] GitHub repo created (public): `jm-wanja/thwake-reservoir-remote-sensing-monitor`, first push 2026-10-09
- [x] Restructure to standard layout + engineering quick wins ([ADR 0010](decisions/0010-repository-layout.md), [engineering roadmap](engineering-roadmap.md))

## Phase 1 — Baseline (now, before/at start of filling)
- [x] AOI + max-extent mask (prompt 03, 2026-10-09): max extent 30.36 km² vs official ~29 km²; awaiting human review
- [x] AEV curve from Copernicus DEM, cross-checked with SRTM; sanity-checked vs official capacity (prompt 04, 2026-10-09, **draft, not frozen**): volume at FSL 743 MCM (GLO-30, +8%) and 796 MCM (SRTM, +16%) vs design 688 MCM, both inside the 681–825 design-history range; SRTM rim overflows at ≈910 m (below FSL). Awaiting human review
- [ ] Pre-filling land cover of flood zone; "before" composite; historic river channel
- [ ] Freeze baseline v1 (tag release `baseline-v1`)
- **Exit:** baseline files committed + method written up

## Phase 1.5 — Validation (before Phase 2) — [ADR 0009](decisions/0009-validation-phase.md)
- [ ] Reference reservoir: method run on an existing reservoir with published figures (`/05a-validation-reference-reservoir`)
- [ ] Labelled test set: ~20–30 human-digitised shorelines; IoU / precision / recall per sensor (`/05b-validation-labelled-set`, labelling is a human step)
- [ ] Evaluation harness: `thwake evaluate` + CI gate on thresholds (`/05c-validation-evaluation-harness`)
- [ ] Accuracy table in README and methodology
- [ ] (Optional, engineering roadmap C1) Otsu vs ML comparison on the labelled set
- **Exit:** published accuracy numbers; CI fails if accuracy regresses

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
