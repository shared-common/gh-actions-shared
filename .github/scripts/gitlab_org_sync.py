from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from _common import config_path, get_installation_id_for_org, get_installation_token, list_org_repos, require_env, require_secret
from gitlab_sync_profile import resolve_profile_group_path
from gitlab_sync import run_sync
from repo_filters import apply_filters


PROFILE_MAPPING_KEYS = {
    "upstream": "GH_ORG_UPSTREAM",
    "xf-main": "GH_ORG_XF_MAIN",
    "xf-secops": "GH_ORG_XF_SECOPS",
    "xf-checkout": "GH_ORG_XF_CHECKOUT",
}


def _prefix_results(repo_full_name: str, results: dict) -> dict:
    prefixed: Dict[str, List[str]] = {"created": [], "updated": [], "skipped": []}
    for key in prefixed:
        values = results.get(key, [])
        if isinstance(values, list):
            prefixed[key].extend(f"{repo_full_name}:{value}" for value in values)
    return prefixed


def _resolve_gitlab_group_path(target_org: str, target_profile: str) -> str:
    mapping_file = os.environ.get("GL_MAPPING_JSON_FILE", "").strip()
    if mapping_file:
        try:
            mapping = json.loads(require_secret("GL_MAPPING_JSON"))
        except json.JSONDecodeError as exc:
            raise SystemExit("GL_MAPPING_JSON is not valid JSON") from exc
        if isinstance(mapping, dict):
            alias_key = PROFILE_MAPPING_KEYS.get(target_profile)
            for key in (target_org, target_profile, alias_key):
                if not key:
                    continue
                value = mapping.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return resolve_profile_group_path(target_profile, require_secret)


def main() -> int:
    target_org = require_env("TARGET_ORG")
    target_profile = require_env("TARGET_PROFILE")
    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    filters_path = os.environ.get("REPO_FILTERS_PATH", config_path("repo-filters.json"))
    gitlab_group_path = _resolve_gitlab_group_path(target_org, target_profile)

    installation_id = get_installation_id_for_org(app_id, pem_path, target_org)
    token = get_installation_token(app_id, pem_path, installation_id)
    repos = [repo for repo in list_org_repos(token, target_org) if not repo.get("archived")]
    if filters_path:
        repos = apply_filters(repos, filters_path)

    aggregate: Dict[str, List[str]] = {"created": [], "updated": [], "skipped": []}
    errors: List[str] = []

    for repo in repos:
        if not isinstance(repo, dict):
            continue
        repo_full_name = repo.get("full_name")
        repo_default_branch = repo.get("default_branch")
        if not isinstance(repo_full_name, str) or not isinstance(repo_default_branch, str):
            errors.append("invalid_repo_metadata")
            continue
        parent = repo.get("parent") if isinstance(repo.get("parent"), dict) else None
        input_data = {
            "repo_full_name": repo_full_name,
            "job_type": "sync",
            "repo_default_branch": repo_default_branch,
            "repo_is_fork": bool(repo.get("fork")),
            "repo_parent_full_name": parent.get("full_name") if isinstance(parent, dict) else None,
            "repo_parent_default_branch": parent.get("default_branch") if isinstance(parent, dict) else None,
            "action": "sync",
            "ref": None,
            "after": None,
            "event_name": "schedule",
            "delivery_id": f"sync-{target_org}",
            "org_login": target_org,
            "repo_id": int(repo.get("id") or 0),
            "source_repo_full_name": parent.get("full_name") if isinstance(parent, dict) else None,
            "gitlab_group_path": gitlab_group_path,
        }
        try:
            payload = run_sync(
                input_data,
                gh_install_token=token,
                allow_project_create=True,
                protect_tracked_branches=True,
                bootstrap_required_branches=False,
                skip_missing_source_branches=True,
            )
        except SystemExit as exc:
            message = str(exc) or "sync_failed"
            errors.append(f"{repo_full_name}:{message}")
            continue
        except Exception as exc:  # pragma: no cover
            errors.append(f"{repo_full_name}:{exc}")
            continue

        prefixed = _prefix_results(repo_full_name, payload.get("results", {}))
        for key in aggregate:
            aggregate[key].extend(prefixed[key])

    output = {
        "org": target_org,
        "profile": target_profile,
        "job_type": "sync",
        "results": aggregate,
        "errors": errors,
    }
    output_path = Path(os.environ.get("OUTPUT_PATH", "summary.json"))
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(output_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
