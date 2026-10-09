# Documentation

Everything about **what** this project is, **why** it exists, **how** it is built and **what has been decided**. Start with the root [README](../README.md); agent rules are in [AGENTS.md](../AGENTS.md).

| # | Document | What it answers |
|---|----------|-----------------|
| 1 | [project-brief.md](project-brief.md) | What, why, who it's for, goals, non-goals, success criteria |
| 2 | [background-thwake.md](background-thwake.md) | Sourced facts about Thwake Dam |
| 3 | [architecture.md](architecture.md) | System design: components, data flow, repository layout, data contracts, deployment |
| 4 | [methodology.md](methodology.md) | The science: water detection, area → volume, uncertainty, water quality, regional change |
| 5 | [data-sources.md](data-sources.md) | Every dataset, with Earth Engine IDs, resolution, licence |
| 6 | [roadmap.md](roadmap.md) | Phases (incl. Phase 1.5 Validation), milestones, update cadence |
| 7 | [engineering-roadmap.md](engineering-roadmap.md) | Reviewer-level quality plan: validation, provenance, CI, ML comparison |
| 8 | [deployment.md](deployment.md) | How the app and story page are published for free |
| 9 | [risks-and-limitations.md](risks-and-limitations.md) | What can go wrong, what the project cannot claim |
| 10 | [open-questions.md](open-questions.md) | Unresolved questions to verify or decide |
| 11 | [glossary.md](glossary.md) | Plain-language definitions of technical terms |
| 12 | [decisions/](decisions/) | Architecture Decision Records (ADRs) — one file per decision |
| 13 | [agent-workflow.md](agent-workflow.md) | How the project is built with AI agents: slash commands, order, review |
| 14 | [human-steps.md](human-steps.md) | Steps only the author does: accounts, secrets, commits, publishing, approvals |

## Maintenance rules

- **Decisions** go in `decisions/NNNN-short-title.md` using [decisions/0000-template.md](decisions/0000-template.md). Never edit an accepted ADR's decision — supersede it with a new ADR.
- **Facts** (dam capacity, dates, etc.) must cite a source. Unverified facts are marked `⚠️ verify`.
- **Open questions** live in [open-questions.md](open-questions.md) until resolved; record the answer where it belongs (doc or ADR) and strike it from the list.
- **Changes** visible to users go in [`CHANGELOG.md`](../CHANGELOG.md).
- Keep docs short and current. An outdated doc is worse than no doc.
