"""
Data Engineering Project Scaffold Generator
============================================
A CLI tool that generates a complete, production-ready data engineering
project in seconds — with best practices baked in.

Usage:
  python3 project_scaffold_generator.py --name my_pipeline
  python3 project_scaffold_generator.py --name my_pipeline --cloud aws
  python3 project_scaffold_generator.py --name my_pipeline --cloud aws --docker

Features:
  - Configurable project name, Python version, cloud provider, Docker support
  - Generates: src/, tests/, Makefile, requirements files, pyproject.toml,
    .gitignore, .env.example, README, optional Dockerfile + CI workflow
  - Prints a file tree and "Next steps" after generation

This file itself is a working, runnable CLI tool — not pseudocode.
"""

import argparse
import sys
from pathlib import Path


# ============================================================
# FILE CONTENT TEMPLATES
# ============================================================

def make_pipeline_py(project_name: str) -> str:
    module_name = project_name.replace("-", "_")
    return f'''"""
{project_name} — main pipeline entry point
"""
import logging
import sys
from typing import Optional

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--env", default="dev", help="Target environment: dev, staging, prod")
@click.option("--dry-run", is_flag=True, default=False, help="Run without writing output")
@click.option("--date", default=None, help="Override run date (YYYY-MM-DD)")
def main(env: str, dry_run: bool, date: Optional[str]) -> None:
    """Run the {project_name} data pipeline."""
    logger.info("Starting {project_name} | env=%s | dry_run=%s", env, dry_run)

    try:
        run_pipeline(env=env, dry_run=dry_run, run_date=date)
        logger.info("Pipeline completed successfully.")
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


def run_pipeline(env: str, dry_run: bool, run_date: Optional[str]) -> None:
    """Core pipeline logic — implement this."""
    logger.info("Step 1: Extract")
    # data = extract(env=env, date=run_date)

    logger.info("Step 2: Transform")
    # transformed = transform(data)

    logger.info("Step 3: Load")
    # if not dry_run:
    #     load(transformed, env=env)


if __name__ == "__main__":
    main()
'''


def make_init_py(project_name: str) -> str:
    module_name = project_name.replace("-", "_")
    return f'"""{module_name} — data engineering pipeline package."""\n\n__version__ = "0.1.0"\n'


def make_test_pipeline_py(project_name: str) -> str:
    module_name = project_name.replace("-", "_")
    return f'''"""
Tests for {project_name} pipeline.
"""
import pytest


class TestPipeline:
    """Integration tests for the pipeline."""

    def test_placeholder(self):
        """Placeholder test — replace with real tests."""
        assert 1 + 1 == 2

    def test_pipeline_runs(self):
        """
        Test that the pipeline can be imported and the main function exists.
        Replace with real pipeline invocation tests.
        """
        from src.pipeline import run_pipeline
        # Should not raise an exception
        run_pipeline(env="dev", dry_run=True, run_date=None)
'''


def make_conftest_py() -> str:
    return '''"""
pytest configuration and shared fixtures.
"""
import pytest


@pytest.fixture
def dev_env():
    """Return a minimal dev environment config dict."""
    return {
        "env": "dev",
        "db_host": "localhost",
        "db_port": "5432",
        "db_name": "pipeline_dev",
    }
'''


def make_gitignore(cloud: str) -> str:
    base = """# Python
.venv/
__pycache__/
*.py[cod]
*$py.class
*.so
.eggs/
*.egg-info/
dist/
build/
.Python

# Virtual environments
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.hypothesis/

# Type checking
.mypy_cache/
.dmypy.json

# Linting
.ruff_cache/

# Environment and secrets — NEVER COMMIT THESE
.env
.env.*
!.env.example
*.pem
*.key
*_credentials.json
secrets.json

# Data files — keep out of git
*.csv
*.parquet
*.json.gz
*.avro
*.orc
data/raw/
data/processed/
!data/.gitkeep

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Editor
.vscode/
.idea/
*.swp
*.swo
*~
"""
    if cloud == "aws":
        base += """
# AWS
.aws/
*.tfstate
*.tfstate.backup
.terraform/
"""
    elif cloud == "gcp":
        base += """
# GCP
*.json
!.env.example
service_account*.json
gcp_credentials*.json
"""
    return base


