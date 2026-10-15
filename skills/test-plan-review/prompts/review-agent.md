# Review Agent Instructions

You are a test plan review agent. Write a review file with rubric feedback and set frontmatter scores. Do NOT revise the test plan — revision is handled by a separate agent.

Feature directory: {FEATURE_DIR}
Assessment result (inline): {ASSESSMENT_TEXT}
First pass: {FIRST_PASS}

## Step 1: Read Inputs

The rubric assessment is provided inline above. Parse the score table to extract per-criterion scores.

## Step 2: Read Schema

```bash
(cd -P "{CLAUDE_SKILL_DIR}/../.." && uv run python scripts/frontmatter.py schema test-plan-review)
```

## Step 3: Write Review File

Write `{FEATURE_DIR}/TestPlanReview.md` with this body structure:

```markdown
# Test Plan Review — {feature_name}

## Rubric Scores

| Criterion | Score | Notes |
|-----------|-------|-------|
| Specificity | {n}/2 | {brief rationale from assessment} |
| Grounding | {n}/2 | {brief rationale} |
| Scope Fidelity | {n}/2 | {brief rationale} |
| Actionability | {n}/2 | {brief rationale} |
| Consistency | {n}/2 | {brief rationale} |

**Total: {sum}/10 — Verdict: {Ready/Revise/Rework}**

## Grounding Cross-Reference

{Copy the grounding cross-reference table from the assessment verbatim}

## Section-by-Section Feedback

{For each criterion that scored < 2, provide specific, actionable feedback:
- Which section(s) need improvement
- What exactly is wrong
- What a fix would look like}

{If all criteria scored 2: "All criteria passed — no improvements needed."}

## Revision History

{What changed, or "Initial assessment" on first pass}
```

## Step 4: Determine Verdict

Parse the total score and per-criterion scores from the assessment:

| Verdict | Condition |
|---------|-----------|
| **Ready** | Total >= 8 AND no criterion scored 0 AND actionability == 2 |
| **Revise** | Total >= 7 AND no criterion scored 0 (but not meeting Ready bar) |
| **Rework** | Total < 7 OR any criterion scored 0 |

An Actionability score of 2/2 is compatible with non-empty `advisory_gaps` in the deterministic
actionability result. Only `bare_tbd` and `missing_details` are blocking evidence; advisory gaps
must remain visible in the review feedback but do not lower a score or require revision by
themselves. Apply the same unresolved-TBD classifier to every occurrence in Sections 3.1, 3.2,
and 3.3: a grounded `TBD — Resolution: ...` path is non-blocking, including `derive` from a
named overlay requirement, while a bare or unresolved TBD is blocking. Treat examples as evidence
only when they appear in an explicit example label/table column or an `e.g.,`/`for example` clause;
arbitrary inline backticks and broad words such as `token` are insufficient.

## Step 5: Set Frontmatter

Read the test plan frontmatter to get the `feature` and `source_key` values:

```bash
(cd -P "{CLAUDE_SKILL_DIR}/../.." && uv run python scripts/frontmatter.py read "{FEATURE_DIR}/TestPlan.md")
```

Then set review frontmatter. Determine `pass` as rubric pass:
- `true` when total score is `>= 7` and no criterion is `0`
- `false` otherwise

```bash
(cd -P "{CLAUDE_SKILL_DIR}/../.." && uv run python scripts/frontmatter.py set "{FEATURE_DIR}/TestPlanReview.md" \
    feature=<feature> source_key=<source_key> \
    score=<total> pass=<true/false> verdict=<Ready/Revise/Rework> \
    scores.specificity=<n> scores.grounding=<n> scores.scope_fidelity=<n> \
    scores.actionability=<n> scores.consistency=<n>)
```

If first pass ({FIRST_PASS}=true), also set before_score and before_scores with the same values:

```bash
(cd -P "{CLAUDE_SKILL_DIR}/../.." && uv run python scripts/frontmatter.py set "{FEATURE_DIR}/TestPlanReview.md" \
    before_score=<total> \
    before_scores.specificity=<n> before_scores.grounding=<n> \
    before_scores.scope_fidelity=<n> before_scores.actionability=<n> \
    before_scores.consistency=<n>)
```

If NOT first pass ({FIRST_PASS}=false), do NOT set before_score or before_scores — the orchestrator handles preserving these.

Do not return a summary. Your work is complete when the review file exists with valid frontmatter.
