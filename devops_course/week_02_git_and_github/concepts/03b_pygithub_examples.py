"""
Automating GitHub from Python — PyGithub
=========================================
Companion to 03_github_prs_and_workflows.md, section 7.

Unlike the rest of week 2, this genuinely needs to be a .py file: it's
demonstrating a Python library's API, not a sequence of shell commands.

Use cases: CI status reporting, PR-age monitoring, auto-filing issues from
a failed pipeline run, Slack digests of open PRs.

Setup:
    pip install PyGithub
    export GITHUB_TOKEN=$(gh auth token)      # reuse gh CLI's stored token
    export GITHUB_REPO=yourorg/data-pipelines # org/repo to inspect

Run:
    python3 concepts/03b_pygithub_examples.py
"""

import os
import sys
from datetime import datetime, timezone


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPO")

    if not token or not repo_name:
        print(__doc__)
        print("Set GITHUB_TOKEN and GITHUB_REPO to run this against a real repo.")
        print("Example:")
        print("  export GITHUB_TOKEN=$(gh auth token)")
        print("  export GITHUB_REPO=yourorg/data-pipelines")
        sys.exit(0)

    try:
        from github import Github
    except ImportError:
        print("PyGithub isn't installed. Run: pip install PyGithub")
        sys.exit(1)

    g = Github(token)
    repo = g.get_repo(repo_name)

    # ------------------------------------------------------------------
    # 1. List open PRs
    # ------------------------------------------------------------------
    print(f"\nOpen Pull Requests in {repo_name}:")
    open_prs = list(repo.get_pulls(state="open", sort="created"))
    if not open_prs:
        print("  (none)")
    for pr in open_prs:
        print(f"  #{pr.number}: {pr.title}")
        print(f"    Author: {pr.user.login}")
        print(f"    Branch: {pr.head.ref} -> {pr.base.ref}")
        print(f"    URL:    {pr.html_url}")

    # ------------------------------------------------------------------
    # 2. CI status for the most recent open PR
    # ------------------------------------------------------------------
    if open_prs:
        pr = open_prs[0]
        commit = repo.get_commit(pr.head.sha)
        print(f"\nCI status for PR #{pr.number}:")
        statuses = list(commit.get_combined_status().statuses)
        if not statuses:
            print("  (no status checks reported)")
        for status in statuses:
            print(f"  {status.context}: {status.state}")

    # ------------------------------------------------------------------
    # 3. Flag PRs open longer than N days
    # ------------------------------------------------------------------
    stale_after_days = 3
    now = datetime.now(timezone.utc)
    print(f"\nPRs open longer than {stale_after_days} days:")
    stale = [pr for pr in open_prs if (now - pr.created_at).days > stale_after_days]
    if not stale:
        print("  (none)")
    for pr in stale:
        age_days = (now - pr.created_at).days
        print(f"  WARNING: PR #{pr.number} open for {age_days} days: {pr.title}")


def create_issue_on_pipeline_failure(repo, pipeline_name, run_id, error_message, log_url):
    """Example of the write side: file an issue when a pipeline run fails.

    Not called by main() — this is here as a reference snippet for wiring
    into a CI failure hook or an orchestrator's on-failure callback.
    """
    repo.create_issue(
        title=f"Pipeline test failure: {pipeline_name}",
        body=f"Run ID: {run_id}\nError: {error_message}\nLogs: {log_url}",
        labels=["bug", "pipeline"],
        assignees=["oncall-engineer"],
    )


if __name__ == "__main__":
    main()
