"""
CI/CD with GitHub Actions — Practice Exercises
===============================================
7 exercises, from writing your first workflow to debugging and security review.

Each exercise is a SCENARIO you would encounter on a real data team.
Work through the TASKS before reading the SOLUTION.

GitHub Actions workflows run in GitHub's cloud — you cannot run them locally.
For each exercise, write the YAML (or identify the issue), then verify
by reading the solution and comparing your answer.

Run this file: python3 practice/exercises.py
This prints all exercises, hints, and solutions.
"""

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def exercise(number, title, scenario, tasks, hint, solution):
    section(f"EXERCISE {number}: {title}")
    print(f"\n  SCENARIO:\n  {scenario}\n")
    print("  TASKS:")
    for i, task in enumerate(tasks, 1):
        print(f"    {i}. {task}")
    print(f"\n  HINT:\n  {hint}")
    print("\n  SOLUTION:")
    for line in solution.strip().splitlines():
        print(f"  {line}")


# ============================================================
# EXERCISE 1 — Write Your First Workflow
# ============================================================

exercise(
    number=1,
    title="Write Your First Workflow",
    scenario=(
        "You just joined a data team. Their main ETL pipeline lives in a "
        "GitHub repo at org/etl-pipeline. There is no CI — developers push "
        "directly to main and hope for the best. Last week a broken import "
        "crashed the pipeline. Your job: add basic CI."
    ),
    tasks=[
        "Create a workflow file at the correct path (.github/workflows/ci.yml).",
        "Trigger on push and pull_request to main branch.",
        "Use a single job named 'test' that runs on ubuntu-latest.",
        "Steps: checkout code, setup Python 3.11, install requirements-dev.txt, run pytest tests/ -v.",
        "Name each step descriptively.",
    ],
    hint=(
        "The workflow needs: name, on (with push and pull_request), jobs with a "
        "test job, runs-on: ubuntu-latest, and four steps using uses: and run:."
    ),
    solution="""
# SOLUTION: .github/workflows/ci.yml

name: Pipeline CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v

# KEY CONCEPTS:
# - actions/checkout@v4 is ALWAYS the first step
# - actions/setup-python@v5 handles Python installation
# - steps run sequentially; one failure stops the rest
# - This creates a green/red check on every PR
""",
)


# ============================================================
# EXERCISE 2 — Add Service Container
# ============================================================

exercise(
    number=2,
    title="Add a Postgres Service Container for Integration Tests",
    scenario=(
        "Your ETL pipeline writes data to Postgres. The unit tests mock the DB. "
        "Your tech lead says: 'Mocks lie — we need real integration tests.' "
        "She wants a Postgres 15 database running in CI so tests connect to a "
        "real database. Extend your Exercise 1 workflow to support this."
    ),
    tasks=[
        "Add a services: block to your test job with a Postgres 15 container.",
        "Configure POSTGRES_USER=testuser, POSTGRES_PASSWORD=testpass, POSTGRES_DB=testdb.",
        "Add a health check so GitHub waits until Postgres is ready.",
        "Pass the DATABASE_URL as an environment variable to the pytest step.",
        "Run: pytest tests/integration/ -v --tb=short (separate from unit tests).",
    ],
    hint=(
        "The services: block goes at the job level (same indent as steps:). "
        "The service name becomes the hostname. Ports: ['5432:5432']. "
        "Use options: for the health check with --health-cmd pg_isready."
    ),
    solution="""
# SOLUTION: .github/workflows/ci.yml (with integration tests)

name: Pipeline CI with Integration Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests]           # Only run if unit tests pass

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements-dev.txt
      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
        run: pytest tests/integration/ -v --tb=short

# KEY CONCEPTS:
# - services: is at job level, parallel to steps:
# - health check prevents tests from starting before Postgres is ready
# - DATABASE_URL is passed as env var to the step that needs it
# - localhost:5432 works because of the ports: mapping
""",
)


# ============================================================
# EXERCISE 3 — Matrix Build
# ============================================================

