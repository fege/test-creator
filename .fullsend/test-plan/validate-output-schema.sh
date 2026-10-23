#!/usr/bin/env bash
set -euo pipefail

: "${FULLSEND_OUTPUT_SCHEMA:?FULLSEND_OUTPUT_SCHEMA must be set}"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

python3 - "$FULLSEND_OUTPUT_SCHEMA" <<'PY'
import json
import sys
from pathlib import Path

from jsonschema import validate

result = json.loads(Path("output/agent-result.json").read_text())
schema = json.loads(Path(sys.argv[1]).read_text())
validate(instance=result, schema=schema)
PY

# Fullsend runs this on the host with TARGET_REPO_DIR set to the extracted workspace (empty in the
# post-loop sweep, which then fails). Check the files post-test-plan.py requires before it runs.
python3 "$script_dir/check-handoff-files.py" output/agent-result.json "${TARGET_REPO_DIR:-}"
