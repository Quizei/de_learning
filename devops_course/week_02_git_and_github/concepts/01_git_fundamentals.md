# Git Fundamentals — Walkthrough

"No more `final_v2_REAL_fixed_USE_THIS.py`."

This is not a script you run — it's a set of commands you type yourself, in
your own terminal, in order. Git only sticks if your hands do it. After each
command there's a **checkpoint**: what you should see before moving on.

Budget ~25 minutes.

## Setup

```bash
mkdir my_pipeline_project && cd my_pipeline_project
git init
git config user.name "Your Name"
git config user.email "you@example.com"
```
**Checkpoint:** `git status` should say `On branch main` and `No commits yet`.

---

## 1. The three-area model

Every git command you're about to run moves a file between three places:

```
Working Tree  ──git add──►  Staging Area  ──git commit──►  Repository (.git/)
(files on disk)             (draft of next commit)         (permanent history)
     ◄──git restore──             ◄──git restore --staged──
```

- **Working tree** — the files you edit.
- **Staging area** — "I want to include *these* changes in the next commit."
- **Repository** — permanent, in `.git/`. Never delete that folder.

Why bother with a staging area? You can make 10 changes but commit them as
3 logical units — fix + config update + doc update, each with its own
message — instead of one giant "saved everything" commit.

---

## 2. `git status` — reading the output

```bash
echo 'import pandas as pd' > pipeline.py
echo 'def transform(df): return df' > transform.py
echo '# Data Pipeline Project' > README.md
echo 'DB_PASSWORD=secret123' > .env
git status
```
**Checkpoint:** all four files listed under `Untracked files` (red).

```bash
git add pipeline.py
git status
```
**Checkpoint:** `pipeline.py` moved to `Changes to be committed:` (green).
The other three are still untracked.

Short format, worth memorizing:
```bash
git status -s
```
```
M  = modified, staged        A  = added, staged
 M = modified, unstaged      ?? = untracked
```

**Do not `git add .env`** — it holds a real secret. You'll cover this
properly in concept 4 (.gitignore).

---

## 3. `git add` — staging changes

```bash
git add README.md transform.py
git status -s
```
**Checkpoint:** `pipeline.py`, `README.md`, `transform.py` all staged (`A`).
`.env` still untracked.

The one worth learning beyond `git add file`:

