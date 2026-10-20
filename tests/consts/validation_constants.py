"""Constants for validation pattern tests"""

from scripts.utils.schemas import TEMPLATE_HEADINGS
from scripts.utils.validation_config_loader import load_boilerplate_patterns, load_scope_patterns

# Load actual production configs (single source of truth)
CORE_SCOPE_PATTERNS = load_scope_patterns("scripts/checks", teams=None)
CORE_BOILERPLATE_PATTERNS = load_boilerplate_patterns("scripts/checks", teams=None)

# TestPlan.md with boilerplate in multiple sections (invalid)
TESTPLAN_WITH_BOILERPLATE = f"""---
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

1. Verify the registration works as expected
2. Verify error handling works correctly
3. Test core functionality of the API

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **E2E System Testing** — end-to-end workflows

{TEMPLATE_HEADINGS["2.3"]}

- **P0 (Critical)** — core functionality, basic workflow

{TEMPLATE_HEADINGS["8"]}

**Risk**: Dependency on external services

**Mitigation**: Monitor service health

**Risk**: Environment instability

**Mitigation**: Improve infrastructure
"""

VALID_CITATIONS = {"valid": True, "total": 5, "cited": 5, "uncited": [], "invalid_citations": []}
VALID_COVERAGE = {"valid": True, "ac_count": 5, "covered": [1, 2, 3, 4, 5], "missing": []}
INVALID_CITATIONS = {
    "valid": False,
    "total": 2,
    "cited": 0,
    "uncited": [{"text": "1. Verify login (AC: Given a user logs in...)", "line_number": 79}],
    "invalid_citations": [
        {"text": "2. Verify logout (AC: #9 — out of range)", "line_number": 82, "reasons": ["out_of_range"]}
    ],
}
INVALID_COVERAGE = {"valid": False, "ac_count": 5, "covered": [1], "missing": [2, 3, 4, 5]}

VALID_SCOPE_CHECK = {"valid": True, "violations": []}
INVALID_SCOPE_CHECK = {
    "valid": False,
    "violations": [
        {
            "file": "TestPlan.md",
            "line": 10,
            "section": "2.1",
            "matched_pattern": "Unit Testing",
            "violation_type": "forbidden_test_level",
            "context": "- **Unit Testing** — component logic",
        }
    ],
}

VALID_BOILERPLATE = {"valid": True, "total_violations": 0, "by_section": {}}
VALID_SCOPE_COVERAGE = {"valid": True, "missing": [], "unmapped_objectives": []}
INVALID_SCOPE_COVERAGE = {
    "valid": False,
    "missing": [
        {
            "section": "2.3",
            "text": "Optional description and tags",
            "reason": "no Section 1.3 objective",
        }
    ],
    "unmapped_objectives": [],
}
INVALID_SCOPE_COVERAGE_REVERSE = {
    "valid": False,
    "missing": [],
    "unmapped_objectives": [
        {
            "section": "1.3",
            "text": "Verify an invented deliverable",
            "reason": "no grounded strategy requirement",
        }
    ],
}
VALID_ACTIONABILITY = {"valid": True, "bare_tbd": [], "missing_details": [], "advisory_gaps": []}
INVALID_ACTIONABILITY = {
    "valid": False,
    "bare_tbd": ["OpenShift version", "RHOAI version"],
    "missing_details": ["RBAC roles and permissions"],
    "advisory_gaps": [],
}
BOILERPLATE_THREE_VIOLATIONS = {
    "valid": False,
    "total_violations": 3,
    "by_section": {
        "1.3": [
            {
                "file": "TestPlan.md",
                "line": 5,
                "matched_pattern": "works as expected",
                "context": "1. Verify it works as expected",
                "category": "objectives",
            }
        ]
    },
}
BOILERPLATE_FIVE_VIOLATIONS = {**BOILERPLATE_THREE_VIOLATIONS, "total_violations": 5}

# TestPlan.md with no boilerplate (valid)
TESTPLAN_NO_BOILERPLATE = f"""---
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

1. Verify vector store registration creates catalog entry (AC: #1 — "registration persists")
2. Verify proper error handling for invalid credentials (AC: #2 — "invalid credentials return 400")

{TEMPLATE_HEADINGS["2"]}

{TEMPLATE_HEADINGS["2.1"]}

- **E2E System Testing** — end-to-end workflows

{TEMPLATE_HEADINGS["2.3"]}

- **P0 (Critical)** — registration and deletion flows

{TEMPLATE_HEADINGS["8"]}

**Risk**: Dependency on external services - PostgreSQL vector database

**Mitigation**: Integration test suite with containerized PostgreSQL
"""

