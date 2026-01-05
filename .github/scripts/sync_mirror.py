from __future__ import annotations

from typing import Any, Dict

from github_api import GitHubApi, GitHubApiError


def sync_mirror(api: GitHubApi, owner: str, repo: str, mirror_branch: str) -> Dict[str, Any]:
    try:
        resp = api.request(
            "POST",
            f"/repos/{owner}/{repo}/merge-upstream",
            payload={"branch": mirror_branch},
        )
        return {
            "status": "ok",
            "message": resp.data.get("message") if isinstance(resp.data, dict) else "ok",
        }
    except GitHubApiError as exc:
        return {
            "status": "error",
            "code": exc.status,
            "message": str(exc),
            "details": exc.details,
        }
