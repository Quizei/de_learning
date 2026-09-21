"""
Testing and Linting in CI — Making Your Pipeline Bulletproof
=============================================================
"If it's not tested in CI, it's not tested."

Linting and testing locally is good. Linting and testing in CI on every
commit is non-negotiable. CI is the last line of defence before production.

This file covers:
- pytest in CI: basic, with coverage, with failure thresholds
- Service containers: run a real Postgres database in CI (no mocking!)
- Linting tools: ruff, black, mypy, sqlfluff
- Caching dependencies (2-3x speedup)
- Uploading artifacts: test results and coverage reports
- Fast-fail vs run-all strategies
- Security scanning: bandit and safety
- Build status badges
- A complete, realistic CI workflow for a data pipeline project

Run this file: python3 concepts/03_testing_and_linting_in_ci.py
CI workflows are printed and explained — they run in GitHub's cloud.
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
# 1. PYTEST IN CI
# ============================================================

section("1. PYTEST IN CI — BASIC TO ADVANCED")

print("""
  pytest is the standard Python test runner.
  Running it in CI is nearly identical to running it locally —
  the difference is the environment and the reporting.
""")

pytest_basic_yaml = """
- name: Run tests
  run: pytest tests/ -v --tb=short
"""

explain_yaml(pytest_basic_yaml, """
  -v (verbose): show each test name as it runs, not just dots.
  --tb=short:   shorter traceback on failure (full stack traces are noisy in CI).

  Other useful flags for CI:
    --tb=no       no traceback at all (only test names and PASSED/FAILED)
    -x            exit after first failure (fast-fail mode)
    -q            quiet mode (minimal output)
    --durations=10  show 10 slowest tests (find bottlenecks)
""")

pytest_coverage_yaml = """
- name: Run tests with coverage
  run: |
    pytest tests/ \\
      --cov=src \\
      --cov-report=xml \\
      --cov-report=term-missing \\
      --cov-fail-under=80 \\
      -v \\
      --tb=short
"""

explain_yaml(pytest_coverage_yaml, """
  COVERAGE FLAGS:
    --cov=src               measure coverage of everything in src/
    --cov-report=xml        write coverage.xml (for CI tools + SonarQube)
    --cov-report=term-missing  print which lines are NOT covered in terminal
    --cov-fail-under=80     FAIL the step if coverage < 80%

  This last flag is the enforcement mechanism.
  Without it: coverage is informational. With it: coverage is mandatory.
  Start at 70% and raise it as the team adds tests.

  Requires: pip install pytest-cov (add to requirements-dev.txt)

  WHERE TO SET THE THRESHOLD?
    Greenfield project: start at 70-75%
    Mature data project: aim for 85%+
    Pure transform functions: can reach 95%+ easily
    Avoid chasing 100% — I/O and error handling paths are hard to test
""")


# ============================================================
# 2. SERVICE CONTAINERS — THE KEY CONCEPT
# ============================================================

section("2. SERVICE CONTAINERS — TEST AGAINST A REAL DATABASE IN CI")

print("""
  This is the most powerful CI feature for data engineers.

  THE PROBLEM WITH MOCKING:
    Your pipeline has 200 lines of SQLAlchemy queries.
    You mock the database in tests. Tests pass.
    But your SQL has a syntax error. The mock doesn't care.
    Production fails. Mocks lied to you.

  THE SOLUTION — SERVICE CONTAINERS:
    GitHub Actions can run a Docker container (Postgres, MySQL, Redis)
    ALONGSIDE your test job, on the same virtual network.
    Your tests connect to a REAL database — no mocking.
    The container is destroyed when the job finishes. Clean every time.

  This is the approach for serious integration testing.
""")

postgres_service_yaml = """
jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:                              # Docker containers to run alongside
      postgres:                           # Service name (used as hostname!)
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_USER: testuser
          POSTGRES_DB: testdb
        ports:
          - 5432:5432                      # host_port:container_port
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
        run: pytest tests/integration/ -v --tb=short
