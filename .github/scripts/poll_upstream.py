import json
import os
from pathlib import Path
from typing import List

from _common import (
    allowed_orgs,
    config_path,
    get_branch_sha,
    get_installation_token_for_org,
    get_repo,
    list_org_repos,
    require_env,
    require_secret,
    validate_ref_name,
)
from repo_filters import apply_filters
from log_sanitize import sanitize


def audit_log(message: str) -> None:
    print(sanitize(message))


def main() -> int:
    org = require_env("TARGET_ORG")
    app_id = require_secret("GH_ORG_POLLING_APP_ID")
    pem_path = require_env("GH_ORG_POLLING_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")
    prefix = require_secret("GIT_BRANCH_PREFIX")
    main_branch = require_secret("GIT_BRANCH_MAIN")

    validate_ref_name(prefix, "GIT_BRANCH_PREFIX")
    validate_ref_name(main_branch, "GIT_BRANCH_MAIN")

    if org not in allowed_orgs(install_json):
        raise SystemExit(f"Target org '{org}' is not in installation mapping")

    token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    repos = list_org_repos(token, org)
    repos = apply_filters(repos, os.environ.get("REPO_FILTERS_PATH", config_path("repo-filters.json")))

    payloads: List[dict] = []
    for repo in repos:
        name = repo.get("name")
        if not isinstance(name, str) or not name:
            continue
        details = get_repo(token, org, name)
        if not details.get("fork"):
            continue
        full_name = details.get("full_name")
        if not isinstance(full_name, str) or "/" not in full_name:
            continue
        parent = details.get("parent")
        if not isinstance(parent, dict):
            continue
        parent_full = parent.get("full_name")
        parent_branch = parent.get("default_branch")
        if not isinstance(parent_full, str) or not isinstance(parent_branch, str):
            continue
        try:
            validate_ref_name(parent_branch, "parent default branch")
        except SystemExit:
            continue
        parent_org, parent_repo = parent_full.split("/", 1)
        parent_token = (
            token if parent_org == org else get_installation_token_for_org(app_id, pem_path, install_json, parent_org)
        )
        try:
            upstream_sha = get_branch_sha(parent_token, parent_org, parent_repo, parent_branch)
            fork_sha = get_branch_sha(token, org, name, f"{prefix}/{main_branch}")
        except SystemExit:
            continue
        if upstream_sha != fork_sha:
            payloads.append(
                {
                    "repo_full_name": full_name,
                    "repo_default_branch": details.get("default_branch"),
                    "repo_is_fork": True,
                    "repo_parent_full_name": parent_full,
                    "repo_parent_default_branch": parent_branch,
                    "job_type": "polling",
                }
            )
            audit_log(
                f"[audit] upstream divergence org={org} repo={full_name} parent={parent_full} branch={parent_branch}"
            )

    output = Path(os.environ.get("OUTPUT_PATH", "polling.json"))
    output.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    audit_log(f"[audit] poll summary org={org} payloads={len(payloads)}")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
