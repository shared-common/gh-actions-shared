#!/bin/sh
set -eu

python3 - <<'PY'
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), ".github", "scripts"))
from matrix_build import build_gitlab_matrix

matrix = build_gitlab_matrix(
    org_keys=["GH_ORG_TOOLS", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE"],
    group_key="GL_GROUP_TOP_DERIVED",
    subgroup_keys=["GL_GROUP_SUB_TOOLS", "GL_GROUP_SUB_SECOPS", "GL_GROUP_SUB_WIKI", "GL_GROUP_SUB_DIVERGE"],
)
print(json.dumps(matrix, separators=(",", ":")))
PY
