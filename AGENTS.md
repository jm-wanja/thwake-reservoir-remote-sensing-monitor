# AGENTS.md — Working on the Thwake Reservoir Remote Sensing Monitor

Instructions for AI coding agents and human contributors. Read this before making any change.

## 1. Project in one paragraph

An independent, long-running **satellite record of Thwake Dam reservoir** (Makueni/Kitui, Kenya) as it fills from first impoundment, currently targeted for early 2027. It tracks **how fast it fills** (area, level, volume, % full), **whether the water is clean** (turbidity / algae signals from Athi River pollution), and **what the dam changes** in the region (flooded land, evaporation, downstream irrigation). Results are published for free as an **interactive Earth Engine App** and a **public story page on GitHub Pages**, both linked from the root README. Full context: [docs/project-brief.md](docs/project-brief.md).

## 2. Audience (design for all three; portfolio + research are primary — [ADR 0007](docs/decisions/0007-name-and-primary-audience.md))

- **Public** (Makueni, Kitui, Machakos residents, journalists) → plain language, visuals first.
- **Employers / portfolio reviewers** → clean, documented, reproducible code.
- **Researchers / water sector** → stated methods, uncertainty, downloadable data, citations.

## 3. Current status

- Phase: **1 — Baseline, in progress.** AOI and max-extent mask done (prompt 03): `python -m thwake baseline --step extent` → `data/baseline/{aoi,max_extent}.geojson`. AEV curve drafted, not frozen (prompt 04): `python -m thwake baseline --step aev` → `data/baseline/aev_curve_v1.{csv,json}`, `media/aev_curve_v1.png`.
- Next: baseline freeze (`/05-phase1-baseline-freeze`), then **Phase 1.5 — Validation** (`/05a`–`/05c`, [ADR 0009](docs/decisions/0009-validation-phase.md)) before Phase 2 — see [docs/roadmap.md](docs/roadmap.md).
- Engineering quality backlog (tests, CI, provenance, validation, ML comparison): [docs/engineering-roadmap.md](docs/engineering-roadmap.md).
- Do not start a later phase's work before the earlier phase's exit criteria are met unless an ADR says otherwise.

## 4. Tech stack (see ADRs for reasoning)

| Area | Choice | ADR |
|------|--------|-----|
| Analysis & exports | Python 3.11 + `earthengine-api` + `geemap`, `pandas`, `geopandas` | [0002](docs/decisions/0002-python-and-earth-engine-stack.md) |
| Interactive app | Google Earth Engine App (JavaScript, Code Editor) | [0003](docs/decisions/0003-free-deployment-ee-app-and-github-pages.md) |
| Story page | Quarto → static HTML, Leaflet/MapLibre, JuxtaposeJS | [0003](docs/decisions/0003-free-deployment-ee-app-and-github-pages.md) |
| Hosting | GitHub Pages (story + data), Earth Engine Apps (live app) | [0003](docs/decisions/0003-free-deployment-ee-app-and-github-pages.md) |
| Automation | GitHub Actions (scheduled export + Pages deploy) | [0003](docs/decisions/0003-free-deployment-ee-app-and-github-pages.md) |
| Water detection | Sentinel-1 + Sentinel-2 combined | [0005](docs/decisions/0005-dual-sensor-water-detection.md) |
| Volume | Pre-dam DEM area–elevation–volume curve | [0006](docs/decisions/0006-dem-based-volume-estimation.md) |
| Max extent | Wall-as-barrier + rim-pass closure; Copernicus GLO-30 2024_1 | [0008](docs/decisions/0008-max-extent-method-and-dem-release.md) |
| Validation | Reference reservoir + labelled shorelines + `thwake evaluate` gate | [0009](docs/decisions/0009-validation-phase.md) |
| Repo layout | Root `AGENTS.md`, `docs/`, prompts as `.claude/commands/` | [0010](docs/decisions/0010-repository-layout.md) |

Do not introduce new frameworks, paid services, or servers without a new ADR.

## 5. Hard rules

