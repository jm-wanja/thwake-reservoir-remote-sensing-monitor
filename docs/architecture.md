# Architecture — Thwake Reservoir Remote Sensing Monitor

Status: **Draft v0.1** (Phase 1 in progress: AOI and max extent implemented) · Last updated: 2026-10-09

## 1. Goals the architecture must serve

1. Turn free satellite data into a **trustworthy time series** of reservoir area, level, volume, % full, and water-quality indicators.
2. Publish it **for free** as (a) a live interactive app and (b) a public story page, both linked from the README.
3. **Update itself** on a schedule with minimal manual work, for years.
4. Be **reproducible**: anyone can rerun the pipeline from the repo + public data.

## 2. System overview

```
                         ┌──────────────────────────────────────────┐
                         │         Google Earth Engine (cloud)       │
                         │  Sentinel-1 · Sentinel-2 · DEM · CHIRPS   │
                         │  ERA5-Land · WorldCover · JRC GSW         │
                         └───────────────┬──────────────────────────┘
                                         │  (server-side compute)
          ┌──────────────────────────────┼───────────────────────────────┐
          │                              │                               │
          ▼                              ▼                               ▼
┌───────────────────┐        ┌───────────────────────┐        ┌───────────────────────┐
│ A. Baseline        │        │ B. Processing pipeline │        │ C. Earth Engine App   │
│ (run once, frozen) │──────► │ (Python, scheduled)    │        │ (JavaScript, live)    │
│ AOI, max-extent    │  AEV   │ water masks → area →   │        │ date picker, map,     │
│ mask, AEV curve    │ curve  │ volume → % full;       │        │ outline, chart        │
└───────────────────┘        │ water quality; rainfall│        └──────────┬────────────┘
                             └──────────┬────────────┘                   │
                                        │ small derived outputs           │ hosted by Google
                                        ▼                                 │ *.projects.earthengine.app
                             ┌───────────────────────┐                   │
                             │ D. Repo data store     │                   │
                             │ data/processed/*.csv   │                   │
                             │ *.geojson, media/*.gif │                   │
                             └──────────┬────────────┘                   │
                                        ▼                                 │
                             ┌───────────────────────┐                   │
                             │ E. Story page (Quarto) │◄── embeds/links ──┘
                             │ static HTML + JS maps  │
                             └──────────┬────────────┘
                                        ▼
                             ┌───────────────────────┐
                             │ GitHub Pages           │  <user>.github.io/thwake-reservoir-remote-sensing-monitor
                             └───────────────────────┘
                                        ▲
                             ┌──────────┴────────────┐
                             │ F. GitHub Actions      │  monthly + after each rainy season:
                             │ run B → commit D →     │  export, test, build E, deploy
                             │ build & deploy E       │
                             └───────────────────────┘
```

## 3. Components

### A. Baseline (Phase 1 — run once, then frozen)
- **Inputs:** pre-dam DEM (Copernicus GLO-30, cross-checked with SRTM), dam wall location, design full supply level (FSL) ⚠️ verify.
- **Does:**
  1. Builds the **Area of Interest (AOI)**: valley upstream of the dam wall, buffered above FSL.
  2. Builds the **max-extent mask**: DEM pixels below FSL that are hydrologically connected to the dam site → the only place water may be counted.
  3. Computes the **Area–Elevation–Volume (AEV) curve** by flooding the DEM in 0.5 m steps.
  4. Captures **pre-filling reference**: land cover of the flood zone (WorldCover / Dynamic World), cloud-free Sentinel-2 composite, historic river channel (JRC GSW).
- **Outputs (versioned, committed):** `data/baseline/aoi.geojson`, `max_extent.geojson`, `aev_curve_v1.csv` (+ `.json`), `landcover_flood_zone.csv` (+ `.json`), `river_channel.geojson`, `before_composite.json`; `media/aev_curve_v1.png`, `media/before_composite.png`; the full composite as an EE asset (`before_composite_s2_v1`). Freeze manifest `data/baseline/baseline_v1.sha256` (checked in CI). Write-up and freeze record: [baseline-v1.md](baseline-v1.md).
- **Rule:** frozen once filling analysis begins; changes need an ADR and a new version suffix (`_v2`).

### B. Processing pipeline (Python, `src/thwake/`)
Modules (one responsibility each):

