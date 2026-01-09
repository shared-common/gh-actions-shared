from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Iterable, List

from secret_env import read_optional_value

_SECRET_KEYS = (
    "GITHUB_APP_TOKEN",
    "GL_TOKEN_DERIVED",
    "GH_ORG_SHARED_APP_PEM",
    "GH_ORG_SHARED_APP_ID",
    "BWS_ACCESS_TOKEN",
)


@lru_cache(maxsize=1)
def _secret_values() -> List[str]:
    values: List[str] = []
    for key in _SECRET_KEYS:
        try:
            value = read_optional_value(key, allow_env=False)
        except ValueError:
            value = None
        if value:
            values.append(value)
    return values


def redact_text(text: str) -> str:
    redacted = text
    for secret in _secret_values():
        redacted = redacted.replace(secret, "***")
    return redacted


def redact_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, str):
            redacted[key] = redact_text(value)
        else:
            redacted[key] = value
    return redacted


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **redact_fields(fields)}
    print(json.dumps(payload, separators=(",", ":")))