exercise(
    number=3,
    title="Matrix Build — Test Against Python 3.10, 3.11, 3.12",
    scenario=(
        "Your pipeline library is published internally and used by teams running "
        "different Python versions. It must work on 3.10, 3.11, and 3.12. "
        "Currently CI only tests on 3.11. Write a matrix build that tests all "
        "three versions simultaneously and doesn't cancel all runs if one fails."
    ),
    tasks=[
        "Add a strategy.matrix block to define python-version as a list of three versions.",
        "Reference the matrix value in the setup-python step.",
        "Set fail-fast: false so all three versions always run to completion.",
        "Make the job name show which Python version is running.",
    ],
    hint=(
        "Use strategy: matrix: python-version: [...] with fail-fast: false. "
        "Reference the value with ${{ matrix.python-version }}. "
        "Job name can use ${{ matrix.python-version }} for clarity."
    ),
    solution="""
# SOLUTION: Matrix build across Python versions

name: Matrix Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test Python ${{ matrix.python-version }}
    runs-on: ubuntu-latest

    strategy:
      fail-fast: false                    # All versions always complete
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v --tb=short

# RESULT: GitHub runs 3 parallel jobs:
#   Test Python 3.10  (ubuntu-latest)
#   Test Python 3.11  (ubuntu-latest)
#   Test Python 3.12  (ubuntu-latest)
#
# fail-fast: false means if 3.10 fails, 3.11 and 3.12 still complete.
# You see: "3.10 fails, 3.11 passes, 3.12 passes" — full picture.
# Without it you'd only know 3.10 failed, not whether 3.11 and 3.12 work.
""",
)


# ============================================================
# EXERCISE 4 — Add Caching
# ============================================================

exercise(
    number=4,
    title="Add pip Caching to Speed Up CI",
    scenario=(
        "Your CI job takes 3 minutes: 90 seconds is just pip install. "
        "The team pushes 30 times a day. That's 45 minutes/day wasted on "
        "downloading the same packages. Add pip caching to bring install "
        "time down to ~5 seconds on cache hit."
    ),
    tasks=[
        "Add a cache step BEFORE the pip install step.",
        "Cache the ~/.cache/pip directory.",
        "Use a cache key that includes the OS and a hash of all requirements*.txt files.",
        "Add restore-keys as a fallback for partial cache hits.",
        "Explain in a comment: when does the cache invalidate?",
    ],
    hint=(
        "Use actions/cache@v3. The key should be: "
        "${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}. "
        "restore-keys is the prefix: ${{ runner.os }}-pip-. "
        "The cache invalidates when requirements*.txt content changes."
    ),
    solution="""
# SOLUTION: Adding pip caching

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      # CACHE STEP — must come BEFORE pip install
      - name: Cache pip dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          # Cache key: OS + hash of all requirements files
          # Cache INVALIDATES when any requirements*.txt changes
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: pip install -r requirements-dev.txt
        # CACHE HIT:  packages already in ~/.cache/pip → ~5 seconds
        # CACHE MISS: packages downloaded fresh, then cached → ~90 seconds

      - run: pytest tests/ -v

# HOW CACHING WORKS:
#   1. GitHub computes: SHA256(all requirements*.txt files)
#   2. Looks for a cache with key "Linux-pip-<that hash>"
#   3. Cache HIT: restores ~/.cache/pip → pip finds packages → fast install
#   4. Cache MISS: fresh install, then saves ~/.cache/pip as new cache entry
#
# CACHE INVALIDATION:
#   - Add a new package to requirements.txt → hash changes → cache miss
#   - Update a version pin → hash changes → cache miss
#   - Documentation-only commit → hash unchanged → cache hit
#
# restore-keys: fallback partial match:
#   Even after adding one package, the old cache is restored first.
#   pip only downloads the new package, not everything.
#   Much faster than a full miss.
""",
)


# ============================================================
# EXERCISE 5 — Deployment Workflow
# ============================================================

exercise(
    number=5,
    title="Write a Deployment Workflow — Build Docker Image on Main Push",
    scenario=(
        "Your pipeline now passes CI. The next step: automated deployment. "
        "On every merge to main, build a Docker image, tag it with the git SHA, "
        "and push it to Docker Hub. Only run on main branch pushes (not PRs). "
        "Use Docker Hub secrets. Add a Slack notification on failure."
    ),
    tasks=[
        "Trigger ONLY on push to main (not pull_request).",
        "Set up Docker Buildx and log in to Docker Hub using secrets.",
        "Build and push the image tagged with the full git SHA.",
        "Add a final step that sends a Slack notification only on failure.",
        "Use the correct secret names: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, SLACK_WEBHOOK_URL.",
    ],
    hint=(
        "Use docker/setup-buildx-action@v3, docker/login-action@v3, and "
        "docker/build-push-action@v5. Tag with ${{ github.sha }}. "
        "For the failure notification use if: failure() and curl to the Slack webhook."
    ),
    solution="""
# SOLUTION: .github/workflows/deploy.yml

name: Deploy Pipeline

on:
  push:
    branches: [main]              # Only on main branch merges, not PRs

jobs:
  build-and-push:
    name: Build and Push Docker Image
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKERHUB_USERNAME }}/my-pipeline:${{ github.sha }}
            ${{ secrets.DOCKERHUB_USERNAME }}/my-pipeline:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Notify Slack on failure
        if: failure()
        run: |
          curl -s -X POST -H 'Content-type: application/json' \\
            --data '{
              "text": "Deploy FAILED for ${{ github.repository }} @ ${{ github.sha }}. Logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            }' \\
            ${{ secrets.SLACK_WEBHOOK_URL }}

# KEY POINTS:
# - on: push: branches: [main]  (no pull_request trigger)
# - tagged with both :sha (precise) and :latest (convenience)
# - failure notification has the run URL for quick debugging
# - secrets are passed via with: and ${{ secrets.X }}, never hardcoded
""",
)


