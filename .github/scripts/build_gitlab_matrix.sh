#!/bin/sh
set -eu

python3 - <<'PY'
import json
import os

org_keys = ("GH_ORG_TOOLS", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE")
group_keys = (
    "GL_GROUP_TOP_DERIVED",
    "GL_GROUP_SUB_TOOLS",
    "GL_GROUP_SUB_SECOPS",
    "GL_GROUP_SUB_WIKI",
    "GL_GROUP_SUB_DIVERGE",
)
env = {key: os.environ.get(key, "").strip() for key in org_keys + group_keys}
missing = [key for key, value in env.items() if not value]
if missing:
    raise SystemExit(f"Missing config in env: {', '.join(missing)}")
dupes = sorted(
    {env[key] for key in org_keys if env[key] and list(env.values()).count(env[key]) > 1}
)
if dupes:
    raise SystemExit(f"Duplicate org entries: {', '.join(dupes)}")
matrix = {
    "include": [
        {
            "github_org": env["GH_ORG_TOOLS"],
            "gitlab_group": env["GL_GROUP_TOP_DERIVED"],
            "gitlab_subgroup": env["GL_GROUP_SUB_TOOLS"],
        },
        {
            "github_org": env["GH_ORG_SECOPS"],
            "gitlab_group": env["GL_GROUP_TOP_DERIVED"],
            "gitlab_subgroup": env["GL_GROUP_SUB_SECOPS"],
        },
        {
            "github_org": env["GH_ORG_WIKI"],
            "gitlab_group": env["GL_GROUP_TOP_DERIVED"],
            "gitlab_subgroup": env["GL_GROUP_SUB_WIKI"],
        },
        {
            "github_org": env["GH_ORG_DIVERGE"],
            "gitlab_group": env["GL_GROUP_TOP_DERIVED"],
            "gitlab_subgroup": env["GL_GROUP_SUB_DIVERGE"],
        },
    ]
}
print(json.dumps(matrix))
PY
