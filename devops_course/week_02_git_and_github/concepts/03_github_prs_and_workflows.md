# GitHub, Pull Requests, and Team Workflows — Walkthrough

Local git gets your code versioned. GitHub makes collaboration possible.
This walkthrough needs a real GitHub account and one throwaway repo — network
operations can't be faked in a local temp folder the way concepts 1 and 2
were.

**Setup:** create a scratch repo to practice on (delete it when you're done):
```bash
gh repo create git-practice-scratch --private --clone
cd git-practice-scratch
echo "# scratch" > README.md
git add README.md && git commit -m "Initial commit"
git push -u origin main
```
If you don't have `gh` yet: `brew install gh` then `gh auth login`.

---

## 1. Remotes — origin, upstream, tracking branches

A "remote" is just a named URL to another copy of the repo, stored in
`.git/config`.

- **origin** — the repo you cloned from (created automatically by `git clone`).
- **upstream** — the *original* repo, when `origin` is your fork of it. Fork
  `apache/airflow` → your fork is `origin`, `apache/airflow` is `upstream`.
- **tracking branch** (`origin/main`) — your local snapshot of what `main`
  looks like on GitHub. It only updates when you `fetch`/`pull` — it is not live.

```
GitHub             Your Machine
──────────────     ─────────────────────────────
main  [C3]   ◄──── origin/main  [C3]  (tracking)
                    main        [C3]  (local)
                    feature/x   [C5]  (local, not pushed yet)
```

```bash
git remote -v                 # show configured remotes
git remote add upstream https://github.com/apache/airflow.git
git remote remove upstream    # just removes the reference, not the actual repo
git branch -vv                # local branches + their upstream tracking branch
```

---

## 2. Push, fetch, pull

```
git fetch   → download remote changes, does NOT touch your local branches
git pull    → fetch + merge (or rebase) into your current branch
git push    → send your local commits to the remote
```

```bash
echo "def transform(): pass" > pipeline.py
git add pipeline.py
git commit -m "Add pipeline transform stub"
git checkout -b feature/add-s3-loader
git push -u origin feature/add-s3-loader   # -u sets tracking; after this, plain `git push` works
```
**Checkpoint:** `gh repo view --web` shows the new branch on GitHub.

```bash
git push                       # now that tracking is set, no args needed
git push --force-with-lease    # safe force push — only overwrites if no one else pushed since
```
**Never `git push --force`** on a shared branch — it overwrites remote
history unconditionally and can delete someone else's work. `--force-with-lease`
refuses if the remote moved since you last fetched.

```bash
git fetch origin
git fetch --prune              # also drop remote-tracking branches deleted on GitHub
git diff main origin/main      # what's on remote you don't have locally yet
git log main..origin/main      # commits on remote but not local
```

```bash
git pull                # fetch + merge
git pull --rebase       # fetch + rebase — your commits replay on top, no merge commit
git config pull.rebase true   # make --rebase the default
```
Most teams prefer `--rebase`: it avoids the noisy
`Merge branch 'main' into main` commits and keeps history linear.

---

## 3. Pull Requests — anatomy and review

A PR is GitHub's UI layer over git: "merge this branch into that one, please
review first."

**A good PR description:**
```
Title: Add incremental load mode to orders pipeline
Branch: feature/add-incremental-load → main

## What changed
Added incremental load option to orders ETL. Instead of full reload,
pipeline now checks the `updated_at` watermark and only loads records
modified since the last successful run.

## Why
Full reload takes 45 minutes. Incremental takes ~2 minutes. Required
for SLA compliance after the data grew >10M rows.

## How to test
- [ ] Run `python3 -m pytest tests/test_orders_etl.py`
- [ ] Trigger pipeline with INCREMENTAL=true in staging
- [ ] Compare row counts: incremental vs full load match

## Risks
- First run after deployment still does full reload
- updated_at must not be NULL (validation added)
```

**Title rules** (same as commit messages): imperative mood, under ~72
characters, specific — "Add retry logic to S3 upload", not "update pipeline".

**Review process:** author opens PR → reviewers comment (line-level or
general) → author addresses or explains → reviewer approves or requests
changes → someone merges per team policy.

Good review comments name a concrete failure, not just a style preference:
`"This throws a KeyError if user_id is missing — consider .get()"` beats
`"looks off"`.

**Merge strategies:**
| Strategy | Effect | Best when |
|---|---|---|
| Squash and merge | all branch commits → 1 commit on main | branch has messy WIP commits (most teams default here) |
| Merge commit | preserves full branch history + a merge commit | you want to see exactly when a feature landed |
| Rebase and merge | replays commits linearly, no merge commit | commits are already clean and atomic |

---

## 4. GitHub CLI — try these on your scratch repo

```bash
gh repo view                  # info in the terminal
gh repo view --web            # open in browser
```

```bash
gh pr create --title "Add pipeline transform stub" --body "Testing the PR workflow."
gh pr create --draft          # not ready for review yet, just visible
gh pr list                    # all open PRs
```
**Checkpoint:** the PR you just created shows up in `gh pr list`.

```bash
gh pr view <number>
gh pr view <number> --web
gh pr checkout <number>       # pull the PR's branch down locally — great for reviewing
gh pr review <number> --approve
gh pr merge <number> --squash --delete-branch
```

```bash
gh issue create --title "Orders pipeline fails on empty result set" --body "Steps to reproduce..."
gh issue list
gh issue close <number> --reason completed
```

```bash
gh run list                   # recent CI workflow runs (needs a repo with Actions configured)
gh run watch <id>             # stream a running job's logs live
gh run view <id> --log
gh workflow list
gh workflow run ci.yml
```

---

## 5. Git workflows for data teams

**Trunk-based development (recommended for most data teams):** one `main`,
short-lived feature branches (< 2 days), merge often.
```
main
└── feature/x   (from main, merged within a day or two)
└── bugfix/y    (from main, merged within hours)
```
Rules: keep branches short, use feature flags for incomplete work, CI must
pass before merge, require 1-2 approvals. Benefit: no "merge hell" from
long-lived divergent branches, main is always deployable.

**Gitflow (for versioned releases):** heavier structure —
`main` (tagged releases only), `develop` (integration), `release/x.y`,
`feature/x` (from develop), `hotfix/x` (from main, merges to both). Good
for software with multiple versions in production at once; overkill for a
modern data pipeline that just ships continuously — use trunk-based instead.

---

## 6. Tags and releases

```bash
git tag v1.0.0                                              # lightweight — just a pointer
git tag -a v1.0.0 -m "Release v1.0.0 — stable users and orders ETL"  # annotated — preferred, has message/author/date
git tag                                                      # list all tags
git show v1.0.0                                              # what it points to
git push origin v1.0.0                                       # tags aren't pushed by plain `git push`
git push origin --tags                                       # push all tags
git checkout v1.0.0                                          # detached HEAD at that tag
```

```bash
gh release create v1.0.0 --title "v1.0.0 - Stable ETL" --notes "Changelog here"
gh release create v1.0.0 --generate-notes    # auto-generate from merged PRs
```

**Semantic versioning:** `MAJOR.MINOR.PATCH` — MAJOR = breaking change
(e.g. schema change), MINOR = new backward-compatible functionality,
PATCH = bug fix. Some data teams prefer date-based tags instead
(`v2024.06.10`) since it's obvious when something deployed.

---

## 7. Automating GitHub from Python

For scripted PR/CI/issue automation (Slack bots, CI status reporters,
auto-filed bug tickets), see the companion script:
[`03b_pygithub_examples.py`](03b_pygithub_examples.py) — real, runnable
PyGithub code, not just examples to read.

---

## Done — clean up

```bash
gh repo delete git-practice-scratch --yes
```

## Quick reference

```bash
# Remotes
git remote -v                       git remote add origin <url>
git push -u origin branch-name      git fetch --prune
git pull --rebase

# gh CLI
gh pr create --title "..." --body "..."   gh pr list
gh pr checkout 42                         gh pr merge 42 --squash
gh run list                               gh run watch <id>
gh issue create --title "..."             gh auth login

# Tags
git tag -a v1.0.0 -m "message"      git push origin v1.0.0
git push origin --tags

# Workflows
Trunk-based: short branches (<2 days), merge often, CI gates
Gitflow: main/develop/release/hotfix (for versioned software)
```

## Before moving on

- [ ] You pushed a branch, opened a real PR with `gh pr create`, and merged it.
- [ ] You can explain squash vs merge-commit vs rebase-and-merge and when to use each.
- [ ] You created an annotated tag and pushed it.
- [ ] You deleted the scratch repo.

Next: `concepts/04_gitignore_and_data_project_hygiene.md`
