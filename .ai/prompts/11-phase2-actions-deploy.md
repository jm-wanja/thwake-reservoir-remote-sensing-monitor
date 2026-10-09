# 11 — Phase 2: GitHub Actions and deployment

**Requires:** H3 (public repo, Pages source = GitHub Actions) and H4 (secret EE_SERVICE_ACCOUNT_KEY, variable EE_PROJECT).

```
Task: Automate updates and deploy the story page to GitHub Pages
(ARCHITECTURE §3F, .ai/docs/06-deployment.md, ADR 0003).

Read first: .ai/docs/06-deployment.md, ARCHITECTURE §3F and §8.

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

Acceptance criteria:
- Workflows pass on a manual run; Pages URL is live.
- Secrets never appear in logs or files. Update roadmap and AGENTS.md status. Stop.
```
