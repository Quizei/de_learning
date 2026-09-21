"""
Makefiles and Project Automation
=================================
A Makefile turns a project's "how to run" documentation into
executable shortcuts. Instead of hunting through a README for
the right command, a new team member runs: make help.

This file covers:
- What a Makefile is and why it belongs in every data project
- Makefile syntax: targets, dependencies, commands, .PHONY
- Variables and reusable Makefiles
- The help target: self-documenting automation
- A complete data engineering Makefile with explanations
- Common patterns: dbt, testing, Docker, deployment
- Chaining and conditional targets

Run this file: python3 concepts/03_makefile_and_project_automation.py
The Makefile is printed with explanations.
A small demo Makefile is created in a temp directory and actually run.
"""

import subprocess
import tempfile
import os
import shutil


# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def show(cmd, cwd=None, note=""):
    """Run a command and print its output."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    output = (result.stdout + result.stderr).strip()
    if output:
        for line in output.splitlines()[:30]:
            print(f"    {line}")
    else:
        print("    (no output)")


def demo(cmd, note=""):
    """Print a command without executing it."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")


# ============================================================
# 1. WHAT IS A MAKEFILE?
# ============================================================

section("1. WHAT IS A MAKEFILE AND WHY DO DATA ENGINEERS NEED IT?")

print("""
  A Makefile is a file named 'Makefile' (capital M) in your project root.
  It defines named commands — called targets — that anyone can run with:

    make <target>

  It was originally designed for compiling C code (hence the name 'make').
  Data engineers repurpose it as a project command runner.

  WHY IT MATTERS:
  ─────────────────────────────────────────────────────────────────────
  Without a Makefile, your README has a "How to run" section:

    To run the pipeline:
      1. Create venv: python -m venv .venv
      2. Activate: source .venv/bin/activate
      3. Install deps: pip install -r requirements-dev.txt
      4. Set env: export $(cat .env | xargs)
      5. Run: python src/pipeline.py

  With a Makefile:
    make install   # steps 1-3
    make run       # steps 4-5

  Benefits:
    - Self-documenting: 'make help' lists all commands with descriptions
    - Consistent: everyone runs the exact same command sequence
    - Discoverable: new engineers know what's available immediately
    - Works everywhere: make is installed on every Unix/Linux/macOS machine
    - No extra tooling: no NPM scripts to learn, no Invoke to install
    - Great with CI/CD: your pipeline runs the same make targets
""")


# ============================================================
# 2. MAKEFILE SYNTAX
# ============================================================

section("2. MAKEFILE SYNTAX — The Three Rules")

print("""
  RULE 1: Target, optional dependencies, and recipe

    target: dependency1 dependency2
    \\tcommand1
    \\tcommand2

  RULE 2: THE TAB CHARACTER IS MANDATORY.
    The recipe (commands) MUST be indented with a TAB — not 4 spaces.
    This is the #1 Makefile gotcha. Your editor may convert tabs to spaces.
    Check your editor settings if you get: "Makefile:5: *** missing separator."

    In VS Code: Preferences → Settings → search "insertSpaces" → disable for Makefile files.

  RULE 3: Each line in a recipe runs in a SEPARATE shell.
    This means cd in one line doesn't affect the next line.

    BAD:                        GOOD:
    target:                     target:
    \\tcd some/dir              \\tcd some/dir && python script.py
    \\tpython script.py         # or use \\
                                \\tcd some/dir \\\\
                                \\t&& python script.py

  .PHONY:
    Make was designed for building files. If a file named 'test'
    exists in your directory, 'make test' would do nothing (the file
    is already "up to date"). .PHONY tells make to always run these
    targets regardless of whether files by those names exist.

    .PHONY: install test lint run clean help
    Always add all your command-style targets to .PHONY.
""")


# ============================================================
# 3. COMPLETE DATA ENGINEERING MAKEFILE
# ============================================================

section("3. COMPLETE DATA ENGINEERING MAKEFILE")

print("""
  Here is a production-ready Makefile for a data engineering project.
  Every line is explained. Copy this and adapt it.
""")

print("""
  ─── Makefile ─────────────────────────────────────────────────────────
""")