1. **Free only.** No paid APIs, no paid hosting, no custom domain. Everything must run on free tiers for a public, non-commercial repo.
2. **Never commit secrets.** Earth Engine service-account keys live only in GitHub Actions secrets and local env vars. `.env`, `*.json` keys and credentials folders must be git-ignored.
3. **Never commit large rasters.** Exported imagery goes to Earth Engine assets or is regenerated; the repo only holds small derived outputs (CSV, GeoJSON, PNG/GIF/MP4 under a size budget, ~10 MB per file).
4. **Every number shown publicly carries uncertainty** (a range or ± value) and a date of the source image.
5. **Every fact cites a source.** Unverified facts are marked `⚠️ verify` and listed in [docs/open-questions.md](docs/open-questions.md).
6. **Reproducibility:** any figure on the story page must be regenerable from code in the repo plus public data.
7. **Satellite water quality is an indicator, not a lab measurement.** Never write "contaminated" or "safe"; write "higher turbidity signal", "possible algal bloom signal", etc.
8. **Baseline before results:** the area–elevation–volume curve (Phase 1) is frozen and versioned before filling data is analysed, so it cannot be tuned to fit results. Changes to it require an ADR.
9. **Respect people:** no imagery or data identifying individual households; resettlement/land topics stay at area level.
10. **No git writes, accounts, credentials or publishing.** Agents never `git commit`, `push`, `tag`, create repos/accounts, handle keys/secrets, publish the Earth Engine App, or approve their own work (baseline freeze, ADR acceptance, public wording). Prepare the change, then stop and tell the human what to run. See [human-steps.md](docs/human-steps.md). The only automated commits are by the scheduled `update.yml` workflow the human set up. **Enforced** for Claude Code sessions by `.claude/settings.json` (deny rules) and `.claude/hooks/block-repo-writes.sh` (blocks any git/gh command not on a read-only allowlist) — do not edit or work around these files.

## 6. Conventions

- **Layout:** follow [architecture.md §5](docs/architecture.md#5-repository-layout). Don't invent new top-level folders. Human-facing docs live in `docs/`; decisions in `docs/decisions/`; task prompts in `.claude/commands/` (agents must not edit these).
- **Python:** type hints (checked by `mypy`), docstrings on public functions, `ruff` for lint/format, `pytest` + coverage for tests. Config in `pyproject.toml`. Run everything with `make check`.
- **Config, not constants:** AOI paths, date ranges, thresholds, capacity value live in `config/*.yaml`, never hard-coded.
- **Earth Engine IDs** (collection names) live in one config file so version bumps are one-line changes.
- **Outputs** are named `<metric>_<sensor>_<YYYYMMDD>.<ext>` and the canonical time series is `data/processed/thwake_timeseries.csv` (schema in [architecture.md §6](docs/architecture.md#6-data-contracts)).
- **Units:** area km², level m a.s.l., volume million m³ (MCM), rainfall mm, dates ISO-8601 UTC.
- **Notebooks** are for exploration only; anything used by the pipeline must live in `src/`.
- **Commits (made by the human):** small, imperative messages ("Add Otsu threshold for S1 water mask"). Agents may *suggest* a message at the end of a task, including a `Co-authored-by:` trailer for AI-assisted work (see [human-steps.md](docs/human-steps.md) H3).
- **CHANGELOG:** add a line under `## [Unreleased]` in `CHANGELOG.md` for every user-visible change.

## 7. Definition of done (for any change)

- [ ] Code runs from a clean environment using documented commands.
- [ ] `make check` passes (ruff, mypy, pytest with coverage); new logic has tests (at least on synthetic data).
- [ ] If the change affects water detection or volume: `thwake evaluate` still meets its thresholds (once Phase 1.5 exists).
- [ ] `CHANGELOG.md` updated.
- [ ] Docs updated if behaviour, data, or decisions changed (incl. an ADR when a decision was made).
- [ ] Public-facing numbers include uncertainty and image date.
- [ ] No secrets, no large files committed.

## 8. Where to find things

- Why / who / goals → [docs/project-brief.md](docs/project-brief.md)
- System design → [docs/architecture.md](docs/architecture.md)
- Method details → [docs/methodology.md](docs/methodology.md)
- Datasets → [docs/data-sources.md](docs/data-sources.md)
- Plan → [docs/roadmap.md](docs/roadmap.md)
- Deployment → [docs/deployment.md](docs/deployment.md)
- Risks → [docs/risks-and-limitations.md](docs/risks-and-limitations.md)
- Unknowns → [docs/open-questions.md](docs/open-questions.md)
- Engineering quality backlog → [docs/engineering-roadmap.md](docs/engineering-roadmap.md)
- Task prompts (what to build next, in order) → [docs/agent-workflow.md](docs/agent-workflow.md) (commands live in `.claude/commands/`)
- Human-only steps (accounts, secrets, commits, publishing, approvals) → [human-steps.md](docs/human-steps.md)

## 9. Session rules (every task)

- Do **only** the task you were given (usually one `/NN-…` command). Do not start later phases or "nice to have" extras.
- Never invent facts (dam specs, coordinates, dates, figures). If something is unknown, mark it `⚠️ verify`, add it to [docs/open-questions.md](docs/open-questions.md), and say so.
- If the task needs a decision not covered by an ADR, stop and propose one (format: [docs/decisions/0000-template.md](docs/decisions/0000-template.md)) before implementing.
- Never request, print, or commit credentials.
- At the end: summarise what changed, how to run/verify it, what's left; update [docs/roadmap.md](docs/roadmap.md) checkboxes and `CHANGELOG.md`; suggest a commit message; list any human steps now needed.

## 10. When unsure

Prefer asking (or writing the question into `docs/open-questions.md`) over guessing. Never fabricate dam specifications, dates, or validation figures.
