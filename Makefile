# Amharic Document AI
.DEFAULT_GOAL := help
SHELL := /bin/bash
PY := .venv/bin/python
UV := uv

.PHONY: help venv install lock dev down migrate test test-unit test-integration \
        lint fmt typecheck security sbom train eval clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv
	$(UV) venv --python 3.11 .venv

install: venv ## Install dev dependencies and the package (editable)
	$(UV) pip install --python $(PY) -r requirements/dev.lock.txt
	$(UV) pip install --python $(PY) --no-deps -e .

lock: ## Regenerate all dependency locks from pyproject.toml
	$(UV) pip compile --python-version 3.11 --no-header pyproject.toml -o requirements/api.lock.txt
	$(UV) pip compile --python-version 3.11 --no-header --extra dev pyproject.toml -o requirements/dev.lock.txt
	$(UV) pip compile --python-version 3.11 --no-header --extra ml  pyproject.toml -o requirements/ml.lock.txt

dev: ## Bring the whole stack up (api, worker, postgres, redis, frontend)
	docker compose up --build

down: ## Stop the stack and remove volumes
	docker compose down -v

migrate: ## Apply database migrations
	PYTHONPATH=src $(PY) -m alembic upgrade head

test: ## Run the full test suite
	$(PY) -m pytest tests -q

test-unit: ## Unit and security tests only (no database needed)
	$(PY) -m pytest tests/unit tests/security -q

test-integration: ## Integration tests (needs Postgres)
	$(PY) -m pytest tests/integration -q

lint: ## ruff check + format check
	$(PY) -m ruff check src tests scripts
	$(PY) -m ruff format --check src tests scripts

fmt: ## Apply ruff formatting and autofixes
	$(PY) -m ruff check --fix src tests scripts
	$(PY) -m ruff format src tests scripts

typecheck: ## mypy strict
	$(PY) -m mypy

security: ## Dependency audit, secret scan, API isolation, doc invariants
	@echo "--- C-45: API image contains no ML stack ---"
	$(PY) scripts/check_api_isolation.py requirements/api.lock.txt
	@echo "--- C-39: dependency audit (build-failing) ---"
	$(PY) -m pip_audit -r requirements/api.lock.txt --progress-spinner off
	@echo "--- C-36: secret scan across the working tree ---"
	$(PY) -m detect_secrets scan --baseline .secrets.baseline
	@echo "--- threat-model coverage invariant ---"
	$(PY) docs/research/verify_threat_coverage.py
	@echo "--- Ethiopic inventory figures ---"
	$(PY) docs/research/verify_ethiopic_inventory.py

sbom: ## Generate a CycloneDX SBOM (control C-39)
	$(PY) -m cyclonedx_py requirements requirements/api.lock.txt -o sbom.json

train: ## Train a recogniser -- BLOCKED, see docs/STATUS.md
	@echo "train: not available."
	@echo "The Fidel corpus is not accessible (huggingface.co is egress-blocked) and no"
	@echo "loader may be written against an unverified schema. See ADR-0008 and"
	@echo "src/adai/data/fidel.py. Resolve dataset access first."
	@exit 1

eval: ## Run the evaluation harness -- needs a dataset, see docs/STATUS.md
	@echo "eval: no dataset available. See ADR-0008 and docs/STATUS.md."
	@exit 1

clean: ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build sbom.json
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
