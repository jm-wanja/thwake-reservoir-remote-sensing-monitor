# `.ai/` — Project knowledge base

This folder is the single source of truth for **what** this project is, **why** it exists, **how** it is built, and **what has been decided**. It is written for both humans and AI coding agents.

Read in this order:

| # | File | What it answers |
|---|------|-----------------|
| 1 | [AGENTS.md](AGENTS.md) | Rules and context for anyone (human or AI) working on the repo |
| 2 | [docs/01-project-brief.md](docs/01-project-brief.md) | What, why, who it is for, goals, non-goals, success criteria |
| 3 | [docs/02-background-thwake.md](docs/02-background-thwake.md) | Facts about Thwake Dam, with sources |
| 4 | [ARCHITECTURE.md](ARCHITECTURE.md) | System design: components, data flow, folders, deployment |
| 5 | [docs/03-methodology.md](docs/03-methodology.md) | The science: water detection, area→volume, water quality, regional change |
| 6 | [docs/04-data-sources.md](docs/04-data-sources.md) | Every dataset used, with IDs, resolution, licence |
| 7 | [docs/05-roadmap.md](docs/05-roadmap.md) | Phases, milestones, update cadence |
| 8 | [docs/06-deployment.md](docs/06-deployment.md) | How the app and story page are published for free |
| 9 | [docs/07-risks-and-limitations.md](docs/07-risks-and-limitations.md) | What can go wrong, what the project cannot claim |
| 10 | [docs/08-open-questions.md](docs/08-open-questions.md) | Unresolved questions to verify or decide |
| 11 | [docs/glossary.md](docs/glossary.md) | Plain-language definitions of technical terms |
| 12 | [decisions/](decisions/) | Architecture Decision Records (ADRs) — one file per decision |
| 13 | [prompts/](prompts/README.md) | Ordered, copy-paste prompts for building the project with an AI agent |
| 14 | [HUMAN-STEPS.md](HUMAN-STEPS.md) | Steps only you can do: accounts, secrets, commits & pushes, publishing, approvals |

## Maintenance rules

- **Decisions** go in `decisions/NNNN-short-title.md` using [decisions/0000-template.md](decisions/0000-template.md). Never edit an accepted ADR's decision — supersede it with a new ADR.
- **Facts** (dam capacity, dates, etc.) must cite a source. Unverified facts are marked `⚠️ verify`.
- **Open questions** live in `docs/08-open-questions.md` until resolved; when resolved, record the answer where it belongs (doc or ADR) and strike it from the list.
- Keep docs short and current. An outdated doc is worse than no doc.
