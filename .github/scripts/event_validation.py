from typing import Any, Dict, Optional

from _common import allowed_orgs, load_json, parse_installations


def _ensure_dict(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be a JSON object")
    return value


def validate_event_context(
    event: Dict[str, Any],
    *,
    event_name: str,
    expected_action: Optional[str],
    target_org: Optional[str],
    allowlist_path: str,
    install_json: Optional[str],
) -> None:
    allowlist = load_json(allowlist_path, "event allowlist")
    if not isinstance(allowlist, dict):
        raise SystemExit("Event allowlist must be a JSON object")
    allowed_actions = allowlist.get(event_name)
    if not isinstance(allowed_actions, list):
        raise SystemExit(f"Event '{event_name}' is not allowed")

    action = event.get("action")
    if event_name == "workflow_dispatch":
        inputs = event.get("inputs")
        if not isinstance(inputs, dict):
            raise SystemExit("workflow_dispatch inputs missing from event")
        dispatch_action = inputs.get("dispatch_action")
        if not isinstance(dispatch_action, str):
            raise SystemExit("workflow_dispatch dispatch_action missing from event inputs")
        if allowed_actions and dispatch_action not in allowed_actions:
            raise SystemExit(f"Event action '{dispatch_action}' is not allowed")
        if expected_action and dispatch_action != expected_action:
            raise SystemExit(f"Unexpected event action '{dispatch_action}'")
    elif event_name == "repository_dispatch":
        if not isinstance(action, str):
            raise SystemExit("repository_dispatch action missing from event")
        if allowed_actions and action not in allowed_actions:
            raise SystemExit(f"Event action '{action}' is not allowed")
        if expected_action and action != expected_action:
            raise SystemExit(f"Unexpected event action '{action}'")
    elif expected_action and expected_action not in allowed_actions:
        raise SystemExit(f"Event '{event_name}' does not allow '{expected_action}'")

    if target_org:
        repository = event.get("repository")
        if isinstance(repository, dict):
            owner = repository.get("owner")
            if isinstance(owner, dict):
                owner_login = owner.get("login")
                if isinstance(owner_login, str) and owner_login != target_org:
                    raise SystemExit("Event repository owner does not match target org")

    if install_json:
        mapping = parse_installations(install_json)
        if target_org and mapping:
            expected_id = mapping.get(target_org)
            if not expected_id:
                raise SystemExit(f"Target org '{target_org}' not in installation mapping")
            installation = _ensure_dict(event.get("installation", {}), "installation")
            install_id = installation.get("id")
            if event_name == "repository_dispatch":
                if install_id != expected_id:
                    raise SystemExit("Installation id does not match target org")


def allowed_orgs_from_installations(install_json: str) -> list[str]:
    return allowed_orgs(install_json)
