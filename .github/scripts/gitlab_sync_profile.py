from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


COMMON_BWS_SECRETS = (
    "GL_BASE_URL",
    "GIT_BRANCH_PREFIX",
    "GIT_BRANCH_MAIN",
    "GIT_BRANCH_STAGING",
    "GIT_BRANCH_RELEASE",
    "GIT_BRANCH_SNAPSHOT",
    "GIT_BRANCH_FEATURE",
)


@dataclass(frozen=True)
class GitlabProfileConfig:
    profile: str
    group_top_secret: str
    group_sub_secret: str
    git_username_secret: str
    api_token_secret: str


PROFILE_CONFIG: dict[str, GitlabProfileConfig] = {
    "upstream": GitlabProfileConfig(
        profile="upstream",
        group_top_secret="GL_GROUP_TOP_UPSTREAM",
        group_sub_secret="GL_GROUP_SUB_CANONICAL",
        git_username_secret="GL_BRIDGE_FORK_USER_SEEDBED",
        api_token_secret="GL_PAT_FORK_SEEDBED_SVC",
    ),
    "xf-main": GitlabProfileConfig(
        profile="xf-main",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_MAIN",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
    "xf-secops": GitlabProfileConfig(
        profile="xf-secops",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_SECOPS",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
    "xf-checkout": GitlabProfileConfig(
        profile="xf-checkout",
        group_top_secret="GL_GROUP_TOP_DIVERGE",
        group_sub_secret="GL_GROUP_SUB_XF_CHECKOUT",
        git_username_secret="GL_BRIDGE_FORK_USER_DERIVED",
        api_token_secret="GL_PAT_FORK_DERIVED_SVC",
    ),
}


def get_profile_config(profile: str) -> GitlabProfileConfig:
    try:
        return PROFILE_CONFIG[profile]
    except KeyError as exc:
        raise SystemExit(f"Unsupported target profile for GitLab sync: {profile}") from exc


def required_bws_secrets(profile: str) -> tuple[str, ...]:
    cfg = get_profile_config(profile)
    ordered: list[str] = list(COMMON_BWS_SECRETS)
    for name in (cfg.group_top_secret, cfg.group_sub_secret, cfg.git_username_secret, cfg.api_token_secret):
        if name not in ordered:
            ordered.append(name)
    return tuple(ordered)


def resolve_profile_values(
    profile: str,
    require_secret: Callable[[str], str],
) -> tuple[str, str, str, str]:
    cfg = get_profile_config(profile)
    group_top = require_secret(cfg.group_top_secret)
    group_sub = require_secret(cfg.group_sub_secret)
    git_username = require_secret(cfg.git_username_secret)
    api_token = require_secret(cfg.api_token_secret)
    return group_top, group_sub, git_username, api_token


def format_required_bws_secrets(profile: str) -> str:
    return ",".join(required_bws_secrets(profile))


__all__: Sequence[str] = (
    "COMMON_BWS_SECRETS",
    "GitlabProfileConfig",
    "PROFILE_CONFIG",
    "format_required_bws_secrets",
    "get_profile_config",
    "required_bws_secrets",
    "resolve_profile_values",
)
