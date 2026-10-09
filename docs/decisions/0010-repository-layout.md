# 0010 — Repository layout: root AGENTS.md, docs/, prompts as slash commands

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
All documentation, decisions, agent rules and task prompts lived in a hidden `.ai/` folder. `.ai/` is not a recognised convention: agent tools look for `AGENTS.md` / `CLAUDE.md` at the repo root, and human reviewers expect documentation in `docs/` and decision records in `docs/decisions/` (or `docs/adr/`). Reviewers skim; hidden folders hide the strongest material.

## Decision
- `AGENTS.md` at the repo root (cross-tool convention); `CLAUDE.md` imports it for Claude Code.
- Human-facing documentation in `docs/` (brief, background, methodology, data sources, architecture, roadmap, deployment, risks, open questions, glossary, human steps, engineering roadmap); decision records in `docs/decisions/`.
- Task prompts as Claude Code project slash commands in `.claude/commands/` (e.g. `/04-phase1-aev-curve`); the workflow guide is `docs/agent-workflow.md`. Commands are committed (shared, reproducible) and protected from agent edits by `.claude/settings.json`.
- README links directly to the key docs.

## Alternatives considered
- **Keep `.ai/`** — works, but non-standard and hidden from reviewers; agents needed a manual "read .ai/AGENTS.md" step.
- **`docs/adr/` naming** — equally conventional; `docs/decisions/` chosen for plain-language clarity.
- **Git-ignore prompts** — loses reproducibility and portfolio evidence of the workflow; rejected.

## Consequences
- One-time move of ~40 files; all links rewritten and checked (0 broken).
- Agents pick up rules automatically; `/session-start` becomes optional.
- Link paths inside ADRs 0001–0007 were updated mechanically to the new layout; their decision text is unchanged (accepted ADRs are immutable).
