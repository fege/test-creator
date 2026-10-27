# Test Plan

End-to-end test planning workflow for RHOAI: generate E2E/UI-focused test plans from Jira strategies,
create traceable test cases, implement executable automation code, verify UI tests against live clusters
via Playwright, publish to GitHub, resolve review feedback, and score plans with deterministic evidence
gates and automated rubrics.

## Skills

### User-invocable (8 skills)

| Skill | Description |
|-------|-------------|
| `/test-plan-create` | Generate a test plan from a strategy (RHAISTRAT or RHOAIENG), with optional ADR and/or design spec |
| `/test-plan-create-cases` | Generate individual test case files from an existing test plan |
| `/test-plan-update` | Update test plan with new docs (ADR, API specs, design specs), re-analyze, bump version |
| `/test-plan-case-implement` | Generate executable test automation code from TC specifications (default target: opendatahub-tests; skips TC-UI-*) |
| `/test-plan-ui-verify` | Verify UI test cases from a PR against a live ODH/RHOAI cluster via Playwright |
| `/test-plan-publish` | Publish test plan artifacts to GitHub — branch, commit, and open a PR |
| `/test-plan-resolve-feedback` | Assess PR review comments, let the user decide what to apply, and push updates |
| `/test-plan-score` | Score an existing test plan using quality rubric (without auto-revision) |

### Sub-agents (8 internal skills: 7 forked, 1 in-parent)

| Skill | Description |
|-------|-------------|
| `test-plan-analyze-endpoints` | Extract feature scope, test objectives, and API endpoints from docs |
| `test-plan-analyze-risks` | Analyze strategy/ADR to determine test levels, types, priorities, risks |
| `test-plan-analyze-infra` | Identify test environment, data, infrastructure requirements |
| `test-plan-merge` | Intelligently merge new analyzer findings into existing test plan |
| `test-plan-resolve-gaps` | Cross-reference gaps with new findings to determine what's resolved |
| `test-plan-review` | Review test plan for completeness, consistency, and quality with auto-revision |
| `test-plan-generate-test-file` | Generate complete test file with all functions, quality scoring and auto-revision |
| `test-plan-score-test-function` | Score generated test function code using 5-criteria quality rubric |

## Installation

### Option 1: Install from Marketplace (Recommended)

