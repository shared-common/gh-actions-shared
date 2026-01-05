from __future__ import annotations

from typing import Any, Dict

from github_api import GitHubApi, GitHubApiError


def compare_refs(api: GitHubApi, owner: str, repo: str, base: str, head: str) -> Dict[str, Any]:
    resp = api.request("GET", f"/repos/{owner}/{repo}/compare/{base}...{head}")
    if not isinstance(resp.data, dict):
        raise GitHubApiError(resp.status, "Unexpected compare response")
    return resp.data


def ff_update(api: GitHubApi, owner: str, repo: str, ref: str, sha: str) -> None:
    api.request(
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{ref}",
        payload={"sha": sha, "force": False},
    )
