#!/usr/bin/env python3
"""Unified validation CLI for test plan artifacts.

Replaces validate_feature_dir.py, validate_gap_counts.py, and
validate_test_cases.py with a single entry point. The ``all``
subcommand orchestrates all checks so skills need only one call.

Usage:
    uv run python scripts/validate.py feature-dir <feature_dir>
    uv run python scripts/validate.py gap-counts <feature_dir> <resolved> <unresolved> <new>
    uv run python scripts/validate.py test-cases <feature_dir>
    uv run python scripts/validate.py all <feature_dir>
    uv run python scripts/validate.py ac-citations <testplan_path> [--ac-count N] [--nfr-category CATEGORY ...]
    uv run python scripts/validate.py ac-coverage <testplan_path> --ac-count N
    uv run python scripts/validate.py structure <testplan_path>
    uv run python scripts/validate.py category-prefixes <testplan_path>
    uv run python scripts/validate.py feature-name <feature_name>
    uv run python scripts/validate.py readme <feature_dir> --strat-url URL
    uv run python scripts/validate.py interface-types <testplan_path>
    uv run python scripts/validate.py interface-coverage <testplan_path>
    uv run python scripts/validate.py infra-scope <testplan_path>
    uv run python scripts/validate.py tc-counts <feature_dir>
    uv run python scripts/validate.py tc-scope <feature_dir>
    uv run python scripts/validate.py tc-traceability <feature_dir>
    uv run python scripts/validate.py check-interactive
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

from scripts.utils.frontmatter_utils import read_frontmatter, read_frontmatter_validated
from scripts.utils.markdown_utils import (
    extract_section,
    has_citation,
    is_filled_cell,
    normalize_interface,
    parse_citations,
    parse_numbered_objectives,
    parse_table_rows,
)
from scripts.utils.schemas import TEMPLATE_HEADINGS, TESTPLAN_STRUCTURE, detect_schema_type
from scripts.validate_test_scope import load_and_validate as validate_test_scope


def validate_feature_dir(feature_dir: str) -> str:
    """Validate feature directory structure and read metadata.

    Returns JSON string with validation results.
    """
    feature_path = Path(feature_dir)

    testplan_path = feature_path / "TestPlan.md"
    if not testplan_path.exists():
        return json.dumps(
            {
                "valid": False,
                "error": f"TestPlan.md not found at {testplan_path}",
            },
            indent=2,
        )

    tc_dir = feature_path / "test_cases"
    if not tc_dir.exists() or not tc_dir.is_dir():
        return json.dumps(
            {
                "valid": False,
                "error": f"test_cases directory not found at {tc_dir}",
            },
            indent=2,
        )

    index_path = tc_dir / "INDEX.md"
    if not index_path.exists():
        return json.dumps(
            {
                "valid": False,
                "error": f"INDEX.md not found at {index_path}",
            },
            indent=2,
        )

    tc_files = list(tc_dir.glob("TC-*.md"))
    if not tc_files:
        return json.dumps(
            {
                "valid": False,
                "error": f"No TC-*.md files found in {tc_dir}",
            },
            indent=2,
        )

    try:
        testplan_frontmatter, _ = read_frontmatter(str(testplan_path))
    except (OSError, yaml.YAMLError, ValueError) as e:
        return json.dumps(
            {
                "valid": False,
                "error": f"Failed to read TestPlan.md frontmatter: {e}",
            },
            indent=2,
        )
    if "components" not in testplan_frontmatter:
        testplan_frontmatter["components"] = []

    return json.dumps(
        {
            "valid": True,
            "feature_dir": str(feature_path),
            "testplan_frontmatter": testplan_frontmatter,
            "tc_count": len(tc_files),
        },
        indent=2,
    )


def validate_gap_counts(feature_dir: str, resolved: int, unresolved: int, new: int) -> dict:
    """Validate gap count arithmetic: unresolved == original - resolved + new.

    Returns dict with validation results.
    """
    gaps_file = Path(feature_dir) / "TestPlanGaps.md"
    if not gaps_file.exists():
        return {"valid": False, "error": f"{gaps_file} not found"}

    try:
        frontmatter, _ = read_frontmatter_validated(str(gaps_file), "test-gaps")
        original = frontmatter.get("gap_count", 0)
    except Exception as e:
        return {"valid": False, "error": f"Failed to read gap count: {e}"}

    expected = original - resolved + new

    result = {
        "original": original,
        "resolved": resolved,
        "unresolved": unresolved,
        "new": new,
        "expected": expected,
    }

    if unresolved == expected:
        return {"valid": True, **result}
    else:
        return {"valid": False, **result}


def validate_test_cases(feature_dir: str, schema_type: str = "test-case") -> dict:
    """Validate all TC-*.md files in feature_dir/test_cases/.

    Returns dict with validation results.
    """
    test_cases_dir = Path(feature_dir) / "test_cases"
    if not test_cases_dir.exists():
        return {"valid": True, "checked": 0, "failed": 0, "errors": []}

    tc_files = list(test_cases_dir.glob("TC-*.md"))
    if not tc_files:
        return {"valid": True, "checked": 0, "failed": 0, "errors": []}

    if not (test_cases_dir / "INDEX.md").exists():
        return {
            "valid": False,
            "checked": 0,
            "failed": 0,
            "errors": [{"file": "INDEX.md", "error": "INDEX.md not found in test_cases/"}],
        }

    errors = []
    for f in tc_files:
        try:
            read_frontmatter_validated(str(f), schema_type)
        except Exception as e:
            errors.append({"file": str(f), "error": str(e)})

    return {
        "valid": not errors,
        "checked": len(tc_files),
        "failed": len(errors),
        "errors": errors,
    }


def _citation_reason(citation: dict, ac_count: int, nfr_categories: list) -> str | None:
    """Return an invalid-citation reason, or None when the citation is in bounds.

    Presence-only mode (``ac_count is None``) never flags anything — any recognized ``(AC:...)`` or
    ``(NFR:...)`` marker counts as cited, preserving the pre-machine-checkable behavior for callers
    that have no STRAT counts to check against (e.g. ``validate_all``). When ``ac_count`` is given,
    an AC citation's ``#N`` must be present and within ``1..ac_count``, and an NFR citation's
    category must match one of ``nfr_categories`` case-insensitively.
    """
    if ac_count is None:
        return None
    if citation["kind"] == "AC":
        number = citation["number"]
        if number is None:
            return "missing_number"
        if number < 1 or number > ac_count:
            return "out_of_range"
        return None
    known = {c.casefold() for c in (nfr_categories or [])}
    if (citation["category"] or "").casefold() not in known:
        return "unknown_nfr_category"
    return None


def validate_ac_citations(testplan_path: str, ac_count: int | None = None, nfr_categories: list | None = None) -> dict:
    """Check Section 1.3 objectives for (AC: #N — text) / (NFR: category — text) citations.

    Presence-only when ``ac_count`` is None: any recognized marker counts as cited. When ``ac_count``
    is supplied, each AC citation's ``#N`` is bounds-checked against it and each NFR citation's
    category against ``nfr_categories``; out-of-bounds citations land in ``invalid_citations`` so the
    gate can tell "uncited" apart from "cited but wrong."
    """
    if ac_count is not None and ac_count < 0:
        return {"valid": False, "error": "ac_count must be non-negative"}

    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    section_lines, start_line = extract_section(content, TEMPLATE_HEADINGS["1.3"])
    if not section_lines:
        return {"valid": True, "total": 0, "cited": 0, "uncited": [], "invalid_citations": []}

    objectives = [
        {"text": obj["text"], "line_number": start_line + obj["line_index"]}
        for obj in parse_numbered_objectives(section_lines)
    ]

    has_content = any(line.strip() for line in section_lines)
    if has_content and not objectives:
        return {
            "valid": False,
            "error": "Section 1.3 has content but no numbered objectives detected (expected: 1. 2. 3. ...)",
        }

    uncited = []
    invalid_citations = []
    for obj in objectives:
        cites = parse_citations(obj["text"])
        if not cites:
            uncited.append(obj)
            continue
        reasons = [r for c in cites if (r := _citation_reason(c, ac_count, nfr_categories)) is not None]
        if reasons:
            invalid_citations.append({**obj, "reasons": reasons})

    cited = len(objectives) - len(uncited) - len(invalid_citations)

    return {
        "valid": not uncited and not invalid_citations,
        "total": len(objectives),
        "cited": cited,
        "uncited": uncited,
        "invalid_citations": invalid_citations,
    }


def validate_ac_coverage(testplan_path: str, ac_count: int) -> dict:
    """Check every AC number 1..ac_count is cited by at least one Section 1.3 objective."""
    if ac_count < 0:
        return {"valid": False, "error": "ac_count must be non-negative"}
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    section_lines, _ = extract_section(content, TEMPLATE_HEADINGS["1.3"])
    objectives = parse_numbered_objectives(section_lines) if section_lines else []
    covered = set()
    for obj in objectives:
        for citation in parse_citations(obj["text"]):
            if citation["kind"] == "AC" and citation["number"] is not None:
                covered.add(citation["number"])

    missing = [n for n in range(1, ac_count + 1) if n not in covered]

    return {
        "valid": not missing,
        "ac_count": ac_count,
        "covered": sorted(covered),
        "missing": missing,
    }


def validate_structure(testplan_path: str) -> dict:
    """Check TestPlan.md for required headings and bold-text pseudo-headings."""
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    lines = content.splitlines()

    required = [s["heading"] for s in TESTPLAN_STRUCTURE["sections"] if s["required"]]
    missing_headings = [h for h in required if not any(line.startswith(h) for line in lines)]

    pseudo_re = re.compile(r"^\*\*[A-Z][^*]+\*\*:?\s*$")
    pseudo_headings = [
        {"text": line.strip(), "line_number": i + 1} for i, line in enumerate(lines) if pseudo_re.match(line.strip())
    ]

    return {
        "valid": not missing_headings and not pseudo_headings,
        "missing_headings": missing_headings,
        "pseudo_headings": pseudo_headings,
    }


FEATURE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_feature_name(feature_name: str) -> dict:
    """Check feature_name is a safe snake_case directory name."""
    if not FEATURE_NAME_RE.fullmatch(feature_name):
        return {
            "valid": False,
            "error": f"feature_name must be snake_case (^[a-z][a-z0-9_]*$): {feature_name!r}",
        }
    return {"valid": True}


TESTPLAN_LINK_RE = re.compile(r"\]\(\s*(?:\./)?TestPlan\.md(?:#[^)\s]*)?\s*\)")


def validate_readme(feature_dir: str, strat_url: str) -> dict:
    """Check README.md exists, is non-empty, and contains strat_url and a link to TestPlan.md."""
    if not strat_url.strip():
        return {"valid": False, "error": "strat_url must be non-empty"}
    path = Path(feature_dir) / "README.md"
    if not path.is_file():
        return {"valid": False, "error": f"File not found: {path}"}
    content = path.read_text()
    if not content.strip():
        return {"valid": False, "error": f"README.md is empty: {path}"}
    missing = []
    if not re.search(re.escape(strat_url) + r"(?![\w-])", content):
        missing.append("strat_url")
    if not TESTPLAN_LINK_RE.search(content):
        missing.append("TestPlan.md link")
    return {"valid": not missing, "missing": missing}


def validate_category_prefixes(testplan_path: str) -> dict:
    """Check Section 5.2 for disallowed TC category prefixes."""
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    section_lines, start_line = extract_section(content, TEMPLATE_HEADINGS["5.2"])
    if not section_lines:
        return {"valid": True, "disallowed": []}

    allowed = set(TESTPLAN_STRUCTURE["allowed_tc_categories"])
    tc_re = re.compile(r"TC-([A-Za-z0-9]+)")

    disallowed = []
    seen = set()
    for i, line in enumerate(section_lines):
        for match in tc_re.finditer(line):
            cat = match.group(1)
            if cat not in allowed and cat not in seen:
                seen.add(cat)
                disallowed.append({"category": cat, "line_number": start_line + i})

    return {"valid": not disallowed, "disallowed": disallowed}


INTERFACE_TABLE_COLUMNS = ["Interface", "Type", "Purpose"]
ALLOWED_INTERFACE_TYPES = frozenset({"REST", "gRPC", "UI", "CLI", "CRD"})
MARKDOWN_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
E2E_OR_UI_REFERENCE_RE = re.compile(r"(?<![\w-])TC-(?:E2E|UI)-[A-Za-z0-9]+(?![\w-])")


def _is_markdown_separator_row(columns: list[str]) -> bool:
    """True when every cell is a Markdown table separator cell (e.g. ``---``, ``:---:``)."""
    return bool(columns) and all(MARKDOWN_SEPARATOR_CELL_RE.match(c.strip()) for c in columns)


def validate_interface_types(testplan_path: str) -> dict:
    """Check Section 4 for allowed interface types and correct table columns (no Priority)."""
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    section_lines, start_line = extract_section(content, TEMPLATE_HEADINGS["4"])
    if not section_lines:
        return {"valid": True, "disallowed_entries": [], "header": None}

    disallowed_entries = []
    header = None
    header_error = None
    first_pipe_row = True
    for i, line in enumerate(section_lines):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue

        columns = [c.strip() for c in stripped.strip("|").split("|")]
        if _is_markdown_separator_row(columns):
            continue

        line_number = start_line + i
        if first_pipe_row:
            header = columns
            first_pipe_row = False
            if header != INTERFACE_TABLE_COLUMNS:
                header_error = {
                    "expected": INTERFACE_TABLE_COLUMNS,
                    "found": header,
                    "line_number": line_number,
                }
            continue

        interface = columns[0] if columns else ""
        type_cell = columns[1] if len(columns) > 1 else ""
        if type_cell not in ALLOWED_INTERFACE_TYPES:
            disallowed_entries.append({"interface": interface, "type": type_cell, "line_number": line_number})

    result = {
        "valid": not disallowed_entries and header_error is None,
        "disallowed_entries": disallowed_entries,
        "header": header,
    }
    if header_error:
        result["header_error"] = header_error
    return result


def validate_interface_coverage(testplan_path: str) -> dict:
    """Check Section 9.2 and Section 6.2 cover Section 4 interfaces and E2E/UI references."""
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()

    section4_lines, _ = extract_section(content, TEMPLATE_HEADINGS["4"])
    section4_rows = parse_table_rows(section4_lines)
    interfaces = [row[0] for row in section4_rows if row and row[0]]

    pending = [
        row[0] for row in section4_rows if row and row[0] and any("pending details" in cell.lower() for cell in row)
    ]
    pending_set = {normalize_interface(p) for p in pending}

    if not interfaces:
        return {
            "valid": True,
            "interfaces": [],
            "pending": [],
            "missing_in_9_2": [],
            "missing_in_6_2": [],
            "missing_e2e_or_ui_in_6_2": [],
            "section_9_2_populated": False,
            "section_6_2_populated": False,
        }

    # 9.2 is populated by the Test Cases column: /test-plan-create fills the Interface column
    # but leaves Test Cases blank until /test-plan-create-cases runs, so key the guard on col 1.
    section92_lines, _ = extract_section(content, TEMPLATE_HEADINGS["9.2"])
    rows_92 = parse_table_rows(section92_lines)
    populated_92 = any(row and row[0] and len(row) > 1 and is_filled_cell(row[1]) for row in rows_92)
    covered_92 = {
        normalize_interface(row[0]) for row in rows_92 if row and row[0] and len(row) > 1 and is_filled_cell(row[1])
    }
    skip_92 = covered_92 | pending_set
    missing_in_9_2 = [i for i in interfaces if normalize_interface(i) not in skip_92] if populated_92 else []

    # 6.2 is empty pre-create-cases (no interface names either), so its guard keys on col 0.
    section62_lines, _ = extract_section(content, TEMPLATE_HEADINGS["6.2"])
    rows_62 = parse_table_rows(section62_lines)
    populated_62 = any(row and row[0] for row in rows_62)
    populated_rows_62 = [row for row in rows_62 if row and row[0] and len(row) > 1 and is_filled_cell(row[1])]
    covered_62 = {normalize_interface(row[0]) for row in populated_rows_62}
    skip_62 = covered_62 | pending_set
    missing_in_6_2 = [i for i in interfaces if normalize_interface(i) not in skip_62] if populated_62 else []
    declared_interfaces = {normalize_interface(i) for i in interfaces}
    declared_rows_62 = [row for row in rows_62 if row and row[0] and normalize_interface(row[0]) in declared_interfaces]
    missing_e2e_or_ui_interfaces = set()
    # Check every declared row independently, including blank/placeholder cells: a duplicate row
    # with a valid reference must not mask another duplicate row for the same interface that has
    # neither reference. Keep lone blank/placeholder rows under missing_in_6_2 only.
    for row in declared_rows_62:
        interface = normalize_interface(row[0])
        reference_cell = row[1] if len(row) > 1 else ""
        if (
            interface in declared_interfaces
            and interface not in pending_set
            and not E2E_OR_UI_REFERENCE_RE.search(reference_cell)
        ):
            missing_e2e_or_ui_interfaces.add(interface)
    missing_e2e_or_ui_in_6_2 = (
        [
            i
            for i in interfaces
            if normalize_interface(i) in covered_62 and normalize_interface(i) in missing_e2e_or_ui_interfaces
        ]
        if populated_62
        else []
    )

    return {
        "valid": not missing_in_9_2 and not missing_in_6_2 and not missing_e2e_or_ui_in_6_2,
        "interfaces": interfaces,
        "pending": pending,
        "missing_in_9_2": missing_in_9_2,
        "missing_in_6_2": missing_in_6_2,
        "missing_e2e_or_ui_in_6_2": missing_e2e_or_ui_in_6_2,
        "section_9_2_populated": populated_92,
        "section_6_2_populated": populated_62,
    }


def validate_infra_scope(testplan_path: str) -> dict:
    """Check Sections 3.1/3.4 for local development tooling indicators."""
    path = Path(testplan_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {testplan_path}"}

    content = path.read_text()
    indicators = TESTPLAN_STRUCTURE["dev_tooling_indicators"]
    section_headings = TESTPLAN_STRUCTURE["infra_sections"]

    warnings = []
    seen = set()
    boundary_res = {ind: re.compile(r"(?<![\w-])" + re.escape(ind.casefold()) + r"(?![\w-])") for ind in indicators}
    for heading in section_headings:
        section_lines, start_line = extract_section(content, heading)
        if not section_lines:
            continue
        for i, line in enumerate(section_lines):
            normalized_line = line.casefold()
            for indicator in indicators:
                if boundary_res[indicator].search(normalized_line) and indicator not in seen:
                    seen.add(indicator)
                    warnings.append(
                        {
                            "indicator": indicator,
                            "section": heading,
                            "line_number": start_line + i,
                        }
                    )

    return {"valid": not warnings, "warnings": warnings}


def validate_tc_counts(feature_dir: str) -> dict:
    """Check Section 9.1 TC totals match actual TC file count and row arithmetic."""
    feature_path = Path(feature_dir)
    testplan_path = feature_path / "TestPlan.md"
    tc_dir = feature_path / "test_cases"

    if not testplan_path.exists():
        return {"valid": False, "error": f"TestPlan.md not found at {testplan_path}"}
    if not tc_dir.exists():
        return {"valid": True, "file_count": 0, "table_total": 0, "mismatches": []}

    actual_count = len(list(tc_dir.glob("TC-*.md")))

    content = testplan_path.read_text()
    section_lines, _ = extract_section(content, TEMPLATE_HEADINGS["9.1"])
    if not section_lines:
        return {"valid": True, "file_count": actual_count, "table_total": 0, "mismatches": []}

    total_re = re.compile(r"^\|\s*\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*")
    row_re = re.compile(r"^\|\s*TC-\S+\s*\|\s*(\d+)\s*\|")

    table_total = 0
    row_sum = 0
    mismatches = []
    for line in section_lines:
        total_match = total_re.match(line)
        if total_match:
            table_total = int(total_match.group(1))
        row_match = row_re.match(line)
        if row_match:
            row_sum += int(row_match.group(1))

    if table_total > 0 and row_sum != table_total:
        mismatches.append(f"Row sum ({row_sum}) != table total ({table_total})")

    if table_total > 0 and actual_count != table_total:
        mismatches.append(f"TC file count ({actual_count}) != table total ({table_total})")
    if row_sum > 0 and actual_count != row_sum:
        mismatches.append(f"TC file count ({actual_count}) != row sum ({row_sum})")
    if table_total == 0 and row_sum == 0 and actual_count > 0:
        mismatches.append(f"TC files exist ({actual_count}) but no parseable Total/row counts in Section 9.1")

    return {
        "valid": not mismatches,
        "file_count": actual_count,
        "table_total": table_total,
        "row_sum": row_sum,
        "mismatches": mismatches,
    }


def validate_tc_scope(feature_dir: str) -> dict:
    """Check TC-*.md filenames follow TC-<CATEGORY>-<id>.md with allowed categories and matching test_case_id."""
    tc_dir = Path(feature_dir) / "test_cases"
    if not tc_dir.exists():
        return {"valid": True, "checked": 0, "disallowed": [], "id_mismatches": [], "malformed": []}

    tc_files = sorted(tc_dir.glob("TC-*.md"))
    if not tc_files:
        return {"valid": True, "checked": 0, "disallowed": [], "id_mismatches": [], "malformed": []}

    allowed = set(TESTPLAN_STRUCTURE["allowed_tc_categories"])
    tc_re = re.compile(r"^TC-([A-Z0-9]+)-\d+\.md$")

    disallowed = []
    id_mismatches = []
    malformed = []
    for f in tc_files:
        match = tc_re.match(f.name)
        if not match:
            malformed.append(f.name)
            continue
        if match.group(1) not in allowed:
            disallowed.append({"file": f.name, "category": match.group(1)})

        try:
            frontmatter, _ = read_frontmatter(str(f))
        except (OSError, yaml.YAMLError, ValueError) as e:
            id_mismatches.append({"file": f.name, "error": f"Failed to read frontmatter: {e}"})
            continue

        test_case_id = frontmatter.get("test_case_id")
        if test_case_id != f.stem:
            id_mismatches.append({"file": f.name, "frontmatter_test_case_id": test_case_id})

    return {
        "valid": not disallowed and not id_mismatches and not malformed,
        "checked": len(tc_files),
        "disallowed": disallowed,
        "id_mismatches": id_mismatches,
        "malformed": malformed,
    }


def validate_tc_traceability(feature_dir: str) -> dict:
    """Check TC objectives frontmatter traces to Section 1.3 objectives with AC citations."""
    feature_path = Path(feature_dir)
    testplan_path = feature_path / "TestPlan.md"
    if not testplan_path.exists():
        return {"valid": False, "error": f"TestPlan.md not found at {testplan_path}"}

    tc_dir = feature_path / "test_cases"
    if not tc_dir.exists():
        return {"valid": True, "checked": 0, "objectives_found": 0, "errors": []}

    tc_files = sorted(tc_dir.glob("TC-*.md"))
    if not tc_files:
        return {"valid": True, "checked": 0, "objectives_found": 0, "errors": []}

    content = testplan_path.read_text()
    section_lines, _ = extract_section(content, TEMPLATE_HEADINGS["1.3"])

    objectives = {
        obj["num"]: {"text": obj["text"], "has_citation": has_citation(obj["text"])}
        for obj in parse_numbered_objectives(section_lines)
    }

    errors = []
    for f in tc_files:
        try:
            frontmatter, _ = read_frontmatter(str(f))
        except (OSError, yaml.YAMLError, ValueError) as e:
            errors.append({"file": f.name, "error": f"Failed to read frontmatter: {e}"})
            continue

        raw_objectives = frontmatter.get("objectives")
        if not raw_objectives:
            errors.append({"file": f.name, "error": "Missing or empty 'objectives' field"})
            continue
        if not isinstance(raw_objectives, list):
            type_name = type(raw_objectives).__name__
            errors.append({"file": f.name, "error": f"'objectives' field must be a list, got {type_name}"})
            continue

        for raw_num in raw_objectives:
            try:
                num = int(raw_num)
            except (TypeError, ValueError):
                errors.append({"file": f.name, "error": f"Invalid objective reference: {raw_num!r}"})
                continue

            obj = objectives.get(num)
            if obj is None:
                errors.append({"file": f.name, "error": f"References nonexistent objective {num}"})
            elif not obj["has_citation"]:
                errors.append({"file": f.name, "error": f"Objective {num} has no AC or NFR citation"})

    return {
        "valid": not errors,
        "checked": len(tc_files),
        "objectives_found": len(objectives),
        "errors": errors,
    }


def check_interactive() -> dict:
    """Check whether the session is interactive or non-interactive (CI).

    Returns dict with:
        interactive: bool — True if interactive, False if non-interactive
        reason: str — which env var triggered non-interactive mode
    """
    ci = os.environ.get("CI", "")
    non_interactive = os.environ.get("CLAUDE_NON_INTERACTIVE", "")

    if non_interactive:
        return {"interactive": False, "reason": "CLAUDE_NON_INTERACTIVE is set"}
    if ci:
        return {"interactive": False, "reason": "CI is set"}
    return {"interactive": True, "reason": "no CI or CLAUDE_NON_INTERACTIVE env var detected"}


def validate_all(feature_dir: str, checks_dir: str = "scripts/checks") -> dict:
    """Run all validations on a feature directory.

    Only TestPlan.md is required. TestPlanGaps.md and test_cases/ are
    validated when present but their absence is not a failure.
    """
    feature_path = Path(feature_dir)

    testplan_path = feature_path / "TestPlan.md"
    if not testplan_path.exists():
        return {"valid": False, "error": f"TestPlan.md not found at {testplan_path}"}

    frontmatter_results = []
    for artifact in ["TestPlan.md", "TestPlanGaps.md"]:
        path = feature_path / artifact
        if not path.exists():
            continue
        try:
            read_frontmatter_validated(str(path), detect_schema_type(str(path)))
            frontmatter_results.append({"file": artifact, "valid": True})
        except Exception as e:
            frontmatter_results.append({"file": artifact, "valid": False, "error": str(e)})

    tc_result = validate_test_cases(feature_dir)
    ac_result = validate_ac_citations(str(testplan_path))
    structure_result = validate_structure(str(testplan_path))
    category_result = validate_category_prefixes(str(testplan_path))
    interface_result = validate_interface_types(str(testplan_path))
    interface_coverage_result = validate_interface_coverage(str(testplan_path))
    infra_result = validate_infra_scope(str(testplan_path))
    test_scope_result = validate_test_scope(str(testplan_path), checks_dir)
    tc_counts_result = validate_tc_counts(feature_dir)
    tc_scope_result = validate_tc_scope(feature_dir)
    tc_traceability_result = validate_tc_traceability(feature_dir)

    valid = (
        all(f["valid"] for f in frontmatter_results)
        and tc_result["valid"]
        and ac_result["valid"]
        and structure_result["valid"]
        and category_result["valid"]
        and interface_result["valid"]
        and interface_coverage_result["valid"]
        and infra_result["valid"]
        and test_scope_result["valid"]
        and tc_counts_result["valid"]
        and tc_scope_result["valid"]
        and tc_traceability_result["valid"]
    )

    return {
        "valid": valid,
        "frontmatter": frontmatter_results,
        "test_cases": tc_result,
        "ac_citations": ac_result,
        "structure": structure_result,
        "category_prefixes": category_result,
        "interface_types": interface_result,
        "interface_coverage": interface_coverage_result,
        "infra_scope": infra_result,
        "test_scope": test_scope_result,
        "tc_counts": tc_counts_result,
        "tc_scope": tc_scope_result,
        "tc_traceability": tc_traceability_result,
    }


def cmd_feature_dir(args):
    result = validate_feature_dir(args.feature_dir)
    print(result)
    data = json.loads(result)
    sys.exit(0 if data.get("valid") else 1)


def cmd_gap_counts(args):
    result = validate_gap_counts(args.feature_dir, args.resolved, args.unresolved, args.new)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_test_cases(args):
    result = validate_test_cases(args.feature_dir, args.schema_type)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_all(args):
    result = validate_all(args.feature_dir, args.checks_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_ac_citations(args):
    nfr_categories = [c.strip() for c in (args.nfr_category or []) if c.strip()]
    result = validate_ac_citations(args.testplan_path, ac_count=args.ac_count, nfr_categories=nfr_categories)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_ac_coverage(args):
    result = validate_ac_coverage(args.testplan_path, ac_count=args.ac_count)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_structure(args):
    result = validate_structure(args.testplan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_category_prefixes(args):
    result = validate_category_prefixes(args.testplan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_feature_name(args):
    result = validate_feature_name(args.feature_name)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_readme(args):
    result = validate_readme(args.feature_dir, args.strat_url)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_interface_types(args):
    result = validate_interface_types(args.testplan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_interface_coverage(args):
    result = validate_interface_coverage(args.testplan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_infra_scope(args):
    result = validate_infra_scope(args.testplan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_tc_counts(args):
    result = validate_tc_counts(args.feature_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_tc_scope(args):
    result = validate_tc_scope(args.feature_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_tc_traceability(args):
    result = validate_tc_traceability(args.feature_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_check_interactive(_args):
    result = check_interactive()
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["interactive"] else 0)


def main():
    parser = argparse.ArgumentParser(
        description="Unified validation CLI for test plan artifacts",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_feature = subparsers.add_parser("feature-dir", help="Validate feature directory structure")
    p_feature.add_argument("feature_dir", help="Path to feature directory")
    p_feature.set_defaults(func=cmd_feature_dir)

    p_gaps = subparsers.add_parser("gap-counts", help="Validate gap count arithmetic")
    p_gaps.add_argument("feature_dir", help="Path to feature directory")
    p_gaps.add_argument("resolved", type=int, help="Gaps resolved")
    p_gaps.add_argument("unresolved", type=int, help="Gaps still unresolved")
    p_gaps.add_argument("new", type=int, help="New gaps identified")
    p_gaps.set_defaults(func=cmd_gap_counts)

    p_tc = subparsers.add_parser("test-cases", help="Validate all TC-*.md frontmatter")
    p_tc.add_argument("feature_dir", help="Path to feature directory")
    p_tc.add_argument("schema_type", nargs="?", default="test-case", help="Schema type (default: test-case)")
    p_tc.set_defaults(func=cmd_test_cases)

    p_all = subparsers.add_parser("all", help="Run all validations on a feature directory")
    p_all.add_argument("feature_dir", help="Path to feature directory")
    p_all.add_argument("--checks-dir", default="scripts/checks", help="Base directory for check config files")
    p_all.set_defaults(func=cmd_all)

    p_ac = subparsers.add_parser("ac-citations", help="Check Section 1.3 objectives for AC/NFR citations")
    p_ac.add_argument("testplan_path", help="Path to TestPlan.md")
    p_ac.add_argument(
        "--ac-count", type=int, default=None, help="STRAT acceptance-criteria count; enables (AC: #N) bounds-checking"
    )
    p_ac.add_argument(
        "--nfr-category",
        action="append",
        dest="nfr_category",
        default=None,
        metavar="CATEGORY",
        help="NFR category name to validate (NFR: category) against; repeat for multiple",
    )
    p_ac.set_defaults(func=cmd_ac_citations)

    p_ac_cov = subparsers.add_parser(
        "ac-coverage", help="Check every AC number 1..ac_count is cited by some Section 1.3 objective"
    )
    p_ac_cov.add_argument("testplan_path", help="Path to TestPlan.md")
    p_ac_cov.add_argument(
        "--ac-count", type=int, required=True, help="STRAT acceptance-criteria count to check coverage against"
    )
    p_ac_cov.set_defaults(func=cmd_ac_coverage)

    p_struct = subparsers.add_parser("structure", help="Check required headings and pseudo-heading violations")
    p_struct.add_argument("testplan_path", help="Path to TestPlan.md")
    p_struct.set_defaults(func=cmd_structure)

    p_cat = subparsers.add_parser("category-prefixes", help="Check Section 5.2 for disallowed TC categories")
    p_cat.add_argument("testplan_path", help="Path to TestPlan.md")
    p_cat.set_defaults(func=cmd_category_prefixes)

    p_feature_name = subparsers.add_parser(
        "feature-name", help="Check feature_name is safe snake_case (no path traversal)"
    )
    p_feature_name.add_argument("feature_name", help="Feature directory name to validate")
    p_feature_name.set_defaults(func=cmd_feature_name)

    p_readme = subparsers.add_parser("readme", help="Check README.md has strat_url and a TestPlan.md link")
    p_readme.add_argument("feature_dir", help="Path to feature directory")
    p_readme.add_argument("--strat-url", required=True, help="Strategy URL README.md must contain")
    p_readme.set_defaults(func=cmd_readme)

    p_iface = subparsers.add_parser(
        "interface-types", help="Check Section 4 interface types against REST/gRPC/UI/CLI/CRD allowlist"
    )
    p_iface.add_argument("testplan_path", help="Path to TestPlan.md")
    p_iface.set_defaults(func=cmd_interface_types)

    p_iface_cov = subparsers.add_parser("interface-coverage", help="Check Section 9.2/6.2 cover Section 4 interfaces")
    p_iface_cov.add_argument("testplan_path", help="Path to TestPlan.md")
    p_iface_cov.set_defaults(func=cmd_interface_coverage)

    p_infra = subparsers.add_parser("infra-scope", help="Check Sections 3.1/3.4 for dev tooling")
    p_infra.add_argument("testplan_path", help="Path to TestPlan.md")
    p_infra.set_defaults(func=cmd_infra_scope)

    p_tc_counts = subparsers.add_parser("tc-counts", help="Check Section 9.1 TC totals match file count")
    p_tc_counts.add_argument("feature_dir", help="Path to feature directory")
    p_tc_counts.set_defaults(func=cmd_tc_counts)

    p_tc_scope = subparsers.add_parser("tc-scope", help="Check TC filenames use allowed categories")
    p_tc_scope.add_argument("feature_dir", help="Path to feature directory")
    p_tc_scope.set_defaults(func=cmd_tc_scope)

    p_tc_trace = subparsers.add_parser("tc-traceability", help="Check TC objectives trace to Section 1.3 + AC")
    p_tc_trace.add_argument("feature_dir", help="Path to feature directory")
    p_tc_trace.set_defaults(func=cmd_tc_traceability)

    p_check_interactive = subparsers.add_parser("check-interactive", help="Check if session is non-interactive (CI)")
    p_check_interactive.set_defaults(func=cmd_check_interactive)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
