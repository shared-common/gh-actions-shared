import json
import os
from pathlib import Path
from typing import Dict, List

from _common import (
    branch_exists,
    create_branch,
    get_branch_sha,
    get_installation_token_for_org,
    parse_installations,
    require_env,
    require_secret,
    update_branch,
    validate_ref_name,
    validate_repo_full_name,
)
from branch_policy import BranchPolicy, load_branch_policy


def load_input() -> dict:
    path = os.environ.get("INPUT_PATH")
    if not path:
        raise SystemExit("Missing INPUT_PATH")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing INPUT_PATH file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc


def _coerce_branch(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SystemExit(f"Invalid {label}")
    validate_ref_name(value, label)
    return value


def get_base_sha(
    input_data: dict, org: str, repo: str, app_id: str, pem_path: str, install_json: str
) -> str:
    default_branch = _coerce_branch(input_data.get("repo_default_branch") or "main", "repo_default_branch")
    base_token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    install_map = parse_installations(install_json)
    if input_data.get("repo_parent_full_name"):
        parent_full = input_data.get("repo_parent_full_name")
        if isinstance(parent_full, str) and "/" in parent_full:
            parent_org, parent_repo = validate_repo_full_name(parent_full)
            parent_branch = _coerce_branch(
                input_data.get("repo_parent_default_branch") or default_branch, "repo_parent_default_branch"
            )
            if parent_org != org and parent_org not in install_map:
                return get_branch_sha(base_token, org, repo, str(default_branch))
            parent_token = (
                base_token
                if parent_org == org
                else get_installation_token_for_org(app_id, pem_path, install_json, parent_org)
            )
            return get_branch_sha(parent_token, parent_org, parent_repo, parent_branch)
    return get_branch_sha(base_token, org, repo, str(default_branch))


def main() -> int:
    input_data = load_input()
    repo_full = input_data.get("repo_full_name")
    org, repo = validate_repo_full_name(repo_full)
    job_type = input_data.get("job_type") or "create"
    if job_type not in {"create", "polling", "sync"}:
        raise SystemExit(f"Unsupported job_type: {job_type}")

    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")

    target_org = os.environ.get("TARGET_ORG")
    if target_org and target_org != org:
        raise SystemExit("repo_full_name org does not match target org")

    policy_path = os.environ.get("BRANCH_POLICY_PATH")
    policy: BranchPolicy = load_branch_policy(policy_path)

    token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    base_sha = get_base_sha(input_data, org, repo, app_id, pem_path, install_json)

    results: Dict[str, List[str]] = {"created": [], "updated": [], "skipped": []}

    for spec in policy.order:
        full = spec.full_name
        if branch_exists(token, org, repo, full):
            results["skipped"].append(full)
            continue
        create_branch(token, org, repo, full, base_sha)
        results["created"].append(full)

    if job_type in {"polling", "sync"}:
        for spec in policy.order:
            if not spec.update:
                continue
            name = spec.full_name
            try:
                current = get_branch_sha(token, org, repo, name)
            except SystemExit:
                current = ""
            if current != base_sha:
                update_branch(token, org, repo, name, base_sha, force=True)
                results["updated"].append(name)

    output_path = os.environ.get("OUTPUT_PATH")
    payload = {"repo": repo_full, "job_type": job_type, "results": results}
    event_id = input_data.get("event_id")
    if isinstance(event_id, str) and event_id:
        payload["event_id"] = event_id
    if output_path:
        Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