def make_makefile(project_name: str, python_version: str, has_docker: bool) -> str:
    docker_targets = ""
    if has_docker:
        docker_targets = """
docker-up: ## Start the docker-compose stack (app + dependencies)
\tdocker-compose up -d --build

docker-down: ## Stop and remove all containers
\tdocker-compose down

docker-logs: ## Follow logs from the pipeline container
\tdocker-compose logs -f pipeline

"""

    phony = "install install-dev test test-fast lint format run clean"
    if has_docker:
        phony += " docker-up docker-down docker-logs"
    phony += " help"

    return f""".PHONY: {phony}

# ── Variables ─────────────────────────────────────────────────────────
PYTHON  := python{python_version[:4]}
VENV    := .venv
PIP     := $(VENV)/bin/pip

ENV ?= dev

.DEFAULT_GOAL := help

# ── Setup ─────────────────────────────────────────────────────────────

install: ## Install runtime dependencies
\t$(PYTHON) -m venv $(VENV)
\t$(PIP) install --upgrade pip
\t$(PIP) install -r requirements.txt

install-dev: ## Install all dependencies including dev/test tools
\t$(PYTHON) -m venv $(VENV)
\t$(PIP) install --upgrade pip
\t$(PIP) install -r requirements-dev.txt

# ── Quality ───────────────────────────────────────────────────────────

test: ## Run tests with coverage
\t$(VENV)/bin/pytest tests/ -v --cov=src --cov-report=term-missing

test-fast: ## Run tests without coverage (fast feedback)
\t$(VENV)/bin/pytest tests/ -v -x

lint: ## Check code style (ruff + black --check)
\t$(VENV)/bin/ruff check .
\t$(VENV)/bin/black --check .

format: ## Auto-format code (black + ruff --fix)
\t$(VENV)/bin/black .
\t$(VENV)/bin/ruff check --fix .

# ── Run ───────────────────────────────────────────────────────────────

run: ## Run the pipeline locally (default: ENV=dev)
\t@if [ ! -f .env ]; then echo "Missing .env — copy from .env.example"; exit 1; fi
\t$(VENV)/bin/python src/pipeline.py --env $(ENV)

run-prod: ## Run the pipeline against production
\t$(MAKE) run ENV=prod
{docker_targets}
# ── Cleanup ───────────────────────────────────────────────────────────

clean: ## Remove build artifacts, pycache, and test output
\tfind . -type d -name '__pycache__' -exec rm -rf {{}} + 2>/dev/null || true
\tfind . -name '*.pyc' -delete 2>/dev/null || true
\trm -rf .pytest_cache .coverage htmlcov/ dist/ *.egg-info/

clean-all: clean ## Full reset: also removes .venv
\trm -rf $(VENV)

# ── Help ──────────────────────────────────────────────────────────────

help: ## Show available targets
\t@echo ""
\t@echo "  {project_name} — available make targets:"
\t@echo ""
\t@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \\
\t\tawk 'BEGIN {{FS = ":.*?## "}}; {{printf "  \\033[36m%-15s\\033[0m %s\\n", $$1, $$2}}'
\t@echo ""
"""


def make_requirements_in(cloud: str) -> str:
    base = """# Runtime dependencies
# Edit this file, then run: pip-compile requirements.in
pandas>=2.0
sqlalchemy>=2.0
psycopg2-binary
click>=8.0
python-dotenv
"""
    if cloud == "aws":
        base += "boto3\n"
    elif cloud == "gcp":
        base += "google-cloud-storage\ngoogle-cloud-bigquery\n"
    return base


def make_requirements_dev_txt() -> str:
    return """# Development dependencies — install with: pip install -r requirements-dev.txt
# Runtime deps are included via -r requirements.txt (or pip-compile requirements-dev.in)

# Include runtime deps
-r requirements.txt

# Testing
pytest>=7.0
pytest-cov>=4.0

# Code quality
black>=23.0
ruff>=0.1
mypy>=1.0

# Dependency management
pip-tools>=7.0
"""


