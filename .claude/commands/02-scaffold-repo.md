---
description: "Scaffold the repository"
---

<!-- Prompt 02 — Scaffold the repository. Run in a fresh session: /02-scaffold-repo -->

Prerequisites (human must have done these): H1 (Python 3.11 + uv/venv).
If a prerequisite is not met, stop and tell the human.

Task: Create the repository skeleton exactly as in docs/architecture.md §5. No analysis logic yet.

Read first: docs/architecture.md (§3B modules, §5 layout, §6 data contracts, §8 security),
AGENTS.md §4–6, ADR 0002.

Create:
- pyproject.toml: package "thwake" in src/, Python 3.11, deps (earthengine-api, geemap,
  pandas, geopandas, pyyaml, click or typer, python-dotenv), dev deps (pytest, ruff).
  Pin versions. Ruff + pytest config included.
- src/thwake/ with empty-but-documented module stubs for each module in ARCHITECTURE §3B
  (docstring stating responsibility; no implementation) and a CLI entry point exposing
  `baseline`, `update`, `media`, `qa` commands that print "not implemented".
- src/thwake/config.py that loads config/*.yaml and .env (implemented, tested).
- config/settings.yaml (dam name, AOI path, dates, capacity — values from
  data/external/official_figures.csv or "null" with a ⚠️ comment),
  config/ee_collections.yaml (IDs from docs/data-sources.md),
  config/thresholds.yaml (starting values from docs/methodology.md).
- data/{baseline,processed,external}/, media/, notebooks/, site/, app/ee-app/, tests/
  with .gitkeep where empty.
- .gitignore covering: .env, *.json keys, credentials/, *.tif, *.tiff, .venv/, venv/,
  __pycache__/, .ipynb_checkpoints/, site/_site/, .quarto/.
- .env.example with EE_PROJECT= (no real values).
- tests/test_config.py.
- .github/workflows/ci.yml: ruff + pytest on push/PR, plus a step failing on files > 10 MB.
- LICENSE: leave a TODO noting open question 12 (licence choice) — do not choose.

Acceptance criteria:
- `uv sync` (or pip install -e .[dev]) works; `ruff check .` and `pytest` pass.
- `python -m thwake --help` lists the four commands.
- No secrets, no real credentials, no large files.
- Update docs/roadmap.md.
