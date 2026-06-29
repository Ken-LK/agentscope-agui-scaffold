.PHONY: backend-install backend-lint backend-run frontend-install frontend-build frontend-dev clean-runtime

PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.12

backend-install:
	cd backend && $(PYTHON_BOOTSTRAP) -m venv .venv
	cd backend && .venv/bin/pip install -e ".[dev]"

backend-lint:
	cd backend && $(PYTHON) -m ruff check app scripts

backend-run:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-install:
	cd frontend && pnpm install

frontend-build:
	cd frontend && pnpm build

frontend-dev:
	cd frontend && pnpm dev --host 0.0.0.0

clean-runtime:
	rm -rf backend/.agentscope-service backend/.workspaces frontend/dist frontend/tsconfig.tsbuildinfo
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
	find backend -type d -name '.ruff_cache' -prune -exec rm -rf {} +
