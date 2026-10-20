# AGENTS.md

Working rules for AI coding agents (and the humans driving them) in this repository.

[CLAUDE.md](CLAUDE.md) documents the architecture and the skill pipeline in depth. This file
holds the conventions that keep changes consistent with the codebase. For conventions, this
file wins; for architecture, CLAUDE.md wins. The human workflow (setup, PRs, DCO) is in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Scope discipline

These rules exist because agent review/fix loops otherwise over-generalize: each review
finding gets answered with a more general mechanism until the change dwarfs the issue it
fixes.

- Implement the linked issue's acceptance criteria, nothing more. Layouts, inputs, and edge
  cases the issue did not name are out of scope — mention them in the PR description instead
  of handling them silently.
- Prefer targeted changes over generic mechanisms. When a review finding can be fixed either
  by narrowing what existing code matches or by adding a new discovery/parsing layer, narrow.
- Do not refactor, rename, or reformat code the change does not require.
- Every new behavior gets a test in the same change; every new helper gets a caller.

## Commands

```bash
uv sync --extra dev                 # install dependencies (editable mode)
uv run pytest tests/ -v             # all tests
uv run pytest tests/unit/ -v        # unit tests only
uv run pytest tests/unit/test_enforce_citation_gate.py -v                      # one file
uv run pytest tests/unit/test_enforce_citation_gate.py::TestApplyScoreCaps -v  # one class
uv run pytest tests/ -v --cov=scripts --cov-report=term-missing  # coverage (CI gate: 70%)
pre-commit run --all-files          # ruff, flake8 (UUC/UFN), standard hooks
make lint                           # skillsaw (SKILL.md files)
make skillsaw-fix                   # auto-fix skillsaw issues
```

This is the single canonical command reference — [CLAUDE.md](CLAUDE.md),
[CONTRIBUTING.md](CONTRIBUTING.md), and the README link here instead of duplicating it.

CI runs tests on Python 3.14 with `--cov-fail-under=70`, plus pre-commit and skillsaw, on
every PR (see [`.github/workflows/`](.github/workflows/)).

## Test conventions

- **Shared test data lives in `tests/consts/<domain>_constants.py`** — existing domains:
  `validation_constants.py`, `test_plan_constants.py`, `gaps_constants.py`,
  `calibration_constants.py`, `markdown_constants.py`. If the fixture you need does not
  exist, add it to the matching file (or create a new `<domain>_constants.py`) — do not
  define it inside a test module. `tests/constants.py` is the legacy artifact-base-data
  module (`REPO_ROOT`, `VALID_TEST_CASE_DATA`, `VALID_TC_CONTENT`); do not add new domain
  fixtures there.
- **Reuse `tests/helpers.py` and `tests/conftest.py` before writing local helpers.**
  `write_valid_testplan`, `write_tc`, `build_review_payload` (helpers) and `run_cli`,
  `git_repo`, `feature_dir` (fixtures) cover the common cases. Never duplicate a
  module-level helper as a staticmethod inside a test class.
- **Parametrize idiom**: inline `@pytest.mark.parametrize` on the test, `pytest.param(...,
  id="...")` entries for case lists, the `ids=` keyword for plain value lists. Do not create
  module-level decorator aliases.
- **Organization**: tests call script `main()` functions directly via the `run_cli` fixture
  and assert on the captured JSON. Group tests in `Test*` classes by the unit under test,
  following the separation in `tests/unit/test_enforce_citation_gate.py` (pure-function
  tests, persistence tests, and CLI tests as separate classes).
- Prefer exact substring assertions (positive and negative) over re-parsing generated
  documents in the test.

## Code conventions

- **`scripts/` is deterministic**: no LLM or AI API calls. CLIs output JSON to stdout; only
  single-value utilities consumed via bash `$()` (e.g. `get_framework.py`) output bare
  strings. Errors are structured JSON: `{"status": "failed", "error": "..."}`.
- **Credentials** come from environment variables (`JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN`) —
  never hardcoded.
- **`SKILL.md` files contain instructions, not logic** — procedural steps go into
  `scripts/`. skillsaw enforces context budgets (warn 6000 / error 8000 tokens) in strict
  mode.
- **Line length is 120** (ruff and flake8).
- **Names must be unique repo-wide**: the RedHatQE flake8 plugins UUC (constants) and UFN
  (functions) reject duplicate names across the project. Grep for a new name before adding
  it.

## When the sandbox cannot run the tooling

Fullsend sandboxes restrict network egress: `pre-commit` cannot fetch its hook repos, and
`uvx`/skillsaw may be unavailable. When that happens:

- still run `uv run pytest` on the touched test files — that always works;
- keep lines within 120 characters manually;
- check new constant/function names for uniqueness by grepping the repo;
- state in the PR summary exactly which checks could not run. Never claim lint passed when
  it did not execute.

## Commits and PRs

- Conventional commit subjects: `fix:`, `feat:`, `docs:`, `chore:`, `test:`, `refactor:`
  (scope optional, e.g. `fix(test-plan): ...`), imperative mood, referencing the issue
  (`Closes #NN`).
- Human commits must carry a DCO sign-off (`git commit -s`). Commits pushed by the fullsend
  bot identities are exempt — the DCO app skips bots.
- `.fullsend/config.yaml`, `.github/workflows/fullsend.yaml`, and
  `.github/workflows/prioritize.yml` are managed by fullsend — do not edit them in feature
  work.

## Where things are

- Architecture and skill pipeline → [CLAUDE.md](CLAUDE.md)
- Skill catalog and installation → [README.md](README.md)
- Review threat model and per-path review instructions → [`.coderabbit.yaml`](.coderabbit.yaml)
- Human review workflow for generated test plans →
  [docs/human-review-guide.md](docs/human-review-guide.md)
