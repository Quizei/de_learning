"""
CI/CD Concepts and Why It Matters — From Zero to Pipeline
==========================================================
"Stop merging once a week and praying."

Every team that skips CI/CD eventually hits "integration hell":
  - Monday: everyone merges their week of work
  - Tuesday morning: nothing works, nobody knows whose change broke it
  - Tuesday afternoon–Thursday: debugging instead of building
  - Friday: emergency hotfix to prod that somebody deployed manually

CI/CD solves this. Every commit triggers automated checks.
Problems are caught in minutes, not days, and you always know who caused them.

This file covers:
- The problem without CI/CD (integration hell)
- CI vs CD vs CD (three different things!)
- Why data engineers specifically need this
- The pipeline stages for a data project
- CI/CD platform comparison
- A Python simulation of a CI pipeline running locally

Run this file: python3 concepts/01_cicd_concepts_and_why_it_matters.py
No external dependencies needed — pure Python simulation.
"""

import time
import random

# ============================================================
# HELPERS
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def explain_yaml(yaml_str, notes=""):
    """Print a YAML block with explanation — used throughout CI/CD concepts."""
    print()
    print("  " + "-" * 66)
    for line in yaml_str.strip().splitlines():
        print(f"  {line}")
    print("  " + "-" * 66)
    if notes:
        print()
        for note in notes.strip().splitlines():
            print(f"  {note}")


# ============================================================
# 1. THE PROBLEM: INTEGRATION HELL
# ============================================================

section("1. THE PROBLEM: INTEGRATION HELL")

print("""
  Without CI, teams typically work in isolation for days or weeks,
  then merge everything at once. Here is what that week looks like:

  Monday:
    Alice finishes her feature branch (5 days of work).
    Bob finishes his feature branch (5 days of work).
    Carol finishes her bug fix branch (3 days of work).
    Everyone merges to main.

  Tuesday 9am:
    The build is broken. 47 test failures.
    Alice's schema change conflicts with Bob's query.
    Carol's fix assumed a column that Alice renamed.
    Nobody knows whose change caused what.

  Tuesday–Thursday:
    The team debugs instead of shipping.
    Nobody wants to merge again because last time was painful.

  Friday:
    A hotfix gets deployed manually, without tests, under pressure.
    "We'll add tests next sprint." (Spoiler: they won't.)

  This is integration hell. And it gets worse as the team grows.

  THE FIX — Integrate Continuously:
    Every push triggers automated checks.
    Problems surface in minutes, not days.
    You always know WHICH commit broke something.
    The fix is small (one commit) not large (a week of tangled changes).
""")


# ============================================================
# 2. CI vs CD vs CD — THREE DIFFERENT THINGS
# ============================================================

section("2. CI vs CD vs CD — THREE DIFFERENT THINGS")

print("""
  These three terms are often confused. They exist on a spectrum:

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                    │
  │  CI → Continuous Integration                                       │
  │    Merge frequently (multiple times per day).                      │
  │    Every commit triggers: lint → test → build.                     │
  │    Goal: "the main branch always builds and passes tests."         │
  │                                                                    │
  │  CD → Continuous Delivery                                          │
  │    Every commit that passes CI is READY to deploy.                 │
  │    Deployment is still manual (a human clicks a button).           │
  │    Goal: "we CAN deploy any commit, any time, in 5 minutes."       │
  │                                                                    │
  │  CD → Continuous Deployment                                        │
  │    Every commit that passes CI is automatically deployed.          │
  │    No human intervention needed.                                   │
  │    Goal: "50 deploys per day, all automated."                      │
  │                                                                    │
  └──────────────────────────────────────────────────────────────────┘

  commit → CI passes → [Delivery: human deploys] OR [Deployment: auto-deploys]

  Which one should you use?
    - Small team, data project, Airflow DAGs: Continuous Delivery is fine.
      A human reviewer approves the merge, then deploys.
    - Large team, customer-facing API: Continuous Deployment is powerful
      but requires excellent test coverage and rollback mechanisms.
    - Anything with a database schema migration: almost always keep
      Continuous Delivery — migrations need human review before prod.
""")


# ============================================================
# 3. WHY DATA ENGINEERS SPECIFICALLY NEED CI/CD
# ============================================================

section("3. WHY DATA ENGINEERS SPECIFICALLY NEED CI/CD")

