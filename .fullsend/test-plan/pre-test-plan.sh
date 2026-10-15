#!/usr/bin/env bash
set -euo pipefail

target_repo_dir="${TARGET_REPO_DIR:-}"
if [[ -z "$target_repo_dir" || ! -d "$target_repo_dir" ]]; then
    echo "TARGET_REPO_DIR must name the target checkout" >&2
    exit 1
fi
target_repo_dir=$(cd -- "$target_repo_dir" && pwd -P)
cd -- "$target_repo_dir"

if [[ ! -f pyproject.toml || ! -f scripts/bootstrap.sh ]]; then
    echo "TARGET_REPO_DIR must name a test-plan producer checkout" >&2
    exit 1
fi

if [[ -L .claude || ( -e .claude && ! -d .claude ) ]]; then
    echo "Refusing to use a non-directory .claude entry" >&2
    exit 1
fi
mkdir -p .claude
if [[ -L .claude/skills || ( -e .claude/skills && ! -d .claude/skills ) ]]; then
    echo "Refusing to use a non-directory .claude/skills entry" >&2
    exit 1
fi
mkdir -p .claude/skills

link_skill() {
    local link_name="$1"
    local skill_name="$2"
    local link_path=".claude/skills/$link_name"
    local target_path="../../skills/$skill_name"

    if [[ ! -d "skills/$skill_name" || ! -f "skills/$skill_name/SKILL.md" ]]; then
        echo "Missing producer skill: skills/$skill_name/SKILL.md" >&2
        exit 1
    fi
    if [[ -L "$link_path" ]]; then
        if [[ "$(readlink "$link_path")" == "$target_path" ]]; then
            return 0
        fi
        echo "Refusing to replace foreign skill link: $link_path" >&2
        exit 1
    fi
    if [[ -e "$link_path" ]]; then
        echo "Refusing to replace foreign skill entry: $link_path" >&2
        exit 1
    fi
    ln -s "$target_path" "$link_path"
}

link_skill test-plan-create test-plan-create
link_skill test-plan-create-cases test-plan-create-cases
# Keep the existing Skill-tool names while linking the producer-owned skills.
link_skill test-plan.analyze.endpoints test-plan-analyze-endpoints
link_skill test-plan.analyze.infra test-plan-analyze-infra
link_skill test-plan.analyze.risks test-plan-analyze-risks
link_skill test-plan.review test-plan-review
