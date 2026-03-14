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
)


@dataclass(frozen=True)
class GitlabProfileConfig:
    profile: str
    git_username_secret: str
    api_token_secret: str
    group_top_secret: str
    group_sub_secret: str


PROFILE_CONFIG: dict[str, GitlabProfileConfig] = {
    "upstream": GitlabProfileConfig(
        profile="upstream",
        git_username_secret="GL_BRIDGE_FORK_USER_SEEDBED",
        api_token_secret="GL_PAT_FORK_SEEDBED_SVC",
        group_top_secret="GL_GROUP_TOP_UPSTREAM",
        group_sub_secret="GL_GROUP_SUB_CANONICAL",
    ),
    "xf-main": GitlabProfileConfig(
        profile="xf-main",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_MAIN",
    ),
    "xf-secops": GitlabProfileConfig(
        profile="xf-secops",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_SECOPS",
    ),
    "xf-checkout": GitlabProfileConfig(
        profile="xf-checkout",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_CHECKOUT",
    ),
}


def get_profile_config(profile: str) -> GitlabProfileConfig:
    try:
        return PROFILE_CONFIG[profile]
    except KeyError as exc:
        raise SystemExit(f"Unsupported target profile for GitLab sync: {profile}") from exc


def required_bws_secrets(profile: str, *, include_github_app: bool = False, mode: str = "create") -> tuple[str, ...]:
    cfg = get_profile_config(profile)
    if mode == "create":
        ordered: list[str] = list(COMMON_BWS_SECRETS)
    elif mode == "sync":
        ordered = [
            "GL_BASE_URL",
            "GIT_BRANCH_PREFIX",
            "GIT_BRANCH_MAIN",
            "GIT_BRANCH_STAGING",
            cfg.group_top_secret,
            cfg.group_sub_secret,
        ]
    else:
        raise SystemExit(f"Unsupported GitLab sync secret mode: {mode}")
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


def resolve_profile_group_path(profile: str, require_secret: Callable[[str], str]) -> str:
    cfg = get_profile_config(profile)
    group_top = require_secret(cfg.group_top_secret).strip()
    group_sub = require_secret(cfg.group_sub_secret).strip()
    if not group_top or not group_sub:
        raise SystemExit(f"Missing GitLab group path components for profile: {profile}")
    return f"{group_top}/{group_sub}"


def format_required_bws_secrets(profile: str, *, include_github_app: bool = False, mode: str = "create") -> str:
    return ",".join(required_bws_secrets(profile, include_github_app=include_github_app, mode=mode))


__all__: Sequence[str] = (
    "COMMON_BWS_SECRETS",
    "GITHUB_APP_BWS_SECRETS",
    "GitlabProfileConfig",
    "PROFILE_CONFIG",
    "format_required_bws_secrets",
    "get_profile_config",
    "resolve_profile_group_path",
    "required_bws_secrets",
    "resolve_profile_values",
)
