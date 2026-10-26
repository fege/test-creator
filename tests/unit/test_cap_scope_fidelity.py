"""Unit tests for scripts/cap_scope_fidelity.py — the stateless CLI wrapper around
enforce_citation_gate.apply_score_caps(), for callers with no TestPlanReview.md to persist to
(test-plan-score, which presents a rubric assessment directly without writing a review file).

Scores are passed as a single --scores-json argument — a JSON object with five rubric keys,
each an integer from 0 to 2. The Python helper validates the schema before processing.
"""

import json
import sys

import pytest

from scripts.cap_scope_fidelity import main
from tests.consts.validation_constants import (
    BOILERPLATE_FIVE_VIOLATIONS,
    BOILERPLATE_THREE_VIOLATIONS,
    INVALID_ACTIONABILITY,
    INVALID_CITATIONS,
    INVALID_SCOPE_CHECK,
    VALID_ACTIONABILITY,
    VALID_BOILERPLATE,
    VALID_CITATIONS,
    VALID_COVERAGE,
    VALID_SCOPE_COVERAGE,
    VALID_SCOPE_CHECK,
)

ALL_TWOS = {"specificity": 2, "grounding": 2, "scope_fidelity": 2, "actionability": 2, "consistency": 2}
ALL_TWOS_ARGS = ["--scores-json", json.dumps(ALL_TWOS)]
DEFAULT_RESULT_ARGS = [
    "--ac-citations-result",
    json.dumps(VALID_CITATIONS),
    "--ac-coverage-result",
    json.dumps(VALID_COVERAGE),
    "--scope-check-result",
    json.dumps(VALID_SCOPE_CHECK),
    "--boilerplate-result",
    json.dumps(VALID_BOILERPLATE),
    "--scope-coverage-result",
    json.dumps(VALID_SCOPE_COVERAGE),
    "--actionability-result",
    json.dumps(VALID_ACTIONABILITY),
]


def _run(argv, capsys):
    argv = list(argv)
    for flag, payload in (
        ("--scope-coverage-result", VALID_SCOPE_COVERAGE),
        ("--actionability-result", VALID_ACTIONABILITY),
    ):
        if flag not in argv:
            argv.extend((flag, json.dumps(payload)))
    old_argv = sys.argv
    try:
        sys.argv = ["cap_scope_fidelity.py", *argv]
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("main() must exit with code 0")
    finally:
        sys.argv = old_argv
    return json.loads(capsys.readouterr().out)


class TestCapScopeFidelityVerdict:
    """Cluster A: valid input → correct status/scores/verdict."""

    @pytest.mark.parametrize(
        "citations, expected_status",
        [
            pytest.param(VALID_CITATIONS, "ok", id="ok-when-citations-valid"),
            pytest.param(INVALID_CITATIONS, "overridden", id="overridden-when-citations-invalid"),
        ],
    )
    def test_verdict(self, citations, expected_status, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(citations),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ],
            capsys,
        )

        assert output["status"] == expected_status
        if expected_status == "ok":
            assert output == {"status": "ok", "scores": ALL_TWOS}
        else:
            assert output["scores"]["scope_fidelity"] == 1
            assert output["score"] == 9
            assert output["verdict"] == "Ready"
            assert output["pass"] is True

    def test_overridden_when_scope_check_invalid(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(INVALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ],
            capsys,
        )

        assert output["status"] == "overridden"
        assert output["scores"]["scope_fidelity"] == 1
        assert output["scores"]["specificity"] == 2  # untouched

    @pytest.mark.parametrize(
        "boilerplate, expected_cap",
        [
            pytest.param(BOILERPLATE_THREE_VIOLATIONS, 1, id="three-violations-caps-to-1"),
            pytest.param(BOILERPLATE_FIVE_VIOLATIONS, 0, id="five-violations-caps-to-0"),
        ],
    )
    def test_overridden_when_boilerplate_present(self, boilerplate, expected_cap, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(boilerplate),
            ],
            capsys,
        )

        assert output["status"] == "overridden"
        assert output["scores"]["specificity"] == expected_cap
        assert output["scores"]["scope_fidelity"] == 2  # untouched

    def test_both_scope_fidelity_and_specificity_capped_together(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(INVALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(BOILERPLATE_FIVE_VIOLATIONS),
            ],
            capsys,
        )

        assert output["status"] == "overridden"
        assert output["scores"]["scope_fidelity"] == 1
        assert output["scores"]["specificity"] == 0
        assert output["score"] == 7  # 0 + 2 + 1 + 2 + 2

    def test_quality_evidence_caps_actionability_in_stateless_score_flow(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
                "--scope-coverage-result",
                json.dumps(VALID_SCOPE_COVERAGE),
                "--actionability-result",
                json.dumps(INVALID_ACTIONABILITY),
            ],
            capsys,
        )

        assert output["status"] == "overridden"
        assert output["scores"]["actionability"] == 1
        assert output["score"] == 9
        assert output["verdict"] == "Revise"

    def test_valid_actionability_raises_stateless_score_to_two(self, capsys):
        scores = {**ALL_TWOS, "actionability": 1}

        output = _run(["--scores-json", json.dumps(scores), *DEFAULT_RESULT_ARGS], capsys)

        assert output["status"] == "overridden"
        assert output["scores"] == ALL_TWOS
        assert output["score"] == 10
        assert output["verdict"] == "Ready"
        assert output["actionability_raised"] is True
        assert output["actionability_capped"] is False


