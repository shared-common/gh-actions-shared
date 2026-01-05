from __future__ import annotations

from typing import Any, Dict, Optional

from github_api import GitHubApi


def _find_open_issue(api: GitHubApi, owner: str, repo: str, title: str) -> Optional[Dict[str, Any]]:
    for issue in api.paginate(
        f"/repos/{owner}/{repo}/issues",
        query={"state": "open", "per_page": "100"},
    ):
        if issue.get("title") == title:
            return issue
    return None


def create_or_update_issue(
    api: GitHubApi,
    owner: str,
    repo: str,
    title: str,
    body: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        existing = _find_open_issue(api, owner, repo, title)
        if existing:
            issue_number = existing.get("number")
            api.request(
                "PATCH",
                f"/repos/{owner}/{repo}/issues/{issue_number}",
                payload={"body": body},
            )
            if comment:
                api.request(
                    "POST",
                    f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    payload={"body": comment},
                )
            return {"action": "updated", "number": issue_number, "url": existing.get("html_url")}
        created = api.request(
            "POST",
            f"/repos/{owner}/{repo}/issues",
            payload={"title": title, "body": body},
        )
        return {
            "action": "created",
            "number": created.data.get("number") if isinstance(created.data, dict) else None,
            "url": created.data.get("html_url") if isinstance(created.data, dict) else None,
        }
    except Exception as exc:  # GitHubApiError or other unexpected failures
        status = getattr(exc, "status", None)
        if status == 410:
            return {"action": "skipped", "reason": "issues disabled"}
        raise
