"""Integration contracts for installed and Fullsend plugin delivery."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.utils.frontmatter_utils import read_frontmatter, write_frontmatter, write_frontmatter_with_body
from tests.constants import VALID_TEST_CASE_DATA
from tests.consts.test_plan_constants import (
    VALID_TEST_PLAN_BODY_FOR_CASES_VALIDATION,
    VALID_TEST_PLAN_DATA,
    VALID_TEST_PLAN_REVIEW_DATA,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHING_SKILL = "test-plan-publish"
STRATEGY_CONTENT = "# Local strategy fixture\n"
BOOTSTRAP_SCRIPT = Path("scripts/bootstrap.sh")
RUNTIME_ALIAS_NAME = ".odh-test-gen"
GIT_REPOSITORY_LOCATION_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_PREFIX",
)
FULLSEND_POST_TEST_PLAN_HOOK = REPO_ROOT / ".fullsend" / "test-plan" / "post-test-plan.py"
POST_HOOK_OLD_INDEX = (
    "# Previous cases\n\n"
    "- [TC-E2E-001](TC-E2E-001.md)\n"
    "- [TC-E2E-002](./TC-E2E-002.md)\n"
    "- [TC-E2E-777](../TC-E2E-777.md)\n"
)
POST_HOOK_NEW_INDEX = "# Current cases\n\n- [TC-E2E-001](TC-E2E-001.md)\n- [TC-E2E-003](./TC-E2E-003.md)\n"
POST_HOOK_OLD_RETAINED_CASE = b"old retained case\n"
POST_HOOK_UPDATED_RETAINED_CASE = b"updated retained case\n"
POST_HOOK_OLD_REMOVED_CASE = b"old removed case\n"
POST_HOOK_UNINDEXED_CASE = b"unindexed case-like file\n"
POST_HOOK_NEW_CASE = b"new case\n"
POST_HOOK_OUTSIDE_CASE = b"outside cases directory\n"
LAYOUT_ENTRYPOINT_SKILLS = (
    "test-plan-case-implement",
    "test-plan-create-cases",
    "test-plan-create",
    "test-plan-generate-test-file",
    "test-plan-publish",
    "test-plan-resolve-feedback",
    "test-plan-review",
    "test-plan-score",
    "test-plan-update",
)
SKILL_PACKAGE_ROOT_SKILLS = (
    "test-plan-case-implement",
    "test-plan-create",
    "test-plan-create-cases",
    "test-plan-generate-test-file",
    "test-plan-resolve-feedback",
    "test-plan-review",
    "test-plan-score",
    "test-plan-update",
)
SHELL_BLOCK_RE = re.compile(r"(?ms)^[ \t]*\x60\x60\x60(?:bash|sh|shell)\b[^\n]*\n(.*?)^[ \t]*\x60\x60\x60")
GIT_SKILL_ROOT_RE = re.compile(r"\bgit\s+-C\s+['\"]?\$\{?CLAUDE_SKILL_DIR\}?['\"]?\s+rev-parse\s+--show-toplevel\b")


def _git_repository_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in GIT_REPOSITORY_LOCATION_ENV_VARS:
        environment.pop(variable, None)
    return environment


def _tracked_paths(repository: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        env=_git_repository_environment(),
        capture_output=True,
        check=True,
    )
    return tuple(Path(os.fsdecode(raw_path)) for raw_path in result.stdout.split(b"\0") if raw_path)


def _untracked_paths(repository: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repository,
        env=_git_repository_environment(),
        capture_output=True,
        check=True,
    )
    return tuple(Path(os.fsdecode(raw_path)) for raw_path in result.stdout.split(b"\0") if raw_path)


def _copy_tracked_checkout(source: Path, target: Path) -> Path:
    """Stage tracked files plus the one bootstrap script under development."""
    target.mkdir(parents=True)
    staged_paths = set(_tracked_paths(source))
    candidate_bootstrap = source / BOOTSTRAP_SCRIPT
    if candidate_bootstrap.is_file() and not candidate_bootstrap.is_symlink():
        staged_paths.add(BOOTSTRAP_SCRIPT)

    for relative_path in sorted(staged_paths):
        source_path = source / relative_path
        if source_path.is_symlink() or not source_path.is_file():
            continue
        target_path = target / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    return target


def _symlink_entries(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): os.readlink(path) for path in root.rglob("*") if path.is_symlink()}


def _initialize_git_repository(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    repository = path.resolve()
    environment = _git_repository_environment()
    subprocess.run(["git", "init", "--quiet"], cwd=repository, env=environment, capture_output=True, check=True)
    git_dir = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=repository,
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    expected_git_dir = (repository / ".git").resolve()
    assert Path(git_dir).resolve() == expected_git_dir, (
        f"Git initialized {git_dir!r}, expected the fixture repository at {expected_git_dir}"
    )
    return repository


def _shell_blocks(document: Path) -> list[str]:
    return [match.group(1) for match in SHELL_BLOCK_RE.finditer(document.read_text(encoding="utf-8"))]


def _non_publishing_skill_docs(repository: Path) -> list[Path]:
    return [
        document
        for document in sorted((repository / "skills").glob("*/SKILL.md"))
        if document.parent.name != PUBLISHING_SKILL
    ]


def _find_shell_block(document: Path, needle: str, skill_dir: Path | None = None) -> str:
    content = document.read_text(encoding="utf-8")
    if skill_dir is not None:
        content = content.replace("${CLAUDE_SKILL_DIR}", str(skill_dir))
    for match in SHELL_BLOCK_RE.finditer(content):
        block = match.group(1)
        if needle in block:
            return block
    raise AssertionError(f"No shell command block in {document} contains {needle!r}")


def _package_root_cd(document: Path) -> str:
    for block in _shell_blocks(document):
        match = re.search(
            r'cd(?: -P)?\s+"\$\{CLAUDE_SKILL_DIR\}/\.\./\.\."\s*&&\s*pwd -P',
            block,
        )
        if match:
            return match.group(0)
    raise AssertionError(f"No package-root cd using CLAUDE_SKILL_DIR in {document}")


def _skill_dir_for_delivery_layout(package_root: Path, skill_name: str, layout: str) -> Path:
    skill_dir = package_root / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if layout == "direct-installed-version":
        return skill_dir
    if layout == "fullsend-skill-alias":
        alias = package_root / ".claude" / "skills" / skill_name
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(Path("../../skills") / skill_name, target_is_directory=True)
        return alias

    raise AssertionError(f"Unsupported plugin delivery layout: {layout}")


def _through_line(block: str, needle: str) -> str:
    lines = block.splitlines()
    end = next(index + 1 for index, line in enumerate(lines) if needle in line)
    return "\n".join(lines[:end])


def _prompt_frontmatter_command(prompt_text: str, marker: str) -> str:
    for block_match in SHELL_BLOCK_RE.finditer(prompt_text):
        lines = block_match.group(1).splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if not line.startswith(("uv run ", "(cd ")):
                index += 1
                continue

            command_lines = [line]
            while command_lines[-1].endswith("\\"):
                index += 1
                command_lines.append(lines[index].strip())
            command = "\n".join(command_lines)
            if "frontmatter.py" in command and marker in command:
                return command
            index += 1

    raise AssertionError(f"No documented frontmatter command contains {marker!r}")


def _write_uv_stub(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    implementation = bin_dir / "uv_stub.py"
    implementation.write_text(
        """import json
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
caller_cwd = Path.cwd().resolve()
project = None
for index, argument in enumerate(arguments):
    if argument in {"--project", "--directory", "--project-dir"} and index + 1 < len(arguments):
        project = arguments[index + 1]
    elif argument.startswith(("--project=", "--directory=", "--project-dir=")):
        project = argument.split("=", 1)[1]

