# Changelog

All notable changes to this project are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Tags are created by the author (see `docs/human-steps.md`).

## [Unreleased]

### Added
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
