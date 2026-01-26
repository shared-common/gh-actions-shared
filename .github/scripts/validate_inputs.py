import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from _common import config_path, require_secret, validate_ref_name, validate_repo_full_name
from event_validation import validate_event_context
from json_schema import load_json, validate

ALLOWED_JOB_TYPES = {"create", "polling", "sync"}


def load_payload() -> Dict[str, Any]:
    input_path = os.environ.get("INPUT_PATH")
    if input_path:
        try:
            return json.loads(Path(input_path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SystemExit(f"Missing INPUT_PATH file: {input_path}") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("Missing INPUT_PATH and GITHUB_EVENT_PATH")
    data = load_json(event_path, "GITHUB_EVENT_PATH")
    payload = data.get("client_payload") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        raise SystemExit("Missing/invalid client_payload in event")
    return payload


def validate_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    if "job_type" not in payload:
        payload["job_type"] = "create"
    schema_path = os.environ.get("INPUT_SCHEMA_PATH", config_path("inputs.schema.json"))
    schema = load_json(schema_path, "inputs schema")
    validate(payload, schema)

    org, repo = validate_repo_full_name(payload.get("repo_full_name"))
    target_org = os.environ.get("TARGET_ORG")
    if target_org and org != target_org:
        raise SystemExit("repo_full_name org does not match target org")

    job_type = payload.get("job_type")
    if job_type not in ALLOWED_JOB_TYPES:
        raise SystemExit(f"Unsupported job_type: {job_type}")

    default_branch = payload.get("repo_default_branch")
    if isinstance(default_branch, str):
        validate_ref_name(default_branch, "repo_default_branch")

    parent_full = payload.get("repo_parent_full_name")
    if isinstance(parent_full, str):
        validate_repo_full_name(parent_full)
        parent_branch = payload.get("repo_parent_default_branch")
        if isinstance(parent_branch, str):
            validate_ref_name(parent_branch, "repo_parent_default_branch")
        if payload.get("repo_is_fork") is False:
            raise SystemExit("repo_parent_full_name provided but repo_is_fork is false")

    return payload, org


def maybe_validate_event_context() -> None:
    event_context_path = os.environ.get("EVENT_CONTEXT_PATH")
    event_name = os.environ.get("EVENT_NAME")
    if not event_context_path and not event_name:
        return
    if not event_context_path or not event_name:
        raise SystemExit("EVENT_CONTEXT_PATH and EVENT_NAME are required together")

    event = load_json(event_context_path, "event context")
    if not isinstance(event, dict):
        raise SystemExit("Event context must be a JSON object")

    expected_action = os.environ.get("EXPECTED_EVENT_ACTION")
    target_org = os.environ.get("TARGET_ORG")
    allowlist_path = os.environ.get("EVENT_ALLOWLIST_PATH", config_path("event-allowlist.json"))
    install_json = require_secret("GH_INSTALL_JSON")
    validate_event_context(
        event,
        event_name=event_name,
        expected_action=expected_action,
        target_org=target_org,
        allowlist_path=allowlist_path,
        install_json=install_json,
    )


def main() -> int:
    maybe_validate_event_context()
    payload = load_payload()
    payload, _ = validate_payload(payload)
    output = Path(os.environ.get("OUTPUT_PATH", "validated.json"))
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
