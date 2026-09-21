"""
Project: Git Workflow Simulator
================================
A Python script that simulates a realistic data team git workflow
from scratch, using real subprocess git commands.

Watching this run gives you a visceral understanding of how branches,
merges, and tags work together — you see the actual git graph evolve
at each step.

WHAT IT SIMULATES:
  1. Initial commit on main (pipeline.py, README.md)
  2. Feature branch: feature/add-s3-loader (3 commits)
  3. Hotfix on main while feature is in progress
  4. Merge hotfix to main
  5. Merge feature branch to main (3-way merge)
  6. Tag the release v1.0.0
  7. Second feature with rebase workflow
  8. Final state: clean linear history

After each key step: prints the git graph so you see the branch structure evolve.

USAGE:
  python3 projects/git_workflow_simulator.py

OUTPUT:
  Walks through each step with explanations, live git output, and the graph.
  At the end: summary of what each step demonstrated.
"""

import os
import subprocess
import tempfile
import shutil
import sys


# ============================================================
# HELPERS
# ============================================================

def run(cmd, cwd):
    """Run a git command and return its output."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Data Engineer"
    env["GIT_AUTHOR_EMAIL"] = "de@datateam.com"
    env["GIT_COMMITTER_NAME"] = "Data Engineer"
    env["GIT_COMMITTER_EMAIL"] = "de@datateam.com"
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=env
    )
    return (result.stdout + result.stderr).strip()


def banner(text):
    """Print a step banner."""
    print()
    print()
    print("╔" + "═" * 68 + "╗")
    print(f"║  {text:<66}║")
    print("╚" + "═" * 68 + "╝")


def step(text):
    """Print a step label."""
    print(f"\n  ── {text}")


def cmd_out(cmd, cwd, note=""):
    """Run a command and print it with output."""
    print(f"\n  $ {cmd}")
    if note:
        print(f"  # {note}")
    output = run(cmd, cwd=cwd)
    if output:
        for line in output.splitlines()[:20]:
            print(f"    {line}")
    return output


def graph(cwd, label="Current graph"):
    """Print the git log graph."""
    print(f"\n  [{label}]")
    output = run("git log --oneline --graph --all --decorate", cwd=cwd)
    if output:
        for line in output.splitlines():
            print(f"    {line}")
    else:
        print("    (no commits yet)")


def write_file(cwd, filename, content):
    """Write a file to the repo directory."""
    filepath = os.path.join(cwd, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)


def commit(cwd, filename, content, message):
    """Write a file and create a commit."""
    write_file(cwd, filename, content)
    run(f"git add {filename}", cwd=cwd)
    run(f'git commit -m "{message}"', cwd=cwd)


def pause():
    """Pause between steps for readability."""
    print()


# ============================================================
# MAIN SIMULATION
# ============================================================

def run_simulation():

    # ── SETUP ────────────────────────────────────────────────────────────
    tmpdir = tempfile.mkdtemp(prefix="git_workflow_sim_")
    repo = tmpdir

    run("git init", cwd=repo)
    run("git config user.email 'de@datateam.com'", cwd=repo)
    run("git config user.name 'Data Engineer'", cwd=repo)

    print()
    print("=" * 70)
    print("  GIT WORKFLOW SIMULATOR — Data Team Scenario")
    print("=" * 70)
    print(f"""
  Simulating a realistic data team git workflow.
  Repo: {repo}

  Scenario:
    A data engineering team is building a pipeline to load users data
    to S3. Midway through the feature work, a production bug is reported.
    The team must hotfix while keeping the feature in progress, then
    complete the merge and ship a release.

  Watch the git graph evolve at each step.
""")
    input("  Press ENTER to start...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 1: Initial commit on main
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 1: Initialize the project on main")

    print("""
  Every project starts with an initial commit.
  We create the core files and establish the first snapshot.
""")

    step("Create pipeline.py")
    commit(
        repo,
        "pipeline.py",
        """# Data Pipeline — Users ETL
