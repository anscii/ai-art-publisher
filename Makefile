SHELL := $(shell which bash)
UV    := UV_EXTRA_INDEX_URL="" uv
PY    := UV_EXTRA_INDEX_URL="" .venv/bin/python

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	$(PY) -m uvicorn app.main:app --reload

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PY) -m pytest -v -s --cov=app --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml .

test-fast:
	$(PY) -m pytest -v .

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
	$(PY) -m pre_commit install

hooks:
	$(PY) -m pre_commit install

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -name __pycache__ -exec rm -rf {} +
	find . -name "*.py[co]" -exec rm -rf {} +
	find . -name .pytest_cache -exec rm -rf {} +
	find . -name .mypy_cache  -exec rm -rf {} +
	find . -name .ruff_cache  -exec rm -rf {} +

.PHONY: dev test test-fast format lint lint-fix types check migrate migrate-new venv install install-dev hooks clean
