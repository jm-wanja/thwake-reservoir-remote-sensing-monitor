# Human-only steps

Things an AI agent **cannot or must not** do on this project. The agent prepares, you act. Each step lists **when** it's needed (which prompt in [prompts/](prompts/README.md)) and **how**.

> Rule: agents never commit, push, tag, create accounts, handle credentials, publish, or approve their own work. They stop and tell you what to run.

---

## H1 — Local tools (before prompt 02)

- [x] Install Python 3.11 (pyenv) and `uv`.
- [x] Install Git and confirm `git config user.name` / `user.email` are set.
- [x] Install the GitHub CLI (`gh`) and log in: `gh auth login` (optional but handy).
- [x] Install Quarto (needed by prompt 10).
- [x] Pinned Python 3.11 (`uv python pin 3.11`) and created `.venv` (`uv venv`) — done 2026-10-09.

## H2 — Google Earth Engine account (before prompt 03)

- [x] Sign up for Earth Engine with your Google account: https://earthengine.google.com
- [x] Create (or choose) a Google Cloud project and **register it for non-commercial use**. — Done 2026-10-09: project **`thwake-monitor`**, non-commercial (individual research), **Community** tier (no billing account). Eligibility expires **9 Apr 2028**.
- [x] Enable the Earth Engine API on that project.
- [x] Authenticate locally: `earthengine authenticate` (opens a browser — you sign in, not the agent).
- [x] Create `.env` in the repo root (git-ignored) with `EE_PROJECT=<your-project-id>`. — `EE_PROJECT=thwake-monitor`; connection test passed 2026-10-09.
- [x] Create an assets folder in the EE Code Editor for baseline layers; put its path in `config/settings.yaml` (or tell the agent the path). — `projects/thwake-monitor/assets/thwake`.

## H3 — Git repository: create, commit, push

### Create (once, after prompt 02)
- [ ] `git init` in `thwake-reservoir-remote-sensing-monitor/`.
- [ ] Check nothing secret or large is staged: `git status`, look for `.env`, `*.json` keys, `*.tif`.
- [ ] First commit.
- [ ] Create a **public** repo `thwake-reservoir-remote-sensing-monitor` on GitHub (web UI or `gh repo create`).
- [ ] Add remote and push `main`.
- [ ] Settings → Pages → Source: **GitHub Actions**.

### After every agent task
- [ ] Review the diff (`git diff`) against the prompt's acceptance criteria.
- [ ] Run tests yourself: `ruff check .` and `pytest`.
- [ ] Check no secrets / large files are included.
- [ ] Commit with a clear message (small, imperative: "Add S1 water mask").
- [ ] Push (or open a PR if you use branches).

### Tags / releases
- [ ] After approving the baseline (prompt 05): `git tag baseline-v1` and `git push origin baseline-v1`.
- [ ] Optional: a GitHub Release at each phase completion.

> Exception: the scheduled `update.yml` workflow commits refreshed data/media as a bot. That's automation you set up and approved in prompt 11 — not an agent acting on its own.

## H4 — Service account & GitHub secrets (before prompt 11)

- [ ] In Google Cloud console: create a service account in your EE project.
- [ ] Grant minimal roles (Earth Engine resource viewer/writer for this project; Service Usage Consumer).
- [ ] Register the service account for Earth Engine access.
- [ ] Create a JSON key — download it **once**, store it **outside** the repo.
- [ ] GitHub repo → Settings → Secrets and variables → Actions:
  - Secret `EE_SERVICE_ACCOUNT_KEY` = full JSON contents
  - Variable `EE_PROJECT` = project ID
- [ ] Delete the local key file (or keep it in a password manager). **Never paste it into an agent chat.**
- [ ] Share baseline EE assets with the service account if needed.

## H5 — Publish the Earth Engine App (after prompt 09)

- [ ] Open the EE Code Editor, create a new script, paste `app/ee-app/main.js`.
- [ ] Run it; check it works.
- [ ] Make the baseline assets readable by the app (Asset → Share → "Anyone can read" or app access).
- [ ] Apps → New App → name `thwake` → choose the script → Publish.
- [ ] Open the public URL in a private/incognito window to confirm it works without login.
- [ ] Paste the URL into `README.md` (or give it to the agent to add), then commit & push.

## H6 — Facts, documents and approvals (ongoing)

- [ ] Verify every value the agent marks ⚠️ (dam coordinates, full supply level, capacity, construction start, impoundment date) — ideally from official documents.
- [ ] Supply documents the agent can't reach (ESIA PDFs, irrigation command-area boundaries, any in-situ water-quality data).
- [ ] **Approve the baseline freeze** (prompt 05) — the agent must wait for you.
- [ ] Change ADR status from "Proposed" to "Accepted" (prompt 91).
- [ ] Choose the licence (open question 12) — code (e.g. MIT) and data/text (e.g. CC BY 4.0).

## H7 — Going public (after prompt 11, and at each seasonal update)

- [ ] Confirm the GitHub Pages URL loads: `https://<your-username>.github.io/thwake-reservoir-remote-sensing-monitor/`
- [ ] Read all public-facing wording yourself (story page, README, seasonal updates) — numbers have ranges and dates; no "safe"/"contaminated" claims.
- [ ] Decide whether and where to share (LinkedIn, CV, blog, journalists).
- [ ] Twice a year (≈June, ≈January): run prompt 90, approve the seasonal write-up, commit & push.

## H8 — Ongoing account hygiene

- [ ] **Re-verify Earth Engine non-commercial eligibility before 9 Apr 2028** (Cloud console → Earth Engine → Configuration → Manage registration). Google may also ask earlier.
- [ ] Watch EECU usage on the Community tier (Configuration → Manage your EECU time usage); upgrade to Contributor only if limits are hit.
- [ ] Rotate the service-account key yearly (new key → update GitHub secret → delete old key).
- [ ] Check Earth Engine non-commercial terms/quotas haven't changed.
- [ ] Watch GitHub Actions for failed runs (email notifications) and re-run or fix.

---

## Quick map: which human step unblocks which prompt

| Prompt | Needs |
|--------|-------|
| 01 Resolve open questions | (agent with web access) → you verify results (H6) |
| 02 Scaffold | H1 → then H3 create/commit/push |
| 03 AOI | H2 |
| 05 Baseline freeze | H6 approval → H3 tag |
| 09 EE App | → H5 publish |
| 11 Actions & deploy | H3 (repo + Pages), H4 (secrets) → H7 |
| 90 Seasonal review | H7 approve wording → H3 commit & push |
| Every prompt | H3 review, test, commit, push |