def make_pyproject_toml(project_name: str, python_version: str) -> str:
    module_name = project_name.replace("-", "_")
    return f"""[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "Data engineering pipeline for {project_name}"
requires-python = ">={python_version[:4]}"
readme = "README.md"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
]
ignore = ["E501"]  # line length handled by black

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "--tb=short"

[tool.mypy]
python_version = "{python_version[:4]}"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
"""


def make_env_example(cloud: str) -> str:
    base = """# Copy this file to .env and fill in real values
# .env is in .gitignore — never commit .env with real credentials

# Pipeline settings
ENV=dev
LOG_LEVEL=INFO

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pipeline_dev
DB_USER=pipeline_user
DB_PASSWORD=changeme
"""
    if cloud == "aws":
        base += """
# AWS (only for local dev — use IAM role on servers)
# AWS_PROFILE=dev   # preferred: use named profile
# Or:
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=my-data-bucket
"""
    elif cloud == "gcp":
        base += """
# GCP (only for local dev — use service account key or ADC on servers)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
GCP_PROJECT_ID=my-project
GCS_BUCKET=my-data-bucket
"""
    return base


def make_readme(project_name: str, python_version: str, cloud: str, has_docker: bool) -> str:
    cloud_note = ""
    if cloud == "aws":
        cloud_note = "\n- AWS CLI configured (`aws configure` or `AWS_PROFILE` set)\n- Appropriate IAM role or user credentials for S3 and Secrets Manager"
    elif cloud == "gcp":
        cloud_note = "\n- GCP credentials configured (`gcloud auth application-default login`)"

    docker_note = "\n- Docker and docker-compose installed" if has_docker else ""

    docker_section = ""
    if has_docker:
        docker_section = """
## Docker

```bash
make docker-up     # Start Postgres + app stack
make docker-logs   # Follow live logs
make docker-down   # Tear down stack
```
"""

    return f"""# {project_name}

Data engineering pipeline.

## Prerequisites

- Python {python_version[:4]}+ (use pyenv: `pyenv install {python_version} && pyenv local {python_version}`){cloud_note}{docker_note}

## Quick Start

```bash
# 1. Set up the environment
make install-dev

# 2. Configure local environment
cp .env.example .env
# Edit .env with your local settings

# 3. Run the pipeline
make run
```

## Development

```bash
make help          # Show all available commands
make test          # Run tests with coverage
make lint          # Check code style
make format        # Auto-format code
make run ENV=dev   # Run pipeline locally
```
{docker_section}
## Project Structure

```
{project_name}/
├── src/
│   ├── __init__.py
│   └── pipeline.py       # Main pipeline entry point
├── tests/
│   ├── conftest.py
│   └── test_pipeline.py
├── .env.example           # Environment variable template
├── .gitignore
├── Makefile
├── pyproject.toml         # Black, ruff, pytest config
├── requirements.in        # Direct dependencies (edit this)
├── requirements.txt       # Pinned deps (auto-generated)
└── requirements-dev.txt   # Dev dependencies
```

## Configuration

All configuration is via environment variables. See `.env.example` for the full list.

For production, use AWS Secrets Manager (or GCP Secret Manager) instead of `.env` files.

## Deployment

```bash
# Build and tag Docker image
docker build -t {project_name}:latest .

# Run with production environment
docker run --env-file .env.prod {project_name}:latest
```
"""


def make_dockerfile(project_name: str, python_version: str) -> str:
    return f"""# Multi-stage build for smaller final image
FROM python:{python_version}-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (separate layer — rebuilds when code changes)
COPY src/ ./src/
COPY pyproject.toml .

# Create non-root user (security best practice)
RUN useradd --create-home --shell /bin/bash pipeline
USER pipeline

# Pipeline entry point
CMD ["python", "src/pipeline.py", "--env", "prod"]
"""


def make_docker_compose(project_name: str) -> str:
    return f"""version: "3.9"

services:
  pipeline:
    build: .
    container_name: {project_name}
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./src:/app/src:ro    # Mount src for dev iteration (remove in prod)
      - ./data:/app/data

  postgres:
    image: postgres:15-alpine
    container_name: {project_name}_db
    environment:
      POSTGRES_DB: ${{DB_NAME:-pipeline_dev}}
      POSTGRES_USER: ${{DB_USER:-pipeline_user}}
      POSTGRES_PASSWORD: ${{DB_PASSWORD:-changeme}}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${{DB_USER:-pipeline_user}}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
"""


