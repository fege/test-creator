#!/usr/bin/env python3
"""CLI for repository discovery, management, and artifact publishing.

Skills call this script to find repositories, clone them, publish test plan artifacts, and load test context.

Usage:
    # Find a repository in common locations
    uv run python scripts/repo.py find <repo_name>
    # Outputs: /absolute/path/to/repo (or empty if not found)
    # Exit code: 0 if found, 1 if not found

    # Find a known repository (odh-test-context, tiger-team)
    uv run python scripts/repo.py find-known <repo_type>
    # Outputs JSON: {"path": "/path/to/repo", "url": "https://..."}
    # Exit code: 0 if found, 1 if not found

    # Find a target repository (handles org/repo format)
    uv run python scripts/repo.py find-target <repo_name>
    # Outputs: /absolute/path/to/repo (or empty if not found)
    # Exit code: 0 if found, 1 if not found

    # Clone a repository
    uv run python scripts/repo.py clone <repo_url> <target_path>
    # Outputs: /absolute/path/to/cloned/repo
    # Exit code: 0 if success, 1 if failed

    # Locate feature directory from various source types
    uv run python scripts/repo.py locate-feature-dir <source>
    # Outputs JSON: {"feature_dir": "/path", "source_type": "local|github", "repo_owner": "...", "repo_name": "..."}
    # Exit code: 0 if success, 1 if failed

    # Validate local path is outside the plugin and inside a Fullsend target, if set.
    uv run python scripts/repo.py validate-local-path <path> [--force]
    # Exit code: 0 if valid, 1 if invalid (in skill repo)

    # Validate remote repository is not the delivered skill repository.
    uv run python scripts/repo.py validate-remote <owner/repo>
    # Exit code: 0 if valid, 1 if invalid (is skill repo)

    # Safely checkout branch with uncommitted changes check and stale branch detection
    uv run python scripts/repo.py safe-checkout <repo_path> <branch> [--remote <remote_name>]
    # Exit code: 0 if success, 1 if uncommitted changes or git error

    # Fetch all review comments from a PR (conversation + inline, bots filtered)
    uv run python scripts/repo.py pr-comments <owner/repo> <pr_number>
    # Outputs JSON: [{"author": "...", "body": "...", "type": "conversation|review|inline", ...}]
    # Exit code: 0 if success, 1 if gh CLI fails

    # Create a PR or detect an existing one for a branch
    uv run python scripts/repo.py pr-create <target_repo> <branch> <title> <body> [--reviewers user1,user2]
    # Outputs JSON: {"pr_url": "...", "pr_number": N, "created": true/false}
    # Exit code: 0 if success, 1 if gh CLI fails

    # Stage, check for changes, and commit test plan artifacts in one call
    uv run python scripts/repo.py publish-artifacts <repo_path> <feature_name> <message>
    # Outputs JSON: {"staged_files": [...], "skipped_files": [...], "committed": true/false, "message": "..."}
    # Exit code: 0 if success, 1 if required files missing or commit failed

    # Stage test plan artifacts selectively (used internally by publish-artifacts)
    uv run python scripts/repo.py stage <repo_path> <feature_name>
    # Outputs JSON: {"staged_files": [...], "skipped_files": [...]}
    # Exit code: 0 if success, 1 if required files missing

Examples:
    uv run python scripts/repo.py find opendatahub-test-plans
    uv run python scripts/repo.py find-known odh-test-context
    uv run python scripts/repo.py find-target opendatahub-io/odh-dashboard
    uv run python scripts/repo.py clone <github-url> ~/Code/repo
    uv run python scripts/repo.py locate-feature-dir ~/Code/repo/plans/feature
    uv run python scripts/repo.py locate-feature-dir <pr-url>
    uv run python scripts/repo.py validate-local-path /tmp/test-validation
    uv run python scripts/repo.py validate-remote org/repo
    uv run python scripts/repo.py safe-checkout ~/Code/repo branch
    uv run python scripts/repo.py safe-checkout ~/Code/repo branch --remote target
    uv run python scripts/repo.py publish-artifacts ~/Code/repo feature "msg"
    uv run python scripts/repo.py stage ~/Code/repo feature
    uv run python scripts/repo.py pr-create org/repo branch "Title" "Body"
    uv run python scripts/repo.py pr-comments org/repo 10
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.utils.error_utils import exit_error, exit_error_multiline
from scripts.utils.repo_utils import (
    clone_repo,
    find_known_repo,
    find_repo_in_common_locations,
    find_target_repo,
    get_git_remote,
    get_git_root,
)


def cmd_find(args):
    """Find repository in common locations."""
    result = find_repo_in_common_locations(args.repo_name)
    if result:
        print(result)
        return 0
    else:
        return 1


def cmd_find_known(args):
    """Find known repository (odh-test-context, tiger-team)."""
    try:
        path, url = find_known_repo(args.repo_type)
        result = {"path": path, "url": url}
        print(json.dumps(result, indent=2))
        return 0 if path else 1
    except ValueError as e:
        exit_error(f"Error: {e}")


def cmd_find_target(args):
    """Find target repository (handles org/repo format)."""
    result = find_target_repo(args.repo_name)
    if result:
        print(result)
        return 0
    else:
        return 1


def cmd_clone(args):
    """Clone repository."""
    result = clone_repo(args.repo_url, args.target_path)
    if result:
        print(result)
        return 0
    else:
        exit_error(f"Failed to clone {args.repo_url}")


def cmd_locate_feature_dir(args):
    """Locate test plan feature directory from various source types."""
    source = args.source

    # GitHub PR URL: https://github.com/owner/repo/pull/123
    pr_match = re.match(r"^https://github.com/([^/]+)/([^/]+)/pull/(\d+)$", source)
    if pr_match:
        owner, repo, pr_number = pr_match.groups()
        return _handle_github_pr(owner, repo, pr_number)

    # GitHub branch URL: https://github.com/owner/repo/tree/branch-name
    branch_match = re.match(r"^https://github.com/([^/]+)/([^/]+)/tree/(.+)$", source)
    if branch_match:
        owner, repo, branch = branch_match.groups()
        return _handle_github_branch(owner, repo, branch)

    # Local directory path
    return _handle_local_path(source)


def _handle_github_pr(owner, repo, pr_number):
    """Handle GitHub PR URL - fetch branch name and process."""
    try:
        # Fetch PR metadata to get branch name
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--repo", f"{owner}/{repo}", "--json", "headRefName"],
            capture_output=True,
            text=True,
            check=True,
        )
        pr_data = json.loads(result.stdout)
        branch_name = pr_data["headRefName"]

        return _handle_github_branch(owner, repo, branch_name)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        exit_error(f"ERROR: Failed to fetch PR {pr_number}: {e}")


def stage_artifacts(repo_path, feature_name):
    """Selectively stage test plan artifacts for commit.

    Stages required files (TestPlan.md, README.md) and optional files
    (TestPlanGaps.md, TestPlanReview.md, .source-design-spec.md, test_cases/*.md)
    if they exist.

    Args:
        repo_path: Path to git repository root
        feature_name: Name of the feature directory (basename)

    Returns:
        (exit_code, result_dict) where result_dict contains:
        - staged_files: list of staged relative paths
        - skipped_files: list of skipped relative paths
        - error: error message (only on failure)
    """
    feature_dir = Path(repo_path) / feature_name
    staged = []
    skipped = []

    required = ["TestPlan.md", "README.md"]
    for name in required:
        if not (feature_dir / name).is_file():
            return 1, {"error": f"{name} not found in {feature_name}/"}

    optional = ["TestPlanGaps.md", "TestPlanReview.md", ".source-design-spec.md"]

    for name in required + optional:
        rel = f"{feature_name}/{name}"
        if (feature_dir / name).is_file():
            try:
                subprocess.run(
                    ["git", "add", rel],
                    cwd=repo_path,
                    capture_output=True,
                    check=True,
                )
                staged.append(rel)
            except subprocess.CalledProcessError as e:
                return 1, {"error": f"git add failed for {rel}: {e}"}
        else:
            skipped.append(rel)

    tc_dir = feature_dir / "test_cases"
    if tc_dir.is_dir():
        for md_file in tc_dir.glob("*.md"):
            rel = f"{feature_name}/test_cases/{md_file.name}"
            try:
                subprocess.run(
                    ["git", "add", rel],
                    cwd=repo_path,
                    capture_output=True,
                    check=True,
                )
                staged.append(rel)
            except subprocess.CalledProcessError as e:
                return 1, {"error": f"git add failed for {rel}: {e}"}
    else:
        skipped.append(f"{feature_name}/test_cases/")

    return 0, {"staged_files": staged, "skipped_files": skipped}


def publish_artifacts(repo_path, feature_name, message):
    """Stage test plan artifacts, check for changes, and commit.

    Combines stage + has-changes + commit into a single deterministic
    operation. Push is left to the caller since remote/branch varies.

    Args:
        repo_path: Path to git repository root
        feature_name: Name of the feature directory (basename)
        message: Commit message

    Returns:
        (exit_code, result_dict) where result_dict contains:
        - staged_files: list of staged relative paths
        - skipped_files: list of skipped relative paths
        - committed: bool (False if no changes to commit)
        - message: commit message (only if committed)
        - error: error message (only on failure)
    """
    exit_code, stage_result = stage_artifacts(repo_path, feature_name)
    if exit_code != 0:
        return exit_code, stage_result

    has_changes = (
        subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_path,
            capture_output=True,
        ).returncode
        != 0
    )

    if not has_changes:
        return 0, {**stage_result, "committed": False}

    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return 1, {**stage_result, "committed": False, "error": f"git commit failed: {e}"}

    return 0, {**stage_result, "committed": True, "message": message}


def pr_create(target_repo, branch, title, body, reviewers=None):
    """Create a PR or detect an existing one for the given branch.

    Args:
        target_repo: Target repository in owner/repo format
        branch: Branch name (e.g., test-plan/RHAISTRAT-400)
        title: PR title
        body: PR body (markdown)
        reviewers: Comma-separated reviewer usernames (optional)

    Returns:
        (exit_code, result_dict) where result_dict contains:
        - pr_url: URL of the created or existing PR
        - pr_number: PR number
        - created: bool (True if new PR, False if existing)
        - error: error message (only on failure)
    """
    try:
        list_result = subprocess.run(
            ["gh", "pr", "list", "--repo", target_repo, "--head", branch, "--json", "number,url"],
            capture_output=True,
            text=True,
            check=True,
        )
        existing = json.loads(list_result.stdout.strip())

        if existing:
            pr = existing[0]
            return 0, {
                "pr_url": pr["url"],
                "pr_number": pr["number"],
                "created": False,
            }

        create_cmd = [
            "gh",
            "pr",
            "create",
            "--repo",
            target_repo,
            "--title",
            title,
            "--body",
            body,
            "--base",
            "main",
            "--head",
            branch,
        ]
        if reviewers:
            create_cmd.extend(["--reviewer", reviewers])

        create_result = subprocess.run(
            create_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        pr_url = create_result.stdout.strip()
        pr_number_match = re.search(r"/pull/(\d+)", pr_url)
        if not pr_number_match:
            return 1, {"error": f"Could not parse PR number from: {pr_url}"}
        return 0, {
            "pr_url": pr_url,
            "pr_number": int(pr_number_match.group(1)),
            "created": True,
        }

    except subprocess.CalledProcessError as e:
        return 1, {"error": f"GitHub CLI failed: {e.stderr or e}"}
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return 1, {"error": f"Failed to parse gh output: {e}"}


def _gh_api_paginated(endpoint):
    """Call gh api --paginate with --jq '.[]' to avoid JSON concatenation bugs.

    gh api --paginate concatenates raw JSON arrays ('[...][...]') when results
    span multiple pages. Using --jq '.[]' flattens each page into NDJSON,
    which we parse line-by-line and collect into a single list.
    """
    result = subprocess.run(
        ["gh", "api", "--paginate", "--jq", ".[]", endpoint],
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = result.stdout.strip()
    if not stdout:
        return []
    return [json.loads(line) for line in stdout.splitlines()]


def pr_comments(repo, pr_number):
    """Fetch all review comments from a PR.

    Merges conversation comments, formal reviews, and inline comments.
    Filters out bot accounts (usernames ending with [bot]).

    Args:
        repo: Repository in owner/repo format
        pr_number: PR number

    Returns:
        (exit_code, comments_list) where each comment has:
        - author: username
        - body: comment text
        - type: "conversation", "review", or "inline"
        - path: file path (inline only)
        - line: line number (inline only)
    """
    try:
        conv_data = _gh_api_paginated(f"repos/{repo}/issues/{pr_number}/comments")
        review_data = _gh_api_paginated(f"repos/{repo}/pulls/{pr_number}/reviews")
        inline_data = _gh_api_paginated(f"repos/{repo}/pulls/{pr_number}/comments")

    except subprocess.CalledProcessError as e:
        return 1, {"error": f"GitHub CLI failed: {e.stderr or e}"}
    except json.JSONDecodeError as e:
        return 1, {"error": f"Failed to parse gh output: {e}"}

    comments = []

    for c in conv_data:
        author = c.get("user", {}).get("login", "")
        if author.endswith("[bot]"):
            continue
        comments.append(
            {
                "author": author,
                "body": c.get("body", ""),
                "type": "conversation",
            }
        )

    for r in review_data:
        author = r.get("user", {}).get("login", "")
        if author.endswith("[bot]"):
            continue
        body = r.get("body", "")
        if not body:
            continue
        comments.append(
            {
                "author": author,
                "body": body,
                "type": "review",
            }
        )

    for ic in inline_data:
        author = ic.get("user", {}).get("login", "")
        if author.endswith("[bot]"):
            continue
        comments.append(
            {
                "author": author,
                "body": ic.get("body", ""),
                "type": "inline",
                "path": ic.get("path", ""),
                "line": ic.get("line"),
            }
        )

    return 0, comments


def safe_checkout_branch(repo_path, branch, remote="origin"):
    """Safely checkout a branch with safety checks.

    Performs:
    - Uncommitted changes check (fails if dirty)
    - Stale branch detection (warns and updates if behind remote)
    - Creates tracking branch if doesn't exist locally
    - Pulls latest changes

    Args:
        repo_path: Path to git repository
        branch: Branch name to checkout
        remote: Remote name (default: "origin")

    Returns:
        0 on success, 1 on error
    """
    try:
        # Check for dirty working tree
        status_result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True, check=True
        )

        if status_result.stdout.strip():
            # Uncommitted changes found
            print(f"ERROR: Cannot checkout branch - uncommitted changes in {repo_path}", file=sys.stderr)
            print("Please commit or stash your changes first:", file=sys.stderr)
            print("  git stash", file=sys.stderr)
            print("  # or", file=sys.stderr)
            print("  git add . && git commit -m 'WIP'", file=sys.stderr)
            return 1

        # Fetch latest from remote
        subprocess.run(["git", "fetch", remote], cwd=repo_path, check=True, capture_output=True)

        # Check if branch exists locally
        local_branch_exists = (
            subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_path, capture_output=True
            ).returncode
            == 0
        )

        if local_branch_exists:
            # Check if local branch is stale (behind remote)
            local_sha = subprocess.run(
                ["git", "rev-parse", branch], cwd=repo_path, capture_output=True, text=True, check=True
            ).stdout.strip()

            remote_sha = subprocess.run(
                ["git", "rev-parse", f"{remote}/{branch}"], cwd=repo_path, capture_output=True, text=True, check=True
            ).stdout.strip()

            if local_sha != remote_sha:
                print(f"⚠️  Local branch '{branch}' is stale. Updating...", file=sys.stderr)

            # Checkout and pull
            subprocess.run(["git", "checkout", branch], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "pull", remote, branch], cwd=repo_path, check=True, capture_output=True)
        else:
            # Branch doesn't exist locally, create tracking branch
            subprocess.run(
                ["git", "checkout", "-b", branch, f"{remote}/{branch}"], cwd=repo_path, check=True, capture_output=True
            )

        return 0

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git operations failed: {e}", file=sys.stderr)
        return 1


def _handle_github_branch(owner, repo, branch):
    """Handle GitHub branch - find/clone repo, checkout branch safely, find TestPlan.md.

    Safety: Checks for uncommitted changes before checkout to prevent data loss.
    """
    repo_path = find_repo_in_common_locations(repo)

    if repo_path:
        # Repo exists locally - use safe checkout
        if safe_checkout_branch(repo_path, branch, remote="origin") != 0:
            exit_error("Branch checkout failed")
    else:
        # Clone repo to ~/Code
        repo_url = f"https://github.com/{owner}/{repo}.git"
        target_path = os.path.expanduser(f"~/Code/{repo}")
        repo_path = clone_repo(repo_url, target_path)
        if not repo_path:
            exit_error(f"ERROR: Failed to clone {repo_url}")

        # Checkout branch
        try:
            subprocess.run(["git", "checkout", branch], cwd=repo_path, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            exit_error(f"ERROR: Failed to checkout branch {branch}: {e}")

    # Find TestPlan.md in the repository (pass branch for disambiguation)
    feature_dir = _find_testplan_in_repo(repo_path, branch_hint=branch)
    if not feature_dir:
        exit_error_multiline(
            [
                f"ERROR: TestPlan.md not found in {repo_path}",
                "",
                "Please check that the repository has a valid test plan directory.",
            ]
        )

    # Output results
    result = {"feature_dir": feature_dir, "source_type": "github", "repo_owner": owner, "repo_name": repo}
    print(json.dumps(result, indent=2))
    return 0


def _handle_local_path(path):
    """Handle local directory path - validate and return."""
    # Expand ~ to home directory
    path = os.path.expanduser(path)

    # Convert to absolute path
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    # Verify TestPlan.md exists
    testplan_path = os.path.join(path, "TestPlan.md")
    if not os.path.isfile(testplan_path):
        exit_error(f"ERROR: TestPlan.md not found at {path}")

    # Output results
    result = {"feature_dir": path, "source_type": "local"}
    print(json.dumps(result, indent=2))
    return 0


def _find_testplan_in_repo(repo_path, branch_hint=None):
    """Find TestPlan.md in repository (may be in subdirectory).

    Args:
        repo_path: Path to repository
        branch_hint: Optional branch name to help disambiguate (e.g., "test-plan/RHAISTRAT-1507")

    Returns the directory containing TestPlan.md, or None if not found.
    If multiple TestPlan.md exist, uses branch_hint to match source_key in frontmatter.
    """
    repo_path = Path(repo_path)

    # Search for all TestPlan.md files
    testplans = list(repo_path.rglob("TestPlan.md"))

    if not testplans:
        return None

    if len(testplans) == 1:
        # Only one found, no ambiguity
        return str(testplans[0].parent)

    # Multiple TestPlan.md files - try to disambiguate using branch_hint
    if branch_hint:
        # Extract issue key from branch name (e.g., "RHAISTRAT-1507" from "test-plan/RHAISTRAT-1507")
        issue_key_match = re.search(r"(RHAISTRAT|RHOAIENG|RHODA)-\d+", branch_hint)
        if issue_key_match:
            issue_key = issue_key_match.group(0)

            # Search for TestPlan.md with matching source_key in frontmatter
            for testplan in testplans:
                try:
                    content = testplan.read_text()
                    # Quick check for source_key in frontmatter
                    if f"source_key: {issue_key}" in content[:500]:
                        return str(testplan.parent)
                except Exception:
                    continue

    # Multiple features found and couldn't disambiguate
    relative_paths = [str(t.relative_to(repo_path)) for t in testplans]
    print(f"ERROR: Multiple TestPlan.md files found in {repo_path}:", file=sys.stderr)
    for path in sorted(relative_paths):
        print(f"  - {path}", file=sys.stderr)
    print(file=sys.stderr)
    print("Please specify the feature directory explicitly:", file=sys.stderr)
    print(f"  Example: {repo_path}/{Path(relative_paths[0]).parent}", file=sys.stderr)
    return None


def cmd_validate_local_path(args):
    """Validate a local path against protected package source and Fullsend artifacts."""
    path = args.path
    force = args.force

    runtime_root = os.environ.get("FULLSEND_TARGET_REPO_DIR")

    # The script location identifies the delivered plugin when Claude's
    # Markdown-only skill token is not exported into the process environment.
    skill_dir = os.environ.get("CLAUDE_SKILL_DIR")
    skill_root_path = Path(skill_dir).resolve().parent.parent if skill_dir else Path(__file__).resolve().parent.parent

    # Get absolute path of target directory
    path_abs = Path(os.path.expanduser(path)).resolve()

    if runtime_root:
        output_root = Path(runtime_root).expanduser().resolve()
        task_words = os.environ.get("FULLSEND_TASK", "").split(maxsplit=1)
        fullsend_task = task_words[0] if task_words else ""
        if output_root == skill_root_path:
            if fullsend_task not in {"/test-plan-create", "/test-plan-create-cases"}:
                print(
                    "❌ ERROR: The producer checkout is a Fullsend target only for create/cases tasks",
                    file=sys.stderr,
                )
                return 1
            if not path_abs.is_relative_to(output_root):
                print(
                    "❌ ERROR: Fullsend create/cases output must stay in the producer checkout",
                    file=sys.stderr,
                )
                return 1
            return 0
        if (
            output_root.is_relative_to(skill_root_path)
            or skill_root_path.is_relative_to(output_root)
            or not path_abs.is_relative_to(output_root)
        ):
            print("❌ ERROR: Output path must stay in the separate Fullsend target workspace", file=sys.stderr)
            return 1

    if path_abs.is_relative_to(skill_root_path):
        print(f"❌ ERROR: Cannot create artifacts in skill repository ({skill_root_path})", file=sys.stderr)
        print("Please specify a different directory.", file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Use --output-dir flag to force creation in current directory if needed.", file=sys.stderr)
        return 1

    # --force selects a contributor's output path; it never authorizes writes
    # into the delivered plugin or outside a Fullsend target workspace.
    if force:
        return 0

    return 0


def cmd_validate_remote_repo(args):
    """Validate that a remote repository is NOT the skill repository."""
    repo = args.repo

    # Preserve an explicit selected skill while supporting an unexported token.
    skill_dir = os.environ.get("CLAUDE_SKILL_DIR")
    skill_parent = Path(skill_dir).resolve().parent.parent if skill_dir else Path(__file__).resolve().parent.parent
    skill_root = get_git_root(str(skill_parent))

    if not skill_root:
        # Can't detect skill repo, allow
        return 0

    skill_remote = get_git_remote(skill_root)

    if not skill_remote:
        # Can't detect skill repo remote, allow
        return 0

    # Check if target repo matches skill repo
    if repo == skill_remote:
        print(f"❌ ERROR: Cannot publish to skill repository ({skill_remote})", file=sys.stderr)
        print("Test plans must be published to a separate repository.", file=sys.stderr)
        return 1

    return 0


def cmd_pr_comments(args):
    """Fetch all review comments from a PR."""
    exit_code, result = pr_comments(args.repo, args.pr_number)
    print(json.dumps(result, indent=2))
    return exit_code


def cmd_pr_create(args):
    """Create a PR or detect an existing one."""
    exit_code, result = pr_create(
        args.target_repo,
        args.branch,
        args.title,
        args.body,
        reviewers=args.reviewers,
    )
    print(json.dumps(result, indent=2))
    return exit_code


def cmd_publish_artifacts(args):
    """Stage test plan artifacts, check for changes, and commit."""
    repo_path = os.path.expanduser(args.repo_path)
    exit_code, result = publish_artifacts(repo_path, args.feature_name, args.message)
    print(json.dumps(result, indent=2))
    return exit_code


def cmd_stage(args):
    """Stage test plan artifacts selectively."""
    repo_path = os.path.expanduser(args.repo_path)
    exit_code, result = stage_artifacts(repo_path, args.feature_name)
    print(json.dumps(result, indent=2))
    return exit_code


def cmd_safe_checkout(args):
    """Safely checkout a branch with uncommitted changes check and stale branch detection."""
    repo_path = args.repo_path
    branch = args.branch
    remote = args.remote

    # Expand paths
    repo_path = os.path.expanduser(repo_path)

    # Verify it's a git repo
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        exit_error(f"ERROR: Not a git repository: {repo_path}")

    return safe_checkout_branch(repo_path, branch, remote)


def main():
    parser = argparse.ArgumentParser(
        description="Repository discovery and management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # find command
    parser_find = subparsers.add_parser("find", help="Find repository in common locations")
    parser_find.add_argument("repo_name", help="Repository name to find")
    parser_find.set_defaults(func=cmd_find)

    # find-known command
    parser_find_known = subparsers.add_parser("find-known", help="Find known repository (odh-test-context, tiger-team)")
    parser_find_known.add_argument(
        "repo_type", choices=["odh-test-context", "tiger-team"], help="Type of known repository"
    )
    parser_find_known.set_defaults(func=cmd_find_known)

    # find-target command
    parser_find_target = subparsers.add_parser("find-target", help="Find target repository (handles org/repo format)")
    parser_find_target.add_argument("repo_name", help="Repository name (with or without org)")
    parser_find_target.set_defaults(func=cmd_find_target)

    # clone command
    parser_clone = subparsers.add_parser("clone", help="Clone repository")
    parser_clone.add_argument("repo_url", help="GitHub URL to clone")
    parser_clone.add_argument("target_path", help="Where to clone (~ expanded)")
    parser_clone.set_defaults(func=cmd_clone)

    # locate-feature-dir command
    parser_locate = subparsers.add_parser(
        "locate-feature-dir", help="Locate test plan feature directory from local path or GitHub URL"
    )
    parser_locate.add_argument("source", help="Local path, GitHub PR URL, or GitHub branch URL")
    parser_locate.set_defaults(func=cmd_locate_feature_dir)

    # validate-local-path command
    parser_validate_path = subparsers.add_parser(
        "validate-local-path", help="Validate that a local path is not inside the skill repository"
    )
    parser_validate_path.add_argument("path", help="Path to validate")
    parser_validate_path.add_argument(
        "--force", action="store_true", help="Contributor override; safety checks still apply"
    )
    parser_validate_path.set_defaults(func=cmd_validate_local_path)

    # validate-remote command
    parser_validate_remote = subparsers.add_parser(
        "validate-remote", help="Validate that a remote repository is not the skill repository"
    )
    parser_validate_remote.add_argument("repo", help="Remote repository in owner/repo format")
    parser_validate_remote.set_defaults(func=cmd_validate_remote_repo)

    # pr-comments command
    parser_pr_comments = subparsers.add_parser("pr-comments", help="Fetch all review comments from a PR")
    parser_pr_comments.add_argument("repo", help="Repository (owner/repo)")
    parser_pr_comments.add_argument("pr_number", type=int, help="PR number")
    parser_pr_comments.set_defaults(func=cmd_pr_comments)

    # pr-create command
    parser_pr_create = subparsers.add_parser("pr-create", help="Create a PR or detect an existing one for a branch")
    parser_pr_create.add_argument("target_repo", help="Target repository (owner/repo)")
    parser_pr_create.add_argument("branch", help="Branch name")
    parser_pr_create.add_argument("title", help="PR title")
    parser_pr_create.add_argument("body", help="PR body (markdown)")
    parser_pr_create.add_argument("--reviewers", help="Comma-separated reviewer usernames")
    parser_pr_create.set_defaults(func=cmd_pr_create)

    # publish-artifacts command
    parser_publish = subparsers.add_parser(
        "publish-artifacts", help="Stage test plan artifacts, check for changes, and commit"
    )
    parser_publish.add_argument("repo_path", help="Path to git repository root")
    parser_publish.add_argument("feature_name", help="Feature directory name (basename)")
    parser_publish.add_argument("message", help="Commit message")
    parser_publish.set_defaults(func=cmd_publish_artifacts)

    # stage command
    parser_stage = subparsers.add_parser("stage", help="Selectively stage test plan artifacts for commit")
    parser_stage.add_argument("repo_path", help="Path to git repository root")
    parser_stage.add_argument("feature_name", help="Feature directory name (basename)")
    parser_stage.set_defaults(func=cmd_stage)

    # safe-checkout command
    parser_safe_checkout = subparsers.add_parser(
        "safe-checkout", help="Safely checkout a branch with uncommitted changes check and stale branch detection"
    )
    parser_safe_checkout.add_argument("repo_path", help="Path to git repository")
    parser_safe_checkout.add_argument("branch", help="Branch name to checkout")
    parser_safe_checkout.add_argument("--remote", default="origin", help="Remote name (default: origin)")
    parser_safe_checkout.set_defaults(func=cmd_safe_checkout)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
