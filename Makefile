.PHONY: help install sandbox-image lint typecheck test test-unit test-docker content-check check up down

help:  ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install:  ## Install Python and frontend dependencies
	uv sync
	cd frontend && npm ci

sandbox-image:  ## Build the grading sandbox image
	docker build -t lattice-sandbox-python:dev -f grader/images/python/Dockerfile grader

lint:  ## Lint and format-check Python, check import layering
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports

typecheck:  ## Strict type-check Python
	uv run mypy backend/src grader/src

test-unit:  ## Fast tests (no Docker)
	uv run pytest -m "not docker"

test-docker: sandbox-image  ## Sandbox integration tests
	uv run pytest -m docker

content-check: sandbox-image  ## Validate content and grade the foundations' solutions and wrong cases
	uv run forgeway content validate --require-capstones
	uv run forgeway content test --only starter.

check: lint typecheck test-unit test-docker content-check  ## Everything CI runs for the backend

up:  ## Run the full stack
	docker compose up --build

down:  ## Stop the stack
	docker compose down
