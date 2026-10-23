#!/usr/bin/env python3
"""Fail validation when feature files that post-test-plan.py requires are missing or empty.

Runs on the host from validate-output-schema.sh, so it uses only the standard library.

Usage: check-handoff-files.py <agent-result.json> <target-repo-dir>
"""

import json
import stat
import sys
from pathlib import Path


def required_handoff_files(no_acceptance_criteria: bool) -> list[str]:
    """Return the feature files post-test-plan.py opens unconditionally."""
    names = ["TestPlanReview.md", ".source-strategy.md"]
    if not no_acceptance_criteria:
        names.extend(("TestPlan.md", "README.md"))
    return names


def handoff_errors(repo_dir: str, result: dict) -> list[str]:
    """Return one message per required feature file that is missing, not a regular file, or empty."""
    feature = result.get("feature_dir")
    if not isinstance(feature, str) or "\\" in feature or any(part in ("", ".", "..") for part in feature.split("/")):
        return ["feature_dir must be a relative path inside the target workspace"]
    feature_path = Path(repo_dir, *feature.split("/"))
    if not feature_path.is_dir():
        return [f"feature_dir not found in target workspace: {feature}"]

    no_acceptance_criteria = result.get("no_acceptance_criteria", False) is True
    errors = []
    for name in required_handoff_files(no_acceptance_criteria):
        path = feature_path / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            errors.append(f"required file is missing: {feature}/{name}")
            continue
        if not stat.S_ISREG(info.st_mode):
            errors.append(f"required file is not a regular file: {feature}/{name}")
        elif info.st_size == 0:
            errors.append(f"required file is empty: {feature}/{name}")
    # Without the AC gate both files are optional, but post-test-plan.py still requires the pair.
    if no_acceptance_criteria and (feature_path / "TestPlan.md").exists() != (feature_path / "README.md").exists():
        errors.append(f"TestPlan.md and README.md must be present together in {feature}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: check-handoff-files.py <agent-result.json> <target-repo-dir>", file=sys.stderr)
        return 2
    result_file, repo_dir = args
    if not repo_dir:
        print("FAIL: TARGET_REPO_DIR is empty; cannot check the feature files the post-script needs", file=sys.stderr)
        return 1
    result = json.loads(Path(result_file).read_text())
    errors = handoff_errors(repo_dir, result)
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"handoff files present: {result['feature_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
