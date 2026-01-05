from __future__ import annotations

from typing import Dict, List, Optional

from github_api import GitHubApi


def _validate_repo_filter(repo_filter: Optional[str]) -> Optional[str]:
    if not repo_filter:
        return None
    candidate = repo_filter.strip()
    if not candidate:
        return None
    if "/" in candidate or candidate.startswith(".") or " " in candidate:
        raise ValueError(f"Invalid repo filter: {candidate}")
    return candidate


def discover_fork_repos(api: GitHubApi, org: str, repo_filter: Optional[str]) -> List[Dict[str, str]]:
    repo_filter = _validate_repo_filter(repo_filter)
    repos: List[Dict[str, str]] = []
    for repo in api.paginate(f"/orgs/{org}/repos", query={"type": "all"}):
        if repo.get("archived") or repo.get("disabled"):
            continue
        name = repo.get("name")
        if repo_filter and name != repo_filter:
            continue
        if isinstance(name, str) and name:
            repos.append({"name": name})
    return repos
