# Week 2 Practice Exercises — Git and GitHub

Do these in a real terminal, inside `practice_repo/`. Read a scenario, do the
tasks yourself, and only expand **Solution** once you've actually tried —
that's the whole point, muscle memory over reading comprehension.

**Setup (run once):**
```bash
python3 exercises.py
```
This creates `./practice_repo/` with a realistic history: multiple commits,
a feature branch, a hotfix branch, two tags (`v0.1.0`, `v0.1.1`, `v1.0.0`),
and prints the resulting log graph and branch list so you can see what you're
starting from.

---

## Exercise 1 — Git History Investigation

**Scenario:** something broke in production with the orders pipeline. You
need to investigate history to understand what changed, who changed it, and when.

Working directory: `practice_repo/`

a) Show the full git log as a one-line graph (all branches).
b) How many commits touch `pipeline.py`? Show the log for just that file.
c) Who made the commit that added the `validate` function? (find the commit, then read it)
d) Use `git blame` on `pipeline.py` to find what commit introduced the line containing `drop_duplicate_keys`.
e) Find all commits with "incremental" in their message.
f) Show the diff between tag `v0.1.0` and `v1.0.0` — how many files changed?

**Hint:** `git log --oneline --graph --all`, `git log --oneline -- pipeline.py`,
`git log --grep="keyword"`, `git blame pipeline.py`, `git diff v0.1.0 v1.0.0 --stat`

<details>
<summary>Solution</summary>

a) `git log --oneline --graph --all`

b) `git log --oneline -- pipeline.py`
   (`--follow` also tracks renames: `git log --follow --oneline -- pipeline.py`)

c) `git log --oneline --all -S "def validate"`
   `-S` is pickaxe search — finds commits that added/removed this exact string.
   Then `git show <hash>` for the full commit.

d) `git blame pipeline.py | grep "drop_duplicate_keys"`
   Output is `hash (author date line#) code` — then `git show <hash>` for context.

e) `git log --oneline --grep="incremental" --all`

f) `git diff v0.1.0 v1.0.0 --stat` (drop `--stat` for the full diff)

</details>

---

## Exercise 2 — The Hotfix Scenario

**Scenario:** you're mid-feature with uncommitted changes. Your manager pings:
"PROD IS DOWN — the orders pipeline is failing with a KeyError on `status`.
Fix it NOW." You can't push half-done work. Switch to main, apply the hotfix,
come back.

Working directory: `practice_repo/`

a) Simulate WIP work: append `# WIP: adding monitoring` to `pipeline.py`. Don't commit.
b) Stash it with a descriptive message. Confirm the working tree is clean.
c) Switch to `main`.
d) Create `hotfix/fix-orders-status-keyerror`. Append
   `# Fixed: use .get('status', 'unknown') instead of direct key access` to
   `orders_pipeline.py`, commit as `"Fix KeyError on status column in orders pipeline"`.
e) Merge the hotfix into `main` with `git merge hotfix/fix-orders-status-keyerror --no-ff`.
f) Go back to `feature/add-incremental-load` and pop your stash. Confirm the WIP comment is back.
g) **Bonus:** cherry-pick the hotfix commit from (d) onto `feature/add-incremental-load` too.

**Hint:** `git stash push -m "wip: ..."`, `git stash list`, `git switch`/`git checkout -b`,
`git merge --no-ff`, `git stash pop`, `git cherry-pick <hash>`

<details>
<summary>Solution</summary>

```bash
cd practice_repo

# a-b) simulate WIP, stash it
echo "# WIP: adding monitoring" >> pipeline.py
git stash push -m "wip: adding monitoring hooks to pipeline"
git status   # clean

# c-d) hotfix on main
git switch main
git checkout -b hotfix/fix-orders-status-keyerror
echo "# Fixed: use .get('status', 'unknown') instead of direct key access" >> orders_pipeline.py
git add orders_pipeline.py
git commit -m "Fix KeyError on status column in orders pipeline"

# e) merge with a merge commit (--no-ff preserves that a hotfix branch was used)
git switch main
git merge hotfix/fix-orders-status-keyerror --no-ff

# f) back to feature, restore stash
git switch feature/add-incremental-load
git stash pop
tail pipeline.py   # "# WIP: adding monitoring" should be there

# g) bonus cherry-pick
git log main --oneline | head -5   # find the hotfix commit hash
git cherry-pick <hotfix-commit-hash>
```
</details>

---

## Exercise 3 — Merge Conflict Resolution