# Bytes that are not valid UTF-8 — Path.read_text(encoding="utf-8") raises UnicodeDecodeError.
NON_UTF8_PLAN_BYTES = b"\xff\xfe not utf-8"

# Kinds of unreadable test_plan_path for load_and_detect / load_and_validate wrappers.
UNREADABLE_TEST_PLAN_KINDS = ("directory", "non_utf8")

# Values that must not be accepted as list[str] config fields (string splits into chars;
# null / nested lists TypeError in merge/_dedupe). Loaders must raise ValueError instead.
INVALID_LIST_STR_FIELD_VALUES = ("a string", None, [["nested"]])
INVALID_LIST_STR_FIELD_IDS = ("string", "null", "nested-list")
SCOPE_LIST_FIELDS = ("allowed_test_levels", "forbidden_test_levels", "forbidden_patterns")
BOILERPLATE_PATTERN_CATEGORIES = ("objectives", "risks", "priorities")

# Structured evidence fixtures for validate_quality_evidence.py. Scope-bearing plan entries
# must explicitly identify the Section 1.3 objective they implement with `(Objective: #N)`.
# The objective, in turn, cites the STRAT requirement using the existing `(AC: #N — ...)` or
# `(NFR: category — ...)` syntax. This validates a concrete mapping chain without trying to
# infer semantic similarity from free-form prose.
QUALITY_EVIDENCE_STRATEGY = "h3. Acceptance Criteria\n\n# Given a user registers a store, then it persists\n"
QUALITY_EVIDENCE_OBJECTIVE = "1. Verify store registration (AC: #1 — registration persists)"
QUALITY_EVIDENCE_OBJECTIVES_SECTION = f"{TEMPLATE_HEADINGS['1.3']}\n\n{QUALITY_EVIDENCE_OBJECTIVE}"

UNMAPPED_SCOPE_CASES = (
    (
        "1.2",
        f"{TEMPLATE_HEADINGS['1.2']}\n\n- Register a store through the API",
        "Register a store through the API",
    ),
    (
        "2.3",
        f"{TEMPLATE_HEADINGS['2.3']}\n\n- **P0 (Critical)** — register a store",
        "**P0 (Critical)** — register a store",
    ),
    (
        "7.1",
        f"{TEMPLATE_HEADINGS['7.1']}\n\n- Verify mirrored images are available to the registration service",
        "Verify mirrored images are available to the registration service",
    ),
    (
        "7.2",
        f"{TEMPLATE_HEADINGS['7.2']}\n\n- Verify store registrations survive the operator upgrade",
        "Verify store registrations survive the operator upgrade",
    ),
    (
        "7.3",
        f"{TEMPLATE_HEADINGS['7.3']}\n\n- Verify concurrent store registrations remain within the latency target",
        "Verify concurrent store registrations remain within the latency target",
    ),
    (
        "7.4",
        f"{TEMPLATE_HEADINGS['7.4']}\n\n- Verify service-account authorization for store registration",
        "Verify service-account authorization for store registration",
    ),
    (
        "7.5",
        f"{TEMPLATE_HEADINGS['7.5']}\n\n- Verify registration requests require valid service credentials",
        "Verify registration requests require valid service credentials",
    ),
    (
        "8",
        f"{TEMPLATE_HEADINGS['8']}\n\n"
        "| Risk | Impact | Probability | Mitigation |\n"
        "|------|--------|-------------|------------|\n"
        "| Store registration is unavailable | High | Medium | Retry the API request |",
        "Store registration is unavailable",
    ),
)

FULLY_MAPPED_SCOPE_PLAN = f"""{TEMPLATE_HEADINGS["1.2"]}

- Register a store through the API (Objective: #1)

{QUALITY_EVIDENCE_OBJECTIVES_SECTION}

{TEMPLATE_HEADINGS["2.3"]}

- **P0 (Critical)** — register a store (Objective: #1)

{TEMPLATE_HEADINGS["7.4"]}

- Verify service-account authorization for store registration (Objective: #1)

{TEMPLATE_HEADINGS["8"]}

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Store registration is unavailable | High | Medium | Retry the API request (Objective: #1) |
"""

