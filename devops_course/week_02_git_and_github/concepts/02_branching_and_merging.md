# Git Branching and Merging — Walkthrough

A branch is just a lightweight pointer to a commit — creating one costs
almost nothing. That's what lets a whole team work on the same codebase at
once without stepping on each other.

Type every command yourself. Budget ~30 minutes.

## Setup

```bash
mkdir git_branch_demo && cd git_branch_demo
git init -b main
git config user.name "Your Name"
git config user.email "you@example.com"

echo "# Data Pipeline

def run():
    pass" > pipeline.py
git add pipeline.py && git commit -m "Initialize data pipeline project"

echo "S3_BUCKET = 'data-lake-prod'
REGION = 'us-east-1'" > config.py
git add config.py && git commit -m "Add S3 configuration"

echo "# Pipeline
Runs daily ETL jobs." > README.md
git add README.md && git commit -m "Add README"
```
**Checkpoint:** `git log --oneline` shows 3 commits on `main`.

---

## 1. What a branch actually is

```
main ──► [C3] ──► [C2] ──► [C1]
           ▲
          HEAD  (HEAD points at the current branch)
```
Creating `feature/add-s3-loader` from `main` just writes 40 bytes to
`.git/refs/heads/feature/add-s3-loader` pointing at the same commit as
`main`. No files are copied.

```
main                    ──► [C3]
feature/add-s3-loader   ──► [C3]   (same commit, two names)
```
Once you commit on the feature branch, only that branch's pointer moves —
`main` doesn't budge until you merge.

```bash
git log --oneline --graph
```

---

## 2. Branch commands — create, list, delete

```bash
git branch                              # list local branches, * = current
git branch -a                           # + remote-tracking branches
git branch feature/add-s3-loader        # create, but don't switch
git branch                              # exists, but HEAD is still on main
```

```bash
git checkout -b feature/incremental-load    # create + switch, classic syntax
git branch                                  # now on feature/incremental-load
git checkout main
```

```bash
git switch feature/add-s3-loader   # git switch: the modern alternative to checkout for branches
git branch
git switch main
```

**Naming conventions worth adopting:**
```
feature/add-s3-loader          new functionality
bugfix/fix-null-in-users-etl   bug fix
hotfix/revert-broken-join      urgent prod fix
refactor/migrate-to-polars     code cleanup
chore/update-dependencies      maintenance
```

```bash
git branch -d feature/incremental-load   # -d: safe delete, fails if unmerged
git branch -D feature/add-s3-loader      # -D: force delete, even if unmerged
git branch
```
**Checkpoint:** both branches are gone; only `main` remains.

---

## 3. HEAD and detached HEAD

HEAD normally points at a branch name. Check out a raw commit hash instead
and HEAD points directly at that commit — **detached HEAD**.

```
Normal:     HEAD ──► main ──► [C3]
Detached:   HEAD ─────────────► [C1]     main ──► [C3]
```

```bash
old_hash=$(git log --oneline | tail -1 | awk '{print $1}')
git checkout $old_hash
git log --oneline -1     # HEAD points straight at the commit, not a branch
git switch main          # back to normal
```
**Checkpoint:** `git status` while detached says `HEAD detached at <hash>`.

You *can* commit in detached HEAD, but that commit is orphaned the moment
you switch away — nothing points at it anymore. Useful for looking at old
code (`git checkout v1.2.0`) but if you want to keep work made there, run
`git switch -c new-branch` before leaving.

---

## 4. Fast-forward merge

Happens when `main` hasn't moved since the feature branch was cut — git just
slides the `main` pointer forward, no merge commit needed.

```bash
git checkout -b feature/add-users-loader
mkdir -p loaders
echo "def load_users(path):
    pass" > loaders/users_loader.py
git add loaders/users_loader.py
git commit -m "Add users loader function"

echo "def load_users(path):
    try:
        pass
    except Exception as e:
        raise" > loaders/users_loader.py
git add loaders/users_loader.py
git commit -m "Add error handling to users loader"

git log --oneline --graph --all    # before merge
```

```bash
git switch main
git merge feature/add-users-loader
git log --oneline --graph --all    # after: main just moved forward, no merge commit
```
**Checkpoint:** history is linear — no merge commit appears.

To force a merge commit even when fast-forward is possible (makes it
explicit a feature branch landed, at the cost of a slightly noisier log):
```bash
git merge --no-ff feature/name
```

---

## 5. Three-way merge

