# 0001 — Thwake as a standalone project

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
Exploration started from Mombasa's water and sewerage system and produced three ideas: (1) a Mombasa water dashboard (WASREB + census data), (2) Mwache Dam satellite monitoring, (3) Thwake Dam satellite monitoring. Mwache and Thwake share methods; both begin impounding around Oct–Nov 2026. No existing satellite monitoring was found for either.

## Decision
Thwake Reservoir Monitor is its **own repository and project**. The Mwache monitor and the Mombasa water dashboard are separate, independent projects.

## Alternatives considered
- **Combined "Kenya's new reservoirs" (Thwake + Mwache)** — same code could run on both, but doubles verification work and blurs the story. Can be revisited later by reusing this pipeline.
- **Mwache as part of the Mombasa dashboard** — rejected earlier; different data types and skills.

## Consequences
- Focused scope and a clear story (filling, water quality from the polluted Athi, semi-arid change).
- Pipeline should stay **dam-agnostic where cheap** (AOI, FSL, capacity in config) so Mwache can reuse it later.
