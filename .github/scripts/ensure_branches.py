from __future__ import annotations

from typing import Any, Dict, Optional

from github_api import GitHubApi, GitHubApiError


def _get_ref_sha(api: GitHubApi, owner: str, repo: str, ref: str) -> Optional[str]:
    try:
        resp = api.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
    except GitHubApiError as exc:
        if exc.status == 404:
            return None
        raise
    if isinstance(resp.data, dict):
        return resp.data.get("object", {}).get("sha")
    return None


def _create_ref(api: GitHubApi, owner: str, repo: str, ref: str, sha: str) -> None:
    api.request(
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        payload={"ref": f"refs/heads/{ref}", "sha": sha},
    )


def ensure_branch(api: GitHubApi, owner: str, repo: str, ref: str, base_sha: str) -> Dict[str, Any]:
    existing_sha = _get_ref_sha(api, owner, repo, ref)
    if existing_sha:
        return {"status": "exists", "sha": existing_sha}
    _create_ref(api, owner, repo, ref, base_sha)
    return {"status": "created", "sha": base_sha}

