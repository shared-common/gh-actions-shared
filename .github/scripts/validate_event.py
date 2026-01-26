import os

from _common import config_path, load_json, require_secret
from event_validation import validate_event_context


def main() -> int:
    event_context = os.environ.get("EVENT_CONTEXT_PATH")
    event_name = os.environ.get("EVENT_NAME")
    expected_action = os.environ.get("EXPECTED_EVENT_ACTION")
    if not event_context or not event_name or not expected_action:
        raise SystemExit("EVENT_CONTEXT_PATH, EVENT_NAME, and EXPECTED_EVENT_ACTION are required")

    event = load_json(event_context, "event context")
    if not isinstance(event, dict):
        raise SystemExit("Event context must be a JSON object")

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
