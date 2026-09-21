# .gitignore and Data Project Hygiene — Walkthrough

"Teammate pushed AWS keys to GitHub at 9pm. We got an email from AWS
security at 9:04. The keys had already been used."

This is the walkthrough that keeps that from happening to you. Type every
command yourself. Budget ~25 minutes.

## Setup — a realistic messy project

```bash
mkdir gitignore_demo && cd gitignore_demo
git init -b main
git config user.name "Your Name"
git config user.email "you@example.com"

mkdir -p pipelines tests data/raw data/processed dbt/models dbt/target \
         notebooks/.ipynb_checkpoints __pycache__ .venv/lib/python3.11/site-packages

echo "import pandas as pd" > pipeline.py
echo "import pytest" > tests/test_pipeline.py
echo "DB_PASSWORD=secret123
AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE" > .env
echo '{"type":"service_account","private_key":"-----BEGIN RSA"}' > credentials.json
echo "id,name,email
1,Alice,alice@test.com" > data/raw/users_2024_06_10.csv
echo "fake parquet bytes" > data/processed/users_clean.parquet
echo "SELECT * FROM raw.users" > dbt/models/users.sql
echo '{"results": []}' > dbt/target/run_results.json
echo "data_pipeline:
  target: dev
  outputs:
    dev:
      password: secret" > dbt/profiles.yml
echo '{"cells": [], "metadata": {}, "nbformat": 4}' > notebooks/analysis.ipynb
echo "checkpoint" > notebooks/.ipynb_checkpoints/analysis-checkpoint.ipynb
echo "fake bytecode" > __pycache__/pipeline.cpython-311.pyc
echo "fake package" > .venv/lib/python3.11/site-packages/requests/__init__.py 2>/dev/null || \
  { mkdir -p .venv/lib/python3.11/site-packages/requests && echo "fake package" > .venv/lib/python3.11/site-packages/requests/__init__.py; }
```

```bash
git status -s
```
**Checkpoint:** every single file shows as `??` (untracked) — including
`.env` and `credentials.json`. This is the state that leads to disaster:
nothing stops `git add .` from picking up secrets right now.

---

## 1. How `.gitignore` patterns work

```
*.pyc                 any file ending in .pyc, any directory
*.csv                 any .csv file
/dist/                dist/ at the repo root only
data/raw/             a data/raw/ directory anywhere
data/**/raw/          raw/ at any depth under data/
!data/raw/sample.csv  negate: track this one file even though data/raw/ is ignored
.env                  a file literally named .env
.env*                 .env, .env.local, .env.staging, ...
```
More specific rules beat general ones; a later line can override an
earlier one; `!` negation only works if the parent directory isn't already
ignored. A `.gitignore` in a subdirectory applies to that directory and
below; `~/.gitignore_global` (set via `git config --global core.excludesfile`)
applies to every repo on your machine.

---

## 2. Write a real .gitignore for a data project

Create `.gitignore` with this content:
```gitignore
# Python
__pycache__/
*.py[cod]
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
env/

# Credentials and secrets — CRITICAL
.env
.env.*
!.env.example        # DO include a template with no real values
*.pem
*.key
*.p12
credentials.json
secrets.yml
secrets.yaml
service_account*.json
*_credentials.json
.aws/
.gcp/

# Data files — git is not a data store
*.csv
*.tsv
*.parquet
*.avro
*.orc
*.db
*.sqlite
*.sqlite3
data/raw/
data/processed/
data/interim/
data/external/
!data/sample/
!tests/fixtures/

# dbt
target/
dbt_packages/
profiles.yml          # contains database passwords!
logs/

# Jupyter
.ipynb_checkpoints/
*/.ipynb_checkpoints/

# IDE and OS
.idea/
.vscode/
*.swp
.DS_Store

# Misc
*.log
*.tmp
.terraform/
terraform.tfstate
```