# NFR category with no concrete grounding — a bare "Not Applicable" statement must not need
# `(Objective: #N)`, since no Section 1.3 objective was ever created for it.
NOT_APPLICABLE_NFR_SECTIONS = ("7.1", "7.2", "7.3", "7.4", "7.5")
NOT_APPLICABLE_NFR_CASES = tuple(
    (
        section,
        f"{QUALITY_EVIDENCE_OBJECTIVES_SECTION}\n\n"
        f"{TEMPLATE_HEADINGS[section]}\n\n"
        "**Not Applicable** — this feature has no grounding for this category.\n",
    )
    for section in NOT_APPLICABLE_NFR_SECTIONS
)


def _compose_actionability_sections(*sections: str) -> str:
    """Join complete Section 3 fixtures while keeping one consistent Markdown layout."""
    return "\n\n".join(section.strip() for section in sections) + "\n"


def _actionability_section(section: str, body: str) -> str:
    return f"{TEMPLATE_HEADINGS[section]}\n\n{body.strip()}\n"


def _build_actionability_plan(infrastructure: str, test_data: str, users: str) -> str:
    """Build a plan from subsection bodies without repeating Section 3 headings in every fixture."""
    return _compose_actionability_sections(
        _actionability_section("3.1", infrastructure),
        _actionability_section("3.2", test_data),
        _actionability_section("3.3", users),
    )


_ACTIONABILITY_CONCRETE_INFRASTRUCTURE = """OpenShift version: 4.18
RHOAI version: 2.25"""

_ACTIONABILITY_CONCRETE_DATA = """| Format | Example |
|--------|---------|
| JSON object with a unique name | {"name": "orders"} |"""

_ACTIONABILITY_CONCRETE_DATA_WITH_BARE_TBD = f"""{_ACTIONABILITY_CONCRETE_DATA}
- Invalid HF token value: TBD"""

_ACTIONABILITY_CONCRETE_DATA_WITH_RESOLVED_TBD = f"""{_ACTIONABILITY_CONCRETE_DATA}
- Invalid HF token value: TBD — Resolution: obtain a concrete invalid token fixture before test execution."""

_ACTIONABILITY_CONCRETE_RBAC = """| Role | Resource | Permissions |
|------|----------|-------------|
| QE administrator | vector-store resources | create, get, delete |"""

ACTIONABILITY_CONCRETE_RBAC_SECTION = _actionability_section("3.3", _ACTIONABILITY_CONCRETE_RBAC)
ACTIONABILITY_CONCRETE_DATA_AND_RBAC = _compose_actionability_sections(
    _actionability_section("3.2", _ACTIONABILITY_CONCRETE_DATA),
    ACTIONABILITY_CONCRETE_RBAC_SECTION,
)

ACTIONABILITY_CONCRETE_DATA_WITH_BARE_TBD_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA_WITH_BARE_TBD,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_CONCRETE_DATA_WITH_RESOLVED_TBD_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA_WITH_RESOLVED_TBD,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_TBD_UNKNOWN_PLAN = _build_actionability_plan(
    """OpenShift version: TBD — unknown
RHOAI version: 2.25""",
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_TBD_DATA_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    "Payload format: TBD; Example: TBD",
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_PROSE_RBAC_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    "The test user role has permissions and can access the environment.",
)

ACTIONABILITY_GENERIC_PROSE_RBAC_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    "The test user can create, get, and delete all resources.",
)

ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    "The qe-test-user can create, get, and delete vector-store resources.",
)

ACTIONABILITY_FORMATTED_RBAC_TABLE_PLANS = tuple(
    _build_actionability_plan(
        _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
        _ACTIONABILITY_CONCRETE_DATA,
        _ACTIONABILITY_CONCRETE_RBAC.replace("vector-store resources", resource),
    )
    for resource in ("**vector-store resources**", "`vector-store resources`")
)

ACTIONABILITY_RBAC_WITHOUT_RESOURCE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    'Registration payload: JSON object; Example: {"name": "orders"}',
    """| Role | Permissions |
|------|-------------|
| QE administrator | create, get, delete |""",
)

ACTIONABILITY_BROAD_RBAC_TABLE_PLANS = tuple(
    _build_actionability_plan(
        _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
        _ACTIONABILITY_CONCRETE_DATA,
        _ACTIONABILITY_CONCRETE_RBAC.replace("vector-store resources", resource),
    )
    for resource in (
        "all namespaces",
        "all projects",
        "any resources",
        "all vector-store resources",
        "every service account",
        "vector-store* resources",
        "**vector-store resources/* scope**",
        "`vector-store resources/*`",
    )
)