"""

explain_yaml(postgres_service_yaml, """
  ANATOMY OF A SERVICE CONTAINER:

  services:
    postgres:                  Job-scoped container name.
                               "postgres" is also the HOSTNAME on the internal network.
                               Steps can reach it at localhost:5432 (via ports mapping)
                               OR at postgres:5432 (via service network).

  image: postgres:15           Official Docker Hub image. Pin the version!

  env: POSTGRES_PASSWORD/USER/DB
    These are the official postgres image's environment variables.
    They create a database with those credentials on startup.

  ports: - 5432:5432
    Maps port 5432 on the VM (localhost) to port 5432 in the container.
    Your test code connects to: localhost:5432

  options: --health-cmd pg_isready ...
    GitHub waits until pg_isready exits 0 before starting your steps.
    Without this: your tests might start before Postgres is ready → failure.
    --health-interval 10s: check every 10 seconds
    --health-retries 5:    try 5 times before declaring unhealthy

  env: DATABASE_URL: ...
    Pass the connection string to your tests via environment variable.
    Your test code reads: os.environ["DATABASE_URL"]
    In pytest: use a fixture that reads this env var.

  HOW TESTS USE IT (Python conftest.py):

    import os, pytest, sqlalchemy

    @pytest.fixture(scope="session")
    def db_engine():
        url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
        engine = sqlalchemy.create_engine(url)
        yield engine
        engine.dispose()

  OTHER USEFUL SERVICE CONTAINERS:
    Redis:
      image: redis:7
      ports: [6379:6379]

    MySQL:
      image: mysql:8
      env: {MYSQL_ROOT_PASSWORD: testpass, MYSQL_DATABASE: testdb}
      ports: [3306:3306]
      options: --health-cmd "mysqladmin ping" --health-interval 10s --health-retries 5

    LocalStack (AWS S3/SQS locally):
      image: localstack/localstack
      env: {SERVICES: s3,sqs}
      ports: [4566:4566]
""")


# ============================================================
# 3. LINTING AND FORMATTING
# ============================================================

section("3. LINTING AND FORMATTING — THE QUALITY GATE")

print("""
  Linting catches problems before tests run.
  Formatting enforces consistency so code reviews focus on logic, not style.
  These run in under 30 seconds — extremely fast feedback.
""")

linting_yaml = """
- name: Lint with ruff
  run: ruff check .

- name: Check formatting with black
  run: black --check .

- name: Type checking with mypy
  run: mypy src/
  continue-on-error: true           # Non-blocking — advisory only

- name: SQL linting (dbt models)
  run: sqlfluff lint dbt/models/ --dialect snowflake
  continue-on-error: true           # SQL style is advisory
"""

explain_yaml(linting_yaml, """
  TOOL BREAKDOWN:

  ruff check .
    Fastest Python linter available (written in Rust).
    Replaces: flake8, isort, pyupgrade, and more in one tool.
    Catches: unused imports, undefined names, bad style, security issues.
    Speed: ~10ms for a medium codebase. No excuses for skipping.
    Config in pyproject.toml:
      [tool.ruff]
      line-length = 100
      select = ["E", "F", "I", "UP"]  # error, pyflakes, isort, pyupgrade

  black --check .
    --check mode: doesn't FORMAT, just reports if any file needs formatting.
    Exit code 1 if any file isn't formatted → step fails → PR blocked.
    This enforces that all committed code is already formatted.
    No more "can you reformat this?" in code reviews.

  mypy src/
    Static type checker. Catches type errors before runtime.
    continue-on-error: true → advisory, not blocking.
    Why non-blocking? Type hints are often incomplete on legacy code.
    Start non-blocking, fix all errors, then make it blocking.

  sqlfluff lint dbt/models/ --dialect snowflake
    SQL linter for dbt models. Enforces consistent SQL style.
    Dialects: snowflake, bigquery, spark, postgres, ansi, etc.
    Config in .sqlfluff:
      [sqlfluff]
      dialect = snowflake
      [sqlfluff:rules]
      max_line_length = 120
""")

print("""
  RECOMMENDED STEP ORDER (fastest feedback first):
    1. ruff check .          (seconds — fails fast on obvious issues)
    2. black --check .       (seconds)
    3. pytest unit tests     (fast — no I/O)
    4. pytest integration    (slower — needs DB)
    5. mypy / sqlfluff       (advisory)
