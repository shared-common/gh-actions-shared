from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


MAX_CACHE_BYTES = 10 * 1024 * 1024
CACHE_VERSION = 1


def _now() -> float:
    return time.time()


def _is_fresh(ts: Optional[float], ttl: int) -> bool:
    if ts is None or ttl <= 0:
        return False
    return (_now() - float(ts)) <= ttl


def _load_json(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {"version": CACHE_VERSION, "orgs": {}}
    size = os.path.getsize(path)
    if size > MAX_CACHE_BYTES:
        return {"version": CACHE_VERSION, "orgs": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"version": CACHE_VERSION, "orgs": {}}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {"version": CACHE_VERSION, "orgs": {}}
    if not isinstance(data.get("orgs"), dict):
        data["orgs"] = {}
    return data


def load_cache(path: str) -> Dict[str, Any]:
    return _load_json(path)


def save_cache(path: str, data: Dict[str, Any]) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"))
    os.replace(tmp_path, path)


def _org_cache(data: Dict[str, Any], org: str) -> Dict[str, Any]:
    orgs = data.setdefault("orgs", {})
    org_cache = orgs.setdefault(org, {"repos": {}})
    if "repos" not in org_cache or not isinstance(org_cache["repos"], dict):
        org_cache["repos"] = {}
    return org_cache


def _repo_cache(data: Dict[str, Any], org: str, repo: str) -> Dict[str, Any]:
    org_cache = _org_cache(data, org)
    repos = org_cache["repos"]
    repo_cache = repos.setdefault(repo, {})
    return repo_cache


def get_repo_meta(data: Dict[str, Any], org: str, repo: str, ttl: int) -> Optional[Dict[str, Any]]:
    entry = _repo_cache(data, org, repo).get("meta")
    if not isinstance(entry, dict):
        return None
    if not _is_fresh(entry.get("ts"), ttl):
        return None
    value = entry.get("value")
    return value if isinstance(value, dict) else None


def set_repo_meta(data: Dict[str, Any], org: str, repo: str, value: Dict[str, Any]) -> None:
    _repo_cache(data, org, repo)["meta"] = {"ts": _now(), "value": value}


def get_ref_sha(data: Dict[str, Any], org: str, repo: str, ref: str, ttl: int) -> Optional[str]:
    refs = _repo_cache(data, org, repo).get("refs")
    if not isinstance(refs, dict):
        return None
    entry = refs.get(ref)
    if not isinstance(entry, dict) or not _is_fresh(entry.get("ts"), ttl):
        return None
    sha = entry.get("sha")
    return sha if isinstance(sha, str) else None


def set_ref_sha(data: Dict[str, Any], org: str, repo: str, ref: str, sha: str) -> None:
    repo_cache = _repo_cache(data, org, repo)
    refs = repo_cache.setdefault("refs", {})
    if not isinstance(refs, dict):
        refs = {}
        repo_cache["refs"] = refs
    refs[ref] = {"ts": _now(), "sha": sha}


def is_negative(
    data: Dict[str, Any],
    org: str,
    repo: str,
    kind: str,
    ttl: int,
    ref: Optional[str] = None,
) -> bool:
    negative = _repo_cache(data, org, repo).get("negative")
    if not isinstance(negative, dict):
        return False
    if kind == "missing_ref":
        missing = negative.get("missing_refs")
        if not isinstance(missing, dict) or not ref:
            return False
        entry = missing.get(ref)
        if not isinstance(entry, dict):
            return False
        return _is_fresh(entry.get("ts"), ttl)
    entry = negative.get(kind)
    if not isinstance(entry, dict):
        return False
    return _is_fresh(entry.get("ts"), ttl)


def set_negative(
    data: Dict[str, Any],
    org: str,
    repo: str,
    kind: str,
    ref: Optional[str] = None,
) -> None:
    repo_cache = _repo_cache(data, org, repo)
    negative = repo_cache.setdefault("negative", {})
    if not isinstance(negative, dict):
        negative = {}
        repo_cache["negative"] = negative
    if kind == "missing_ref":
        missing = negative.setdefault("missing_refs", {})
        if not isinstance(missing, dict):
            missing = {}
            negative["missing_refs"] = missing
        if ref:
            missing[ref] = {"ts": _now()}
        return
    negative[kind] = {"ts": _now()}


def get_gitlab_project(data: Dict[str, Any], org: str, repo: str, ttl: int) -> Optional[str]:
    entry = _repo_cache(data, org, repo).get("gitlab", {}).get("project")
    if not isinstance(entry, dict) or not _is_fresh(entry.get("ts"), ttl):
        return None
    status = entry.get("status")
    return status if isinstance(status, str) else None


def set_gitlab_project(data: Dict[str, Any], org: str, repo: str, status: str) -> None:
    repo_cache = _repo_cache(data, org, repo)
    gitlab = repo_cache.setdefault("gitlab", {})
    if not isinstance(gitlab, dict):
        gitlab = {}
        repo_cache["gitlab"] = gitlab
    gitlab["project"] = {"ts": _now(), "status": status}


def get_gitlab_branch(data: Dict[str, Any], org: str, repo: str, ref: str, ttl: int) -> Optional[str]:
    branches = _repo_cache(data, org, repo).get("gitlab", {}).get("branches")
    if not isinstance(branches, dict):
        return None
    entry = branches.get(ref)
    if not isinstance(entry, dict) or not _is_fresh(entry.get("ts"), ttl):
        return None
    status = entry.get("status")
    return status if isinstance(status, str) else None


def set_gitlab_branch(data: Dict[str, Any], org: str, repo: str, ref: str, status: str) -> None:
    repo_cache = _repo_cache(data, org, repo)
    gitlab = repo_cache.setdefault("gitlab", {})
    if not isinstance(gitlab, dict):
        gitlab = {}
        repo_cache["gitlab"] = gitlab
    branches = gitlab.setdefault("branches", {})
    if not isinstance(branches, dict):
        branches = {}
        gitlab["branches"] = branches
    branches[ref] = {"ts": _now(), "status": status}


def get_gitlab_protection(data: Dict[str, Any], org: str, repo: str, ref: str, ttl: int) -> Optional[str]:
    protections = _repo_cache(data, org, repo).get("gitlab", {}).get("protections")
    if not isinstance(protections, dict):
        return None
    entry = protections.get(ref)
    if not isinstance(entry, dict) or not _is_fresh(entry.get("ts"), ttl):
        return None
    status = entry.get("status")
    return status if isinstance(status, str) else None


def set_gitlab_protection(data: Dict[str, Any], org: str, repo: str, ref: str, status: str) -> None:
    repo_cache = _repo_cache(data, org, repo)
    gitlab = repo_cache.setdefault("gitlab", {})
    if not isinstance(gitlab, dict):
        gitlab = {}
        repo_cache["gitlab"] = gitlab
    protections = gitlab.setdefault("protections", {})
    if not isinstance(protections, dict):
        protections = {}
        gitlab["protections"] = protections
    protections[ref] = {"ts": _now(), "status": status}
