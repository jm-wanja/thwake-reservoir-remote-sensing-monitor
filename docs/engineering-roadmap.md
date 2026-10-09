# Engineering & Credibility Backlog

What a very senior AI / ML / remote-sensing engineer would look for in this repo that does not exist yet. Recorded 2026-10-09 after a gap review. Each item has a target phase and a "done when". Tick items here; when an item becomes real work, give it a prompt and/or ADR and link it.

**Already in place (for context):** documented architecture + ADRs, pinned deps + `uv.lock`, CI (ruff lint + format, pytest, >10 MB guard, least-privilege permissions), secrets git-ignored, agent guardrails (`.claude/settings.json` + `block-repo-writes.sh`), sourced facts, stated limitations.

**Status key:** ☐ todo · ◐ in progress · ☑ done (on commit of the restructure, 2026-10-09)

---

## A. High impact — reviewers would notice these are missing

| # | Item | Why it matters | Target | Done when | Status |
|---|------|----------------|--------|-----------|--------|
| A1 | **Validation against known truth** — run the method on a reference reservoir with published figures (e.g. Masinga Dam, Kenya) and/or reproduce a GERD Sentinel-1 result | Proves the method is *accurate*, not just that code runs. The #1 question: "how do you know?" | **Phase 1.5 (Validation)** | Reference-reservoir report in docs: our area/volume vs published, with % difference | ☐ |
| A2 | **Hand-labelled test set** — ~20–30 scenes, digitised true shorelines; report IoU, precision, recall for S1 vs S2 | Quantifies water-mask accuracy | Phase 1.5 | `data/validation/` labels + accuracy table in docs and README | ☐ |
| A3 | **Evaluation harness** — `thwake evaluate` CLI; CI fails if accuracy drops below threshold | Never change the method without re-measuring (ML-engineering discipline) | Phase 1.5 | Command exists, runs in CI on small labelled set, thresholds in config | ☐ |
| A4 | **Tests for the agent guardrail** — turn the 30-case check of `block-repo-writes.sh` into pytest tests run in CI | "My safety controls are tested" | Restructure (now) | `tests/test_guardrail_hook.py` passes in CI | ☑ |
| A5 | **Data provenance on every output** — run-metadata (scene IDs, EE collection versions, git commit, config hash, run date) alongside CSV | Any number traceable to how it was made | Phase 2 (prompts 07–08) | `data/processed/run_metadata.json` (or per-row fields); schema documented in ARCHITECTURE §6 | ☐ |
| A6 | **Licence** — choose code + data/text licences (open question 12) | Without it, nobody may legally reuse the work | Restructure (human decision) | `LICENSE` (code) + data/text licence stated in README | ◐ |
| A7 | **`CITATION.cff`** (+ later Zenodo DOI on a release) | Research credibility; makes the work citable | Restructure (CFF); DOI after first results release | `CITATION.cff` valid; DOI badge in README | ☑ |

## B. Medium impact — signs of engineering maturity

| # | Item | Target | Done when | Status |
|---|------|--------|-----------|--------|
| B1 | Type checking (`mypy` or `pyright`) in CI | Restructure | Type check step passes in CI | ☑ |
| B2 | Test coverage report (`pytest-cov`), shown in CI output | Restructure | Coverage printed in CI; target set later | ☑ |
| B3 | `pre-commit` hooks: ruff, large-file check, secret scan (`gitleaks`), end-of-file fixes | Restructure | `.pre-commit-config.yaml`; human runs `pre-commit install` | ◐ |
| B4 | Notebook hygiene (`nbstripout`) so outputs/data don't bloat or leak into git | Restructure | nbstripout configured (pre-commit or git attribute) | ☑ |
| B5 | Pin GitHub Actions by commit SHA + Dependabot (pip/uv + actions) | Restructure | Actions pinned; `.github/dependabot.yml` | ☑ |
| B6 | Task runner (`Makefile` or `justfile`): `make test`, `make lint`, `make baseline`, … | Restructure | One obvious command per task, documented in README | ☑ |
| B7 | `CHANGELOG.md` + tagged releases (`v0.1.0`, `baseline-v1`, …) | Restructure (start); every phase | CHANGELOG exists; tags pushed by human | ◐ |
| B8 | PR-per-prompt workflow — each agent task on a branch → PR with description → human review → merge | From prompt 04 onward | Commands/human-steps.md describe branch + PR flow; PR template exists | ◐ |
| B9 | AI co-authorship trailers on commits made from agent work | From prompt 04 onward | Convention documented in AGENTS.md / human-steps.md | ◐ |

## C. Showing AI / ML skills (optional, high portfolio value)

| # | Item | Target | Done when | Status |
|---|------|--------|-----------|--------|
| C1 | **Otsu vs ML comparison** — e.g. random forest on S1/S2 bands, and/or Dynamic World water class, evaluated on the A2 labelled set | After Phase 1.5 (needs labels) | Write-up: accuracy table, cost/complexity trade-off, which method is used and why (ADR) | ☐ |
| C2 | (Stretch) Small segmentation model or pretrained geospatial foundation model fine-tune, same evaluation | Later | Same evaluation table extended | ☐ |

## D. Later — once results exist

| # | Item | Target | Done when | Status |
|---|------|--------|-----------|--------|
| D1 | **Results-first README** — time-lapse GIF + filling chart at the top | Phase 2 | README opens with current % full (range + date) and visuals | ☐ |
| D2 | **Dataset card** for the published CSV — what, how, limitations, licence | Phase 2 | `docs/dataset-card.md` linked from README and story page | ☐ |
| D3 | **Run monitoring** — failed monthly Action notifies the owner; basic run log | Phase 2 (prompt 11) | Failure notification configured; run summary in Actions logs | ☐ |
| D4 | Compare against external products (Global Water Watch, DAHITI/G-REALM) if Thwake appears | Phase 2+ | Comparison note in methodology | ☐ |

---

## Notes on partial items (◐)
- **A6** licence drafted (MIT + CC BY 4.0); final when the author commits.
- **B3** `.pre-commit-config.yaml` added and verified (all hooks pass); author runs `pre-commit install` once.
- **B7** `CHANGELOG.md` started; first tag (`v0.1.0` or `baseline-v1`) is a human step.
- **B8/B9** PR template + branch/PR flow and co-author trailer documented in `human-steps.md` H3; in use from prompt 04.
- **A1–A3, C1** now have slash commands `/05a`–`/05d` (Phase 1.5, ADR 0009). **A5, D1–D3** are written into commands `/08`, `/10`, `/11`.

## Plan of record

1. ☑ **Restructure (2026-10-09, ADR 0010):** root `AGENTS.md` + `CLAUDE.md`, human docs → `docs/` (decisions → `docs/decisions/`), prompts → `.claude/commands/`, plus quick wins **A4, A6 (human choice), A7, B1–B7**.
2. ☑ **Add Phase 1.5 — Validation** (A1–A3) to the roadmap with an ADR and new prompts, between Phase 1 (baseline) and Phase 2 (filling tracker).
3. **From prompt 04:** B8 + B9 workflow.
4. **Phase 2:** A5, D1–D3. **After 1.5:** C1.