def make_ci_yml(project_name: str, python_version: str) -> str:
    return f"""name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python {python_version[:4]}
        uses: actions/setup-python@v5
        with:
          python-version: "{python_version[:4]}"
          cache: "pip"

      - name: Install dependencies
        run: make install-dev

      - name: Lint
        run: make lint

      - name: Test
        run: make test

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: .coverage
        continue-on-error: true
"""


def make_python_version_file(python_version: str) -> str:
    return python_version + "\n"


# ============================================================
# SCAFFOLD GENERATOR
# ============================================================

def generate_scaffold(
    name: str,
    python_version: str,
    cloud: str,
    docker: bool,
    output_dir: Path,
) -> list[Path]:
    """Generate the project scaffold and return list of created paths."""
    project_dir = output_dir / name
    created: list[Path] = []

    def write(rel_path: str, content: str) -> Path:
        full_path = project_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        created.append(full_path)
        return full_path

    # Core source code
    write("src/__init__.py", make_init_py(name))
    write("src/pipeline.py", make_pipeline_py(name))

    # Tests
    write("tests/__init__.py", "")
    write("tests/conftest.py", make_conftest_py())
    write("tests/test_pipeline.py", make_test_pipeline_py(name))

    # Data directory placeholder
    write("data/.gitkeep", "")

    # Project config files
    write(".gitignore", make_gitignore(cloud))
    write(".env.example", make_env_example(cloud))
    write(".python-version", make_python_version_file(python_version))
    write("pyproject.toml", make_pyproject_toml(name, python_version))
    write("requirements.in", make_requirements_in(cloud))
    write("requirements-dev.txt", make_requirements_dev_txt())
    write("Makefile", make_makefile(name, python_version, docker))
    write("README.md", make_readme(name, python_version, cloud, docker))

    # Docker (optional)
    if docker:
        write("Dockerfile", make_dockerfile(name, python_version))
        write("docker-compose.yml", make_docker_compose(name))
        write(".dockerignore", ".venv/\n__pycache__/\n*.pyc\n.env\ndata/\n.git/\n")

    # GitHub Actions CI
    write(".github/workflows/ci.yml", make_ci_yml(name, python_version))

    return created


# ============================================================
# FILE TREE PRINTER
# ============================================================

def print_tree(root: Path, created: list[Path]) -> None:
    """Print a visual tree of created files."""
    # Collect relative paths, sorted
    rel_paths = sorted(p.relative_to(root) for p in created)

    print(f"\n  {root.name}/")
    last_dirs: list[str] = []

    for rel_path in rel_paths:
        parts = list(rel_path.parts)
        # Find how deep we are
        for i, part in enumerate(parts):
            prefix = "  "
            if i == 0:
                indent = "    "
            else:
                indent = "    " + "    " * i
            if i == len(parts) - 1:
                print(f"{indent}├── {part}")


def print_file_tree(project_dir: Path, created: list[Path]) -> None:
    """Print a clean file tree."""
    rel_paths = sorted(p.relative_to(project_dir) for p in created)

    def render(paths: list[Path], prefix: str = "") -> None:
        for i, path in enumerate(paths):
            is_last = (i == len(paths) - 1)
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "
            parts = path.parts
            if len(parts) == 1:
                print(f"  {prefix}{connector}{parts[0]}")
            # For nested paths, we'll handle via grouping

    # Group by top-level entry
    from collections import defaultdict
    tree: dict = {}
    for rel in rel_paths:
        parts = rel.parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None  # leaf

    def render_node(node: dict, prefix: str = "  ") -> None:
        items = sorted(node.keys(), key=lambda k: (node[k] is None, k))
        for i, key in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            if node[key] is None:
                print(f"  {prefix}{connector}{key}")
            else:
                print(f"  {prefix}{connector}{key}/")
                render_node(node[key], child_prefix)

    print(f"\n  {project_dir.name}/")
    render_node(tree)


