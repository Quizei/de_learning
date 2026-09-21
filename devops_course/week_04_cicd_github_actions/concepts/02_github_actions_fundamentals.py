"""
GitHub Actions Fundamentals — Workflows, Jobs, Steps, and Triggers
===================================================================
"Your CI/CD pipeline lives in the same repo as your code."

GitHub Actions is GitHub's built-in CI/CD platform.
Workflows are YAML files in .github/workflows/.
Every push, PR, or scheduled event can trigger a workflow.
The workflow runs on a virtual machine GitHub manages for you.

This file covers:
- Where workflows live and the complete annotated structure
- Triggers: push, pull_request, schedule, workflow_dispatch, paths
- Jobs: parallel and sequential
- Steps: uses (actions) vs run (shell commands)
- Popular actions every data engineer should know
- Environment variables and secrets
- Matrix builds: test multiple Python versions simultaneously
- How to read CI results in the GitHub UI

Run this file: python3 concepts/02_github_actions_fundamentals.py
Workflows can't run locally — we print and explain them instead.
"""

# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def explain_yaml(yaml_str, notes=""):
    """Print a YAML block with annotation lines, then explanatory notes."""
    print()
    print("  " + "-" * 66)
    for line in yaml_str.strip().splitlines():
        print(f"  {line}")
    print("  " + "-" * 66)
    if notes:
        print()
        for note_line in notes.strip().splitlines():
            print(f"  {note_line}")


# ============================================================
# 1. WHERE WORKFLOWS LIVE
# ============================================================

section("1. WHERE WORKFLOWS LIVE")

print("""
  Every GitHub Actions workflow is a YAML file inside:

    .github/workflows/

  This directory lives at the ROOT of your repository.
  You can have as many workflow files as you want:

    .github/
    └── workflows/
        ├── ci.yml          ← runs on every push/PR
        ├── deploy.yml      ← runs only on main branch merge
        ├── nightly.yml     ← runs on a cron schedule
        └── release.yml     ← runs when you create a GitHub Release tag

  IMPORTANT: The workflow file IS your pipeline definition.
  It's version-controlled with your code.
  Code review includes pipeline review.
  Rolling back a bad pipeline = git revert.
""")


# ============================================================
# 2. COMPLETE ANNOTATED WORKFLOW
# ============================================================

section("2. COMPLETE ANNOTATED WORKFLOW — EVERY LINE EXPLAINED")

print("""
  Let's read a complete workflow file line by line.
  This is the most important YAML you will ever read.
""")

basic_workflow = """
# ── FILE: .github/workflows/ci.yml ──────────────────────────────

name: Pipeline CI                     # Display name in GitHub UI

on:                                   # TRIGGERS — when does this run?
  push:
    branches: [main]                  # On push to main branch
  pull_request:
    branches: [main]                  # On any PR targeting main

jobs:                                 # JOBS — units of work

  test:                               # Job ID (can be anything)
    runs-on: ubuntu-latest            # Which VM to use

    steps:                            # STEPS — sequential commands in this job

      - uses: actions/checkout@v4     # Step 1: checkout your repo code
                                      # Without this, the VM has NO code!

      - uses: actions/setup-python@v5 # Step 2: install Python
        with:
          python-version: '3.11'      # Which Python version

      - name: Install dependencies    # Step 3: install your packages
        run: pip install -r requirements-dev.txt

      - name: Lint with ruff          # Step 4: run the linter
        run: ruff check .

      - name: Format check            # Step 5: check formatting
        run: black --check .

      - name: Run tests               # Step 6: run the test suite
        run: pytest tests/ -v --tb=short
"""