| Module | Responsibility |
|--------|----------------|
| `config` | Load YAML config (AOI, dates, thresholds, EE collection IDs, capacity). |
| `baseline` | Phase 1: AOI and max-extent mask (wall barrier, flood fill, rim pass closures); AEV curve per DEM and rim check (Earth Engine side). |
| `reference` | Phase 1: pre-filling reference layers: land cover in the max extent, Sentinel-2 "before" composite (asset + PNG), JRC river channel. |
| `ee_auth` | Authenticate (user creds locally, service account in CI). |
| `collections` | Fetch & filter S1, S2, CHIRPS, ERA5 for AOI/date range; S2 cloud masking (Cloud Score+). |
| `water_s2` | MNDWI/NDWI → Otsu threshold → water mask; daily Sentinel-2 mosaics (implemented in prompt 05a). |
| `water_s1` | Speckle filter → VV backscatter → Otsu / dB threshold → water mask; daily Sentinel-1 mosaics (prompt 05a). |
| `otsu` | Otsu threshold from a fixed-bin histogram, with plausible-range fallback (shared by `water_s1`/`water_s2`). |
| `postprocess` | Clip to max-extent, keep component connected to dam, remove specks, gap-fill cloud-obscured edges (optional, see methodology). |
| `area` | Pixel area sum → km², with a range for obscured pixels and edge pixels (prompt 05a; threshold sensitivity in prompt 07). |
| `volume` | AEV curve: build from per-bin sums, read/write CSV; area → level & volume interpolation; (Phase 2) uncertainty propagation. |
| `quality` | (Phase 3) turbidity & chlorophyll-proxy indices over water pixels; stats per zone (inflow arm vs dam). |
| `climate` | Catchment rainfall (CHIRPS), evaporation (ERA5-Land) aggregates. |
| `regional` | (Phase 4) land-cover change, downstream NDVI dry-season irrigation signal. |
| `export` | Write CSV/GeoJSON/media (AEV figure so far); append to canonical time series idempotently. |
| `qa` | Sanity checks: S1 vs S2 agreement, impossible jumps, area > max-extent, etc. |
| `validation` | Phase 1.5: reference-reservoir check (mask, DEM curves, scene areas in Earth Engine; area → level vs published levels, metrics, figure offline). See [validation.md](validation.md). |

Entry points (CLI, e.g. `python -m thwake <command>`): `baseline`, `validate reference --name <reservoir> [--compare-only]`, `update --since <date>`, `media`, `qa`.

### C. Earth Engine App (JavaScript, `app/ee-app/`)
- Live explorer hosted by Google. Reads collections directly + baseline assets.
- Features: date slider / image picker, true-colour + water outline overlay, S1/S2 toggle, area/volume chart, before/after swipe, water-quality layer (Phase 3).
- Source is kept in the repo (`app/ee-app/main.js`) and pasted/published from the EE Code Editor. The **repo copy is the source of truth**.
- Logic duplication with Python is acceptable but must follow the same documented thresholds (see [ADR 0003](decisions/0003-free-deployment-ee-app-and-github-pages.md)).

### D. Repo data store
- Only **small, derived, public** files: CSV time series, GeoJSON outlines, compressed GIF/MP4/PNG.
- Large rasters stay in Earth Engine assets or are regenerated.

### E. Story page (Quarto, `site/`)
- Scroll-driven narrative: the valley before → the dam → the lake forms → is the water clean? → what it means.
- Reads `data/processed/*.csv` and `*.geojson` at build time / client side.
- Leaflet or MapLibre maps (OSM tiles), JuxtaposeJS before/after slider, embedded time-lapse, charts (Plotly or Observable Plot).
- Links to the EE App and to the raw data downloads.

### F. Automation (GitHub Actions, `.github/workflows/`)
- `update.yml` — scheduled (monthly + manual trigger): auth via service-account secret → `thwake update` → `thwake qa` → commit changed outputs.
- `pages.yml` — on push to `main` touching `site/` or `data/processed/`: build Quarto → deploy to GitHub Pages.
- `ci.yml` — on PR: lint (`ruff`), tests (`pytest`), no-large-file check.

## 4. Data flow per update