ACTIONABILITY_DELIMITED_DATA_PLACEHOLDER_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    "Registration payload: JSON object; Example: {placeholder}",
    _ACTIONABILITY_CONCRETE_RBAC,
)

# Keep an independent Section 3.1 detail so resolution-path tests cannot pass solely because a
# version field happens to make the section look substantive.
ACTIONABILITY_JUSTIFIED_TBD_RESOLUTION = (
    "retrieve the supported-platform matrix from platform engineering before setup."
)

ACTIONABILITY_JUSTIFIED_TBD_PLAN = _build_actionability_plan(
    f"""OpenShift version: TBD — Resolution: {ACTIONABILITY_JUSTIFIED_TBD_RESOLUTION}
RHOAI version: 2.25
KServe deployment uses GPU nodes in the test namespace.""",
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_RESOLUTION_TARGET_BOUNDARY_CASES = (
    ("confirm with someone", False),
    ("confirm the version with the test team", False),
    ("confirm the version with the team", False),
    ("confirm the version with the feature owner", False),
    ("confirm the version with engineering", False),
    ("confirm the version with the engineering team", False),
    ("confirm the version with the test engineering team", False),
    ("confirm the supported version with\n  Owner: test team", False),
    ("retrieve the supported-platform matrix from platform engineering before setup.", True),
    ("confirm the supported version before environment setup.", True),
    ("confirm the supported version by the end of environment setup.", True),
    ("obtain the supported version from RHAISTRAT-1234.", True),
)

_ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_USERS = """- Cluster admin with permissions to manage catalog sources and
  HF tokens — exact ClusterRole/Role name: `TBD — Resolution: confirm
  required RBAC role (cluster-admin vs. dedicated catalog-admin) with
  Platform team per strategy open question (Owner: Platform team)`
- QE test users can get and create vector-store resources in serving namespaces."""

ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_USERS,
)

ACTIONABILITY_WRAPPED_GENERIC_RBAC_RESOLUTION_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_USERS.replace(
        "Platform team per strategy open question (Owner: Platform team)",
        "Owner: test team",
    ),
)

# This is a concise synthetic regression for wrapped Markdown labels and values. It is not a copy
# of the external RHAISTRAT-1258 artifact; real-data verification remains an explicit manual step.
_ACTIONABILITY_ARTIFACT_LIKE_INFRASTRUCTURE = """- OpenShift cluster — version: `TBD — Resolution: confirm minimum
  supported OpenShift version with Platform team before test environment
  provisioning`
- RHOAI 3.6 EA2 — exact build: `TBD — Resolution: obtain pinned build
  number from release engineering before test execution begins`
- KServe with storage handler supporting `hf://` protocol"""

_ACTIONABILITY_ARTIFACT_LIKE_DATA = """- Valid Hugging Face API tokens with `read` scope
  (format: `hf_*` string; must be verified against the HF Hub API)
- Private Hugging Face model identifiers for discovery
  (e.g., `hf://org/private-model-name`)"""

_ACTIONABILITY_ARTIFACT_LIKE_RBAC = "- QE test users can get and create vector-store resources in serving namespaces."

ACTIONABILITY_ARTIFACT_LIKE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_ARTIFACT_LIKE_INFRASTRUCTURE,
    _ACTIONABILITY_ARTIFACT_LIKE_DATA,
    _ACTIONABILITY_ARTIFACT_LIKE_RBAC,
)