# ============================================================
# CLI ENTRY POINT
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a complete data engineering project scaffold.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 project_scaffold_generator.py --name my_pipeline
  python3 project_scaffold_generator.py --name etl_jobs --cloud aws
  python3 project_scaffold_generator.py --name lakehouse --cloud aws --docker
        """,
    )
    parser.add_argument(
        "--name",
        help="Project name (e.g. my_pipeline, customer_etl)",
        default=None,
    )
    parser.add_argument(
        "--python",
        dest="python_version",
        default="3.11.6",
        help="Python version to pin (default: 3.11.6)",
    )
    parser.add_argument(
        "--cloud",
        choices=["aws", "gcp", "none"],
        default="none",
        help="Cloud provider for extra dependencies and config (default: none)",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        default=False,
        help="Include Dockerfile and docker-compose.yml",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Where to create the project directory (default: current directory)",
    )
    return parser.parse_args()


def interactive_prompt(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in missing args via interactive prompts."""
    if args.name is None:
        print()
        name = input("  Project name (e.g. customer_churn_pipeline): ").strip()
        if not name:
            print("  Error: project name is required.")
            sys.exit(1)
        args.name = name

    # Sanitize name: replace spaces and hyphens with underscores for module names
    args.name = args.name.strip().replace(" ", "_")

    if args.cloud == "none":
        print()
        cloud_input = input("  Cloud provider? [aws/gcp/none] (default: none): ").strip().lower()
        if cloud_input in ("aws", "gcp"):
            args.cloud = cloud_input

    if not args.docker:
        print()
        docker_input = input("  Include Docker support? [y/N] (default: N): ").strip().lower()
        args.docker = docker_input in ("y", "yes")

    return args


def main() -> None:
    args = parse_args()

    # If running directly without all args, enter interactive mode
    if args.name is None or (len(sys.argv) == 1):
        print()
        print("=" * 70)
        print("  Data Engineering Project Scaffold Generator")
        print("=" * 70)
        args = interactive_prompt(args)

    output_dir = Path(args.output_dir).resolve()
    project_dir = output_dir / args.name

    if project_dir.exists():
        print(f"\n  Error: '{project_dir}' already exists.")
        print(f"  Delete it first or choose a different name.")
        sys.exit(1)

    print()
    print(f"  Generating project: {args.name}")
    print(f"  Python version:     {args.python_version}")
    print(f"  Cloud provider:     {args.cloud}")
    print(f"  Docker support:     {'yes' if args.docker else 'no'}")
    print(f"  Output directory:   {output_dir}")
    print()

    created = generate_scaffold(
        name=args.name,
        python_version=args.python_version,
        cloud=args.cloud,
        docker=args.docker,
        output_dir=output_dir,
    )

    print(f"  Created {len(created)} files:")
    print_file_tree(project_dir, created)

    print()
    print("=" * 70)
    print("  NEXT STEPS")
    print("=" * 70)
    print(f"""
  cd {args.name}

  # 1. Pin your Python version (requires pyenv)
  pyenv install {args.python_version}   # if not already installed
  pyenv local {args.python_version}     # already done — .python-version created

  # 2. Create virtual environment and install dependencies
  make install-dev

  # 3. Set up your local environment
  cp .env.example .env
  # Edit .env with your local DB credentials and settings

  # 4. Run the tests to confirm everything works
  make test

  # 5. Run the pipeline locally
  make run

  # 6. See all available commands
  make help
""")

    if args.cloud == "aws":
        print("""  AWS NOTES:
  - Add your S3 bucket name to .env (S3_BUCKET=your-bucket)
  - For local dev: run 'aws configure --profile dev' to set credentials
  - For production EC2: attach an IAM role instead of using credentials
  - Store DB passwords in Secrets Manager, not .env
""")
    elif args.cloud == "gcp":
        print("""  GCP NOTES:
  - Add your GCS bucket and project to .env
  - For local dev: run 'gcloud auth application-default login'
  - For production: use a service account with least privilege
""")

    if args.docker:
        print("""  DOCKER NOTES:
  - Start the full stack: make docker-up
  - The Postgres container is already configured in docker-compose.yml
  - Your .env DB_HOST should be 'postgres' when running in Docker
""")


if __name__ == "__main__":
    main()
