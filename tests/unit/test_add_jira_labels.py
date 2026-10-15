"""Unit tests for scripts/add_jira_labels.py."""

import json
from unittest.mock import patch

import pytest

from scripts.add_jira_labels import main, rubric_label_for_verdict


@pytest.fixture(autouse=True)
def isolate_test_plan_dry_run_env(monkeypatch):
    """Keep ambient dry-run configuration from changing unrelated test behavior."""
    monkeypatch.delenv("TEST_PLAN_DRY_RUN", raising=False)


class TestRubricLabelForVerdict:
    """Tests for rubric_label_for_verdict() pure function."""

    @pytest.mark.parametrize(
        "verdict,expected_label",
        [
            ("Ready", "test-plan-rubric-pass"),
            ("Revise", "test-plan-rubric-revise"),
            ("Rework", "test-plan-rubric-fail"),
            ("Bogus", None),
        ],
    )
    def test_verdict_to_label_mapping(self, verdict, expected_label):
        assert rubric_label_for_verdict(verdict) == expected_label


class TestMain:
    """Tests for main() argument handling and label assembly."""

    @pytest.mark.parametrize(
        "extra_argv,expected_exit,expected_labels,expected_remove,expected_stderr",
        [
            pytest.param(
                ["--verdict", "Ready", "test-plan-auto-revised"],
                0,
                ["test-plan-rubric-pass", "test-plan-auto-revised"],
                ["test-plan-rubric-revise", "test-plan-rubric-fail"],
                None,
                id="verdict_and_literal_combined",
            ),
            pytest.param(
                ["--verdict", "Typo", "test-plan-auto-revised"],
                0,
                ["test-plan-auto-revised"],
                [],
                "Unexpected verdict",
                id="unrecognized_verdict_still_adds_literal_labels",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "dry_run_value",
        [pytest.param(None, id="flag_unset"), pytest.param("false", id="flag_false")],
    )
    @patch("scripts.add_jira_labels.add_labels")
    def test_main_label_assembly(
        self,
        mock_add_labels,
        monkeypatch,
        capsys,
        extra_argv,
        expected_exit,
        expected_labels,
        expected_remove,
        expected_stderr,
        dry_run_value,
    ):
        if dry_run_value is None:
            monkeypatch.delenv("TEST_PLAN_DRY_RUN", raising=False)
        else:
            monkeypatch.setenv("TEST_PLAN_DRY_RUN", dry_run_value)
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", *extra_argv])

        exit_code = main()

        assert exit_code == expected_exit
        mock_add_labels.assert_called_once_with("RHAISTRAT-400", expected_labels, remove=expected_remove)
        if expected_stderr is not None:
            assert expected_stderr in capsys.readouterr().err

    @pytest.mark.parametrize(
        "extra_argv",
        [
            pytest.param(["--verdict", "Ready", "test-plan-auto-revised"], id="verdict-and-literal"),
            pytest.param(["test-plan-rubric-pass", "test-plan-auto-created"], id="literal-rubric-label"),
            pytest.param(["custom-label"], id="literal-label"),
        ],
    )
    @patch("scripts.add_jira_labels.add_labels")
    def test_main_dry_run_skips_valid_requests(self, mock_add_labels, monkeypatch, capsys, extra_argv):
        monkeypatch.setenv("TEST_PLAN_DRY_RUN", "true")
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", *extra_argv])

        assert main() == 0

        mock_add_labels.assert_not_called()
        assert json.loads(capsys.readouterr().out)["status"] == "skipped"

    @pytest.mark.parametrize(
        "extra_argv,expected_error",
        [
            pytest.param([], "no_labels_to_add", id="no-labels"),
            pytest.param(["--verdict", "Bogus"], "invalid_verdict", id="invalid-verdict"),
            pytest.param(
                ["--verdict", "Ready", "test-plan-rubric-fail"],
                "conflicting_rubric_labels",
                id="conflicting-rubric-labels",
            ),
        ],
    )
    @patch("scripts.add_jira_labels.add_labels")
    def test_main_dry_run_still_rejects_invalid_requests(
        self, mock_add_labels, monkeypatch, capsys, extra_argv, expected_error
    ):
        monkeypatch.setenv("TEST_PLAN_DRY_RUN", "true")
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", *extra_argv])

        assert main() == 1

        mock_add_labels.assert_not_called()
        assert json.loads(capsys.readouterr().out) == {"status": "error", "error": expected_error}

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_changed_verdict_removes_stale_rubric_label(self, mock_add_labels, monkeypatch):
        """Regression test for the CodeRabbit finding on PR #46: a verdict change (e.g.
        Ready -> Revise) must remove every *other* rubric label, not just add the new one,
        since jira_utils.add_labels only ever appends unless told what to remove.
        """
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", "--verdict", "Revise"])

        assert main() == 0

        mock_add_labels.assert_called_once_with(
            "RHAISTRAT-400",
            ["test-plan-rubric-revise"],
            remove=["test-plan-rubric-pass", "test-plan-rubric-fail"],
        )

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_rejects_literal_rubric_label_conflicting_with_verdict(self, mock_add_labels, monkeypatch, capsys):
        """--verdict Ready with literal test-plan-rubric-fail must fail before Jira."""
        monkeypatch.setattr(
            "sys.argv",
            ["add_jira_labels.py", "RHAISTRAT-400", "--verdict", "Ready", "test-plan-rubric-fail"],
        )

        assert main() == 1
        mock_add_labels.assert_not_called()
        captured = capsys.readouterr()
        assert "conflict" in captured.err
        assert json.loads(captured.out) == {"status": "error", "error": "conflicting_rubric_labels"}

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_positional_rubric_label_removes_stale_without_verdict(self, mock_add_labels, monkeypatch):
        """A lone positional rubric label must still clear the other rubric labels."""
        monkeypatch.setattr(
            "sys.argv",
            ["add_jira_labels.py", "RHAISTRAT-400", "test-plan-rubric-pass", "test-plan-auto-created"],
        )

        assert main() == 0
        mock_add_labels.assert_called_once_with(
            "RHAISTRAT-400",
            ["test-plan-rubric-pass", "test-plan-auto-created"],
            remove=["test-plan-rubric-revise", "test-plan-rubric-fail"],
        )

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_rejects_multiple_positional_rubric_labels(self, mock_add_labels, monkeypatch, capsys):
        """Two different positional rubric labels must fail before Jira."""
        monkeypatch.setattr(
            "sys.argv",
            ["add_jira_labels.py", "RHAISTRAT-400", "test-plan-rubric-pass", "test-plan-rubric-fail"],
        )

        assert main() == 1
        mock_add_labels.assert_not_called()
        assert json.loads(capsys.readouterr().out) == {"status": "error", "error": "conflicting_rubric_labels"}

    @pytest.mark.parametrize(
        "extra_argv",
        [
            pytest.param(["--verdict", "Bogus"], id="unrecognized_verdict_alone"),
            pytest.param(["--verdict", ""], id="empty_verdict"),
        ],
    )
    @patch("scripts.add_jira_labels.add_labels")
    def test_main_invalid_verdict_alone_emits_json_error(self, mock_add_labels, monkeypatch, capsys, extra_argv):
        """Unrecognized --verdict with nothing else to stamp is a structured failure."""
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", *extra_argv])

        assert main() == 1
        mock_add_labels.assert_not_called()
        captured = capsys.readouterr()
        assert "Unexpected verdict" in captured.err
        assert json.loads(captured.out) == {"status": "error", "error": "invalid_verdict"}

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_no_labels_emits_json_error_on_stdout(self, mock_add_labels, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400"])

        assert main() == 1
        mock_add_labels.assert_not_called()
        captured = capsys.readouterr()
        assert "No labels to add" in captured.err
        assert json.loads(captured.out) == {"status": "error", "error": "no_labels_to_add"}

    @patch("scripts.add_jira_labels.add_labels")
    def test_main_add_labels_failure_emits_json_error_on_stdout(self, mock_add_labels, monkeypatch, capsys):
        mock_add_labels.side_effect = RuntimeError("Jira API unreachable")
        monkeypatch.setattr("sys.argv", ["add_jira_labels.py", "RHAISTRAT-400", "some-label"])

        assert main() == 1
        captured = capsys.readouterr()
        assert "Failed to add labels" in captured.err
        assert json.loads(captured.out) == {"status": "error", "error": "add_labels_failed"}
