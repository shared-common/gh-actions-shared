from __future__ import annotations

from typing import Dict, List, Optional

from github_api import GitHubApi


def discover_fork_repos(api: GitHubApi, org: str, repo_filter: Optional[str]) -> List[Dict]:
    repos = []
    for repo in api.paginate(f"/orgs/{org}/repos", query={"type": "all"}):
        if repo.get("archived") or repo.get("disabled"):
            continue
        if repo_filter and repo.get("name") != repo_filter:
            continue
        repos.append(repo)
    return repos