Install from the [opendatahub-io/skills-registry](https://github.com/opendatahub-io/skills-registry) marketplace:

```bash
# Add the marketplace (one-time)
claude plugin marketplace add opendatahub-io/skills-registry

# Install test-plan plugin
/plugin install test-plan@opendatahub-skills
```

This clones the repository and makes skills immediately available. Then install Python dependencies:

```bash
cd ~/.claude/plugins/test-plan
uv sync --extra dev
```

Use skills:
```bash
# Will prompt for artifact location (default: ~/Code/opendatahub-test-plans/plans/)
/test-plan-create RHAISTRAT-400

# Auto-uses location from /test-plan-create
/test-plan-create-cases

# Auto-detects feature from /test-plan-create session
# Will prompt for publish target (default: opendatahub-io/opendatahub-test-plans)
/test-plan-publish
```

### Option 2: Manual Clone (For Contributors)

Clone the repository directly:

```bash
git clone https://github.com/fullsend-ai/test-creator ~/Code/test-creator
cd ~/Code/test-creator
uv sync --extra dev
```

Skills are available from `skills/` directory.

**Note**: Skills use symlinks for shared utilities (`_common/scripts → ../../scripts`). Both installation methods clone the full repository, so symlinks resolve correctly.

User-invocable skills define frontmatter used for slash-command discovery and invocation.

## Artifact Location

**Important**: Test plan artifacts are kept separate from the skill repository to maintain clean boundaries between code and data.

### Default Behavior

When you run `/test-plan-create`, it asks where to save artifacts:
```text
Where should test plan artifacts be created?

Provide a directory path (e.g., ~/Code/opendatahub-test-plans/plans/<team-name>), or press Enter for: ~/Code/opendatahub-test-plans/plans/

Note: Replace <team-name> with your team name (e.g., ai-hub, dashboard, etc.)
```

- **QE Teams**: Provide your team's directory path (e.g., `~/Code/opendatahub-test-plans/plans/ai-hub`)
- **Contributors**: Use default `~/Code/opendatahub-test-plans/plans/` or any path outside the skill repo
- **Save Preference**: Optionally save your choice to `.claude/settings.json` for future runs

The skill creates: `<your-path>/<feature-name>/`  
Example: If you enter `~/Code/opendatahub-test-plans/plans/ai-hub`, it creates `~/Code/opendatahub-test-plans/plans/ai-hub/mcp_catalog/`

### Session Context

`/test-plan-create-cases` automatically uses the same location as `/test-plan-create` when run in the same session (no prompt needed).

### Publishing

**Fork Workflow Required**: You must work from a personal fork to contribute:

1. **Fork** `opendatahub-io/opendatahub-test-plans` on GitHub to `your-username/opendatahub-test-plans`
2. **Clone** your fork: `git clone https://github.com/YOUR-USERNAME/opendatahub-test-plans ~/Code/opendatahub-test-plans`
3. **Create** test plans with `/test-plan-create` (saved in your fork)
4. **Publish** with `/test-plan-publish`:
   - Pushes to YOUR fork
   - Creates PR from your fork → upstream `opendatahub-io/opendatahub-test-plans`
   - The skill verifies you're working from a fork, not upstream

**Default publish target**: `opendatahub-io/opendatahub-test-plans`

### Contributor Override

Contributors testing skills can use `--output-dir` to force creation in the current directory:
```bash
/test-plan-create RHAISTRAT-400 --output-dir .
```

**Note**: The skill repository blocks artifact creation by default to prevent mixing code and test plan data.

## Architecture

### Design Principles

**Deterministic Scripts** - Procedural logic extracted to Python scripts (no LLM calls):
- Feature validation, citation and scope evidence, component detection, test-case filtering, and file mapping
- AST-based function extraction, score parsing, frontmatter/version updates, Jira operations, and gap consolidation
- Deterministic operations are covered by unit and integration tests

**LLMs Only Where Necessary** - Semantic understanding and code generation:
- Writing test code, quality scoring, semantic function matching
- Analyzing requirements, merging findings, resolving gaps

**Sub-Agent Orchestration** - 8 internal skills:
- **Forked (7 with `context: fork`)**: Analyzers (endpoints, risks, infra), workflow (merge, resolve-gaps), quality (generate-test-file, score-test-function) — clean isolation, parallel execution
- **In-parent (1 without fork)**: review — writes persistent files in parent context
- All invoked via Skill tool, deterministic return values

**CLI Orchestration** - Scripts own deterministic parsing and validation, return structured JSON where
consumed by skills, and use standard command-line JSON tooling to pass values between workflow steps.

### Quality Evidence Gate

`validate_quality_evidence.py` produces the scope coverage and actionability evidence payloads
from the test plan and resolved strategy: `scope_coverage_result` and `actionability_result`.
The actionability payload separates blocking `bare_tbd`/`missing_details` from non-blocking
`advisory_gaps`; the latter remain visible in `TestPlanGaps.md` but do not cap scores or trigger
revision by themselves. The persisted review gate (`enforce_citation_gate.py`) can cap Scope
Fidelity/Specificity and blocking Actionability evidence when deterministic evidence contradicts
a 2/2 rubric score; valid Actionability evidence with no blocking gaps raises a 0/1 score to 2/2.
The stateless scorer gate
(`cap_scope_fidelity.py`) applies the same Scope Fidelity/Specificity caps and Actionability
correction before `test-plan-score` presents its result, so scorer compliance is not trusted.

During gap collection, analyzer concerns that are version/build-only or
test-data-format/example-only are reclassified as advisory only when the actionability payload
reports the matching advisory; other analyzer concerns remain counted and trigger the normal
document-request flow.

The shared `build_citation_inputs.py` gate also checks AC citations, AC coverage, interface coverage,
scope markers, and actionability before review or scoring. Once Section 6.2 is populated, each declared
non-pending interface row must contain at least one `TC-E2E-*` or `TC-UI-*` reference. Empty
pre-create-cases matrices remain pending/valid, and duplicate rows are checked independently. The
`missing_e2e_or_ui_in_6_2` diagnostic identifies declared interfaces with a row lacking both references.

During scope analysis, the endpoint analyzer records in `## Gaps` any in-scope Section 1.2 item omitted
from Section 1.3 because it has no backing acceptance criterion. The gap consolidator carries that
disclosure into `TestPlanGaps.md`; it does not invent a test objective or infer additional exclusions.

## Usage

### Basic Workflow

**Prerequisites**: Fork and clone `opendatahub-io/opendatahub-test-plans` first (see Publishing section above).

```bash
# 1. Generate a test plan from a Jira strategy
#    Will ask: Where to save artifacts? [~/Code/opendatahub-test-plans/plans/]
#    Provide your team path, e.g.: ~/Code/opendatahub-test-plans/plans/ai-hub
#    Creates: ~/Code/opendatahub-test-plans/plans/ai-hub/<feature>/
/test-plan-create RHAISTRAT-400

# For CI/automation (skips interactive gap resolution):
export CLAUDE_NON_INTERACTIVE=true
/test-plan-create RHAISTRAT-400

# 2. Generate test cases (auto-uses location from step 1)
/test-plan-create-cases

# 3. Publish to GitHub
#    Auto-detects feature directory from /test-plan-create session
#    Verifies you're working from a fork
#    Creates PR from your-username/opendatahub-test-plans → opendatahub-io/opendatahub-test-plans
/test-plan-publish mcp_catalog
```

### Advanced Options

```bash
# Generate test plan with ADR for extra technical depth
/test-plan-create RHAISTRAT-400 /path/to/adr.pdf

# Generate test plan with a local design spec (UI screens + journeys)
/test-plan-create RHAISTRAT-400 ./path/to/design-spec.md

# Design specs can also be attached on the Jira STRAT as
# {KEY}-design-spec.md (or *design-spec*.md); create auto-discovers them
/test-plan-create RHAISTRAT-400

# ADR + design spec together
/test-plan-create RHAISTRAT-400 /path/to/adr.pdf ./design-spec.md

# Generate test cases from a GitHub PR (for /test-plan-resolve-feedback workflow)
/test-plan-create-cases https://github.com/opendatahub-io/opendatahub-test-plans/pull/5

# Generate test cases for a specific local directory
/test-plan-create-cases ~/Code/opendatahub-test-plans/plans/ai-hub/mcp_catalog

# Publish with specific reviewers
/test-plan-publish mcp_catalog --reviewers alice,bob

# Publish to a specific repository
/test-plan-publish mcp_catalog --repo opendatahub-io/test-plans

# Resolve PR review feedback
/test-plan-resolve-feedback https://github.com/opendatahub-io/opendatahub-test-plans/pull/42

# Update test plan with new documentation
/test-plan-update ~/Code/opendatahub-test-plans/plans/ai-hub/mcp_catalog adr.pdf api-spec.md

# Update test plan from GitHub PR with new docs
/test-plan-update https://github.com/opendatahub-io/opendatahub-test-plans/pull/42 design-doc.md

# Generate executable test code from test cases
/test-plan-case-implement mcp_catalog

# Generate code for specific test cases only
/test-plan-case-implement mcp_catalog --test-cases TC-E2E-001,TC-E2E-002

# Score a test plan without triggering auto-revision
/test-plan-score mcp_catalog
```

### Contributor Workflow

```bash
# Force creation in current directory (bypasses skill repo validation)
/test-plan-create RHAISTRAT-400 --output-dir .

# Force test case creation in current directory
/test-plan-create-cases mcp_catalog --output-dir .
```

## Pipeline

```
/test-plan-create RHAISTRAT-400
        │
        ├── test-plan-analyze-endpoints  ─┐
        ├── test-plan-analyze-risks      ─┤  (parallel)
        └── test-plan-analyze-infra      ─┘
                    │
                    ▼
            TestPlan.md + TestPlanGaps.md
                    │
                    ▼
            Gap resolution (HITL)
                    │
                    ▼
            test-plan-review (auto-revision, scoring)
                    │
                    ▼
        /test-plan-create-cases (optional auto-run)
                    │
                    ▼
            TC-*.md + INDEX.md
                    │
                    ├─────────────────────┐
                    │                     │
                    ▼                     ▼
        /test-plan-publish    /test-plan-case-implement
                    │                     │
                    │                     ├── preflight.py (validation + detection)
                    │                     ├── filter_test_cases.py, map_test_files.py
                    │                     └── test-plan-generate-test-file (parallel per file)
                    │                         ├── list_test_functions.py (AST)
                    │                         ├── test-plan-score-test-function (per function)
                    │                         └── parse_test_score.py
                    │                     │
                    ▼                     ▼
            GitHub PR          Generated test code in target repos
                    │
                    ▼
            GitHub PR (with optional reviewers)
                    │
                    ├──────────────────────────────────────┐
                    │                                      │
                    ▼                                      ▼
        /test-plan-resolve-feedback          /test-plan-update (new docs)
        (after PR reviews)                    │
                    │                         ├── re-run analyzers
                    │                         ├── update TestPlan.md
                    │                         ├── test-plan-review
                    │                         └── optionally regenerate test cases
                    │                         │
                    ▼                         ▼
            Updated artifacts ◄───────────────┘
                    │
                    ▼
            /test-plan-publish (commit & push updates)
```

## Prerequisites

### Required for All Users
- [Claude Code](https://claude.ai/code) installed
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Git installed
- Python 3.10 or higher

### CI/Automation Mode
Skills support non-interactive mode for CI environments:
- Set `CLAUDE_NON_INTERACTIVE=true` to skip interactive prompts
- Or run in a CI environment (auto-detected via `CI` environment variable)
- Gap resolution and other prompts will auto-proceed with safe defaults

### Required for Specific Features
- **Jira integration**: Environment variables configured (for `/test-plan-create`, `/test-plan-review`, `/test-plan-score`):
  - `JIRA_URL`: Base URL for your Jira instance (e.g., `https://redhat.atlassian.net`)
  - `JIRA_USER`: Username or email for authentication
  - `JIRA_TOKEN`: [API token](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/) for authentication
- **GitHub publishing**: [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated (for `/test-plan-publish` and `/test-plan-resolve-feedback`)
- **Test implementation**: Local or cloned target repositories (for `/test-plan-case-implement`)

## Repository Structure

```
.claude-plugin/
└── plugin.json             # Plugin metadata

skills/
├── test-plan-create/
│   ├── SKILL.md
│   └── test-plan-template.md
├── test-plan-analyze-endpoints/
│   └── SKILL.md
├── test-plan-analyze-risks/
│   └── SKILL.md
├── test-plan-analyze-infra/
│   └── SKILL.md
├── test-plan-merge/
│   └── SKILL.md
├── test-plan-resolve-gaps/
│   └── SKILL.md
├── test-plan-review/
│   └── SKILL.md
├── test-plan-create-cases/
│   ├── SKILL.md
│   └── test-case-template.md
├── test-plan-update/
│   └── SKILL.md
├── test-plan-publish/
│   └── SKILL.md
├── test-plan-resolve-feedback/
│   └── SKILL.md
├── test-plan-case-implement/
│   └── SKILL.md            # Main orchestration skill
├── test-plan-generate-test-file/
│   └── SKILL.md            # Test file generation sub-agent
├── test-plan-ui-verify/
│   ├── README.md
│   └── SKILL.md
├── test-plan-score/
│   └── SKILL.md
└── _common/                # Shared scripts (symlinked)

scripts/
├── frontmatter.py          # YAML frontmatter validation and manipulation
├── repo.py                 # Repository discovery, cloning, validation, artifact publishing, PR operations
├── tc_regeneration.py      # Test case regeneration mode detection
├── preflight.py            # Unified preflight checks (validation + detection + odh-test-context)
├── validate.py             # Unified validation CLI (feature-dir, gap-counts, test-cases, all)
├── detect_components.py    # Component detection and repository mapping
├── filter_test_cases.py    # Filter test cases by automation status
├── map_test_files.py       # Map test cases to test files (strategy pattern)
├── list_test_functions.py  # Extract test functions from Python files (AST)
├── load_pattern_guides.py  # Load CLAUDE.md and testing pattern guides
├── parse_test_score.py     # Parse test quality score assessments
├── parse_test_cases.py     # Parse test case files into structured data
├── update_tc_frontmatter.py # Bulk update TC frontmatter fields
├── analyze_common_setup.py # Identify common setup requirements across test cases
├── extract_and_format_conventions.py # Extract conventions from odh-test-context as markdown
├── format_conventions.py  # Format test conventions dict as markdown
├── format_file_result.py  # Format test file generation result as JSON
├── version.py              # Test plan version management
├── jira_utils.py           # Jira REST API client with retry logic
├── strategy_source.py      # Shared Jira issue-to-strategy formatting helpers
├── fetch_issue.py          # Fetch Jira issues, save as markdown, extract components
├── parse_strat.py          # Parse STRAT sections; snapshot strategy files for test-plan-create
├── resolve_design_spec.py  # Discover design-spec (local path or Jira attachment); snapshot into feature dir
├── resolve_strategy.py     # Snapshot-primary strategy resolution for test-plan-review/score
├── build_citation_inputs.py # Build citation gate inputs (AC/NFR/interface coverage) from a strategy
├── validate_quality_evidence.py # Produce scope coverage and actionability evidence payloads
├── enforce_citation_gate.py # Deterministically cap Scope Fidelity/Specificity/Actionability
├── cap_scope_fidelity.py   # Stateless scorer enforcement for Scope Fidelity/Specificity/Actionability
├── filter_for_revision.py # Decide whether a test plan review warrants revision
├── preserve_review_state.py # Save/restore cumulative review state across re-assessment cycles
├── add_jira_labels.py      # Add labels to Jira issues (CLI wrapper)
└── utils/                  # Shared utilities
    ├── schemas.py          # Schema validation (test-plan, test-case, test-gaps, review)
    ├── frontmatter_utils.py # Frontmatter read/write operations
    ├── repo_utils.py       # Repository discovery and test context loading
    ├── component_map.py    # Component to repository mapping
    ├── repo_discovery.py   # Extract repo indicators from test plans
    ├── tc_parser.py        # Test case file parsing (extended with category/title extraction)
    ├── text_utils.py       # Text transformation utilities (snake_case conversion)
    ├── markdown_utils.py   # Parse markdown section content
    ├── strat_utils.py      # Parse STRAT sections from fetched Jira wiki markup
    └── test_analyzer.py    # Common setup requirements identification

tests/
├── unit/                   # Unit tests (fast, isolated)
├── integration/            # Integration tests (subprocess, file I/O)
├── consts/                 # Shared test data by domain (<domain>_constants.py)
├── fixtures/               # Static fixture files
├── conftest.py             # Shared fixtures (run_cli, git_repo, feature_dir)
├── helpers.py              # Factories for valid test artifacts
└── constants.py            # Legacy artifact base data (do not extend — see AGENTS.md)
```

## Development

Development setup, commands, conventions, and the pull-request workflow (including the
fullsend agent workflow) are documented in [CONTRIBUTING.md](CONTRIBUTING.md). Working
conventions for AI coding agents are in [AGENTS.md](AGENTS.md); architecture background is in
[CLAUDE.md](CLAUDE.md).

The test suite layout is described in [AGENTS.md](AGENTS.md#test-conventions) — the
`tests/` directory itself is the source of truth for the current file list.
