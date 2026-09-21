# ──────────────────────────────────────────────────────────────
# Makefile — Containerized Pipeline Stack
# ──────────────────────────────────────────────────────────────
# Shortcuts for the most common docker-compose commands.
# Run 'make help' to see all available targets.
#
# Prerequisites:
#   - Docker Desktop running
#   - .env file exists (cp .env.example .env, then edit)
#
# Quick start:
#   make up       → builds images + starts all services
#   make logs     → watch all services (Ctrl+C to stop)
#   make psql     → connect to Postgres
#   make down     → stop everything (data preserved)
# ──────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

# ──────────────────────────────────────────────────────────────
# CORE COMMANDS
# ──────────────────────────────────────────────────────────────

.PHONY: up
up: check-env  ## Build images and start all services in the background
	docker-compose up -d --build
	@echo ""
	@echo "  Stack started. Try:"
	@echo "    make logs     — watch all output"
	@echo "    make psql     — connect to Postgres"
	@echo "    make ps       — check service status"

.PHONY: down
down:  ## Stop all services (data volumes preserved)
	docker-compose down
	@echo "  Services stopped. Data volumes preserved."
	@echo "  Run 'make up' to restart."

.PHONY: clean
clean:  ## Stop all services AND delete data volumes (fresh start)
	docker-compose down -v
	@echo "  Services stopped and data volumes deleted."
	@echo "  Next 'make up' will start with an empty database."

# ──────────────────────────────────────────────────────────────
# LOGS
# ──────────────────────────────────────────────────────────────

.PHONY: logs
logs:  ## Follow logs from ALL services (Ctrl+C to stop)
	docker-compose logs -f

.PHONY: logs-pipeline
logs-pipeline:  ## Follow logs from the pipeline service only
	docker-compose logs -f pipeline

.PHONY: logs-postgres
logs-postgres:  ## Follow logs from Postgres only
	docker-compose logs -f postgres

# ──────────────────────────────────────────────────────────────
# DATABASE ACCESS
# ──────────────────────────────────────────────────────────────

.PHONY: psql
psql:  ## Open a psql shell inside the running Postgres container
	docker-compose exec postgres psql -U pipeline_user -d pipeline_db

# ──────────────────────────────────────────────────────────────
# RUN PIPELINE
# ──────────────────────────────────────────────────────────────

.PHONY: run
run:  ## Run the pipeline once in a fresh container (Postgres must be running)
	docker-compose run --rm pipeline python pipeline.py

# ──────────────────────────────────────────────────────────────
# DEVELOPMENT HELPERS
# ──────────────────────────────────────────────────────────────

.PHONY: ps
ps:  ## Show status of all services
	docker-compose ps

.PHONY: build
build:  ## Rebuild the pipeline image without starting
	docker-compose build pipeline

.PHONY: rebuild
rebuild:  ## Force rebuild without cache, then start
	docker-compose build --no-cache pipeline
	docker-compose up -d

.PHONY: shell
shell:  ## Open a bash shell in a new pipeline container (Postgres must be running)
	docker-compose run --rm pipeline bash

# ──────────────────────────────────────────────────────────────
# SETUP VERIFICATION
# ──────────────────────────────────────────────────────────────

.PHONY: check-env
check-env:  ## Verify .env file exists before starting
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "  ERROR: .env file not found."; \
		echo "  Run: cp .env.example .env"; \
		echo "  Then edit .env with your desired values."; \
		echo ""; \
		exit 1; \
	fi

.PHONY: check-docker
check-docker:  ## Verify Docker is running
	@docker info > /dev/null 2>&1 || (echo "  ERROR: Docker is not running. Start Docker Desktop." && exit 1)
	@echo "  Docker is running."

# ──────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help message
	@echo ""
	@echo "  Containerized Pipeline Stack — Available Commands"
	@echo "  ================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Quick start:"
	@echo "    cp .env.example .env   # copy config template"
	@echo "    make up                # build + start everything"
	@echo "    make logs              # watch output"
	@echo "    make psql              # inspect the database"
	@echo "    make down              # stop (keeps data)"
	@echo "    make clean             # stop + delete all data"
	@echo ""
