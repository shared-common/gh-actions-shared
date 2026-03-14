from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


COMMON_BWS_SECRETS = (
    "GL_BASE_URL",
    "GL_MAPPING_JSON",
    "GIT_BRANCH_PREFIX",
    "GIT_BRANCH_MAIN",
    "GIT_BRANCH_STAGING",
    "GIT_BRANCH_RELEASE",
    "GIT_BRANCH_SNAPSHOT",
    "GIT_BRANCH_FEATURE",
)

GITHUB_APP_BWS_SECRETS = (
    "GH_ORG_SHARED_APP_ID",
    "GH_ORG_SHARED_APP_PEM",
    "GH_INSTALL_JSON",
)


@dataclass(frozen=True)
class GitlabProfileConfig:
    profile: str
    git_username_secret: str
    api_token_secret: str


PROFILE_CONFIG: dict[str, GitlabProfileConfig] = {
    "upstream": GitlabProfileConfig(
        profile="upstream",
        git_username_secret="GL_BRIDGE_FORK_USER_SEEDBED",
        api_token_secret="GL_PAT_FORK_SEEDBED_SVC",
    ),
    "xf-main": GitlabProfileConfig(
        profile="xf-main",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
    "xf-secops": GitlabProfileConfig(
        profile="xf-secops",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
    "xf-checkout": GitlabProfileConfig(
        profile="xf-checkout",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
}


def get_profile_config(profile: str) -> GitlabProfileConfig:
    try:
        return PROFILE_CONFIG[profile]
    except KeyError as exc:
        raise SystemExit(f"Unsupported target profile for GitLab sync: {profile}") from exc


def required_bws_secrets(profile: str, *, include_github_app: bool = False) -> tuple[str, ...]:
    cfg = get_profile_config(profile)
    ordered: list[str] = list(COMMON_BWS_SECRETS)
    for name in (cfg.git_username_secret, cfg.api_token_secret):
        if name not in ordered:
            ordered.append(name)
    if include_github_app:
        for name in GITHUB_APP_BWS_SECRETS:
            if name not in ordered:
                ordered.append(name)
    return tuple(ordered)


def resolve_profile_values(
    profile: str,
    require_secret: Callable[[str], str],
) -> tuple[str, str]:
    cfg = get_profile_config(profile)
    git_username = require_secret(cfg.git_username_secret)
    api_token = require_secret(cfg.api_token_secret)
    return git_username, api_token


def format_required_bws_secrets(profile: str, *, include_github_app: bool = False) -> str:
    return ",".join(required_bws_secrets(profile, include_github_app=include_github_app))


__all__: Sequence[str] = (
    "COMMON_BWS_SECRETS",
    "GITHUB_APP_BWS_SECRETS",
    "GitlabProfileConfig",
    "PROFILE_CONFIG",
    "format_required_bws_secrets",
    "get_profile_config",
    "required_bws_secrets",
    "resolve_profile_values",
)
