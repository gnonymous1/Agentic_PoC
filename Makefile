.PHONY: help install lint typecheck test test-unit test-integration run dev docker-up docker-down migrate seed clean

SHELL := /bin/bash
PYTHON := python

help:
	@echo "GNONE Platform Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  install       Install Python dependencies"
	@echo "  lint          Run ruff linter"
	@echo "  typecheck     Run mypy type checker"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests"
	@echo "  test-int      Run integration tests"
	@echo "  run           Run production server"
	@echo "  dev           Run development server with reload"
	@echo "  docker-up     Start all Docker services"
	@echo "  docker-down   Stop all Docker services"
	@echo "  migrate       Run database migrations"
	@echo "  seed          Seed test data"
	@echo "  clean         Remove cache files"

install:
	pip install -r requirements.txt

lint:
	ruff check app/ tests/

typecheck:
	mypy app/ --ignore-missing-imports

test: test-unit test-int

test-unit:
	pytest tests/unit -v --cov=app --cov-report=term-missing

test-int:
	pytest tests/integration -v

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

migrate:
	$(PYTHON) -m app.cli.deploy migrate

seed:
	$(PYTHON) -m app.cli.manage seed --count 10

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