class TestCapScopeFidelityStructuredErrors:
    """Cluster B: input passes argparse but fails downstream validation → structured error
    (exit 0, status "error").
    """

    @pytest.mark.parametrize(
        "override, expected_substring",
        [
            pytest.param({"grounding": 3}, "between 0 and 2", id="out-of-range-score"),
            pytest.param({"specificity": -1}, "between 0 and 2", id="negative-score"),
        ],
    )
    def test_score_validation_error(self, override, expected_substring, capsys):
        scores = {**ALL_TWOS, **override}
        argv = ["--scores-json", json.dumps(scores), *DEFAULT_RESULT_ARGS]

        output = _run(argv, capsys)

        assert output["status"] == "error"
        assert expected_substring in output["error"]

    @pytest.mark.parametrize(
        "scores_json, expected_substring",
        [
            pytest.param("NOT-JSON{{{", "malformed --scores-json", id="malformed-scores-json"),
            pytest.param(json.dumps([1, 2, 3]), "must be a JSON object", id="scores-not-object"),
            pytest.param(
                json.dumps({**ALL_TWOS, "specificity": "foo"}),
                "must be an integer",
                id="non-integer-score",
            ),
        ],
    )
    def test_scores_json_validation_error(self, scores_json, expected_substring, capsys):
        output = _run(["--scores-json", scores_json, *DEFAULT_RESULT_ARGS], capsys)

        assert output["status"] == "error"
        assert expected_substring in output["error"]

    @pytest.mark.parametrize(
        "citations_arg, coverage_arg",
        [
            pytest.param("NOT-JSON{{{", json.dumps(VALID_COVERAGE), id="ac-citations"),
            pytest.param(json.dumps(VALID_CITATIONS), "NOT-JSON{{{", id="ac-coverage"),
        ],
    )
    def test_malformed_json_result_arg(self, citations_arg, coverage_arg, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                citations_arg,
                "--ac-coverage-result",
                coverage_arg,
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ],
            capsys,
        )

        assert output["status"] == "error"
        assert "malformed" in output["error"]

    def test_missing_valid_field_in_ac_citations(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps({"total": 5}),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ],
            capsys,
        )

        assert output["status"] == "error"
        assert "valid" in output["error"]

    def test_missing_valid_field_in_scope_check(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps({"violations": []}),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ],
            capsys,
        )

        assert output["status"] == "error"
        assert "valid" in output["error"]

    def test_non_integer_total_violations_in_boilerplate(self, capsys):
        output = _run(
            [
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--scope-check-result",
                json.dumps(VALID_SCOPE_CHECK),
                "--boilerplate-result",
                json.dumps({"valid": False, "total_violations": "many"}),
            ],
            capsys,
        )

        assert output["status"] == "error"
        assert "total_violations" in output["error"]


class TestCapScopeFidelityArgparseRejection:
    """Cluster C: argparse-level rejection → SystemExit code 2 (before any application logic)."""

    def test_missing_scores_json_exits_with_code_2(self):
        old_argv = sys.argv
        try:
            sys.argv = ["cap_scope_fidelity.py", *DEFAULT_RESULT_ARGS]
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        finally:
            sys.argv = old_argv

    def test_missing_scope_check_result_exits_with_code_2(self):
        old_argv = sys.argv
        try:
            sys.argv = [
                "cap_scope_fidelity.py",
                *ALL_TWOS_ARGS,
                "--ac-citations-result",
                json.dumps(VALID_CITATIONS),
                "--ac-coverage-result",
                json.dumps(VALID_COVERAGE),
                "--boilerplate-result",
                json.dumps(VALID_BOILERPLATE),
            ]
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        finally:
            sys.argv = old_argv

    @pytest.mark.parametrize("missing_flag", ("--scope-coverage-result", "--actionability-result"))
    def test_missing_quality_evidence_result_exits_with_code_2(self, missing_flag):
        argv = ["cap_scope_fidelity.py", *ALL_TWOS_ARGS, *DEFAULT_RESULT_ARGS]
        flag_index = argv.index(missing_flag)
        del argv[flag_index : flag_index + 2]
        old_argv = sys.argv
        try:
            sys.argv = argv
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        finally:
            sys.argv = old_argv