# Supply explicit RBAC evidence so the version/test-data parser regression is isolated from the
# separate plural-user prose matcher.
ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN = _build_actionability_plan(
    _ACTIONABILITY_ARTIFACT_LIKE_INFRASTRUCTURE,
    _ACTIONABILITY_ARTIFACT_LIKE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

_ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_RESOLVED_VALUE = (
    "TBD — Resolution: confirm minimum\n"
    "  supported OpenShift version with Platform team before test environment\n"
    "  provisioning"
)
_ACTIONABILITY_ARTIFACT_LIKE_RHOAI_RESOLVED_VALUE = (
    "TBD — Resolution: obtain pinned build\n  number from release engineering before test execution begins"
)

ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_BARE_TBD_PLAN = ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN.replace(
    _ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_RESOLVED_VALUE,
    "TBD",
)

ACTIONABILITY_ARTIFACT_LIKE_RHOAI_BARE_TBD_PLAN = ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN.replace(
    _ACTIONABILITY_ARTIFACT_LIKE_RHOAI_RESOLVED_VALUE,
    "TBD",
)

ACTIONABILITY_ARTIFACT_LIKE_RHOAI_EXACT_BUILD_RESOLVED_TBD_PLAN = ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN.replace(
    _ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_RESOLVED_VALUE,
    "4.18",
)

ACTIONABILITY_CONCRETE_VERSION_LABELS_PLAN = _build_actionability_plan(
    """- **OpenShift cluster — version:**
  `4.18`
- **RHOAI 3.6 EA2 — exact build:**
  `3.6.0-ea2`""",
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_ADVISORY_GAPS_PLAN = _build_actionability_plan(
    """- OpenShift cluster — version: `latest`
- RHOAI 3.6 EA2 — exact build: `current`""",
    "- Test data requirements will be confirmed during test setup.",
    "- qe-test-user can create, get, and delete vector-store resources.",
)

ACTIONABILITY_MISSING_VERSION_DATA_PLAN = _build_actionability_plan(
    "- Environment: shared OpenShift cluster with RHOAI installed; the test namespace is provisioned before execution.",
    "- Test data will be supplied by the test environment.",
    "- qe-test-user can create, get, and delete vector-store resources.",
)

ACTIONABILITY_NON_SUBSTANTIVE_INFRASTRUCTURE_PLAN = _build_actionability_plan(
    "Environment details unavailable",
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_ADVISORY_RESULT = {
    "valid": True,
    "bare_tbd": [],
    "missing_details": [],
    "advisory_gaps": ["OpenShift version", "RHOAI version", "test data formats and examples"],
}

ACTIONABILITY_ADVISORY_AND_BLOCKING_RESULT = {
    "valid": False,
    "bare_tbd": [],
    "missing_details": ["RBAC roles and permissions"],
    "advisory_gaps": ["OpenShift version", "RHOAI version", "test data formats and examples"],
}

ACTIONABILITY_GENERIC_TBD_CONFIGURATION_PLAN = _build_actionability_plan(
    """- OpenShift version: 4.18
- GPU configuration: TBD
- RHOAI version: 2.25""",
    _ACTIONABILITY_CONCRETE_DATA,
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_RBAC_TBD_PROSE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    _ACTIONABILITY_CONCRETE_DATA,
    "The catalog-admin role is TBD. The qe-test-user can create, get, and delete vector-store resources.",
)

ACTIONABILITY_RBAC_UNRESOLVED_TBD_PROSE_PLAN = ACTIONABILITY_RBAC_TBD_PROSE_PLAN.replace(
    "role is TBD.", "role is TBD — unknown."
)

ACTIONABILITY_RESOLVED_TBD_DATA_AND_RBAC_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    """Registration payload format: JSON object; Example: TBD — Resolution: obtain a concrete registration payload from
API specification before test setup.""",
    """The catalog-admin role is TBD — Resolution: confirm the required RBAC role with Platform team before environment
setup. The qe-test-user can create, get, and delete vector-store resources.""",
)

ACTIONABILITY_RESOLVED_TBD_VISIBILITY_PLAN = _build_actionability_plan(
    """OpenShift version: TBD — Resolution: retrieve the supported-platform matrix from Platform team before setup.
RHOAI version: TBD — Resolution: obtain the pinned RHOAI build from Release Engineering before test setup.""",
    """Registration payload format: JSON object; Example: TBD — Resolution: obtain a concrete registration payload from
API specification before test setup.""",
    """The catalog-admin role is TBD — Resolution: confirm the required RBAC role with Platform team before environment
setup. The qe-test-user can create, get, and delete vector-store resources.""",
)

ACTIONABILITY_BARE_TBD_VISIBILITY_PLAN = ACTIONABILITY_RESOLVED_TBD_VISIBILITY_PLAN.replace(
    "OpenShift version: TBD — Resolution: retrieve the supported-platform matrix from Platform team before setup.",
    "OpenShift version: TBD",
)

ACTIONABILITY_UNRESOLVED_TBD_VISIBILITY_PLAN = ACTIONABILITY_RESOLVED_TBD_VISIBILITY_PLAN.replace(
    "RHOAI version: TBD — Resolution: obtain the pinned RHOAI build from Release Engineering before test setup.",
    "RHOAI version: TBD — unknown",
)

ACTIONABILITY_RESOLVED_TBD_VISIBILITY_LABELS = (
    "OpenShift version",
    "RHOAI version",
    "test data formats and examples",
    "RBAC roles and permissions",
)

ACTIONABILITY_EG_CONCRETE_VALUE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    "Token format: string identifier; e.g., model-123",
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_FOR_EXAMPLE_CONCRETE_VALUE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    'Payload format: JSON object; for example {"name": "orders"}',
    _ACTIONABILITY_CONCRETE_RBAC,
)

ACTIONABILITY_ARBITRARY_BACKTICK_TOKEN_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    "A token is stored in `opaque-token-value` for transport during the test.",
    _ACTIONABILITY_CONCRETE_RBAC,
)