explain_yaml(basic_workflow, """
  LINE-BY-LINE BREAKDOWN:

  name: Pipeline CI
    → The workflow name shown in GitHub's Actions tab.
      Use something descriptive: "CI", "Tests", "Deploy to Prod".

  on: push: branches: [main]
    → This workflow triggers on every push to the main branch.
      Square brackets = YAML list. Could also write:
        branches:
          - main
          - develop

  on: pull_request: branches: [main]
    → Also triggers on every PR that targets main.
      This means BEFORE the code merges, CI already ran.
      You see green/red checks on the PR before you click Merge.

  jobs: test:
    → "test" is the job ID. It appears in the GitHub UI.
      You could name it "run-ci", "build", "check" — anything.

  runs-on: ubuntu-latest
    → GitHub spins up a fresh Ubuntu VM for this job.
      Options: ubuntu-latest, ubuntu-22.04, windows-latest, macos-latest
      ubuntu-latest is standard for Python/Docker work.
      The VM is DISCARDED after the job finishes — fully clean each run.

  steps:
    → Steps run SEQUENTIALLY in the same VM.
      If one step fails, subsequent steps are skipped (by default).

  - uses: actions/checkout@v4
    → "uses" runs a reusable Action from the Marketplace.
      actions/checkout checks out YOUR repo onto the VM.
      @v4 = version 4. ALWAYS pin to a version (not @main) for stability.
      Without this step, the VM is empty — your code isn't there yet.

  - uses: actions/setup-python@v5
    → Installs the specified Python version on the VM.
      "with:" provides input parameters to the action.
      python-version: '3.11' installs CPython 3.11.

  - name: Install dependencies
    run: pip install -r requirements-dev.txt
    → "run:" executes a shell command.
      "name:" is optional but makes logs readable.
      Multi-line run: use | (pipe) for multiple commands:
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

  - name: Run tests
    run: pytest tests/ -v --tb=short
    → If pytest exits with code != 0, this step fails.
      A failed step fails the job.
      A failed job blocks PR merging (if branch protection is on).
""")


# ============================================================
# 3. TRIGGERS DEEP DIVE
# ============================================================

section("3. TRIGGERS DEEP DIVE")

print("""
  The "on:" block controls WHEN your workflow runs.
  This is where most customization happens for data teams.
""")

triggers_yaml = """
on:
  # ── PUSH ─────────────────────────────────────────────────
  push:
    branches:
      - main
      - 'release/**'           # wildcard: release/1.0, release/2.3
    paths:                     # Only trigger if THESE files changed
      - 'pipelines/**'         # Any file under pipelines/
      - 'dbt/**'               # Any dbt model
      - 'requirements*.txt'    # Any requirements file
      - '!docs/**'             # Ignore docs changes (! = exclude)

  # ── PULL REQUEST ─────────────────────────────────────────
  pull_request:
    branches: [main]
    types:
      - opened                 # New PR opened
      - synchronize            # New commit pushed to existing PR
      - reopened               # Closed PR reopened
    paths:
      - 'pipelines/**'
      - '**.py'

  # ── SCHEDULE (CRON) ──────────────────────────────────────
  schedule:
    - cron: '0 2 * * *'       # Every day at 2am UTC
    - cron: '0 9 * * 1'       # Every Monday at 9am UTC

  # ── MANUAL TRIGGER ───────────────────────────────────────
  workflow_dispatch:            # Adds a "Run workflow" button in GitHub UI
    inputs:                     # Optional: collect user input
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]
"""

explain_yaml(triggers_yaml, """
  KEY CONCEPTS:

  paths: filter — critical for data repos
    Without paths filter: EVERY push (including README edits) runs CI.
    With paths filter: CI only runs when pipeline code actually changes.
    This saves CI minutes and reduces noise.

    Example: you're updating documentation.
    Without paths filter: full CI run (2-3 minutes, wastes quota).
    With paths filter: no CI run (documentation didn't touch pipelines/**).

    DATA ENGINEER PATHS TO FILTER ON:
      - 'pipelines/**'     your ETL code
      - 'dbt/**'           dbt models
      - 'airflow/**'       DAG files
      - 'requirements*.txt' dependency changes always trigger
      - '**.py'            any Python file

  schedule: cron syntax:
    ┌─ minute (0-59)
    │ ┌─ hour (0-23)
    │ │ ┌─ day of month (1-31)
    │ │ │ ┌─ month (1-12)
    │ │ │ │ ┌─ day of week (0-7, 0 and 7 are Sunday)
    │ │ │ │ │
    0 2 * * *   = every day at 2am UTC
    0 9 * * 1   = every Monday at 9am UTC
    0 */6 * * * = every 6 hours
    0 0 1 * *   = first day of every month at midnight

  workflow_dispatch:
    Adds a manual "Run workflow" button in GitHub Actions UI.
    Useful for: one-off data backfills, manual deploys to prod,
    running the pipeline for a specific date range.
    The "inputs" block lets you pass parameters when you click the button.
""")


# ============================================================
# 4. JOBS — PARALLEL AND SEQUENTIAL
# ============================================================

section("4. JOBS — PARALLEL AND SEQUENTIAL")

