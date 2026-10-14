#!/usr/bin/env python3
"""Save and restore cumulative review state across re-assessment cycles.

Saves before_scores, auto_revised, and revision history to a JSON state file
before re-review, then restores them after the new review file is written.

Usage:
    python3 scripts/preserve_review_state.py save <feature_dir>
    python3 scripts/preserve_review_state.py restore <feature_dir>
"""

import json
import os
import re
import sys

from scripts.utils.error_utils import exit_error
from scripts.utils.frontmatter_utils import read_frontmatter, update_frontmatter


def _review_path(feature_dir):
    return os.path.join(feature_dir, "TestPlanReview.md")


def _state_path(feature_dir):
    return os.path.join(feature_dir, ".review-state.json")


def _extract_revision_history(filepath):
    """Extract the ## Revision History section content from a review file."""
    with open(filepath) as f:
        content = f.read()

    return _extract_revision_history_from_content(content)


def _extract_revision_history_from_content(content):
    """Extract the ## Revision History section content from file content."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3 :].lstrip("\n")

    match = re.search(r"^## Revision History\s*\n(.*)", content, re.MULTILINE | re.DOTALL)
    if not match:
        return ""

    section = match.group(1)

    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]

    return section.strip()


def _is_placeholder_history(text):
    """Return true when revision history body is placeholder text."""
    normalized = text.strip().lower()
    return normalized in {"", "initial assessment", "none", "n/a"}


def _replace_revision_history(content, new_history):
    """Replace body of ## Revision History section with new history text."""
    pattern = re.compile(
        r"(^## Revision History\s*\n)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    replacement_body = new_history.strip()

    def repl(match):
        if replacement_body:
            return match.group(1) + replacement_body + "\n\n"
        return match.group(1)

    return pattern.sub(repl, content, count=1)


def save(feature_dir):
    """Save before_scores, auto_revised, and revision history to a state file."""
    rpath = _review_path(feature_dir)
    if not os.path.exists(rpath):
        print(f"SKIP (no review file in {feature_dir})")
        return

    data, _ = read_frontmatter(rpath)
    state = {
        "before_score": data.get("before_score"),
        "before_scores": data.get("before_scores"),
        "auto_revised": data.get("auto_revised", False),
        "revision_history": _extract_revision_history(rpath),
    }

    spath = _state_path(feature_dir)
    with open(spath, "w") as f:
        json.dump(state, f, indent=2)

    print(f"SAVED state for {feature_dir}")


def restore(feature_dir):
    """Restore cumulative scores, auto-revision status, and history from state."""
    spath = _state_path(feature_dir)
    if not os.path.exists(spath):
        print(f"SKIP (no state file for {feature_dir})")
        return

    with open(spath) as f:
        state = json.load(f)

    rpath = _review_path(feature_dir)
    if not os.path.exists(rpath):
        print(f"SKIP (no review file to restore into for {feature_dir})")
        return

    fm_updates = {}
    if state.get("before_score") is not None:
        fm_updates["before_score"] = state["before_score"]
    if state.get("before_scores"):
        fm_updates["before_scores"] = state["before_scores"]
    if "auto_revised" in state:
        current_data, _ = read_frontmatter(rpath)
        fm_updates["auto_revised"] = state["auto_revised"] or current_data.get("auto_revised", False)
    if fm_updates:
        update_frontmatter(rpath, fm_updates, "test-plan-review")

    saved_history = state.get("revision_history", "").strip()
    if saved_history:
        with open(rpath) as f:
            content = f.read()

        current_history = _extract_revision_history_from_content(content)
        if _is_placeholder_history(current_history):
            merged_history = saved_history
        elif current_history.startswith(saved_history):
            merged_history = current_history
        else:
            merged_history = f"{saved_history}\n\n{current_history}"

        content = _replace_revision_history(content, merged_history)
        with open(rpath, "w") as f:
            f.write(content)

    os.remove(spath)
    print(f"RESTORED state for {feature_dir}")


def main():
    if len(sys.argv) != 3:
        exit_error("Usage: preserve_review_state.py save|restore <feature_dir>")

    action = sys.argv[1]
    feature_dir = sys.argv[2]

    if action == "save":
        save(feature_dir)
    elif action == "restore":
        restore(feature_dir)
    else:
        exit_error(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
