"""Unit tests for .fullsend/test-plan/check-handoff-files.py."""

import importlib.util
import json

import pytest

from tests.consts.test_plan_constants import HANDOFF_FEATURE_DIR, README_VALID
from tests.constants import REPO_ROOT

_SPEC = importlib.util.spec_from_file_location(
    "check_handoff_files", REPO_ROOT / ".fullsend" / "test-plan" / "check-handoff-files.py"
)
check_handoff_files = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_handoff_files)

ALL_HANDOFF_FILES = ("TestPlan.md", "README.md", "TestPlanReview.md", ".source-strategy.md")


def _write_feature(repo_dir, names=ALL_HANDOFF_FILES):
    feature_path = repo_dir.joinpath(*HANDOFF_FEATURE_DIR.split("/"))
    feature_path.mkdir(parents=True)
    for name in names:
        (feature_path / name).write_text(README_VALID if name == "README.md" else f"# {name}\n")
    return feature_path


class TestHandoffErrors:
    def test_complete_feature_passes(self, tmp_path):
        _write_feature(tmp_path)

        assert check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": HANDOFF_FEATURE_DIR}) == []

    @pytest.mark.parametrize("missing", ALL_HANDOFF_FILES, ids=list(ALL_HANDOFF_FILES))
    def test_missing_required_file_fails(self, tmp_path, missing):
        _write_feature(tmp_path, [name for name in ALL_HANDOFF_FILES if name != missing])

        errors = check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": HANDOFF_FEATURE_DIR})

        assert f"required file is missing: {HANDOFF_FEATURE_DIR}/{missing}" in errors

    def test_empty_readme_fails(self, tmp_path):
        feature_path = _write_feature(tmp_path)
        (feature_path / "README.md").write_text("")

        errors = check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": HANDOFF_FEATURE_DIR})

        assert errors == [f"required file is empty: {HANDOFF_FEATURE_DIR}/README.md"]

    def test_symlinked_readme_fails(self, tmp_path):
        feature_path = _write_feature(tmp_path)
        (feature_path / "README.md").unlink()
        (feature_path / "README.md").symlink_to(feature_path / "TestPlan.md")

        errors = check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": HANDOFF_FEATURE_DIR})

        assert errors == [f"required file is not a regular file: {HANDOFF_FEATURE_DIR}/README.md"]

    def test_no_acceptance_criteria_skips_plan_and_readme(self, tmp_path):
        _write_feature(tmp_path, ["TestPlanReview.md", ".source-strategy.md"])
        result = {"feature_dir": HANDOFF_FEATURE_DIR, "no_acceptance_criteria": True}

        assert check_handoff_files.handoff_errors(str(tmp_path), result) == []

    @pytest.mark.parametrize("missing", ["TestPlanReview.md", ".source-strategy.md"])
    def test_no_acceptance_criteria_still_requires_review_and_strategy(self, tmp_path, missing):
        _write_feature(tmp_path, [name for name in ("TestPlanReview.md", ".source-strategy.md") if name != missing])
        result = {"feature_dir": HANDOFF_FEATURE_DIR, "no_acceptance_criteria": True}

        errors = check_handoff_files.handoff_errors(str(tmp_path), result)

        assert errors == [f"required file is missing: {HANDOFF_FEATURE_DIR}/{missing}"]

    def test_no_acceptance_criteria_plan_without_readme_fails(self, tmp_path):
        _write_feature(tmp_path, ["TestPlan.md", "TestPlanReview.md", ".source-strategy.md"])
        result = {"feature_dir": HANDOFF_FEATURE_DIR, "no_acceptance_criteria": True}

        errors = check_handoff_files.handoff_errors(str(tmp_path), result)

        assert errors == [f"TestPlan.md and README.md must be present together in {HANDOFF_FEATURE_DIR}"]

    @pytest.mark.parametrize("feature_dir", ["/abs/feature", "plans/../escape", "plans\\feature", "", None])
    def test_unsafe_feature_dir_fails(self, tmp_path, feature_dir):
        errors = check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": feature_dir})

        assert errors == ["feature_dir must be a relative path inside the target workspace"]

    def test_missing_feature_dir_fails(self, tmp_path):
        errors = check_handoff_files.handoff_errors(str(tmp_path), {"feature_dir": HANDOFF_FEATURE_DIR})

        assert errors == [f"feature_dir not found in target workspace: {HANDOFF_FEATURE_DIR}"]


class TestCheckHandoffFilesCli:
    def _result_file(self, tmp_path, result):
        path = tmp_path / "agent-result.json"
        path.write_text(json.dumps(result))
        return str(path)

    def test_passes_for_complete_feature(self, tmp_path, capsys):
        repo_dir = tmp_path / "repo"
        _write_feature(repo_dir)

        exit_code = check_handoff_files.main(
            [self._result_file(tmp_path, {"feature_dir": HANDOFF_FEATURE_DIR}), str(repo_dir)]
        )

        assert exit_code == 0
        assert f"handoff files present: {HANDOFF_FEATURE_DIR}" in capsys.readouterr().out

    def test_fails_when_readme_missing(self, tmp_path, capsys):
        repo_dir = tmp_path / "repo"
        _write_feature(repo_dir, ["TestPlan.md", "TestPlanReview.md", ".source-strategy.md"])

        exit_code = check_handoff_files.main(
            [self._result_file(tmp_path, {"feature_dir": HANDOFF_FEATURE_DIR}), str(repo_dir)]
        )

        assert exit_code == 1
        assert f"FAIL: required file is missing: {HANDOFF_FEATURE_DIR}/README.md" in capsys.readouterr().err

    def test_fails_without_target_repo_dir(self, tmp_path, capsys):
        exit_code = check_handoff_files.main([self._result_file(tmp_path, {"feature_dir": HANDOFF_FEATURE_DIR}), ""])

        assert exit_code == 1
        assert "TARGET_REPO_DIR is empty" in capsys.readouterr().err

    def test_rejects_wrong_argument_count(self, capsys):
        assert check_handoff_files.main([]) == 2
        assert "usage:" in capsys.readouterr().err