print("""
  A workflow can have multiple jobs.
  By default, all jobs run IN PARALLEL.
  Use "needs:" to create dependencies between jobs.
""")

jobs_yaml = """
jobs:

  # ── JOB 1: LINT (runs immediately) ───────────────────────
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install ruff black
      - run: ruff check . && black --check .

  # ── JOB 2: UNIT TESTS (runs immediately, parallel to lint) ──
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ -v

  # ── JOB 3: INTEG TESTS (waits for BOTH above to pass) ───
  integration-tests:
    runs-on: ubuntu-latest
    needs: [lint, unit-tests]         # Won't start until both pass
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/integration/ -v

  # ── JOB 4: DEPLOY (waits for integ tests) ────────────────
  deploy:
    runs-on: ubuntu-latest
    needs: [integration-tests]        # Only deploys if integ tests pass
    if: github.ref == 'refs/heads/main'  # Only on main branch
    steps:
      - uses: actions/checkout@v4
      - run: ./scripts/deploy.sh
"""

explain_yaml(jobs_yaml, """
  EXECUTION ORDER:

    lint ──────────────────────────────────────────┐
                                                    ├──► integration-tests ──► deploy
    unit-tests ────────────────────────────────────┘

  lint and unit-tests run SIMULTANEOUSLY (parallel).
  integration-tests waits for BOTH to pass (needs: [lint, unit-tests]).
  deploy waits for integration-tests AND only runs on main.

  WHY PARALLELIZE?
    Without parallel: lint + unit + integ = 1+2+3 = 6 minutes total.
    With parallel:    lint || unit + integ = max(1,2)+3 = 5 minutes.
    For big test suites, parallelism cuts CI time significantly.

  if: github.ref == 'refs/heads/main'
    Conditional execution — only run this job on the main branch.
    On a PR branch, CI runs but deploy is skipped.
    This is the gating mechanism: only merged code deploys.

  OTHER USEFUL CONDITIONS:
    if: github.event_name == 'push'          only on push, not PR
    if: contains(github.ref, 'release/')     only on release branches
    if: failure()                            only if previous step failed
    if: always()                             always run (even if job failed)
""")


# ============================================================
# 5. POPULAR ACTIONS EVERY DATA ENGINEER SHOULD KNOW
# ============================================================

section("5. POPULAR ACTIONS EVERY DATA ENGINEER SHOULD KNOW")

print("""
  Actions are reusable units of work published on the GitHub Marketplace.
  Think of them as "pip install for CI steps."
  You reference them as: uses: owner/action-name@version
""")

actions = [
    ("actions/checkout@v4",
     "ALWAYS the first step. Checks out your repository code onto the VM.\n"
     "     Without this: the VM has no code to work with."),

    ("actions/setup-python@v5",
     "Installs a specific Python version. Supports 3.9 through 3.13.\n"
     "     with: python-version: '3.11'"),

    ("actions/cache@v3",
     "Caches a directory between runs. Huge speed improvement for pip.\n"
     "     Reduces 90-second pip install to 5-second cache restore."),

    ("actions/upload-artifact@v4",
     "Saves files from a job (test reports, coverage XML, built binaries).\n"
     "     Use it to persist coverage.xml for later steps or PR comments."),

    ("actions/download-artifact@v4",
     "Downloads artifacts uploaded by a previous job in the same workflow."),

    ("docker/login-action@v3",
     "Authenticate to Docker Hub, ECR, GCR, or any registry.\n"
     "     Uses secrets for credentials."),

    ("docker/build-push-action@v5",
     "Build and push a Docker image. Handles multi-platform builds.\n"
     "     Integrates with docker/login-action for auth."),

    ("docker/setup-buildx-action@v3",
     "Enables Docker BuildKit (faster builds, better caching).\n"
     "     Required before docker/build-push-action."),

    ("aws-actions/configure-aws-credentials@v4",
     "Authenticate to AWS using GitHub OIDC (no long-lived keys needed).\n"
     "     Sets AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars."),

    ("google-github-actions/auth@v2",
     "Authenticate to Google Cloud (GCS, BigQuery, Cloud Run, etc.).\n"
     "     Use OIDC for keyless auth in production."),
]

for action_name, description in actions:
    print(f"\n  uses: {action_name}")
    print(f"     {description}")

print("""

  CACHE ACTION EXAMPLE (the most impactful optimization):
""")