# Loads users data from Postgres → S3

def run():
    \"\"\"Main entry point for the users ETL pipeline.\"\"\"
    df = extract()
    df = transform(df)
    load(df)
    print("Pipeline complete.")

def extract():
    raise NotImplementedError("Extract not yet implemented")

def transform(df):
    return df

def load(df):
    raise NotImplementedError("Load not yet implemented")
""",
        "Initialize users ETL pipeline skeleton",
    )

    step("Create README.md")
    commit(
        repo,
        "README.md",
        """# Users ETL Pipeline

Loads users data from Postgres to S3 data lake.

## Status
Under active development.

## Usage
```bash
python3 pipeline.py
```
""",
        "Add project README",
    )

    # Rename default branch to main if needed
    run("git branch -m main 2>/dev/null || true", cwd=repo)

    graph(repo, "Initial state — two commits on main")

    print("""
  Result: main branch has 2 commits.
  This is the stable baseline everyone branches from.
""")
    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 2: Create feature branch
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 2: Engineer creates feature/add-s3-loader branch")

    print("""
  The engineer is tasked with implementing the S3 loader.
  They create a feature branch to isolate their work.
  Main stays untouched — this is trunk-based development.
""")

    cmd_out("git checkout -b feature/add-s3-loader", cwd=repo,
            note="Create branch AND switch to it")

    graph(repo, "Feature branch created (same commit as main)")

    print("""
  Notice: both 'main' and 'feature/add-s3-loader' point to the SAME commit.
  A branch is just a pointer — no code has moved.
""")

    step("First feature commit: S3 client setup")
    commit(
        repo,
        "s3_loader.py",
        """import boto3
import pandas as pd
from botocore.exceptions import ClientError

S3_CLIENT = None

def get_s3_client():
    \"\"\"Lazy-initialize S3 client.\"\"\"
    global S3_CLIENT
    if S3_CLIENT is None:
        S3_CLIENT = boto3.client('s3')
    return S3_CLIENT
""",
        "Add S3 client initialization with lazy loading",
    )

    step("Second feature commit: upload function")
    commit(
        repo,
        "s3_loader.py",
        """import boto3
import pandas as pd
from botocore.exceptions import ClientError
import io

S3_CLIENT = None

def get_s3_client():
    \"\"\"Lazy-initialize S3 client.\"\"\"
    global S3_CLIENT
    if S3_CLIENT is None:
        S3_CLIENT = boto3.client('s3')
    return S3_CLIENT

def upload_parquet(df, bucket, key):
    \"\"\"Upload a DataFrame to S3 as parquet.\"\"\"
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)
    get_s3_client().put_object(Bucket=bucket, Key=key, Body=buffer)
    print(f"Uploaded {len(df)} rows to s3://{bucket}/{key}")
""",
        "Add upload_parquet function to S3 loader",
    )

    step("Third feature commit: error handling")
    commit(
        repo,
        "s3_loader.py",
        """import boto3
import pandas as pd
from botocore.exceptions import ClientError
import io
import time

S3_CLIENT = None
MAX_RETRIES = 3

def get_s3_client():
    \"\"\"Lazy-initialize S3 client.\"\"\"
    global S3_CLIENT
    if S3_CLIENT is None:
        S3_CLIENT = boto3.client('s3')
    return S3_CLIENT

def upload_parquet(df, bucket, key, retries=MAX_RETRIES):
    \"\"\"Upload a DataFrame to S3 as parquet with exponential backoff retry.\"\"\"
    for attempt in range(retries):
        try:
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False)
            buffer.seek(0)
            get_s3_client().put_object(Bucket=bucket, Key=key, Body=buffer)
            print(f"Uploaded {len(df)} rows to s3://{bucket}/{key}")
            return
        except ClientError as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"Upload failed (attempt {attempt+1}/{retries}), retrying in {wait}s...")
            time.sleep(wait)
