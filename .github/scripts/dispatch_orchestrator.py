import json
import os
from pathlib import Path

from _common import (
    get_installation_token_for_org,
    github_request,
    require_env,
    require_secret,
    validate_repo_full_name,
)


def dispatch(token: str, org: str, repo: str, payload: dict) -> None:
    github_request(token, "POST", f"/repos/{org}/{repo}/dispatches", {"event_type": "orchestrator", "client_payload": payload})


def normalize_payload(payload: dict) -> dict:
    repo_full = payload.get("repo_full_name")
    org, repo = validate_repo_full_name(repo_full)
    job_type = payload.get("job_type") or "polling"
    if job_type not in {"create", "polling", "sync"}:
        raise SystemExit(f"Unsupported job_type: {job_type}")
    payload["repo_full_name"] = f"{org}/{repo}"
    payload["job_type"] = job_type
    return payload


def main() -> int:
    org = require_env("TARGET_ORG")
    orchestrator_repo = require_env("ORCHESTRATOR_REPO")
    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")
    input_path = os.environ.get("INPUT_PATH")

    token = get_installation_token_for_org(app_id, pem_path, install_json, org)

    if input_path:
        try:
            payload_data = json.loads(Path(input_path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SystemExit(f"Missing INPUT_PATH file: {input_path}") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc
    else:
        payload_data = None

    if isinstance(payload_data, list):
        for item in payload_data:
            if isinstance(item, dict):
                dispatch(token, org, orchestrator_repo, normalize_payload(item))
        return 0
    if isinstance(payload_data, dict):
        dispatch(token, org, orchestrator_repo, normalize_payload(payload_data))
        return 0

    repo_full = os.environ.get("REPO_FULL_NAME")
    if not repo_full:
        raise SystemExit("Missing INPUT_PATH or REPO_FULL_NAME")
    payload = {"repo_full_name": repo_full, "job_type": os.environ.get("JOB_TYPE", "polling")}
    payload = normalize_payload(payload)
    dispatch(token, org, orchestrator_repo, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
