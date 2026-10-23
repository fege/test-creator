"""
Test data constants for TestPlan.md artifact tests.

Provides valid/invalid TestPlan content templates for validation tests.
"""

from scripts.utils.schemas import TEMPLATE_HEADINGS

# Valid TestPlan.md content for validation tests
VALID_TESTPLAN_CONTENT = f"""---
source_key: RHAISTRAT-1507
feature: Notebook Spawning
version: 1.0.0
status: Draft
components:
  - Notebooks
  - AI Hub
---

{TEMPLATE_HEADINGS["1"]}
Test notebook spawning feature.

{TEMPLATE_HEADINGS["1.2"]}
This feature enables users to spawn Jupyter notebooks.
"""

# TestPlan.md with only e2e/UI test levels (valid scope)
TESTPLAN_E2E_ONLY = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

1. Verify model deployment via e2e system test (AC: "Users can deploy models")
2. Verify dashboard navigation via UI test (AC: "Dashboard shows model status")

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **E2E System Testing** — end-to-end workflows through API and CLI
- **UI Testing** — dashboard interactions and form validation

{TEMPLATE_HEADINGS["2.2"]}

- **Positive Testing** — valid inputs
"""

# TestPlan.md with disallowed test levels (invalid scope)
TESTPLAN_BROAD_LEVELS = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

1. Verify API endpoint returns correct data
2. Verify UI renders correctly

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **API Integration Testing** — REST endpoint testing against backend
- **Data Validation Testing** — data transformation, persistence
- **E2E System Testing** — end-to-end workflows
- **Functional Testing** — business logic, filtering

{TEMPLATE_HEADINGS["2.2"]}

- **Positive Testing** — valid inputs
"""

# TestPlan.md with no Section 2.1
TESTPLAN_NO_SECTION_21 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.2"]}

- **Positive Testing** — valid inputs
"""

# TestPlan.md with all AC citations present (valid)
# Objective 1's (AC: ...) is wrapped onto a continuation line — the parser must join
# continuation lines before checking, or it reads objective 1 as uncited.
TESTPLAN_AC_CITED = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

1. Verify model deployment works end-to-end
   (AC: #1 — "Users can deploy models from the catalog")
2. Verify dashboard shows status (AC: #2 — "Model status is visible in the dashboard")
3. Verify RBAC enforcement (AC: #3 — "Non-admin users cannot delete models")

{TEMPLATE_HEADINGS["2"]}
"""

# TestPlan.md with missing AC citations (invalid)
TESTPLAN_AC_MISSING = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

1. Verify model deployment works end-to-end (AC: #1 — "Users can deploy models")
2. Verify dashboard shows correct status
3. Verify RBAC enforcement for admin users (AC: #3 — "Admin users can manage all models")

{TEMPLATE_HEADINGS["2"]}
"""

# TestPlan.md with bullet-style objectives (not numbered — triggers format error)
TESTPLAN_AC_BULLET_FORMAT = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

- **Obj-1**: Verify catalog tile is visible (AC: "tile is visible")
- **Obj-2**: Verify dialog displays samples (AC: "samples displayed")

{TEMPLATE_HEADINGS["2"]}
"""

# TestPlan.md with no Section 1.3
TESTPLAN_NO_SECTION_13 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["2"]}
"""

# TestPlan.md body content with proper structure (no frontmatter)
TESTPLAN_VALID_BODY = f"""
# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.1"]}

Test the feature.

{TEMPLATE_HEADINGS["1.2"]}

In scope items.

{TEMPLATE_HEADINGS["1.3"]}

1. Verify something (AC: #1 — "acceptance criterion")

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **E2E System Testing** — end-to-end workflows

{TEMPLATE_HEADINGS["2.2"]}

- **Positive Testing** — valid inputs

{TEMPLATE_HEADINGS["2.3"]}

- **P0 (Critical)** — core flows

{TEMPLATE_HEADINGS["3"]}

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["7"]}

{TEMPLATE_HEADINGS["8"]}

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | | |
| `/v1/models` | | |
"""

# TestPlan.md with bold-text pseudo-headings (invalid structure)
TESTPLAN_BOLD_HEADINGS = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.1"]}

Test the feature.

{TEMPLATE_HEADINGS["1.2"]}

In scope items.

{TEMPLATE_HEADINGS["1.3"]}

1. Verify something (AC: #1 — "acceptance criterion")

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **E2E System Testing** — end-to-end workflows

{TEMPLATE_HEADINGS["2.2"]}

- **Positive Testing** — valid inputs

{TEMPLATE_HEADINGS["2.3"]}

- **P0 (Critical)** — core flows

{TEMPLATE_HEADINGS["3"]}

{TEMPLATE_HEADINGS["4"]}

{TEMPLATE_HEADINGS["7"]}

**Measurement Points:**

Some content here.

**Purpose:**

More content.

{TEMPLATE_HEADINGS["8"]}

{TEMPLATE_HEADINGS["9"]}
"""

# TestPlan.md missing required sections
TESTPLAN_MISSING_SECTIONS = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.1"]}

Test the feature.

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["9"]}
"""

# TestPlan.md with allowed TC categories in Section 5.2 (valid)
TESTPLAN_VALID_CATEGORIES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["5"]}

{TEMPLATE_HEADINGS["5.1"]}

3 test cases total.

{TEMPLATE_HEADINGS["5.2"]}

Test cases follow the naming pattern: `TC-<CATEGORY>-<NUMBER>`

| Prefix | Meaning |
|--------|---------|
| TC-E2E | End-to-end user journey flows |
| TC-UI | Browser-based UI interaction flows |
| TC-NEG | Negative and error path journeys |
"""

