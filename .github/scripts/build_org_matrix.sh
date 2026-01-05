#!/bin/sh
set -eu

sh .github/scripts/bws_export_env_unmasked.sh \
  GH_ORG_TBOX \
  GH_ORG_SECOPS \
  GH_ORG_WIKI \
  GH_ORG_DIVERGE

python3 - <<'PY' >> "${GITHUB_OUTPUT:?}"
import json
import os

org_keys = ("GH_ORG_TBOX", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE")
orgs = [os.environ.get(key, "").strip() for key in org_keys]
missing = [key for key, value in zip(org_keys, orgs) if not value]
if missing:
    raise SystemExit(f"Missing orgs in env: {', '.join(missing)}")
if len(set(orgs)) != len(orgs):
    raise SystemExit("Duplicate org entries")
matrix = {"include": [{"github_org": org} for org in orgs]}
print(f"matrix={json.dumps(matrix)}")
PY