print("""
  General software engineers have needed CI/CD for years.
  Data engineers resisted it — "it's just scripts, not a real app."
  This is wrong. Here is why data pipelines need CI/CD MORE, not less:

  PROBLEM 1: dbt model changes break downstream tables
  ─────────────────────────────────────────────────────
  You rename a column in staging.orders.
  Downstream model finance.monthly_revenue joins on that column.
  Finance dashboard breaks. Nobody noticed until the CFO called.

  CI FIX: dbt test + dbt compile runs on every PR.
  Broken refs are caught before merge.

    # In CI, run:
    dbt deps && dbt compile && dbt test --select state:modified+

  PROBLEM 2: Schema changes break dependent pipelines
  ─────────────────────────────────────────────────────
  The payments team adds a NOT NULL constraint to a column
  your pipeline has been writing NULL values to for months.
  Next pipeline run: crash.

  CI FIX: Integration tests with a real test database container.
  Schema changes are tested in CI before any migration runs in prod.

  PROBLEM 3: Python dependency updates break transforms
  ─────────────────────────────────────────────────────
  Someone updates pandas from 1.x to 2.x.
  df.append() is removed in pandas 2.x. Your transforms use it.
  Prod pipeline crashes on Monday morning.

  CI FIX: requirements.txt is pinned. CI runs tests on every dep change.
  Test suite catches the broken .append() calls before deployment.

  PROBLEM 4: Untested code deploys to prod Airflow
  ─────────────────────────────────────────────────
  A new DAG is pushed directly to prod without review.
  It has a syntax error. Airflow fails to import the DAG.
  ALL other DAGs in the same file also fail to load.

  CI FIX: DAG validation in CI:
    python -c "from dags import my_dag" — catches syntax errors
    pytest tests/dags/ — catches logic errors
    Only merged PRs (that passed CI) can deploy.

  PROBLEM 5: Nobody knows what prod is running
  ─────────────────────────────────────────────
  Six engineers all deployed to prod manually at different times.
  What version is running? Nobody knows. The git log doesn't match.

  CI/CD FIX: Only CI deploys. Every deploy is a git commit.
  Git log IS the deployment history. Rollback = git revert.
""")


# ============================================================
# 4. THE PIPELINE STAGES FOR A DATA PROJECT
# ============================================================

section("4. THE PIPELINE STAGES FOR A DATA PROJECT")

print("""
  Every push to a data project should run through these stages in order.
  A failure in any stage stops the pipeline — no point testing if lint fails.

  STAGE 1 — LINT & FORMAT
  ────────────────────────
  Fast. Runs in seconds. Catches style and syntax issues.

    ruff check .              Fast Python linter (replaces flake8, isort)
    black --check .           Format checker (fails if code isn't formatted)
    sqlfluff lint dbt/        SQL linter for dbt models

  STAGE 2 — UNIT TESTS
  ──────────────────────
  Test pure Python logic with no external dependencies.
  Fast — runs in under a minute.

    pytest tests/unit/ -v --tb=short

  STAGE 3 — INTEGRATION TESTS
  ─────────────────────────────
  Test against a real database (Postgres, Snowflake emulator, etc.)
  Slower — may take 3-5 minutes.
  GitHub Actions can spin up a Postgres container for you.

    pytest tests/integration/ -v

  STAGE 4 — BUILD DOCKER IMAGE
  ─────────────────────────────
  Build the container image to verify it compiles.
  Tag it with the git SHA so every image is traceable to a commit.

    docker build -t my-pipeline:$GIT_SHA .

  STAGE 5 — DEPLOY
  ─────────────────
  Only runs on merge to main.
  Push Docker image to registry, update Airflow, deploy to ECS, etc.
  May require human approval (Continuous Delivery) or be automatic.

  ┌────────────────────────────────────────────────────────────────────┐
  │  git push                                                           │
  │      │                                                              │
  │      ▼                                                              │
  │  [LINT]──fail──► PR blocked, developer fixes and pushes again       │
  │      │ pass                                                         │
  │      ▼                                                              │
  │  [UNIT TESTS]──fail──► PR blocked                                   │
  │      │ pass                                                         │
  │      ▼                                                              │
  │  [INTEGRATION TESTS]──fail──► PR blocked                            │
  │      │ pass                                                         │
  │      ▼                                                              │
  │  [BUILD IMAGE]──fail──► PR blocked                                  │
  │      │ pass (only on main merge)                                    │
  │      ▼                                                              │
  │  [DEPLOY]──► Staging first, then prod                               │
  └────────────────────────────────────────────────────────────────────┘
""")


# ============================================================
# 5. CI/CD PLATFORM COMPARISON
# ============================================================

section("5. CI/CD PLATFORM COMPARISON")

