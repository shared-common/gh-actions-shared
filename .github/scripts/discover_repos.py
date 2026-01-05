from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Dict, List, Optional

from github_api import GitHubApi


MAX_CACHE_BYTES = 5 * 1024 * 1024


def _cache_path(org: str, repo_filter: Optional[str]) -> Optional[str]:
    cache_dir = os.environ.get("REPO_CACHE_DIR")
    if not cache_dir:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    key = f"{org}:{repo_filter or ''}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return os.path.join(cache_dir, f"repos-{digest}.json")


def _normalize_repo_entry(entry: Dict) -> Optional[Dict[str, str]]:
    name = entry.get("name")
    if isinstance(name, str) and name:
        return {"name": name}
    return None


def _load_cache(
    path: str,
    ttl_seconds: int,
    repo_filter: Optional[str],
) -> Optional[List[Dict[str, str]]]:
    try:
        size = os.path.getsize(path)
        if size > MAX_CACHE_BYTES:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        repos = [repo for repo in (_normalize_repo_entry(item) for item in payload) if repo]
        if not repos and not repo_filter:
            return None
        return repos
    if not isinstance(payload, dict):
        return None
    timestamp = payload.get("timestamp")
    repos = payload.get("repos")
    if not isinstance(timestamp, (int, float)) or not isinstance(repos, list):
        return None
    if time.time() - float(timestamp) > ttl_seconds:
        return None
    normalized = [repo for repo in (_normalize_repo_entry(item) for item in repos) if repo]
    if not normalized and not repo_filter:
        return None
    return normalized


def _write_cache(path: str, org: str, repo_filter: Optional[str], repos: List[Dict[str, str]]) -> None:
    payload = {
        "org": org,
        "repo_filter": repo_filter,
        "timestamp": time.time(),
        "repos": repos,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    os.replace(tmp_path, path)


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
    cache_path = _cache_path(org, repo_filter)
    try:
        ttl_seconds = int(os.environ.get("REPO_CACHE_TTL_SECONDS", "3600"))
    except ValueError:
        ttl_seconds = 3600
    if ttl_seconds < 0:
        ttl_seconds = 0
    cache_path_override = os.environ.get("REPO_CACHE_PATH")
    if cache_path_override:
        cached = _load_cache(cache_path_override, ttl_seconds, repo_filter)
        if cached is not None:
            return cached
    if cache_path:
        cached = _load_cache(cache_path, ttl_seconds, repo_filter)
        if cached is not None:
            return cached
    repos: List[Dict[str, str]] = []
    for repo in api.paginate(f"/orgs/{org}/repos", query={"type": "all"}):
        if repo.get("archived") or repo.get("disabled"):
            continue
        name = repo.get("name")
        if repo_filter and name != repo_filter:
            continue
        if isinstance(name, str) and name:
            repos.append({"name": name})
    if cache_path_override and (repos or repo_filter):
        _write_cache(cache_path_override, org, repo_filter, repos)
    if cache_path and (repos or repo_filter):
        _write_cache(cache_path, org, repo_filter, repos)
    return repos
