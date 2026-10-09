# Thwake Reservoir Remote Sensing Monitor 🛰️💧

*A remote sensing and geospatial data science project using Sentinel-1/2 and Google Earth Engine.*

An independent, satellite-based record of **Thwake Dam reservoir** (Makueni/Kitui, Kenya) — how fast it fills, whether the water is clean, and what it changes in the region. Built entirely on free, public data.

> **Status:** Phase 0 complete (planning, research, scaffold). Phase 1 (pre-filling baseline) next. First impoundment is officially targeted for early 2027.

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
| [Project brief](.ai/docs/01-project-brief.md) | Why it exists, who it's for, goals, non-goals, success criteria |
| [Background: Thwake Dam](.ai/docs/02-background-thwake.md) | Sourced facts about the dam (FSL, capacity, timeline) |
| [Methodology](.ai/docs/03-methodology.md) | Water detection, volume estimation, uncertainty, water quality, validation, references |
| [Data sources](.ai/docs/04-data-sources.md) | Every dataset, with Earth Engine IDs, resolution and licence |
| [Architecture](.ai/ARCHITECTURE.md) | System design, data flow, repository layout, data contracts, deployment |
| [Decision records](.ai/decisions/) | Key decisions with the alternatives considered (stack, sensors, volume method, naming) |
| [Roadmap](.ai/docs/05-roadmap.md) | Phases, milestones and update cadence |
| [Risks & limitations](.ai/docs/07-risks-and-limitations.md) | What the project can and cannot claim |
| [Open questions](.ai/docs/08-open-questions.md) | What is still being verified |
| [Glossary](.ai/docs/glossary.md) | Plain-language definitions of technical terms |

Full index: [`.ai/README.md`](.ai/README.md).

### How this project is built

Development uses AI coding agents under explicit rules ([`AGENTS.md`](.ai/AGENTS.md)) and task prompts ([`.ai/prompts/`](.ai/prompts/README.md)). Decisions, fact-checking, approvals, commits and publishing are done by the author ([human steps](.ai/HUMAN-STEPS.md)); agents are technically blocked from writing to git repositories.

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
uv run python -m thwake --help
```

Earth Engine access requires a registered Google Cloud project; set `EE_PROJECT` in a local `.env` (see [`.env.example`](.env.example)) and run `uv run earthengine authenticate`.

## Licence

Not chosen yet (see [open questions](.ai/docs/08-open-questions.md)).