# ============================================================
# EXERCISE 6 — Workflow Debugging
# ============================================================

exercise(
    number=6,
    title="Workflow Debugging — Find and Fix All the Bugs",
    scenario=(
        "A junior engineer wrote the following CI workflow. It has 5 bugs "
        "— some cause failures, some are security issues, some are inefficiencies. "
        "Find all 5 bugs and explain why each one is wrong."
    ),
    tasks=[
        "Read the broken workflow below carefully.",
        "Identify all 5 bugs (some subtle, some obvious).",
        "Write the corrected version.",
        "Explain why each bug is a problem.",
    ],
    hint=(
        "Look for: missing checkout, wrong action version pin, checkout order, "
        "run before install, and an unnecessary echo of a secret."
    ),
    solution="""
# BROKEN WORKFLOW (do not use — has 5 bugs):
# ──────────────────────────────────────────────
# name: CI
# on:
#   push:
#     branches: [main]
#
# jobs:
#   test:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/setup-python@v5      BUG 1: no checkout step first!
#         with:
#           python-version: '3.11'
#
#       - name: Run tests                    BUG 2: running tests before install
#         run: pytest tests/ -v
#
#       - uses: actions/checkout@main        BUG 3: @main not @v4 (unstable)
#
#       - name: Install deps
#         run: pip install -r requirements-dev.txt
#
#       - name: Debug secret                 BUG 4: echoing a secret (leaked in logs)
#         run: echo "DB password is ${{ secrets.DB_PASSWORD }}"
#
#       - name: Run lint
#         run: ruff check
#                                            BUG 5: ruff check missing path argument

# CORRECTED WORKFLOW:
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4           # FIX 1: checkout FIRST, pinned to v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - name: Install dependencies          # FIX 2: install BEFORE running tests
        run: pip install -r requirements-dev.txt

      - name: Run lint
        run: ruff check .                   # FIX 5: . = current directory

      - name: Run tests
        run: pytest tests/ -v
                                            # FIX 4: removed the secret echo entirely

# BUG EXPLANATIONS:
# BUG 1: actions/checkout must be first. Without it, the VM has no code.
#         setup-python succeeds, but then pytest can't find tests/ (no code).
#
# BUG 2: pytest runs BEFORE pip install. No packages installed → ImportError.
#        Order must be: checkout → install → test.
#
# BUG 3: actions/checkout@main uses the latest commit on the main branch
#        of the actions repo. Could break without warning when they push changes.
#        ALWAYS use a pinned version tag like @v4.
#
# BUG 4: echo "${{ secrets.DB_PASSWORD }}" echoes the secret in workflow YAML.
#        Even though GitHub masks it in logs, this is bad practice.
#        GitHub can't mask substrings — partial values may be visible.
#        NEVER echo secrets. Never pass them as inline arguments.
#
# BUG 5: ruff check without a path is ambiguous and may not lint all files.
#        Always pass . for current directory: ruff check .
""",
)


# ============================================================
# EXERCISE 7 — Secrets Security Review
# ============================================================