cache_yaml = """
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-

- name: Install dependencies
  run: pip install -r requirements-dev.txt
"""

explain_yaml(cache_yaml, """
  HOW CACHING WORKS:
    1. GitHub hashes your requirements*.txt files.
    2. If a cache with that hash exists from a previous run → restore it.
    3. pip install then finds packages already in ~/.cache/pip → fast.
    4. If requirements.txt changed → hash changes → cache miss → fresh install.
    5. The new packages are cached for the next run.

  RESULT: pip install goes from ~90 seconds to ~5 seconds on cache hit.
  This is a 2-3x speedup for most CI jobs.

  restore-keys: fallback if exact key misses (uses partial match).
  This means even if you add ONE new package, you still restore the
  old cache and only download the new package.
""")


# ============================================================
# 6. ENVIRONMENT VARIABLES AND SECRETS
# ============================================================

section("6. ENVIRONMENT VARIABLES AND SECRETS")

print("""
  Workflows need configuration (database URLs, API keys, bucket names).
  There are three tiers: hardcoded env, repository secrets, context variables.
""")

env_yaml = """
jobs:
  test:
    runs-on: ubuntu-latest

    env:                                          # Job-level env vars
      PYTHONPATH: src
      LOG_LEVEL: DEBUG
      DB_HOST: localhost                          # OK to hardcode non-secrets

    steps:
      - uses: actions/checkout@v4

      - name: Run tests with DB credentials
        env:                                      # Step-level (overrides job-level)
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }} # From GitHub Secrets
          AWS_REGION: us-east-1                   # Hardcoded (not secret)
        run: |
          echo "DB_HOST is $DB_HOST"              # prints: DB_HOST is localhost
          echo "DB_PASSWORD is $DB_PASSWORD"      # prints: DB_PASSWORD is ***
          pytest tests/ -v

      - name: Build image with git SHA tag
        run: |
          docker build -t myapp:${{ github.sha }} .
          # github.sha = full commit hash, e.g. a3f9c2d7b1e4f...
"""

explain_yaml(env_yaml, """
  THREE TIERS OF VARIABLES:

  1. HARDCODED env vars (env: KEY: VALUE)
     Fine for: log levels, hostnames in non-prod, feature flags.
     NOT for: passwords, API keys, connection strings.

  2. SECRETS (${{ secrets.SECRET_NAME }})
     Stored in: GitHub repo Settings → Secrets and variables → Actions.
     GitHub AUTOMATICALLY masks them in logs: shows *** instead.
     Use for: DB_PASSWORD, AWS_ACCESS_KEY_ID, DOCKER_TOKEN.
     Never set: echo ${{ secrets.MYPASSWORD }} — it appears in YAML plaintext.
     DO: pass to env: and use the env var in your script.

  3. CONTEXT VARIABLES (${{ github.sha }}, ${{ github.ref }}, etc.)
     Provided by GitHub for every run. No setup needed.
     MOST USEFUL ONES:
       ${{ github.sha }}       full commit hash (40 chars)
       ${{ github.ref }}       branch/tag ref (refs/heads/main)
       ${{ github.actor }}     who triggered the run (username)
       ${{ github.event_name }} push, pull_request, schedule, etc.
       ${{ runner.os }}        Linux, macOS, Windows

  SECURITY RULES:
    Never print a secret directly: echo ${{ secrets.X }}
    Never write a secret to a file that gets uploaded as an artifact
    Never pass secrets between jobs via artifacts (use environment scoping)
    GitHub masks secrets in logs automatically — but only exact matches
""")


# ============================================================
# 7. MATRIX BUILDS — TEST MULTIPLE VERSIONS IN PARALLEL
# ============================================================

section("7. MATRIX BUILDS — TEST MULTIPLE PYTHON VERSIONS")

print("""
  Matrix strategy runs the SAME job with DIFFERENT configurations.
  Most common use: test against multiple Python versions simultaneously.
  Instead of 3 separate jobs, you write one job with a matrix.
""")

matrix_yaml = """
jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']  # Run job 3 times
      fail-fast: false   # Don't cancel all runs if one fails

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}  # Use matrix value

      - name: Install and test
        run: |
          pip install -r requirements-dev.txt
          pytest tests/ -v
"""