print("""
  PLATFORM COMPARISON:
  ┌──────────────────┬──────────────────────────────────────────────────┐
  │ Platform          │ Best for                                          │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ GitHub Actions    │ Code on GitHub. YAML in .github/workflows/.       │
  │                   │ Free for public repos, generous free tier.        │
  │                   │ Marketplace of 10,000+ reusable actions.          │
  │                   │ Native integration with GitHub PRs and secrets.   │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ GitLab CI         │ Code on GitLab (self-hosted or cloud).            │
  │                   │ gitlab-ci.yml in repo root.                       │
  │                   │ More built-in features (registry, environments).  │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ Jenkins           │ Legacy enterprise. Maximum customization.         │
  │                   │ High operational cost — you run the servers.      │
  │                   │ Groovy-based Jenkinsfile. Powerful but complex.   │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ CircleCI          │ Good for complex workflows. Orbs (reusable        │
  │                   │ config). Pay-per-minute after free tier.          │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ Buildkite         │ Enterprise. Runs on your own infra (agents).      │
  │                   │ Great for large data teams with compliance needs. │
  └──────────────────┴──────────────────────────────────────────────────┘

  WHY WE USE GITHUB ACTIONS IN THIS COURSE:
  - If your code is on GitHub, it's the obvious choice
  - Zero infrastructure to manage — GitHub runs the VMs
  - Tight integration: CI results appear directly on PRs
  - Free 2,000 minutes/month for private repos
  - The workflow file lives in your repo — versioned with your code
""")


# ============================================================
# 6. SIMULATING A CI PIPELINE IN PYTHON
# ============================================================

section("6. SIMULATING A CI PIPELINE IN PYTHON")

print("""
  GitHub Actions can't run locally — it runs in GitHub's cloud.
  But we can simulate the LOGIC of a CI pipeline right here.

  This simulation shows:
  - Pipeline stages executing in order
  - How a failure in one stage blocks subsequent stages
  - "Fast fail" vs "run all checks" modes
  - What a CI run looks and feels like
""")

class PipelineStage:
    """Represents a single stage in a CI pipeline."""

    def __init__(self, name: str, command: str, critical: bool = True):
        self.name = name
        self.command = command
        self.critical = critical  # if False, failure doesn't block pipeline
        self.status = None        # "pass", "fail", "skipped"
        self.duration_ms = 0

    def run(self, force_result=None) -> bool:
        """Simulate running the stage. Returns True if passed."""
        start = time.time()
        print(f"\n  [{self.name}]  $ {self.command}")

        # Simulate some work
        time.sleep(0.05)

        if force_result is not None:
            passed = force_result
        else:
            # In real CI: run the actual command, check exit code
            passed = True  # default: pass for demo

        self.duration_ms = int((time.time() - start) * 1000)

        if passed:
            self.status = "pass"
            print(f"  ✓ PASSED  ({self.duration_ms}ms)")
        else:
            self.status = "fail"
            print(f"  ✗ FAILED  ({self.duration_ms}ms)")
            if not self.critical:
                print(f"  ! Non-critical — pipeline continues")

        return passed


class CIPipeline:
    """Simulates a CI pipeline with configurable stages."""

    def __init__(self, name: str, fast_fail: bool = True):
        self.name = name
        self.fast_fail = fast_fail
        self.stages: list[PipelineStage] = []
        self.results: dict[str, str] = {}

    def add_stage(self, stage: PipelineStage):
        self.stages.append(stage)

    def run(self, stage_results: dict[str, bool] = None) -> bool:
        """
        Run the pipeline.
        stage_results: dict of {stage_name: True/False} to simulate pass/fail.
        """
        stage_results = stage_results or {}
        overall_pass = True

        print(f"\n  Pipeline: {self.name}")
        print(f"  Mode: {'fast-fail (stop on first critical failure)' if self.fast_fail else 'run-all (collect all failures)'}")
        print(f"  Stages: {len(self.stages)}")
        print()

        blocked = False

        for stage in self.stages:
            if blocked:
                stage.status = "skipped"
                print(f"\n  [{stage.name}]  SKIPPED (previous stage failed)")
                self.results[stage.name] = "skipped"
                continue

            force_result = stage_results.get(stage.name, None)
            passed = stage.run(force_result=force_result)
            self.results[stage.name] = stage.status

            if not passed:
                overall_pass = False
                if stage.critical and self.fast_fail:
                    blocked = True

        print()
        print("  " + "-" * 50)
        print(f"  PIPELINE RESULT: {'PASSED' if overall_pass else 'FAILED'}")
        print("  " + "-" * 50)

        for stage in self.stages:
            icon = {"pass": "✓", "fail": "✗", "skipped": "○"}.get(stage.status, "?")
            crit_label = "" if stage.critical else " (non-critical)"
            print(f"  {icon} {stage.name}{crit_label}")

        return overall_pass