Happens when **both** branches have new commits since they diverged — git
needs a merge commit to bring them together, using the common ancestor plus
both tips to figure out what changed.

```bash
git checkout main
echo "ALERT_EMAIL = 'oncall@example.com'
DASHBOARD_URL = 'http://grafana/'" > monitoring.py
git add monitoring.py
git commit -m "Add monitoring configuration"

git checkout -b feature/add-orders-pipeline
mkdir -p pipelines
echo "def extract_orders(): pass" > pipelines/orders_etl.py
git add pipelines/orders_etl.py
git commit -m "Add orders ETL skeleton"

echo "def extract_orders(): pass
def transform_orders(df): return df" > pipelines/orders_etl.py
git add pipelines/orders_etl.py
git commit -m "Add orders transform logic"

git log --oneline --graph --all   # main and feature both moved since the fork
```

```bash
git switch main
git merge feature/add-orders-pipeline --no-edit
git log --oneline --graph --all   # a merge commit now ties both lines together
```
**Checkpoint:** the graph shows a merge commit with two parent lines.

If the same lines were touched on both sides, this is where you'd hit a
conflict instead of an automatic merge — that's section 9.

---

## 6. Squash merge

`git merge --squash` collapses every commit on a feature branch into one
staged change, so you write a single clean commit message on `main`.

```
Before:  feature ──► [wip3] ──► [wip2] ──► [wip1] ──► [C]
After:   main    ──► [Add orders pipeline] ──► [C]
```

This does **not** create a merge commit, and the feature branch's individual
commits don't appear in `main`'s history — that's the point, when you don't
care about the messy path, only the result:

```bash
git checkout main
git merge --squash feature/add-orders-pipeline
git commit -m "Add complete orders ETL pipeline"
```
(Skip actually running this now — you already merged that branch normally
above. Come back and try it on a fresh branch if you want to see it live.)

---

## 7. Rebase — replay commits on a new base

`git rebase main` replays your branch's commits on top of another branch,
producing a linear history that looks like you branched from the latest tip.

```
Before:  main    ──► [M2] ──► [M1] ──► [C]
         feature ──► [F2] ──► [F1] ──► [C]

After (git checkout feature && git rebase main):
         feature ──► [F2'] ──► [F1'] ──► [M2] ──► [M1] ──► [C]
```
`F1'`/`F2'` are **new commits** — same content, new hashes, replayed on `M2`.

**The golden rule: never rebase a branch that's been pushed and pulled by
anyone else.** Rebasing rewrites hashes; if others already have the old
ones, their history diverges from yours and everyone has a bad time. Safe
to rebase your own local feature branch before opening a PR — never `main`
or any shared branch.

```bash
git checkout -b feature/add-logging
echo "import logging
logging.basicConfig(level=logging.INFO)" > logging_config.py
git add logging_config.py
git commit -m "Add basic logging setup"

echo "import logging
FMT = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=FMT)" > logging_config.py
git add logging_config.py
git commit -m "Add structured log format"

git switch main
echo "def health(): return {'status': 'ok'}" > healthcheck.py
git add healthcheck.py
git commit -m "Add healthcheck endpoint"

git log --oneline --graph --all   # feature/add-logging branched from an older main
```

```bash
git switch feature/add-logging
git rebase main
git log --oneline --graph --all   # feature now sits on top of main's tip

git switch main
git merge feature/add-logging     # fast-forward now, because we rebased
git log --oneline --graph --all   # perfectly linear
```
**Checkpoint:** the final merge was a fast-forward — no merge commit needed,
because rebase already put your commits on top.

---

## 8. Interactive rebase — clean up your own commits

`git rebase -i HEAD~3` opens an editor listing your last 3 commits, letting
you edit, squash, reorder, or drop them **before sharing them**:

```
pick a1b2c3 Add users loader function
pick d4e5f6 fix typo
pick g7h8i9 WIP: more work
```

Change `pick` to:
| Command | Effect |
|---|---|
| `reword` | keep the commit, edit its message |
| `edit` | pause here so you can amend it |
| `squash` | merge into the previous commit, keep both messages |
| `fixup` | merge into the previous commit, discard this message |
| `drop` | remove the commit entirely |

**Try it for real:**
```bash
git rebase -i HEAD~3
```
Change the middle `pick d4e5f6 fix typo` to `squash`, and drop the WIP line
entirely (delete it or mark `drop`). Save and close the editor.
```bash
git log --oneline
```
**Checkpoint:** 3 commits became 2, and the typo fix is folded into the one
above it.