""",
        "Add retry logic with exponential backoff to S3 loader",
    )

    graph(repo, "After 3 feature commits")

    print("""
  The feature branch now has 3 commits ahead of main.
  Main is untouched — no risk to production.
  Feature work continues in isolation.
""")
    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 3: Hotfix while feature is in progress
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 3: PROD BUG — hotfix while feature is in progress")

    print("""
  10:47 AM: Slack alert fires.
  "Users pipeline failing with AttributeError: 'NoneType' has no attribute 'columns'"
  Root cause: transform() returns None when input is empty.

  The engineer can't push their half-done S3 loader.
  They must: switch to main, branch, fix, merge — NOW.
""")

    step("Switch back to main for the hotfix")
    cmd_out("git switch main", cwd=repo,
            note="Back to the clean, stable main branch")

    step("Create hotfix branch from main")
    cmd_out("git checkout -b hotfix/fix-null-transform-crash", cwd=repo)

    step("Apply the fix")
    commit(
        repo,
        "pipeline.py",
        """# Data Pipeline — Users ETL
# Loads users data from Postgres → S3

def run():
    \"\"\"Main entry point for the users ETL pipeline.\"\"\"
    df = extract()
    df = transform(df)
    if df is None or len(df) == 0:
        print("No data to load. Exiting.")
        return
    load(df)
    print(f"Pipeline complete. Loaded {len(df)} rows.")

def extract():
    raise NotImplementedError("Extract not yet implemented")

def transform(df):
    if df is None:
        return None
    # Guard against empty DataFrames
    if len(df) == 0:
        return df
    df = df.dropna(subset=['user_id'])
    df = df.drop_duplicates(subset=['user_id'])
    return df

def load(df):
    raise NotImplementedError("Load not yet implemented")
""",
        "Fix AttributeError crash when transform receives None or empty DataFrame",
    )

    graph(repo, "Hotfix branch created from main, fix committed")

    print("""
  The hotfix is isolated. Only the fix — nothing from the in-progress feature.
  This is why we branch: the hotfix can be reviewed and merged independently.
""")
    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 4: Merge hotfix to main
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 4: Merge hotfix to main → deploy fix")

    print("""
  After a quick review: "Looks good, approved."
  Merge the hotfix to main and deploy.
