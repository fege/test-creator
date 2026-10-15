---
name: test-plan-generate-test-file
description: Generate one complete test file with all functions for assigned test cases, including quality scoring and auto-revision
user-invocable: false
context: fork
model: claude-opus-4-6
allowedTools:
  - Read
  - Bash
  - Skill
---

# Test File Generator Sub-Agent

Generate a complete test file for test cases assigned to one file from the file_mapping.

**Called in parallel** by test-plan-case-implement (one sub-agent per file in file_mapping).

**IMPORTANT:** This sub-agent does NOT write files to their final destination. It:
1. Assembles test file content in memory
2. Validates syntax using bash (`echo > /tmp/...`)
3. Writes result to /tmp/test_plan_results/file_{i}.json
4. Returns tiny confirmation JSON
5. Parent reads files and writes to target repositories

Write tool is intentionally excluded from allowedTools. Uses `context: fork` for clean return.

## Inputs (from Skill args / `$ARGUMENTS`)

Parent passes all data via Skill `args` as a JSON block:
```json
{
  "file_index": 0,
  "file_path": "tests/upgrade/test_odh_cli.py",
  "test_cases": [
    {"test_case_id": "TC-CLI-001", "title": "...", "objective": "...", ...},
    {"test_case_id": "TC-CLI-003", ...}
  ],
  "function_names": ["test_tc_cli_001", "test_tc_cli_003_pre_upgrade_readiness"],
  "framework": "pytest",
  "conventions_file": "/path/to/conventions.md",
  "pattern_guide": "...content or null...",
  "repo_instructions": "...content or null...",
  "common_setup_requirements": [...],
  "target_repo_path": "/path/to/repo",
  "feature_dir": "/path/to/feature"
}
```

Parse this JSON from `$ARGUMENTS` to extract all needed variables.

## Process

### Shared helper path

Before running any test-plan helper, prepare the caller workspace:

```bash
bash "${CLAUDE_SKILL_DIR}/../../scripts/bootstrap.sh" --layout "${CLAUDE_SKILL_DIR}" || exit 1
```

### Step 0: Extract Data from Prompt

Extract JSON data block from `$ARGUMENTS`. Parse to get:
- `file_index` - Index for temp file naming
- `file_path` - Target file path in the target repo
- `test_cases` - Array of TC objects for this file (already filtered)
- `function_names` - Array of function names for TCs
- `framework` - Test framework (pytest, go, jest)
- `conventions_file` - Path to conventions file
- `pattern_guide` - Pattern guide content (or null)
- `repo_instructions` - Repo instructions content (or null)
- `common_setup_requirements` - Array of shared preconditions
- `target_repo_path` - Repository path
- `feature_dir` - Feature directory path

Store `test_cases` as `tcs_for_this_file` for use in later steps.

### Step 1: Check Existing Test File

**IMPORTANT:** When analyzing target repository: Read code files and use grep/bash. Do NOT import target repo dependencies (not in test-plan venv) or use inspect.signature().

Get full file path: `<target_repo_path>/<file_path>`

If file exists, list existing functions:
```bash
(cd "$(cd -P "${CLAUDE_SKILL_DIR}/../.." && pwd -P)" && uv run python scripts/list_test_functions.py "$full_file_path")
```

Returns JSON: `{"functions": [{"name": "...", "line": 42, "docstring": "..."}]}`

**Semantic matching:** For each TC and expected function name, check if semantic match exists:
- Compare TC title/objective with function name/docstring  
- If match: Mark TC as already_implemented, store function details
- Use LLM judgment for semantic equivalence

If already-implemented tests found, ask user via AskUserQuestion:
```
✓ Found {N} already-implemented test(s) in {file_path}:
  - TC-E2E-001: test_notebook_creation (line 42)

Options:
1. Skip them - Only implement missing tests
2. Re-generate - Overwrite existing functions
3. Review - Show me existing code first
```

Set `mode`: "create" (new file), "append" (add to existing), or filter out implemented TCs.

### Step 2: Generate File Header

If `mode == "create"` (new file), generate header with:

1. **Module docstring** - Brief description
2. **Import statements** - Based on framework:
   - Read pattern_guide examples to see common imports
   - Read repo_instructions for import style
   - Add framework imports (pytest, unittest, etc.)
   - Add repo-specific utilities from pattern examples
3. **Common fixtures** - If `common_setup_requirements` has items used in this file:
   - Generate fixture functions for shared preconditions
   - Use framework's fixture decorator
   - Reference in test function parameters

### Step 3: Generate Test Functions

For each TC in `tcs_for_this_file` (sequential):

**Generate function code** using TC spec + conventions + patterns with this priority:

1. **CONSTITUTION.md** (in repo_instructions) - Hard constraints that MUST be followed
2. **CLAUDE.md / AGENTS.md** (in repo_instructions) - Repo testing guidelines and conventions
3. **odh-test-context conventions** (in conventions_file) - Repo-specific patterns (markers, file patterns, fixtures, test commands)
4. **Tiger Team pattern guides** (in pattern_guide) - Framework-specific patterns (pytest-tests.md, go-tests.md with code examples)

