#!/usr/bin/env bash
# Prepare the caller-local helper alias for a delivered test-plan plugin.
set -euo pipefail

if [[ "${1:-}" != "--layout" || $# -ne 2 ]]; then
    echo "Usage: bootstrap.sh --layout <selected-skill-dir>" >&2
    exit 2
fi

if [[ ! -d "$2" ]]; then
    echo "Selected skill directory must name a delivered skill" >&2
    exit 1
fi

plugin_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
skill_root=$(cd "$2" && pwd -P)
if [[ "$(dirname "$skill_root")" != "$plugin_root/skills" \
      || ! -f "$skill_root/SKILL.md" || -L "$skill_root/SKILL.md" ]]; then
    echo "Selected skill directory does not belong to this test-plan plugin" >&2
    exit 1
fi

caller_root=$(pwd -P)
same_root_fullsend_generation=false
if [[ -n "${FULLSEND_TARGET_REPO_DIR:-}" ]]; then
    if [[ ! -d "$FULLSEND_TARGET_REPO_DIR" ]]; then
        echo "FULLSEND_TARGET_REPO_DIR must name the output workspace" >&2
        exit 1
    fi
    output_root=$(cd "$FULLSEND_TARGET_REPO_DIR" && pwd -P)
    if [[ "$output_root" == "$plugin_root" ]]; then
        fullsend_task="${FULLSEND_TASK:-}"
        fullsend_task="${fullsend_task%% *}"
        case "$fullsend_task" in
            /test-plan-create|/test-plan-create-cases) same_root_fullsend_generation=true ;;
            * ) echo "Fullsend plugin package and output workspace must be disjoint" >&2; exit 1 ;;
        esac
    else
        case "$output_root/" in
            "${plugin_root%/}/"* ) echo "Fullsend plugin package and output workspace must be disjoint" >&2; exit 1 ;;
        esac
        case "$plugin_root/" in
            "${output_root%/}/"* ) echo "Fullsend plugin package and output workspace must be disjoint" >&2; exit 1 ;;
        esac
    fi
    case "$caller_root/" in
        "$output_root/"* ) ;;
        * ) echo "Caller workspace must stay inside the Fullsend output workspace" >&2; exit 1 ;;
    esac
fi

if [[ "$same_root_fullsend_generation" == true ]]; then
    exit 0
fi

if [[ "$caller_root" == "$plugin_root" ]]; then
    exit 0
fi
case "$caller_root/" in
    "$plugin_root/"* ) echo "Caller workspace is inside the plugin package" >&2; exit 1 ;;
esac
case "$plugin_root/" in
    "$caller_root/"* ) echo "Plugin package is inside the caller workspace" >&2; exit 1 ;;
esac

alias_path="$caller_root/.odh-test-gen"
if [[ -L "$alias_path" ]]; then
    if [[ -d "$alias_path" && "$(cd "$alias_path" && pwd -P)" == "$plugin_root" ]]; then
        exit 0
    fi
    echo "Foreign runtime link: $alias_path" >&2
    exit 1
fi
if [[ -e "$alias_path" ]]; then
    echo "Foreign runtime entry: $alias_path" >&2
    exit 1
fi
ln -s "$plugin_root" "$alias_path"