**Scenario:** two engineers edit `config.py` at the same time — one adds DB
connection pooling, the other updates the S3 bucket. Merging collides.

Working directory: `practice_repo/`

a) From `main`, create `engineer-a/update-db-settings`. Overwrite `config.py`:
   ```python
   import os
   DB_HOST = os.environ.get('DB_HOST', 'prod-db.internal')
   DB_PORT = int(os.environ.get('DB_PORT', 5432))
   DB_POOL_SIZE = 10
   S3_BUCKET = os.environ.get('S3_BUCKET', 'my-datalake')
   ```
   Commit as `"Add database connection pooling config"`.

b) Back on `main`, create `engineer-b/update-s3-bucket`. Overwrite `config.py`:
   ```python
   import os
   DB_HOST = os.environ.get('DB_HOST', 'localhost')
   DB_PORT = int(os.environ.get('DB_PORT', 5432))
   S3_BUCKET = os.environ.get('S3_BUCKET', 'data-lake-prod-v2')
   S3_REGION = 'us-east-1'
   ```
   Commit as `"Update S3 bucket to new prod location"`.

c) On `main`, merge engineer-a's branch (fast-forward), then engineer-b's — it should conflict.
d) Resolve manually: `config.py` should end up with `DB_HOST`, `DB_PORT`, `DB_POOL_SIZE`,
   the *new* `S3_BUCKET`, and `S3_REGION`. Stage and complete the merge.
e) Verify the final file has all settings from both engineers.

**Hint:** `git checkout -b`, `git add`/`git commit`, `git merge` (conflict markers appear),
edit out `<<<`/`===`/`>>>`, `git add config.py`, `git commit`

<details>
<summary>Solution</summary>

```bash
cd practice_repo

# a) engineer A
git checkout -b engineer-a/update-db-settings
cat > config.py << 'EOF'
import os
DB_HOST = os.environ.get('DB_HOST', 'prod-db.internal')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
DB_POOL_SIZE = 10
S3_BUCKET = os.environ.get('S3_BUCKET', 'my-datalake')
EOF
git add config.py
git commit -m "Add database connection pooling config"

# b) engineer B
git switch main
git checkout -b engineer-b/update-s3-bucket
cat > config.py << 'EOF'
import os
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
S3_BUCKET = os.environ.get('S3_BUCKET', 'data-lake-prod-v2')
S3_REGION = 'us-east-1'
EOF
git add config.py
git commit -m "Update S3 bucket to new prod location"

# c) merge both
git switch main
git merge engineer-a/update-db-settings   # fast-forward
git merge engineer-b/update-s3-bucket     # CONFLICT on config.py

# d) resolve
git status   # both modified: config.py
cat > config.py << 'EOF'
import os
DB_HOST = os.environ.get('DB_HOST', 'prod-db.internal')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
DB_POOL_SIZE = 10
S3_BUCKET = os.environ.get('S3_BUCKET', 'data-lake-prod-v2')
S3_REGION = 'us-east-1'
EOF
git add config.py
git commit -m "Merge engineer configs: combine pooling and new S3 bucket"

# e) verify
cat config.py   # DB_POOL_SIZE, S3_REGION, and the updated S3_BUCKET should all be there
```
</details>

---

## Exercise 4 — Undoing Mistakes

**Scenario:** you need the four undo operations to be reflexive.

Working directory: `practice_repo/`

a) **Undo last commit, keep staged:** add `print('DEBUG: checking...')` to
   `quality_checks.py`, commit as `"Add debug print to quality checks"`. Undo
   just the commit, keeping the change staged. Verify with `git log`.
b) **Discard working-tree changes:** add `# TODO: this is all wrong` to
   `quality_checks.py`, don't stage it, then throw it away with `git restore`.
   Verify with `git diff`.
c) **Unstage one file:** edit both `pipeline.py` and `README.md`, `git add .`
   both, then unstage just `pipeline.py` and commit only `README.md`. Verify
   `pipeline.py`'s edit is still there (unstaged) but not committed.
d) **Safe revert:** find the commit that added "Add retry logic to S3
   operations", `git revert` it with `--no-edit`. Verify a new `Revert ...`
   commit appears and the retry logic is gone from `pipeline.py`.

**Hint:** `git reset --soft HEAD~1`, `git restore file`,
`git restore --staged file`, `git revert <hash> --no-edit`, `git log --grep="retry"`

<details>
<summary>Solution</summary>

