"""Unit tests for scripts/validate.py — unified validation CLI."""

import json
import sys

import pytest

from scripts import validate as validate_module
from scripts.utils.frontmatter_utils import write_frontmatter
from scripts.utils.schemas import TEMPLATE_HEADINGS
from scripts.validate import (
    check_interactive,
    validate_ac_citations,
    validate_ac_coverage,
    validate_all,
    validate_category_prefixes,
    validate_feature_dir,
    validate_feature_name,
    validate_gap_counts,
    validate_infra_scope,
    validate_interface_coverage,
    validate_interface_types,
    validate_readme,
    validate_structure,
    validate_tc_counts,
    validate_tc_scope,
    validate_tc_traceability,
    validate_test_cases,
)
from scripts.validate_test_scope import load_and_validate as validate_scope
from tests.consts.test_plan_constants import (
    README_NO_STRAT_URL,
    README_NO_TESTPLAN_LINK,
    README_STRAT_URL,
    README_VALID,
    TESTPLAN_AC_BULLET_FORMAT,
    TESTPLAN_AC_CITED,
    TESTPLAN_AC_MISSING,
    TESTPLAN_BOLD_HEADINGS,
    TESTPLAN_BROAD_LEVELS,
    TESTPLAN_CLEAN_INFRA,
    TESTPLAN_CONFIG_INTERFACES,
    TESTPLAN_DATABASE_INTERFACES,
    TESTPLAN_DEV_TOOLING_INFRA,
    TESTPLAN_E2E_ONLY,
    TESTPLAN_EMPTY_TYPE_INTERFACES,
    TESTPLAN_FEATURE_CATEGORIES,
    TESTPLAN_INTERFACE_COVERAGE_EMPTY_6_2_CELL,
    TESTPLAN_INTERFACE_COVERAGE_EMPTY_9_2_CELL,
    TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_E2E_6_2,
    TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_MIXED_6_2,
    TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_NO_E2E_OR_UI_6_2,
    TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_PLACEHOLDER_TEMPLATE_6_2,
    TESTPLAN_INTERFACE_COVERAGE_EXTRA_6_2_ROW,
    TESTPLAN_INTERFACE_COVERAGE_FULL,
    TESTPLAN_INTERFACE_COVERAGE_MISSING_6_2,
    TESTPLAN_INTERFACE_COVERAGE_MISSING_9_2,
    TESTPLAN_INTERFACE_COVERAGE_MIXED_6_2,
    TESTPLAN_INTERFACE_COVERAGE_NO_E2E_OR_UI_6_2,
    TESTPLAN_INTERFACE_COVERAGE_PENDING,
    TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_6_2,
    TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_SCENARIO_CELL,
    TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_TC_CELL,
    TESTPLAN_INTERFACE_COVERAGE_UI_ONLY_6_2,
    TESTPLAN_INTERFACE_TYPES_BLANK_HEADER_CELL,
    TESTPLAN_MISSING_SECTIONS,
    TESTPLAN_MISSING_TYPE_COLUMN_INTERFACES,
    TESTPLAN_NO_SECTION_13,
    TESTPLAN_NO_SECTION_21,
    TESTPLAN_NO_SECTION_52,
    TESTPLAN_NO_SEPARATOR_INTERFACES,
    TESTPLAN_REST_WRONG_CASE_INTERFACES,
    TESTPLAN_VALID_CATEGORIES,
    TESTPLAN_VALID_INTERFACES,
    VALID_TEST_PLAN_DATA,
    VALID_TESTPLAN_CONTENT,
)
from tests.constants import VALID_TC_CONTENT, VALID_TEST_GAPS_DATA
from tests.helpers import write_testplan_with_objectives, write_valid_testplan

E2E_OR_UI_DIAGNOSTIC_KEY = "missing_e2e_or_ui_in_6_2"


def assert_e2e_or_ui_diagnostic(result, expected):
    assert E2E_OR_UI_DIAGNOSTIC_KEY in result
    assert result[E2E_OR_UI_DIAGNOSTIC_KEY] == expected


@pytest.fixture
def gaps_dir(tmp_path):
    """A directory with a TestPlanGaps.md (gap_count=10)."""
    data = {**VALID_TEST_GAPS_DATA, "gap_count": 10}
    write_frontmatter(str(tmp_path / "TestPlanGaps.md"), data, "test-gaps")
    return str(tmp_path)


class TestValidateFeatureDir:
    """Tests for validate_feature_dir function."""

    def test_valid_feature_dir(self, feature_dir):
        result = json.loads(validate_feature_dir(feature_dir))

        assert result["valid"] is True
        assert result["tc_count"] == 1
        assert result["testplan_frontmatter"]["source_key"] == VALID_TEST_PLAN_DATA["source_key"]

    def test_missing_testplan(self, tmp_path):
        result = json.loads(validate_feature_dir(str(tmp_path)))

        assert result["valid"] is False
        assert "TestPlan.md not found" in result["error"]

    def test_missing_test_cases_dir(self, tmp_path):
        (tmp_path / "TestPlan.md").write_text(VALID_TESTPLAN_CONTENT)

        result = json.loads(validate_feature_dir(str(tmp_path)))

        assert result["valid"] is False
        assert "test_cases" in result["error"]

    def test_malformed_yaml_returns_json_error(self, tmp_path):
        (tmp_path / "TestPlan.md").write_text("---\n: invalid yaml: [\n---\n")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")
        (tc_dir / "TC-E2E-001.md").write_text(VALID_TC_CONTENT)

        result = json.loads(validate_feature_dir(str(tmp_path)))

        assert result["valid"] is False
        assert "error" in result

    def test_no_tc_files(self, tmp_path):
        (tmp_path / "TestPlan.md").write_text(VALID_TESTPLAN_CONTENT)
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")

        result = json.loads(validate_feature_dir(str(tmp_path)))

        assert result["valid"] is False
        assert "No TC-*.md files found" in result["error"]


