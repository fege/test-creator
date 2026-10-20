#!/usr/bin/env python3
"""Force-correct Scope Fidelity, Specificity, and Actionability when the review agent disagrees with the
deterministic checks it was given.

score-agent.md instructs the LLM to read ac_citations_result.valid / ac_coverage_result.valid /
scope_check_result.valid directly and cap Scope Fidelity to <= 1 when any is false, cap
Actionability when blocking actionability evidence is present, and cap Specificity per
boilerplate_result.total_violations — but LLM compliance with those instructions isn't guaranteed.
This re-applies the same rules after TestPlanReview.md is written: overriding the recorded score
(in the frontmatter and in the body's score table, total, and verdict text) when it's inconsistent
with the already-computed results, and injecting a deterministic feedback
note (which objectives are uncited/invalid, which AC numbers are missing, which Section 2.1
levels are disallowed, which sections have boilerplate language, and which blocking actionability
gaps remain) so the revise agent has something concrete to act on even if the review agent's own
prose feedback missed it.

Usage:
    python3 scripts/enforce_citation_gate.py <feature_dir> \
        --ac-citations-result '<json from validate.py ac-citations>' \
        --ac-coverage-result '<json from validate.py ac-coverage>' \
        --scope-check-result '<json from validate_test_scope.py>' \
        --boilerplate-result '<json from detect_boilerplate.py>' \
        --scope-coverage-result '<json from validate_quality_evidence.py>' \
        --actionability-result '<json from validate_quality_evidence.py>'

Exit code 0 always; prints a JSON object to stdout with `status` one of "overridden", "ok",
"skip", or "error" (with an `error` message field).
"""

import argparse
import json
import os
import re
import sys

import yaml

from scripts.utils.error_utils import exit_graceful
from scripts.utils.frontmatter_utils import read_frontmatter_validated, update_frontmatter
from scripts.utils.schemas import CRITERION_LABELS, REVIEW_CRITERIA, ValidationError, compute_verdict_and_pass
from scripts.validate_quality_evidence import validate_actionability_result

FEEDBACK_HEADING = "## Section-by-Section Feedback"