""")


# ============================================================
# 4. CACHING DEPENDENCIES
# ============================================================

section("4. CACHING DEPENDENCIES — 2-3x FASTER CI")

print("""
  Without caching: pip installs ALL dependencies on every run.
  pandas + sqlalchemy + boto3 = ~90 seconds per job.

  With caching: first run installs and caches. Every subsequent run
  restores from cache in ~5 seconds.

  For a team pushing 20 times a day, this saves 20 * 85s = 28 minutes/day.
""")

cache_yaml = """
steps:
  - uses: actions/checkout@v4

  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'

  - name: Cache pip dependencies
    uses: actions/cache@v3
    id: cache-pip                         # ID lets you reference this step
    with:
      path: ~/.cache/pip                  # Where pip stores downloaded packages
      key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
      restore-keys: |
        ${{ runner.os }}-pip-

  - name: Install dependencies
    run: pip install -r requirements-dev.txt
    # If cache hit: packages already in ~/.cache/pip, install is fast
    # If cache miss: packages downloaded fresh, then cached for next run
"""

explain_yaml(cache_yaml, """
  CACHE KEY EXPLAINED:
    ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

    runner.os           = "Linux" (OS-specific caches are separate)
    pip                 = namespace (arbitrary label)
    hashFiles(...)      = SHA256 of all requirements files

    If requirements.txt changes → hash changes → cache miss → fresh install.
    If requirements.txt unchanged → same hash → cache hit → instant.

  RESTORE KEYS (fallback):
    restore-keys: |
      ${{ runner.os }}-pip-

    If exact key misses, try this partial key.
    Effect: even if you added a new package, you restore the OLD cache
    and only download the new package. Much faster than a full miss.

  PATH TO CACHE:
    ~/.cache/pip           Linux (ubuntu-latest)
    ~/Library/Caches/pip   macOS
    C:\\Users\\...\\pip     Windows
    Use ${{ runner.os }} to handle cross-platform if needed.

  ALSO CACHE:
    dbt packages:   path: ~/.dbt/packages
    node_modules:   path: node_modules, key: ...-${{ hashFiles('package-lock.json') }}
    pre-commit:     path: ~/.cache/pre-commit, key: ...-${{ hashFiles('.pre-commit-config.yaml') }}
""")


# ============================================================
# 5. UPLOADING ARTIFACTS
# ============================================================

section("5. UPLOADING ARTIFACTS — SAVE TEST RESULTS")

print("""
  Artifacts are files you save from a job.
  They appear as downloadable attachments on the workflow run.
  Useful for: coverage reports, test XML files, build outputs.
""")

artifacts_yaml = """
- name: Run tests with coverage
  run: |
    pytest tests/ \\
      --cov=src \\
      --cov-report=xml:coverage.xml \\
      --junitxml=test-results.xml \\
      -v

- name: Upload coverage report
  uses: actions/upload-artifact@v4
  if: always()                          # Upload even if tests fail
  with:
    name: coverage-report
    path: coverage.xml
    retention-days: 30

- name: Upload test results
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: test-results
    path: test-results.xml
    retention-days: 14
"""

explain_yaml(artifacts_yaml, """
  if: always()
    Upload EVEN IF the previous step (tests) failed.
    Without this: if tests fail, the upload step is skipped.
    You want the coverage/results report ESPECIALLY when tests fail!

  --junitxml=test-results.xml
    Standard XML format for test results. GitHub can parse this to
    show a test summary directly in the PR (with actions that support it).

  retention-days: 30
    GitHub keeps artifacts for 30 days then auto-deletes.
    Default is 90 days. Reduce to save storage quota.

  VIEWING ARTIFACTS:
    Go to the workflow run page → scroll to bottom → "Artifacts" section.
    Download the zip file.

  USING COVERAGE ARTIFACTS IN PR COMMENTS:
    Several marketplace actions can comment on PRs with coverage changes:
      - orgoro/coverage@v3
      - codecov/codecov-action@v3 (free for public repos)
""")


# ============================================================
# 6. FAST-FAIL VS RUN-ALL
# ============================================================

section("6. FAST-FAIL vs RUN-ALL — WHEN TO USE EACH")

print("""
  You have two choices when a step fails:
  stop immediately (fast-fail) or keep going and collect all failures.