```bash
git add -p pipeline.py
```
This walks you through each changed **hunk** one at a time and asks
`y` (stage it) / `n` (skip it) / `s` (split smaller) / `e` (edit) / `q` (quit).
Use it when one file has two unrelated changes and you want to commit them
separately. (Nothing is staged for pipeline.py yet, so this will just say
"No changes" — come back to it once you've made an edit worth splitting.)

---

## 4. `git commit` — making it permanent

A commit is a permanent snapshot: hash, author, timestamp, message, pointer
to its parent, and the full state of every tracked file.

```bash
git commit -m "Add initial pipeline scaffolding"
git status
```
**Checkpoint:** `nothing to commit, working tree clean`. `.env` still untracked.

**Commit message rules:**
| Bad | Good |
|---|---|
| `fixed stuff` | `Fix null pointer in users ETL when email column missing` |
| `pipeline changes` | `Add incremental load mode to orders pipeline` |
| `WIP` | `Refactor S3 loader to use boto3 resource instead of client` |

1. Imperative mood — "Add", "Fix", "Refactor" (not "Added").
2. Subject line under ~72 characters.
3. Say **why**, not what — the diff already shows what.

Make three more, so there's real history to inspect below:

```bash
echo 'def extract(query): pass' >> pipeline.py
echo 'def load(df, path): pass' >> pipeline.py
git add pipeline.py
git commit -m "Add extract and load function stubs to pipeline"

echo 'def clean_nulls(df): return df.dropna()' >> transform.py
echo 'def deduplicate(df): return df.drop_duplicates()' >> transform.py
git add transform.py
git commit -m "Add null cleaning and deduplication transforms"

mkdir tests && echo 'import pytest' > tests/test_transform.py
git add tests/
git commit -m "Add test scaffolding for transforms"
```
**Checkpoint:** `git log --oneline` shows 4 commits.

---

## 5. `git log` — reading history

```bash
git log --oneline                          # short hash + message, most-used view
git log --oneline --graph                  # branch shape (more useful later, with branches)
git log -3                                 # last 3, full format
git log --stat                             # which files changed, how many lines
git log -p -1                              # full diff of most recent commit
git log --oneline -- pipeline.py           # only commits touching this file
git log --follow --oneline -- pipeline.py  # same, but tracks it through renames
```
**Checkpoint:** the `-- pipeline.py` log should show 2 commits (the initial one
and the extract/load one) — `transform.py`'s commits shouldn't appear.

Searching:
```bash
git log --grep="null"           # commits with 'null' in the message
git log --author="Your Name"
git log --since="2 weeks ago"
```

---

## 6. `git diff` and `git show`

```bash
echo '# TODO: add retry logic' >> pipeline.py
echo 'def validate(df): pass' >> transform.py
git add transform.py    # stage transform.py, leave pipeline.py unstaged
```

```bash
git diff              # working tree vs staging area (unstaged only)
git diff --staged     # staging area vs last commit (staged only)
git diff HEAD         # everything since last commit, staged + unstaged
```
**Checkpoint:** `git diff` shows only the `pipeline.py` TODO line.
`git diff --staged` shows only the `transform.py` validate function.

```bash
git show HEAD             # full diff + metadata of the most recent commit
git show HEAD --stat      # just the summary of what changed
```

---

## 7. `git blame` — who changed this line, and why

```bash
git blame transform.py
```
Each line is prefixed `<hash> (<author> <date>) <line number>) <content>`.

**Practical use:** you spot a bug on line 42 of some file in production.
`git blame` names the commit that last touched it →
`git show <that hash>` shows the full change and its message → now you know
*why* it was written that way before you touch it.

```bash
git blame -L 10,20 pipeline.py   # only lines 10-20
```

---

## 8. Undoing things — the most important section

| Situation | Command |
|---|---|
| Discard working-tree changes | `git restore file` |
| Unstage a file | `git restore --staged file` |
| Undo a commit, safely (new commit) | `git revert <hash>` |
| Undo a commit, keep changes staged | `git reset --soft HEAD~1` |
| Undo a commit, discard everything | `git reset --hard HEAD~1` |

**Rule of thumb:** `git revert` is almost always right on a shared/pushed
branch. `git reset --hard` destroys commits — only use it on commits that
exist *nowhere but your own machine*.

**A — discard an unstaged change (cannot undo):**
```bash
git status -s                # pipeline.py shows unstaged changes
git restore pipeline.py
git status -s                # gone
```

**B — unstage without losing the change:**
```bash
echo 'accidental_change = True' >> transform.py
git add transform.py
git status -s                 # transform.py staged (oops)
git restore --staged transform.py
git status -s                 # back to unstaged — content preserved
git add transform.py
git commit -m "Add validate function to transforms"
```

**C — `git revert`: safe undo, new commit, history preserved:**
```bash
git log --oneline
git revert HEAD --no-edit
git log --oneline
```
**Checkpoint:** a new `Revert "..."` commit sits on top. The original commit
is still in history, just cancelled out — nothing was deleted or rewritten.
This is why it's safe on `main`: nobody else's history breaks.

**D — `git reset --soft`: undo the commit, keep the work staged:**
```bash
echo '# debug line' >> transform.py
git add transform.py
git commit -m "fixed stuff"     # bad message, on purpose
git log --oneline
git reset --soft HEAD~1
git status -s                   # staged again — free to fix the message
git commit -m "Add debug logging to transforms"
```

**Never** run `git reset --hard HEAD~1` unless you're certain that commit
has never been pushed anywhere. It discards the commit *and* any
uncommitted changes, with no undo.

---

## 9. `git stash` — save work in progress

**Scenario:** you're mid-feature. Someone says prod is down, fix it now.
You can't commit half-finished work — stash it instead.

```bash
echo '# WIP: adding retry logic' >> pipeline.py
git add pipeline.py
git status -s                                        # WIP, partially staged

git stash push -m "wip: adding retry logic to pipeline"
git status                                            # clean — safe to switch branches now

git stash list                                        # stash@{0} = most recent, LIFO
```

Do the (imaginary) hotfix, then come back:
```bash
git stash pop      # re-applies the most recent stash and removes it from the list
git status -s      # WIP is back
```

Other stash commands worth knowing:
```bash
git stash push -- file.py       # stash only one file
git stash show stash@{0}        # peek at what's in a stash
git stash apply stash@{1}       # apply a specific stash, keep it in the list
git stash drop stash@{0}        # delete one stash
git stash clear                 # delete ALL stashes (careful)
```

---

## Done — clean up

```bash
cd .. && rm -rf my_pipeline_project
```

## Quick reference

```bash
# Setup
git init                          git clone <url>

# Inspect
git status / git status -s
git log --oneline --graph
git log --oneline -- file.py
git diff / git diff --staged / git diff HEAD~1
git show <hash>                   git blame file.py

# Stage & commit
git add file.py / git add -p file.py
git commit -m "message"

# Undo
git restore file.py               git restore --staged file.py
git revert <hash>                 git reset --soft HEAD~1
git reset --hard HEAD~1           # DESTRUCTIVE

# Stash
git stash push -m "wip: ..."      git stash list
git stash pop                     git stash drop stash@{0}
```

## Before moving on

- [ ] You made 4+ commits with proper imperative messages, no `python3` involved.
- [ ] You can explain the difference between `git diff` and `git diff --staged` without looking it up.
- [ ] You know when to reach for `git revert` vs `git reset --soft` vs `git reset --hard`.
- [ ] You stashed something, switched context, and popped it back.

Next: `concepts/02_branching_and_merging.md`
