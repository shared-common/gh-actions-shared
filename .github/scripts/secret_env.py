from __future__ import annotations

import os
from typing import Optional

MAX_SECRET_BYTES = 64 * 1024


def _read_file(path: str, name: str, max_bytes: int) -> str:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"{name} file too large")
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def read_required_value(name: str, *, allow_env: bool = True, max_bytes: int = MAX_SECRET_BYTES) -> str:
    value = os.environ.get(name)
    if value:
        if not allow_env:
            raise ValueError(f"{name} must not be set directly; use {name}_FILE instead")
        return value.strip()
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        return _read_file(file_path, name, max_bytes)
    raise ValueError(f"Missing required env var: {name}")


def ensure_file_env(name: str) -> str:
    file_key = f"{name}_FILE"
    if file_key in os.environ:
        file_path = os.environ.get(file_key)
        if file_path:
            return file_path
        raise ValueError(f"{file_key} is set but empty")
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        candidate = os.path.join(runner_temp, "bws", name)
        if os.path.exists(candidate):
            os.environ[file_key] = candidate
            return candidate
    raise ValueError(f"Missing required env var: {file_key}")


def read_required_secret_file(name: str, *, max_bytes: int = MAX_SECRET_BYTES) -> str:
    return read_required_value(name, allow_env=False, max_bytes=max_bytes)


def read_optional_value(
    name: str,
    *,
    allow_env: bool = True,
    max_bytes: int = MAX_SECRET_BYTES,
) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        if not allow_env:
            raise ValueError(f"{name} must not be set directly; use {name}_FILE instead")
        return value.strip()
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        return _read_file(file_path, name, max_bytes)
    return None


def has_env_or_file(name: str) -> bool:
    if os.environ.get(name):
        return True
    return bool(os.environ.get(f"{name}_FILE"))