```bash
cd practice_repo

# a) undo last commit, keep staged
echo "print('DEBUG: checking...')" >> quality_checks.py
git add quality_checks.py
git commit -m "Add debug print to quality checks"
git log --oneline | head -3     # see it there
git reset --soft HEAD~1
git log --oneline | head -3     # commit gone
git status -s                   # quality_checks.py staged again

# b) discard working tree changes
echo "# TODO: this is all wrong" >> quality_checks.py
git diff quality_checks.py      # see the change
git restore quality_checks.py
git diff quality_checks.py      # nothing — discarded

# c) unstage one file
echo "# Performance note" >> pipeline.py
echo "Updated 2024-06-10" >> README.md
git add .
git status -s                   # both staged
git restore --staged pipeline.py
git status -s                   # README.md staged, pipeline.py unstaged
git commit -m "Update README with date"
git status -s                   # pipeline.py still shows modified

# d) safe revert
git log --oneline --grep="retry"       # note the hash, e.g. a1b2c3d
git revert a1b2c3d --no-edit
git log --oneline | head -3            # "Revert Add retry logic..."
grep "def extract" pipeline.py         # retry loop simplified again
```
</details>

---

## Exercise 5 — Write a .gitignore for a Data Project

**Scenario:** a new project from scratch — Python code, dbt models, Jupyter
notebooks, a `.env` file, CSV data, pytest.

a) Outside `practice_repo/`, make `new_project/`, `git init` it, and create:
   `pipeline.py`, `.env`, `data/raw/users.csv`, `data/processed/users.parquet`,
   `notebooks/analysis.ipynb`, `notebooks/.ipynb_checkpoints/analysis-checkpoint.ipynb`,
   `dbt/target/run_results.json`, `dbt/profiles.yml`,
   `__pycache__/pipeline.cpython-311.pyc`, `.venv/lib/something.py`.
b) `git status -s` — everything should show untracked.
c) Write a `.gitignore` covering: `.env`/`.env.*`, all CSV/Parquet, `__pycache__/`
   and `*.pyc`, `.venv/`, `dbt/target/`, `dbt/profiles.yml`, `.ipynb_checkpoints/`, `.DS_Store`.
d) `git status -s` again — confirm `pipeline.py` and `notebooks/analysis.ipynb`
   are tracked, but `dbt/target/`, `.env`, and `.venv/` are gone.
e) `git check-ignore -v .env` — confirm which rule caught it.
f) **Bonus:** add `!data/sample/`, create `data/sample/tiny_test.csv` with a
   few rows — is it tracked? Why?

**Hint:** `mkdir new_project && cd new_project && git init`, then write files
and `.gitignore`, then `git check-ignore -v filename`

<details>
<summary>Solution</summary>

```bash
# a-b) create project and files
mkdir -p new_project/data/raw new_project/data/processed
mkdir -p new_project/notebooks/.ipynb_checkpoints
mkdir -p new_project/dbt/target new_project/__pycache__
mkdir -p new_project/.venv/lib
touch new_project/pipeline.py
echo "DB_PASSWORD=secret" > new_project/.env
echo "id,name" > new_project/data/raw/users.csv
touch new_project/data/processed/users.parquet
touch new_project/notebooks/analysis.ipynb
touch new_project/notebooks/.ipynb_checkpoints/analysis-checkpoint.ipynb
echo '{"results":[]}' > new_project/dbt/target/run_results.json
echo "password: secret" > new_project/dbt/profiles.yml
touch new_project/__pycache__/pipeline.cpython-311.pyc
touch new_project/.venv/lib/something.py

cd new_project && git init && git status -s   # everything untracked

# c) .gitignore
cat > .gitignore << 'EOF'
.env
.env.*
*.csv
*.parquet
__pycache__/
*.pyc
.venv/
dbt/target/
dbt/profiles.yml
.ipynb_checkpoints/
.DS_Store
EOF

# d) verify
git status -s
# pipeline.py        -> tracked
# notebooks/*.ipynb  -> tracked (outputs handled by nbstripout separately)
# .env, dbt/target/, .venv/ -> not shown (ignored)

# e) why is .env ignored?
git check-ignore -v .env      # .gitignore:1:.env    .env

# f) bonus negation
echo "!data/sample/" >> .gitignore
mkdir -p data/sample
printf "id,name\n1,Alice\n2,Bob\n3,Carol\n" > data/sample/tiny_test.csv
git status -s
# data/sample/tiny_test.csv IS tracked — the !data/sample/ line negates the
# *.csv rule for that directory (negation only works if the parent isn't
# already ignored — data/sample/ itself was never matched by an earlier rule)
```
</details>

