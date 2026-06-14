SHELL := $(shell which bash)
UV    := uv

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
    --reload-dir app \
    --reload-include "*.js" \
    --reload-include "*.html" \
    --reload-include "*.css"


# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(UV) run pytest -v -s --cov=app --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml .

test-fast:
	$(UV) run pytest -v .

test-front:
	$(UV) run pytest -m e2e -v

test-back:
	$(UV) run pytest -m "not e2e" -v --cov=app --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml

playwright-install:
	$(UV) run playwright install chromium

# ── Lint & format ─────────────────────────────────────────────────────────────
format:
	$(UV) run ruff format app

lint:
	$(UV) run ruff check app
	$(UV) run ruff format --diff app

lint-fix:
	$(UV) run ruff format app
	$(UV) run ruff check app --fix

# ── Type check ────────────────────────────────────────────────────────────────
types:
	$(UV) run mypy app

# ── Run everything ────────────────────────────────────────────────────────────
check: lint-fix lint types test

# ── Database migrations ───────────────────────────────────────────────────────
test-prompt:
	$(UV) run python scripts/test_generation.py --hint "$(hint)" $(if $(provider),--provider $(provider),) $(if $(model),--model $(model),) $(if $(variants),--variants $(variants),)

migrate:
	$(UV) run python scripts/migrate.py

migrate-new:
	$(UV) run alembic revision --autogenerate -m "$(msg)"

# ── Environment ───────────────────────────────────────────────────────────────
install:
	$(UV) sync --no-dev

install-dev:
	$(UV) sync

lock:
	$(UV) lock

hooks:
	$(UV) run pre-commit install

# ── Database snapshots ───────────────────────────────────────────────────────
pull-prod-db:
	$(eval SNAP := ./data/prod_snapshot_$(shell date +%Y%m%d_%H%M).db)
	fly sftp get /app/data/db.sqlite $(SNAP)
	@echo "Saved to $(SNAP)"

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -name __pycache__ -exec rm -rf {} +
	find . -name "*.py[co]" -exec rm -rf {} +
	find . -name .pytest_cache -exec rm -rf {} +
	find . -name .mypy_cache  -exec rm -rf {} +
	find . -name .ruff_cache  -exec rm -rf {} +

.PHONY: run test test-fast test-front test-back playwright-install format lint lint-fix types check test-prompt migrate migrate-new install install-dev lock hooks clean pull-prod-db
