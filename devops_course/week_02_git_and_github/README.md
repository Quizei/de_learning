# Week 2: Git and GitHub for Data Engineers

## What This Week Covers

Version control is the foundation of collaborative engineering.
Every pipeline change, every schema migration, every dbt model update —
it all belongs in git. This week teaches you how to use git like a professional.

## Topics

### Concept 1 — Git Fundamentals
- What git is: the three-area model (working tree → staging area → repository)
- `git init`, `git clone` — start a repo from scratch or from a URL
- `git status` — reading the output (untracked, modified, staged)
- `git add file`, `git add -p` (stage by hunk), `git add .`
- `git commit -m "message"` — what makes a good commit message (imperative, why not what)
- `git log --oneline --graph`, `git log -p`, `git log --follow file`
- `git diff` (unstaged), `git diff --staged`, `git diff HEAD~1`
- `git show <commit>`, `git blame file` — find who changed what line
- Undoing things: `git restore`, `git restore --staged`, `git revert`, `git reset --soft`, `git reset --hard`
- `git stash push -m "wip: ..."`, `git stash pop`, `git stash list`, `git stash drop`

### Concept 2 — Branching and Merging
- What branches actually are: lightweight pointers (creating one is instant)
- `git branch`, `git branch -a`, `git branch -d`
- `git checkout -b feature/name`, `git switch` (modern alternative)
- HEAD and detached HEAD state — what it means and how to escape it
- Fast-forward merge vs three-way merge (with ASCII commit graphs)
- `git merge --no-ff`, `git merge --squash`
- Rebase: `git rebase main` — replay commits on new base for linear history
- Interactive rebase: `git rebase -i HEAD~3` — squash, reorder, reword, drop
- Golden rule: NEVER rebase public/shared branches
- Conflict resolution step by step: markers, edit, `git add`, `git commit`
- `git cherry-pick <hash>` — apply one commit to another branch

### Concept 3 — GitHub, Pull Requests, and Workflows
- Remotes: origin, upstream, tracking branches
- `git push -u origin branch`, `git fetch`, `git pull --rebase`
- Pull Request anatomy: title, description template, review process
- Merge strategies: squash merge, merge commit, rebase merge — when to use each
- GitHub CLI (`gh`): create PRs, list issues, watch CI — all from the terminal
- `gh pr create`, `gh pr list`, `gh pr checkout`, `gh pr merge --squash`
- `gh run list`, `gh run watch` — monitor CI in your terminal
- Team git workflows: trunk-based development (recommended) vs Gitflow
- Tags and releases: `git tag -a v1.0.0`, `gh release create`
- PyGitHub API: list PRs, check CI status, create issues programmatically

### Concept 4 — .gitignore and Data Project Hygiene
- `.gitignore` pattern syntax: `*` glob, `**` recursive, `!` negation
- Complete `.gitignore` for a data engineering project (Python + dbt + notebooks + .env)
- The Jupyter notebook problem: cell outputs bloat git history
- `nbstripout`: strips outputs before every commit (transparent git filter)
- Large files: git is NOT designed for data files > 50MB — use S3/GCS
- Git LFS: pointer in git, file stored externally (when you must)
- Secrets hygiene: the most critical section — what happens when a key leaks
- `detect-secrets` and `pre-commit`: hooks that BLOCK credential commits
- Incident response: rotate credentials immediately, then `git filter-repo`
- `.pre-commit-config.yaml`: black, ruff, nbstripout, detect-secrets, no-commit-to-branch
- `.gitattributes`: normalize line endings (`text=auto eol=lf`), binary markers

## Folder Structure

```
week_02_git_and_github/
  concepts/
    01_git_fundamentals.md             — walkthrough: type every command yourself
    02_branching_and_merging.md        — walkthrough: branches, merges, rebase, conflicts
    03_github_prs_and_workflows.md     — walkthrough: push/pull, PRs, gh CLI, workflows
    03b_pygithub_examples.py           — run me: real PyGithub API calls (needs GITHUB_TOKEN)
    04_gitignore_and_data_project_hygiene.md  — walkthrough: .gitignore, pre-commit, secrets
  practice/
    exercises.py                       — run me: builds practice_repo/ with real history
    exercises.md                       — 7 hands-on exercises, solutions collapsed till you try
  projects/
    git_workflow_simulator.py          — interactive step-by-step workflow simulation
```