# TestPlan.md with feature-area TC categories in Section 5.2 (invalid)
TESTPLAN_FEATURE_CATEGORIES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["5"]}

{TEMPLATE_HEADINGS["5.1"]}

5 test cases total.

{TEMPLATE_HEADINGS["5.2"]}

Test cases follow the naming pattern: `TC-<CATEGORY>-<NUMBER>`

| Prefix | Meaning |
|--------|---------|
| TC-CSAF | Content safety filtering tests |
| TC-AUTH | Authentication and authorization tests |
| TC-TOPIC | Topical blocking tests |
| TC-E2E | End-to-end user journey flows |
"""

# TestPlan.md with no Section 5.2
TESTPLAN_NO_SECTION_52 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["5"]}

{TEMPLATE_HEADINGS["5.1"]}

0 test cases.

{TEMPLATE_HEADINGS["6"]}
"""

# TestPlan.md with valid interface types in Section 4 (no Config)
TESTPLAN_VALID_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| Inference gRPC | gRPC | Streaming inference |
| `oc get` | CLI | Cluster inspection |
| NemoGuardrails CRD | CRD | Guardrail configuration |
| Dashboard model page | UI | Model management |
"""

# Section 4 header row has a blank cell — the validator must report the real header row
# (above the separator), not silently promote the first data row to "header".
TESTPLAN_INTERFACE_TYPES_BLANK_HEADER_CELL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type |  |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
"""

# TestPlan.md with Config-type entries in Section 4 (invalid)
TESTPLAN_CONFIG_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `config.yaml` | Config | Runtime configuration |
| `BASE_URL` env var | Config | Service endpoint |
| Dashboard model page | UI | Model management |
"""


# TestPlan.md with Database-type entry in Section 4 (invalid — not in allowlist).
# Interface name itself contains "---" so this also regression-covers separator-row
# detection: a data row must not be mistaken for the header's "---" divider row.
TESTPLAN_DATABASE_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| legacy---store | Database | Purpose |
"""

# TestPlan.md with wrong-case ReST type in Section 4 (invalid — allowlist is exact)
TESTPLAN_REST_WRONG_CASE_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| Chat completions API | ReST | Purpose |
"""

# TestPlan.md with empty Type cell in Section 4 (invalid — empty types fail)
TESTPLAN_EMPTY_TYPE_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| Widget API |  | Purpose |
"""

# Section 4 table with no separator row — data Type must still be checked.
TESTPLAN_NO_SEPARATOR_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
| Unseparated datastore | Database | Purpose |
"""

# Section 4 data row with a single cell (no Type column) — Type is treated as empty.
TESTPLAN_MISSING_TYPE_COLUMN_INTERFACES = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| Single-cell interface |
"""