class TestValidateGapCounts:
    """Tests for validate_gap_counts function."""

    def test_valid_arithmetic(self, gaps_dir):
        result = validate_gap_counts(gaps_dir, 3, 9, 2)

        assert result["valid"] is True
        assert result["original"] == 10
        assert result["expected"] == 9

    def test_mismatch(self, gaps_dir):
        result = validate_gap_counts(gaps_dir, 3, 8, 2)

        assert result["valid"] is False
        assert result["expected"] == 9
        assert result["unresolved"] == 8

    def test_missing_file(self, tmp_path):
        result = validate_gap_counts(str(tmp_path), 0, 0, 0)

        assert result["valid"] is False
        assert "not found" in result["error"]


class TestValidateTestCases:
    """Tests for validate_test_cases function."""

    def test_valid_returns_pass(self, feature_dir):
        result = validate_test_cases(feature_dir)

        assert result["valid"] is True
        assert result["checked"] == 1
        assert result["failed"] == 0

    def test_invalid_returns_fail(self, tmp_path):
        (tmp_path / "TestPlan.md").write_text(VALID_TESTPLAN_CONTENT)
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")
        (tc_dir / "TC-E2E-001.md").write_text("---\ntest_case_id: TC-E2E-001\n---\n")

        result = validate_test_cases(str(tmp_path))

        assert result["valid"] is False
        assert result["failed"] > 0
        assert len(result["errors"]) > 0

    def test_missing_index_with_tc_files(self, tmp_path):
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "TC-E2E-001.md").write_text(VALID_TC_CONTENT)

        result = validate_test_cases(str(tmp_path))

        assert result["valid"] is False
        assert "INDEX.md" in result["errors"][0]["error"]

    def test_no_test_cases_dir(self, tmp_path):
        result = validate_test_cases(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 0


class TestValidateAll:
    """Tests for validate_all — orchestration."""

    def test_all_valid(self, tmp_path):
        write_valid_testplan(tmp_path / "TestPlan.md")
        write_frontmatter(str(tmp_path / "TestPlanGaps.md"), {**VALID_TEST_GAPS_DATA, "gap_count": 3}, "test-gaps")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")
        (tc_dir / "TC-E2E-001.md").write_text(VALID_TC_CONTENT)

        result = validate_all(str(tmp_path))

        assert result["valid"] is True
        assert len(result["frontmatter"]) == 2
        assert all(f["valid"] for f in result["frontmatter"])
        assert result["test_cases"]["valid"] is True
        assert result["tc_scope"]["valid"] is True
        assert result["tc_traceability"]["valid"] is True
        assert result["interface_coverage"]["valid"] is True

    def test_valid_without_test_cases(self, tmp_path):
        write_valid_testplan(tmp_path / "TestPlan.md")

        result = validate_all(str(tmp_path))

        assert result["valid"] is True
        assert result["test_cases"]["checked"] == 0
        # Populated Section 4 + blank 9.2 Test Cases + no test_cases/ is the publish-before-cases
        # state — coverage must be skipped, not flagged missing.
        assert result["interface_coverage"]["section_9_2_populated"] is False
        assert result["interface_coverage"]["missing_in_9_2"] == []

    def test_stops_on_missing_testplan(self, tmp_path):
        result = validate_all(str(tmp_path))

        assert result["valid"] is False
        assert "TestPlan.md" in result["error"]

    def test_skips_optional_gaps(self, tmp_path):
        write_valid_testplan(tmp_path / "TestPlan.md")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")
        (tc_dir / "TC-E2E-001.md").write_text(VALID_TC_CONTENT)

        result = validate_all(str(tmp_path))

        assert result["valid"] is True
        assert len(result["frontmatter"]) == 1

    def test_reports_invalid_test_cases(self, tmp_path):
        write_valid_testplan(tmp_path / "TestPlan.md")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "INDEX.md").write_text("# Index")
        (tc_dir / "TC-E2E-001.md").write_text("---\ntest_case_id: TC-E2E-001\n---\n")

        result = validate_all(str(tmp_path))

        assert result["valid"] is False
        assert result["test_cases"]["valid"] is False

    def test_flags_disallowed_test_level_in_scope(self, tmp_path):
        """validate_all must catch Section 2.1 scope violations (not just infra/tc scope)."""
        write_valid_testplan(tmp_path / "TestPlan.md")
        testplan_path = tmp_path / "TestPlan.md"
        testplan_path.write_text(testplan_path.read_text().replace("E2E System Testing", "Unit Testing"))

        result = validate_all(str(tmp_path))

        assert result["valid"] is False
        assert result["test_scope"]["valid"] is False


class TestValidateScope:
    """Tests for validate_scope — disallowed test levels in Section 2.1."""

    def test_e2e_only_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_E2E_ONLY)

        result = validate_scope(str(testplan), checks_dir="scripts/checks", teams=None)

        assert result["valid"] is True
        assert result["violations"] == []

    def test_disallowed_levels_fail(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_BROAD_LEVELS)

        result = validate_scope(str(testplan), checks_dir="scripts/checks", teams=None)

        assert result["valid"] is False
        assert len(result["violations"]) == 3
        violation_names = [v["matched_pattern"] for v in result["violations"]]
        assert "API Integration Testing" in violation_names
        assert "Data Validation Testing" in violation_names
        # Functional Testing is caught by regex pattern
        assert any("functional" in pattern.lower() for pattern in violation_names)

    def test_missing_section_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_21)

        result = validate_scope(str(testplan), checks_dir="scripts/checks", teams=None)

        assert result["valid"] is True
        assert result["violations"] == []

    def test_file_not_found(self):
        result = validate_scope("/nonexistent/TestPlan.md", checks_dir="scripts/checks", teams=None)

        assert result["valid"] is False
        assert "error" in result


