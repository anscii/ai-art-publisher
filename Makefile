SHELL := $(shell which bash)
UV    := uv
PY    := .venv/bin/python

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PY) -m pytest -v -s --cov=app --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml .

test-fast:
	$(PY) -m pytest -v .

test-front:
	$(PY) -m pytest -m e2e -v

test-back:
	$(PY) -m pytest  -m "not e2e" -v

playwright-install:
	$(PY) -m playwright install chromium

# ── Lint & format ─────────────────────────────────────────────────────────────
format:
	$(PY) -m ruff format app

lint:
	$(PY) -m ruff check app
	$(PY) -m ruff format --diff app

lint-fix:
	$(PY) -m ruff format app
	$(PY) -m ruff check app --fix

# ── Type check ────────────────────────────────────────────────────────────────
types:
	$(PY) -m mypy app

# ── Run everything ────────────────────────────────────────────────────────────
check: lint-fix lint types test

# ── Database migrations ───────────────────────────────────────────────────────
migrate:
	$(PY) scripts/migrate.py

migrate-new:
	$(PY) -m alembic revision --autogenerate -m "$(msg)"

# ── Environment ───────────────────────────────────────────────────────────────
venv:
	uv venv .venv --python=python3.12

install:
	$(UV) pip install -r requirements.txt

install-dev:
	$(UV) pip install -r requirements.txt -r requirements-dev.txt

hooks:
	$(PY) -m pre_commit install

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

.PHONY: run test test-fast test-front test-back playwright-install format lint lint-fix types check migrate migrate-new venv install install-dev hooks clean pull-prod-db
