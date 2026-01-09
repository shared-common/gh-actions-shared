#!/bin/sh
set -eu

python3 - <<'PY' >> "${GITHUB_OUTPUT:?}"
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), ".github", "scripts"))
from secret_env import read_required_secret_file


def _ensure_secret_file(name: str) -> None:
    file_key = f"{name}_FILE"
    if os.environ.get(file_key):
        return
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        candidate = os.path.join(runner_temp, "bws", name)
        if os.path.exists(candidate):
            os.environ[file_key] = candidate
            return
    raise SystemExit(f"Missing required env var: {file_key}")

org_keys = ("GH_ORG_TOOLS", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE")
for key in org_keys:
    _ensure_secret_file(key)
orgs = [read_required_secret_file(key).strip() for key in org_keys]
missing = [key for key, value in zip(org_keys, orgs) if not value]
if missing:
    raise SystemExit(f"Missing orgs in env: {', '.join(missing)}")
if len(set(orgs)) != len(orgs):
    raise SystemExit("Duplicate org entries")
matrix = {"include": [{"github_org": org} for org in orgs]}
print(f"matrix={json.dumps(matrix)}")
PY
