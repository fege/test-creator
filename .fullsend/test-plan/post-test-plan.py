#!/usr/bin/env python3
import json
import os
import re
import shutil
import stat
import tempfile
from io import BytesIO
from pathlib import Path


def directory(path, create=False):
    if create and not path.exists() and not path.is_symlink():
        path.mkdir()
    mode = path.lstat().st_mode
    if not stat.S_ISDIR(mode):
        raise ValueError(f"directory is missing or is a link: {path}")


def child_dir(root, parts, create=False):
    path = root
    for part in parts:
        path /= part
        directory(path, create=create)
    return path


def open_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError(f"expected a regular file: {path}")
    return os.fdopen(fd, "rb")


def write_atomic(path, source):
    if path.exists() or path.is_symlink():
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f"refusing to replace non-file: {path}")
        source_position = source.tell()
        try:
            with open_regular(path) as existing:
                while True:
                    source_chunk = source.read(64 * 1024)
                    existing_chunk = existing.read(64 * 1024)
                    if source_chunk != existing_chunk:
                        break
                    if not source_chunk:
                        return
        finally:
            source.seek(source_position)
    fd, temp = tempfile.mkstemp(prefix=".test-plan-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            shutil.copyfileobj(source, output)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def indexed_case_names(markdown):
    names = set()
    links = re.finditer(
        r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:[ \t]+[^)\n]*)?\)",
        markdown,
    )
    for match in links:
        name = match.group(1)
        if name.startswith("./"):
            name = name[2:]
        if name.startswith("TC-") and name.endswith(".md") and "/" not in name and "\\" not in name:
            names.add(name)
    return names


validated_iteration = os.environ.get("FULLSEND_VALIDATED_ITERATION_DIR")
repo_dir = os.environ.get("REPO_DIR")
task_words = os.environ.get("FULLSEND_TASK", "").split(maxsplit=1)
if not all((validated_iteration, repo_dir, task_words)):
    raise ValueError("validated iteration, matching workspace, and task are required")
task = task_words[0]
if task not in ("/test-plan-create", "/test-plan-create-cases"):
    raise ValueError(f"unsupported test-plan task: {task}")

result_file = Path(validated_iteration) / "agent-result.json"
repo_arg = Path(repo_dir)
iteration_output = Path(validated_iteration)
if not iteration_output.is_absolute():
    raise ValueError("validated iteration output directory must be absolute")
# Fullsend supplies <output-base>/<sandbox>/iteration-N/output. Keep feature
# artifacts in the shared output base so create and cases update one directory.
if iteration_output.name != "output" or not iteration_output.parent.name.startswith("iteration-"):
    raise ValueError("unexpected Fullsend validated iteration output layout")
target_arg = iteration_output.parent.parent.parent
with open_regular(result_file) as stream:
    result = json.load(stream)
feature = result["feature_dir"]
no_acceptance_criteria = result.get("no_acceptance_criteria", False) is True
if no_acceptance_criteria and task != "/test-plan-create":
    raise ValueError("no_acceptance_criteria applies only to test-plan creation")
if not isinstance(feature, str) or "\\" in feature or any(part in ("", ".", "..") for part in feature.split("/")):
    raise ValueError("feature_dir must be a relative path inside the target workspace")
parts = feature.split("/")
repo = repo_arg.resolve(strict=True)
target = target_arg.resolve(strict=True)
directory(repo_arg)
directory(target_arg)
if repo == target or repo.is_relative_to(target) or target.is_relative_to(repo):
    raise ValueError("downloaded workspace and run output must be disjoint")
source_dir = child_dir(repo, parts)

required = ["TestPlanReview.md", ".source-strategy.md"]
if not no_acceptance_criteria:
    required.extend(("TestPlan.md", "README.md"))
optional = (
    "TestPlan.md",
    "README.md",
    "TestPlanGaps.md",
    ".analysis-endpoints.md",
    ".source-design-spec.md",
    ".analysis-risks.md",
    ".analysis-infra.md",
)
for name in required:
    with open_regular(source_dir / name) as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            raise ValueError(f"required file is empty: {name}")
if (source_dir / "TestPlan.md").exists() != (source_dir / "README.md").exists():
    raise ValueError("plan and README must be present together")
with open_regular(source_dir / ".test-plan-output-dir.json") as stream:
    marker = json.load(stream)
if not isinstance(marker, dict) or not isinstance(marker.get("output_dir"), str):
    raise ValueError("invalid test-plan output directory marker")

source_cases = source_dir / "test_cases"
files = []
if source_cases.exists() or source_cases.is_symlink():
    directory(source_cases)
    files = [
        path
        for path in source_cases.iterdir()
        if path.name == "INDEX.md" or (path.name.startswith("TC-") and path.suffix == ".md")
    ]
    for path in files:
        with open_regular(path) as stream:
            if task == "/test-plan-create-cases" and path.name == "INDEX.md" and os.fstat(stream.fileno()).st_size == 0:
                raise ValueError("required file is empty: test_cases/INDEX.md")
if task == "/test-plan-create-cases" and not any(path.name == "INDEX.md" for path in files):
    raise ValueError("case generation requires test_cases/INDEX.md")

target_dir = child_dir(target, parts, create=True)
for name in ("TestPlanReview.md", ".source-strategy.md") + optional:
    source_path = source_dir / name
    if name in optional and not source_path.exists() and not source_path.is_symlink():
        continue
    with open_regular(source_path) as stream:
        write_atomic(target_dir / name, stream)

marker["output_dir"] = str(target_dir.parent)
with BytesIO((json.dumps(marker) + "\n").encode()) as stream:
    write_atomic(target_dir / ".test-plan-output-dir.json", stream)

stale_case_paths = []
if task == "/test-plan-create-cases":
    target_cases = target_dir / "test_cases"
    if target_cases.exists() or target_cases.is_symlink():
        directory(target_cases)
        previous_index = target_cases / "INDEX.md"
        if previous_index.exists() or previous_index.is_symlink():
            if not stat.S_ISREG(previous_index.lstat().st_mode):
                raise ValueError(f"expected a regular file: {previous_index}")
            with open_regular(previous_index) as stream:
                previous_names = indexed_case_names(stream.read().decode("utf-8"))
            current_names = {path.name for path in files if path.name.startswith("TC-") and path.suffix == ".md"}
            for name in sorted(previous_names - current_names):
                stale_path = target_cases / name
                if stale_path.exists() or stale_path.is_symlink():
                    if not stat.S_ISREG(stale_path.lstat().st_mode):
                        raise ValueError(f"refusing to remove non-file: {stale_path}")
                    with open_regular(stale_path):
                        pass
                    stale_case_paths.append(stale_path)

if files:
    target_cases = child_dir(target_dir, ["test_cases"], create=True)
    for path in files:
        with open_regular(path) as stream:
            write_atomic(target_cases / path.name, stream)
    if task == "/test-plan-create-cases":
        for stale_path in stale_case_paths:
            if not stat.S_ISREG(stale_path.lstat().st_mode):
                raise ValueError(f"refusing to remove non-file: {stale_path}")
            with open_regular(stale_path):
                pass
            stale_path.unlink()
print(f"Copied test-plan handoff: {target_dir}")
