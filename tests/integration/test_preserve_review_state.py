import json
import os
import shutil
import tempfile
import unittest

from scripts import preserve_review_state
from scripts.utils.frontmatter_utils import read_frontmatter_validated, write_frontmatter_with_body


def _base_review_payload():
    return {
        "feature": "kagenti_agent_templates",
        "source_key": "RHAISTRAT-1290",
        "score": 8,
        "pass": True,
        "verdict": "Revise",
        "scores": {
            "specificity": 2,
            "grounding": 2,
            "scope_fidelity": 2,
            "actionability": 1,
            "consistency": 1,
        },
        "auto_revised": False,
        "before_score": None,
        "before_scores": None,
        "error": None,
        "last_updated": "2026-04-10",
    }


def _write_review(feature_dir, revision_history, auto_revised=False):
    review_path = os.path.join(feature_dir, "TestPlanReview.md")
    body = f"## Test Plan Review\n\n## Revision History\n{revision_history}\n\n## Notes\n- review body placeholder\n"
    payload = _base_review_payload()
    if auto_revised is None:
        payload.pop("auto_revised")
    else:
        payload["auto_revised"] = auto_revised
    return write_frontmatter_with_body(review_path, body, payload, "test-plan-review")


def _write_state(feature_dir, revision_history, auto_revised=None):
    state_path = os.path.join(feature_dir, ".review-state.json")
    state = {
        "before_score": 8,
        "before_scores": {
            "specificity": 2,
            "grounding": 2,
            "scope_fidelity": 2,
            "actionability": 1,
            "consistency": 1,
        },
        "revision_history": revision_history,
    }
    if auto_revised is not None:
        state["auto_revised"] = auto_revised

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


class TestPreserveReviewState(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="test-plan-preserve-state-")

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_restore_replaces_placeholder_history(self):
        saved_history = "### Cycle 1 Revision\n- tightened endpoint mapping"
        review_path = _write_review(self.tempdir, "Initial assessment")
        _write_state(self.tempdir, saved_history)

        preserve_review_state.restore(self.tempdir)

        final_history = preserve_review_state._extract_revision_history(review_path)
        self.assertEqual(final_history, saved_history)
        self.assertNotIn("Initial assessment", final_history)

        data, _ = read_frontmatter_validated(review_path, "test-plan-review")
        self.assertEqual(data["before_score"], 8)
        self.assertEqual(data["before_scores"]["specificity"], 2)
        self.assertFalse(os.path.exists(os.path.join(self.tempdir, ".review-state.json")))

    def test_save_restore_preserves_auto_revised_across_review_recreation(self):
        state_path = os.path.join(self.tempdir, ".review-state.json")
        for original_auto_revised in (False, True):
            with self.subTest(original_auto_revised=original_auto_revised):
                history = "### Cycle 1 Revision\n- revised after initial assessment"
                review_path = _write_review(self.tempdir, history, auto_revised=original_auto_revised)

                preserve_review_state.save(self.tempdir)

                with open(state_path, encoding="utf-8") as state_file:
                    saved_state = json.load(state_file)
                self.assertIs(type(saved_state["auto_revised"]), bool)
                self.assertIs(saved_state["auto_revised"], original_auto_revised)

                os.remove(review_path)
                recreated_path = _write_review(self.tempdir, "Initial assessment", auto_revised=None)
                recreated, _ = read_frontmatter_validated(recreated_path, "test-plan-review")
                self.assertIs(recreated["auto_revised"], False)

                preserve_review_state.restore(self.tempdir)

                restored, _ = read_frontmatter_validated(recreated_path, "test-plan-review")
                self.assertIs(restored["auto_revised"], original_auto_revised)
                self.assertFalse(os.path.exists(state_path))

    def test_restore_combines_saved_and_current_auto_revised_flags(self):
        for saved_auto_revised in (False, True):
            for current_auto_revised in (False, True):
                with self.subTest(
                    saved_auto_revised=saved_auto_revised,
                    current_auto_revised=current_auto_revised,
                ):
                    review_path = _write_review(
                        self.tempdir,
                        "Current assessment",
                        auto_revised=current_auto_revised,
                    )
                    _write_state(
                        self.tempdir,
                        "### Cycle 1 Revision\n- preserved saved history",
                        auto_revised=saved_auto_revised,
                    )

                    preserve_review_state.restore(self.tempdir)

                    restored, _ = read_frontmatter_validated(review_path, "test-plan-review")
                    self.assertIs(restored["auto_revised"], saved_auto_revised or current_auto_revised)

    def test_restore_legacy_state_preserves_current_auto_revised_flag(self):
        for current_auto_revised in (False, True):
            with self.subTest(current_auto_revised=current_auto_revised):
                review_path = _write_review(
                    self.tempdir,
                    "Current assessment",
                    auto_revised=current_auto_revised,
                )
                _write_state(self.tempdir, "### Cycle 1 Revision\n- legacy saved history")

                preserve_review_state.restore(self.tempdir)

                restored, _ = read_frontmatter_validated(review_path, "test-plan-review")
                self.assertIs(restored["auto_revised"], current_auto_revised)

    def test_repeated_save_restore_cycles_retain_auto_revised_true(self):
        state_path = os.path.join(self.tempdir, ".review-state.json")
        review_path = _write_review(
            self.tempdir,
            "### Cycle 1 Revision\n- automatic revision recorded",
            auto_revised=True,
        )

        for cycle in range(3):
            with self.subTest(cycle=cycle + 1):
                preserve_review_state.save(self.tempdir)
                with open(state_path, encoding="utf-8") as state_file:
                    saved_state = json.load(state_file)
                self.assertIs(saved_state["auto_revised"], True)

                os.remove(review_path)
                review_path = _write_review(self.tempdir, "Initial assessment", auto_revised=None)
                preserve_review_state.restore(self.tempdir)

                restored, _ = read_frontmatter_validated(review_path, "test-plan-review")
                self.assertIs(restored["auto_revised"], True)
                self.assertFalse(os.path.exists(state_path))

    def test_restore_merges_saved_and_new_history_when_new_is_meaningful(self):
        saved_history = "### Cycle 1 Revision\n- added endpoint/method matrix"
        current_history = "### Cycle 2 Reassessment\n- score improved to 9/10"
        review_path = _write_review(self.tempdir, current_history)
        _write_state(self.tempdir, saved_history)

        preserve_review_state.restore(self.tempdir)

        final_history = preserve_review_state._extract_revision_history(review_path)
        self.assertEqual(final_history, f"{saved_history}\n\n{current_history}")

    def test_restore_does_not_duplicate_history_when_already_prefixed(self):
        saved_history = "### Cycle 1 Revision\n- tightened scope fidelity notes"
        current_history = f"{saved_history}\n\n### Cycle 2 Reassessment\n- no further changes needed"
        review_path = _write_review(self.tempdir, current_history)
        _write_state(self.tempdir, saved_history)

        preserve_review_state.restore(self.tempdir)

        final_history = preserve_review_state._extract_revision_history(review_path)
        self.assertEqual(final_history, current_history)
        self.assertEqual(final_history.count("### Cycle 1 Revision"), 1)
