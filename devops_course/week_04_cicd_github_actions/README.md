# Week 4: CI/CD with GitHub Actions

Automate testing and deployment for every commit. Never deploy untested code again.

---

## What You'll Learn

| File | Topic |
|------|-------|
| `concepts/01_cicd_concepts_and_why_it_matters.py` | Integration hell, CI vs CD, data-engineer-specific pain points, pipeline stages, a Python simulation of a CI pipeline |
| `concepts/02_github_actions_fundamentals.py` | Workflow structure, all triggers (push/PR/schedule/dispatch/paths), jobs, steps, popular actions, secrets and context variables, matrix builds |
| `concepts/03_testing_and_linting_in_ci.py` | pytest in CI with coverage enforcement, Postgres service containers, ruff/black/mypy/sqlfluff, pip caching, artifact uploads, security scanning with bandit and safety |
| `concepts/04_deploying_data_pipelines_with_actions.py` | Four deployment patterns (Airflow, dbt, Docker, Lambda), build+push Docker image, environment-based deployment, secrets best practices, Slack notifications, reusable workflows |

---

## Folder Structure

```
week_04_cicd_github_actions/
├── README.md
├── concepts/
│   ├── 01_cicd_concepts_and_why_it_matters.py
│   ├── 02_github_actions_fundamentals.py
│   ├── 03_testing_and_linting_in_ci.py
│   └── 04_deploying_data_pipelines_with_actions.py
├── practice/
│   └── exercises.py
└── projects/
    └── sample_pipeline_with_ci/
        ├── pipeline.py               ETL: extract, transform, load
        ├── test_pipeline.py          pytest unit tests (13 tests)
        ├── requirements.txt          pandas, sqlalchemy
        ├── requirements-dev.txt      + pytest, pytest-cov, black, ruff, mypy
        ├── Makefile                  make test / lint / format / ci-local
        ├── .pre-commit-config.yaml   black + ruff pre-commit hooks
        └── .github/
            └── workflows/
                ├── ci.yml            lint + test with coverage on every PR
                └── deploy.yml        build + push Docker image on main merge
```

---

## How to Use This Week

### Run the concept files (no installs needed for concepts 1-4)

```bash
# Concepts 1-4 use only the Python standard library
python3 concepts/01_cicd_concepts_and_why_it_matters.py
python3 concepts/02_github_actions_fundamentals.py
python3 concepts/03_testing_and_linting_in_ci.py
python3 concepts/04_deploying_data_pipelines_with_actions.py
```

### Run the practice exercises

```bash
python3 practice/exercises.py
```

### Run the sample project locally

```bash
cd projects/sample_pipeline_with_ci

# Install everything
pip install -r requirements-dev.txt

# Run tests
make test

# Check code quality
make lint

# Auto-format
make format

# Simulate full CI run locally (lint + test)
make ci-local

# Run the actual pipeline
make run

# Set up pre-commit hooks (runs black + ruff before every commit)
pip install pre-commit
pre-commit install
```

### Enable CI on GitHub

1. Push the `projects/sample_pipeline_with_ci/` directory (or the whole repo) to GitHub.
2. GitHub automatically detects `.github/workflows/ci.yml`.
3. Go to the **Actions** tab to see your workflow.
4. Open a PR — green/red checks appear at the bottom of the PR.
5. Go to repo **Settings → Branches → Add rule**, check "Require status checks", select "Unit Tests" and "Lint and Format Check".

---

## Practice Goals

By the end of this week you should be able to:

1. **Write a CI workflow from scratch** — triggers, jobs, steps, checkout, setup-python, install, test.
2. **Add a Postgres service container** to run integration tests against a real database in CI.
3. **Set up pip caching** with the correct cache key (hashFiles pattern) to cut CI time by 2-3x.
4. **Configure a matrix build** to test against Python 3.10, 3.11, and 3.12 simultaneously.
5. **Write a deploy workflow** that triggers only on main, builds a Docker image tagged with the git SHA, and pushes to a registry.
6. **Identify and fix security issues** — hardcoded credentials, secret echoing, artifact leaks.

---

## GitHub Actions Cheat Sheet

### Workflow Structure

```yaml
name: My Workflow

on:
  push:
    branches: [main]
    paths: ['**.py', 'requirements*.txt']
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'       # daily at 2am UTC
  workflow_dispatch:            # manual trigger button

jobs:
  my-job:
    runs-on: ubuntu-latest
    needs: [other-job]          # wait for other-job first
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: My step
        run: echo "hello"
```

### Essential Actions

| Action | Purpose |
|--------|---------|
| `actions/checkout@v4` | Checkout your repo (always first) |
| `actions/setup-python@v5` | Install Python version |
| `actions/cache@v3` | Cache pip dependencies (2-3x speedup) |
| `actions/upload-artifact@v4` | Save files (coverage.xml, test results) |
| `docker/setup-buildx-action@v3` | Enable Docker BuildKit |
| `docker/login-action@v3` | Authenticate to Docker Hub / ECR / GCR |
| `docker/build-push-action@v5` | Build and push Docker image |
| `aws-actions/configure-aws-credentials@v4` | Authenticate to AWS |

### Context Variables

```yaml
${{ github.sha }}          # full 40-char commit hash
${{ github.ref }}          # refs/heads/main
${{ github.actor }}        # who triggered the run
${{ github.repository }}   # org/repo-name
${{ github.event_name }}   # push, pull_request, schedule
${{ runner.os }}           # Linux, macOS, Windows
${{ secrets.MY_SECRET }}   # repository or environment secret
```

### Cache Pattern

```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Service Container (Postgres)

```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: testpass
      POSTGRES_USER: testuser
      POSTGRES_DB: testdb
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### Matrix Build

```yaml
strategy:
  fail-fast: false
  matrix:
    python-version: ['3.10', '3.11', '3.12']
steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

### Conditionals

```yaml
if: success()              # run only if all previous steps passed (default)
if: failure()              # run only if something failed (notifications)
if: always()               # always run (artifact uploads)
if: github.ref == 'refs/heads/main'  # only on main branch
continue-on-error: true    # advisory steps (security scan, mypy)
```

### Secrets Best Practices

```yaml
# CORRECT: pass as env var, use $ENV_VAR in scripts
- name: Deploy
  env:
    DB_URL: ${{ secrets.PROD_DB_URL }}
  run: python deploy.py    # reads os.environ["DB_URL"]

# WRONG: embedding secret in run command
# run: python deploy.py --db ${{ secrets.PROD_DB_URL }}
```

---

## Key Concepts Summary

**CI (Continuous Integration):** merge frequently, run automated checks on every commit.

**CD (Continuous Delivery):** every passing commit is deployable; humans approve production deployments.

**CD (Continuous Deployment):** every passing commit auto-deploys, no human intervention.

**Integration hell:** what happens when teams avoid CI — merge once a week, everything breaks, nobody knows why.

**Service containers:** run a real database (Postgres, MySQL, Redis) alongside your CI job. No mocking. Real integration tests.

**cache key invalidation:** `hashFiles('requirements*.txt')` — the cache automatically invalidates when dependency files change.

**Image tagging:** always tag with git SHA (`:abc123def`). Never pin to `:latest` in production — you lose traceability.

**Environment secrets:** scoped to GitHub Environments (staging/production). More secure than repo-level secrets.
