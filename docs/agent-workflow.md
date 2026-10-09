# Agent workflow — building the project with AI coding agents

Rules for agents live in [AGENTS.md](../AGENTS.md) (loaded automatically by Claude Code via `CLAUDE.md`, and read by other agent tools). Each unit of work is a **slash command** in [`.claude/commands/`](../.claude/commands/): a bounded task with prerequisites, acceptance criteria and a stop point. The author reviews and commits every result; agents are technically blocked from writing to git ([ADR 0010](decisions/0010-repository-layout.md), `.claude/settings.json`).

## How to run a task

1. Open a **fresh** Claude Code session in the repository root (one task per session).
2. Optional: `/session-start` — the agent confirms it has read the rules and reports status.
3. Run the next command, e.g. `/04-phase1-aev-curve`.
4. Review the result against the command's **Acceptance criteria**: diff in VS Code Source Control, `make check`, outputs/notebook.
5. **You** commit (and, from prompt 04 on, preferably via a branch + pull request — see [human-steps.md](human-steps.md) H3). Tick the row below.

## Order & status

| Command | Phase | Human prerequisites | Done |
|---------|-------|---------------------|------|
| `/session-start` | — | — | (optional, any time) |
| `/01-resolve-open-questions` | 0 | — | ☑ |
| `/02-scaffold-repo` | 0 | H1 | ☑ |
| `/03-phase1-aoi-max-extent` | 1 | H2 | ☑ |
| `/04-phase1-aev-curve` | 1 | — | ☐ |
| `/05-phase1-baseline-freeze` | 1 | review & approve freeze | ☐ |
| `/05a-validation-reference-reservoir` | 1.5 | approve reference choice | ☐ |
| `/05b-validation-labelled-set` | 1.5 | label ~25 scenes (H6) | ☐ |
| `/05c-validation-evaluation-harness` | 1.5 | approve thresholds | ☐ |
| `/05d-ml-vs-otsu-comparison` | 1.5 (optional) | approve design | ☐ |
| `/06-phase2-water-detection` | 2 | — | ☐ |
| `/07-phase2-volume-uncertainty-qa` | 2 | — | ☐ |
| `/08-phase2-timeseries-cli` | 2 | — | ☐ |
| `/09-phase2-ee-app` | 2 | H5 (publish app) | ☐ |
| `/10-phase2-story-page` | 2 | — | ☐ |
| `/11-phase2-actions-deploy` | 2 | H3, H4 (Pages, secrets) | ☐ |
| `/12-phase3-water-quality` | 3 | — | ☐ |
| `/13-phase4-regional-change` | 4 | H6 (irrigation boundaries) | ☐ |
| `/90-seasonal-update-review` | ongoing | — | recurring |
| `/91-record-decision` | any | — | as needed |
| `/92-docs-sync-check` | any | — | after each phase |

## Human-only steps

Full checklist: [human-steps.md](human-steps.md). In short: local tools (H1), Earth Engine (H2), git — **every commit, push, tag and PR merge** (H3), service account + secrets (H4), publishing the Earth Engine App (H5), verifying facts and approvals (H6), going public (H7), ongoing upkeep (H8).

## Tips

- If the agent invents numbers (FSL, capacity, coordinates) — stop it; that violates AGENTS.md rule 5.
- If a task needs a decision, run `/91-record-decision` first.
- Commands are protected from agent edits; change them yourself (or in a separate planning session) and commit.