Same golden rule as regular rebase: only rewrite commits nobody has pulled.

---

## 9. Conflict resolution, step by step

A conflict happens when two branches change the **same lines** of the
**same file** — git can't guess which version you want.

```bash
git checkout -b feature/update-config
echo "S3_BUCKET = 'staging-lake'
REGION = 'us-west-2'
TIMEOUT = 30" > config.py
git add config.py
git commit -m "Update config to use staging environment"

git switch main
echo "S3_BUCKET = 'data-lake-v2'
REGION = 'us-east-1'
MAX_RETRIES = 5" > config.py
git add config.py
git commit -m "Update config with new bucket and retry settings"

git merge feature/update-config
```
**Checkpoint:** git reports `CONFLICT (content): Merge conflict in config.py`.

```bash
git status     # "both modified" marks the conflicted file
cat config.py
```
You'll see conflict markers:
```
<<<<<<< HEAD
S3_BUCKET = 'data-lake-v2'
REGION = 'us-east-1'
MAX_RETRIES = 5
=======
S3_BUCKET = 'staging-lake'
REGION = 'us-west-2'
TIMEOUT = 30
>>>>>>> feature/update-config
```
Everything between `<<<<<<< HEAD` and `=======` is *your current branch's*
version; between `=======` and `>>>>>>> feature/update-config` is the
*incoming* version.

**Resolve it** — open `config.py` in your editor, delete the markers, and
keep the combination you actually want:
```bash
echo "S3_BUCKET = 'data-lake-v2'
REGION = 'us-east-1'
MAX_RETRIES = 5
TIMEOUT = 30" > config.py

git add config.py
git status    # conflict resolved, staged
git commit -m "Merge feature/update-config: combine retry and timeout settings"
git log --oneline --graph --all
```
**Checkpoint:** log shows a merge commit; `config.py` has all four settings.

**Prevention:** keep branches short-lived, communicate who owns which
files, make small focused commits, and `git pull --rebase` often to stay
in sync. If markers get messy, `git mergetool` opens a visual diff tool
(configure with `git config merge.tool vscode`).

---

## 10. Cherry-pick — apply one commit to another branch

`git cherry-pick <hash>` applies a single commit to your current branch —
not the whole branch, just that one commit.

**Scenario:** you're deep in a multi-week feature branch. A critical fix
just landed on another branch. You need it now, in your branch, without
merging everything else in.

```bash
git checkout -b hotfix/fix-s3-timeout
echo "S3_BUCKET = 'data-lake-v2'
REGION = 'us-east-1'
MAX_RETRIES = 5
TIMEOUT = 300  # was 30, need 300 for large parquet files
CONNECT_TIMEOUT = 30" > config.py
git add config.py
git commit -m "Fix S3 connection timeout for large files"

bugfix_hash=$(git log --oneline -1 | awk '{print $1}')
git switch main
git cherry-pick $bugfix_hash
git log --oneline --graph --all
```
**Checkpoint:** `main` has a new commit with the same change but a
**different hash** — cherry-pick creates a fresh commit, it doesn't move
the original.

```bash
# If it conflicts:
git cherry-pick --continue   # after resolving, like a merge conflict
git cherry-pick --abort      # or bail out entirely

# Multiple commits, or a range:
git cherry-pick A B C
git cherry-pick A..C         # excludes A, includes B through C
```
Use it for an emergency hotfix or pulling one useful commit from an old
branch — not as a substitute for a real merge, or you'll end up with
duplicate commits later.

---

## Done — clean up

```bash
cd .. && rm -rf git_branch_demo
```

## Quick reference

```bash
# Create / switch
git checkout -b feature/name        git switch -c feature/name
git switch main                     git branch feature/name

# List / delete
git branch                          git branch -a
git branch -d feature/name          git branch -D feature/name

# Merge
git merge feature/name              git merge --no-ff feature/name
git merge --squash feature/name

# Rebase
git rebase main                     git rebase -i HEAD~3

# Conflicts
git status / (edit file) / git add file.py / git commit
git merge --abort

# Cherry-pick
git cherry-pick <hash>              git cherry-pick A..C
```

## Before moving on

- [ ] You can draw the difference between fast-forward and three-way merge from memory.
- [ ] You caused a real conflict, saw the markers, and resolved it yourself.
- [ ] You know why rebasing a shared branch is dangerous — and could explain it to a teammate.
- [ ] You cherry-picked a commit and confirmed it got a new hash.

Next: `concepts/03_github_prs_and_workflows.md`