makefile_content = r"""
# ======================================================================
# PROJECT MAKEFILE — Data Engineering Pipeline
# ======================================================================
# Run 'make help' to see all available targets.
# ======================================================================

# .PHONY tells make: "these targets are commands, not filenames"
# Without .PHONY, a file named 'clean' would prevent 'make clean' from running.
.PHONY: install install-dev test lint format run docker-up docker-down clean help

# ── VARIABLES ──────────────────────────────────────────────────────────
# Define once at the top, reference everywhere as $(VARNAME)
PYTHON    := python3
VENV      := .venv
PIP       := $(VENV)/bin/pip
PYTEST    := $(VENV)/bin/pytest
BLACK     := $(VENV)/bin/black
RUFF      := $(VENV)/bin/ruff

# Overridable from command line: make run ENV=prod
ENV       ?= dev

# Set the default target — 'make' with no args shows help
.DEFAULT_GOAL := help

# ── SETUP ──────────────────────────────────────────────────────────────

install: ## Install runtime dependencies only
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: ## Install all dependencies including dev tools
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

# ── CODE QUALITY ───────────────────────────────────────────────────────

test: ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=src --cov-report=term-missing

test-fast: ## Run tests without coverage (faster)
	$(PYTEST) tests/ -v -x

lint: ## Check code style without modifying (ruff + black check)
	$(RUFF) check .
	$(BLACK) --check .

format: ## Auto-format code in-place (black + ruff fix)
	$(BLACK) .
	$(RUFF) check --fix .

# ── PIPELINE ───────────────────────────────────────────────────────────

run: ## Run the pipeline locally (ENV=dev by default)
	@echo "Running pipeline in $(ENV) mode..."
	$(VENV)/bin/python src/pipeline.py --env $(ENV)

run-prod: ## Run the pipeline in production mode
	$(MAKE) run ENV=prod

# ── DOCKER ─────────────────────────────────────────────────────────────

docker-up: ## Start the full docker-compose stack (Postgres + Redis + app)
	docker-compose up -d --build

docker-down: ## Stop and remove all containers in the stack
	docker-compose down

docker-logs: ## Follow live logs from the pipeline container
	docker-compose logs -f pipeline

# ── DBT (if using dbt) ─────────────────────────────────────────────────

dbt-run: ## Run all dbt models
	cd dbt && $(VENV)/bin/dbt run

dbt-test: ## Run all dbt tests
	cd dbt && $(VENV)/bin/dbt test

dbt-docs: ## Generate and serve dbt documentation
	cd dbt && $(VENV)/bin/dbt docs generate && $(VENV)/bin/dbt docs serve

# ── CLEANUP ────────────────────────────────────────────────────────────

clean: ## Remove Python bytecode, test cache, and build artifacts
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov/ dist/ *.egg-info/

clean-all: clean ## Remove .venv as well (full reset)
	rm -rf $(VENV)

# ── HELP ───────────────────────────────────────────────────────────────

help: ## Show this help message (auto-generated from ## comments)
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
"""

print(makefile_content)

print("""
  ─── END OF MAKEFILE ──────────────────────────────────────────────────

  KEY EXPLANATIONS:

  $(VENV)/bin/pytest vs pytest:
    We call executables through the venv path explicitly.
    This means 'make test' works even without activating the venv.
    CI/CD servers often can't 'source .venv/bin/activate' in Makefiles.

  ENV ?= dev:
    The ?= operator means "set this default ONLY if not already set."
    make run         → ENV=dev  (uses default)
    make run ENV=staging → ENV=staging  (overrides default)
    export ENV=prod && make run → ENV=prod  (shell env wins)

  $(MAKE) run ENV=prod:
    Calling make from within make using $(MAKE) passes flags correctly.
    Never write 'make' inside a Makefile — always use $(MAKE).

  The help target magic:
    grep -E '^[a-zA-Z_-]+:.*?## .*$$' — finds lines like: target: ## description
    awk '{printf "  \\033[36m%-15s\\033[0m %s\\n", $$1, $$2}' — colors target names
    Result: every target with ## after it appears automatically in 'make help'.

  @echo vs echo:
    The @ prefix suppresses printing the command itself.
    Without @: make prints 'echo "Running..."' then prints "Running..."
    With @:    make only prints "Running..."
""")


# ============================================================
# 4. VARIABLES AND PATTERNS
# ============================================================

section("4. VARIABLES, CHAINING, AND USEFUL PATTERNS")

print("""
  VARIABLES:
  ─────────────────────────────────────────────────────────────────────
  Defined with := (immediate assignment) or = (lazy assignment):
    IMAGE_TAG := $(shell git rev-parse --short HEAD)   # current git commit hash
    TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)
    REGISTRY  := 123456789.dkr.ecr.us-east-1.amazonaws.com

  Use in recipes:
    docker build -t $(REGISTRY)/my_pipeline:$(IMAGE_TAG) .
    docker push $(REGISTRY)/my_pipeline:$(IMAGE_TAG)

  CHAINING TARGETS:
  ─────────────────────────────────────────────────────────────────────
  Run multiple targets in sequence:
    make lint test       ← runs lint then test, sequential
    make install-dev test lint format ← common before a commit

  A target can depend on other targets (run them first):
    test: lint   # always lint before running tests
    \\t$(PYTEST) tests/

  CI target that chains everything:
    ci: install-dev lint test   ## Run full CI suite locally

  CONDITIONAL LOGIC:
  ─────────────────────────────────────────────────────────────────────
  Check if .env file exists before running:
    run:
    \\t@if [ ! -f .env ]; then echo "ERROR: .env file missing. Copy .env.example."; exit 1; fi
    \\t$(VENV)/bin/python src/pipeline.py

  Check if Docker is running:
    docker-up:
    \\t@docker info > /dev/null 2>&1 || (echo "Docker is not running"; exit 1)
    \\tdocker-compose up -d --build

  COMMON PATTERNS FOR DATA TEAMS:
  ─────────────────────────────────────────────────────────────────────
""")