```bash
git status -s
```
**Checkpoint:** only `pipeline.py`, `tests/`, `dbt/models/`,
`notebooks/analysis.ipynb`, and `.gitignore` itself show up now. Everything
under `data/`, `.env`, `credentials.json`, `dbt/target/`, `dbt/profiles.yml`,
`__pycache__/`, and `.venv/` has vanished from the listing.

```bash
git check-ignore -v .env
git check-ignore -v credentials.json
git check-ignore -v data/raw/users_2024_06_10.csv
git check-ignore -v dbt/target/run_results.json
```
**Checkpoint:** each line prints `<gitignore-path>:<line-number>:<pattern> <file>`
— proof of exactly which rule caught that file. Use this any time you're
not sure why something is (or isn't) being tracked.

```bash
git add .
git status -s
```
**Checkpoint:** staged files are exactly the safe ones from above — `.env`
and `credentials.json` are nowhere in the list.

```bash
git commit -m "Add pipeline scaffolding with data-safe .gitignore"
```

---

## 3. The Jupyter notebook problem

`.ipynb` files store cell **outputs** inside the JSON — so re-running a
notebook changes the file even when the code didn't change. That means
huge diffs (base64 image blobs), meaningless "ran the notebook" commits,
merge conflicts when two people run the same cells, and repo bloat.

**Fix: nbstripout** — a git filter that strips outputs before git ever
sees the file.
```bash
pip install nbstripout
nbstripout --install          # this repo only
nbstripout --install --global # every repo on this machine
cat .git/config                # see the [filter "nbstripout"] section it added
```
After this, every `git add notebook.ipynb` stores code only — no outputs.

**Alternative: Jupytext** — save notebooks as plain `.py` files with `%%`
cell delimiters, so diffs are just text:
```bash
pip install jupytext
jupytext --to py:percent notebooks/analysis.ipynb
```
Then `.gitignore` the `.ipynb` and track the `.py` version instead.

(Manually clearing outputs via Kernel → Restart & Clear Output works too,
but relies on remembering every time — nbstripout removes the need to.)

---

## 4. Large files — git is not a data store

Git keeps the **complete history** of every file forever. Commit a 500MB
CSV and even deleting it later doesn't shrink the repo — it's still in
history, and every clone downloads it. GitHub hard-blocks pushes over
100MB and warns above 50MB.

**The right pattern:** code lives in git; data lives in S3/GCS/Azure Blob.
Git tracks the *pointer or config*, not the data itself:
```python
# config.py (gitignored if it has real values)
RAW_DATA_PATH = "s3://my-datalake/raw/users/2024/"
df = spark.read.parquet(RAW_DATA_PATH)
# tests use a tiny fixture: tests/fixtures/users_sample.parquet (10 rows, ~2KB — fine to commit)
```

**If you must version a large file in git**, use Git LFS — it stores the
real file externally and keeps only a pointer in your repo:
```bash
brew install git-lfs
git lfs install
git lfs track "*.parquet"
git lfs track "*.pkl"     # ML model weights
git add .gitattributes
git lfs status            # which files are LFS-tracked
git lfs ls-files
```
For most data teams, DVC (tracks a manifest in git, data stays in remote
storage) beats LFS.

**If a large file is already sitting in history**, find and remove it:
```bash
# Find the biggest blobs in history:
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print $3, $4}' | sort -rn | head -20

# Remove one from ALL history (git filter-repo, never filter-branch — deprecated and dangerous):
pip install git-filter-repo
git filter-repo --path data/huge_file.csv --invert-paths
```
After rewriting history: force-push, and get every collaborator to
re-clone — their old history no longer matches.

---

## 5. Secrets hygiene — the most critical part

**The incident, minute by minute:**
```
9:04:00 PM  git commit -m "add config"; git push origin main
9:04:03 PM  GitHub secret scanning detects the AWS key in the diff
9:04:05 PM  AWS security emails: "Potentially exposed credential detected"
9:05:00 PM  Attackers already found it via GitHub search
9:05:30 PM  Your S3 buckets are being enumerated
```
The key is in history the instant it's pushed — deleting the file and
pushing again does nothing. **Rotate first, clean history second.**

**Prevention — `pre-commit`.** Write `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/kynan/nbstripout
    rev: 0.7.1
    hooks:
      - id: nbstripout

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: no-commit-to-branch
        args: ['--branch', 'main']
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-merge-conflict
      - id: detect-private-key
```

```bash
pip install pre-commit detect-secrets
pre-commit install              # wires hooks into .git/hooks/pre-commit
detect-secrets scan > .secrets.baseline   # whitelist of existing/fake patterns
git add .secrets.baseline .pre-commit-config.yaml
pre-commit run --all-files      # run every hook right now, on demand
```
**Checkpoint:** from now on, every `git commit` runs these hooks first. A
failing hook blocks the commit until you fix it and re-stage.

**Checking whether a secret was ever committed** (even if later deleted):
```bash
git log --all --full-history -- .env
git log --all --full-history -- "*.pem"
git log --all -p | grep -E "AKIA[0-9A-Z]{16}"    # AWS key pattern
```

**If secrets are already in history — the response plan:**
1. **Rotate the credential immediately** — before anything else, assume it's already been used.
2. Assess blast radius: public or private repo? what can that key touch? check CloudTrail/audit logs.
3. Remove it from history:
   ```bash
   pip install git-filter-repo
   git filter-repo --path .env --invert-paths
   git filter-repo --replace-text <(echo 'AKIA...<secret>==>***REMOVED***')
   ```
4. `git push --force-with-lease --all` (coordinate with the team first).
5. Everyone re-clones — history was rewritten.
6. Post-mortem: what process change actually prevents this next time?

---

## 6. `.gitattributes` — line endings and diff drivers

Create `.gitattributes`:
```gitattributes
* text=auto eol=lf

*.bat text eol=crlf
*.cmd text eol=crlf

*.png binary
*.jpg binary
*.pdf binary
*.pkl binary        # ML model weights
*.parquet binary
*.avro binary

# nbstripout as the diff driver — clean diffs, no base64 blobs
*.ipynb diff=ipynb
```

Without `text=auto eol=lf`, a Windows teammate's CRLF line endings vs your
LF ones make every line in a file look changed, even when nothing actually
changed. `*.ipynb diff=ipynb` pairs with the `nbstripout --install` config
from section 3 so `git diff notebook.ipynb` shows only real code changes.

```bash
git add .gitattributes
git commit -m "Add .gitattributes for line endings and notebook diffs"
```

---

## Done — clean up

```bash
cd .. && rm -rf gitignore_demo
```

## Quick reference

```bash
# .gitignore essentials
*.csv *.parquet *.db          data files
.env .env.*                   secrets
__pycache__/ *.pyc            python cache
.venv/                        virtual environment
dbt/target/ dbt/profiles.yml  dbt build artifacts + credentials
.ipynb_checkpoints/           jupyter checkpoints

# Check ignore
git check-ignore -v file.csv  why is this file ignored?

# Jupyter
pip install nbstripout && nbstripout --install

# Large files
git lfs track "*.parquet"                  if you MUST track large files
git filter-repo --path f --invert-paths    remove a file from ALL history

# Secrets
pip install pre-commit detect-secrets
detect-secrets scan > .secrets.baseline
pre-commit install
git log --all --full-history -- .env       check if .env was ever committed

# Incident response
1. Rotate credentials IMMEDIATELY
2. git filter-repo to remove from history
3. Force-push, team re-clones
```

## Before moving on

- [ ] You wrote a `.gitignore` from scratch and confirmed with `git check-ignore -v` that it caught secrets and data files.
- [ ] You know why nbstripout matters and installed it once for real.
- [ ] You can explain the rotate-first-clean-history-second rule without hesitating.
- [ ] You wired up `.pre-commit-config.yaml` and watched a hook actually run.

This is the last concept file for week 2 — head to `practice/exercises.py` next.
