"""Unit tests for scripts/remove_runtime_alias.py."""

from pathlib import Path

import pytest

import scripts.remove_runtime_alias as remove_runtime_alias_module
from scripts.remove_runtime_alias import PLUGIN_ROOT, RUNTIME_ALIAS_NAME, main, remove_runtime_alias


def _output_and_feature(tmp_path: Path) -> tuple[Path, Path]:
    output_dir = tmp_path / "test-plans" / "RHAISTRAT" / "20261022-142300-RHAISTRAT-2980"
    feature_dir = output_dir / "fixture_feature"
    feature_dir.mkdir(parents=True)
    return output_dir, feature_dir


def _make_foreign_entry(path: Path, kind: str, tmp_path: Path) -> None:
    if kind == "foreign-symlink":
        target = tmp_path / "other-plugin"
        target.mkdir()
        path.symlink_to(target, target_is_directory=True)
    elif kind == "dangling-symlink":
        path.symlink_to(tmp_path / "missing-target")
    elif kind == "file":
        path.write_text("not a link\n")
    elif kind == "directory":
        path.mkdir()
        (path / "keep.txt").write_text("keep\n")
    else:
        raise AssertionError(f"unknown foreign entry kind {kind!r}")


class TestRemoveRuntimeAlias:
    @pytest.mark.parametrize("location", ["output", "feature", "both"])
    def test_removes_plugin_link(self, tmp_path, location):
        output_dir, feature_dir = _output_and_feature(tmp_path)
        directories = {"output": [output_dir], "feature": [feature_dir], "both": [output_dir, feature_dir]}[location]
        for directory in directories:
            (directory / RUNTIME_ALIAS_NAME).symlink_to(PLUGIN_ROOT, target_is_directory=True)

        result = remove_runtime_alias(str(feature_dir))

        assert result["status"] == "ok"
        assert sorted(result["removed"]) == sorted(str(d / RUNTIME_ALIAS_NAME) for d in directories)
        assert result["skipped"] == []
        for directory in (output_dir, feature_dir):
            assert not (directory / RUNTIME_ALIAS_NAME).is_symlink()
            assert not (directory / RUNTIME_ALIAS_NAME).exists()
        assert PLUGIN_ROOT.is_dir(), "Removing the link must not touch the plugin itself"

    def test_removes_relative_link_resolving_to_plugin(self, tmp_path):
        _, feature_dir = _output_and_feature(tmp_path)
        alias = feature_dir / RUNTIME_ALIAS_NAME
        alias.symlink_to(Path("..") / ".." / ".." / ".." / "plugin", target_is_directory=True)
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()

        result = remove_runtime_alias(str(feature_dir), plugin_root=plugin_root)

        assert result["removed"] == [str(alias)]
        assert not alias.is_symlink()
        assert plugin_root.is_dir()

    @pytest.mark.parametrize("kind", ["foreign-symlink", "dangling-symlink", "file", "directory"])
    def test_leaves_foreign_entries(self, tmp_path, kind):
        output_dir, feature_dir = _output_and_feature(tmp_path)
        alias = output_dir / RUNTIME_ALIAS_NAME
        _make_foreign_entry(alias, kind, tmp_path)

        result = remove_runtime_alias(str(feature_dir))

        assert result == {"status": "ok", "removed": [], "skipped": [str(alias)]}
        assert alias.is_symlink() or alias.exists()

    def test_no_alias_is_a_no_op(self, tmp_path):
        output_dir, feature_dir = _output_and_feature(tmp_path)
        (feature_dir / "TestPlan.md").write_text("# plan\n")

        result = remove_runtime_alias(str(feature_dir))

        assert result == {"status": "ok", "removed": [], "skipped": []}
        assert (feature_dir / "TestPlan.md").is_file()
        assert sorted(p.name for p in output_dir.iterdir()) == ["fixture_feature"]

    def test_does_not_look_in_nested_or_ancestor_directories(self, tmp_path):
        output_dir, feature_dir = _output_and_feature(tmp_path)
        nested = feature_dir / "test_cases" / RUNTIME_ALIAS_NAME
        nested.parent.mkdir()
        nested.symlink_to(PLUGIN_ROOT, target_is_directory=True)
        ancestor = output_dir.parent / RUNTIME_ALIAS_NAME
        ancestor.symlink_to(PLUGIN_ROOT, target_is_directory=True)

        result = remove_runtime_alias(str(feature_dir))

        assert result == {"status": "ok", "removed": [], "skipped": []}
        assert nested.is_symlink()
        assert ancestor.is_symlink()

    def test_missing_feature_dir_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Feature directory not found"):
            remove_runtime_alias(str(tmp_path / "missing"))


class TestRemoveRuntimeAliasCli:
    def test_cli_reports_removed_link(self, tmp_path, run_cli):
        _, feature_dir = _output_and_feature(tmp_path)
        alias = feature_dir / RUNTIME_ALIAS_NAME
        alias.symlink_to(PLUGIN_ROOT, target_is_directory=True)

        exit_code, output = run_cli(main, [str(feature_dir)])

        assert exit_code == 0
        assert output == {"status": "ok", "removed": [str(alias)], "skipped": []}
        assert not alias.is_symlink()

    def test_cli_missing_feature_dir_returns_json_error(self, tmp_path, run_cli):
        exit_code, output = run_cli(main, [str(tmp_path / "missing")])

        assert exit_code == 1
        assert output["status"] == "failed"
        assert "Feature directory not found" in output["error"]

    def test_cli_unlink_failure_returns_json_error(self, tmp_path, run_cli, monkeypatch):
        _, feature_dir = _output_and_feature(tmp_path)
        alias = feature_dir / RUNTIME_ALIAS_NAME
        alias.symlink_to(PLUGIN_ROOT, target_is_directory=True)

        def _deny_unlink(self, missing_ok=False):
            raise PermissionError(f"Permission denied: {self}")

        monkeypatch.setattr(remove_runtime_alias_module.Path, "unlink", _deny_unlink)

        exit_code, output = run_cli(main, [str(feature_dir)])

        assert exit_code == 1
        assert output["status"] == "failed"
        assert "Permission denied" in output["error"]
        assert alias.is_symlink()
