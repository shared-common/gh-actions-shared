import os
import re
from pathlib import Path

SECRET_KEYS = [
    "BWS_ACCESS_TOKEN",
    "BWS_PROJECT_ID",
    "GH_ORG_SHARED_APP_PEM",
    "GH_ORG_SHARED_APP_ID",
    "GH_INSTALL_JSON",
    "GH_ORG_ALLOWED_SHARED_JSON",
    "GH_ORG_SHARED_ALLOWED_JSON",
]
TOKEN_PATTERNS = [
    re.compile(r"[A-Fa-f0-9]{32,}"),
    re.compile(r"ghs_[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
]


def _read_secret_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def sanitize(text: str) -> str:
    sanitized = text
    for key in SECRET_KEYS:
        value = os.environ.get(key)
        if value:
            sanitized = sanitized.replace(value, "***")
        file_path = os.environ.get(f"{key}_FILE")
        if file_path:
            file_value = _read_secret_file(file_path)
            if file_value:
                sanitized = sanitized.replace(file_value, "***")
    for pattern in TOKEN_PATTERNS:
        sanitized = pattern.sub("***", sanitized)
    return sanitized


if __name__ == "__main__":
    import sys

    data = sys.stdin.read()
    sys.stdout.write(sanitize(data))
