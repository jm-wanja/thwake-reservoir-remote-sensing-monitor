# Thwake Reservoir Remote Sensing Monitor 🛰️💧

*A remote sensing and geospatial data science project using Sentinel-1/2 and Google Earth Engine.*

An independent, satellite-based record of **Thwake Dam reservoir** (Makueni/Kitui, Kenya) — how fast it fills, whether the water is clean, and what it changes in the region. Built entirely on free, public data.

> **Status:** Phase 1 (pre-filling baseline) in progress — reservoir extent mapped (30.4 km² at full supply level vs ~29 km² official); draft volume curve gives 743–796 MCM at full supply level from two elevation models (design: 688 MCM). Next: baseline freeze, then a validation phase before filling, officially targeted for early 2027.

## Live links

- 🛰️ **Interactive app:** _coming in Phase 2_ — `https://thwake-monitor.projects.earthengine.app/view/thwake`
- 📖 **Story page:** _coming in Phase 2_ — `https://jm-wanja.github.io/thwake-reservoir-remote-sensing-monitor/`
- 📊 **Data (CSV):** _coming in Phase 2_ — `data/processed/thwake_timeseries.csv`

## Why this project

Thwake Dam is planned to be one of Kenya's largest reservoirs (688 million m³ at a full supply level of 912 m a.s.l.), supplying water to ~1.3 million people, irrigation and hydropower. Progress reaches the public mainly through press statements, and no independent satellite monitoring of it exists. This project builds one — and asks whether the polluted Athi River inflow shows up in the new reservoir's water.

## How it works

1. **Baseline (before filling):** pre-dam elevation models (Copernicus DEM, SRTM) map the valley below the full supply level and give an area–elevation–volume curve, frozen before any filling data is analysed.
2. **Water detection:** Sentinel-2 (optical, MNDWI + Otsu) and Sentinel-1 (radar, sees through cloud) map the water surface every few days.
3. **Area → level → volume → % full**, with uncertainty ranges and quality flags on every number.
4. **Water quality & regional change:** turbidity and chlorophyll indicators, evaporation, flooded land and downstream irrigation.
5. **Publishing:** an Earth Engine App, a Quarto story page on GitHub Pages, and a CSV time series — updated monthly by GitHub Actions.

## Project documentation

| Read this | For |
|-----------|-----|
| [Project brief](docs/project-brief.md) | Why it exists, who it's for, goals, non-goals, success criteria |
| [Background: Thwake Dam](docs/background-thwake.md) | Sourced facts about the dam (FSL, capacity, timeline) |
| [Methodology](docs/methodology.md) | Water detection, volume estimation, uncertainty, water quality, validation, references |
| [Data sources](docs/data-sources.md) | Every dataset, with Earth Engine IDs, resolution and licence |
| [Architecture](docs/architecture.md) | System design, data flow, repository layout, data contracts, deployment |
| [Decision records](docs/decisions/) | Key decisions with the alternatives considered (stack, sensors, volume method, naming) |
| [Roadmap](docs/roadmap.md) | Phases (incl. a validation phase before filling), milestones, update cadence |
| [Engineering roadmap](docs/engineering-roadmap.md) | Quality plan: validation, provenance, CI, ML comparison |
| [Risks & limitations](docs/risks-and-limitations.md) | What the project can and cannot claim |
| [Open questions](docs/open-questions.md) | What is still being verified |
| [Glossary](docs/glossary.md) | Plain-language definitions of technical terms |

Full index: [`docs/README.md`](docs/README.md).

### How this project is built

Development uses AI coding agents under explicit rules ([`AGENTS.md`](AGENTS.md)), with each task a reviewed slash command in [`.claude/commands/`](.claude/commands/) ([workflow](docs/agent-workflow.md)). Decisions, fact-checking, approvals, commits and publishing are done by the author ([human steps](docs/human-steps.md)); agents are technically blocked from writing to git repositories.

## Development

```bash
make install      # uv sync from the lockfile
make check        # ruff + mypy + pytest with coverage (what CI runs)
make help         # all tasks
uv run python -m thwake --help
```

Quality gates: CI on every push (lint, format, type check, tests incl. agent-guardrail tests, large-file guard), pre-commit hooks (incl. secret scan), Dependabot, actions pinned by SHA.

Earth Engine access requires a registered Google Cloud project; set `EE_PROJECT` in a local `.env` (see [`.env.example`](.env.example)) and run `uv run earthengine authenticate`.

## Licence & citation

Code: [MIT](LICENSE). Data, figures and documentation: [CC BY 4.0](LICENSE-DATA.md); third-party data keep their own terms. To cite this work, see [`CITATION.cff`](CITATION.cff).
