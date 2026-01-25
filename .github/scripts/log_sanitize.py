from __future__ import annotations

import os
import re

SECRET_KEYS = [
    "BWS_ACCESS_TOKEN",
    "GH_ORG_SHARED_APP_PEM",
    "GH_ORG_SHARED_APP_ID",
]


def sanitize(text: str) -> str:
    sanitized = text
    for key in SECRET_KEYS:
        value = os.environ.get(key)
        if value:
            sanitized = sanitized.replace(value, "***")
    sanitized = re.sub(r"[A-Fa-f0-9]{32,}", "***", sanitized)
    return sanitized


if __name__ == "__main__":
    import sys

    data = sys.stdin.read()
    sys.stdout.write(sanitize(data))