""")

continue_on_error_yaml = """
steps:
  # CRITICAL — fail fast, block the PR
  - name: Lint (critical)
    run: ruff check .
    # No continue-on-error — default is stop on failure

  # CRITICAL — fail fast, block the PR
  - name: Tests (critical)
    run: pytest tests/ -v
    # No continue-on-error — default is stop on failure

  # ADVISORY — warn but don't block
  - name: Type check (advisory)
    run: mypy src/
    continue-on-error: true           # Step fails → job continues

  # ADVISORY — security info only
  - name: Security scan (advisory)
    run: bandit -r src/ -ll
    continue-on-error: true

  # CRITICAL — but upload results regardless
  - name: Upload coverage
    uses: actions/upload-artifact@v4
    if: always()                      # Run even if tests step failed
    with:
      name: coverage
      path: coverage.xml
"""

explain_yaml(continue_on_error_yaml, """
  DECISION FRAMEWORK:

  USE continue-on-error: true WHEN:
    - The check is advisory (type hints, SQL style, security warnings)
    - You're introducing a new check and have existing violations to fix
    - You want the information but don't want to block deploys yet
    - The tool is flaky/unreliable (rare but happens)

  DON'T USE continue-on-error WHEN:
    - Tests fail → broken code. Always block.
    - Linting fails → sloppy code. Always block.
    - Build fails → can't deploy. Always block.

  if: always() vs if: success() vs if: failure():
    if: always()    → run regardless of previous step result
    if: success()   → default behavior (run only if all previous steps passed)
    if: failure()   → run ONLY if a previous step failed
                      (useful for notifications: notify team on failure)

  EXAMPLE — notify on failure:
    - name: Notify Slack on failure
      if: failure()
      run: |
        curl -X POST -H 'Content-type: application/json' \\
          --data '{"text":"CI failed on ${{ github.ref }} by ${{ github.actor }}"}' \\
          ${{ secrets.SLACK_WEBHOOK_URL }}
""")


# ============================================================
# 7. SECURITY SCANNING IN CI
# ============================================================

section("7. SECURITY SCANNING — BANDIT AND SAFETY")

print("""
  Security scanning in CI gives you early warning about:
  - Python code with known security anti-patterns (bandit)
  - Dependencies with known CVEs (safety)

  These are advisory — set continue-on-error: true.
  You want the information. Don't block deploys over advisories.
  But DO review them regularly and patch critical CVEs.
""")

security_yaml = """
- name: Install security tools
  run: pip install bandit safety

- name: Python security scan (bandit)
  run: bandit -r src/ -ll --format txt
  continue-on-error: true
  # -ll = report LOW severity and above (use -iii for only HIGH)
  # -r  = recursive scan of src/ directory

- name: Dependency CVE check (safety)
  run: safety check --full-report
  continue-on-error: true
  # Checks installed packages against a CVE database
  # Reports known vulnerabilities with severity and fix versions
"""

explain_yaml(security_yaml, """
  BANDIT — Python security linter:
    Checks for common security issues in Python code:
    B101  use of assert (disabled by -S flag at runtime)
    B103  setting permissive file permissions
    B105  hardcoded password strings
    B106  hardcoded password as function argument
    B201  Flask app with debug=True
    B301  pickle deserializes arbitrary code (CVE risk)
    B501  requests with verify=False (disables SSL cert check)
    B602  subprocess with shell=True (command injection risk)

  DATA ENGINEER COMMON FINDINGS:
    - subprocess.run(cmd, shell=True) in pipeline scripts
    - hardcoded credentials in older scripts
    - requests.get(url, verify=False) for internal HTTPS endpoints

  SAFETY — dependency CVE scanner:
    Checks your installed packages against a database of known CVEs.
    Output format:
      Package    Installed  Affected  Description
      requests   2.28.0     <2.31.0   CVE-2023-XXXX: SSRF vulnerability
    Then you pin to the safe version: requests>=2.31.0

  SEMGREP (advanced — worth knowing):
    A more powerful static analysis tool.
    Has data-engineering specific rules (SQL injection patterns, etc.)
    GitHub has a free SEMGREP action:
      uses: semgrep/semgrep-action@v1
