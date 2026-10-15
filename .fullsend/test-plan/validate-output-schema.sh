#!/usr/bin/env bash
set -euo pipefail

: "${FULLSEND_OUTPUT_SCHEMA:?FULLSEND_OUTPUT_SCHEMA must be set}"

python3 - "$FULLSEND_OUTPUT_SCHEMA" <<'PY'
import json
import sys
from pathlib import Path

from jsonschema import validate

result = json.loads(Path("output/agent-result.json").read_text())
schema = json.loads(Path(sys.argv[1]).read_text())
validate(instance=result, schema=schema)
PY