**Function structure:**

**Decorators/Markers:**
- Read available markers from conventions_file (odh-test-context provides marker list)
- Map TC priority → repo markers (P0 → tier1 or p0)
- Map TC category → repo markers (API → api)
- **Only use markers registered in the repo** (conventions + existing test examples). Never emit
  an unregistered marker — it breaks collection under `--strict-markers`.
- **Negative tests → the repo's negative tier** (commonly `tier3`), not `tier1`.
- **Tests that need live external API access → `skip_on_disconnected`** (or the repo's equivalent).
- Do NOT add team markers unless the repo's existing tests actually use them.

**Function Signature:**
- Use provided function_name exactly
- Add fixture parameters based on preconditions
- Follow conventions import style

**Docstring:**
- Format: `{tc_id}: {objective}`
- Example: `TC-E2E-001: Verify metadata fields match expected schema`

**Implementation** (AAA pattern):
- **Arrange**: Setup from preconditions
- **Act**: Execute test steps
- **Assert**: Validate expected results with messages

**Correctness guardrails (avoid false-green tests):**

A test that passes while the feature is absent or broken is worse than no test. Apply these:

- **Activation gate:** If the feature-under-test has an enablement/activation gate, derive the gate
  from the actual distribution/config source (e.g. the distribution `run.yaml` env var like
  `ENABLE_GEMINI`), **not** from the credential name (`GEMINI_API_KEY`). Injecting only the
  credential can leave the feature inactive so every test passes while exercising nothing. If the
  gate cannot be verified, emit a prominent `TODO` **and** a fixture assertion that fails loudly when
  the feature is not actually active.
- **Feature-specific signal (false green):** Assert a signal that would *differ* if the feature were
  broken/absent — presence of the provider/model under test, provider-identity checks, a
  distinguishing response field. Never assert only generic success (e.g. "all requests returned
  200"), which passes for any working backend.
- **skip vs. fail:** Classify each precondition. Environment/harness prerequisite not guaranteed in
  the target env (secondary API keys, packet-capture tooling, MCP harness) → `pytest.skip`.
  Something the active feature *must* provide (a model the active provider should register, the
  provider itself) → `pytest.fail`. Do NOT default every missing precondition to `skip` — that hides
  the exact defects the test exists to catch.
- **Tight assertions:** Use exact type checks over broad ABCs (validate embedding floats with
  `float`, not `numbers.Real`, which also accepts `int`/`bool`); add finiteness checks
  (reject `NaN`/`inf`); assert a collection is non-empty before indexing (`response.choices[0]`);
  iterate **all** candidates (every container/file/match), not just the first.
- **No probabilistic assertions:** Do not assert on stochastic model output (e.g. temperature
  variability ordering) or anything you cannot verify with the available harness (e.g. on-wire
  parameter forwarding without request capture). Generate the deterministic subset that *can* be
  checked and document the unverifiable gap instead of a flaky assertion.
- **Bounded loops:** Every stream-consume / poll loop needs a max-iteration or deadline bound that
  fails loudly on overrun — never iterate until the server closes an unbounded stream. A bound
  checked inside the loop does not stop a blocking read, so also set a client-level read timeout (or
  cancellation) that enforces the deadline on a stalled `next()`/socket read; on timeout, close the
  stream and fail the test.
- **Helper safety:** Apply the same bar to generated helper/util code as to tests. Never invoke a
  shell on values that may be influenced by test input — use argv-form subprocess calls with
  `shell=False` and allowlist the executable and argument choices; never use `shell=True`,
  `os.system`, or `sh -c` (CWE-78). Use exact comparison over substring (`"SET" in output` also
  matches `"UNSET"`); reject unknown enum values explicitly instead of silently falling through to a
  default.

Collect each generated function in `functions` array.

### Step 4: Assemble Complete File

- **mode == "create"**: `complete_file = header + "\n\n".join(functions)`
- **mode == "append"**: `complete_file = existing_content + "\n\n".join(functions)`

### Step 5: Validate Syntax

```bash
cat > /tmp/test_file_${file_index}.py << 'PYEOF'
$complete_file
PYEOF
python -m py_compile /tmp/test_file_${file_index}.py 2>&1
```

If syntax error: Fix once, retry. If still invalid: save as .draft, skip scoring.

### Step 6: Score Quality

This skill has Bash; `test-plan-score-test-function` does not. Load calibration here and pass
it via a temp file. Fail closed on nonzero exit. Adding a pair is dropping a file under
`skills/test-plan-score-test-function/calibration/core/`, `calibration/ui/`, or a team dir.

```bash
repo_root=$(cd -P "${CLAUDE_SKILL_DIR}/../.." && pwd -P)
team_list=$(cd "$repo_root" && uv run python scripts/get_component_test_dir.py \
    --teams-only "$feature_dir") || {
    echo "ERROR: scripts/get_component_test_dir.py --teams-only failed — stopping." >&2
    echo "$team_list" >&2
    exit 1
}

calibration_raw=$(cd "$repo_root" && uv run python scripts/load_calibration.py \
    "${CLAUDE_SKILL_DIR}/../test-plan-score-test-function/calibration" \
    --framework "$framework" --include-teams="$team_list") || {
    echo "ERROR: scripts/load_calibration.py failed — stopping." >&2
    echo "$calibration_raw" >&2
    exit 1
}

printf '%s\n' "$calibration_raw" | jq -r '.calibration_text' > /tmp/calibration_${file_index}.md
printf '%s\n' "$calibration_raw" | jq -r '.warnings[]?' >&2
```

For each function, invoke in parallel:

```bash
/test-plan-score-test-function \
  --test-code-file /tmp/func_${tc_id}.py \
  --tc-file <tc_file_path> \
  --conventions-file <conventions_file> \
  --framework <framework> \
  --output-file /tmp/test_scores/${tc_id}_score.md \
  --calibration-file /tmp/calibration_${file_index}.md
```

Parse score, handle verdicts:
- **7-10:** Accept
- **4-6:** Auto-revise (re-generate with feedback)
- **0-3:** Save as .draft

**MAX REVISIONS: 1 per function**

### Step 7: Return Result to Parent

#### 7a: Write Result to File and Return Confirmation

Build metadata JSON and write to persistent location:

```bash
# Create results directory
mkdir -p /tmp/test_plan_results

# Build metadata JSON
cat > /tmp/file_metadata_${file_index}.json << EOF
{
  "file_index": ${file_index},
  "file_path": "${file_path}",
  "tc_ids": ${tc_ids_for_file_json},
  "functions": ${functions_json},
  "quality_summary": ${quality_summary_json},
  "draft_files": ${draft_files_json},
  "errors": ${errors_json}
}
EOF

# Format and write complete result (reads /tmp/test_file_${file_index}.py, embeds content)
(cd "$(cd -P "${CLAUDE_SKILL_DIR}/../.." && pwd -P)" && uv run python scripts/format_file_result.py /tmp/file_metadata_${file_index}.json) > /tmp/test_plan_results/file_${file_index}.json

# Output tiny confirmation (NOT full JSON - keeps context clean)
echo '{"status": "complete", "file_index": '${file_index}', "result_file": "/tmp/test_plan_results/file_'${file_index}'.json"}'
```

**CRITICAL:** Output ONLY the tiny confirmation JSON. Do NOT add:
- Narrative summaries ("Sub-agent complete...")
- Full file content or quality data
- Success messages
- Any text after the JSON

The parent reads the full result from the file. This keeps the return value small (~100 bytes) and avoids polluting parent context.

#### 7b: Clean Up Temp Work Files

Clean up temporary work files (keep result file for parent):

```bash
# Remove temp work files (parallel-safe - indexed by file_index and unique tc_ids)
rm -f /tmp/test_file_${file_index}.py
rm -f /tmp/file_metadata_${file_index}.json

# Remove per-TC temp files
for tc_id in ${tc_ids_for_file[@]}; do
    rm -f /tmp/func_${tc_id}.py
    rm -f /tmp/test_scores/${tc_id}_score.md
    rm -f /tmp/test_scores/${tc_id}_score_revised.md
done

# DO NOT remove /tmp/test_plan_results/file_${file_index}.json - parent will read it
```

**Why keep result file:** Parent needs to read the full result after all sub-agents complete. Parent will cleanup /tmp/test_plan_results/ after reading all files.

**CRITICAL:** After Step 7b cleanup completes, this sub-agent is DONE. Do NOT output any additional text, summaries, or explanations. The tiny confirmation JSON from Step 7a is the complete return value. The parent skill will read the full result from the file and proceed automatically.

---

## Style Decision Priority

When making code generation decisions, follow this priority:

1. **CONSTITUTION.md** (in repo_instructions) - Hard constraints, never violate
2. **CLAUDE.md / AGENTS.md** (in repo_instructions) - Repo-level testing requirements
3. **odh-test-context conventions** (in conventions_file) - Repo-specific test patterns from Tiger Team's repository analysis (markers, fixtures, test commands, linting)
4. **Tiger Team pattern guides** (in pattern_guide) - Framework-specific patterns with code examples (pytest-tests.md, go-tests.md, jest-tests.md)
5. **General framework conventions** - Standard framework idioms

odh-test-context and Tiger Team guides are both from the Tiger Team - one analyzes repos, one provides framework patterns.

## Error Handling

- Syntax error after fix: Save as .draft, continue
- Scorer fails: Accept without score, log warning  
- Generation fails: Log error, continue

**Philosophy:** Partial success > total failure.

$ARGUMENTS