Concepts 1-4 are markdown walkthroughs, not scripts: you type every git
command yourself in your own terminal, with a checkpoint after each one
telling you what to expect. Nothing runs it for you — that's the point.
The one exception is `03b_pygithub_examples.py`, which stays a real script
because it demonstrates a Python library's API, not shell commands.

## How to Use This Week

1. Work through each walkthrough in order, typing every command yourself:
   ```bash
   open concepts/01_git_fundamentals.md
   open concepts/02_branching_and_merging.md
   open concepts/03_github_prs_and_workflows.md
   open concepts/04_gitignore_and_data_project_hygiene.md
   ```
   Concept 3's PyGithub section has a real companion script:
   ```bash
   export GITHUB_TOKEN=$(gh auth token)
   export GITHUB_REPO=yourorg/data-pipelines
   python3 concepts/03b_pygithub_examples.py
   ```

2. Build the practice repo, then work through the exercises yourself:
   ```bash
   python3 practice/exercises.py    # creates practice_repo/ with full history
   open practice/exercises.md       # 7 exercises — try each before expanding its solution
   ```

3. Run the workflow simulator (interactive, press ENTER to advance):
   ```bash
   python3 projects/git_workflow_simulator.py
   ```

## Practice Goals

- [ ] Make a commit, write a good message, use `git log --graph` to see it
- [ ] Create a branch, commit on it, merge back to main — both fast-forward and three-way
- [ ] Cause a merge conflict deliberately, resolve it, and complete the merge
- [ ] Use `git stash` to save WIP, switch branches, come back and pop the stash
- [ ] Write a complete `.gitignore` for a data project from memory
- [ ] Use `git restore` and `git reset --soft` to undo mistakes without panicking

## Key Commands Cheat Sheet

```bash
# Setup
git init                            start a new local repo
git clone <url>                     copy a repo

# Status and inspect
git status                          what's changed?
git status -s                       short format
git log --oneline --graph --all     pretty history with branches
git log --oneline -- pipeline.py    commits touching one file
git diff                            unstaged changes
git diff --staged                   what's about to be committed
git show <hash>                     full commit details
git blame file.py                   who changed each line

# Stage and commit
git add file.py                     stage a file
git add -p file.py                  stage interactively by hunk
git commit -m "message"             commit staged changes

# Branches
git checkout -b feature/name        create + switch to branch
git switch main                     switch to existing branch
git branch -a                       list all branches
git branch -d feature/name          delete merged branch

# Merge and rebase
git merge feature/name              merge branch into current
git merge --no-ff feature/name      force merge commit
git rebase main                     replay current branch onto main
git rebase -i HEAD~3                interactive rebase (squash/edit)

# Undo
git restore file.py                 discard working tree changes
git restore --staged file.py        unstage a file
git revert <hash> --no-edit         safe undo (new commit)
git reset --soft HEAD~1             undo commit, keep staged

# Stash
git stash push -m "wip: ..."        save work in progress
git stash list                      see all stashes
git stash pop                       restore most recent

# Remote
git push -u origin branch-name      push + set tracking
git fetch origin                    download without merging
git pull --rebase                   fetch + rebase (clean history)
git remote -v                       show configured remotes

# Tags
git tag -a v1.0.0 -m "message"     create annotated tag
git push origin --tags              push all tags to remote

# GitHub CLI
gh pr create --title "..." --body "..."
gh pr list
gh pr checkout 42
gh pr merge 42 --squash --delete-branch
gh run list
gh run watch <run-id>

# Hygiene
git check-ignore -v file.csv        why is this file ignored?
git log --all --full-history -- .env  was .env ever committed?
```
