#!/bin/sh
set -eu

python3 - <<'PY'
import json
import os

org_keys = ("GH_ORG_TBOX", "GH_ORG_SECOPS", "GH_ORG_WIKI", "GH_ORG_DIVERGE")
group_keys = (
    "GL_GROUP_ZFORKS",
    "GL_GROUP_TBOX",
    "GL_GROUP_SECOPS",
    "GL_GROUP_WIKI",
    "GL_GROUP_ZDIVERGE",
    "GL_GROUP_GENERAL",
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
            "github_org": env["GH_ORG_TBOX"],
            "gitlab_group": env["GL_GROUP_ZFORKS"],
            "gitlab_subgroup": env["GL_GROUP_TBOX"],
        },
        {
            "github_org": env["GH_ORG_SECOPS"],
            "gitlab_group": env["GL_GROUP_ZFORKS"],
            "gitlab_subgroup": env["GL_GROUP_SECOPS"],
        },
        {
            "github_org": env["GH_ORG_WIKI"],
            "gitlab_group": env["GL_GROUP_ZFORKS"],
            "gitlab_subgroup": env["GL_GROUP_WIKI"],
        },
        {
            "github_org": env["GH_ORG_DIVERGE"],
            "gitlab_group": env["GL_GROUP_ZDIVERGE"],
            "gitlab_subgroup": env["GL_GROUP_GENERAL"],
        },
    ]
}
print(json.dumps(matrix))
PY
