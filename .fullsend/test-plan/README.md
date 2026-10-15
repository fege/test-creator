# Run the test-plan producer

## Prerequisites

- Run from an `odh-test-gen` checkout with the Fullsend CLI and OpenShell configured.
- Install `jsonschema>=4.18` in the host Python environment.
- Export `JIRA_URL`, `JIRA_USER`, and `JIRA_TOKEN`.
- Export `ANTHROPIC_VERTEX_PROJECT_ID`, `GOOGLE_CLOUD_PROJECT`, `CLOUD_ML_REGION`, and `GOOGLE_APPLICATION_CREDENTIALS`.

## Create a plan

From the producer checkout, set the strategy key and run Fullsend with the checkout as its target:

```bash
RUN_OUTPUT=$(mktemp -d /tmp/fullsend-test-plan.XXXXXX)
export FULLSEND_TASK='/test-plan-create RHAISTRAT-XXX --output-dir plans'
fullsend run test-plan --fullsend-dir .fullsend --target-repo . --output-dir "$RUN_OUTPUT"
```

Replace `RHAISTRAT-XXX` with the strategy issue. If credentials are stored in an env file, add
`--env-file .env`; add `--keep-sandbox` when you need to inspect a failed run.

## Compare without Jira label writes

This still runs inference and creates plan/review artifacts. The comparison harness sets
`TEST_PLAN_DRY_RUN=true` and enforces read-only Jira access; artifacts stay under
`$RUN_OUTPUT/plans/<feature>/`.

```bash
RUN_OUTPUT=$(mktemp -d /tmp/fullsend-test-plan.XXXXXX)
export FULLSEND_TASK='/test-plan-create RHAISTRAT-XXX --output-dir plans'
fullsend run test-plan-dry-run --fullsend-dir .fullsend --target-repo . --output-dir "$RUN_OUTPUT"
```

## Generate cases for an eligible plan

The post-hook prints the absolute feature directory: `$RUN_OUTPUT/plans/<feature>`.
Inspect its `TestPlanReview.md` and proceed only when the verdict is `Ready` and the score is at
least 8.

`test-plan-create` saves `.test-plan-output-dir.json` in the generated feature directory.
`test-plan-create-cases` takes that existing directory, validates the marker, reads `TestPlan.md`
and any gaps, then writes `test_cases/INDEX.md` and `TC-*.md` beneath it. It also updates the plan
and README in place. It does not need a separate cases output directory.

The create skill can invoke cases after review when “Proceed + generate test cases” is selected.
This Fullsend harness chooses review only; its prompt leaves the eligibility decision and separate
cases invocation to the host. A separate Fullsend invocation requires the existing feature directory
inside its sandbox target workspace. `--output-dir` collects host results; it does not supply those
results as input to the next sandbox. The current descriptor does not automate that transfer.
Before running cases, copy `$RUN_OUTPUT/plans/<feature>` to `plans/<feature>` in the checkout passed
to `--target-repo`.

When the feature is available as `plans/<feature>` in the target checkout, run:

```bash
export FULLSEND_TASK='/test-plan-create-cases plans/example_feature'
fullsend run test-plan --fullsend-dir .fullsend --target-repo . --output-dir "$RUN_OUTPUT"
```

Replace `example_feature` with the generated feature name and reuse the create command's
`$RUN_OUTPUT` so both commands collect artifacts in the same feature directory.

Plans, reviews, and handoff files are collected under `$RUN_OUTPUT/plans/<feature>/`.
Generated cases are nested in that feature's `test_cases/` directory.

Fullsend keeps each command's diagnostics under `$RUN_OUTPUT/<sandbox-name>/`, with transcripts
and `output/agent-result.json` in `iteration-N/`. An iteration is an agent attempt in Fullsend's
validation loop. This descriptor sets `max_iterations: 1`, so each command has `iteration-1`;
case generation is a separate command with its own sandbox, not iteration 2 of plan creation.
The post-hook reads the validated attempt and copies its feature artifacts to the shared
`$RUN_OUTPUT/plans/<feature>/` directory. It does not copy outcomes into `--target-repo`.