explain_yaml(matrix_yaml, """
  WHAT THIS CREATES:
    Job 1: test (python-version: '3.10')  → runs in parallel
    Job 2: test (python-version: '3.11')  → runs in parallel
    Job 3: test (python-version: '3.12')  → runs in parallel

  All three run simultaneously. Total time = max(one run), not sum.

  fail-fast: false
    Without this: if Python 3.10 tests fail, GitHub cancels 3.11 and 3.12.
    With fail-fast: false: all three run to completion.
    This gives you the full picture: "3.10 fails, 3.11 and 3.12 pass."

  MULTI-DIMENSIONAL MATRIX:
    matrix:
      python-version: ['3.10', '3.11', '3.12']
      os: [ubuntu-latest, macos-latest]
    → Creates 6 jobs: every combination of Python x OS.

  MATRIX EXCLUSIONS (exclude specific combinations):
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
        os: [ubuntu-latest, windows-latest]
        exclude:
          - python-version: '3.10'
            os: windows-latest    # Skip this specific combo

  DATA ENGINEER USE CASE:
    Test your pandas transforms against pandas 1.x and 2.x.
    (df.append() was removed in 2.x — matrix catches breakage.)
    matrix:
      pandas-version: ['1.5.3', '2.1.4']
""")


# ============================================================
# 8. READING CI RESULTS IN GITHUB UI
# ============================================================

section("8. READING CI RESULTS IN THE GITHUB UI")

print("""
  When you push or open a PR, here's what to look at:

  ON A PULL REQUEST:
  ──────────────────
  1. Scroll to the bottom of the PR.
  2. You'll see "Checks" section with green ✓ or red ✗ per job.
  3. Click on a failing check to see details.
  4. Click "Details" to open the full log.

  IN THE ACTIONS TAB:
  ───────────────────
  1. Click "Actions" in the top nav of your GitHub repo.
  2. Left sidebar: filter by workflow.
  3. Click a workflow run to see all jobs.
  4. Click a job to see all steps.
  5. Click a step to see its full output.

  READING A FAILING LOG:
  ──────────────────────
  1. Red X on a step = that step's command exited with non-zero code.
  2. Expand the step to see the error output.
  3. Look for: "FAILED", "Error:", "exit code 1", assertion errors.
  4. Common patterns:
     - "No module named X" → missing from requirements.txt
     - "ImportError" → dependency version mismatch
     - "AssertionError" → test failure (shows which test + expected vs actual)
     - "Permission denied" → file permission issue (rare in Actions)

  BRANCH PROTECTION RULES:
  ─────────────────────────
  Set in: repo Settings → Branches → Branch protection rules
  Check: "Require status checks to pass before merging"
  Then select: your CI job names (e.g., "test", "lint")
  Effect: the Merge button is DISABLED until CI passes.
  This makes CI mandatory — nobody can bypass it.

  BUILD STATUS BADGE — add to your README:
""")

badge_example = """
  # In your README.md — shows green/red CI status:
  ![CI](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)

  # For a specific branch:
  ![CI](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg?branch=main)
"""

print(badge_example)


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — GitHub Actions Fundamentals")
print("=" * 70)
print("""
  WORKFLOW STRUCTURE:
    name: ...            display name in GitHub UI
    on: ...              triggers (push, pull_request, schedule, workflow_dispatch)
    jobs:                one or more jobs
      job-id:
        runs-on: ubuntu-latest
        needs: [other-job]   wait for another job
        if: condition        conditional execution
        steps:
          - uses: action@v4  run a reusable action
          - name: label      optional label
            run: command     run a shell command

  KEY TRIGGERS:
    push: branches: [main]
    pull_request: branches: [main]
    schedule: - cron: '0 2 * * *'
    workflow_dispatch:
    push: paths: ['pipelines/**']

  ESSENTIAL ACTIONS:
    actions/checkout@v4          always first
    actions/setup-python@v5      install Python
    actions/cache@v3             cache pip deps (big speedup)
    actions/upload-artifact@v4   save files for later
    docker/build-push-action@v5  build + push Docker image
    aws-actions/configure-aws-credentials@v4  auth to AWS

  CONTEXT VARIABLES:
    ${{ github.sha }}     commit hash
    ${{ github.ref }}     branch/tag ref
    ${{ github.actor }}   who triggered it
    ${{ runner.os }}      Linux / macOS / Windows
    ${{ secrets.NAME }}   repository secret

  MATRIX BUILDS:
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
      fail-fast: false

  CACHE KEY PATTERN (invalidates when requirements change):
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
""")
