# Prompts — building the project with an AI agent

The docs in `.ai/` give an agent **context**. These prompts give it **bounded tasks** in the right order, each with acceptance criteria and a stop point. Run them one at a time, review the result, then move on.

## How to use

1. Start a fresh agent session in the repo root.
2. Paste [00-session-start.md](00-session-start.md) first (every session).
3. Paste the next numbered prompt.
4. Review the diff/output against the prompt's **Acceptance criteria**, run tests, then **you** commit and push (agents never do — see [HUMAN-STEPS.md H3](../HUMAN-STEPS.md#h3--git-repository-create-commit-push)).
5. Tick it off below.

One prompt = one session (or one PR) is ideal. Don't paste several at once.

## Order & status

| # | Prompt | Phase | Needs human first? | Done |
|---|--------|-------|--------------------|------|
| 00 | [Session start](00-session-start.md) | — | — | (every time) |
| 01 | [Resolve open questions](01-resolve-open-questions.md) | 0 | — | ☐ |
| 02 | [Scaffold repo](02-scaffold-repo.md) | 0 | H1 (Python env) | ☐ |
| 03 | [AOI & max-extent mask](03-phase1-aoi-max-extent.md) | 1 | H2 (Earth Engine) | ☐ |
| 04 | [AEV curve](04-phase1-aev-curve.md) | 1 | — | ☐ |
| 05 | [Baseline reference & freeze](05-phase1-baseline-freeze.md) | 1 | review & approve freeze | ☐ |
| 06 | [Water detection S2 + S1](06-phase2-water-detection.md) | 2 | — | ☐ |
| 07 | [Area, volume, uncertainty, QA](07-phase2-volume-uncertainty-qa.md) | 2 | — | ☐ |
| 08 | [Time series & update CLI](08-phase2-timeseries-cli.md) | 2 | — | ☐ |
| 09 | [Earth Engine App](09-phase2-ee-app.md) | 2 | H5 (publish app) | ☐ |
| 10 | [Story page](10-phase2-story-page.md) | 2 | — | ☐ |
| 11 | [GitHub Actions & deploy](11-phase2-actions-deploy.md) | 2 | H3, H4 (repo, secrets, Pages) | ☐ |
| 12 | [Water quality](12-phase3-water-quality.md) | 3 | — | ☐ |
| 13 | [Regional change](13-phase4-regional-change.md) | 4 | H6 (irrigation boundaries) | ☐ |
| 90 | [Seasonal update review](90-seasonal-update-review.md) | ongoing | — | recurring |
| 91 | [Record a decision (ADR)](91-record-decision.md) | any | — | as needed |
| 92 | [Docs sync check](92-docs-sync-check.md) | any | — | after each phase |

## Human-only steps (an agent cannot or must not do these)

Full checklist with how-to: **[../HUMAN-STEPS.md](../HUMAN-STEPS.md)**. Summary:

- **H1** Local tools — Python 3.11, uv, Git, gh, Quarto.
- **H2** Earth Engine — sign up, Cloud project registered for non-commercial use, `earthengine authenticate`, `.env`.
- **H3** Git — `git init`, create the public GitHub repo, **every commit, push and tag**, enable Pages.
- **H4** Service account + GitHub secrets — never paste keys into an agent chat.
- **H5** Publish the Earth Engine App and add its URL to the README.
- **H6** Verify ⚠️ facts, supply documents, approve the baseline freeze and ADRs, choose the licence.
- **H7** Going public — check live links, approve public wording, seasonal write-ups.
- **H8** Ongoing — rotate keys, watch failed Actions, check EE terms.

## Tips

- If the agent has no web access, prompt 01 becomes a human task.
- If the agent starts inventing numbers (FSL, capacity, coordinates) — stop it; that violates AGENTS.md rule 5.
- If a prompt reveals a needed decision, use prompt 91 before continuing.