1. Find new S1/S2 scenes over AOI since last date in `thwake_timeseries.csv`.
2. For each scene: water mask → clip to max-extent → area (+ range).
3. Area → level → volume (+ range) via frozen AEV curve → % full.
4. (Phase 3+) water-quality stats on water pixels.
5. Attach catchment rainfall for the preceding window.
6. QA checks; flag (don't drop) suspicious rows.
7. Append to time series; regenerate charts/media; rebuild story page.

## 5. Repository layout

See [ADR 0010](decisions/0010-repository-layout.md).

```
thwake-reservoir-remote-sensing-monitor/
├── README.md                 # front door: why, how, live links, links into docs/
├── AGENTS.md                 # rules for AI agents (cross-tool convention)
├── CLAUDE.md                 # imports AGENTS.md for Claude Code
├── CHANGELOG.md              # notable changes (Keep a Changelog)
├── CITATION.cff              # how to cite the software/data
├── LICENSE                   # MIT (code)
├── LICENSE-DATA.md           # CC BY 4.0 (data, figures, docs) + third-party terms
├── Makefile                  # make check / test / lint / typecheck / baseline
├── pyproject.toml, uv.lock   # dependencies (pinned) + tool config (ruff, mypy, pytest, coverage)
├── .pre-commit-config.yaml   # ruff, large files, private-key + secret scan, nbstripout
├── .claude/
│   ├── settings.json         # permissions: agents read-only on git/GitHub
│   ├── hooks/                # block-repo-writes.sh (tested in tests/test_guardrail_hook.py)
│   └── commands/             # task prompts as slash commands (/04-phase1-aev-curve …)
├── .github/
│   ├── workflows/            # ci.yml (+ update.yml, pages.yml in Phase 2); actions pinned by SHA
│   ├── dependabot.yml
│   └── pull_request_template.md
├── docs/                     # human-facing documentation (index: docs/README.md)
│   └── decisions/            # ADRs
├── app/ee-app/               # Earth Engine App JavaScript (source of truth)
├── config/                   # settings.yaml, ee_collections.yaml, thresholds.yaml
├── data/
│   ├── baseline/             # frozen AOI, max-extent, AEV curve (versioned)
│   ├── processed/            # thwake_timeseries.csv, outlines/*.geojson, run metadata
│   ├── validation/           # Phase 1.5: reference-reservoir outputs, labelled shorelines, metrics
│   └── external/             # small reference files (official figures w/ source)
├── media/                    # time-lapse GIF/MP4, static figures for site/README
├── notebooks/                # exploration only (outputs stripped by nbstripout)
├── site/                     # Quarto story page source
├── src/thwake/               # pipeline package (modules in §3B)
└── tests/                    # pytest, synthetic fixtures, guardrail tests
```

## 6. Data contracts

### `data/processed/thwake_timeseries.csv` (one row per scene)

| Column | Type | Description |
|--------|------|-------------|
| `date` | ISO date | Image acquisition date (UTC) |
| `sensor` | `S1` \| `S2` | Source sensor |
| `scene_id` | str | EE image ID |
| `valid_fraction` | 0–1 | Share of max-extent not obscured (clouds/no data) |
| `area_km2` | float | Best-estimate water area |
| `area_km2_low` / `_high` | float | Sensitivity range |
| `level_m_asl` | float | Estimated water level |
| `volume_mcm` | float | Best-estimate volume (million m³) |
| `volume_mcm_low` / `_high` | float | Uncertainty range |
| `pct_full` | float | volume ÷ design capacity × 100 |
| `rain_mm_prev7d` | float | Catchment rainfall, preceding 7 days |
| `qa_flag` | str | `ok`, `low_coverage`, `sensor_disagree`, `jump`, … |
| `method_version` | str | Pipeline/AEV version used |

### `data/baseline/aev_curve_v1.csv`
`level_m_asl, area_km2, volume_mcm, dem_source`

Changes to these schemas require an ADR.

## 7. Deployment summary

| Surface | Host | Cost | URL pattern |
|---------|------|------|-------------|
| Interactive app | Earth Engine Apps | Free (non-commercial) | `https://<cloud-project>.projects.earthengine.app/view/thwake` |
| Story page + data | GitHub Pages | Free (public repo) | `https://<github-user>.github.io/thwake-reservoir-remote-sensing-monitor/` |
| Automation | GitHub Actions | Free (public repo) | — |

Details: [docs/deployment.md](deployment.md).

## 8. Security & secrets

- EE service-account JSON key → GitHub secret `EE_SERVICE_ACCOUNT_KEY` only. Never in repo, logs, or notebooks.
- Service account has minimal roles (Earth Engine resource viewer/writer on the project only).
- `.gitignore` must cover `*.json` keys, `.env`, `credentials/`, large rasters (`*.tif`).

## 9. Quality attributes

| Attribute | How it's achieved |
|-----------|-------------------|
| Trustworthiness | Two sensors, frozen baseline, QA flags, uncertainty ranges, published method |
| Reproducibility | Config-driven, pinned dependencies, public data only |
| Low maintenance | Scheduled Actions, idempotent updates, no servers |
| Cost | $0 — all free tiers |
| Accessibility | Plain-language story page, alt text, colour-blind-safe palettes, mobile layout |

## 10. Known architectural trade-offs

- **Two languages (Python + JS).** EE Apps require JavaScript; analysis is Python. Mitigated by shared thresholds in config and documenting them. See ADR 0003.
- **EE App and pipeline can disagree slightly** (live vs exported). The CSV is the canonical record; the app is for exploration.
- **Earth Engine dependency.** If non-commercial access changes, the pipeline could move to Microsoft Planetary Computer / Copernicus Data Space (open STAC) — would need an ADR.