_ACTIONABILITY_GENERIC_EXAMPLE_PHRASES = (
    "Example: a valid token",
    "for example a model identifier",
    "Example: an API payload",
    "for example a JSON object",
    "Example: a YAML manifest",
)
ACTIONABILITY_GENERIC_EXAMPLE_PLANS = tuple(
    _build_actionability_plan(
        _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
        f"Token format: string; {example_phrase}",
        _ACTIONABILITY_CONCRETE_RBAC,
    )
    for example_phrase in _ACTIONABILITY_GENERIC_EXAMPLE_PHRASES
)

ACTIONABILITY_YAML_EXAMPLE_VALUE_PLAN = _build_actionability_plan(
    _ACTIONABILITY_CONCRETE_INFRASTRUCTURE,
    "Manifest format: YAML; Example: kind: InferenceService",
    _ACTIONABILITY_CONCRETE_RBAC,
)

LOGICAL_MARKDOWN_ENTRY_CASES = (
    (
        "- Environment source: TBD — Resolution: retrieve the supported-platform matrix\n"
        "  from Platform team before environment setup\n"
        "- GPU configuration: TBD",
        [
            "- Environment source: TBD — Resolution: retrieve the supported-platform matrix from Platform team "
            "before environment setup",
            "- GPU configuration: TBD",
        ],
    ),
    (
        "A paragraph starts here\n"
        "and continues on the next line\n\n"
        "1. A numbered entry starts here\n"
        "   and also continues",
        [
            "A paragraph starts here and continues on the next line",
            "1. A numbered entry starts here and also continues",
        ],
    ),
)

OCCURRENCE_LEVEL_TBD_CASES = (
    (
        "- Environment source: TBD — Resolution: retrieve the supported-platform matrix\n"
        "  from Platform team before environment setup\n"
        "- GPU configuration: TBD",
        ["GPU configuration"],
    ),
    (
        "GPU configuration: TBD. Node selector: TBD — Resolution: confirm the node selector before environment setup.",
        ["GPU configuration"],
    ),
    (
        "GPU configuration: TBD. Node selector: TBD",
        ["GPU configuration", "Node selector"],
    ),
)

# TestPlanReview.md bodies in the two documented score layouts, all criteria 2/2 (10/10, Ready).
REVIEW_RUBRIC_SCORES_LAYOUT = """# Test Plan Review — AI Grid Provider Admin Tenant Onboarding

## Rubric Scores

| Criterion | Score | Notes |
|-----------|-------|-------|
| Specificity | 2/2 | Tenant onboarding steps are feature-specific. |
| Grounding | 2/2 | All Section 4 interfaces trace to the strategy. |
| Scope Fidelity | 2/2 | Every objective cites an AC or NFR. |
| Actionability | 2/2 | Environment, test data, and RBAC are concrete. |
| Consistency | 2/2 | Scope, objectives, and coverage tables align. |

**Total: 10/10 — Verdict: Ready**

## Grounding Cross-Reference

| Section 4 Entry | Source Match | Status |
|-----------------|-------------|--------|
| Tenant onboarding API | "Provider admins onboard tenants" | Grounded |

## Revision History

Initial assessment
"""

# Mirrors the RHAISTRAT-2930 review: `## Score Table` with a Total row and no
# `## Section-by-Section Feedback` heading.
REVIEW_SCORE_TABLE_LAYOUT = """# Test Plan Review — AI Grid Provider Admin Tenant Onboarding

## Score Table

| Criterion | Score | Evidence | Notes |
|-----------|-------|----------|-------|
| Specificity | 2/2 | Tenant quota and onboarding flows named. | Passes the swap test. |
| Grounding | 2/2 | Interfaces trace to strategy sentences. | No fabrications. |
| Scope Fidelity | 2/2 | All objectives carry AC/NFR citations. | No orphans. |
| Actionability | 2/2 | Versions pinned, RBAC table present. | No blocking TBDs. |
| Consistency | 2/2 | All seven cross-checks pass. | No mismatches. |
| **Total** | **10/10** | | |

**Total: 10/10 — Verdict: Ready**

## Revision History

Initial assessment
"""
