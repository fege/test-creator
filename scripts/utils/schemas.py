"""
Schema definitions and validation for test plan artifacts.

Defines schemas for:
- test-plan (TestPlan.md)
- test-case (TC-*.md)
- test-gaps (TestPlanGaps.md)
- test-plan-review (TestPlanReview.md)

Provides validation and default value application.
"""

import datetime
import os
import re
import sys
from pathlib import Path

from scripts.utils.markdown_utils import extract_headings

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required but not installed.\nInstall it with: uv sync",
        file=sys.stderr,
    )
    sys.exit(1)


# ─── Schema Definitions ────────────────────────────────────────────────────────

# Each schema is a dict of field_name -> field_spec.
# field_spec keys:
#   type:     "string" | "int" | "bool" | "list" | "dict"
#   required: bool (default False)
#   enum:     list of allowed values (optional)
#   pattern:  regex pattern the value must match (optional, strings only)
#   default:  default value when not provided (optional)
#   fields:   sub-field specs (required for type "dict")

SCHEMAS = {
    "test-plan": {
        "feature": {
            "type": "string",
            "required": True,
        },
        "source_key": {
            "type": "string",
            "required": True,
            "pattern": r"^(RHAISTRAT|RHOAIENG|RHAIRFE)-\d+$",
        },
        "source_type": {
            "type": "string",
            "required": False,
            "enum": ["strat", "issue"],
            "default": None,
        },
        "version": {
            "type": "string",
            "required": True,
            "pattern": r"^\d+\.\d+\.\d+$",
            "default": "0.0.0",
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Draft", "In Review", "Approved"],
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
        "author": {
            "type": "string",
            "required": True,
        },
        "components": {
            "type": "list",
            "required": False,
            "default": [],
        },
        "additional_docs": {
            "type": "list",
            "required": False,
            "default": [],
        },
        "reviewers": {
            "type": "list",
            "required": False,
            "default": [],
        },
    },
    "test-case": {
        "test_case_id": {
            "type": "string",
            "required": True,
            "pattern": r"^TC-[A-Z0-9]+-\d+$",
        },
        "source_key": {
            "type": "string",
            "required": True,
            "pattern": r"^(RHAISTRAT|RHOAIENG|RHAIRFE)-\d+$",
        },
        "objectives": {
            "type": "list",
            "required": True,
            "min_length": 1,
        },
        "priority": {
            "type": "string",
            "required": True,
            "enum": ["P0", "P1", "P2"],
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Draft", "Ready", "Automated", "Blocked"],
        },
        "automation_status": {
            "type": "string",
            "required": False,
            "enum": ["Not Started", "In Progress", "Complete", "N/A"],
            "default": "Not Started",
        },
        "automation_file": {
            "type": "string",
            "required": False,
            "default": None,
        },
        "automation_function": {
            "type": "string",
            "required": False,
            "default": None,
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
        "upgrade_phase": {
            "type": "string",
            "required": False,
            "enum": ["pre", "post", "both"],
            "default": None,
        },
    },
    "test-gaps": {
        "feature": {
            "type": "string",
            "required": True,
        },
        "source_key": {
            "type": "string",
            "required": True,
            "pattern": r"^(RHAISTRAT|RHOAIENG|RHAIRFE)-\d+$",
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Open", "Resolved"],
        },
        "gap_count": {
            "type": "int",
            "required": True,
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
    },
    "test-plan-review": {
        "feature": {
            "type": "string",
            "required": True,
        },
        "source_key": {
            "type": "string",
            "required": True,
            "pattern": r"^(RHAISTRAT|RHOAIENG|RHAIRFE)-\d+$",
        },
        "score": {
            "type": "int",
            "required": True,
            "min": 0,
            "max": 10,
        },
        "pass": {
            "type": "bool",
            "required": True,
        },
        "verdict": {
            "type": "string",
            "required": True,
            "enum": ["Ready", "Revise", "Rework"],
        },
        "scores": {
            "type": "dict",
            "required": True,
            "fields": {
                "specificity": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "grounding": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "scope_fidelity": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "actionability": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "consistency": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
            },
        },
        "auto_revised": {
            "type": "bool",
            "required": True,
            "default": False,
        },
        "before_score": {
            "type": "int",
            "required": False,
            "default": None,
            "min": 0,
            "max": 10,
        },
        "before_scores": {
            "type": "dict",
            "required": False,
            "default": None,
            "fields": {
                "specificity": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "grounding": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "scope_fidelity": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "actionability": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
                "consistency": {
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 2,
                },
            },
        },
        "error": {
            "type": "string",
            "required": False,
            "default": None,
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
    },
}


# ─── Review Scoring ─────────────────────────────────────────────────────────────

REVIEW_CRITERIA = ("specificity", "grounding", "scope_fidelity", "actionability", "consistency")
"""The five review-rubric criteria, in canonical order.

Must stay in sync with ``scores`` sub-fields in ``SCHEMAS["test-plan-review"]`` above.
"""

CRITERION_LABELS = {
    "specificity": "Specificity",
    "grounding": "Grounding",
    "scope_fidelity": "Scope Fidelity",
    "actionability": "Actionability",
    "consistency": "Consistency",
}
"""Human-readable criterion names as they appear in the first column of the review score table.

Must have exactly the same keys as ``REVIEW_CRITERIA`` — adding, removing, or renaming a criterion
requires updating both (and the ``scores`` sub-fields in ``SCHEMAS["test-plan-review"]``).
"""


def compute_verdict_and_pass(scores: dict) -> tuple[str, int, bool]:
    """Single Python authority for the review verdict/pass formula.

    Implements the rubric rules documented in
    ``skills/test-plan-review/prompts/review-agent.md`` (Step 4 — Determine
    Verdict, Step 5 — ``pass`` definition).  Any future rubric change MUST
    update this function AND ALSO synchronize:
    ``skills/test-plan-review/prompts/review-agent.md``,
    ``skills/test-plan-score/SKILL.md``, and
    ``docs/human-review-guide.md`` — each independently restates the verdict
    table and must stay in sync.

    Args:
        scores: dict mapping each criterion name to its int score (0-2).
        The verdict is computed from the total and the no_zero flag, with an
        additional gate on actionability==2 for the Ready verdict:
        - Ready: total >= 8 AND no criterion scored 0 AND actionability == 2
        - Revise: total >= 7 AND no criterion scored 0 (but not Ready)
        - Rework: total < 7 OR any criterion scored 0

    Returns:
        (verdict, total_score, passed) where *verdict* is one of
        ``"Ready"``/``"Revise"``/``"Rework"``, *total_score* is the sum of
        all criterion scores, and *passed* is the rubric-pass boolean
        (unchanged — actionability does not gate pass).
    """
    total = sum(scores[k] for k in REVIEW_CRITERIA)
    no_zero = all(scores[k] > 0 for k in REVIEW_CRITERIA)
    actionability_ok = scores["actionability"] == 2
    if total >= 8 and no_zero and actionability_ok:
        verdict = "Ready"
    elif total >= 7 and no_zero:
        verdict = "Revise"
    else:
        verdict = "Rework"
    passed = total >= 7 and no_zero
    return verdict, total, passed


# ─── Test Plan Structure Schema ───────────────────────────────────────────────────

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "skills" / "test-plan-create" / "test-plan-template.md"

_VALIDATED_SECTION_NUMBERS = {
    "1",
    "1.1",
    "1.2",
    "1.3",
    "2",
    "2.1",
    "2.2",
    "2.3",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
}

_OPTIONAL_SECTION_NUMBERS = {"5", "6"}

_TEST_CASE_SUBSECTION_NUMBERS = {"3.1", "3.4", "5.2", "6.2", "9.1", "9.2"}

_SECTION_NUMBER_RE = re.compile(r"^(#{2,3})\s+(\d+(?:\.\d+)?)[.\s]")


def _parse_template_headings():
    try:
        content = _TEMPLATE_PATH.read_text()
    except OSError as e:
        raise ValueError(f"Test plan template not found at {_TEMPLATE_PATH}; scripts require the repo layout.") from e
    headings = {}
    for h in extract_headings(content):
        m = _SECTION_NUMBER_RE.match(h)
        if m:
            headings[m.group(2)] = h
    return headings


def _require_headings(headings):
    """Fail closed if the parsed template omits any heading the code depends on."""
    missing = sorted(
        (_VALIDATED_SECTION_NUMBERS | _TEST_CASE_SUBSECTION_NUMBERS) - headings.keys(),
        key=lambda x: [int(p) for p in x.split(".")],
    )
    if missing:
        raise ValueError(f"Test plan template {_TEMPLATE_PATH} is missing required section headings: {missing}")


TEMPLATE_HEADINGS = _parse_template_headings()
_require_headings(TEMPLATE_HEADINGS)


TESTPLAN_STRUCTURE = {
    "sections": [
        {"heading": TEMPLATE_HEADINGS[num], "required": num not in _OPTIONAL_SECTION_NUMBERS}
        for num in sorted(_VALIDATED_SECTION_NUMBERS, key=lambda x: [int(p) for p in x.split(".")])
    ],
    "disallowed_test_levels": [
        "Unit Testing",
        "Integration Testing",
        "Component Testing",
        "Data Validation Testing",
        "Functional Testing",
        "API Integration Testing",
    ],
    "allowed_tc_categories": ["E2E", "UI", "NEG", "NFR", "UPG"],
    "dev_tooling_indicators": [
        "pip install",
        "pip",
        "podman",
        "docker-compose",
        "Ollama",
        "ollama",
        "localhost",
        "local LLM",
        "docker run",
        "npm install",
        "yarn install",
    ],
    "infra_sections": [TEMPLATE_HEADINGS["3.1"], TEMPLATE_HEADINGS["3.4"]],
}


# ─── Auto-detection ─────────────────────────────────────────────────────────────


def detect_schema_type(path):
    """Detect schema type from file path."""
    basename = os.path.basename(path)
    if basename == "TestPlanGaps.md":
        return "test-gaps"
    if basename == "TestPlanReview.md":
        return "test-plan-review"
    if basename.startswith("TC-"):
        return "test-case"
    if basename == "TestPlan.md":
        return "test-plan"
    return None


# ─── Validation ─────────────────────────────────────────────────────────────────


class ValidationError(Exception):
    """Raised when frontmatter fails schema validation."""


def _validate_field(name, value, spec):
    """Validate a single field against its spec. Returns list of errors."""
    errors = []

    if value is None:
        if spec.get("required", False) and "default" not in spec:
            errors.append(f"Missing required field: {name}")
        return errors

    expected_type = spec.get("type", "string")

    if expected_type == "string":
        # Convert date/datetime objects to ISO format strings (YAML auto-parsing compatibility)
        if isinstance(value, (datetime.date, datetime.datetime)):
            value = value.isoformat().split("T")[0]  # Get YYYY-MM-DD

        if not isinstance(value, str):
            errors.append(f"{name}: expected string, got {type(value).__name__}")
            return errors
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{name}: '{value}' not in {spec['enum']}")
        if "pattern" in spec and not re.match(spec["pattern"], value):
            errors.append(f"{name}: '{value}' does not match {spec['pattern']}")

    elif expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{name}: expected int, got {type(value).__name__}")
        else:
            if "min" in spec and value < spec["min"]:
                errors.append(f"{name}: {value} is less than minimum {spec['min']}")
            if "max" in spec and value > spec["max"]:
                errors.append(f"{name}: {value} is greater than maximum {spec['max']}")

    elif expected_type == "bool":
        if not isinstance(value, bool):
            errors.append(f"{name}: expected bool, got {type(value).__name__}")

    elif expected_type == "list":
        if not isinstance(value, list):
            errors.append(f"{name}: expected list, got {type(value).__name__}")
        elif "min_length" in spec and len(value) < spec["min_length"]:
            errors.append(f"{name}: expected at least {spec['min_length']} item(s), got {len(value)}")

    elif expected_type == "dict":
        if not isinstance(value, dict):
            errors.append(f"{name}: expected dict, got {type(value).__name__}")
        elif "fields" in spec:
            for sub_name, sub_spec in spec["fields"].items():
                errors.extend(_validate_field(f"{name}.{sub_name}", value.get(sub_name), sub_spec))
            for sub_key in value:
                if sub_key not in spec["fields"]:
                    errors.append(f"{name}: unknown sub-field '{sub_key}'")

    return errors


def validate(data, schema_type):
    """Validate frontmatter data against a schema.

    Args:
        data: dict of frontmatter fields
        schema_type: one of the keys in SCHEMAS

    Returns:
        list of error strings (empty if valid)

    Raises:
        ValueError: if schema_type is unknown
    """
    if schema_type not in SCHEMAS:
        raise ValueError(f"Unknown schema type: {schema_type}. Valid types: {list(SCHEMAS.keys())}")

    schema = SCHEMAS[schema_type]
    errors = []

    for key in data:
        if key not in schema:
            errors.append(f"Unknown field: {key}")

    for field_name, field_spec in schema.items():
        errors.extend(_validate_field(field_name, data.get(field_name), field_spec))

    if schema_type == "test-plan-review":
        scores = data.get("scores")
        score = data.get("score")
        if isinstance(scores, dict) and isinstance(score, int):
            if all(isinstance(scores.get(k), int) for k in REVIEW_CRITERIA):
                expected_verdict, expected_total, expected_pass = compute_verdict_and_pass(scores)
                if score != expected_total:
                    errors.append(f"score: expected {expected_total} from scores.*, got {score}")
                if data.get("verdict") != expected_verdict:
                    errors.append(f"verdict: expected {expected_verdict!r} from scores.*, got {data.get('verdict')!r}")
                if data.get("pass") != expected_pass:
                    errors.append(f"pass: expected {expected_pass} from scores.*, got {data.get('pass')}")

        before_scores = data.get("before_scores")
        before_score = data.get("before_score")
        if (before_score is None) != (before_scores is None):
            errors.append("before_score and before_scores must both be set or both be null")
        if isinstance(before_scores, dict) and isinstance(before_score, int):
            if all(isinstance(before_scores.get(k), int) for k in REVIEW_CRITERIA):
                expected_before = sum(before_scores[k] for k in REVIEW_CRITERIA)
                if before_score != expected_before:
                    errors.append(f"before_score: expected {expected_before} from before_scores.*, got {before_score}")

    return errors


def apply_defaults(data, schema_type):
    """Apply default values for missing optional fields.

    Modifies data in-place and returns it.

    Raises:
        ValueError: if schema_type is unknown
    """
    if schema_type not in SCHEMAS:
        raise ValueError(f"Unknown schema type: {schema_type}. Valid types: {list(SCHEMAS.keys())}")

    schema = SCHEMAS[schema_type]
    for field_name, field_spec in schema.items():
        if field_name not in data and "default" in field_spec:
            data[field_name] = field_spec["default"]
    return data


def get_schema_yaml(schema_type):
    """Return the schema definition as a YAML string for display."""
    if schema_type not in SCHEMAS:
        raise ValueError(f"Unknown schema type: {schema_type}. Valid types: {list(SCHEMAS.keys())}")

    schema = SCHEMAS[schema_type]
    output = {"required": {}, "optional": {}}

    for name, spec in schema.items():
        entry = {"type": spec["type"]}
        if "enum" in spec:
            entry["enum"] = spec["enum"]
        if "pattern" in spec:
            entry["pattern"] = spec["pattern"]
        if "default" in spec:
            entry["default"] = spec["default"]
        if "min" in spec:
            entry["min"] = spec["min"]
        if "max" in spec:
            entry["max"] = spec["max"]
        if "fields" in spec:
            entry["fields"] = {
                k: {
                    "type": v["type"],
                    **({"min": v["min"]} if "min" in v else {}),
                    **({"max": v["max"]} if "max" in v else {}),
                }
                for k, v in spec["fields"].items()
            }

        if spec.get("required", False):
            output["required"][name] = entry
        else:
            output["optional"][name] = entry

    return yaml.dump(output, default_flow_style=False, sort_keys=False)
