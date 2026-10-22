# Human Review Guide

> **Audience**: QE engineers, team leads, and domain experts who review
> AI-generated test plans and test cases before they become the basis
> for test automation.
>
> | Label | Meaning |
> |-------|---------|
> | `test-plan-auto-created` | AI generated the test plan |
> | `test-plan-rubric-pass` | Automated rubric scored >= 8/10, no zeros, AND actionability == 2 |
> | `test-plan-rubric-revise` | Automated rubric scored Revise verdict (qualifying total but a criterion below 2, including a blocking Actionability gap) |
> | `test-plan-rubric-fail` | Automated rubric scored < 7, or any criterion scored 0 |
> | `test-plan-auto-revised` | AI applied at least one auto-revision cycle |
> | `test-plan-human-reviewed` | Human has reviewed and approved |

## How Test Plans Enter the Pipeline

Test plans can be generated through two paths: manually via Claude Code
skills, or automatically via the agentic CI pipeline.

### Manual triggering (Claude Code)

A test plan is generated from a Jira strategy (RHAISTRAT) or issue
(RHOAIENG) using `/test-plan-create`. The pipeline:

1. Fetches the strategy from Jira
2. Runs three parallel analyzers (endpoints, risks, infrastructure)
3. Assembles a structured test plan from their findings
4. Identifies gaps where source material was insufficient
5. Scores the plan against a 5-criterion rubric (0-10)
6. Auto-revises if any criterion scores below 2 (max 2 cycles)
7. Stamps verdict labels on the Jira issue

After scoring, test cases are generated with `/test-plan-create-cases`
and the complete artifact set is published to GitHub via
`/test-plan-publish`, which opens a PR for human review.

### Automated triggering (agentic CI)