class TestValidateAcCitations:
    """Tests for validate_ac_citations — AC citation in Section 1.3 objectives."""

    def test_all_objectives_cited_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_AC_CITED)

        result = validate_ac_citations(str(testplan))

        assert result["valid"] is True
        assert result["total"] == 3
        assert result["cited"] == 3
        assert result["uncited"] == []

    def test_missing_citation_fails(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_AC_MISSING)

        result = validate_ac_citations(str(testplan))

        assert result["valid"] is False
        assert result["total"] == 3
        assert result["cited"] == 2
        assert len(result["uncited"]) == 1
        assert result["uncited"][0]["line_number"] > 0

    def test_no_section_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_13)

        result = validate_ac_citations(str(testplan))

        assert result["valid"] is True
        assert result["total"] == 0

    def test_non_numbered_format_fails(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_AC_BULLET_FORMAT)

        result = validate_ac_citations(str(testplan))

        assert result["valid"] is False
        assert "no numbered objectives detected" in result["error"]

    def test_file_not_found(self):
        result = validate_ac_citations("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result

    def test_negative_ac_count_is_rejected(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_13)

        result = validate_ac_citations(str(testplan), ac_count=-1)

        assert result["valid"] is False
        assert "error" in result
        assert "non-negative" in result["error"].lower()


class TestValidateAcCitationsNumbered:
    """(AC: #N — text) / (NFR: category — text) machine-checkable citation validation."""

    @pytest.mark.parametrize(
        "citation, ac_count, nfr_categories, expected_reason",
        [
            ("(AC: #1 — first)", 2, [], None),
            ("(NFR: upgrade — shape kept)", 0, ["Upgrade"], None),
            ("(AC: #5 — beyond count)", 2, [], "out_of_range"),
            ("(AC: #0 — below one)", 2, [], "out_of_range"),
            ("(AC: — users can deploy)", 2, [], "missing_number"),
            ("(NFR: Performance — responsive)", 1, ["Upgrade"], "unknown_nfr_category"),
        ],
        ids=["valid-ac", "valid-nfr-caseless", "ac-too-high", "ac-too-low", "ac-no-number", "unknown-nfr"],
    )
    def test_single_citation_validation(self, tmp_path, citation, ac_count, nfr_categories, expected_reason):
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", f"1. Verify something {citation}\n")

        result = validate_ac_citations(path, ac_count=ac_count, nfr_categories=nfr_categories)

        if expected_reason is None:
            assert result["valid"] is True
            assert result["cited"] == 1
            assert result["invalid_citations"] == []
        else:
            assert result["valid"] is False
            assert result["cited"] == 0
            assert len(result["invalid_citations"]) == 1
            assert result["invalid_citations"][0]["reasons"] == [expected_reason]
            assert result["invalid_citations"][0]["line_number"] > 0

    def test_counts_split_across_buckets(self, tmp_path):
        body = (
            "1. Verify a (AC: #1 — first)\n"
            "2. Verify b (NFR: Upgrade — GET endpoints keep their shape)\n"
            "3. Verify c (AC: #9 — beyond count)\n"
            "4. Verify d with no citation at all\n"
        )
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path, ac_count=2, nfr_categories=["Upgrade"])

        assert result["valid"] is False
        assert result["total"] == 4
        assert result["cited"] == 2
        assert len(result["uncited"]) == 1
        assert len(result["invalid_citations"]) == 1
        assert result["invalid_citations"][0]["reasons"] == ["out_of_range"]

    def test_presence_only_mode_accepts_nfr_marker(self, tmp_path):
        # No ac_count -> presence-only (the validate_all path); an NFR marker counts as cited.
        body = (
            "1. Verify deployment (AC: #1 — users can deploy)\n"
            "2. Verify upgrade (NFR: Upgrade — GET endpoints keep their shape)\n"
        )
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path)

        assert result["valid"] is True
        assert result["total"] == 2
        assert result["cited"] == 2
        assert result["uncited"] == []
        assert result["invalid_citations"] == []


class TestValidateAcCoverage:
    """Tests for validate_ac_coverage — every AC number 1..ac_count cited by some objective.

    This is the inverse of validate_ac_citations: that checks each *objective's* citation is
    well-formed; this checks each *AC number* got covered at all, catching an analyzer that
    silently drops or conflates an AC even when every citation it did write is individually valid.
    """

    @pytest.mark.parametrize(
        "body, ac_count, expected_valid, expected_covered, expected_missing",
        [
            (
                "1. Verify a (AC: #1 — first)\n2. Verify b (AC: #2 — second)\n3. Verify c (AC: #3 — third)\n",
                3,
                True,
                [1, 2, 3],
                [],
            ),
            ("1. Verify a (AC: #1 — first)\n2. Verify c (AC: #3 — third)\n", 3, False, [1, 3], [2]),
            ("1. Verify a (AC: #1 — first)\n2. Verify upgrade (NFR: Upgrade — shape kept)\n", 2, False, [1], [2]),
            ("1. Verify a (AC: #1 — first)\n2. Verify a again (AC: #1 — first)\n", 2, False, [1], [2]),
            ("", 0, True, [], []),
        ],
        ids=[
            "all-covered",
            "one-missing",
            "nfr-does-not-count",
            "duplicate-collapses-other-still-missing",
            "zero-ac-count",
        ],
    )
    def test_coverage(self, tmp_path, body, ac_count, expected_valid, expected_covered, expected_missing):
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_coverage(path, ac_count=ac_count)

        assert result["valid"] is expected_valid
        assert result["covered"] == expected_covered
        assert result["missing"] == expected_missing

    def test_no_section_with_positive_ac_count_fails(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_13)

        result = validate_ac_coverage(str(testplan), ac_count=2)

        assert result["valid"] is False
        assert result["missing"] == [1, 2]

    def test_file_not_found(self):
        result = validate_ac_coverage("/nonexistent/TestPlan.md", ac_count=2)

        assert result["valid"] is False
        assert "error" in result

    def test_negative_ac_count_is_rejected(self, tmp_path):
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", "")

        result = validate_ac_coverage(path, ac_count=-1)

        assert result["valid"] is False
        assert "error" in result
        assert "non-negative" in result["error"].lower()

    def test_zero_ac_count_is_valid_with_empty_missing(self, tmp_path):
        # ac_count=0 is the "no ACs" edge case — valid, nothing to cover.
        # This is existing behaviour; the test pins it so the negative-ac fix cannot regress it.
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", "")

        result = validate_ac_coverage(path, ac_count=0)

        assert result["valid"] is True
        assert result["missing"] == []


