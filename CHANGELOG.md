# Changelog

All notable changes to this project are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Tags are created by the author (see `docs/human-steps.md`).

## [Unreleased]

### Added
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