# The score section of a review, in the two layouts the review writers produce: `## Rubric Scores`
# (review-agent.md) and `## Score Table`. It runs up to the next level-2 heading.
_SCORE_SECTION_RE = re.compile(r"^## (?:Rubric Scores|Score Table)[ \t]*$.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)

# A separate verdict section (e.g. the RHAISTRAT-2930 "Verdict" paragraph), up to the next level-2 heading.
_VERDICT_SECTION_RE = re.compile(r"^## Verdict\b[^\n]*$.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def _require_valid_field(result, name: str) -> None:
    """Fail closed: reject anything that isn't a dict with a boolean `valid` field, and — for
    the entry lists _build_feedback_note iterates and indexes directly — reject any entry that
    isn't shaped the way it expects. A wrong-typed `valid` (e.g. the string "false", which Python
    truthiness alone would treat as truthy) or a malformed entry (e.g. `null` inside `uncited`)
    must never be silently accepted: the latter would otherwise raise mid-write, after
    TestPlanReview.md's frontmatter has already been updated but before the feedback note
    explaining why is inserted.
    """
    if not isinstance(result, dict):
        raise ValueError(f"{name} must be a JSON object")
    if not isinstance(result.get("valid"), bool):
        raise ValueError(f"{name} must have a boolean 'valid' field")

    entry_requirements = (
        ("uncited", ("text", "line_number")),
        ("invalid_citations", ("text", "line_number", "reasons")),
        ("violations", ("line", "matched_pattern", "context")),
    )
    for key, required_fields in entry_requirements:
        entries = result.get(key)
        if entries is None:
            continue
        if not isinstance(entries, list):
            raise ValueError(f"{name}.{key} must be a list")
        for entry in entries:
            if not isinstance(entry, dict) or not all(field in entry for field in required_fields):
                raise ValueError(f"{name}.{key} entries must be objects with {', '.join(required_fields)}")
        if key == "invalid_citations":
            if any(not isinstance(entry["reasons"], list) for entry in entries):
                raise ValueError(f"{name}.{key} entries must have a list 'reasons' field")
            if any(not isinstance(r, str) for entry in entries for r in entry["reasons"]):
                raise ValueError(f"{name}.{key} entries must have a list of string 'reasons'")

    # boilerplate_result.by_section is section_id -> [entry, ...], not a flat list, so it can't
    # reuse the entry_requirements loop above — same required fields as "violations" though.
    by_section = result.get("by_section")
    if by_section is not None:
        if not isinstance(by_section, dict):
            raise ValueError(f"{name}.by_section must be an object")
        for section, entries in by_section.items():
            if not isinstance(entries, list):
                raise ValueError(f"{name}.by_section.{section} must be a list")
            for entry in entries:
                if not isinstance(entry, dict) or not all(
                    field in entry for field in ("line", "matched_pattern", "context")
                ):
                    raise ValueError(
                        f"{name}.by_section.{section} entries must be objects with line, matched_pattern, context"
                    )


def _build_feedback_note(
    ac_citations_result: dict,
    ac_coverage_result: dict,
    scope_check_result: dict,
    boilerplate_result: dict,
    scope_fidelity_capped: bool,
    scope_coverage_result: dict | None,
    actionability_result: dict | None,
    actionability_capped: bool,
    specificity_capped: bool,
) -> str:
    lines: list[str] = []

    if scope_fidelity_capped:
        lines.append(
            "**Automated correction (deterministic citation/scope gate)**: Scope Fidelity was "
            "capped to 1/2 — the recorded score did not reflect this."
        )
        uncited = ac_citations_result.get("uncited") or []
        invalid = ac_citations_result.get("invalid_citations") or []
        if uncited:
            lines.append("\nObjectives with no citation at all:")
            lines.extend(f"- Line {o['line_number']}: {o['text']}" for o in uncited)
        if invalid:
            lines.append("\nObjectives with an invalid citation:")
            lines.extend(f"- Line {o['line_number']}: {o['text']} — {', '.join(o['reasons'])}" for o in invalid)
        missing = ac_coverage_result.get("missing") or []
        if missing:
            lines.append(f"\nAC numbers with no citing objective at all: {missing}")
        violations = scope_check_result.get("violations") or []
        if violations:
            lines.append("\nSection 2.1 test level issues:")
            lines.extend(f"- Line {v['line']}: {v['matched_pattern']} ({v['context']})" for v in violations)
        if scope_coverage_result is not None:
            missing = scope_coverage_result.get("missing") or []
            unmapped = scope_coverage_result.get("unmapped_objectives") or []
            if missing:
                lines.append("\nScope requirements without a Section 1.3 objective:")
                lines.extend(f"- Section {item['section']}: {item['text']} ({item['reason']})" for item in missing)
            if unmapped:
                lines.append("\nObjectives without a grounded strategy requirement:")
                lines.extend(f"- Section {item['section']}: {item['text']} ({item['reason']})" for item in unmapped)
        lines.append(
            "\nFix: add a machine-checkable `(AC: #N — short description)` or "
            "`(NFR: category — text)` citation to each listed objective, and/or remove the "
            "disallowed test levels/patterns from Section 2.1. For listed scope entries, add an "
            "explicit `(Objective: #N)` marker that points at an existing Section 1.3 objective."
        )

    if actionability_capped:
        if lines:
            lines.append("\n---")
        lines.append(
            "**Automated correction (deterministic actionability gate)**: Actionability was "
            "capped to 1/2 — the recorded score did not reflect the plan's operational gaps."
        )
        if actionability_result is not None:
            bare_tbd = actionability_result.get("bare_tbd") or []
            missing_details = actionability_result.get("missing_details") or []
            if bare_tbd:
                lines.append("\nBare TBDs without a resolution path:")
                lines.extend(f"- {item}" for item in bare_tbd)
            if missing_details:
                lines.append("\nMissing actionable details:")
                lines.extend(f"- {item}" for item in missing_details)
        lines.append(
            "\nFix: specify concrete environment, test-data, and test-user permissions, or retain TBD "
            "with an explicit resolution path."
        )

    if specificity_capped:
        if lines:
            lines.append("\n---")
        lines.append(
            "**Automated correction (deterministic boilerplate gate)**: Specificity was capped "
            "— the recorded score did not reflect this."
        )
        for section, violations in (boilerplate_result.get("by_section") or {}).items():
            lines.append(f"\nSection {section} generic phrases:")
            lines.extend(f"- Line {v['line']}: {v['matched_pattern']} ({v['context']})" for v in violations)
        lines.append("\nFix: replace generic phrasing in Sections 1.3/2.3/8 with feature-specific language.")

    return "\n".join(lines)


def _sync_score_cell(section: str, row_label_pattern: str, old: int | str | None, new: int, suffix: str) -> str:
    """Rewrite the score cell of the table row whose first cell is `row_label_pattern`. A cell is
    matched as a whole — bare (`2`) or with its denominator (`2/2`), optionally bold — and its
    formatting is kept. A trailing pipe is optional.
    """
    return re.sub(
        rf"^(\|[ \t]*{row_label_pattern}[ \t]*\|[ \t]*)(\**){old}({re.escape(suffix)})?(\**)(?=[ \t]*(?:\||$))",
        rf"\g<1>\g<2>{new}\g<3>\g<4>",
        section,
        flags=re.MULTILINE,
    )


def _sync_verdict_section(
    section: str, old_score: int | None, old_verdict: str | None, score: int, verdict: str
) -> str:
    """Rewrite only the awarded total and verdict word in a `## Verdict` section: the score named
    after a scoring word (`scores 10/10`, `Total: 10/10`) and the verdict word named after
    `verdict` or leading a line (`**Ready** — ...`). Other `N/10` figures and eligibility wording
    (`must be 2 to qualify as Ready`) are left alone.
    """
    if old_score != score:
        section = re.sub(
            rf"(\b(?:scores?|scored|totals?|awarded|rated)\b[^\n.]{{0,30}}?\b){old_score}/10\b",
            rf"\g<1>{score}/10",
            section,
            flags=re.IGNORECASE,
        )
    if old_verdict and old_verdict != verdict:
        section = re.sub(
            rf"(\bverdict\b[^\n.]{{0,20}}?\**){re.escape(old_verdict)}\b",
            rf"\g<1>{verdict}",
            section,
            flags=re.IGNORECASE,
        )
        # A verdict that leads its line: bolded (`**Ready** — ...`) or followed by a dash or colon
        # (`Ready: ...`). A bare word that merely starts a wrapped line is not touched.
        section = re.sub(
            rf"^([ \t]*)(?:\*\*{re.escape(old_verdict)}\*\*|{re.escape(old_verdict)}(?=[ \t]*[—–:-]))",
            lambda m: m.group(1) + (f"**{verdict}**" if m.group(0).endswith("**") else verdict),
            section,
            flags=re.MULTILINE,
        )
    return section


def _sync_review_body(
    body: str,
    old_scores: dict,
    old_score: int | None,
    old_verdict: str | None,
    scores: dict,
    score: int,
    verdict: str,
) -> str:
    """Bring the human-readable result of the review in line with the corrected frontmatter, so the
    review never shows two conflicting results. The gate knows the exact old and new values, so this
    is a set of targeted substitutions in two places only: the `## Rubric Scores` / `## Score Table`
    section (the score cell of each changed criterion row, the Total row cell, and the
    `Total: <old>/10 — Verdict: <old>` line) and a separate `## Verdict` section (the awarded score
    and verdict word). Everything else, including eligibility wording and Revision History, is left
    untouched.
    """
    match = _SCORE_SECTION_RE.search(body)
    if match is not None:
        section = match.group(0)
        for key, label in CRITERION_LABELS.items():
            if old_scores.get(key) != scores.get(key):
                section = _sync_score_cell(section, label, old_scores.get(key), scores[key], "/2")
        section = _sync_score_cell(section, r"\**Total\**", old_score, score, "/10")
        section = section.replace(
            f"Total: {old_score}/10 — Verdict: {old_verdict}", f"Total: {score}/10 — Verdict: {verdict}"
        )
        body = body[: match.start()] + section + body[match.end() :]
    verdict_match = _VERDICT_SECTION_RE.search(body)
    if verdict_match is not None:
        section = _sync_verdict_section(verdict_match.group(0), old_score, old_verdict, score, verdict)
        body = body[: verdict_match.start()] + section + body[verdict_match.end() :]
    return body


def _insert_feedback_note(body: str, note: str) -> str:
    """Return `body` with the correction note under the feedback heading. When the review writer
    omitted that heading, add it (right after the score section, or at the end of the body) so the
    correction rationale is never silently dropped.
    """
    idx = body.find(FEEDBACK_HEADING)
    if idx != -1:
        insert_at = idx + len(FEEDBACK_HEADING)
        return body[:insert_at] + "\n\n" + note + body[insert_at:]

    section = f"{FEEDBACK_HEADING}\n\n{note}\n"
    score_section = _SCORE_SECTION_RE.search(body)
    if score_section is None or score_section.end() == len(body):
        prefix = body if body.endswith("\n") or not body else body + "\n"
        return f"{prefix}\n{section}" if prefix else section
    insert_at = score_section.end()
    return body[:insert_at] + section + "\n" + body[insert_at:]


def _validate_scores(scores: dict) -> None:
    """Reject anything that isn't a dict containing exactly the 5 rubric criteria, with each
    value being an integer in range 0..2 inclusive (rejecting boolean values explicitly).
    """
    if not isinstance(scores, dict):
        raise ValueError("scores must be a JSON object")

    expected = set(REVIEW_CRITERIA)
    actual = set(scores.keys())

    missing = expected - actual
    if missing:
        raise ValueError(f"scores is missing required criteria: {', '.join(sorted(missing))}")

    extra = actual - expected
    if extra:
        raise ValueError(f"scores contains unknown criteria: {', '.join(sorted(extra))}")

    for k in REVIEW_CRITERIA:
        v = scores[k]
        if type(v) is not int:
            raise ValueError(f"scores.{k} must be an integer, got {type(v).__name__}")
        if not (0 <= v <= 2):
            raise ValueError(f"scores.{k} must be between 0 and 2, got {v}")


def _raise_if_script_error(result: dict) -> None:
    """Script/config failures return {valid: false, error: "..."} — surface that message, not a
    missing-field story that main() used to wrap as invalid TestPlanReview.md.
    """
    error = result.get("error")
    if isinstance(error, str):
        raise ValueError(error)


def _validate_scope_for_capping(result: dict, name: str) -> None:
    """Require a violations list on scope_check_result used for score capping (may be empty)."""
    _raise_if_script_error(result)
    if "violations" not in result:
        raise ValueError(f"{name} must have a 'violations' list")
    if not isinstance(result["violations"], list):
        raise ValueError(f"{name}.violations must be a list")


def _validate_gap_evidence(result: dict, name: str, keys: tuple[str, str], validate_entries) -> None:
    """Shared skeleton for {valid, <gap-list>, <gap-list>} evidence: object/valid-field checks,
    per-key entry validation (caller-supplied, since entry shape differs per validator), and the
    valid-vs-has-gaps consistency check.
    """
    if not isinstance(result, dict):
        raise ValueError(f"{name} must be a JSON object")
    if not isinstance(result.get("valid"), bool):
        raise ValueError(f"{name} must have a boolean 'valid' field")
    for key in keys:
        validate_entries(result.get(key), name, key)
    has_gaps = bool(result[keys[0]] or result[keys[1]])
    if result["valid"] == has_gaps:
        raise ValueError(f"{name}.valid does not agree with its evidence")


def _validate_scope_coverage_entries(entries, name: str, key: str) -> None:
    if not isinstance(entries, list):
        raise ValueError(f"{name}.{key} must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(field), str) and entry[field] for field in ("section", "text", "reason")
        ):
            raise ValueError(f"{name}.{key} entries must have section, text, and reason strings")


def _validate_scope_coverage_for_capping(result: dict, name: str) -> None:
    """Validate required bidirectional scope evidence before any score or review update."""
    _validate_gap_evidence(result, name, ("missing", "unmapped_objectives"), _validate_scope_coverage_entries)


def _validate_actionability_for_capping(result: dict, name: str) -> None:
    """Validate required actionability evidence before any score or review update."""
    validate_actionability_result(result, name)


def _validate_required_quality_result(result: dict | None, name: str, validator) -> None:
    """Fail closed when a public score-gate caller omits required quality evidence."""
    if result is None:
        raise ValueError(f"{name} is required")
    validator(result, name)


def _validate_boilerplate_for_capping(result: dict, name: str) -> None:
    """Require integer total_violations on boilerplate_result used for score capping."""
    _raise_if_script_error(result)
    total = result.get("total_violations")
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError(f"{name}.total_violations must be an integer")


def cap_scope_fidelity(
    scores: dict,
    ac_citations_result: dict,
    ac_coverage_result: dict,
    scope_check_result: dict,
    scope_coverage_result: dict,
) -> dict:
    """Cap Scope Fidelity to 1 if the deterministic citation/coverage/scope checks say it
    should be, but `scores` says 2. Pure — no file I/O — shared by enforce_citation_gate() (which
    persists the result to TestPlanReview.md) and test-plan-score (which has no review file and
    only needs the corrected numbers to present).
    """
    _validate_scores(scores)
    _require_valid_field(ac_citations_result, "ac_citations_result")
    _require_valid_field(ac_coverage_result, "ac_coverage_result")
    _require_valid_field(scope_check_result, "scope_check_result")
    _validate_scope_for_capping(scope_check_result, "scope_check_result")
    _validate_required_quality_result(
        scope_coverage_result, "scope_coverage_result", _validate_scope_coverage_for_capping
    )

    scope_ok = (
        ac_citations_result["valid"]
        and ac_coverage_result["valid"]
        and scope_check_result["valid"]
        and scope_coverage_result["valid"]
    )
    scores = dict(scores)
    if scope_ok or scores.get("scope_fidelity", 0) <= 1:
        return {"overridden": False, "scores": scores}

    scores["scope_fidelity"] = 1
    verdict, score, passed = compute_verdict_and_pass(scores)
    return {"overridden": True, "scores": scores, "score": score, "pass": passed, "verdict": verdict}


def cap_actionability(scores: dict, actionability_result: dict) -> dict:
    """Preserve valid Actionability, or cap it to 1 for blocking evidence."""
    _validate_scores(scores)
    _validate_required_quality_result(actionability_result, "actionability_result", _validate_actionability_for_capping)

    scores = dict(scores)
    blocking_gaps = actionability_result["bare_tbd"] or actionability_result["missing_details"]
    if blocking_gaps:
        if scores["actionability"] <= 1:
            return {"overridden": False, "scores": scores}

        scores["actionability"] = 1
        verdict, score, passed = compute_verdict_and_pass(scores)
        return {
            "overridden": True,
            "scores": scores,
            "score": score,
            "pass": passed,
            "verdict": verdict,
            "actionability_capped": True,
        }

    return {"overridden": False, "scores": scores}


def cap_specificity(scores: dict, boilerplate_result: dict) -> dict:
    """Cap Specificity per score-agent.md's boilerplate severity tiers (>=5 violations -> 0,
    >=3 -> 1), but `scores` disagrees. Pure — no file I/O — same shape as cap_scope_fidelity,
    shared by enforce_citation_gate() and test-plan-score for the same reason.
    """
    _validate_scores(scores)
    _require_valid_field(boilerplate_result, "boilerplate_result")
    _validate_boilerplate_for_capping(boilerplate_result, "boilerplate_result")
    total = boilerplate_result["total_violations"]

    cap = 0 if total >= 5 else (1 if total >= 3 else None)
    scores = dict(scores)
    if cap is None or scores.get("specificity", 0) <= cap:
        return {"overridden": False, "scores": scores}

    scores["specificity"] = cap
    verdict, score, passed = compute_verdict_and_pass(scores)
    return {"overridden": True, "scores": scores, "score": score, "pass": passed, "verdict": verdict}


def apply_score_caps(
    scores: dict,
    ac_citations_result: dict,
    ac_coverage_result: dict,
    scope_check_result: dict,
    boilerplate_result: dict,
    scope_coverage_result: dict,
    actionability_result: dict,
) -> dict:
    """Apply Scope Fidelity and Specificity caps plus Actionability correction together and return one combined result.

    Specificity is capped against the *post-Scope-Fidelity* scores dict (not the original), so
    if both criteria need correcting, the final score/verdict/pass reflect both — not just
    whichever cap ran last with its own isolated view of `scores`.
    """
    _validate_required_quality_result(
        scope_coverage_result, "scope_coverage_result", _validate_scope_coverage_for_capping
    )
    _validate_required_quality_result(actionability_result, "actionability_result", _validate_actionability_for_capping)
    scope_result = cap_scope_fidelity(
        scores,
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        scope_coverage_result=scope_coverage_result,
    )
    actionability_cap_result = cap_actionability(scope_result["scores"], actionability_result)
    specificity_result = cap_specificity(actionability_cap_result["scores"], boilerplate_result)

    scope_fidelity_capped = scope_result["overridden"]
    actionability_overridden = actionability_cap_result["overridden"]
    actionability_capped = actionability_cap_result.get("actionability_capped", False)
    specificity_capped = specificity_result["overridden"]
    if not scope_fidelity_capped and not actionability_overridden and not specificity_capped:
        return {"overridden": False, "scores": specificity_result["scores"]}

    final = (
        specificity_result
        if specificity_capped
        else (actionability_cap_result if actionability_overridden else scope_result)
    )
    return {
        "overridden": True,
        "scores": final["scores"],
        "score": final["score"],
        "pass": final["pass"],
        "verdict": final["verdict"],
        "scope_fidelity_capped": scope_fidelity_capped,
        "actionability_capped": actionability_capped,
        "specificity_capped": specificity_capped,
    }


def enforce_citation_gate(
    feature_dir: str,
    ac_citations_result: dict,
    ac_coverage_result: dict,
    scope_check_result: dict,
    boilerplate_result: dict,
    scope_coverage_result: dict,
    actionability_result: dict,
) -> dict | None:
    """Cap Scope Fidelity/Specificity/Actionability if deterministic checks require it, but the
    persisted review scores disagree. Returns None if TestPlanReview.md doesn't exist.
    """
    _require_valid_field(ac_citations_result, "ac_citations_result")
    _require_valid_field(ac_coverage_result, "ac_coverage_result")
    _require_valid_field(scope_check_result, "scope_check_result")
    _require_valid_field(boilerplate_result, "boilerplate_result")
    _validate_required_quality_result(
        scope_coverage_result, "scope_coverage_result", _validate_scope_coverage_for_capping
    )
    _validate_required_quality_result(actionability_result, "actionability_result", _validate_actionability_for_capping)

    review_path = os.path.join(feature_dir, "TestPlanReview.md")
    if not os.path.exists(review_path):
        return None

    data, body = read_frontmatter_validated(review_path, "test-plan-review")
    old_score = data.get("score")

    result = apply_score_caps(
        data.get("scores", {}),
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        boilerplate_result,
        scope_coverage_result=scope_coverage_result,
        actionability_result=actionability_result,
    )
    if not result["overridden"]:
        return {"overridden": False}

    scores, score, passed, verdict = result["scores"], result["score"], result["pass"], result["verdict"]
    scope_fidelity_capped = result["scope_fidelity_capped"]
    actionability_capped = result["actionability_capped"]
    specificity_capped = result["specificity_capped"]
    updates = {"scores": scores, "score": score, "pass": passed, "verdict": verdict}

    # Built before anything is written, deliberately: if this raises on a malformed result
    # that somehow slipped past _require_valid_field, the frontmatter must not already be
    # written — a half-applied override (corrected score, no explanatory note) is worse than no
    # override at all.
    note = _build_feedback_note(
        ac_citations_result,
        ac_coverage_result,
        scope_check_result,
        boilerplate_result,
        scope_fidelity_capped,
        scope_coverage_result,
        actionability_result,
        actionability_capped,
        specificity_capped,
    )

    # A first-pass review sets before_score/before_scores equal to score not a genuine prior-cycle baseline.
    # Left uncorrected, the lowered score would look like a regression to filter_for_revision.py and get skipped.
    if data.get("before_score") == old_score:
        updates["before_score"] = score
        before_scores = dict(data.get("before_scores") or {})
        if before_scores:
            if scope_fidelity_capped:
                before_scores["scope_fidelity"] = scores["scope_fidelity"]
            if actionability_capped:
                before_scores["actionability"] = scores["actionability"]
            if specificity_capped:
                before_scores["specificity"] = scores["specificity"]
            updates["before_scores"] = before_scores

    # The corrected body and frontmatter are written in one atomic step, so the human-readable score
    # table, total, and verdict never disagree with the frontmatter.
    new_body = _sync_review_body(body, data.get("scores") or {}, old_score, data.get("verdict"), scores, score, verdict)
    new_body = _insert_feedback_note(new_body, note)
    update_frontmatter(review_path, updates, "test-plan-review", body=new_body)

    return {
        "overridden": True,
        "scores": scores,
        "score": score,
        "pass": passed,
        "verdict": verdict,
        "scope_fidelity_capped": scope_fidelity_capped,
        "actionability_capped": actionability_capped,
        "specificity_capped": specificity_capped,
    }


def _fail(message: str) -> None:
    """Report a machine-readable error on stdout (for the calling skill) and a matching
    diagnostic on stderr (for a human watching logs), then exit — a broken gate must not abort
    the review run, but it must never look like a clean OK/SKIP/overridden result either.
    """
    print(json.dumps({"status": "error", "error": message}))
    exit_graceful(f"enforce_citation_gate: {message}")


def _load_and_validate(raw: str, flag: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"malformed {flag} JSON: {exc}")
    try:
        _require_valid_field(value, flag)
    except ValueError as exc:
        _fail(str(exc))
    return value


def _load_optional_quality_result(raw: str | None, flag: str, validator) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"malformed {flag} JSON: {exc}")
    try:
        validator(value, flag)
    except ValueError as exc:
        _fail(str(exc))
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir")
    parser.add_argument("--ac-citations-result", required=True, help="JSON from validate.py ac-citations")
    parser.add_argument("--ac-coverage-result", required=True, help="JSON from validate.py ac-coverage")
    parser.add_argument("--scope-check-result", required=True, help="JSON from validate_test_scope.py")
    parser.add_argument("--boilerplate-result", required=True, help="JSON from detect_boilerplate.py")
    parser.add_argument("--scope-coverage-result", help="JSON from validate_quality_evidence.py")
    parser.add_argument("--actionability-result", help="JSON from validate_quality_evidence.py")
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code == 0:
            raise
        _fail("missing or invalid arguments")

    ac_citations = _load_and_validate(args.ac_citations_result, "--ac-citations-result")
    ac_coverage = _load_and_validate(args.ac_coverage_result, "--ac-coverage-result")
    scope_check = _load_and_validate(args.scope_check_result, "--scope-check-result")
    boilerplate = _load_and_validate(args.boilerplate_result, "--boilerplate-result")
    if args.scope_coverage_result is None:
        _fail("--scope-coverage-result is required")
    if args.actionability_result is None:
        _fail("--actionability-result is required")
    scope_coverage = _load_optional_quality_result(
        args.scope_coverage_result, "--scope-coverage-result", _validate_scope_coverage_for_capping
    )
    actionability = _load_optional_quality_result(
        args.actionability_result, "--actionability-result", _validate_actionability_for_capping
    )

    try:
        result = enforce_citation_gate(
            args.feature_dir,
            ac_citations,
            ac_coverage,
            scope_check,
            boilerplate,
            scope_coverage_result=scope_coverage,
            actionability_result=actionability,
        )
    except ValueError as exc:
        _fail(str(exc))
    except (ValidationError, OSError, yaml.YAMLError) as exc:
        _fail(f"invalid TestPlanReview.md: {exc}")

    if result is None:
        print(json.dumps({"status": "skip"}))
    elif result["overridden"]:
        payload = {"status": "overridden"}
        payload.update({k: v for k, v in result.items() if k != "overridden"})
        print(json.dumps(payload))
    else:
        print(json.dumps({"status": "ok"}))
    sys.exit(0)


if __name__ == "__main__":
    main()
