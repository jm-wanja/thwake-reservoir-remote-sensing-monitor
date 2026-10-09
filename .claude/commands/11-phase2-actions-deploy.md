---
description: "Phase 2: GitHub Actions and deployment"
---

<!-- Prompt 11 — Phase 2: GitHub Actions and deployment. Run in a fresh session: /11-phase2-actions-deploy -->

Prerequisites (human must have done these): H3 (public repo, Pages source = GitHub Actions) and H4 (secret EE_SERVICE_ACCOUNT_KEY, variable EE_PROJECT).
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Automate updates and deploy the story page to GitHub Pages
(ARCHITECTURE §3F, docs/deployment.md, ADR 0003).

Read first: docs/deployment.md, ARCHITECTURE §3F and §8.

Implement:
- ee_auth: service-account auth when EE_SERVICE_ACCOUNT_KEY env var is present, user
  credentials otherwise. Never log the key.
- .github/workflows/update.yml: cron monthly + workflow_dispatch; install deps; write key
  from secret to a temp file outside the repo; run `thwake update`, `thwake qa`,
  `thwake media`; commit changed data/ and media/ files with a bot message; minimal
  permissions (contents: write).
- .github/workflows/pages.yml: on push to main touching site/, data/processed/, media/;
  install Quarto; render; deploy with actions/upload-pages-artifact + actions/deploy-pages.
- Update README.md: story page URL (https://<user>.github.io/thwake-reservoir-remote-sensing-monitor/),
  data link, "last updated" and latest % full (auto-updated by update.yml).

- Budget: estimate the monthly update's EECU cost (only new scenes over the Thwake AOI) and
  record it in docs/deployment.md; the scheduled job must process incrementally, never a full backfill.
- Run monitoring (engineering roadmap D3): failed update runs must be visible (job summary +
  GitHub's failure notification to the owner); add a short run summary to $GITHUB_STEP_SUMMARY.
- Pin all actions by commit SHA (consistent with ci.yml) and keep permissions minimal.

Acceptance criteria:
- Workflows pass on a manual run; Pages URL is live.
- Secrets never appear in logs or files. Update roadmap and AGENTS.md status. Stop.
