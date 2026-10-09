# 0007 — Project name and primary audience

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
The working name was "Thwake Reservoir Monitor" (`thwake-reservoir-monitor`). The project serves three audiences (public, employers, researchers), but the owner's main goal is **portfolio and research**. The method literature it builds on (e.g. *Remote Sensing* journal, GERD Sentinel-1 studies) uses "remote sensing" as the field term.

## Decision
- Repository / URL slug: **`thwake-reservoir-remote-sensing-monitor`**
- Display title: **"Thwake Reservoir Remote Sensing Monitor"**
- Subtitle everywhere: *"A remote sensing and geospatial data science project using Sentinel-1/2 and Google Earth Engine."*
- **Primary audiences: portfolio (employers) and research.** Public communication remains a goal (story page in plain language), but trade-offs favour rigour and field vocabulary.
- Python package name stays `thwake` (unchanged CLI/imports).

## Alternatives considered
- **`thwake-reservoir-remote-sensing`** (shorter slug) — considered, but the owner preferred the slug to match the display title exactly.
- **Keep "Thwake Reservoir Monitor"** with "remote sensing" only in description/topics — shorter and more public-friendly, but hides the field/skill at a glance.
- **Different names per surface** (short repo name, remote sensing in subtitle) — reasonable compromise, but less direct for the primary audiences.

## Consequences
- Longer URL: `https://<user>.github.io/thwake-reservoir-remote-sensing-monitor/`.
- Local folder must be renamed to match (human step).
- Story page should still explain "remote sensing" in plain words for public readers.
- ADR 0001 text mentions the old working name; this ADR supersedes the naming only.