---

## Exercise 6 — Write a Good PR Description

**Scenario:** you finished adding incremental load mode to the users
pipeline, on `feature/add-incremental-load` in `practice_repo/`. Changes:

- Added `watermark.py`: tracks the last-processed timestamp per pipeline.
- `pipeline.py`'s `extract()` now takes `incremental=True/False`; when
  `True`, reads only rows where `updated_at` is newer than the watermark.
- `load()` saves the new watermark after a successful load.
- Cuts daily runtime from 45 min to ~2 min.
- Requires `updated_at` to exist and be non-null; first run is always full.

a) Write a PR title (imperative, under 72 chars, specific).
b) Write a description: what changed, why, how to test, risks.
c) **Bonus:** which merge strategy would you recommend, and why?

**Hint:** titles start with a verb ("Add", "Fix", "Refactor", "Remove");
tests should be concrete steps, not "test the feature".

<details>
<summary>Solution</summary>

**a) Title:** "Add incremental load mode to users pipeline" (or "Add
watermark-based incremental load for users ETL")

**b) Description:**
```
## What changed
- Added `watermark.py`: reads/writes a JSON file tracking the last processed
  `updated_at` timestamp per pipeline name
- Modified `pipeline.py`: `extract()` now accepts `incremental=False` param.
  When `True`, filters to rows where `updated_at > last_watermark`
- `load()` now saves a new watermark after every successful run

## Why
Full reload of the users table takes 45 minutes as the table has grown to
15M rows. With incremental mode, daily runs process only ~50K changed rows,
reducing runtime to ~2 minutes. Required to meet the 5am SLA.

## How to test
- [ ] `pytest tests/test_pipeline.py` passes
- [ ] Run with incremental=False (full load): verify all rows loaded
- [ ] Run with incremental=True on staging: verify only rows after last run processed
- [ ] Check `.watermark.json` is created with a valid timestamp
- [ ] Verify `.watermark.json` is in .gitignore (not committed)
- [ ] Simulate failure mid-run: verify watermark is NOT advanced on error

## Risks
- First production run will be a full load (no watermark yet) — takes 45 min
- `updated_at` must be non-null and indexed; confirm with DBA
- If the pipeline fails mid-run after the watermark was already written,
  some rows might be re-processed next run (currently idempotent, so safe)
```

**c) Bonus:** Squash merge. The branch has 2 meaningful commits, but the PR
as a whole is the atomic unit worth seeing on `main` — squash gives one
clean commit ("Add incremental load mode to users pipeline") while the full
branch history stays visible in the closed PR.
</details>

---

## Exercise 7 — Git Log Archaeology

**Scenario:** answer these using git commands only — don't peek at `exercises.py`.

Working directory: `practice_repo/`

a) How many total commits are on `main`?
b) What's the short commit hash at tag `v0.1.0`?
c) Which files changed between `v0.1.0` and `v1.0.0`?
d) What commit first introduced the word "incremental" into any file's *content* (not message)?
e) Find all commits where lines were added/removed in `config.py`.
f) Show the commit log from the first commit through the `v0.1.1` tag.
g) Show the full diff of the most recent commit on `feature/add-incremental-load`.
h) Build a one-line commit graph showing all branches and tags.

**Hint:** `git rev-list --count main`, `git log --oneline v0.1.0`,
`git diff v0.1.0 v1.0.0 --name-only`, `git log -S "incremental" --all --oneline`,
`git log --oneline -- config.py`, `git log --oneline --graph --all --decorate`

<details>
<summary>Solution</summary>

a) `git rev-list --count main` (or `git log --oneline main | wc -l`)
b) `git log --oneline -1 v0.1.0` (or `git show v0.1.0 --format="%h %s" -s`)
c) `git diff v0.1.0 v1.0.0 --name-only`
d) `git log -S "incremental" --all --oneline` — `-S` (pickaxe) finds commits where the string was added/removed
e) `git log --oneline -- config.py`
f) `git log --oneline v0.1.1` — shows everything reachable from that tag
g) `git show feature/add-incremental-load` (or `git log -1 -p feature/add-incremental-load`)
h) `git log --oneline --graph --all --decorate` — `--decorate` adds tag/branch names

</details>

---

Done all seven? Head to `../projects/git_workflow_simulator.py` next.
