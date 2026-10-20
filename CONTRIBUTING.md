# Contributing to test-plan

Thanks for contributing! This repo is a Claude Code plugin (`test-plan`) providing skills for
end-to-end test planning for RHOAI — see the [README](README.md) for the skill catalog and
[CLAUDE.md](CLAUDE.md) for the architecture. Working conventions for agents and humans live in
[AGENTS.md](AGENTS.md).

## Prerequisites

- Python ≥ 3.10 (CI runs 3.14)
- [uv](https://docs.astral.sh/uv/) for dependency management
- git

## Setup

```bash
git clone git@github.com:fullsend-ai/test-creator.git
cd test-creator
uv sync --extra dev
pre-commit install
```

## Everyday commands

All build, test, and lint commands live in [AGENTS.md](AGENTS.md#commands) — the canonical
reference for humans and agents alike. In short: pytest for tests, pre-commit for ruff and
flake8, `make lint` for skillsaw.

## Project layout

| Path | Contents |
|------|----------|
| `scripts/` | Deterministic Python CLIs (validation, parsing, Jira, repo ops) — no LLM calls |
| `scripts/utils/` | Shared utilities (schemas, frontmatter, error handling) |
| `skills/` | One `SKILL.md` per skill; shared scripts via `skills/_common/scripts` |
| `tests/unit/`, `tests/integration/` | Tests, run with `uv run pytest` |
| `tests/consts/` | Shared test data by domain (`<domain>_constants.py`) |
| `tests/helpers.py`, `tests/conftest.py` | Artifact factories and shared fixtures (`run_cli`, `git_repo`, `feature_dir`) |
| `docs/` | Human review guide for generated test plans |

## Making changes

Follow the rules in [AGENTS.md](AGENTS.md) — the short version:

- Keep changes scoped to the issue's acceptance criteria; prefer targeted edits over new
  frameworks.
- Deterministic logic goes in `scripts/` with JSON output; `SKILL.md` files stay
  instruction-only.
- New behavior needs tests. Shared fixtures go in `tests/consts/`, not inside test modules.
- Line length 120; constant and function names must be unique repo-wide (flake8 UUC/UFN).

## Commits and DCO

- Use conventional commit subjects: `fix:`, `feat:`, `docs:`, `chore:`, `test:`,
  `refactor:` — imperative mood, referencing the issue (`Closes #NN`).
- This repository enforces the [Developer Certificate of Origin](https://developercertificate.org/):
  sign off your commits with `git commit -s`. Commits pushed by the fullsend bot identities
  are exempt (the DCO app skips bots).

## Opening a pull request

CI runs on every PR:

- **Lint** — skillsaw (strict) and pre-commit on Python 3.14.
- **Tests** — full pytest suite with `--cov-fail-under=70`.
- **DCO** — sign-off check.

CodeRabbit also reviews PRs using the per-path instructions and threat model in
[`.coderabbit.yaml`](.coderabbit.yaml).

## Working with the fullsend agents

This repository runs [fullsend](https://github.com/fullsend-ai/fullsend) agents:

- **Every PR is auto-reviewed** by the review agent when opened or pushed. Outcome labels:
  `ready-for-merge` (approved), `requires-manual-review` (needs human judgment), plus
  `risk/*` classification. When the review agent requests changes, the fix agent runs
  automatically on bot-authored PRs; human-authored PRs need the `fullsend-fix` label to
  opt in.
- **Slash commands** (as PR/issue comments):

  | Command | Where | Effect |
  |---------|-------|--------|
  | `/fs-triage` | Issue | Re-run triage (clears labels, re-evaluates) |
  | `/fs-code [instruction]` | Issue | Have the code agent implement it |
  | `/fs-review` | PR | Request a fresh review round |
  | `/fs-fix [instruction]` | PR | Run the fix agent, optionally with directions |
  | `/fs-fix-stop` | PR | Disable bot-triggered fix runs for this PR |

- **Steering the fix agent:** it reads only the review body and the text you write after
  `/fs-fix` — it does **not** see inline review comments or general PR discussion. To have it
  act on a specific inline finding, quote the relevant text in the instruction
  (multi-line, up to 10,000 bytes; same-repo `#NN` references work, external URLs do not).
- **`needs-human`** on a PR means the fix loop is approaching its iteration cap and wants
  your direction — answer with `/fs-fix <instruction>` or push commits yourself.

Commands require repository access: triage-level for `/fs-triage` and `/fs-review`,
write-level for the rest.

## Filing issues

Open an issue with a description, reproduction steps (or the run/artifact that triggered it),
and expected behavior. The triage agent labels new issues; `ready-to-code` hands them to the
code agent, but you can always implement them yourself — agent PRs and human PRs follow the
same review process.
