# Changelog

All notable changes to this project are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Tags are created by the author (see `docs/human-steps.md`).

## [Unreleased]

### Added
- Earth Engine budget rule (AGENTS.md rule 11; `earth_engine.budget` in `config/settings.yaml`): 150 EECU-hours/month Community tier, 10 EECU-hour per-task soft cap, cost estimate before and actual cost after every run; budget block added to every Earth Engine slash command; 80% usage alert configured.
- Plain-language project overview `docs/overview.html` (+ `media/overview.png`) with reservoir map, pipeline, architecture and roadmap diagrams; linked from README.
- Related work and references: Mekong Dam Monitor, RAT, method papers, global reservoir products and the 2025 intercomparison (`docs/methodology.md`); sedimentation as a long-term limitation (Masinga ~13.6% capacity loss by 2011); engineering-roadmap section E (multi-reservoir expansion, SWOT, ALOS AW3D30, Masinga spin-off, bed-change detection, water budget).
- **Phase 1.5 reference-reservoir validation (prompt 05a)** on Masinga (Tana River, Kenya): `thwake validate reference --name masinga` (`--compare-only` redoes the comparison offline). Water area from every Sentinel-2 and Sentinel-1 scene (Oct 2023 – Jun 2026) → level via GLO-30 and SRTM area–elevation curves → compared with KenGen's published levels, as absolute and relative (change between dates) agreement. Both DEMs postdate the dam, so each DEM's flat lake surface is reported and dates below it are listed as not convertible; volume is not testable there. Write-up: `docs/validation.md`; outputs in `data/validation/reference_masinga_*` and `media/validation_reference.png`. Result: Sentinel-1 + GLO-30 levels within 0.46 m RMSE of KenGen (bias −0.33 m, n = 4); SRTM offset −2.25 m with changes agreeing to 0.19 m; Sentinel-1 overestimates water over exposed bed at low levels (10 Oct 2023), and one Sentinel-2 scene (16 Feb 2026) has near-zero green reflectance over water. Against DAHITI (2019–2026): Sentinel-1 + GLO-30 bias −0.38 m, RMSE 0.56 m (n = 32); at low levels Sentinel-1 measures +25.8 km² more water than Sentinel-2 on average.
- `data/external/reference_reservoirs.csv`: Masinga levels and constants, each with source URL, value date and confidence. Low-confidence figures (rounded Feb 2024 level, 120/125 km² area, 1,560 MCM) are shown but kept out of the metrics.
- First water detection, built to be extended by Phase 2: `water_s2` (daily mosaics, Cloud Score+, MNDWI), `water_s1` (daily VV mosaics, focal median), shared `otsu` (histogram Otsu with plausible-range fallback), `area` (range from obscured and edge pixels). New thresholds (set before any comparison): `sentinel2.cloud_score_plus_threshold`, `otsu_valid_range`, histogram settings; `sentinel1.speckle_filter` (focal median, 50 m), `otsu_valid_range`, histogram settings; `validation.*`. New config file `config/validation.yaml`.
- DAHITI satellite altimetry for Masinga (target 40216, Sentinel-3B; Schwatke et al. 2015) as an *independent satellite product, not gauge ground truth*: read from the DAHITI download as-is (`altimetry.path`, raw file git-ignored under `data/external/dahiti/`, only derived comparisons committed), compared with our levels in its own block, and cross-checked against KenGen on near-coincident dates. Scene window extended to Dec 2018 – Sep 2026 to cover it.
- `rapid_change` flag on comparisons where the level moves ≥ 0.04 m/day around the date (rate from the altimetry series), with metrics also given without those rows.
- Earth Engine cost of each validation run (EECU-seconds from request profiles, wall time) recorded in `reference_masinga_scenes.json`.
- Engineering roadmap A8–A9 and open question 27: a guard against Sentinel-1 false water over exposed bed at low levels, and an automatic check for the Sentinel-2 near-zero green-band failure, both to be chosen on the `/05b` labelled set.
- `docs/baseline-v1.md` Erratum 1 (GLO-30 tile acquisition ends 2013-04-21, not 2014-05-24; heights unaffected; frozen files unchanged). Freeze record: tag `baseline-v1` confirmed.
- Open questions 24–26 (Masinga inputs and gauge datum, GLO-30 acquisition dates in the frozen metadata, DAHITI and GERD).
- **Baseline v1 frozen (2026-10-10)**, approved by the author. FSL 912 m and 688 MCM human-verified against ESIA May 2025 §2.3–2.4 (`dam.design_figures_verified`, recorded in the outputs' FSL provenance). Freeze record: `docs/baseline-v1.md`. Tag `baseline-v1` to be created on `main` by the author.
- Freeze manifest `data/baseline/baseline_v1.sha256` (SHA-256 of the 10 frozen files, `sha256sum` format) and CI gate `tests/test_freeze.py`. `thwake baseline --verify` checks it; `--write-manifest` writes it. Once frozen, `thwake baseline` refuses to overwrite outputs without `--force`. `.gitattributes` keeps line endings of frozen files unchanged.
- ADR 0011 (accepted 2026-10-10): both AEV curves use the GLO-30 max-extent mask; rim leaks are reported, not re-masked (open question 20).
- Phase 1 pre-filling reference layers (`src/thwake/reference.py`, methodology §1.4), written up in `docs/baseline-v1.md` (draft, awaiting review before the `baseline-v1` freeze):
  - Land cover inside the max extent → `data/baseline/landcover_flood_zone.csv` (+ `.json`): ESA WorldCover 2021 vs Dynamic World Jun–Sep 2026, hectares per class. The products disagree strongly (e.g. cropland 854 vs 348 ha), so the docs give ranges (open question 23).
  - Sentinel-2 dry-season "before" composite (Jun–Sep 2026, Cloud Score+ ≥ 0.6, 37 dates) → EE asset `before_composite_s2_v1` and `media/before_composite.png` (+ `data/baseline/before_composite.json`).
  - Historic river channel from JRC GSW (occurrence ≥ 10%) → `data/baseline/river_channel.geojson`: 0.353 km² (sensitivity 0.02–0.43 km²).
- `python -m thwake baseline` (no `--step`) runs every baseline step in order. New steps `landcover`, `river` and `composite`; `make baseline` runs them all.
- `collections.sentinel2_clear`: Sentinel-2 scenes masked with Cloud Score+.
- AfDB Appraisal Report (2013) and IPR (Jun 2024) as sources [S13], [S14]: design history (681 MCM, 77 m), Jun 2024 progress (92%), missed completion dates, land acquired (~37.3 km², a cross-check for the flood-zone area). ESIA saddle-dam context (new 2025 scope for the 920.5 m flood level). 11 new rows in `data/external/official_figures.csv`.
- Phase 1 AEV curve (`thwake baseline --step aev`, draft, not frozen): area and volume every 0.5 m from the riverbed to FSL 912 m, for Copernicus GLO-30 and SRTM inside the same max-extent mask, computed in Earth Engine. Outputs: `data/baseline/aev_curve_v1.csv`, `aev_curve_v1.json` (provenance, capacity check, rim check, DEM difference), `media/aev_curve_v1.png`, `notebooks/02_aev_curve.ipynb`. Volume at FSL: 743.4 MCM (GLO-30, +8.1% vs the 688 MCM design) and 795.8 MCM (SRTM, +15.7%); both inside the 681–825 MCM design-history range. SRTM's basin overflows at ≈910 m via rim pass (a). This is reported, not re-masked.
- `thwake.volume`: AEV curve type with area→level, level→volume and area→volume interpolation, plus CSV read/write. Tested on a synthetic cone and V-trough.
- `matplotlib` as an explicit dependency (was already installed via geemap).
- Engineering quality: type checking (mypy) and coverage in CI; pre-commit hooks (ruff, large files, private-key and secret scan with gitleaks, nbstripout); Dependabot; Makefile (`make check`); PR template.
- Tests for the agent guardrail hook (37 cases) — agents can read but not write git/GitHub.
- `CITATION.cff`; licences: MIT (code), CC BY 4.0 (data, figures, docs) — `LICENSE`, `LICENSE-DATA.md`.
- ADR 0008 (max-extent method, DEM release), ADR 0009 (Phase 1.5 Validation), ADR 0010 (repository layout).
- Phase 1.5 Validation in the roadmap, with slash commands `/05a`–`/05c` and optional `/05d` (Otsu vs ML).
- Engineering roadmap (`docs/engineering-roadmap.md`) of reviewer-level improvements.

### Changed
- `tests/test_freeze.py`: the check for unlisted outputs now looks at `data/baseline/` only (`media/` also holds later outputs). Frozen media files stay protected by the checksum manifest test, which is unchanged.
- `.gitignore`: allow-list the two validation JSON outputs; ignore `data/external/dahiti/` (raw third-party downloads).
- Extent and AEV outputs regenerated on 2026-10-10 for provenance only (FSL verification note, wall axis marked human-verified); geometry and curve values unchanged.
- `paths.landcover_metadata` is now an explicit config path.
- AEV outputs no longer say "draft". The freeze state is recorded in `docs/baseline-v1.md` and the `baseline-v1` tag, so the reviewed files are the frozen ones. Numbers unchanged; `aev_curve_v1.json` now also lists the AfDB 681 MCM source.
- Config: `dates.pre_filling_window`, reference-layer paths, `earth_engine.before_composite_asset`, and the `baseline.composite_*`, `river_*` and `landcover_*` thresholds. `.gitignore` allow-lists the two new baseline JSON sidecars.
- `.gitignore`: allow-list `data/baseline/aev_curve_v1.json` (pipeline metadata; all other JSON stays ignored). `make baseline` now runs the extent and AEV steps.
- Dam axis human-verified on Google Earth imagery (25 Jun 2024); confidence raised to high (open question 1 resolved). Saddle pass (a) checked on Feb 2025 imagery: low gap confirmed, no saddle dam visible yet (open question 17).
- Repository layout: `AGENTS.md` (+ `CLAUDE.md`) at root; human docs in `docs/`, decisions in `docs/decisions/`; task prompts are now Claude Code slash commands in `.claude/commands/`.
- GitHub Actions pinned to commit SHAs.
- `baseline.py`: explicit handling of empty Earth Engine responses (type-safety); outputs unchanged.

## [0.1.0] — 2026-10-09 (initial commit, untagged)

### Added
- Project documentation, decision records 0001–0007, agent rules and task prompts.
- Python package scaffold (`thwake` CLI, config loader), CI (ruff, pytest, large-file guard).
- Earth Engine setup (`thwake-monitor`, non-commercial).
- Phase 1 AOI and max-extent mask (`thwake baseline --step extent`): max extent 30.36 km² vs official ~29 km².
