import os

from _common import config_path, load_json, require_secret
from event_validation import validate_event_context


def _parse_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise SystemExit(f"{label} must be an integer")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SystemExit(f"{label} must be an integer")
    if parsed <= 0:
        raise SystemExit(f"{label} must be a positive integer")
    return parsed


def _extract_app_id(event: dict) -> int:
    if "app_id" in event:
        return _parse_int(event.get("app_id"), "app_id")
    app = event.get("app")
    if isinstance(app, dict) and "id" in app:
        return _parse_int(app.get("id"), "app.id")
    installation = event.get("installation")
    if isinstance(installation, dict) and "app_id" in installation:
        return _parse_int(installation.get("app_id"), "installation.app_id")
    raise SystemExit("app_id missing from event context")


def _validate_sender(event: dict) -> None:
    sender = event.get("sender")
    if not isinstance(sender, dict):
        raise SystemExit("sender must be a JSON object")
    sender_type = sender.get("type")
    if sender_type not in ("User", "Bot"):
        raise SystemExit("sender.type must be User or Bot")
    _parse_int(sender.get("id"), "sender.id")
    expected_app_id = _load_expected_app_id()
    app_id = _extract_app_id(event)
    if app_id != expected_app_id:
        raise SystemExit("app_id does not match expected GitHub App id")


def _load_expected_app_id() -> int:
    for key in ("GH_ORG_SHARED_APP_ID", "GH_ORG_POLLING_APP_ID"):
        file_path = os.environ.get(f"{key}_FILE", "").strip()
        if file_path:
            return _parse_int(require_secret(key), key)
    raise SystemExit("Missing required secret file env var: GH_ORG_SHARED_APP_ID_FILE or GH_ORG_POLLING_APP_ID_FILE")


def main() -> int:
    event_context = os.environ.get("EVENT_CONTEXT_PATH")
    event_name = os.environ.get("EVENT_NAME")
    expected_action = os.environ.get("EXPECTED_EVENT_ACTION")
    if not event_context or not event_name or not expected_action:
        raise SystemExit("EVENT_CONTEXT_PATH, EVENT_NAME, and EXPECTED_EVENT_ACTION are required")

    event = load_json(event_context, "event context")
    if not isinstance(event, dict):
        raise SystemExit("Event context must be a JSON object")

    _validate_sender(event)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