# TestPlan.md where Section 9.2 and 6.2 fully cover Section 4 interfaces
# Full coverage, but Section 4 uses bold/plain formatting while 6.2/9.2 use backticks —
# normalization must still match them (regression for exact-string-equality false failures).
TESTPLAN_INTERFACE_COVERAGE_FULL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| **/v1/chat/completions** | REST | Chat inference |
| /v1/models | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |
| `/v1/models` | TC-E2E-002 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | TC-E2E-002 | |
"""

# TestPlan.md where Section 6.2 is populated with UI-only test case references.
TESTPLAN_INTERFACE_COVERAGE_UI_ONLY_6_2 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-UI-001 |
| `/v1/models` | TC-UI-002 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-UI-001 | |
| `/v1/models` | TC-UI-002 | |
"""

# TestPlan.md where Section 6.2 rows are populated but reference neither an E2E
# nor a UI test case.
TESTPLAN_INTERFACE_COVERAGE_NO_E2E_OR_UI_6_2 = TESTPLAN_INTERFACE_COVERAGE_UI_ONLY_6_2.replace(
    "TC-UI-001", "Manual coverage note"
).replace("TC-UI-002", "Manual coverage note")

# TestPlan.md where Section 6.2 contains both UI and E2E references.
TESTPLAN_INTERFACE_COVERAGE_MIXED_6_2 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-UI-001, TC-E2E-001 |
| `/v1/models` | TC-E2E-002 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-UI-001, TC-E2E-001 | |
| `/v1/models` | TC-E2E-002 | |
"""

# TestPlan.md where duplicate Section 6.2 rows for one declared interface both
# satisfy the E2E-or-UI contract.
TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_MIXED_6_2 = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
    "| `/v1/chat/completions` | TC-E2E-001 |",
    "| `/v1/chat/completions` | TC-E2E-001 |\n| `/v1/chat/completions` | TC-UI-001 |",
    1,
)

# TestPlan.md where a satisfying duplicate must not mask a populated duplicate
# with neither an E2E nor a UI reference.
TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_NO_E2E_OR_UI_6_2 = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
    "| `/v1/chat/completions` | TC-E2E-001 |",
    "| `/v1/chat/completions` | TC-E2E-001 |\n| `/v1/chat/completions` | Manual coverage note |",
    1,
)

# Template where a satisfying duplicate row must not mask a duplicate row whose
# scenario/reference cell is blank or a table placeholder.
TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_PLACEHOLDER_TEMPLATE_6_2 = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
    "| `/v1/chat/completions` | TC-E2E-001 |",
    "| `/v1/chat/completions` | TC-E2E-001 |\n| `/v1/chat/completions` | __SCENARIO_REFERENCE__ |",
    1,
)

# TestPlan.md where duplicate Section 6.2 rows all contain E2E references.
TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_E2E_6_2 = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
    "| `/v1/chat/completions` | TC-E2E-001 |",
    "| `/v1/chat/completions` | TC-E2E-001 |\n| `/v1/chat/completions` | TC-E2E-003 |",
    1,
)

# Extra populated Section 6.2 rows for undeclared interfaces are outside this
# validator's contract and must not affect declared-interface coverage.
TESTPLAN_INTERFACE_COVERAGE_EXTRA_6_2_ROW = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
    "| `/v1/models` | TC-E2E-002 |",
    "| `/v1/models` | TC-E2E-002 |\n| `/v1/undeclared` | TC-UI-999 |",
    1,
)

# TestPlan.md where Section 9.2 is missing an interface from Section 4
TESTPLAN_INTERFACE_COVERAGE_MISSING_9_2 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| | |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
"""

# TestPlan.md where Section 6.2 is populated but missing an interface from Section 4
TESTPLAN_INTERFACE_COVERAGE_MISSING_6_2 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | | |
| `/v1/models` | | |
"""

# TestPlan.md where Section 6.2 is still the pre-create-cases placeholder (skip check)
TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_6_2 = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| | |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | TC-E2E-002 | |
"""

# TestPlan.md where an interface is marked "pending details" in Section 4 and is
# absent from both Section 6.2 and 9.2 — it must be excluded from the missing lists.
TESTPLAN_INTERFACE_COVERAGE_PENDING = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | pending details |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
"""

# TestPlan.md where Section 9.2 lists the interface but its Test Cases cell is blank
TESTPLAN_INTERFACE_COVERAGE_EMPTY_9_2_CELL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |
| `/v1/models` | TC-E2E-002 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | | |
"""

