from __future__ import annotations

from typing import Any, Dict

from github_api import GitHubApi, GitHubApiError


def merge_if_needed(api: GitHubApi, owner: str, repo: str, base: str, head: str) -> Dict[str, Any]:
    compare = api.request("GET", f"/repos/{owner}/{repo}/compare/{base}...{head}")
    if not isinstance(compare.data, dict):
        raise GitHubApiError(compare.status, "Unexpected compare response")
    status = compare.data.get("status")
    # GitHub compare base...head: "behind" means base is ahead of head.
    if status in ("identical", "behind"):
        return {"status": "up_to_date"}
    try:
        merge_resp = api.request(
            "POST",
            f"/repos/{owner}/{repo}/merges",
            payload={"base": base, "head": head},
        )
        sha = merge_resp.data.get("sha") if isinstance(merge_resp.data, dict) else None
        return {"status": "merged", "sha": sha}
    except GitHubApiError as exc:
        return {"status": "error", "code": exc.status, "message": str(exc)}