# Demo 1: All stages pass — a clean push
print("\n  DEMO 1: Clean push — all stages pass")
print("  " + "=" * 50)

pipeline = CIPipeline("data-pipeline CI", fast_fail=True)
pipeline.add_stage(PipelineStage("lint",         "ruff check . && black --check ."))
pipeline.add_stage(PipelineStage("unit-tests",   "pytest tests/unit/ -v"))
pipeline.add_stage(PipelineStage("integ-tests",  "pytest tests/integration/ -v"))
pipeline.add_stage(PipelineStage("build",        "docker build -t pipeline:$SHA ."))
pipeline.add_stage(PipelineStage("deploy",       "kubectl apply -f k8s/"))

pipeline.run()


# Demo 2: Lint fails — shows fast-fail blocking subsequent stages
print("\n\n  DEMO 2: Lint fails — fast-fail blocks all subsequent stages")
print("  " + "=" * 50)

pipeline2 = CIPipeline("data-pipeline CI (lint failure)", fast_fail=True)
pipeline2.add_stage(PipelineStage("lint",         "ruff check . && black --check ."))
pipeline2.add_stage(PipelineStage("unit-tests",   "pytest tests/unit/ -v"))
pipeline2.add_stage(PipelineStage("integ-tests",  "pytest tests/integration/ -v"))
pipeline2.add_stage(PipelineStage("build",        "docker build -t pipeline:$SHA ."))
pipeline2.add_stage(PipelineStage("deploy",       "kubectl apply -f k8s/"))

pipeline2.run(stage_results={"lint": False})


# Demo 3: Non-critical stage fails — security scan warns but doesn't block
print("\n\n  DEMO 3: Security scan fails (non-critical) — pipeline continues")
print("  " + "=" * 50)

pipeline3 = CIPipeline("data-pipeline CI (security warning)", fast_fail=True)
pipeline3.add_stage(PipelineStage("lint",         "ruff check . && black --check ."))
pipeline3.add_stage(PipelineStage("unit-tests",   "pytest tests/unit/ -v"))
pipeline3.add_stage(PipelineStage("security",     "bandit -r src/ && safety check",
                                                   critical=False))
pipeline3.add_stage(PipelineStage("build",        "docker build -t pipeline:$SHA ."))
pipeline3.add_stage(PipelineStage("deploy",       "kubectl apply -f k8s/"))

pipeline3.run(stage_results={"security": False})

print("""

  KEY INSIGHT — FAST FAIL vs RUN ALL:

  Fast-fail (default):
    First critical failure stops the pipeline.
    PRO: Feedback is immediate. No point testing if lint fails.
    CON: You only see one problem at a time.

  Run-all:
    All stages run regardless of failures.
    PRO: See every problem in one run.
    CON: Wastes CI minutes. Lint failure makes test results misleading.

  RECOMMENDATION FOR DATA TEAMS:
    Fast-fail for critical stages (lint, tests, build).
    Non-critical for advisory checks (security scan, type hints).
    This way: you ALWAYS get the most important feedback first,
    AND you still collect advisory warnings.
""")


# ============================================================
# QUICK REFERENCE
# ============================================================

print()
print("=" * 70)
print("  QUICK REFERENCE — CI/CD Concepts")
print("=" * 70)
print("""
  DEFINITIONS:
    CI  = Continuous Integration: merge often, run checks on every commit
    CD  = Continuous Delivery: every passing commit is deployable (human deploys)
    CD  = Continuous Deployment: every passing commit auto-deploys

  THE PIPELINE STAGES (in order):
    1. lint        ruff check . && black --check . && sqlfluff lint dbt/
    2. unit tests  pytest tests/unit/ -v --tb=short
    3. integ tests pytest tests/integration/ (needs real DB container)
    4. build       docker build -t image:$SHA .
    5. deploy      only on main merge — to staging first, then prod

  WHY DATA ENGINEERS NEED CI/CD:
    - dbt renames break downstream models
    - Schema changes break pipeline inserts
    - Dep updates break transforms (pandas 2.x removed df.append())
    - Manual prod deploys → nobody knows what's running
    - Untested DAGs crash Airflow and take down neighboring DAGs

  PLATFORM CHOICE:
    Code on GitHub → GitHub Actions (covered in this course)
    Code on GitLab → GitLab CI
    Enterprise on-prem → Jenkins or Buildkite

  FAST-FAIL RULE:
    Critical stages (tests, lint, build): fast-fail=True
    Advisory stages (security scan, type hints): critical=False
""")
