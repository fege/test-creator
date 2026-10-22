#!/usr/bin/env python3
"""Remove the bootstrap helper link from a test-plan output directory.

`scripts/bootstrap.sh` creates `.odh-test-gen -> <plugin root>` in the agent's current directory so
skill helpers can resolve `.odh-test-gen/scripts/...`. When the agent is already inside the output
directory, that link lands in the generated artifacts, where publishers reject symlinks. Skills that
write artifacts run this script as their final step, after every helper that needs the link.

Only `<dir>/.odh-test-gen` in the feature directory and its parent (the output directory recorded
in `.test-plan-output-dir.json`) is considered, and it is removed only when it is a symlink that
resolves to this plugin. Foreign links, regular files, and directories are left untouched.

Usage:
    uv run python scripts/remove_runtime_alias.py <feature_dir>
"""

import argparse
import json
from pathlib import Path

from scripts.utils.error_utils import exit_error_with_json

RUNTIME_ALIAS_NAME = ".odh-test-gen"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def remove_runtime_alias(feature_dir: str, plugin_root: Path = PLUGIN_ROOT) -> dict:
    """Remove plugin-owned `.odh-test-gen` links from the feature and output directories.

    Returns ``{"status": "ok", "removed": [...], "skipped": [...]}`` where ``skipped`` lists
    entries named `.odh-test-gen` that were left in place because they are not this plugin's link.

    Raises:
        ValueError: If ``feature_dir`` is not an existing directory.
        OSError: If a plugin-owned link cannot be removed.
    """
    feature_path = Path(feature_dir).absolute()
    if not feature_path.is_dir():
        raise ValueError(f"Feature directory not found: {feature_dir}")

    plugin_root = plugin_root.resolve()
    removed: list[str] = []
    skipped: list[str] = []
    for directory in dict.fromkeys((feature_path, feature_path.parent)):
        alias = directory / RUNTIME_ALIAS_NAME
        if alias.is_symlink():
            if alias.resolve() == plugin_root:
                alias.unlink()
                removed.append(str(alias))
            else:
                skipped.append(str(alias))
        elif alias.exists():
            skipped.append(str(alias))

    return {"status": "ok", "removed": removed, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(
        description="Remove the plugin's .odh-test-gen helper link from a feature and its output directory"
    )
    parser.add_argument("feature_dir", help="Path to the feature directory")
    args = parser.parse_args()

    try:
        result = remove_runtime_alias(args.feature_dir)
    except (ValueError, OSError) as e:
        exit_error_with_json({"status": "failed", "error": str(e)}, message=str(e))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
