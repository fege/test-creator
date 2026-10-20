"""Unit tests for enforce_citation_gate — deterministic override of a wrongly-scored
Scope Fidelity/Specificity when the review agent disagrees with the already-computed
citation/scope/boilerplate checks.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.enforce_citation_gate import (
    apply_score_caps,
    cap_actionability,
    cap_scope_fidelity,
    cap_specificity,
    enforce_citation_gate,
    main,
)
from scripts.filter_for_revision import filter_for_revision
from scripts.utils.frontmatter_utils import read_frontmatter, write_frontmatter_with_body
from scripts.validate_quality_evidence import validate_actionability
from tests.consts.validation_constants import (
    ACTIONABILITY_ADVISORY_RESULT,
    ACTIONABILITY_ADVISORY_GAPS_PLAN,
    ACTIONABILITY_RBAC_WITHOUT_RESOURCE_PLAN,
    ACTIONABILITY_TBD_UNKNOWN_PLAN,
    BOILERPLATE_FIVE_VIOLATIONS,
    BOILERPLATE_THREE_VIOLATIONS,
    INVALID_CITATIONS,
    INVALID_COVERAGE,
    INVALID_ACTIONABILITY,
    INVALID_SCOPE_COVERAGE,
    INVALID_SCOPE_COVERAGE_REVERSE,
    INVALID_SCOPE_CHECK,
    REVIEW_RUBRIC_SCORES_LAYOUT,
    REVIEW_SCORE_TABLE_LAYOUT,
    VALID_ACTIONABILITY,
    VALID_BOILERPLATE,
    VALID_CITATIONS,
    VALID_COVERAGE,
    VALID_SCOPE_COVERAGE,
    VALID_SCOPE_CHECK,
)
from tests.helpers import build_review_payload

ALL_TWOS = {"specificity": 2, "grounding": 2, "scope_fidelity": 2, "actionability": 2, "consistency": 2}


def _write_review(
    path, scores, score=None, verdict="Ready", passed=True, body=None, before_score=None, before_scores=None
):
    data = build_review_payload(
        scores, score=score, verdict=verdict, passed=passed, before_score=before_score, before_scores=before_scores
    )
    return write_frontmatter_with_body(
        path,
        body or "## Rubric Scores\n\n## Section-by-Section Feedback\n\nAll criteria passed — no improvements needed.\n",
        data,
        "test-plan-review",
    )


def _cap_scope_fidelity(scores, ac_citations_result, ac_coverage_result, scope_check_result):
    """Call the public cap with valid required scope-coverage evidence."""
    return cap_scope_fidelity(
        scores,
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        scope_coverage_result=VALID_SCOPE_COVERAGE,
    )


def _apply_score_caps(
    scores,
    ac_citations_result,
    ac_coverage_result,
    scope_check_result,
    boilerplate_result,
    *,
    scope_coverage_result=VALID_SCOPE_COVERAGE,
    actionability_result=VALID_ACTIONABILITY,
):
    """Call the public cap orchestrator with explicit quality evidence defaults."""
    return apply_score_caps(
        scores,
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        boilerplate_result,
        scope_coverage_result=scope_coverage_result,
        actionability_result=actionability_result,
    )


def _enforce_citation_gate(
    feature_dir,
    ac_citations_result,
    ac_coverage_result,
    scope_check_result,
    boilerplate_result,
    *,
    scope_coverage_result=VALID_SCOPE_COVERAGE,
    actionability_result=VALID_ACTIONABILITY,
):
    """Call the persisted gate with valid required quality evidence by default."""
    return enforce_citation_gate(
        feature_dir,
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        boilerplate_result,
        scope_coverage_result=scope_coverage_result,
        actionability_result=actionability_result,
    )


class TestCapScopeFidelity:
    """Pure-function tests for cap_scope_fidelity — no file I/O, shared by enforce_citation_gate
    (which persists the result to TestPlanReview.md) and test-plan-score (which has no review
    file and only needs the corrected numbers to present to the user).
    """

    def test_no_override_when_all_checks_valid(self):
        result = _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)

        assert result == {"overridden": False, "scores": ALL_TWOS}

    def test_omitting_required_scope_coverage_evidence_raises(self):
        with pytest.raises(TypeError, match="scope_coverage_result"):
            cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)

    def test_scope_coverage_failure_caps_scope_fidelity(self):
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=INVALID_SCOPE_COVERAGE,
            actionability_result=VALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        assert result["scores"]["actionability"] == 2

    def test_actionability_evidence_failure_caps_actionability_and_recomputes_verdict(self):
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=VALID_SCOPE_COVERAGE,
            actionability_result=INVALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 2
        assert result["scores"]["actionability"] == 1
        assert result["score"] == 9
        assert result["verdict"] == "Revise"
        assert result["pass"] is True

    def test_reverse_scope_coverage_failure_caps_scope_fidelity(self):
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=INVALID_SCOPE_COVERAGE_REVERSE,
            actionability_result=VALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1

    @pytest.mark.parametrize(
        "scope_coverage_result, actionability_result, expected_error",
        [
            pytest.param(
                {"missing": [], "unmapped_objectives": []},
                VALID_ACTIONABILITY,
                "scope_coverage_result",
                id="scope-coverage-missing-valid",
            ),
            pytest.param(
                VALID_SCOPE_COVERAGE,
                {
                    "valid": False,
                    "bare_tbd": "OpenShift version",
                    "missing_details": [],
                    "advisory_gaps": [],
                },
                "actionability_result",
                id="actionability-bare-tbd-not-list",
            ),
            pytest.param(
                VALID_SCOPE_COVERAGE,
                {"valid": True, "bare_tbd": [], "missing_details": [], "advisory_gaps": "not-a-list"},
                "actionability_result",
                id="actionability-advisory-gaps-not-list",
            ),
        ],
    )
    def test_quality_evidence_is_validated_before_scoring(
        self, scope_coverage_result, actionability_result, expected_error
    ):
        with pytest.raises(ValueError, match=expected_error):
            _apply_score_caps(
                ALL_TWOS,
                VALID_CITATIONS,
                VALID_COVERAGE,
                VALID_SCOPE_CHECK,
                VALID_BOILERPLATE,
                scope_coverage_result=scope_coverage_result,
                actionability_result=actionability_result,
            )

    @pytest.mark.parametrize(
        "scope_coverage_result",
        [
            pytest.param(None, id="missing-required-scope-coverage"),
            pytest.param(
                {"valid": False, "missing": "not-a-list", "unmapped_objectives": []},
                id="scope-coverage-missing-not-list",
            ),
        ],
    )
    def test_scope_coverage_evidence_fails_closed_when_missing_or_malformed(self, scope_coverage_result):
        with pytest.raises(ValueError, match="scope_coverage_result"):
            cap_scope_fidelity(
                ALL_TWOS,
                VALID_CITATIONS,
                VALID_COVERAGE,
                VALID_SCOPE_CHECK,
                scope_coverage_result=scope_coverage_result,
            )

    def test_override_when_citations_invalid(self):
        result = _cap_scope_fidelity(ALL_TWOS, INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        assert result["score"] == 9
        assert result["verdict"] == "Ready"
        assert result["pass"] is True

    def test_override_when_coverage_invalid(self):
        result = _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, INVALID_COVERAGE, VALID_SCOPE_CHECK)

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1

    def test_override_when_scope_check_invalid(self):
        result = _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, INVALID_SCOPE_CHECK)

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1

    def test_already_capped_scope_fidelity_is_left_alone(self):
        scores = {**ALL_TWOS, "scope_fidelity": 1}

        result = _cap_scope_fidelity(scores, INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)

        assert result == {"overridden": False, "scores": scores}

    def test_does_not_mutate_the_input_scores_dict(self):
        scores = dict(ALL_TWOS)
        original = dict(scores)

        _cap_scope_fidelity(scores, INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)

        assert scores == original

    @pytest.mark.parametrize(
        "citations_result,coverage_result",
        [
            pytest.param({"total": 5}, VALID_COVERAGE, id="missing_valid_in_citations"),
            pytest.param(VALID_CITATIONS, {"missing": []}, id="missing_valid_in_coverage"),
            pytest.param({**VALID_CITATIONS, "valid": "false"}, VALID_COVERAGE, id="string_false_in_citations"),
            pytest.param(VALID_CITATIONS, {**VALID_COVERAGE, "valid": "false"}, id="string_false_in_coverage"),
            pytest.param({"valid": False, "uncited": [None]}, VALID_COVERAGE, id="null_entry_in_uncited"),
            pytest.param(
                {"valid": False, "invalid_citations": [None]}, VALID_COVERAGE, id="null_entry_in_invalid_citations"
            ),
            pytest.param({"valid": False, "uncited": "not-a-list"}, VALID_COVERAGE, id="uncited_not_a_list"),
            pytest.param(
                {"valid": False, "invalid_citations": [{"text": "x", "line_number": 1}]},
                VALID_COVERAGE,
                id="invalid_citation_missing_reasons",
            ),
            pytest.param(
                {"valid": False, "invalid_citations": [{"text": "x", "line_number": 1, "reasons": [None]}]},
                VALID_COVERAGE,
                id="null_reasons_element_in_invalid_citations",
            ),
        ],
    )
    def test_malformed_result_raises(self, citations_result, coverage_result):
        with pytest.raises(ValueError):
            _cap_scope_fidelity(ALL_TWOS, citations_result, coverage_result, VALID_SCOPE_CHECK)

    def test_malformed_scope_check_raises(self):
        with pytest.raises(ValueError):
            _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, {"violations": []})

    def test_successful_scope_result_requires_violations_list(self):
        with pytest.raises(ValueError, match="violations"):
            _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, {"valid": True})

    def test_scope_script_error_surfaces_payload_error(self):
        with pytest.raises(ValueError, match="Core checks directory not found"):
            _cap_scope_fidelity(
                ALL_TWOS,
                VALID_CITATIONS,
                VALID_COVERAGE,
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
            )

    def test_empty_violations_list_is_accepted_for_capping(self):
        result = _cap_scope_fidelity(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, {"valid": True, "violations": []})

        assert result == {"overridden": False, "scores": ALL_TWOS}

    @pytest.mark.parametrize(
        "invalid_scores",
        [
            pytest.param({"specificity": 2, "grounding": 2, "scope_fidelity": 2, "actionability": 2}, id="missing_key"),
            pytest.param(
                {
                    "specificity": 2,
                    "grounding": 2,
                    "scope_fidelity": 2,
                    "actionability": 2,
                    "consistency": 2,
                    "extra": 1,
                },
                id="extra_key",
            ),
            pytest.param(
                {"specificity": 2, "grounding": True, "scope_fidelity": 2, "actionability": 2, "consistency": 2},
                id="bool_value",
            ),
            pytest.param(
                {"specificity": 2, "grounding": "2", "scope_fidelity": 2, "actionability": 2, "consistency": 2},
                id="str_value",
            ),
            pytest.param(
                {"specificity": 3, "grounding": 2, "scope_fidelity": 2, "actionability": 2, "consistency": 2},
                id="out_of_range_high",
            ),
            pytest.param(
                {"specificity": -1, "grounding": 2, "scope_fidelity": 2, "actionability": 2, "consistency": 2},
                id="out_of_range_low",
            ),
        ],
    )
    def test_invalid_scores_raises(self, invalid_scores):
        with pytest.raises(ValueError):
            _cap_scope_fidelity(invalid_scores, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK)


class TestCapSpecificity:
    """Pure-function tests for cap_specificity — mirrors TestCapScopeFidelity's shape."""

    def test_no_override_when_no_violations(self):
        result = cap_specificity(ALL_TWOS, VALID_BOILERPLATE)

        assert result == {"overridden": False, "scores": ALL_TWOS}

    def test_override_caps_to_one_at_three_violations(self):
        result = cap_specificity(ALL_TWOS, BOILERPLATE_THREE_VIOLATIONS)

        assert result["overridden"] is True
        assert result["scores"]["specificity"] == 1
        assert result["score"] == 9

    def test_override_caps_to_zero_at_five_violations(self):
        result = cap_specificity(ALL_TWOS, BOILERPLATE_FIVE_VIOLATIONS)

        assert result["overridden"] is True
        assert result["scores"]["specificity"] == 0
        assert result["score"] == 8

    def test_already_capped_specificity_is_left_alone(self):
        scores = {**ALL_TWOS, "specificity": 0}

        result = cap_specificity(scores, BOILERPLATE_FIVE_VIOLATIONS)

        assert result == {"overridden": False, "scores": scores}

    def test_does_not_mutate_the_input_scores_dict(self):
        scores = dict(ALL_TWOS)
        original = dict(scores)

        cap_specificity(scores, BOILERPLATE_FIVE_VIOLATIONS)

        assert scores == original

    @pytest.mark.parametrize(
        "boilerplate_result",
        [
            pytest.param({"total_violations": 3}, id="missing_valid_field"),
            pytest.param({"valid": False, "total_violations": "many"}, id="non_integer_total"),
            pytest.param({"valid": False, "total_violations": True}, id="bool_total"),
            pytest.param({"valid": True, "by_section": {}}, id="success_missing_total"),
            pytest.param({"valid": True, "total_violations": True, "by_section": {}}, id="success_bool_total"),
            pytest.param(
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
                id="error_shaped_no_total",
            ),
        ],
    )
    def test_malformed_boilerplate_result_raises(self, boilerplate_result):
        with pytest.raises(ValueError):
            cap_specificity(ALL_TWOS, boilerplate_result)