# TestPlan.md where Section 6.2 lists the interface but its E2E Scenarios cell is blank
TESTPLAN_INTERFACE_COVERAGE_EMPTY_6_2_CELL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |
| `/v1/models` | |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | TC-E2E-002 | |
"""

# TestPlan.md where Section 9.2's Test Cases cell is a non-informative placeholder,
# not a real TC ID
TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_TC_CELL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |
| `/v1/models` | TC-E2E-002 |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | TBD | |
"""

# TestPlan.md where Section 6.2's E2E Scenarios cell is a non-informative placeholder,
# not a real TC ID
TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_SCENARIO_CELL = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["4"]}

| Interface | Type | Purpose |
|-----------|------|---------|
| `/v1/chat/completions` | REST | Chat inference |
| `/v1/models` | REST | List models |

{TEMPLATE_HEADINGS["6"]}

{TEMPLATE_HEADINGS["6.2"]}

| Interface (from Section 4) | E2E Scenarios |
|----------------------------|---------------|
| `/v1/chat/completions` | TC-E2E-001 |
| `/v1/models` | - |

{TEMPLATE_HEADINGS["9"]}

{TEMPLATE_HEADINGS["9.2"]}

| Interface | Test Cases | Coverage |
|-----------|------------|----------|
| `/v1/chat/completions` | TC-E2E-001 | |
| `/v1/models` | TC-E2E-002 | |
"""

# TestPlan.md with clean test infra (no SUT/dev tooling)
TESTPLAN_CLEAN_INFRA = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["3.1"]}
- OpenShift 4.16+
- RHOAI 3.5 operator
- `KUBECONFIG` env var for cluster access
- CatalogSource for operator subscription

{TEMPLATE_HEADINGS["3.4"]}
- oc/kubectl for cluster interaction
- curl for API testing
- pytest for test execution
"""

# TestPlan.md with local dev tooling leaked into infra sections
TESTPLAN_DEV_TOOLING_INFRA = f"""---
feature: Test Feature
source_key: RHAISTRAT-400
version: 1.0.0
status: Draft
last_updated: 2026-07-15
author: QE Team
---

# Test Feature Test Plan

{TEMPLATE_HEADINGS["3.1"]}
- OpenShift 4.16+
- Local development runtime: Python 3.x with pip
- Container runtime (podman or docker)
- `KUBECONFIG` env var for cluster access

{TEMPLATE_HEADINGS["3.4"]}
- oc/kubectl for cluster interaction
- pip install for local development
- docker-compose for local SUT setup
- Ollama for local LLM inference
"""

VALID_TEST_PLAN_BODY_FOR_CASES_VALIDATION = f"""# Test Feature Test Plan

{TEMPLATE_HEADINGS["1"]}

{TEMPLATE_HEADINGS["1.3"]}

1. Verify a test case is traceable (AC: #1 — "The generated case references an objective.")

{TEMPLATE_HEADINGS["9.1"]}

| Category | Count |
| --- | ---: |
| TC-E2E | 1 |
| **Total** | **1** |
"""

VALID_TEST_PLAN_DATA = {
    "feature": "Test Feature",
    "source_key": "RHAISTRAT-400",
    "version": "1.0.0",
    "status": "Draft",
    "last_updated": "2026-04-14",
    "author": "QE Team",
}

VALID_TEST_PLAN_REVIEW_DATA = {
    "feature": "Test Feature",
    "source_key": "RHAISTRAT-400",
    "score": 8,
    "pass": True,
    "verdict": "Ready",
    "scores": {
        "specificity": 2,
        "grounding": 2,
        "scope_fidelity": 1,
        "actionability": 2,
        "consistency": 1,
    },
    "auto_revised": False,
    "last_updated": "2026-04-14",
}

# README.md fixtures for validate.py readme and the Fullsend handoff-file check
README_STRAT_URL = "https://issues.example.com/browse/RHAISTRAT-400"
README_VALID = f"""# Test Feature

Strategy: {README_STRAT_URL}

- Test plan: [TestPlan.md](TestPlan.md)
"""
README_NO_STRAT_URL = "# Test Feature\n\n- Test plan: [TestPlan.md](./TestPlan.md)\n"
README_LONGER_STRAT_KEY = f"# Test Feature\n\nStrategy: {README_STRAT_URL}0\n\nSee [TestPlan.md](TestPlan.md).\n"
README_NO_TESTPLAN_LINK = f"# Test Feature\n\nStrategy: {README_STRAT_URL}\n\nSee TestPlan.md for details.\n"
HANDOFF_FEATURE_DIR = "plans/test_feature"
