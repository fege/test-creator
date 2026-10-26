#!/usr/bin/env python3
"""Deterministically cap Scope Fidelity/Specificity/Actionability when the citation/scope/quality/boilerplate checks
say they should be, for callers with no TestPlanReview.md to persist to.

Valid Actionability with no blocking ``bare_tbd``/``missing_details`` evidence raises the
scorer's 0/1 result to 2; only blocking evidence is capped to 1, while ``advisory_gaps`` remain
informational. The test-plan-score skill presents a rubric assessment directly without writing a
review file, so this script provides the deterministic backstop that test-plan-score would otherwise
lack. Wraps scripts.enforce_citation_gate.apply_score_caps() — the same pure logic
test-plan-review's enforce_citation_gate.py uses (that one also persists the result to disk).

Usage:
    uv run python scripts/cap_scope_fidelity.py \
        --scores-json '{"specificity":2,"grounding":2,"scope_fidelity":2,"actionability":2,"consistency":2}' \
        --ac-citations-result '<json from validate.py ac-citations>' \
        --ac-coverage-result '<json from validate.py ac-coverage>' \
        --scope-check-result '<json from validate_test_scope.py>' \
        --boilerplate-result '<json from detect_boilerplate.py>' \
        --scope-coverage-result '<json from validate_quality_evidence.py>' \
        --actionability-result '<json from validate_quality_evidence.py>'

Exit code 0 with a JSON object to stdout: `status` is "overridden", "ok", or "error" (with an
`error` message field). Exit code 2 from argparse on missing args.
"""

import argparse
import json
import sys

from scripts.enforce_citation_gate import apply_score_caps
from scripts.utils.error_utils import exit_graceful


def _fail(message: str) -> None:
    print(json.dumps({"status": "error", "error": message}))
    exit_graceful(f"cap_scope_fidelity: {message}")


def _load_json(raw: str, flag: str) -> dict:
    """Load a required result payload."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"malformed {flag} JSON: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-json", required=True, help="JSON object with five rubric scores (0-2 each)")
    parser.add_argument("--ac-citations-result", required=True, help="JSON from validate.py ac-citations")
    parser.add_argument("--ac-coverage-result", required=True, help="JSON from validate.py ac-coverage")
    parser.add_argument("--scope-check-result", required=True, help="JSON from validate_test_scope.py")
    parser.add_argument("--boilerplate-result", required=True, help="JSON from detect_boilerplate.py")
    parser.add_argument("--scope-coverage-result", required=True, help="JSON from validate_quality_evidence.py")
    parser.add_argument("--actionability-result", required=True, help="JSON from validate_quality_evidence.py")
    args = parser.parse_args()

    scores = _load_json(args.scores_json, "--scores-json")
    if not isinstance(scores, dict):
        _fail("--scores-json must be a JSON object")

    ac_citations = _load_json(args.ac_citations_result, "--ac-citations-result")
    ac_coverage = _load_json(args.ac_coverage_result, "--ac-coverage-result")
    scope_check = _load_json(args.scope_check_result, "--scope-check-result")
    boilerplate = _load_json(args.boilerplate_result, "--boilerplate-result")
    scope_coverage = _load_json(args.scope_coverage_result, "--scope-coverage-result")
    actionability = _load_json(args.actionability_result, "--actionability-result")

    try:
        result = apply_score_caps(
            scores,
            ac_citations,
            ac_coverage,
            scope_check,
            boilerplate,
            scope_coverage_result=scope_coverage,
            actionability_result=actionability,
        )
    except ValueError as exc:
        _fail(str(exc))

    if result["overridden"]:
        payload = {"status": "overridden"}
        payload.update({k: v for k, v in result.items() if k != "overridden"})
    else:
        payload = {"status": "ok", "scores": result["scores"]}
    print(json.dumps(payload))
    sys.exit(0)


if __name__ == "__main__":
    main()