""")

    cmd_out("git switch main", cwd=repo)

    cmd_out("git merge hotfix/fix-null-transform-crash --no-ff",
            cwd=repo,
            note="--no-ff: force merge commit even though fast-forward is possible")

    graph(repo, "Hotfix merged to main (notice merge commit in graph)")

    step("Tag the hotfix release")
    cmd_out('git tag -a v0.1.1 -m "Hotfix: fix null transform crash"', cwd=repo)
    graph(repo, "After tagging v0.1.1")

    print("""
  Hotfix deployed. v0.1.1 tagged.
  Now delete the hotfix branch (it's merged, no longer needed):
""")
    cmd_out("git branch -d hotfix/fix-null-transform-crash", cwd=repo)

    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 5: Merge feature branch to main (three-way merge)
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 5: Merge feature/add-s3-loader into main")

    print("""
  The S3 loader feature is done and tested.
  Time to merge it. This is a three-way merge because BOTH branches
  have commits the other doesn't have:
    - main has: the hotfix commit
    - feature has: three S3 loader commits

  git needs to create a merge commit to bring them together.
""")

    graph(repo, "State before merging feature branch")

    cmd_out("git merge feature/add-s3-loader --no-ff",
            cwd=repo,
            note="Three-way merge: new merge commit brings both diverged branches together")

    graph(repo, "After merging feature/add-s3-loader")

    print("""
  See the diamond shape in the graph?
  That's the three-way merge:
    - The two branches diverged after the initial commits
    - The merge commit at the top ties them back together
    - Both the hotfix commit AND the 3 feature commits are in main's history
""")

    step("Delete merged feature branch")
    cmd_out("git branch -d feature/add-s3-loader", cwd=repo)

    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 6: Tag the release v1.0.0
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 6: Tag release v1.0.0")

    print("""
  The feature is merged and tested. Ship it.
  Create an annotated tag — it has a message, author, and date.
""")

    cmd_out('git tag -a v1.0.0 -m "Release v1.0.0: S3 loader with retry logic"', cwd=repo)

    cmd_out("git tag", cwd=repo, note="List all tags")

    cmd_out("git show v1.0.0", cwd=repo, note="Show tag details")

    graph(repo, "Final graph with v1.0.0 tag")

    print("""
  Tags are permanent bookmarks in history.
  Anyone can checkout v1.0.0 and get exactly this state, forever.
  In real teams: push tags with 'git push origin --tags'
""")
    input("  Press ENTER for next step...")


    # ════════════════════════════════════════════════════════════════════
    # STEP 7: Second feature with rebase workflow (clean history)
    # ════════════════════════════════════════════════════════════════════

    banner("STEP 7: Second feature — rebase workflow for clean history")

    print("""
  A new feature: add data quality checks.
  This time, we'll use the REBASE workflow instead of three-way merge.

  The rebase workflow:
    1. Branch from main
    2. Do feature work
    3. Before merging, rebase onto latest main (linear history)
    4. Fast-forward merge → no merge commit

  Result: perfectly linear history, easier to read with git log.
""")

    step("Create feature branch for quality checks")
    cmd_out("git checkout -b feature/add-quality-checks", cwd=repo)

    commit(
        repo,
        "quality.py",
        """def check_row_count(df, min_rows=1):
    \"\"\"Fail if DataFrame has fewer than min_rows rows.\"\"\"
    if len(df) < min_rows:
        raise ValueError(f"Expected >= {min_rows} rows, got {len(df)}")

def check_no_nulls(df, columns):
    \"\"\"Fail if any of the specified columns have null values.\"\"\"
    for col in columns:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise ValueError(f"Column '{col}' has {null_count} null values")
""",
        "Add row count and null check quality functions",
    )

    commit(
        repo,
        "quality.py",
        """def check_row_count(df, min_rows=1):
    \"\"\"Fail if DataFrame has fewer than min_rows rows.\"\"\"
    if len(df) < min_rows:
        raise ValueError(f"Expected >= {min_rows} rows, got {len(df)}")

def check_no_nulls(df, columns):
    \"\"\"Fail if any of the specified columns have null values.\"\"\"
    for col in columns:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise ValueError(f"Column '{col}' has {null_count} null values")

def check_uniqueness(df, column):
    \"\"\"Fail if column has duplicate values.\"\"\"
    dup_count = df[column].duplicated().sum()
    if dup_count > 0:
        raise ValueError(f"Column '{column}' has {dup_count} duplicate values")

def run_all_checks(df, key_column='user_id', required_columns=None):
    \"\"\"Run all quality checks. Raises on first failure.\"\"\"
    required_columns = required_columns or [key_column]
    check_row_count(df)
    check_no_nulls(df, required_columns)
    check_uniqueness(df, key_column)
    print(f"Quality checks passed: {len(df)} rows, no nulls, unique {key_column}")
""",
        "Add uniqueness check and run_all_checks helper",
    )

    graph(repo, "Feature branch with 2 commits, main unchanged")

    step("Add a commit to main while feature was being worked on (simulating team activity)")
    run("git switch main", cwd=repo)
    commit(
        repo,
        "config.py",
        """import os

# Database
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
DB_NAME = os.environ.get('DB_NAME', 'pipeline_db')

# S3
S3_BUCKET = os.environ.get('S3_BUCKET', 'data-lake-prod')
S3_REGION = os.environ.get('S3_REGION', 'us-east-1')
S3_PREFIX = os.environ.get('S3_PREFIX', 'users/')

# Pipeline
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 10000))
""",
        "Add centralized configuration module",
    )

    graph(repo, "Both main and feature have new commits — diverged")

    print("""
  main and feature/add-quality-checks have diverged.
  If we merge now: three-way merge with a merge commit.

  Instead, we'll REBASE: replay feature commits on top of latest main.
  This makes it look like we branched from the latest main all along.
