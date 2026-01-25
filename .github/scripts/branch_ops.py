from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from _common import (
    branch_exists,
    create_branch,
    get_branch_sha,
    get_installation_token_for_org,
    require_env,
    require_secret,
    update_branch,
)


def load_input() -> dict:
    path = os.environ.get("INPUT_PATH")
    if not path:
        raise SystemExit("Missing INPUT_PATH")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def branch_plan() -> dict:
    prefix = require_secret("GIT_BRANCH_PREFIX")
    main = require_secret("GIT_BRANCH_MAIN")
    staging = require_secret("GIT_BRANCH_STAGING")
    release = require_secret("GIT_BRANCH_RELEASE")
    snapshot = require_secret("GIT_BRANCH_SNAPSHOT")
    feature = require_secret("GIT_BRANCH_FEATURE")
    order = [main, staging, release, snapshot, feature]
    return {
        "prefix": prefix,
        "order": order,
        "branches": {
            "main": f"{prefix}/{main}",
            "staging": f"{prefix}/{staging}",
            "release": f"{prefix}/{release}",
            "snapshot": f"{prefix}/{snapshot}",
            "feature": f"{prefix}/{feature}",
        },
    }


def get_base_sha(input_data: dict, org: str, repo: str, app_id: str, pem_path: str, install_json: str) -> str:
    default_branch = input_data.get("repo_default_branch") or "main"
    base_token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    if input_data.get("repo_parent_full_name"):
        parent_full = input_data.get("repo_parent_full_name")
        if isinstance(parent_full, str) and "/" in parent_full:
            parent_org, parent_repo = parent_full.split("/", 1)
            parent_branch = input_data.get("repo_parent_default_branch") or default_branch
            parent_token = (
                base_token
                if parent_org == org
                else get_installation_token_for_org(app_id, pem_path, install_json, parent_org)
            )
            return get_branch_sha(parent_token, parent_org, parent_repo, str(parent_branch))
    return get_branch_sha(base_token, org, repo, str(default_branch))


def main() -> int:
    input_data = load_input()
    repo_full = input_data.get("repo_full_name")
    if not isinstance(repo_full, str) or "/" not in repo_full:
        raise SystemExit("Invalid repo_full_name")
    org, repo = repo_full.split("/", 1)
    job_type = input_data.get("job_type") or "create"

    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")

    plan = branch_plan()
    prefix = plan["prefix"]
    order: List[str] = plan["order"]

    token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    base_sha = get_base_sha(input_data, org, repo, app_id, pem_path, install_json)

    results: Dict[str, List[str]] = {"created": [], "updated": [], "skipped": []}

    for name in order:
        full = f"{prefix}/{name}"
        if branch_exists(token, org, repo, full):
            results["skipped"].append(full)
            continue
        create_branch(token, org, repo, full, base_sha)
        results["created"].append(full)

    if job_type in {"polling", "sync"}:
        for name in [plan["branches"]["main"], plan["branches"]["staging"]]:
            try:
                current = get_branch_sha(token, org, repo, name)
            except SystemExit:
                current = ""
            if current != base_sha:
                update_branch(token, org, repo, name, base_sha, force=True)
                results["updated"].append(name)

    output_path = os.environ.get("OUTPUT_PATH")
    payload = {"repo": repo_full, "job_type": job_type, "results": results}
    if output_path:
        Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