project_root = Path(project).expanduser() if project else caller_cwd
if not project_root.is_absolute():
    project_root = caller_cwd / project_root
if project_root.is_file():
    project_root = project_root.parent
project_root = project_root.resolve()
if not (project_root / "pyproject.toml").is_file():
    project_root = next(
        (parent for parent in (project_root, *project_root.parents) if (parent / "pyproject.toml").is_file()),
        project_root,
    )

record = {
    "cwd": str(caller_cwd),
    "logical_cwd": os.environ.get("PWD", str(caller_cwd)),
    "project_root": str(project_root),
    "fullsend_target_repo_dir": os.environ.get("FULLSEND_TARGET_REPO_DIR"),
    "arguments": arguments,
}
with open(os.environ["UV_CALL_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\\n")

if "sync" in arguments:
    raise SystemExit(0)

python_index = next(
    (index for index, argument in enumerate(arguments) if argument in {"python", "python3"}),
    None,
)
if python_index is None or "run" not in arguments[:python_index]:
    raise SystemExit(23)

run_environment = os.environ.copy()
python_path = run_environment.get("PYTHONPATH", "")
run_environment["PYTHONPATH"] = str(project_root) + (os.pathsep + python_path if python_path else "")
python = run_environment["PYTHON_BIN"]
os.execve(python, [python, *arguments[python_index + 1 :]], run_environment)
""",
        encoding="utf-8",
    )

    launcher = bin_dir / "uv"
    launcher.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(implementation))} "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)


def _command_environment(skill_dir: Path, tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    _write_uv_stub(bin_dir)
    env = _git_repository_environment()
    env.update(
        {
            "CLAUDE_SKILL_DIR": str(skill_dir),
            "PYTHON_BIN": sys.executable,
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_CALL_LOG": str(tmp_path / "uv-calls.jsonl"),
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
        }
    )
    env.pop("FULLSEND_TASK", None)
    env.pop("FULLSEND_TARGET_REPO_DIR", None)
    return env


@pytest.mark.parametrize(
    "redirect_mode",
    [
        pytest.param("git-dir-and-work-tree", id="redirect-repository"),
        pytest.param("git-index-file", id="redirect-index"),
    ],
)
def test_git_inventory_helpers_use_the_requested_repository(tmp_path: Path, monkeypatch, redirect_mode: str) -> None:
    for variable in GIT_REPOSITORY_LOCATION_ENV_VARS:
        monkeypatch.delenv(variable, raising=False)

    redirected_repo = _initialize_git_repository(tmp_path / "redirected-repository")
    redirected_tracked = "redirected-tracked.txt"
    redirected_untracked = "redirected-untracked.txt"
    (redirected_repo / redirected_tracked).write_text("tracked in redirected repository\n", encoding="utf-8")
    (redirected_repo / redirected_untracked).write_text("untracked in redirected repository\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", redirected_tracked],
        cwd=redirected_repo,
        env=_git_repository_environment(),
        capture_output=True,
        check=True,
    )

    if redirect_mode == "git-dir-and-work-tree":
        monkeypatch.setenv("GIT_DIR", str(redirected_repo / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(redirected_repo))
    else:
        monkeypatch.setenv("GIT_INDEX_FILE", str(redirected_repo / ".git" / "index"))

    requested_repo = _initialize_git_repository(tmp_path / "requested-repository")
    requested_tracked = "requested-tracked.txt"
    requested_untracked = "requested-untracked.txt"
    (requested_repo / requested_tracked).write_text("tracked in requested repository\n", encoding="utf-8")
    (requested_repo / requested_untracked).write_text("untracked in requested repository\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", requested_tracked],
        cwd=requested_repo,
        env=_git_repository_environment(),
        capture_output=True,
        check=True,
    )

    assert _tracked_paths(requested_repo) == (Path(requested_tracked),)
    assert _untracked_paths(requested_repo) == (Path(requested_untracked),)

    for variable in GIT_REPOSITORY_LOCATION_ENV_VARS:
        monkeypatch.setenv(variable, str(redirected_repo / variable.lower()))

    command_env = _command_environment(tmp_path / "skills" / "test-plan-create", tmp_path)
    assert set(GIT_REPOSITORY_LOCATION_ENV_VARS).isdisjoint(command_env)
    git_probe = _run_bash(
        "git ls-files --cached --others --exclude-standard -z",
        cwd=requested_repo,
        env=command_env,
    )
    assert git_probe.returncode == 0, f"stdout:\n{git_probe.stdout}\nstderr:\n{git_probe.stderr}"
    assert set(git_probe.stdout.split("\0")) - {""} == {requested_tracked, requested_untracked}


def _make_caller(path: Path, *, with_git: bool) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(
        '[project]\nname = "unrelated-caller"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    scripts = {
        "parse_strat.py": 'raise SystemExit("caller parse_strat.py was selected")\n',
        "repo.py": 'raise SystemExit("caller repo.py was selected")\n',
    }
    script_dir = path / "scripts"
    script_dir.mkdir()
    for name, content in scripts.items():
        (script_dir / name).write_text(content, encoding="utf-8")
    if with_git:
        _initialize_git_repository(path)
    return scripts


def _run_bash(command: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _json_result_and_caller_cwd(result: subprocess.CompletedProcess[str], caller: Path) -> dict:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    json_text, marker, caller_cwd = result.stdout.rpartition("CALLER_CWD=")
    assert marker, f"helper command did not report the caller cwd: {result.stdout}"
    assert Path(caller_cwd.strip()).resolve() == caller.resolve()
    return json.loads(json_text.strip())


def _json_documents(output: str) -> list[dict]:
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    while position < len(output):
        while position < len(output) and output[position].isspace():
            position += 1
        if position == len(output):
            break
        document, position = decoder.raw_decode(output, position)
        documents.append(document)
    return documents


@pytest.mark.parametrize(
    ("skill_name", "needle", "arguments"),
    [
        pytest.param(
            "test-plan-create",
            "scope_result=$(uv run python scripts/validate_test_scope.py",
            None,
            id="scope-validation-failure",
        ),
        pytest.param(
            "test-plan-create-cases",
            "scripts/parse_skill_args.py",
            "--output-dir /tmp/partial-output mcp_catalog",
            id="output-dir-parse-failure",
        ),
    ],
)
def test_documented_capture_failures_stop_execution(
    tmp_path: Path, skill_name: str, needle: str, arguments: str | None
) -> None:
    skill_dir = REPO_ROOT / "skills" / skill_name
    block = _find_shell_block(skill_dir / "SKILL.md", needle, skill_dir)
    if skill_name == "test-plan-create":
        # Let the later citation capture succeed if the scope guard is missing.
        block = block.split("actionability_result=", 1)[0]

    environment = {"PATH": os.environ.get("PATH", ""), "CLAUDE_SKILL_DIR": str(skill_dir)}
    if arguments is not None:
        environment["ARGUMENTS"] = arguments

    uv_stub = """uv() {
    case "$*" in
        *get_component_test_dir.py*) printf 'team-a\\n' ;;
        *validate_test_scope.py*|*parse_skill_args.py*) printf 'partial output\\n'; return 42 ;;
        *build_citation_inputs.py*) printf '{}\\n' ;;
        *) return 99 ;;
    esac
}
"""
    result = subprocess.run(
        ["bash", "-c", f"{uv_stub}\n{block}\nprintf 'COMPLETED\\n'\n"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "COMPLETED" not in result.stdout


@pytest.mark.parametrize(
    "skill_name",
    SKILL_PACKAGE_ROOT_SKILLS,
)
@pytest.mark.parametrize(
    "layout",
    [
        pytest.param("direct-installed-version", id="direct-installed-version"),
        pytest.param("fullsend-skill-alias", id="fullsend-skill-alias"),
    ],
)
def test_skill_package_root_resolution_across_delivery_layouts(tmp_path: Path, skill_name: str, layout: str) -> None:
    document = REPO_ROOT / "skills" / skill_name / "SKILL.md"
    root_cd = _package_root_cd(document)
    package_root = (
        tmp_path / "direct plugin cache with spaces" / "test-plan" / "2.0.0"
        if layout == "direct-installed-version"
        else tmp_path / "fullsend checkout with spaces"
    )
    skill_dir = _skill_dir_for_delivery_layout(package_root, skill_name, layout)
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "CLAUDE_SKILL_DIR": str(skill_dir),
    }

    result = _run_bash(
        f"printf '%s\\n' \"$({root_cd})\"\n",
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    selected_package_root = Path(result.stdout.strip())
    assert selected_package_root == package_root.resolve(), (
        f"{skill_name} selected {layout} resolved to {selected_package_root}, "
        f"expected physical package root {package_root.resolve()}"
    )


def test_non_publishing_skill_shell_commands_do_not_discover_package_root_with_git() -> None:
    offenders = [
        f"{document.relative_to(REPO_ROOT)}: {match.group(0)}"
        for document in _non_publishing_skill_docs(REPO_ROOT)
        for block in _shell_blocks(document)
        for match in GIT_SKILL_ROOT_RE.finditer(block)
    ]
    assert not offenders, (
        f"Non-publishing skill command blocks must resolve the package root without Git metadata; found: {offenders}"
    )


def test_fullsend_plugin_has_no_tracked_symlinks_to_stage() -> None:
    symlinks = [str(path) for path in _tracked_paths(REPO_ROOT) if (REPO_ROOT / path).is_symlink()]
    assert not symlinks, f"The Fullsend plugin tree must be symlink-free before bootstrap: {symlinks}"


@pytest.mark.parametrize(
    ("delivery_mode", "caller_has_git", "target_root_mode"),
    [
        pytest.param("installed", True, None, id="installed-git-caller"),
        pytest.param("installed", False, None, id="installed-non-git-caller"),
        pytest.param("fullsend", False, "absolute", id="fullsend-no-git-output-workspace"),
        pytest.param("fullsend", False, "relative", id="fullsend-relative-target-root"),
    ],
)
def test_documented_skill_commands_keep_plugin_and_output_roots(
    tmp_path: Path, delivery_mode: str, caller_has_git: bool, target_root_mode: str | None
) -> None:
    untracked_paths = set(_untracked_paths(REPO_ROOT))
    plugin_root = _copy_tracked_checkout(REPO_ROOT, tmp_path / "plugin")
    skill_dir = plugin_root / "skills" / "test-plan-create"
    assert (plugin_root / "pyproject.toml").is_file()
    assert not (plugin_root / ".git").exists()
    assert not _symlink_entries(plugin_root)
    assert all(
        not (plugin_root / relative_path).exists()
        for relative_path in untracked_paths
        if relative_path != BOOTSTRAP_SCRIPT
    ), "Only the in-progress bootstrap script may be copied from untracked source files"
    candidate_bootstrap = REPO_ROOT / BOOTSTRAP_SCRIPT
    if candidate_bootstrap.is_file() and not candidate_bootstrap.is_symlink():
        assert (plugin_root / BOOTSTRAP_SCRIPT).is_file()

    if delivery_mode == "fullsend":
        caller = tmp_path / "target-workspace"
        output_root = caller
    else:
        caller = tmp_path / ("git-caller" if caller_has_git else "non-git-caller")
        output_root = tmp_path / "external-output"
    caller_scripts = _make_caller(caller, with_git=caller_has_git)
    output_root.mkdir(parents=True, exist_ok=True)
    assert output_root.resolve() != plugin_root.resolve()
    if delivery_mode == "fullsend":
        assert not (output_root / ".git").exists()

    env = _command_environment(skill_dir, tmp_path)
    env.pop("CLAUDE_SKILL_DIR")
    if delivery_mode == "fullsend":
        env["FULLSEND_TARGET_REPO_DIR"] = "." if target_root_mode == "relative" else str(output_root)
    else:
        assert "FULLSEND_TARGET_REPO_DIR" not in env
    assert "CLAUDE_SKILL_DIR" not in env

    create_skill = skill_dir / "SKILL.md"
    bootstrap_block = _find_shell_block(create_skill, "scripts/bootstrap.sh", skill_dir)
    bootstrap_result = _run_bash(
        bootstrap_block + '\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    assert bootstrap_result.returncode == 0, f"stdout:\n{bootstrap_result.stdout}\nstderr:\n{bootstrap_result.stderr}"
    assert bootstrap_result.stdout.strip().endswith(f"CALLER_CWD={caller}")

    sync_block = _find_shell_block(create_skill, "uv sync --extra dev", skill_dir)
    if sync_block != bootstrap_block:
        sync_result = _run_bash(sync_block, cwd=caller, env=env)
        assert sync_result.returncode == 0, f"stdout:\n{sync_result.stdout}\nstderr:\n{sync_result.stderr}"

    runtime_links = _symlink_entries(caller)
    assert set(runtime_links) == {RUNTIME_ALIAS_NAME}
    assert (caller / RUNTIME_ALIAS_NAME).resolve(strict=True) == plugin_root.resolve()
    assert not _symlink_entries(plugin_root), "Bootstrap links belong in the caller workspace"

    scratch_block = _through_line(_find_shell_block(create_skill, "new-strat-tmp", skill_dir), "new-strat-tmp")
    scratch_result = _run_bash(
        scratch_block + '\nprintf "%s\\n" "$tmp_result"\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    scratch_payload = _json_result_and_caller_cwd(scratch_result, caller)
    assert scratch_payload["created"] is True
    temp_strategy = Path(scratch_payload["strategy_file"]).resolve()
    assert temp_strategy.parent == (plugin_root / "artifacts" / "strat-tasks" / ".tmp").resolve()
    temp_strategy.write_text(STRATEGY_CONTENT, encoding="utf-8")

    output_dir = output_root / "artifacts" / "test-plans"
    feature_dir = output_dir / "fixture_feature"
    env.update(
        {
            "target_dir": str(output_dir),
            "FORCE_OUTPUT_DIR": "false",
            "repo_root": str(plugin_root),
            "strategy_file": str(temp_strategy),
            "feature_dir": str(feature_dir),
        }
    )
    validation_block = _find_shell_block(create_skill, "validate-local-path", skill_dir)
    output_validation = _run_bash(
        validation_block + '\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    assert output_validation.returncode == 0, (
        f"stdout:\n{output_validation.stdout}\nstderr:\n{output_validation.stderr}"
    )
    assert output_validation.stdout.strip().endswith(f"CALLER_CWD={caller}")

    env["target_dir"] = str(plugin_root / "scripts" / "repo.py")
    package_write = _run_bash(validation_block, cwd=caller, env=env)
    assert package_write.returncode != 0, "Output validation must reject writes into the plugin package"

    if delivery_mode == "fullsend":
        env["target_dir"] = str(tmp_path / "outside-target" / "feature")
        target_escape = _run_bash(validation_block, cwd=caller, env=env)
        assert target_escape.returncode != 0, "Fullsend output validation must stay within its target workspace"

        symlink_target = tmp_path / "outside-symlink-target"
        symlink_target.mkdir()
        symlink_path = output_root / "outside-link"
        symlink_path.symlink_to(symlink_target, target_is_directory=True)
        env["target_dir"] = str(symlink_path / "feature")
        symlink_escape = _run_bash(validation_block, cwd=caller, env=env)
        assert symlink_escape.returncode != 0, "Fullsend output validation must reject symlink escapes"
        symlink_path.unlink()

    snapshot_block = _through_line(_find_shell_block(create_skill, "save-snapshot", skill_dir), "save-snapshot")
    snapshot_result = _run_bash(
        snapshot_block + '\nprintf "%s\\n" "$snapshot_result"\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    snapshot_payload = _json_result_and_caller_cwd(snapshot_result, caller)
    assert snapshot_payload["status"] == "ok"
    assert snapshot_payload["source"] == "temp"
    assert Path(snapshot_payload["strategy_file"]).resolve() == (feature_dir / ".source-strategy.md").resolve()
    assert not temp_strategy.exists()

    cases_skill = plugin_root / "skills" / "test-plan-create-cases" / "SKILL.md"
    cases_skill_dir = cases_skill.parent
    test_plan_path = feature_dir / "TestPlan.md"
    write_frontmatter_with_body(
        str(test_plan_path),
        VALID_TEST_PLAN_BODY_FOR_CASES_VALIDATION,
        dict(VALID_TEST_PLAN_DATA),
        "test-plan",
    )
    test_cases_dir = feature_dir / "test_cases"
    test_cases_dir.mkdir(parents=True, exist_ok=True)
    case_path = test_cases_dir / f"{VALID_TEST_CASE_DATA['test_case_id']}.md"
    write_frontmatter_with_body(
        str(case_path),
        "# Verify the handed-off test case\n\n## Objective\nCheck the case fixture.\n",
        dict(VALID_TEST_CASE_DATA),
        "test-case",
    )
    index_path = test_cases_dir / "INDEX.md"
    index_path.write_text(
        f"# Test Cases\n\n- [{VALID_TEST_CASE_DATA['test_case_id']}]({case_path.name})\n",
        encoding="utf-8",
    )

    if delivery_mode == "fullsend":
        update_skill = plugin_root / "skills" / "test-plan-update" / "SKILL.md"
        update_validation_block = _find_shell_block(update_skill, "validate-local-path", update_skill.parent)
        update_env = env.copy()
        update_env.update({"source_type": "local", "feature_dir": str(feature_dir.resolve())})
        update_validation = _run_bash(update_validation_block, cwd=caller, env=update_env)
        assert update_validation.returncode == 0, (
            f"stdout:\n{update_validation.stdout}\nstderr:\n{update_validation.stderr}"
        )
        assert _symlink_entries(caller) == runtime_links, (
            "The rejected symlink escape probe must not add a caller link before the create-cases handoff"
        )

    cases_bootstrap_block = _through_line(
        _find_shell_block(cases_skill, "scripts/bootstrap.sh", cases_skill_dir),
        "scripts/bootstrap.sh",
    )
    cases_bootstrap = _run_bash(cases_bootstrap_block, cwd=caller, env=env)
    assert cases_bootstrap.returncode == 0, f"stdout:\n{cases_bootstrap.stdout}\nstderr:\n{cases_bootstrap.stderr}"
    assert _symlink_entries(caller) == runtime_links

    env["FEATURE_SOURCE"] = str(feature_dir.resolve())
    feature_lookup_block = _find_shell_block(cases_skill, "locate-feature-dir", cases_skill_dir)
    feature_lookup = _run_bash(
        feature_lookup_block
        + '\nprintf "FEATURE_DIR=%s\\nSOURCE_TYPE=%s\\nCALLER_CWD=%s\\n" "$feature_dir" "$source_type" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    assert feature_lookup.returncode == 0, f"stdout:\n{feature_lookup.stdout}\nstderr:\n{feature_lookup.stderr}"
    assert feature_lookup.stdout.strip().endswith(
        f"FEATURE_DIR={feature_dir.resolve()}\nSOURCE_TYPE=local\nCALLER_CWD={caller}"
    )

    env.update({"source_type": "local", "feature_dir": str(feature_dir.resolve())})
    marker_block = _find_shell_block(cases_skill, "discover_feature_dir.py", cases_skill_dir)
    marker_result = _run_bash(
        marker_block + '\nprintf "%s\\n" "$marker_result"\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
        cwd=caller,
        env=env,
    )
    marker_payload = _json_result_and_caller_cwd(marker_result, caller)
    assert marker_payload == {"output_dir": str(output_dir.resolve())}
    assert json.loads((feature_dir / ".test-plan-output-dir.json").read_text(encoding="utf-8")) == marker_payload

    path_validation_block = _find_shell_block(cases_skill, "validate-local-path", cases_skill_dir)
    path_validation = _run_bash(path_validation_block, cwd=caller, env=env)
    assert path_validation.returncode == 0, f"stdout:\n{path_validation.stdout}\nstderr:\n{path_validation.stderr}"

    case_validation_block = _find_shell_block(cases_skill, "validate.py test-cases", cases_skill_dir)
    case_validation_block = case_validation_block.replace("<feature_dir>", shlex.quote(str(feature_dir.resolve())))
    case_validation = _run_bash(case_validation_block, cwd=caller, env=env)
    assert case_validation.returncode == 0, f"stdout:\n{case_validation.stdout}\nstderr:\n{case_validation.stderr}"
    validation_results = _json_documents(case_validation.stdout)
    assert len(validation_results) == 5
    assert all(result.get("valid") is True for result in validation_results)
    assert validation_results[0]["checked"] == 1

    plan_data, _ = read_frontmatter(str(test_plan_path))
    case_data, _ = read_frontmatter(str(case_path))
    assert plan_data["source_key"] == VALID_TEST_CASE_DATA["source_key"]
    assert case_data["test_case_id"] == VALID_TEST_CASE_DATA["test_case_id"]
    assert case_data["objectives"] == VALID_TEST_CASE_DATA["objectives"]
    assert (feature_dir / ".source-strategy.md").read_text(encoding="utf-8") == STRATEGY_CONTENT
    assert index_path.is_file()

    calls = [json.loads(line) for line in Path(env["UV_CALL_LOG"]).read_text(encoding="utf-8").splitlines()]
    assert calls
    assert {Path(call["project_root"]).resolve() for call in calls} == {plugin_root.resolve()}
    if delivery_mode == "fullsend":
        path_validation_calls = [call for call in calls if "validate-local-path" in call["arguments"]]
        assert path_validation_calls
        assert {call["fullsend_target_repo_dir"] for call in path_validation_calls} == {str(output_root.resolve())}
    helper_calls = [call for call in calls if "new-strat-tmp" in call["arguments"]]
    assert helper_calls
    assert any(
        str(caller / link) in call["logical_cwd"] + json.dumps(call["arguments"])
        or link in call["logical_cwd"] + json.dumps(call["arguments"])
        for link in runtime_links
        for call in helper_calls
    ), "A caller-namespace runtime link must serve the documented helper command"
    assert not (caller / "scripts").is_symlink()
    assert {name: (caller / "scripts" / name).read_text(encoding="utf-8") for name in caller_scripts} == caller_scripts
    assert not (caller / "artifacts" / "strat-tasks").exists()


@pytest.mark.parametrize(
    ("prompt_name", "command_marker"),
    [
        pytest.param(
            "review-agent.md",
            "schema test-plan-review",
            id="review-agent",
        ),
        pytest.param(
            "revise-agent.md",
            "auto_revised=true",
            id="revise-agent",
        ),
    ],
)
@pytest.mark.parametrize(
    "layout",
    [
        pytest.param("direct-installed-version", id="direct-installed-version"),
        pytest.param("fullsend-skill-alias", id="fullsend-skill-alias"),
    ],
)
def test_forked_review_prompts_resolve_helpers_after_explicit_skill_dir_substitution(
    tmp_path: Path, prompt_name: str, command_marker: str, layout: str
) -> None:
    plugin_root = _copy_tracked_checkout(REPO_ROOT, tmp_path / "plugin with spaces")
    skill_dir = _skill_dir_for_delivery_layout(plugin_root, "test-plan-review", layout)
    caller = tmp_path / "unrelated caller"
    _make_caller(caller, with_git=False)
    prompt_file = skill_dir / "prompts" / prompt_name
    prompt_text = prompt_file.read_text(encoding="utf-8")
    documented_command = _prompt_frontmatter_command(prompt_text, command_marker)
    assert "{CLAUDE_SKILL_DIR}" in documented_command, f"{prompt_file} must use the skill-dir placeholder"

    feature_dir = tmp_path / "feature directory"
    feature_dir.mkdir()
    review_file = feature_dir / "TestPlanReview.md"
    write_frontmatter(str(review_file), deepcopy(VALID_TEST_PLAN_REVIEW_DATA), "test-plan-review")

    env = _command_environment(skill_dir, tmp_path)
    env.pop("CLAUDE_SKILL_DIR")
    assert "CLAUDE_SKILL_DIR" not in env
    unresolved = _run_bash(documented_command, cwd=caller, env=env)
    assert unresolved.returncode != 0, "A supporting prompt file must not receive implicit skill substitution"

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    declared_substitutions = set(re.findall(r"(?m)^\s*- `?\{([A-Z0-9_]+)\}`?\s*=", skill_text))
    substitutions = {
        "CLAUDE_SKILL_DIR": str(skill_dir),
        "FEATURE_DIR": str(feature_dir),
    }
    resolved_command = documented_command
    for name in re.findall(r"\{([A-Z0-9_]+)\}", documented_command):
        assert name in declared_substitutions, f"{name} must be explicitly substituted by the parent skill"
        resolved_command = resolved_command.replace("{" + name + "}", substitutions[name])

    resolved = _run_bash(resolved_command, cwd=caller, env=env)
    assert resolved.returncode == 0, f"stdout:\n{resolved.stdout}\nstderr:\n{resolved.stderr}"
    uv_calls = [json.loads(line) for line in Path(env["UV_CALL_LOG"]).read_text(encoding="utf-8").splitlines()]
    assert Path(uv_calls[-1]["cwd"]).resolve() == plugin_root.resolve(), (
        "The substituted prompt command must run from the physical plugin root"
    )
    assert Path(uv_calls[-1]["project_root"]).resolve() == plugin_root.resolve(), (
        "The substituted helper must run in the selected plugin's uv project from an unrelated caller"
    )
    if prompt_name == "revise-agent.md":
        review_data, _ = read_frontmatter(str(review_file))
        assert review_data["auto_revised"] is True


@pytest.mark.parametrize(
    ("skill_name", "foreign_entry", "caller_is_plugin_root", "fullsend_target_layout"),
    [
        *[
            pytest.param(skill_name, None, False, None, id=f"entrypoint-{skill_name}")
            for skill_name in LAYOUT_ENTRYPOINT_SKILLS
        ],
        pytest.param("test-plan-create", "file", False, None, id="foreign-file"),
        pytest.param("test-plan-create", "directory", False, None, id="foreign-directory"),
        pytest.param("test-plan-create", "symlink", False, None, id="foreign-symlink"),
        pytest.param("missing-skill", None, False, None, id="invalid-skill-dir"),
        pytest.param("test-plan-create", None, True, None, id="plugin-root-create-helper"),
        pytest.param("test-plan-create-cases", None, True, None, id="plugin-root-cases-helper"),
        pytest.param(
            "test-plan-create",
            None,
            True,
            "distinct",
            id="plugin-root-fullsend-distinct-target",
        ),
        pytest.param(
            "test-plan-create",
            None,
            True,
            "missing",
            id="plugin-root-fullsend-missing-target",
        ),
        pytest.param(
            "test-plan-create",
            None,
            True,
            "same",
            id="fullsend-plugin-root-equals-output",
        ),
        pytest.param(
            "test-plan-create",
            None,
            False,
            "plugin-nested-under-output",
            id="fullsend-plugin-nested-under-output",
        ),
        pytest.param(
            "test-plan-create",
            None,
            False,
            "output-nested-under-plugin",
            id="fullsend-output-nested-under-plugin",
        ),
    ],
)
def test_documented_bootstrap_handles_skills_and_checkout_layouts(
    tmp_path: Path,
    skill_name: str,
    foreign_entry: str | None,
    caller_is_plugin_root: bool,
    fullsend_target_layout: str | None,
) -> None:
    plugin_root = _copy_tracked_checkout(REPO_ROOT, tmp_path / "plugin")
    assert not (plugin_root / ".git").exists()
    assert not _symlink_entries(plugin_root)
    skill_dir = plugin_root / "skills" / skill_name
    if skill_name == "missing-skill":
        skill_dir.mkdir()
    else:
        assert (skill_dir / "SKILL.md").is_file()

    fullsend_target: Path | None = None
    if fullsend_target_layout == "distinct":
        fullsend_target = tmp_path / "fullsend-output"
        fullsend_target.mkdir()
    elif fullsend_target_layout == "missing":
        fullsend_target = tmp_path / "missing-fullsend-output"
        assert not fullsend_target.exists()
    elif fullsend_target_layout == "same":
        fullsend_target = plugin_root
    elif fullsend_target_layout == "plugin-nested-under-output":
        fullsend_target = tmp_path
    elif fullsend_target_layout == "output-nested-under-plugin":
        fullsend_target = plugin_root / "fullsend-output"
        fullsend_target.mkdir()

    if caller_is_plugin_root:
        caller = plugin_root
        caller_scripts = {}
    elif fullsend_target_layout == "output-nested-under-plugin":
        assert fullsend_target is not None
        caller = fullsend_target / "target-workspace"
        caller_scripts = _make_caller(caller, with_git=False)
    else:
        caller = tmp_path / "target-workspace"
        caller_scripts = _make_caller(caller, with_git=False)

    env = _command_environment(skill_dir, tmp_path)
    if fullsend_target_layout is not None:
        assert fullsend_target is not None
        env["FULLSEND_TARGET_REPO_DIR"] = str(fullsend_target)
    elif not caller_is_plugin_root:
        env["FULLSEND_TARGET_REPO_DIR"] = str(caller)
    layout_document = (
        plugin_root / "skills" / "test-plan-create" / "SKILL.md"
        if skill_name == "missing-skill"
        else skill_dir / "SKILL.md"
    )
    fixture_paths = [caller / "pyproject.toml", plugin_root / BOOTSTRAP_SCRIPT, layout_document]
    fixture_paths.extend(caller / "scripts" / name for name in caller_scripts)
    fixture_contents = {path: path.read_text(encoding="utf-8") for path in fixture_paths}
    layout_block = _through_line(
        _find_shell_block(layout_document, "scripts/bootstrap.sh"),
        "scripts/bootstrap.sh",
    )

    first = _run_bash(layout_block, cwd=caller, env=env)
    if skill_name == "missing-skill":
        assert first.returncode != 0, f"bootstrap accepted invalid skill dir: {first.stdout} {first.stderr}"
        runtime_alias = caller / RUNTIME_ALIAS_NAME
        assert not runtime_alias.exists()
        assert not runtime_alias.is_symlink()
        assert not _symlink_entries(plugin_root)
        return

    if fullsend_target_layout is not None:
        assert first.returncode != 0, (
            f"bootstrap accepted invalid Fullsend target layout {fullsend_target_layout!r}: "
            f"stdout:\n{first.stdout}\nstderr:\n{first.stderr}"
        )
        runtime_alias = caller / RUNTIME_ALIAS_NAME
        assert not runtime_alias.exists()
        assert not runtime_alias.is_symlink()
        assert not _symlink_entries(plugin_root)
        assert {path: path.read_text(encoding="utf-8") for path in fixture_contents} == fixture_contents
        return

    assert first.returncode == 0, f"stdout:\n{first.stdout}\nstderr:\n{first.stderr}"
    if caller_is_plugin_root:
        runtime_alias = caller / RUNTIME_ALIAS_NAME
        assert not (plugin_root / ".git").exists()
        assert not runtime_alias.exists()
        assert not runtime_alias.is_symlink()
        assert not _symlink_entries(plugin_root)
        if skill_name == "test-plan-create":
            helper_block = _through_line(
                _find_shell_block(skill_dir / "SKILL.md", "new-strat-tmp", skill_dir),
                "new-strat-tmp",
            )
            helper_result = _run_bash(
                helper_block + '\nprintf "%s\\n" "$tmp_result"\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
                cwd=plugin_root,
                env=env,
            )
            helper_payload = _json_result_and_caller_cwd(helper_result, plugin_root)
            strategy_file = Path(helper_payload["strategy_file"]).resolve()
            assert helper_payload["created"] is True
            assert strategy_file.parent == (plugin_root / "artifacts" / "strat-tasks" / ".tmp").resolve()
            assert strategy_file.is_file()
        else:
            feature_dir = tmp_path / "handoff-feature"
            feature_dir.mkdir()
            output_dir = tmp_path / "handoff-output"
            marker_payload = {"output_dir": str(output_dir.resolve())}
            (feature_dir / ".test-plan-output-dir.json").write_text(json.dumps(marker_payload), encoding="utf-8")
            env.update({"source_type": "local", "feature_dir": str(feature_dir)})
            helper_block = _find_shell_block(skill_dir / "SKILL.md", "discover_feature_dir.py", skill_dir)
            helper_result = _run_bash(
                helper_block + '\nprintf "%s\\n" "$marker_result"\nprintf "CALLER_CWD=%s\\n" "$PWD"\n',
                cwd=plugin_root,
                env=env,
            )
            assert _json_result_and_caller_cwd(helper_result, plugin_root) == marker_payload
        assert not _symlink_entries(plugin_root)
        return

    first_links = _symlink_entries(caller)
    assert set(first_links) == {RUNTIME_ALIAS_NAME}
    assert (caller / RUNTIME_ALIAS_NAME).resolve(strict=True) == plugin_root.resolve()
    assert {name: (caller / "scripts" / name).read_text(encoding="utf-8") for name in caller_scripts} == caller_scripts
    second = _run_bash(layout_block, cwd=caller, env=env)
    assert second.returncode == 0, f"stdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    assert _symlink_entries(caller) == first_links
    assert not _symlink_entries(plugin_root)

    if foreign_entry is None:
        return

    link_path = caller / RUNTIME_ALIAS_NAME
    link_path.unlink()
    foreign_target = tmp_path / "foreign-target"
    if foreign_entry == "file":
        link_path.write_text("foreign file", encoding="utf-8")
    elif foreign_entry == "directory":
        link_path.mkdir()
        (link_path / "sentinel").write_text("foreign directory", encoding="utf-8")
    else:
        foreign_target.mkdir()
        (foreign_target / "sentinel").write_text("keep", encoding="utf-8")
        link_path.symlink_to(foreign_target, target_is_directory=True)

    before_scripts = {name: (caller / "scripts" / name).read_text(encoding="utf-8") for name in caller_scripts}
    result = _run_bash(layout_block, cwd=caller, env=env)
    assert result.returncode != 0, f"bootstrap accepted a foreign {foreign_entry}: {result.stdout} {result.stderr}"
    assert {name: (caller / "scripts" / name).read_text(encoding="utf-8") for name in caller_scripts} == before_scripts
    if foreign_entry == "file":
        assert link_path.read_text(encoding="utf-8") == "foreign file"
    elif foreign_entry == "directory":
        assert (link_path / "sentinel").read_text(encoding="utf-8") == "foreign directory"
    else:
        assert link_path.is_symlink()
        assert os.readlink(link_path) == str(foreign_target)
        assert (foreign_target / "sentinel").read_text(encoding="utf-8") == "keep"


def test_documented_layout_is_shell_only_before_uv_sync(tmp_path: Path) -> None:
    plugin_root = _copy_tracked_checkout(REPO_ROOT, tmp_path / "plugin")
    skill_dir = plugin_root / "skills" / "test-plan-create"
    caller = tmp_path / "unrelated-caller"
    caller_scripts = _make_caller(caller, with_git=False)
    env = _command_environment(skill_dir, tmp_path)
    env["FULLSEND_TARGET_REPO_DIR"] = str(caller)

    failing_bin = tmp_path / "failing-python-bin"
    failing_bin.mkdir()
    python3_calls = tmp_path / "python3-calls.txt"
    python3_stub = failing_bin / "python3"
    python3_stub.write_text(
        f'#!/bin/sh\nprintf "called\\n" >> {shlex.quote(str(python3_calls))}\nexit 97\n',
        encoding="utf-8",
    )
    python3_stub.chmod(0o755)
    env["PATH"] = str(failing_bin) + os.pathsep + env["PATH"]

    layout_block = _through_line(
        _find_shell_block(skill_dir / "SKILL.md", "scripts/bootstrap.sh"),
        "scripts/bootstrap.sh",
    )
    result = _run_bash(layout_block, cwd=caller, env=env)

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert not python3_calls.exists(), "Layout must not invoke python3 before uv sync"
    assert set(_symlink_entries(caller)) == {RUNTIME_ALIAS_NAME}
    assert (caller / RUNTIME_ALIAS_NAME).resolve(strict=True) == plugin_root.resolve()
    assert {name: (caller / "scripts" / name).read_text(encoding="utf-8") for name in caller_scripts} == caller_scripts


@pytest.mark.parametrize("skill_name", ["test-plan-review", "test-plan-score"])
@pytest.mark.parametrize("shell_name", ["sh", "bash", "zsh"])
def test_documented_calibration_json_parses_in_common_shells(skill_name: str, shell_name: str) -> None:
    shell = shutil.which(shell_name)
    if shell is None:
        pytest.skip(f"{shell_name} is not installed")

    block = _find_shell_block(REPO_ROOT / "skills" / skill_name / "SKILL.md", "load_calibration.py")
    parse_lines = [
        line for line in block.splitlines() if "| jq" in line and (".calibration_text" in line or ".warnings" in line)
    ]
    assert len(parse_lines) == 2

    env = os.environ.copy()
    env["calibration_raw"] = json.dumps(
        {"calibration_text": "first line\nsecond line", "warnings": ["warning\ncontinued"]}
    )
    command = "set -e\n" + "\n".join(parse_lines) + '\nprintf "CALIBRATION=%s\\n" "$calibration_text"\n'
    result = subprocess.run(
        [shell, "-c", command],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "CALIBRATION=first line\nsecond line\n"
    assert result.stderr == "warning\ncontinued\n"


def _invoke_fullsend_post_test_plan_hook(tmp_path: Path) -> Path:
    output_base = tmp_path / "host output"
    iteration_output = output_base / "sandbox" / "iteration-1" / "output"
    iteration_output.mkdir(parents=True)
    repo_dir = tmp_path / "downloaded workspace"
    source_feature = repo_dir / "plans" / "example_feature"
    source_feature.mkdir(parents=True)
    (iteration_output / "agent-result.json").write_text(
        json.dumps({"feature_dir": "plans/example_feature"}),
        encoding="utf-8",
    )
    for name, content in {
        "TestPlanReview.md": "# Review\nValid review.\n",
        ".source-strategy.md": "# Strategy\nValid strategy.\n",
        "TestPlan.md": "# Test plan\nValid plan.\n",
        "README.md": "# Feature\nValid feature README.\n",
        ".test-plan-output-dir.json": json.dumps({"output_dir": str(source_feature.parent)}),
    }.items():
        (source_feature / name).write_text(content, encoding="utf-8")

    source_cases = source_feature / "test_cases"
    source_cases.mkdir()
    (source_cases / "INDEX.md").write_text(POST_HOOK_NEW_INDEX, encoding="utf-8")
    (source_cases / "TC-E2E-001.md").write_bytes(POST_HOOK_UPDATED_RETAINED_CASE)
    (source_cases / "TC-E2E-003.md").write_bytes(POST_HOOK_NEW_CASE)

    target_feature = output_base / "plans" / "example_feature"
    target_cases = target_feature / "test_cases"
    target_cases.mkdir(parents=True)
    (target_cases / "INDEX.md").write_text(POST_HOOK_OLD_INDEX, encoding="utf-8")
    (target_cases / "TC-E2E-001.md").write_bytes(POST_HOOK_OLD_RETAINED_CASE)
    (target_cases / "TC-E2E-002.md").write_bytes(POST_HOOK_OLD_REMOVED_CASE)

    (target_cases / "TC-E2E-999.md").write_bytes(POST_HOOK_UNINDEXED_CASE)
    (target_feature / "TC-E2E-777.md").write_bytes(POST_HOOK_OUTSIDE_CASE)

    environment = {
        "FULLSEND_VALIDATED_ITERATION_DIR": str(iteration_output),
        "REPO_DIR": str(repo_dir),
        "FULLSEND_TASK": "/test-plan-create-cases RHAISTRAT-123",
    }
    result = subprocess.run(
        [sys.executable, str(FULLSEND_POST_TEST_PLAN_HOOK)],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return target_cases


def test_post_test_plan_cases_handoff_reconciles_indexed_cases_safely(tmp_path: Path) -> None:
    target_cases = _invoke_fullsend_post_test_plan_hook(tmp_path)

    assert (target_cases / "INDEX.md").read_bytes() == POST_HOOK_NEW_INDEX.encode()
    assert (target_cases / "TC-E2E-001.md").read_bytes() == POST_HOOK_UPDATED_RETAINED_CASE
    assert (target_cases / "TC-E2E-003.md").read_bytes() == POST_HOOK_NEW_CASE
    assert not (target_cases / "TC-E2E-002.md").exists(), "An obsolete indexed case must be removed"
    assert (target_cases / "TC-E2E-999.md").read_bytes() == POST_HOOK_UNINDEXED_CASE
    assert (target_cases.parent / "TC-E2E-777.md").read_bytes() == POST_HOOK_OUTSIDE_CASE
