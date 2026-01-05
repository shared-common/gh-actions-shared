from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Config:
    org: str
    app_id: str
    app_pem: str
    branch_prefix: str
    product_branch: str
    staging_branch: str
    snapshot_branch: str
    feature_branch: str

    @property
    def mirror_branch(self) -> str:
        return "main"

    @property
    def product_ref(self) -> str:
        return f"{self.branch_prefix}/{self.product_branch}"

    @property
    def staging_ref(self) -> str:
        return f"{self.branch_prefix}/{self.staging_branch}"

    @property
    def snapshot_ref(self) -> str:
        return f"{self.branch_prefix}/{self.snapshot_branch}"

    @property
    def feature_ref(self) -> str:
        return f"{self.branch_prefix}/{self.feature_branch}"


_REQUIRED_ENV = {
    "GH_ORG_SHARED_APP_ID",
    "GH_BRANCH_PREFIX",
    "GH_BRANCH_PRODUCT",
    "GH_BRANCH_STAGING",
    "GH_BRANCH_SNAPSHOT",
    "GH_BRANCH_FEATURE",
}

_ORG_KEYS = (
    "GH_ORG_TBOX",
    "GH_ORG_SECOPS",
    "GH_ORG_WIKI",
    "GH_ORG_DIVERGE",
)


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"Missing required env var: {name}")
    return value


def _get_secret_file_path(env_key: str, file_key: str) -> str:
    direct = os.environ.get(env_key)
    if direct:
        raise ValueError(f"{env_key} must not be set; use {file_key} instead")
    path = os.environ.get(file_key)
    if not path:
        raise ValueError(f"Missing required env var: {file_key}")
    return path


def _read_secret_file(path: str, label: str, max_bytes: int = 64 * 1024) -> str:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"{label} file too large")
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _get_pem() -> str:
    pem_file = _get_secret_file_path("GH_ORG_SHARED_PEM", "GH_ORG_SHARED_PEM_FILE")
    return _read_secret_file(pem_file, "GH_ORG_SHARED_PEM")


def _resolve_org() -> str:
    values = {key: os.environ.get(key, "").strip() for key in _ORG_KEYS}
    active = {key: value for key, value in values.items() if value}
    if not active:
        raise ValueError("Missing required org value")
    if len(active) > 1:
        raise ValueError(f"Multiple org values set: {', '.join(sorted(active.keys()))}")
    return next(iter(active.values()))


def load_config() -> Config:
    org = _resolve_org()
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(sorted(missing))}")
    return Config(
        org=org,
        app_id=_get_env("GH_ORG_SHARED_APP_ID"),
        app_pem=_get_pem(),
        branch_prefix=_get_env("GH_BRANCH_PREFIX"),
        product_branch=_get_env("GH_BRANCH_PRODUCT"),
        staging_branch=_get_env("GH_BRANCH_STAGING"),
        snapshot_branch=_get_env("GH_BRANCH_SNAPSHOT"),
        feature_branch=_get_env("GH_BRANCH_FEATURE"),
    )
