# Makefile — sample_pipeline_with_ci
# Simulates CI locally so you catch issues before pushing.
#
# Usage:
#   make help         show all targets
#   make install      install dependencies
#   make test         run all tests with verbose output
#   make lint         check code style (ruff + black)
#   make format       auto-format code (black + ruff --fix)
#   make ci-local     run lint then test (mirrors CI pipeline)
#   make clean        remove generated files and caches

.PHONY: help install test lint format ci-local clean

# Default target when you just type "make"
.DEFAULT_GOAL := help

help:  ## Show this help message
	@echo ""
	@echo "  sample_pipeline_with_ci — available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

install:  ## Install all dependencies from requirements-dev.txt
	pip install -r requirements-dev.txt

test:  ## Run all tests with verbose output
	pytest test_pipeline.py -v --tb=short

test-cov:  ## Run tests with coverage report (requires pytest-cov)
	pytest test_pipeline.py \
		--cov=pipeline \
		--cov-report=term-missing \
		--cov-fail-under=70 \
		-v --tb=short

lint:  ## Check code with ruff and black (no auto-fix)
	ruff check .
	black --check .

format:  ## Auto-format code with black and ruff --fix
	black .
	ruff check --fix .

ci-local:  ## Run lint then test — mirrors what GitHub Actions does
	@echo ""
	@echo "=== Running CI locally ==="
	@echo ""
	@echo "--- Step 1: lint ---"
	$(MAKE) lint
	@echo ""
	@echo "--- Step 2: tests ---"
	$(MAKE) test
	@echo ""
	@echo "=== CI local complete ==="

run:  ## Run the ETL pipeline with default settings
	python pipeline.py

clean:  ## Remove __pycache__, .pytest_cache, coverage files, output/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf output/ data/
	@echo "Cleaned."