demo("make dbt-run", note="Run all dbt models (maps to: cd dbt && dbt run)")
demo("make dbt-test", note="Run all dbt tests after a model run")
demo("make data-quality", note="Run great_expectations or soda checks")
demo("make deploy-airflow", note="Sync DAGs to Airflow server via rsync or S3")
demo("make lint test", note="Run two targets sequentially (CI pre-commit check)")
demo("make run ENV=staging", note="Pass a variable override on the command line")


# ============================================================
# 5. LIVE DEMO — Actually run a Makefile
# ============================================================

section("5. LIVE DEMO — Running a Real Makefile")

print("""
  Checking if 'make' is available on this machine:
""")

make_check = subprocess.run("which make", shell=True, capture_output=True, text=True)
make_available = make_check.returncode == 0

show("which make", note="Is make installed?")

if make_available:
    tmpdir = tempfile.mkdtemp()
    makefile_path = os.path.join(tmpdir, "Makefile")

    demo_makefile = """.PHONY: greet check-env clean help

.DEFAULT_GOAL := help

PIPELINE := my_data_pipeline

greet: ## Greet the data engineer
\t@echo ""
\t@echo "  Hello from the Makefile!"
\t@echo "  Pipeline: $(PIPELINE)"
\t@echo "  Python: $(shell python3 --version)"
\t@echo "  Working directory: $(shell pwd)"
\t@echo ""

check-env: ## Check if key tools are available
\t@echo "Checking tools..."
\t@which python3 && echo "  [OK] python3" || echo "  [MISSING] python3"
\t@which pip && echo "  [OK] pip" || echo "  [MISSING] pip"
\t@which git && echo "  [OK] git" || echo "  [MISSING] git"
\t@echo "Done."

clean: ## Remove pyc files (demo)
\t@echo "Cleaned build artifacts."

help: ## Show available targets
\t@echo ""
\t@echo "Available targets:"
\t@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \\
\t\tawk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\\n", $$1, $$2}'
\t@echo ""
"""

    with open(makefile_path, "w") as f:
        f.write(demo_makefile)

    print(f"\n  Created demo Makefile in: {tmpdir}")
    print("\n  Running: make help")
    show("make help", cwd=tmpdir)

    print("\n  Running: make greet")
    show("make greet", cwd=tmpdir)

    print("\n  Running: make check-env")
    show("make check-env", cwd=tmpdir)

    shutil.rmtree(tmpdir)
    print(f"\n  Cleaned up temp directory.")
else:
    print("""
  'make' is not installed on this machine.
  To install:
    macOS:  xcode-select --install   (installs make + other dev tools)
            or: brew install make
    Linux:  sudo apt-get install make   (Debian/Ubuntu)
            sudo yum install make       (RHEL/CentOS)
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Makefiles for Data Engineers")
print("=" * 70)
print(r"""
  SYNTAX:
    target: dep1 dep2    target with dependencies
        <TAB>command     recipe — MUST use TAB, not spaces
    .PHONY: t1 t2        mark targets as commands (not file names)
    VAR := value         define variable (immediate)
    VAR ?= default       define variable only if not already set
    $(VAR)               reference a variable
    @command             run silently (don't print the command itself)
    $(MAKE) target       call another target from within a target

  RUNNING:
    make                 run the default goal (.DEFAULT_GOAL)
    make help            show all documented targets
    make install         run the 'install' target
    make lint test       run 'lint' then 'test' sequentially
    make run ENV=prod    override a variable on the command line

  COMMON TARGETS (conventions):
    make install         create venv + install deps
    make install-dev     install dev deps (pytest, black, ruff)
    make test            run tests with coverage
    make lint            check code style
    make format          auto-format code
    make run             run the pipeline
    make docker-up       start docker-compose stack
    make docker-down     stop docker-compose stack
    make clean           remove build artifacts
    make help            show this help (auto-generated from ## comments)

  HELP PATTERN (copy-paste):
    help: ## Show this help
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
            awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
""")
