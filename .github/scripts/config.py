from __future__ import annotations

from dataclasses import dataclass

from secret_env import ensure_file_env, has_env_or_file, read_required_secret_file, read_required_value


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
    "GH_ORG_TOOLS",
    "GH_ORG_SECOPS",
    "GH_ORG_WIKI",
    "GH_ORG_DIVERGE",
)


def _get_pem() -> str:
    return read_required_secret_file("GH_ORG_SHARED_PEM")


def _resolve_org() -> str:
    values = {key: "" for key in _ORG_KEYS}
    for key in _ORG_KEYS:
        try:
            values[key] = read_required_value(key, allow_env=False)
        except ValueError:
            values[key] = ""
    active = {key: value for key, value in values.items() if value}
    if not active:
        raise ValueError("Missing required org value")
    if len(active) > 1:
        raise ValueError(f"Multiple org values set: {', '.join(sorted(active.keys()))}")
    return next(iter(active.values()))


def load_config() -> Config:
    org = _resolve_org()
    for name in _REQUIRED_ENV:
        ensure_file_env(name)
    missing = [name for name in _REQUIRED_ENV if not has_env_or_file(name)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(sorted(missing))}")
    return Config(
        org=org,
        app_id=read_required_value("GH_ORG_SHARED_APP_ID", allow_env=False),
        app_pem=_get_pem(),
        branch_prefix=read_required_value("GH_BRANCH_PREFIX", allow_env=False),
        product_branch=read_required_value("GH_BRANCH_PRODUCT", allow_env=False),
        staging_branch=read_required_value("GH_BRANCH_STAGING", allow_env=False),
        snapshot_branch=read_required_value("GH_BRANCH_SNAPSHOT", allow_env=False),
        feature_branch=read_required_value("GH_BRANCH_FEATURE", allow_env=False),
    )
