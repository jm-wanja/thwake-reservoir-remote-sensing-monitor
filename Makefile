# One obvious command per task. `make help` lists them.
.PHONY: help install lint format typecheck test check baseline hooks

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install/refresh the environment from uv.lock
	uv sync

lint:  ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-format code
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Static type check (mypy)
	uv run mypy

test:  ## Run tests with coverage (incl. agent-guardrail tests)
	uv run pytest

check: lint typecheck test  ## Everything CI runs

baseline:  ## Build Phase 1 baseline outputs (needs Earth Engine auth + .env)
	uv run python -m thwake baseline --step extent

hooks:  ## Run all pre-commit hooks on every file
	pre-commit run --all-files