""")

    cmd_out("git switch feature/add-quality-checks", cwd=repo)
    cmd_out("git rebase main", cwd=repo,
            note="Rebase: pick up feature commits, replay on top of latest main")

    graph(repo, "After rebase — feature sits cleanly on top of main")

    print("""
  The feature's commits now sit on TOP of the latest main commit.
  No merge commit needed. History is linear.
""")

    cmd_out("git switch main", cwd=repo)
    cmd_out("git merge feature/add-quality-checks",
            cwd=repo,
            note="Fast-forward! No merge commit — just moves the main pointer.")

    graph(repo, "After fast-forward merge — perfectly linear history")

    cmd_out('git tag -a v1.1.0 -m "Release v1.1.0: Add data quality checks module"', cwd=repo)
    cmd_out("git branch -d feature/add-quality-checks", cwd=repo)

    input("  Press ENTER to see the final state...")


    # ════════════════════════════════════════════════════════════════════
    # FINAL STATE
    # ════════════════════════════════════════════════════════════════════

    banner("FINAL STATE — Complete workflow overview")

    print("""
  Here's the complete history of the project:
""")

    graph(repo, "Complete project history")

    print()
    print("  Full log with stats:")
    cmd_out("git log --oneline --stat", cwd=repo)

    print()
    print("  All tags:")
    cmd_out("git tag", cwd=repo)

    print()
    print("  Files in the project:")
    cmd_out("ls -la", cwd=repo)


    # ════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════════════════════

    print()
    print("=" * 70)
    print("  SIMULATION COMPLETE — What each step demonstrated")
    print("=" * 70)
    print("""
  STEP 1 — Initial commits on main
    Foundation: every branch starts from a stable baseline.
    Commit messages should be imperative and meaningful.

  STEP 2 — Feature branch (feature/add-s3-loader)
    Creating a branch costs nothing (it's a 40-byte pointer file).
    3 commits on the feature, main untouched.
    Real branches: feature/, bugfix/, refactor/, chore/ prefixes.

  STEP 3 — Hotfix while feature in progress
    This happens constantly on real teams.
    Switch to main, branch, fix, merge — feature work is safe on its branch.
    The feature branch didn't have the hotfix — that's expected.

  STEP 4 — Merge hotfix, tag v0.1.1
    --no-ff creates a merge commit documenting the hotfix was from a branch.
    Annotated tags (-a) mark release points permanently.
    Delete merged branches to keep branch list clean.

  STEP 5 — Three-way merge of feature branch
    Both branches had commits the other didn't → merge commit created.
    The diamond shape in git log --graph shows this visually.
    The full history of both branches is preserved.

  STEP 6 — Tag v1.0.0
    Official release marked in history.
    git push origin --tags to share with the team.

  STEP 7 — Rebase workflow
    Rebase replays feature commits on top of latest main.
    Result: linear history, no merge commits.
    Fast-forward merge afterwards is trivial.
    GOLDEN RULE: only rebase commits that haven't been pushed/shared.

  KEY INSIGHT:
    The SAME code ships whether you use merge commits or rebase.
    The difference is how the history reads.
    Most data teams use: squash-merge via GitHub PR for external features,
    and rebase for keeping local branches up to date.
""")

    # Cleanup
    shutil.rmtree(tmpdir)
    print(f"  (Cleaned up temp directory: {tmpdir})")
    print()
    print("  Read concepts/01_git_fundamentals.md for a hands-on walkthrough of each command.")
    print("  Run python3 practice/exercises.py to test your knowledge.")
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_simulation()