class TestValidateStructure:
    """Tests for validate_structure — required headings and pseudo-heading detection."""

    def test_valid_structure_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        write_valid_testplan(testplan)

        result = validate_structure(str(testplan))

        assert result["valid"] is True
        assert result["missing_headings"] == []
        assert result["pseudo_headings"] == []

    def test_bold_pseudo_headings_fail(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_BOLD_HEADINGS)

        result = validate_structure(str(testplan))

        assert result["valid"] is False
        assert len(result["pseudo_headings"]) == 2
        pseudo_texts = [p["text"] for p in result["pseudo_headings"]]
        assert "**Measurement Points:**" in pseudo_texts
        assert "**Purpose:**" in pseudo_texts

    def test_missing_sections_fail(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_MISSING_SECTIONS)

        result = validate_structure(str(testplan))

        assert result["valid"] is False
        assert TEMPLATE_HEADINGS["1.3"] in result["missing_headings"]
        assert TEMPLATE_HEADINGS["2.1"] in result["missing_headings"]
        assert TEMPLATE_HEADINGS["4"] in result["missing_headings"]

    def test_file_not_found(self):
        result = validate_structure("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result


class TestValidateCategoryPrefixes:
    """Tests for validate_category_prefixes — allowed TC categories in Section 5.2."""

    def test_allowed_categories_pass(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_VALID_CATEGORIES)

        result = validate_category_prefixes(str(testplan))

        assert result["valid"] is True
        assert result["disallowed"] == []

    def test_feature_area_categories_fail(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_FEATURE_CATEGORIES)

        result = validate_category_prefixes(str(testplan))

        assert result["valid"] is False
        assert len(result["disallowed"]) == 3
        disallowed_names = [d["category"] for d in result["disallowed"]]
        assert "CSAF" in disallowed_names
        assert "AUTH" in disallowed_names
        assert "TOPIC" in disallowed_names

    def test_no_section_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_52)

        result = validate_category_prefixes(str(testplan))

        assert result["valid"] is True
        assert result["disallowed"] == []

    def test_file_not_found(self):
        result = validate_category_prefixes("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result


class TestValidateFeatureName:
    """Tests for validate_feature_name — snake_case guard against path traversal / flag injection."""

    @pytest.mark.parametrize(
        "feature_name, expected_valid",
        [
            ("mcp_catalog", True),
            ("feature2_test", True),
            ("../../outside", False),
            ("/tmp/outside", False),
            ("foo/bar", False),
            ("-rf", False),
            ("foo-bar", False),
            ("Feature_Name", False),
            ("", False),
            ("feature\n", False),
            ("feature\nmalicious", False),
        ],
        ids=[
            "simple-snake-case",
            "snake-case-with-digits",
            "relative-path-traversal",
            "absolute-path",
            "embedded-slash",
            "leading-dash",
            "hyphen-instead-of-underscore",
            "uppercase",
            "empty-string",
            "trailing-newline",
            "embedded-newline",
        ],
    )
    def test_validity(self, feature_name, expected_valid):
        result = validate_feature_name(feature_name)

        assert result["valid"] is expected_valid
        if not expected_valid:
            assert "error" in result


class TestValidateReadme:
    """Tests for validate_readme — README.md must exist with strat_url and a TestPlan.md link."""

    @pytest.mark.parametrize(
        "content, expected_missing",
        [
            pytest.param(README_VALID, [], id="complete"),
            pytest.param(README_NO_STRAT_URL, ["strat_url"], id="missing-strat-url"),
            pytest.param(README_NO_TESTPLAN_LINK, ["TestPlan.md link"], id="missing-testplan-link"),
            pytest.param("# Test Feature\n", ["strat_url", "TestPlan.md link"], id="missing-both"),
        ],
    )
    def test_content(self, tmp_path, content, expected_missing):
        (tmp_path / "README.md").write_text(content)

        result = validate_readme(str(tmp_path), README_STRAT_URL)

        assert result["valid"] is (not expected_missing)
        assert result["missing"] == expected_missing

    def test_missing_file(self, tmp_path):
        result = validate_readme(str(tmp_path), README_STRAT_URL)

        assert result["valid"] is False
        assert "File not found" in result["error"]

    def test_empty_file(self, tmp_path):
        (tmp_path / "README.md").write_text("  \n")

        result = validate_readme(str(tmp_path), README_STRAT_URL)

        assert result["valid"] is False
        assert "README.md is empty" in result["error"]

    def test_empty_strat_url_rejected(self, tmp_path):
        (tmp_path / "README.md").write_text(README_VALID)

        result = validate_readme(str(tmp_path), "")

        assert result["valid"] is False
        assert "strat_url must be non-empty" in result["error"]

    @pytest.mark.parametrize(
        "content, expected_exit",
        [pytest.param(README_VALID, 0, id="valid"), pytest.param(README_NO_TESTPLAN_LINK, 1, id="invalid")],
    )
    def test_cli(self, tmp_path, run_cli, content, expected_exit):
        (tmp_path / "README.md").write_text(content)

        exit_code, output = run_cli(validate_module.main, ["readme", str(tmp_path), "--strat-url", README_STRAT_URL])

        assert exit_code == expected_exit
        assert output["valid"] is (expected_exit == 0)


class TestValidateInterfaceTypes:
    """Tests for validate_interface_types — Section 4 Type is a positive allowlist."""

    def test_valid_types_pass(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_VALID_INTERFACES)

        result = validate_interface_types(str(testplan))

        assert result["valid"] is True
        assert result["disallowed_entries"] == []

    def test_config_type_warns(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_CONFIG_INTERFACES)

        result = validate_interface_types(str(testplan))

        assert result["valid"] is False
        assert "header_error" not in result
        config_disallowed = [e for e in result["disallowed_entries"] if e["type"] == "Config"]
        assert len(config_disallowed) == 2
        interfaces = [e["interface"] for e in config_disallowed]
        assert "`config.yaml`" in interfaces
        assert "`BASE_URL` env var" in interfaces
        for entry in config_disallowed:
            assert isinstance(entry["line_number"], int)

    @pytest.mark.parametrize(
        "content, disallowed_type, interface",
        [
            (TESTPLAN_DATABASE_INTERFACES, "Database", "legacy---store"),
            (TESTPLAN_REST_WRONG_CASE_INTERFACES, "ReST", "Chat completions API"),
            (TESTPLAN_EMPTY_TYPE_INTERFACES, "", "Widget API"),
            (TESTPLAN_NO_SEPARATOR_INTERFACES, "Database", "Unseparated datastore"),
            (TESTPLAN_MISSING_TYPE_COLUMN_INTERFACES, "", "Single-cell interface"),
        ],
        ids=["Database", "ReST", "empty_type", "no_separator", "missing_type_column"],
    )
    def test_disallowed_section4_types_fail(self, tmp_path, content, disallowed_type, interface):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(content)

        result = validate_interface_types(str(testplan))

        assert result["valid"] is False
        assert "header_error" not in result
        matching = [
            e for e in result["disallowed_entries"] if e["interface"] == interface and e["type"] == disallowed_type
        ]
        assert matching
        assert isinstance(matching[0]["line_number"], int)

    def test_no_section_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_52)

        result = validate_interface_types(str(testplan))

        assert result["valid"] is True
        assert result["disallowed_entries"] == []

    def test_blank_header_cell_reports_real_header(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_TYPES_BLANK_HEADER_CELL)

        result = validate_interface_types(str(testplan))

        # The real header row (with its blank cell) must be reported — not the first data row.
        assert result["header"] == ["Interface", "Type", ""]
        assert result["valid"] is False
        assert result["header_error"]["found"] == ["Interface", "Type", ""]

    def test_file_not_found(self):
        result = validate_interface_types("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result


class TestValidateInterfaceCoverage:
    """Tests for validate_interface_coverage — Section 4 interfaces vs Section 9.2/6.2 tables."""

    def test_full_coverage_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_FULL)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_9_2"] == []
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    @pytest.mark.parametrize(
        "declared_interface, covered_interface",
        [
            pytest.param("/v1/*", "/v1/", id="parent-interface-does-not-cover-path-glob"),
            pytest.param(
                "/v1/model*name*",
                "/v1/modelname",
                id="concrete-interface-does-not-cover-intratoken-path-glob",
            ),
        ],
    )
    def test_path_wildcard_is_not_satisfied_by_its_parent_interface(
        self, tmp_path, declared_interface, covered_interface
    ):
        testplan = tmp_path / "TestPlan.md"
        content = TESTPLAN_INTERFACE_COVERAGE_FULL.replace(
            "| /v1/models | REST | List models |", f"| {declared_interface} | REST | List models |"
        ).replace("| `/v1/models` |", f"| `{covered_interface}` |")
        testplan.write_text(content)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_9_2"] == [declared_interface]
        assert result["missing_in_6_2"] == [declared_interface]
        assert "**/v1/chat/completions**" not in result["missing_in_9_2"]
        assert "**/v1/chat/completions**" not in result["missing_in_6_2"]

    @pytest.mark.parametrize(
        "fixture",
        [TESTPLAN_INTERFACE_COVERAGE_UI_ONLY_6_2, TESTPLAN_INTERFACE_COVERAGE_FULL],
        ids=["ui-only", "e2e-only"],
    )
    def test_section_6_2_rows_with_e2e_or_ui_references_pass(self, tmp_path, fixture):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(fixture)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["section_6_2_populated"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_section_6_2_rows_with_neither_e2e_nor_ui_reference_fail(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_NO_E2E_OR_UI_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, ["`/v1/chat/completions`", "`/v1/models`"])

    def test_mixed_ui_and_e2e_section_6_2_rows_pass(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_MIXED_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_duplicate_section_6_2_rows_each_satisfying_e2e_or_ui_pass(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_MIXED_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_satisfying_duplicate_cannot_mask_duplicate_without_e2e_or_ui(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_NO_E2E_OR_UI_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, ["**/v1/chat/completions**"])

    @pytest.mark.parametrize(
        "scenario_reference",
        ["", "TBD", "N/A", "-"],
        ids=["blank", "tbd", "n-a", "dash"],
    )
    def test_satisfying_duplicate_cannot_mask_placeholder_duplicate(self, tmp_path, scenario_reference):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(
            TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_PLACEHOLDER_TEMPLATE_6_2.replace(
                "__SCENARIO_REFERENCE__", scenario_reference
            )
        )

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["section_6_2_populated"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, ["**/v1/chat/completions**"])

    def test_duplicate_section_6_2_rows_with_e2e_references_pass(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_DUPLICATE_E2E_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_extra_section_6_2_rows_are_outside_declared_interface_contract(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_EXTRA_6_2_ROW)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_missing_in_9_2_fails(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_MISSING_9_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_9_2"] == ["`/v1/models`"]

    def test_missing_in_6_2_fails_when_populated(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_MISSING_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_6_2"] == ["`/v1/models`"]
        assert_e2e_or_ui_diagnostic(result, [])

    def test_placeholder_6_2_skipped(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_6_2)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["section_6_2_populated"] is False
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_no_section_4_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_52)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["interfaces"] == []
        assert_e2e_or_ui_diagnostic(result, [])

    def test_pending_interfaces_excluded_from_missing(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_INTERFACE_COVERAGE_PENDING)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is True
        assert result["missing_in_9_2"] == []
        assert result["missing_in_6_2"] == []
        assert_e2e_or_ui_diagnostic(result, [])
        assert result["pending"] == ["`/v1/models`"]
        assert "`/v1/models`" in result["interfaces"]

    def test_file_not_found(self):
        result = validate_interface_coverage("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.parametrize(
        "fixture",
        [TESTPLAN_INTERFACE_COVERAGE_EMPTY_9_2_CELL, TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_TC_CELL],
        ids=["blank-cell", "placeholder-cell"],
    )
    def test_uncovered_tc_cell_in_9_2_fails(self, tmp_path, fixture):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(fixture)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_9_2"] == ["`/v1/models`"]

    @pytest.mark.parametrize(
        "fixture",
        [TESTPLAN_INTERFACE_COVERAGE_EMPTY_6_2_CELL, TESTPLAN_INTERFACE_COVERAGE_PLACEHOLDER_SCENARIO_CELL],
        ids=["blank-cell", "placeholder-cell"],
    )
    def test_uncovered_scenario_cell_in_6_2_fails(self, tmp_path, fixture):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(fixture)

        result = validate_interface_coverage(str(testplan))

        assert result["valid"] is False
        assert result["missing_in_6_2"] == ["`/v1/models`"]
        assert_e2e_or_ui_diagnostic(result, [])


class TestValidateInfraScope:
    """Tests for validate_infra_scope — local dev tooling in Sections 3.1/3.4."""

    def test_clean_infra_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_CLEAN_INFRA)

        result = validate_infra_scope(str(testplan))

        assert result["valid"] is True
        assert result["warnings"] == []

    def test_dev_tooling_warns(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_DEV_TOOLING_INFRA)

        result = validate_infra_scope(str(testplan))

        assert result["valid"] is False
        assert len(result["warnings"]) >= 3
        indicators = [w["indicator"] for w in result["warnings"]]
        assert "pip" in indicators
        assert "docker-compose" in indicators
        assert "Ollama" in indicators

    def test_no_sections_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(TESTPLAN_NO_SECTION_52)

        result = validate_infra_scope(str(testplan))

        assert result["valid"] is True
        assert result["warnings"] == []

    def test_file_not_found(self):
        result = validate_infra_scope("/nonexistent/TestPlan.md")

        assert result["valid"] is False
        assert "error" in result


class TestValidateTcCounts:
    """Tests for validate_tc_counts — Section 9.1 totals vs actual TC files."""

    def _make_feature_dir(self, tmp_path, section_91, tc_names):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(f"---\nfeature: Test\n---\n\n### 9.1 Test Case Summary\n\n{section_91}")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        for name in tc_names:
            (tc_dir / f"{name}.md").write_text(f"---\ntest_case_id: {name}\n---\n")
        return tmp_path

    def test_counts_match_passes(self, tmp_path):
        section = (
            "| Category | Total | P0 | P1 | P2 |\n"
            "|----------|-------|----|----|----|\n"
            "| TC-E2E | 2 | 1 | 1 | 0 |\n"
            "| TC-NEG | 1 | 0 | 1 | 0 |\n"
            "| **Total** | **3** | **1** | **2** | **0** |\n"
        )
        self._make_feature_dir(tmp_path, section, ["TC-E2E-001", "TC-E2E-002", "TC-NEG-001"])

        result = validate_tc_counts(str(tmp_path))

        assert result["valid"] is True
        assert result["file_count"] == 3
        assert result["table_total"] == 3

    def test_row_sum_mismatch_fails(self, tmp_path):
        section = (
            "| Category | Total | P0 | P1 | P2 |\n"
            "|----------|-------|----|----|----|\n"
            "| TC-E2E | 3 | 2 | 1 | 0 |\n"
            "| TC-NEG | 2 | 1 | 1 | 0 |\n"
            "| **Total** | **3** | **2** | **1** | **0** |\n"
        )
        tc_names = ["TC-E2E-001", "TC-E2E-002", "TC-E2E-003", "TC-NEG-001", "TC-NEG-002"]
        self._make_feature_dir(tmp_path, section, tc_names)

        result = validate_tc_counts(str(tmp_path))

        assert result["valid"] is False
        assert any("Row sum (5) != table total (3)" in m for m in result["mismatches"])

    def test_file_count_mismatch_fails(self, tmp_path):
        section = (
            "| Category | Total | P0 | P1 | P2 |\n"
            "|----------|-------|----|----|----|\n"
            "| TC-E2E | 2 | 1 | 1 | 0 |\n"
            "| **Total** | **2** | **1** | **1** | **0** |\n"
        )
        self._make_feature_dir(tmp_path, section, ["TC-E2E-001", "TC-E2E-002", "TC-E2E-003"])

        result = validate_tc_counts(str(tmp_path))

        assert result["valid"] is False
        assert any("TC file count (3) != table total (2)" in m for m in result["mismatches"])

    def test_no_test_cases_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text("---\nfeature: Test\n---\n\n### 9.1 Test Case Summary\n")

        result = validate_tc_counts(str(tmp_path))

        assert result["valid"] is True
        assert result["file_count"] == 0

    def test_malformed_table_with_tc_files_fails(self, tmp_path):
        section = "This section has no parseable table rows.\n"
        self._make_feature_dir(tmp_path, section, ["TC-E2E-001", "TC-E2E-002"])

        result = validate_tc_counts(str(tmp_path))

        assert result["valid"] is False
        assert result["file_count"] == 2
        assert any("no parseable" in m for m in result["mismatches"])


class TestValidateTcScope:
    """Tests for validate_tc_scope — TC filename categories vs allowed set."""

    def _make_tc_dir(self, tmp_path, names):
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        for name in names:
            (tc_dir / f"{name}.md").write_text(f"---\ntest_case_id: {name}\n---\n")
        return tmp_path

    def test_allowed_categories_pass(self, tmp_path):
        self._make_tc_dir(tmp_path, ["TC-E2E-001", "TC-UI-001"])

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 2
        assert result["disallowed"] == []

    def test_disallowed_category_fails(self, tmp_path):
        self._make_tc_dir(tmp_path, ["TC-E2E-001", "TC-AUTH-001"])

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is False
        assert result["checked"] == 2
        assert result["disallowed"] == [{"file": "TC-AUTH-001.md", "category": "AUTH"}]

    def test_no_test_cases_dir(self, tmp_path):
        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 0
        assert result["disallowed"] == []

    def test_no_tc_files(self, tmp_path):
        (tmp_path / "test_cases").mkdir()

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 0
        assert result["disallowed"] == []

    def test_frontmatter_id_mismatch_fails(self, tmp_path):
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        (tc_dir / "TC-E2E-001.md").write_text("---\ntest_case_id: TC-E2E-999\n---\n")

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is False
        assert result["id_mismatches"] == [{"file": "TC-E2E-001.md", "frontmatter_test_case_id": "TC-E2E-999"}]

    def test_frontmatter_id_matches_filename_passes(self, tmp_path):
        self._make_tc_dir(tmp_path, ["TC-E2E-001"])

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is True
        assert result["id_mismatches"] == []

    def test_malformed_filename_flagged(self, tmp_path):
        self._make_tc_dir(tmp_path, ["TC-e2e-001", "TC-E2E-abc"])

        result = validate_tc_scope(str(tmp_path))

        assert result["valid"] is False
        assert sorted(result["malformed"]) == ["TC-E2E-abc.md", "TC-e2e-001.md"]
        assert result["disallowed"] == []


class TestValidateTcTraceability:
    """Tests for validate_tc_traceability — TC objectives -> Section 1.3 -> AC citations."""

    def _make_feature_dir(self, tmp_path, section_13, tc_data):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text(f"---\nfeature: Test\n---\n\n### 1.3 Test Objectives\n\n{section_13}")
        tc_dir = tmp_path / "test_cases"
        tc_dir.mkdir()
        for name, frontmatter_extra in tc_data.items():
            fm_lines = "\n".join(f"{k}: {v}" for k, v in frontmatter_extra.items())
            (tc_dir / f"{name}.md").write_text(f"---\ntest_case_id: {name}\n{fm_lines}\n---\n")
        return tmp_path

    def test_valid_traceability_passes(self, tmp_path):
        # Objective 1's AC citation is wrapped onto a continuation line.
        section = (
            "1. Verify login flow\n   (AC: #1 — users can log in)\n2. Verify logout flow (AC: #2 — users can log out)\n"
        )
        self._make_feature_dir(
            tmp_path,
            section,
            {"TC-E2E-001": {"objectives": "[1]"}, "TC-E2E-002": {"objectives": "[2]"}},
        )

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 2
        assert result["objectives_found"] == 2
        assert result["errors"] == []

    def test_missing_objectives_field_fails(self, tmp_path):
        section = "1. Verify login flow (AC: users can log in)\n"
        self._make_feature_dir(tmp_path, section, {"TC-E2E-001": {}})

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "objectives" in result["errors"][0]["error"]

    def test_nonexistent_objective_fails(self, tmp_path):
        section = "1. Verify login flow (AC: users can log in)\n"
        self._make_feature_dir(tmp_path, section, {"TC-E2E-001": {"objectives": "[9]"}})

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "9" in result["errors"][0]["error"]

    def test_uncited_objective_fails(self, tmp_path):
        section = "1. Verify login flow (no AC cited)\n"
        self._make_feature_dir(tmp_path, section, {"TC-E2E-001": {"objectives": "[1]"}})

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "AC" in result["errors"][0]["error"]

    def test_no_test_cases_dir_passes(self, tmp_path):
        testplan = tmp_path / "TestPlan.md"
        testplan.write_text("---\nfeature: Test\n---\n\n### 1.3 Test Objectives\n\n1. Verify login flow (AC: x)\n")

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is True
        assert result["checked"] == 0

    def test_no_testplan_fails(self, tmp_path):
        (tmp_path / "test_cases").mkdir()

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert "error" in result

    def test_string_objectives_field_char_iterates_silently(self, tmp_path):
        """A malformed string objectives field must not be silently char-iterated into valid-looking refs."""
        section = "1. Verify login flow (AC: users can log in)\n2. Verify logout flow (AC: users can log out)\n"
        self._make_feature_dir(
            tmp_path,
            section,
            {"TC-E2E-001": {"objectives": '"12"'}},
        )

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "list" in result["errors"][0]["error"].lower()

    def test_mixed_valid_and_invalid(self, tmp_path):
        section = "1. Verify login flow (AC: #1 — users can log in)\n2. Verify logout flow (no AC cited)\n"
        self._make_feature_dir(
            tmp_path,
            section,
            {
                "TC-E2E-001": {"objectives": "[1]"},
                "TC-E2E-002": {"objectives": "[2]"},
                "TC-E2E-003": {"objectives": "[1, 2]"},
            },
        )

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is False
        assert result["checked"] == 3
        assert len(result["errors"]) == 2
        error_files = {e["file"] for e in result["errors"]}
        assert error_files == {"TC-E2E-002.md", "TC-E2E-003.md"}

    def test_nfr_cited_objective_traces_successfully(self, tmp_path):
        # An objective grounded in an NFR (not a numbered AC) is still a valid trace target.
        section = "1. Verify upgrade path (NFR: Upgrade — endpoints keep response shape)\n"
        self._make_feature_dir(tmp_path, section, {"TC-UPG-001": {"objectives": "[1]"}})

        result = validate_tc_traceability(str(tmp_path))

        assert result["valid"] is True
        assert result["errors"] == []


class TestCheckInteractive:
    """Tests for check_interactive — deterministic CI/non-interactive detection."""

    @pytest.mark.parametrize(
        ("env_vars", "expected_interactive", "expected_reason_contains"),
        [
            ({}, True, "no CI"),
            ({"CLAUDE_NON_INTERACTIVE": "true"}, False, "CLAUDE_NON_INTERACTIVE"),
            ({"CI": "true"}, False, "CI"),
            ({"CLAUDE_NON_INTERACTIVE": "1", "CI": "true"}, False, "CLAUDE_NON_INTERACTIVE"),
        ],
        ids=["interactive", "non-interactive-explicit", "non-interactive-ci", "explicit-takes-precedence"],
    )
    def test_check_interactive(self, monkeypatch, env_vars, expected_interactive, expected_reason_contains):
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("CLAUDE_NON_INTERACTIVE", raising=False)
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = check_interactive()

        assert result["interactive"] is expected_interactive
        assert expected_reason_contains in result["reason"]


class TestAcCitationsCliArgparse:
    """
    Drives the real validate.main() / cmd_ac_citations via sys.argv so that any divergence
    between the argparse definition (action="append", dest="nfr_category") and what
    cmd_ac_citations consumes is caught here against the real production parser.
    """

    def test_comma_containing_category_is_valid_citation(self, tmp_path, monkeypatch, capsys):
        # "Security, Privacy" passed as ONE --nfr-category flag must NOT be split on the comma;
        # the plan objective citing (NFR: Security, Privacy — ...) must be VALID.
        testplan = write_testplan_with_objectives(
            tmp_path / "TestPlan.md",
            "1. Verify data stays in namespace (NFR: Security, Privacy — data must not leave namespace)\n",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            ["validate.py", "ac-citations", testplan, "--ac-count", "0", "--nfr-category", "Security, Privacy"],
        )
        with pytest.raises(SystemExit) as exc_info:
            validate_module.main()

        assert exc_info.value.code == 0
        result = json.loads(capsys.readouterr().out)
        unknown = [c for c in result["invalid_citations"] if "unknown_nfr_category" in c["reasons"]]
        assert unknown == [], f"Category was split or not matched; invalid_citations={result['invalid_citations']}"

    def test_comma_containing_category_fails_without_matching_flag(self, tmp_path, monkeypatch, capsys):
        # Same plan, but a *different* category flag is supplied — proves the name had to match.
        testplan = write_testplan_with_objectives(
            tmp_path / "TestPlan.md",
            "1. Verify data stays in namespace (NFR: Security, Privacy — data must not leave namespace)\n",
        )

        monkeypatch.setattr(
            sys, "argv", ["validate.py", "ac-citations", testplan, "--ac-count", "0", "--nfr-category", "Upgrade"]
        )
        with pytest.raises(SystemExit) as exc_info:
            validate_module.main()

        assert exc_info.value.code == 1
        result = json.loads(capsys.readouterr().out)
        all_reasons = [r for c in result["invalid_citations"] for r in c["reasons"]]
        assert "unknown_nfr_category" in all_reasons

    def test_repeated_nfr_category_flags_both_register(self, tmp_path, monkeypatch, capsys):
        # --nfr-category Security --nfr-category Upgrade must register BOTH; a plan citing
        # Upgrade must be valid, proving the list is not collapsed to just the last value.
        testplan = write_testplan_with_objectives(
            tmp_path / "TestPlan.md",
            "1. Verify upgrade path (NFR: Upgrade — GET endpoints keep their shape)\n",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "validate.py",
                "ac-citations",
                testplan,
                "--ac-count",
                "0",
                "--nfr-category",
                "Security",
                "--nfr-category",
                "Upgrade",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            validate_module.main()

        assert exc_info.value.code == 0
        result = json.loads(capsys.readouterr().out)
        assert result["invalid_citations"] == []

    def test_no_nfr_category_flag_presence_only_mode_exits_0(self, tmp_path, monkeypatch, capsys):
        # When --nfr-category is omitted entirely (args.nfr_category stays None),
        # cmd_ac_citations must not error; a valid (AC: #1 — text) with --ac-count 1 exits 0.
        testplan = write_testplan_with_objectives(
            tmp_path / "TestPlan.md",
            "1. Verify login flow (AC: #1 — users can authenticate)\n",
        )

        monkeypatch.setattr(sys, "argv", ["validate.py", "ac-citations", testplan, "--ac-count", "1"])
        with pytest.raises(SystemExit) as exc_info:
            validate_module.main()

        assert exc_info.value.code == 0
        result = json.loads(capsys.readouterr().out)
        assert result["valid"] is True
        assert result["cited"] == 1


class TestValidateAcCoverageMultiCitation:
    """validate_ac_coverage must count AC numbers from ALL citations per objective, not just the first."""

    def test_single_objective_citing_two_acs_covers_both(self, tmp_path):
        # RED against current code: only (AC: #1) is seen; #2 is dropped → missing==[2].
        body = "1. Verify two flows (AC: #1 — first flow passes) (AC: #2 — second flow passes)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_coverage(path, ac_count=2)

        assert result["valid"] is True
        assert result["covered"] == [1, 2]
        assert result["missing"] == []

    def test_two_objectives_single_citing_covers_non_contiguous(self, tmp_path):
        body = "1. Verify first flow (AC: #1 — first flow)\n2. Verify third flow (AC: #3 — third flow)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_coverage(path, ac_count=3)

        assert result["valid"] is False
        assert result["covered"] == [1, 3]
        assert result["missing"] == [2]


class TestValidateAcCitationsMultiCitation:
    """validate_ac_citations per-objective bucketing with all-citations-examined and reasons list."""

    def test_one_valid_one_invalid_citation_lands_in_invalid(self, tmp_path):
        # RED: current code examines only (AC: #1 — ok), marks objective as cited, misses #99.
        body = "1. Verify dual (AC: #1 — valid) (AC: #99 — out of range)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path, ac_count=5)

        assert result["valid"] is False
        assert result["cited"] == 0
        assert len(result["invalid_citations"]) == 1
        assert result["invalid_citations"][0]["reasons"] == ["out_of_range"]

    def test_two_invalid_citations_collects_both_reasons(self, tmp_path):
        # RED: current code sees only the first citation; the second reason is never collected.
        body = "1. Verify double-bad (AC: #99 — oob) (NFR: bogus — unknown cat)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path, ac_count=5, nfr_categories=["security"])

        assert result["valid"] is False
        assert result["total"] == 1
        assert len(result["invalid_citations"]) == 1
        assert set(result["invalid_citations"][0]["reasons"]) == {"out_of_range", "unknown_nfr_category"}

    def test_two_valid_citations_counted_as_cited(self, tmp_path):
        # Regression: an objective with two valid citations must not be double-counted or lost.
        body = "1. Verify two valid (AC: #1 — first)(AC: #2 — second)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path, ac_count=2)

        assert result["valid"] is True
        assert result["total"] == 1
        assert result["cited"] == 1
        assert result["uncited"] == []
        assert result["invalid_citations"] == []

    def test_presence_only_mode_multi_citation_objective_counts_as_cited(self, tmp_path):
        body = "1. Verify flows (AC: #1 — first) (AC: #2 — second)\n"
        path = write_testplan_with_objectives(tmp_path / "TestPlan.md", body)

        result = validate_ac_citations(path)

        assert result["valid"] is True
        assert result["cited"] == 1
        assert result["invalid_citations"] == []