The [test-plan-generator](https://gitlab.com/redhat/rhel-ai/agentic-ci/test-plan-generator)
monitors Jira for RHAISTRAT issues with a designated label. When
detected, it runs the same generation pipeline automatically and
publishes artifacts to the
[test-plans-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/test-plans-data)
repository on GitLab.

The review process is the same regardless of how the plan was triggered
-- both paths produce the same artifact set and apply the same rubric
scoring.

> **Note**: Final publishing of artifacts to GitLab from the agentic
> pipeline is not yet implemented. Until it is, artifacts from the
> automated flow may require manual retrieval.

## Two Paths to Approval

Every test plan -- whether triggered manually or by the agentic CI
pipeline -- has already passed through automated generation and scoring.
The path forward depends on the rubric verdict:

- **Rubric-pass** (>= 8/10, no zeros, actionability == 2) -- The plan meets baseline
  quality. It may still contain non-blocking actionability advisories listed in
  `TestPlanGaps.md`. Review for domain accuracy, then approve or request changes.
- **Rubric-revise** (total >= 7, no zeros, but not Ready) -- The plan qualifies but has
  minor improvements needed. Review and decide whether to iterate or approve as-is.
- **Rubric-fail** (< 7 or any zero) -- The automated review flagged
  significant issues. These need source documents (ADR, API spec,
  design doc) or manual correction before approval.

Both paths conclude with adding the `test-plan-human-reviewed` label
after the reviewer is satisfied.

## Scoring

The automated rubric evaluates every test plan across 5 dimensions,
each scored 0-2.

| Criterion | What It Measures |
|-----------|-----------------|
| **Specificity** | Is this plan written for *this* feature, or is it generic boilerplate? |
| **Grounding** | Are technical details traceable to source material, or fabricated? |
| **Scope Fidelity** | Does the plan's scope match the strategy's scope? |
| **Actionability** | Could a QE engineer start testing from this plan alone? |
| **Consistency** | Do sections agree with each other? |

| Verdict | Trigger | Meaning |
|---------|---------|---------|
| **Ready** | total >= 8, no zeros, actionability == 2 | Baseline quality met -- proceed to review |
| **Revise** | total >= 7, no zeros (but not Ready) | Minor improvements needed |
| **Rework** | total < 7 or any zero | Significant issues -- needs source docs |

> **Note**: A Ready plan may carry advisory actionability gaps. The frontmatter `pass` boolean is
> a lower floor (total >= 7, no
> zeros) than the `test-plan-rubric-pass` Jira label (>= 8, no zeros, AND
> actionability == 2). A Revise-verdict plan can have `pass: true` while
> still being labeled `test-plan-rubric-revise` -- the two are intentionally
> decoupled, not inconsistent.

## Setup

1. Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
2. Set Jira credentials:
   ```bash
   export JIRA_URL="https://redhat.atlassian.net"
   export JIRA_USER="your-email@redhat.com"
   export JIRA_TOKEN="your-jira-api-token"
   ```
3. Clone the test plans repository (your fork):
   ```bash
   git clone https://github.com/YOUR-USERNAME/opendatahub-test-plans \
       ~/Code/opendatahub-test-plans
   ```
4. Install the skill (if reviewing locally):
   ```bash
   git clone https://github.com/fullsend-ai/test-creator \
       ~/ai/test-creator
   cd ~/ai/test-creator && uv sync --extra dev
   ```

## Workflow

### 1. Open the PR or MR

For manually triggered plans, find the PR in
`opendatahub-io/opendatahub-test-plans` on GitHub. PRs follow the
naming convention `Test Plan: <feature> (v<version>)` and are created
on branches named `test-plan/<JIRA_KEY>`.

For plans generated by the agentic CI pipeline, artifacts are published
to the [test-plans-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/test-plans-data)
repository on GitLab.

The PR/MR body contains the executive summary, scope, and test
objectives extracted from the test plan.

### 2. Read the artifacts

Each PR contains up to four types of artifact:

| File | Purpose |
|------|---------|
| `TestPlan.md` | The test plan -- 9 sections covering scope, strategy, environment, interfaces, test cases, NFRs, risks |
| `TestPlanGaps.md` | Known gaps where the AI lacked source material |
| `TestPlanReview.md` | Automated rubric scores with evidence and cross-references |
| `test_cases/TC-*.md` | Individual test case specifications |
| `test_cases/INDEX.md` | Summary index of all test cases by category and priority |

Start with `TestPlanReview.md` to understand what the automated
scorer found. Then read `TestPlanGaps.md` to see what the AI flagged
as unknown. These two files tell you where to focus your review of
`TestPlan.md`.

### 3. Review the test plan

Use the rubric criteria as your review framework. The automated scorer
catches structural issues, but domain expertise is needed for accuracy.

#### Specificity (Section 2, Section 8)

**Smell test**: Take any risk from Section 8 and mentally paste it into
a test plan for a completely different feature. If it still makes sense,
it's generic boilerplate.

What to check:
- Do P0/P1/P2 priority definitions in Section 2.3 reference
  feature-specific scenarios, or are they vague ("critical
  functionality", "core features")?
- Do risks in Section 8 name specific dependencies and failure modes
  unique to this feature?
- Are test levels in Section 2.1 justified by the actual interface
  types under test?

#### Grounding (Section 4)

**Smell test**: For every entry in Section 4 (interfaces under
test), can you point to the exact sentence in the strategy, ADR, or
any readable additional document (API spec, design doc) listed in the
test plan's `additional_docs` frontmatter? If not, it may be
fabricated.

What to check:
- Are interface paths, method signatures, and version numbers traceable
  to the strategy, ADR, or a readable additional document?
- Are unknowns marked as TBD (acceptable) rather than filled with
  plausible-sounding but invented details (not acceptable)?
- Does `TestPlanReview.md` contain a grounding cross-reference table?
  Check any entries marked "Suspected Fabrication" or "Extrapolated."

**This is the most important criterion for human review.** The
automated scorer can detect structural fabrication patterns, but only a
domain expert can verify whether a specific interface path or API
contract is real.

#### Scope Fidelity (Section 1, Section 4)

**Smell test**: List the strategy's deliverables. For each one, find a
test objective in Section 1.3 that covers it. Any orphans in either
direction indicate misalignment.

What to check:
- Does every in-scope item from the strategy map to at least one test
  objective?
- Are out-of-scope items truly absent from Section 4 interfaces?
- Is there scope creep (testing things the strategy doesn't mention)?

#### Actionability (Section 3, Section 9)

**Smell test**: Hand Sections 3 and 9 to a platform engineer who knows
nothing about the feature. Could they begin provisioning the test environment?
Questions about missing or vague versions or incomplete test-data examples
are advisory; inability to proceed because of missing Section 3.1 evidence,
bare TBDs, or unusable RBAC is blocking.

What to check:
- Are OpenShift and RHOAI versions specified? Missing or vague values are advisory and should be
  visible in `TestPlanGaps.md`; they do not by themselves lower `actionability == 2`. For a
  genuinely unknown required value, use `TBD — Resolution: {concrete action} from/with/by/before/after/using {named source or timing}`.
  A bare or unresolved TBD is blocking and cannot support a 2/2 score.
- Does test data include concrete format and examples, not just "sample data"? Missing or
  incomplete format/examples are advisory, but unresolved required values marked with a bare TBD
  remain blocking.
- Are test users defined with specific roles and permissions?
- Are infrastructure requirements concrete enough to act on?

Use the same unresolved-TBD rule for each occurrence in Sections 3.1, 3.2, and 3.3. A grounded
`TBD — Resolution: ...` path is non-blocking, including `derive` from a named overlay requirement;
a bare or unresolved TBD remains blocking. Count a data example only when it is in an explicit
`Example`/`Sample`/`Fixture` label or table column, or an `e.g.,`/`for example` clause. Arbitrary
inline backticks and broad words such as `token` are not sufficient evidence.

The deterministic actionability payload separates blocking `bare_tbd` and `missing_details` from
non-blocking `advisory_gaps`. A plan can be Ready with the latter. Missing Section 3.1
environment/configuration and missing or unusable RBAC role, permission, or resource evidence are
blocking; advisory gaps alone do not require revision or additional source documents.

#### Consistency (cross-section)

Run these six cross-checks:
1. Section 4 interfaces are a subset of Section 1.2 scope
2. Section 2.1 test levels match interface types in Section 4
3. Priority assignments in Section 6.1 match Section 2.3 definitions
4. Section 9.2 lists every interface from Section 4 (checked
   deterministically -- see `TestPlanReview.md`'s interface-coverage
   result)
5. Section 7 NFR categories are consistent with feature scope (e.g.,
   a feature that pulls images should not mark Disconnected as N/A)
6. Once populated, the Section 6.2 E2E Coverage Matrix must include every
   non-pending interface from Section 4, and each populated Section 6.2 row
   must contain at least one `TC-E2E-*` or `TC-UI-*` reference. The deterministic
   `interface-coverage` result reports `missing_in_6_2` when no filled row exists
   for a declared interface, and `missing_e2e_or_ui_in_6_2` when a declared
   interface has a row without either reference, including a deficient duplicate
   row when another duplicate satisfies coverage. An empty or placeholder matrix
   remains expected before create-cases runs.

### 4. Review test cases

If test cases (`test_cases/TC-*.md`) are included in the PR, review
them for:

#### Structure and completeness

- Does each TC have a clear **Objective** (one sentence)?
- Are **Test Steps** actionable and specific, not vague ("verify it
  works")?
- Are **Expected Results** observable facts that can be verified without
  subjective judgment?
- Is **Test Data** included where the test requires specific requests,
  payloads, or configurations?
- Are **Preconditions** listed only when there are specific requirements
  beyond the default test environment?

#### Coverage

- Does the test case set cover all interfaces from Section 4?
- Do P0 flows in Section 6.1 have adequate test case coverage (not
  just P2 test cases)?
- Is there a mix of positive, negative, and boundary test cases?
- Do E2E test cases (TC-E2E-*) and, where applicable, UI test cases
  (TC-UI-*) cover the user journeys described in the strategy?

#### Priority alignment

- Do test case priorities match the priority definitions in Section 2.3?
- Are the most critical user paths covered by P0 test cases?

#### Naming and organization

- Do test case IDs follow the `TC-<CATEGORY>-<NUMBER>` convention?
- Does `INDEX.md` accurately reflect the full set of test cases?
- Are categories consistent with Section 5.2 naming conventions?

### 5. Provide feedback

**Option A -- PR comments (recommended for team review)**

Leave inline comments on the PR. The test plan author can then use
`/test-plan-resolve-feedback <PR_URL>` to process your comments:

1. The skill reads all review comments from the PR
2. It assesses each comment against the test plan
3. The author decides which to apply (with your assessment as context)
4. Accepted changes are committed and pushed to the same branch
5. The version is bumped (e.g., 1.0.0 -> 1.0.1)

This is the preferred workflow because it preserves review history in
the PR and lets the author triage feedback with AI assistance.

**Option B -- Score only (standalone quality check)**

Run `/test-plan-score <feature_dir>` to get a rubric score without
modifying the plan. Useful for evaluating test plans created outside
the automated pipeline or for a quick quality check.

**Option C -- Direct editing**

For minor corrections (typos, version numbers you know), edit the files
directly and push. For significant changes, prefer Option A so the
changes are documented.

### 6. Approve

Once satisfied:

1. Approve the PR on GitHub
2. Add the `test-plan-human-reviewed` label to the source Jira issue
3. Merge the PR

The test plan is now the basis for test automation via
`/test-plan-case-implement`.

## What to Focus On (By Role)

### QE Engineer (feature owner)

You know the feature best. Focus on:
- **Grounding** -- Are the interfaces and API contracts real? Are
  versions correct?
- **Completeness** -- Are there test scenarios the AI missed that you
  know are important?
- **Environment** -- Can you actually set up the test environment from
  Sections 3 and 9?
- **Test cases** -- Are the test steps ones you could actually execute?

### Team Lead

Focus on:
- **Scope fidelity** -- Does the test plan match what was agreed in the
  strategy?
- **Priority alignment** -- Are the right things marked P0?
- **NFRs** -- Are disconnected, upgrade, performance, RBAC, and
  security considerations properly addressed or explicitly marked
  N/A with justification?
- **Gaps** -- Which gaps in `TestPlanGaps.md` are blocking, and which are
  advisory follow-up items that do not prevent testing from proceeding?

### Domain Expert / Architect

Focus on:
- **Grounding** -- Verify technical details against your knowledge of
  the component
- **Risks** -- Are the identified risks real? Are there risks the AI
  missed?
- **Architecture alignment** -- Does the test approach align with the
  component's architecture and integration points?

## Common Issues and How to Fix Them

| Issue | Where to Look | Fix |
|-------|--------------|-----|
| Generic priority definitions | Section 2.3 | PR comment: "P0 should reference [specific scenario]" |
| Fabricated interface paths | Section 4, TestPlanReview.md grounding table | PR comment with correct paths, or provide ADR |
| Missing test scenarios | Section 4, test_cases/ | PR comment describing the missing scenario |
| Vague environment setup | Sections 3, 9 | Treat missing/vague OpenShift or RHOAI versions as advisory; comment on missing Section 3.1 configuration or other blocking setup gaps |
| Missing test-data format/examples | Section 3.2, TestPlanGaps.md | Treat incomplete format/examples as advisory unless a required value is a bare/unresolved TBD |
| Scope creep (testing out-of-scope items) | Section 1.2 vs Section 4 | PR comment identifying out-of-scope entries |
| NFR marked N/A incorrectly | Section 7 | PR comment explaining why the category applies |
| TBDs that you can resolve | TestPlanGaps.md | Provide the answer or source doc for a blocking bare/unresolved TBD; do not require source documents solely for advisory version/data gaps |
| Inconsistent cross-references | Section 9.2 vs Section 4 | PR comment (often auto-fixed by the pipeline) |
| Missing E2E/UI coverage for interfaces | Section 6.2 | PR comment requesting an E2E or UI test case reference |

## Key Rules

1. **Review the review first.** Start with `TestPlanReview.md` and
   `TestPlanGaps.md` -- they tell you where the AI struggled.
2. **Grounding is your top priority.** The AI can structure a plan, but
   only you know if the technical details are real.
3. **Use PR comments for feedback.** `/test-plan-resolve-feedback`
   turns your comments into tracked, versioned changes.
4. **Resolve blocking TBDs with source documents.** If you can provide an
   ADR, API spec, or design doc, the author can re-run analyzers to fill
   blocking gaps automatically. Advisory version/data gaps remain visible
   and do not by themselves require another source document.
5. **Don't fix what the pipeline can fix.** Consistency issues
   (mismatched tables, missing cross-references) are often handled by
   auto-revision. Focus your review on domain accuracy.
6. **Check fabrication carefully.** A plausible-sounding interface
   path that doesn't exist is worse than a TBD, because downstream
   test cases will be built on it.

## Artifact Lifecycle

```
    Manual (Claude Code)                Automated (Agentic CI)
    ────────────────────                ──────────────────────
/test-plan-create RHAISTRAT-NNN     STRAT label detected by
        |                           test-plan-generator
        v                                   |
  TestPlan.md (Draft, v1.0.0)               v
  TestPlanGaps.md                   Same generation pipeline
  TestPlanReview.md (rubric scores)         |
        |                                   |
        v                                   v
/test-plan-create-cases             test_cases generated
        |                                   |
        v                                   v
  test_cases/TC-*.md                        |
  test_cases/INDEX.md                       |
        |                                   |
        v                                   v
/test-plan-publish                  Publish to GitLab (WIP)
        |                                   |
        v                                   v
  GitHub PR                         GitLab test-plans-data
        |                                   |
        +---------------+------------------+
                        |
                   Human Review  <-- you are here
                        |
                   +---------+----------+
                   |                    |
                   v                    v
                 Approve            Request Changes
                   |                    |
                   v                    v
                 Merge             /test-plan-resolve-feedback
                 + label             (applies accepted feedback,
                                      bumps version, pushes)
                                        |
                                        v
                                    Re-review
```

## Resources

- [README](../README.md) -- Installation, usage, full pipeline diagram
- [CHANGELOG](../CHANGELOG.md) -- Version history
- [Rubric details](../skills/test-plan-review/prompts/score-agent.md)
  -- Full scoring criteria with smell tests
- [Calibration example](../skills/test-plan-review/calibration/)
  -- Scored examples for rubric anchoring
- [Test plan template](../skills/test-plan-create/test-plan-template.md)
  -- The 10-section template structure
- [Test case template](../skills/test-plan-create-cases/test-case-template.md)
  -- TC structure and field definitions
