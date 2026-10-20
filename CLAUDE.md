# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Working conventions for all agents — scope discipline, test idioms, lint expectations,
commit rules — live in [AGENTS.md](AGENTS.md). Read that file before changing code; this
file focuses on architecture and the skill pipeline. The user-facing skill catalog and
installation instructions are in [README.md](README.md).

## Project Overview

A Claude Code plugin (`test-plan`) that provides skills for end-to-end test planning for RHOAI (Red Hat OpenShift AI). Skills generate test plans from Jira strategies, create test cases, implement executable automation code, verify UI tests via Playwright, publish to GitHub, and score quality. The plugin is distributed via the opendatahub-io/skills-registry marketplace.

## Build & Test Commands

All build, test, and lint commands live in [AGENTS.md](AGENTS.md#commands) — the canonical
reference, kept in one place so the listings cannot drift apart. CI enforces
`--cov-fail-under=70` for test coverage (in `.github/workflows/test.yml`).

## Architecture

### Plugin structure

[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) defines the plugin metadata. Each skill lives in `skills/<skill-name>/SKILL.md`. Skills share Python utilities through a symlink chain: `skills/<name>/scripts → skills/_common/scripts → ../../scripts`. The only exception is `test-plan-ui-verify`, which has its own scripts directory with Playwright-based browser automation code.

### Design principle: scripts do logic, LLMs do semantics

Procedural logic is extracted to deterministic Python scripts in `scripts/` — no LLM calls are allowed there. Scripts are invoked as CLIs (argparse `main()` functions); most output JSON to stdout, while single-value utilities consumed via bash `$()` (e.g., `get_framework.py`, `get_component_test_dir.py`) output bare strings. LLMs are only used in SKILL.md instructions for semantic work (analyzing requirements, writing test code, quality scoring).

### Sub-agent orchestration

8 user-invocable skills and 8 internal sub-agent skills. 7 internal skills use `context: fork` for clean isolation and parallel execution. The one exception is `test-plan-review`, which runs in-parent context to write persistent files.

### Key modules in scripts/

- `validate.py` — unified validation CLI with 15+ subcommands for test plan artifacts (feature-dir, gap-counts, test-cases, scope-check, ac-citations, structure, etc.)
- `frontmatter.py` — YAML frontmatter read/write CLI for test plan and test case markdown files
- `parse_strat.py` — parses Jira wiki markup from RHAISTRAT tickets into structured JSON (acceptance criteria, NFRs, out-of-scope)
- `repo.py` — git operations CLI for the test plan output repository (init, stage, commit, publish as PR)
- `fetch_issue.py` — fetches Jira issues and resolves strategy hierarchies
- `utils/schemas.py` — schema definitions and validation for all artifact types (test-plan, test-case, test-gaps, test-plan-review), plus `TEMPLATE_HEADINGS` dict mapping section numbers to canonical heading text

### Test infrastructure

Tests call script `main()` functions directly using the `run_cli` fixture (in `conftest.py`), which captures stdout JSON. The `git_repo` fixture provides a temporary git repository. Shared test data lives in `tests/consts/<domain>_constants.py` (validation, test_plan, gaps, calibration, markdown); helper factories for building valid artifacts are in `tests/helpers.py`; static fixture files live in `tests/fixtures/`. `tests/constants.py` is the legacy artifact-base-data module — do not add new domain fixtures there. CI runs on Python 3.14.

## Skill Pipeline

The user-invocable skills form an ordered pipeline; understanding the ordering requires
reading across several SKILL.md files, so it is captured here:

1. `test-plan-create` — fetch a strategy (RHAISTRAT/RHOAIENG), fan out to the three parallel
   `test-plan-analyze-*` fork skills, merge into `TestPlan.md`, then invoke `test-plan-review`
   (rubric scoring + up to 2 auto-revision cycles) and write `TestPlanGaps.md`/`TestPlanReview.md`.
2. `test-plan-create-cases` — generate individual `TC-*.md` test case files and fill Sections 6/10.
3. `test-plan-case-implement` — generate executable pytest automation from the test cases.
4. `test-plan-publish` — commit artifacts to the separate output repo and open a PR.

Supporting user skills: `test-plan-score` (standalone rubric scoring, no revision),
`test-plan-resolve-feedback` (apply PR review comments), `test-plan-ui-verify` (Playwright checks
against a live cluster), and `test-plan-update`.

Internal fork skills (never invoked directly by users): `test-plan-analyze-endpoints`,
`test-plan-analyze-infra`, `test-plan-analyze-risks`, `test-plan-generate-test-file`,
`test-plan-resolve-gaps`, `test-plan-score-test-function`, `test-plan-merge`. `test-plan-review` is
the sole non-fork internal skill — it runs in-parent so it can write persistent files.

After a plan passes the rubric, a human reviewer signs off; the label taxonomy and review workflow
(`test-plan-auto-created`, `test-plan-rubric-pass`/`-revise`/`-fail`, `test-plan-auto-revised`,
`test-plan-human-reviewed`) are documented in `docs/human-review-guide.md`.

## Linting

Pre-commit hooks enforce code quality:
- **ruff** — linting and formatting (120-char line length, config in `pyproject.toml`)
- **flake8** — with RedHatQE plugins: UUC (unused-unique-constants) and UFN (unique-function-names); config in `.flake8`
- **pymarkdown** — markdown linting on `skills/` files only; config in `.markdownlint.yaml`

CI runs pre-commit and skillsaw on every PR via [`.github/workflows/lint.yml`](.github/workflows/lint.yml). Skillsaw lints skill SKILL.md files for context budget (warn at 6000 tokens, error at 8000), content positioning, and placeholder text. Config is in `.skillsaw.yaml` with strict mode enabled.

## Environment Variables

- `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN` — Required for Jira integration
- `CLAUDE_NON_INTERACTIVE=true` — Skip interactive prompts (CI mode)

## Artifact Separation

Test plan artifacts (TestPlan.md, TC-*.md files) are written to a separate directory (default `~/Code/opendatahub-test-plans/plans/`), never into this skill repository. The `--output-dir .` flag overrides this for contributor testing.

## Code Review Invariants

The contribution rules — deterministic scripts with no LLM calls, credentials via
environment variables, structured JSON errors, instruction-only SKILL.md files — are
stated once in [AGENTS.md](AGENTS.md#code-conventions). Review-time enforcement and the
per-path threat model live in [`.coderabbit.yaml`](.coderabbit.yaml).
