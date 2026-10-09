# 0003 — Free deployment: Earth Engine App + GitHub Pages + GitHub Actions

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
Requirements: free, no custom domain needed, a public link in the README that users can interact with, code on GitHub, regular updates. GitHub Pages serves static files only — it cannot run Python or Earth Engine.

## Decision
- **Interactive app → Earth Engine Apps** (JavaScript from the EE Code Editor; source kept in `app/ee-app/`).
- **Story page + data → GitHub Pages**, built with **Quarto** (static HTML + Leaflet/MapLibre + JuxtaposeJS + charts).
- **Updates → GitHub Actions** (scheduled Python pipeline with EE service account; build & deploy Pages).
- Both public URLs are linked at the top of the README.

## Alternatives considered
- **Streamlit Community Cloud** — free and Python-only, but requires EE service-account auth inside a public app, sleeps when idle, and adds a server to maintain. Possible later for a richer dashboard.
- **Hugging Face Spaces** — similar trade-offs to Streamlit.
- **ArcGIS StoryMaps (public account)** — limited features, platform lock-in, terms may change.
- **GitHub Pages only (no EE App)** — simplest, but no live satellite exploration.

## Consequences
- Two languages (Python + JS). Mitigation: thresholds/parameters documented in config and methodology; CSV is canonical; app is for exploration.
- Zero hosting cost; no servers.
- EE App publishing is a manual step in the Code Editor (repo copy is source of truth).