class TestCapActionability:
    """Pure-function tests for blocking actionability caps and valid-score preservation."""

    @pytest.mark.parametrize("score", (0, 1), ids=("score-zero", "score-one"))
    @pytest.mark.parametrize(
        "actionability_result",
        (
            pytest.param(ACTIONABILITY_ADVISORY_RESULT, id="advisory-only"),
            pytest.param(VALID_ACTIONABILITY, id="valid-concrete"),
        ),
    )
    def test_valid_actionability_preserves_scorer_score_without_override(self, score, actionability_result):
        scores = {**ALL_TWOS, "actionability": score}

        result = cap_actionability(scores, actionability_result)

        assert result == {"overridden": False, "scores": scores}

    def test_blocking_actionability_caps_score_above_one_to_one(self):
        result = cap_actionability(ALL_TWOS, INVALID_ACTIONABILITY)

        assert result["overridden"] is True
        assert result["scores"]["actionability"] == 1
        assert result["actionability_capped"] is True


class TestApplyScoreCaps:
    """Tests for the orchestrator combining both caps — the composition, not each cap alone."""

    def test_no_override_when_everything_valid(self):
        result = _apply_score_caps(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        assert result == {"overridden": False, "scores": ALL_TWOS}

    def test_advisory_actionability_gaps_do_not_cap_stateless_scores(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ADVISORY_GAPS_PLAN)
        actionability_result = validate_actionability(str(plan))

        assert actionability_result["valid"] is True
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=actionability_result,
        )

        assert result == {"overridden": False, "scores": ALL_TWOS}

    @pytest.mark.parametrize(
        "plan_content, evidence_key, expected_evidence",
        (
            pytest.param(ACTIONABILITY_TBD_UNKNOWN_PLAN, "bare_tbd", "OpenShift version", id="bare-tbd"),
            pytest.param(
                ACTIONABILITY_RBAC_WITHOUT_RESOURCE_PLAN,
                "missing_details",
                "RBAC roles and permissions",
                id="unusable-rbac",
            ),
        ),
    )
    def test_blocking_actionability_gaps_still_cap_stateless_scores(
        self, tmp_path, plan_content, evidence_key, expected_evidence
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)
        actionability_result = validate_actionability(str(plan))

        assert actionability_result["valid"] is False
        assert actionability_result["advisory_gaps"] == []
        assert expected_evidence in actionability_result[evidence_key]
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=actionability_result,
        )

        assert result["overridden"] is True
        assert result["scores"]["actionability"] == 1
        assert result["score"] == 9
        assert result["verdict"] == "Revise"
        assert result["actionability_capped"] is True

    def test_omitting_required_quality_evidence_raises(self):
        with pytest.raises(TypeError, match="scope_coverage_result"):
            apply_score_caps(ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

    def test_valid_scope_coverage_and_actionability_do_not_override(self):
        result = _apply_score_caps(
            ALL_TWOS,
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=VALID_SCOPE_COVERAGE,
            actionability_result=VALID_ACTIONABILITY,
        )

        assert result == {"overridden": False, "scores": ALL_TWOS}

    def test_only_scope_fidelity_capped(self):
        result = _apply_score_caps(ALL_TWOS, INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        assert result["overridden"] is True
        assert result["scope_fidelity_capped"] is True
        assert result["specificity_capped"] is False
        assert result["scores"]["scope_fidelity"] == 1
        assert result["scores"]["specificity"] == 2

    def test_only_specificity_capped(self):
        result = _apply_score_caps(
            ALL_TWOS, VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        assert result["overridden"] is True
        assert result["scope_fidelity_capped"] is False
        assert result["specificity_capped"] is True
        assert result["scores"]["specificity"] == 0
        assert result["scores"]["scope_fidelity"] == 2

    def test_both_capped_score_reflects_both_corrections(self):
        result = _apply_score_caps(
            ALL_TWOS, INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        assert result["overridden"] is True
        assert result["scope_fidelity_capped"] is True
        assert result["specificity_capped"] is True
        assert result["scores"] == {
            "specificity": 0,
            "grounding": 2,
            "scope_fidelity": 1,
            "actionability": 2,
            "consistency": 2,
        }
        assert result["score"] == 7
        assert result["verdict"] == "Rework"
        assert result["pass"] is False


class TestEnforceCitationGate:
    def test_omitting_required_quality_evidence_raises(self, tmp_path):
        with pytest.raises(TypeError, match="scope_coverage_result"):
            enforce_citation_gate(str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

    def test_valid_citations_no_override(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result == {"overridden": False}
        data, _ = read_frontmatter(review)
        assert data["scores"]["scope_fidelity"] == 2
        assert data["score"] == 10

    def test_invalid_citations_caps_scope_fidelity_and_recomputes_score(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", passed=True)

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        assert result["score"] == 9
        assert result["verdict"] == "Ready"  # 9 >= 8 and no criterion is 0
        assert result["pass"] is True

        data, _ = read_frontmatter(review)
        assert data["scores"]["scope_fidelity"] == 1
        assert data["score"] == 9

    def test_invalid_scope_check_caps_scope_fidelity(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, INVALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        data, _ = read_frontmatter(review)
        assert data["scores"]["scope_fidelity"] == 1

    def test_boilerplate_caps_specificity(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        assert result["overridden"] is True
        assert result["scores"]["specificity"] == 0
        assert result["scores"]["scope_fidelity"] == 2  # untouched
        data, _ = read_frontmatter(review)
        assert data["scores"]["specificity"] == 0

    def test_override_injects_feedback_note_with_citation_specifics(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, INVALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        body = Path(review).read_text()
        assert "## Section-by-Section Feedback" in body
        assert "Line 79" in body  # uncited objective
        assert "Line 82" in body  # invalid citation
        assert "out_of_range" in body
        assert "[2, 3, 4, 5]" in body  # missing AC numbers from coverage

    def test_override_injects_feedback_note_with_scope_check_specifics(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        _enforce_citation_gate(str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, INVALID_SCOPE_CHECK, VALID_BOILERPLATE)

        body = Path(review).read_text()
        assert "Unit Testing" in body
        assert "Section 2.1" in body

    def test_override_injects_feedback_note_with_boilerplate_specifics(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        body = Path(review).read_text()
        assert "works as expected" in body
        assert "Specificity was capped" in body

    def test_both_corrections_produce_both_feedback_sections(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        body = Path(review).read_text()
        assert "Scope Fidelity was" in body
        assert "Specificity was capped" in body

    def test_note_building_failure_leaves_no_partial_update(self, tmp_path):
        # The note is built from the same untrusted results already validated up front, but this
        # proves the *ordering* independent of what validation does or doesn't catch: if building
        # the note ever fails, the frontmatter must not have been written already.
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)
        original_body = Path(review).read_text()

        with patch("scripts.enforce_citation_gate._build_feedback_note", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                _enforce_citation_gate(
                    str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
                )

        data, _ = read_frontmatter(review)
        assert data == original_data
        assert Path(review).read_text() == original_body

    def test_valid_citations_do_not_touch_body(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_body = Path(review).read_text()

        _enforce_citation_gate(str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        assert Path(review).read_text() == original_body

    def test_invalid_ac_coverage_alone_also_triggers_override(self, tmp_path):
        _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, INVALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1

    def test_scope_coverage_failure_persists_correction_and_missing_item_feedback(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=INVALID_SCOPE_COVERAGE,
            actionability_result=VALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        data, _ = read_frontmatter(review)
        assert data["scores"]["scope_fidelity"] == 1
        body = Path(review).read_text()
        assert "Optional description and tags" in body

    def test_reverse_scope_coverage_failure_persists_orphan_objective_feedback(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=INVALID_SCOPE_COVERAGE_REVERSE,
            actionability_result=VALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["scope_fidelity"] == 1
        body = Path(review).read_text()
        assert "Verify an invented deliverable" in body

    def test_actionability_failure_persists_correction_and_missing_detail_feedback(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            scope_coverage_result=VALID_SCOPE_COVERAGE,
            actionability_result=INVALID_ACTIONABILITY,
        )

        assert result["overridden"] is True
        assert result["scores"]["actionability"] == 1
        assert result["score"] == 9
        assert result["verdict"] == "Revise"
        data, _ = read_frontmatter(review)
        assert data["scores"]["actionability"] == 1
        body = Path(review).read_text()
        assert "OpenShift version" in body
        assert "RBAC roles and permissions" in body

    def test_blocking_actionability_does_not_recap_already_capped_score(self, tmp_path):
        scores = {**ALL_TWOS, "actionability": 1}
        review = _write_review(tmp_path / "TestPlanReview.md", scores, score=9, verdict="Revise", passed=True)
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_TBD_UNKNOWN_PLAN)
        actionability_result = validate_actionability(str(plan))

        assert actionability_result["valid"] is False
        assert actionability_result["bare_tbd"]
        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=actionability_result,
        )

        assert result["overridden"] is False
        assert result.get("actionability_capped", False) is False
        data, _ = read_frontmatter(review)
        assert data["scores"]["actionability"] == 1
        assert sum(data["scores"].values()) == 9
        assert data["score"] == 9
        assert all(score > 0 for score in data["scores"].values())
        assert data["verdict"] == "Revise"
        assert data["pass"] is True

    def test_advisory_actionability_gaps_do_not_cap_persisted_score(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", passed=True)
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ADVISORY_GAPS_PLAN)
        actionability_result = validate_actionability(str(plan))

        assert actionability_result["valid"] is True
        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=actionability_result,
        )

        assert result == {"overridden": False}
        data, _ = read_frontmatter(review)
        assert data["scores"]["actionability"] == 2
        assert data["score"] == 10
        assert filter_for_revision(str(tmp_path)) == "SKIP"

    def test_advisory_actionability_preserves_persisted_score_one(self, tmp_path):
        scores = {**ALL_TWOS, "actionability": 1}
        review = _write_review(
            tmp_path / "TestPlanReview.md",
            scores,
            score=9,
            verdict="Revise",
            passed=True,
            before_score=9,
            before_scores=dict(scores),
        )
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ADVISORY_GAPS_PLAN)
        actionability_result = validate_actionability(str(plan))

        assert actionability_result["valid"] is True
        assert actionability_result["advisory_gaps"]
        result = _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=actionability_result,
        )

        assert result == {"overridden": False}
        data, _ = read_frontmatter(review)
        assert data["scores"] == scores
        assert data["score"] == 9
        assert data["verdict"] == "Revise"
        assert data["before_score"] == 9
        assert data["before_scores"] == scores
        assert filter_for_revision(str(tmp_path)) == "REVISE"
        assert "Actionability was capped" not in Path(review).read_text()

    def test_override_recomputes_score_and_verdict_without_actionability_normalization(self, tmp_path):
        # The resulting scores are specificity=2, grounding=2, scope_fidelity=1, actionability=1,
        # consistency=1 -> total 7, and the recomputed verdict is Revise.
        scores = {"specificity": 2, "grounding": 2, "scope_fidelity": 2, "actionability": 1, "consistency": 1}
        review = _write_review(tmp_path / "TestPlanReview.md", scores, score=8, verdict="Revise", passed=True)

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["scores"] == {
            "specificity": 2,
            "grounding": 2,
            "scope_fidelity": 1,
            "actionability": 1,
            "consistency": 1,
        }
        assert result["score"] == 7
        assert result["verdict"] == "Revise"
        assert result["pass"] is True

        data, _ = read_frontmatter(review)
        assert data["scores"] == result["scores"]
        assert data["score"] == 7
        assert data["verdict"] == "Revise"
        assert data["pass"] is True

    def test_override_can_flip_verdict_from_ready_to_revise(self, tmp_path):
        # specificity=1, grounding=1, scope_fidelity=2, actionability=2, consistency=2 -> tot 8, no
        # zero, actionability=2 -> starting verdict is genuinely Ready. A defect that caps
        # scope_fidelity but never recalls compute_verdict_and_pass would leave verdict="Ready"
        # here, unlike the preceding test, which must preserve actionability=1 while
        # recalculating the verdict after the Scope Fidelity cap.
        scores = {"specificity": 1, "grounding": 1, "scope_fidelity": 2, "actionability": 2, "consistency": 2}
        _write_review(tmp_path / "TestPlanReview.md", scores, score=8, verdict="Ready", passed=True)

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["scores"]["scope_fidelity"] == 1
        assert result["score"] == 7
        assert result["verdict"] == "Revise"
        assert result["pass"] is True

    def test_override_can_flip_verdict_to_rework_below_seven(self, tmp_path):
        # specificity=1, grounding=1, scope_fidelity=2, actionability=2, consistency=1 -> total 7 (Revise)
        scores = {"specificity": 1, "grounding": 1, "scope_fidelity": 2, "actionability": 2, "consistency": 1}
        _write_review(tmp_path / "TestPlanReview.md", scores, score=7, verdict="Revise", passed=True)

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["scores"]["scope_fidelity"] == 1
        assert result["score"] == 6
        assert result["verdict"] == "Rework"
        assert result["pass"] is False

    def test_already_capped_scope_fidelity_is_left_alone(self, tmp_path):
        scores = {**ALL_TWOS, "scope_fidelity": 1}
        review = _write_review(tmp_path / "TestPlanReview.md", scores, score=9, verdict="Ready", passed=True)

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result == {"overridden": False}
        data, _ = read_frontmatter(review)
        assert data["score"] == 9  # untouched

    def test_missing_review_file_returns_none(self, tmp_path):
        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result is None

    def test_first_pass_before_score_mirroring_current_score_is_corrected_too(self, tmp_path):
        review = _write_review(
            tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, before_score=10, before_scores=dict(ALL_TWOS)
        )

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["score"] == 9
        data, _ = read_frontmatter(review)
        assert data["before_score"] == 9
        assert data["before_scores"]["scope_fidelity"] == 1

    def test_first_pass_before_scores_corrects_specificity_too(self, tmp_path):
        review = _write_review(
            tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, before_score=10, before_scores=dict(ALL_TWOS)
        )

        _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        data, _ = read_frontmatter(review)
        assert data["before_scores"]["specificity"] == 0

    def test_genuine_prior_cycle_before_score_is_left_alone(self, tmp_path):
        # before_score differs from score -> it's a real baseline from an earlier revision
        # cycle, not a same-pass mirror. Must not be touched.
        review = _write_review(
            tmp_path / "TestPlanReview.md",
            ALL_TWOS,
            score=10,
            before_score=7,
            before_scores={"specificity": 1, "grounding": 1, "scope_fidelity": 2, "actionability": 2, "consistency": 1},
        )

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        data, _ = read_frontmatter(review)
        assert data["before_score"] == 7
        assert data["before_scores"]["scope_fidelity"] == 2  # untouched

    def test_missing_feedback_heading_still_overrides_frontmatter(self, tmp_path):
        # If the review agent's body doesn't match the expected shape, the score correction
        # (the part that actually drives filter_for_revision) must still apply.
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, body="## Rubric Scores\n")

        result = _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result["overridden"] is True
        data, body = read_frontmatter(review)
        assert data["scores"]["scope_fidelity"] == 1
        # The correction rationale must not be silently dropped when the heading is absent.
        assert "## Section-by-Section Feedback" in body
        assert "Scope Fidelity was capped" in body


LAYOUT_PARAMS = [
    pytest.param(REVIEW_RUBRIC_SCORES_LAYOUT, id="rubric-scores"),
    pytest.param(REVIEW_SCORE_TABLE_LAYOUT, id="score-table"),
]


class TestEnforceCitationGateSyncsReviewBody:
    """A capped score must read the same in the frontmatter and in the score section of the review
    (criterion row, Total row, and `Total: N/10 — Verdict: X` line), for both documented layouts.
    """

    @pytest.mark.parametrize("layout", LAYOUT_PARAMS)
    def test_citation_cap_syncs_row_and_total_and_surfaces_note(self, tmp_path, layout):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", body=layout)

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        data, body = read_frontmatter(review)
        assert data["score"] == 9
        assert data["scores"]["scope_fidelity"] == 1
        assert data["verdict"] == "Ready"
        assert "| Scope Fidelity | 1/2 |" in body
        assert "| Specificity | 2/2 |" in body  # uncapped rows untouched
        assert "Total: 9/10 — Verdict: Ready" in body
        assert "10/10" not in body
        # The note is present even though the layouts have no feedback heading, and sits after the
        # score section rather than after the Revision History.
        assert body.count("## Section-by-Section Feedback") == 1
        assert (
            body.index("Scope Fidelity | 1/2")
            < body.index("Scope Fidelity was capped")
            < body.index("## Revision History")
        )

    @pytest.mark.parametrize("layout", LAYOUT_PARAMS)
    def test_verdict_change_rewrites_total_line(self, tmp_path, layout):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", body=layout)

        _enforce_citation_gate(
            str(tmp_path),
            VALID_CITATIONS,
            VALID_COVERAGE,
            VALID_SCOPE_CHECK,
            VALID_BOILERPLATE,
            actionability_result=INVALID_ACTIONABILITY,
        )

        data, body = read_frontmatter(review)
        assert data["verdict"] == "Revise"
        assert "| Actionability | 1/2 |" in body
        assert "Total: 9/10 — Verdict: Revise" in body
        assert "Verdict: Ready" not in body

    @pytest.mark.parametrize("layout", LAYOUT_PARAMS)
    def test_multiple_caps_sync_every_changed_row(self, tmp_path, layout):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", body=layout)

        _enforce_citation_gate(
            str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, BOILERPLATE_FIVE_VIOLATIONS
        )

        data, body = read_frontmatter(review)
        assert data["score"] == 7
        assert data["verdict"] == "Rework"
        assert "| Scope Fidelity | 1/2 |" in body
        assert "| Specificity | 0/2 |" in body
        assert "Total: 7/10 — Verdict: Rework" in body
        assert "10/10" not in body

    @pytest.mark.parametrize("layout", LAYOUT_PARAMS)
    def test_text_outside_score_section_is_preserved(self, tmp_path, layout):
        layout = layout.replace(
            "## Revision History",
            "## Evidence\n\nThe strategy requires a 10/10 success rate.\n\n"
            "## Revision History\n\n| Criterion | Score |\n|---|---|\n| Scope Fidelity | 2/2 |\n"
            "| **Total** | **10/10** |\n\n**Total: 10/10 — Verdict: Ready**\n",
        )
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", body=layout)

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        _, body = read_frontmatter(review)
        assert "| Scope Fidelity | 1/2 |" in body
        assert "The strategy requires a 10/10 success rate." in body
        assert "| Scope Fidelity | 2/2 |\n| **Total** | **10/10** |\n\n**Total: 10/10 — Verdict: Ready**\n" in body

    @pytest.mark.parametrize(
        ("total_cell", "expected_cell"),
        [pytest.param("10/10", "9/10", id="plain"), pytest.param("**10/10**", "**9/10**", id="bold")],
    )
    def test_total_row_cell_is_synced(self, tmp_path, total_cell, expected_cell):
        layout = REVIEW_SCORE_TABLE_LAYOUT.replace("| **Total** | **10/10** |", f"| Total | {total_cell} |")
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, body=layout)

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        _, body = read_frontmatter(review)
        assert f"| Total | {expected_cell} |" in body

    def test_existing_feedback_heading_receives_note_without_duplication(self, tmp_path):
        layout = REVIEW_RUBRIC_SCORES_LAYOUT.replace(
            "## Revision History", "## Section-by-Section Feedback\n\nAll criteria passed.\n\n## Revision History"
        )
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, body=layout)

        _enforce_citation_gate(str(tmp_path), INVALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE)

        _, body = read_frontmatter(review)
        assert body.count("## Section-by-Section Feedback") == 1
        assert body.index("## Section-by-Section Feedback") < body.index("Scope Fidelity was capped")
        assert "Total: 9/10 — Verdict: Ready" in body

    @pytest.mark.parametrize("layout", LAYOUT_PARAMS)
    def test_no_cap_leaves_body_byte_identical(self, tmp_path, layout):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, body=layout)
        original = Path(review).read_text()

        result = _enforce_citation_gate(
            str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, VALID_BOILERPLATE
        )

        assert result == {"overridden": False}
        assert Path(review).read_text() == original


class TestEnforceCitationGateFailsClosedOnMalformedResults:
    """A malformed ac_citations_result/ac_coverage_result/scope_check_result/boilerplate_result
    must reject outright — never silently default a missing/wrong-typed `valid` field to True.
    `"valid": "false"` is the sharpest case: it's a non-empty string, so Python truthiness alone
    would treat it as truthy/OK.
    """

    @pytest.mark.parametrize(
        "citations_result,coverage_result",
        [
            pytest.param({"total": 5}, VALID_COVERAGE, id="missing_valid_in_citations"),
            pytest.param(VALID_CITATIONS, {"missing": []}, id="missing_valid_in_coverage"),
            pytest.param({**VALID_CITATIONS, "valid": "false"}, VALID_COVERAGE, id="string_false_in_citations"),
            pytest.param(VALID_CITATIONS, {**VALID_COVERAGE, "valid": "false"}, id="string_false_in_coverage"),
            pytest.param("not-a-dict", VALID_COVERAGE, id="citations_not_a_dict"),
            pytest.param(VALID_CITATIONS, "not-a-dict", id="coverage_not_a_dict"),
            pytest.param({"valid": False, "uncited": [None]}, VALID_COVERAGE, id="null_entry_in_uncited"),
            pytest.param(
                {"valid": False, "invalid_citations": [None]}, VALID_COVERAGE, id="null_entry_in_invalid_citations"
            ),
            pytest.param({"valid": False, "uncited": "not-a-list"}, VALID_COVERAGE, id="uncited_not_a_list"),
            pytest.param(
                {"valid": False, "invalid_citations": [{"text": "x", "line_number": 1}]},
                VALID_COVERAGE,
                id="invalid_citation_missing_reasons",
            ),
            pytest.param(
                {"valid": False, "invalid_citations": [{"text": "x", "line_number": 1, "reasons": [None]}]},
                VALID_COVERAGE,
                id="null_reasons_element_in_invalid_citations",
            ),
        ],
    )
    def test_malformed_result_raises_and_does_not_touch_review(self, tmp_path, citations_result, coverage_result):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError):
            _enforce_citation_gate(
                str(tmp_path), citations_result, coverage_result, VALID_SCOPE_CHECK, VALID_BOILERPLATE
            )

        data, _ = read_frontmatter(review)
        assert data == original_data  # rejected before touching the review

    @pytest.mark.parametrize(
        "scope_coverage_result, actionability_result, expected_error",
        [
            pytest.param(
                {"valid": True, "missing": [], "unmapped_objectives": []},
                {
                    "valid": False,
                    "bare_tbd": "OpenShift version",
                    "missing_details": [],
                    "advisory_gaps": [],
                },
                "actionability_result",
                id="actionability-bare-tbd-not-list",
            ),
            pytest.param(
                {"valid": False, "missing": [], "unmapped_objectives": "not-a-list"},
                VALID_ACTIONABILITY,
                "scope_coverage_result",
                id="scope-coverage-unmapped-objectives-not-list",
            ),
        ],
    )
    def test_malformed_quality_evidence_raises_and_does_not_touch_review(
        self, tmp_path, scope_coverage_result, actionability_result, expected_error
    ):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError, match=expected_error):
            _enforce_citation_gate(
                str(tmp_path),
                VALID_CITATIONS,
                VALID_COVERAGE,
                VALID_SCOPE_CHECK,
                VALID_BOILERPLATE,
                scope_coverage_result=scope_coverage_result,
                actionability_result=actionability_result,
            )

        data, _ = read_frontmatter(review)
        assert data == original_data

    def test_malformed_scope_check_raises_and_does_not_touch_review(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError):
            _enforce_citation_gate(
                str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, {"violations": []}, VALID_BOILERPLATE
            )

        data, _ = read_frontmatter(review)
        assert data == original_data

    def test_scope_script_error_raises_and_does_not_touch_review(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError, match="Core checks directory not found"):
            _enforce_citation_gate(
                str(tmp_path),
                VALID_CITATIONS,
                VALID_COVERAGE,
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
                VALID_BOILERPLATE,
            )

        data, _ = read_frontmatter(review)
        assert data == original_data

    @pytest.mark.parametrize(
        "boilerplate_result",
        [
            pytest.param({"valid": False}, id="valid_false_without_total"),
            pytest.param(
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
                id="error_shaped_payload",
            ),
            pytest.param({"valid": True, "by_section": {}}, id="success_missing_total"),
            pytest.param({"valid": True, "total_violations": True, "by_section": {}}, id="success_bool_total"),
        ],
    )
    def test_malformed_boilerplate_raises_and_does_not_touch_review(self, tmp_path, boilerplate_result):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError):
            _enforce_citation_gate(
                str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, VALID_SCOPE_CHECK, boilerplate_result
            )

        data, _ = read_frontmatter(review)
        assert data == original_data

    def test_scope_missing_violations_list_raises_and_does_not_touch_review(self, tmp_path):
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError, match="violations"):
            _enforce_citation_gate(str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, {"valid": True}, VALID_BOILERPLATE)

        data, _ = read_frontmatter(review)
        assert data == original_data

    @pytest.mark.parametrize(
        "scope_check_result, boilerplate_result, expected_match",
        [
            pytest.param(
                {"valid": False, "violations": [{"bad": "shape"}]},
                VALID_BOILERPLATE,
                "violations entries must be objects",
                id="violations_entry_missing_required_field",
            ),
            pytest.param(
                VALID_SCOPE_CHECK,
                {"valid": False, "total_violations": 1, "by_section": {"1.3": [{"bad": "shape"}]}},
                "by_section.1.3 entries must be objects",
                id="by_section_entry_missing_required_field",
            ),
            pytest.param(
                VALID_SCOPE_CHECK,
                {"valid": False, "total_violations": 1, "by_section": "not-a-dict"},
                "by_section must be an object",
                id="by_section_not_a_dict",
            ),
        ],
    )
    def test_malformed_entry_shape_raises_before_write(
        self, tmp_path, scope_check_result, boilerplate_result, expected_match
    ):
        """A violations/by_section entry missing line/matched_pattern/context must reject
        outright — it would otherwise raise a KeyError mid-_build_feedback_note, after the score
        override already wrote to TestPlanReview.md.
        """
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_data, _ = read_frontmatter(review)

        with pytest.raises(ValueError, match=expected_match):
            _enforce_citation_gate(
                str(tmp_path), VALID_CITATIONS, VALID_COVERAGE, scope_check_result, boilerplate_result
            )

        data, _ = read_frontmatter(review)
        assert data == original_data


class TestEnforceCitationGateCLI:
    """CLI-level tests for main() — exercises JSON parsing and ValidationError handling."""

    def _argv(self, feature_dir, **overrides):
        payloads = {
            "--ac-citations-result": json.dumps(VALID_CITATIONS),
            "--ac-coverage-result": json.dumps(VALID_COVERAGE),
            "--scope-check-result": json.dumps(VALID_SCOPE_CHECK),
            "--boilerplate-result": json.dumps(VALID_BOILERPLATE),
            "--scope-coverage-result": json.dumps(VALID_SCOPE_COVERAGE),
            "--actionability-result": json.dumps(VALID_ACTIONABILITY),
        }
        payloads.update(overrides)
        argv = ["enforce_citation_gate.py", str(feature_dir)]
        for flag, value in payloads.items():
            argv.extend([flag, value])
        return argv

    def _run_main(self, argv):
        old_argv = sys.argv
        try:
            sys.argv = argv
            try:
                main()
            except SystemExit as exc:
                assert exc.code == 0
            else:
                raise AssertionError("main() must exit with code 0")
        finally:
            sys.argv = old_argv

    def test_malformed_ac_citations_json_exits_zero_with_stderr_diagnostic(self, tmp_path, capsys):
        self._run_main(self._argv(tmp_path, **{"--ac-citations-result": "NOT-VALID-JSON{{{"}))

        captured = capsys.readouterr()
        assert "malformed --ac-citations-result JSON" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert "malformed --ac-citations-result JSON" in output["error"]

    def test_malformed_ac_coverage_json_exits_zero_with_stderr_diagnostic(self, tmp_path, capsys):
        self._run_main(self._argv(tmp_path, **{"--ac-coverage-result": "%%%bad%%%"}))

        captured = capsys.readouterr()
        assert "malformed --ac-coverage-result JSON" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert "malformed --ac-coverage-result JSON" in output["error"]

    def test_malformed_scope_check_json_exits_zero_with_stderr_diagnostic(self, tmp_path, capsys):
        self._run_main(self._argv(tmp_path, **{"--scope-check-result": "NOT-JSON"}))

        captured = capsys.readouterr()
        assert "malformed --scope-check-result JSON" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"

    def test_malformed_boilerplate_json_exits_zero_with_stderr_diagnostic(self, tmp_path, capsys):
        self._run_main(self._argv(tmp_path, **{"--boilerplate-result": "NOT-JSON"}))

        captured = capsys.readouterr()
        assert "malformed --boilerplate-result JSON" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"

    @pytest.mark.parametrize("missing_flag", ("--scope-coverage-result", "--actionability-result"))
    def test_missing_quality_evidence_result_is_a_structured_error(self, tmp_path, capsys, missing_flag):
        argv = self._argv(tmp_path)
        flag_index = argv.index(missing_flag)
        del argv[flag_index : flag_index + 2]

        self._run_main(argv)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert missing_flag in output["error"]
        assert missing_flag in captured.err

    @pytest.mark.parametrize(
        "citations_payload,coverage_payload,bad_flag",
        [
            pytest.param({"total": 5}, VALID_COVERAGE, "--ac-citations-result", id="citations_missing_valid"),
            pytest.param(
                VALID_CITATIONS,
                {**VALID_COVERAGE, "valid": "false"},
                "--ac-coverage-result",
                id="coverage_string_false",
            ),
        ],
    )
    def test_malformed_valid_field_exits_zero_with_stderr_diagnostic(
        self, tmp_path, capsys, citations_payload, coverage_payload, bad_flag
    ):
        self._run_main(
            self._argv(
                tmp_path,
                **{
                    "--ac-citations-result": json.dumps(citations_payload),
                    "--ac-coverage-result": json.dumps(coverage_payload),
                },
            )
        )

        captured = capsys.readouterr()
        assert bad_flag in captured.err
        assert "valid" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert bad_flag in output["error"]
        assert "valid" in output["error"]

    def test_invalid_review_frontmatter_exits_zero_with_stderr_diagnostic(self, tmp_path, capsys):
        # Write a TestPlanReview.md whose frontmatter violates the schema:
        # score=99 is out of range (max 10) and doesn't match sum of scores.
        review_path = tmp_path / "TestPlanReview.md"
        review_path.write_text(
            "---\n"
            "feature: Test\n"
            "source_key: RHAISTRAT-1\n"
            "score: 99\n"
            "pass: true\n"
            "verdict: Ready\n"
            "scores:\n"
            "  specificity: 2\n"
            "  grounding: 2\n"
            "  scope_fidelity: 2\n"
            "  actionability: 2\n"
            "  consistency: 2\n"
            "auto_revised: false\n"
            "last_updated: '2026-08-06'\n"
            "---\n"
            "## Rubric Scores\n"
        )
        self._run_main(self._argv(tmp_path, **{"--ac-citations-result": json.dumps(INVALID_CITATIONS)}))

        captured = capsys.readouterr()
        assert "invalid TestPlanReview.md" in captured.err
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert "invalid TestPlanReview.md" in output["error"]

    def test_happy_path_override_prints_overridden_status_to_stdout(self, tmp_path, capsys):
        _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", passed=True)

        self._run_main(self._argv(tmp_path, **{"--ac-citations-result": json.dumps(INVALID_CITATIONS)}))

        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "overridden"
        assert output["scores"]["scope_fidelity"] == 1
        assert output["score"] == 9
        assert output["verdict"] == "Ready"
        assert output["pass"] is True

    def test_no_override_needed_prints_ok_status_to_stdout(self, tmp_path, capsys):
        _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", passed=True)

        self._run_main(self._argv(tmp_path))

        assert json.loads(capsys.readouterr().out) == {"status": "ok"}

    def test_missing_review_file_prints_skip_status_to_stdout(self, tmp_path, capsys):
        self._run_main(self._argv(tmp_path))

        assert json.loads(capsys.readouterr().out) == {"status": "skip"}

    @pytest.mark.parametrize(
        "flag, payload, error_clue",
        [
            pytest.param(
                "--boilerplate-result",
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
                "Core checks directory not found: /tmp/nonexistent_checks/core",
                id="boilerplate_error_shaped",
            ),
            pytest.param(
                "--boilerplate-result",
                {"valid": True, "by_section": {}},
                "total_violations",
                id="boilerplate_missing_total_violations",
            ),
            pytest.param(
                "--boilerplate-result",
                {"valid": True, "total_violations": True, "by_section": {}},
                "total_violations",
                id="boilerplate_bool_total_violations",
            ),
            pytest.param(
                "--scope-check-result",
                {"valid": True},
                "violations",
                id="scope_missing_violations_list",
            ),
            pytest.param(
                "--scope-check-result",
                {"valid": False, "error": "Core checks directory not found: /tmp/nonexistent_checks/core"},
                "Core checks directory not found: /tmp/nonexistent_checks/core",
                id="scope_error_shaped",
            ),
            pytest.param(
                "--scope-coverage-result",
                {"valid": False, "missing": [], "unmapped_objectives": "not-a-list"},
                "--scope-coverage-result.unmapped_objectives must be a list",
                id="scope-coverage-unmapped-objectives-not-list",
            ),
            pytest.param(
                "--actionability-result",
                {
                    "valid": False,
                    "bare_tbd": "OpenShift version",
                    "missing_details": [],
                    "advisory_gaps": [],
                },
                "--actionability-result.bare_tbd must be a list of non-empty strings",
                id="actionability-bare-tbd-not-list",
            ),
        ],
    )
    def test_check_tool_payload_errors_are_not_blamed_on_review_file(self, tmp_path, capsys, flag, payload, error_clue):
        """Script/config failures and missing cap fields are gate status:error — not a corrupt
        TestPlanReview.md. The review file must be left untouched.
        """
        review = _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)
        original_text = Path(review).read_text()

        self._run_main(self._argv(tmp_path, **{flag: json.dumps(payload)}))

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "error"
        assert "invalid TestPlanReview.md" not in output["error"]
        assert "invalid TestPlanReview.md" not in captured.err
        assert error_clue in output["error"]
        assert Path(review).read_text() == original_text

    def test_well_formed_boilerplate_still_caps_via_main(self, tmp_path, capsys):
        _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10, verdict="Ready", passed=True)

        self._run_main(self._argv(tmp_path, **{"--boilerplate-result": json.dumps(BOILERPLATE_FIVE_VIOLATIONS)}))

        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "overridden"
        assert output["scores"]["specificity"] == 0

    def test_actionability_failure_can_be_enforced_from_review_cli_payload(self, tmp_path, capsys):
        _write_review(tmp_path / "TestPlanReview.md", ALL_TWOS, score=10)

        self._run_main(
            self._argv(
                tmp_path,
                **{
                    "--scope-coverage-result": json.dumps(VALID_SCOPE_COVERAGE),
                    "--actionability-result": json.dumps(INVALID_ACTIONABILITY),
                },
            )
        )

        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "overridden"
        assert output["scores"]["actionability"] == 1
