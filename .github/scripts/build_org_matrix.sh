#!/bin/sh
set -eu

python3 - <<'PY' >> "${GITHUB_OUTPUT:?}"
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), ".github", "scripts"))
from secret_env import read_required_secret_file

org_keys = ("GH_ORG_TOOLS", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE")
orgs = [read_required_secret_file(key).strip() for key in org_keys]
missing = [key for key, value in zip(org_keys, orgs) if not value]
if missing:
    raise SystemExit(f"Missing orgs in env: {', '.join(missing)}")
if len(set(orgs)) != len(orgs):
    raise SystemExit("Duplicate org entries")
matrix = {"include": [{"github_org": org} for org in orgs]}
print(f"matrix={json.dumps(matrix)}")
PY