exercise(
    number=7,
    title="Secrets Security Review — Fix All Security Issues",
    scenario=(
        "You're reviewing a colleague's deploy workflow before it merges. "
        "It has several security problems with how credentials are handled. "
        "Identify every issue and explain the correct approach for each."
    ),
    tasks=[
        "Read the insecure workflow below.",
        "Identify all security issues (there are 4).",
        "Write the corrected secure version.",
        "Explain the principle behind each fix.",
    ],
    hint=(
        "Look for: hardcoded credentials, secrets in run commands, secrets in "
        "repo-level secrets when they should be environment-scoped, and a secret "
        "being passed to an artifact."
    ),
    solution="""
# INSECURE WORKFLOW (do not use — has 4 security issues):
# ──────────────────────────────────────────────────────
# name: Deploy
# on:
#   push:
#     branches: [main]
#
# jobs:
#   deploy:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#
#       - name: Configure database          ISSUE 1: hardcoded credentials in YAML
#         run: |
#           python deploy.py \\
#             --db-url postgresql://admin:S3cr3tP@ss@prod.db.company.com:5432/prod \\
#             --api-key AKIAIOSFODNN7EXAMPLE123
#
#       - name: Show config for debugging   ISSUE 2: echoing secrets to logs
#         run: |
#           echo "Deploying with token: ${{ secrets.API_TOKEN }}"
#           echo "Database: ${{ secrets.PROD_DB_URL }}"
#
#       - name: Save config artifact        ISSUE 3: uploading file with secrets
#         run: |
#           echo "DB_URL=${{ secrets.PROD_DB_URL }}" > config.env
#           echo "API_KEY=${{ secrets.API_KEY }}" >> config.env
#         uses: actions/upload-artifact@v4
#         with: {name: config, path: config.env}
#
#       - name: Deploy                      ISSUE 4: prod secrets as repo secrets
#         env:
#           PROD_DB_URL: ${{ secrets.PROD_DB_URL }}
#         run: ./deploy.sh

# SECURE CORRECTED WORKFLOW:
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production       # FIX 4: use environment-scoped secrets

    steps:
      - uses: actions/checkout@v4

      - name: Deploy pipeline
        env:                      # FIX 1: pass secrets as env vars, not CLI args
          DATABASE_URL: ${{ secrets.PROD_DB_URL }}
          API_KEY: ${{ secrets.API_KEY }}
        run: |
          # FIX 2: never echo secrets — remove all debug echo statements
          # deploy.py reads DATABASE_URL and API_KEY from os.environ
          python deploy.py

      # FIX 3: removed the artifact step entirely
      # Never write secrets to files, never upload them as artifacts

# ISSUE EXPLANATIONS:
#
# ISSUE 1: Hardcoded credentials in YAML
#   The YAML file is committed to git history — FOREVER.
#   Even if you later remove the credentials, they're in git log.
#   Anyone with read access to the repo (now or in the future) can see them.
#   FIX: Use GitHub Secrets. Rotate the exposed credentials immediately.
#   Reference secrets as env vars: env: DB_URL: ${{ secrets.DB_URL }}
#
# ISSUE 2: Echoing secrets in log output
#   echo "${{ secrets.API_TOKEN }}" → GitHub masks this in the log display.
#   But: multi-line secrets, URL-encoded values, base64 encoded values
#   may not be masked correctly. This is a safety net, not a guarantee.
#   FIX: Remove all debug echo statements that involve secrets.
#   If you need to debug: echo "Secret length: ${#API_TOKEN}" (prints length only).
#
# ISSUE 3: Uploading secrets as artifacts
#   Artifacts are downloadable by anyone with read access to the GitHub repo.
#   Writing secrets to config.env and uploading it = credentials leak.
#   FIX: Never write secrets to files. Never upload files that contain secrets.
#   Pass secrets only as env vars that exist in memory, not on disk.
#
# ISSUE 4: Production secrets as repo-level secrets
#   Repo secrets are available to ALL jobs in ALL workflows.
#   A malicious workflow (from a fork PR) could potentially access them.
#   FIX: Use GitHub Environments (environment: production).
#   Environment secrets are only available to jobs that specify that environment.
#   Add required reviewers to the production environment for extra protection.
""",
)


print()
print("=" * 70)
print("  EXERCISES COMPLETE")
print("=" * 70)
print("""
  WHAT YOU PRACTICED:
    Exercise 1: Basic CI workflow structure (checkout, setup, install, test)
    Exercise 2: Service containers for real database integration tests
    Exercise 3: Matrix strategy to test multiple Python versions in parallel
    Exercise 4: pip caching with cache key invalidation strategy
    Exercise 5: Docker build and push deploy workflow on main merge
    Exercise 6: Debugging broken workflows (5 common bugs)
    Exercise 7: Security review — hardcoded creds, secret leaks, artifacts

  NEXT STEP:
    Apply these to the sample project in projects/sample_pipeline_with_ci/
    That project has a real working Makefile, CI workflow, and test suite.
    Run: cd projects/sample_pipeline_with_ci && make ci-local
""")
