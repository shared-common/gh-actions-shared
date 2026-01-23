#!/bin/sh
set -eu

python3 - <<'PY' >> "${GITHUB_OUTPUT:?}"
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), ".github", "scripts"))
from matrix_build import build_org_matrix

matrix = build_org_matrix(["GH_ORG_TOOLS", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE", "GH_ORG_CHECKOUT"])
print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")
PY