""")


# ============================================================
# 8. COMPLETE REALISTIC CI WORKFLOW
# ============================================================

section("8. COMPLETE REALISTIC CI WORKFLOW FOR A DATA PIPELINE")

print("""
  Here is a production-quality CI workflow that combines everything:
  lint + format + security + unit tests + integration tests + coverage.
""")

complete_ci_yaml = """
# .github/workflows/ci.yml
name: Data Pipeline CI

on:
  push:
    branches: [main]
    paths:
      - '**.py'
      - 'requirements*.txt'
      - '.github/workflows/ci.yml'
  pull_request:
    branches: [main]
    paths:
      - '**.py'
      - 'requirements*.txt'

jobs:
  # ── JOB 1: LINT AND FORMAT ─────────────────────────────
  lint:
    name: Lint and Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - name: Cache pip
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

      - run: pip install ruff black
      - run: ruff check .
      - run: black --check .

  # ── JOB 2: SECURITY SCAN (advisory) ────────────────────
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install bandit safety
      - run: bandit -r src/ -ll
        continue-on-error: true
      - run: safety check
        continue-on-error: true

  # ── JOB 3: UNIT TESTS ──────────────────────────────────
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: [lint]                         # Don't test if lint fails
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}

      - name: Cache pip
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

      - run: pip install -r requirements-dev.txt

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ \\
            --cov=src \\
            --cov-report=xml \\
            --cov-fail-under=70 \\
            -v --tb=short

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-report
          path: coverage.xml

  # ── JOB 4: INTEGRATION TESTS (with real Postgres) ──────
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: [unit-tests]

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_USER: testuser
          POSTGRES_DB: testdb
        ports: ['5432:5432']
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
"""

explain_yaml(complete_ci_yaml, """
  EXECUTION ORDER:
    lint ──────────────────────────────────────────► unit-tests ──► integration-tests
    security (runs in parallel with lint, advisory)

  WHY THIS STRUCTURE:
    - lint gates everything (no point running tests on unformatted code)
    - security runs in parallel (advisory, doesn't block)
    - unit tests need lint to pass (fast feedback on logic errors)
    - integration tests need unit tests (don't spin up Postgres if unit tests fail)

  TOTAL WALL-CLOCK TIME (estimated):
    lint: 30s
    security: 30s (parallel with lint)
    unit-tests: 60s (starts after lint)
    integration-tests: 90s (starts after unit-tests)
    TOTAL: ~3 minutes (vs 3.5 minutes sequential)

  HOW TO ADD THIS TO YOUR REPO:
    1. Create .github/workflows/ directory
    2. Save this as ci.yml
    3. Push to GitHub
    4. Actions tab shows the workflow immediately
    5. Set branch protection: require "Unit Tests" and "Lint" to pass
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — Testing and Linting in CI")
print("=" * 70)
print("""
  PYTEST FLAGS FOR CI:
    pytest tests/ -v --tb=short                    basic
    pytest --cov=src --cov-report=xml              with coverage XML
    pytest --cov-fail-under=80                     enforce 80% threshold
    pytest --junitxml=results.xml                  JUnit XML (for PR comments)
    pytest -x                                      stop on first failure

  LINTING COMMANDS:
    ruff check .                  fast Python linter
    black --check .               format check (don't auto-fix in CI)
    mypy src/                     type checking (usually advisory)
    sqlfluff lint dbt/ --dialect snowflake   SQL linting

  SERVICE CONTAINER PATTERN:
    services:
      postgres:
        image: postgres:15
        env: {POSTGRES_PASSWORD: testpass, POSTGRES_USER: testuser, POSTGRES_DB: testdb}
        ports: ['5432:5432']
        options: --health-cmd pg_isready --health-interval 10s --health-retries 5
    env:
      DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb

  CACHE PATTERN:
    uses: actions/cache@v3
    with:
      path: ~/.cache/pip
      key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

  SECURITY TOOLS:
    bandit -r src/ -ll            Python security linter
    safety check                  CVE check for dependencies

  ARTIFACT UPLOAD:
    uses: actions/upload-artifact@v4
    if: always()
    with: {name: coverage, path: coverage.xml, retention-days: 30}

  continue-on-error: true         advisory steps (security, mypy, sqlfluff)
  if: always()                    run even if previous step failed
  if: failure()                   only run on failure (Slack notifications)
""")
