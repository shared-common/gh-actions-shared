from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from config import load_config
from discover_repos import discover_fork_repos
from github_api import GitHubApi, GitHubApiError
from logging_util import log_event, redact_text
from secret_env import read_required_secret_file


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _optional_env(name: str) -> Optional[str]:
    value = os.environ.get(name, "").strip()
    return value or None


def _branch_sha(api: GitHubApi, owner: str, repo: str, branch: str) -> Optional[str]:
    encoded = urllib.parse.quote(branch, safe="")
    try:
        resp = api.get(f"/repos/{owner}/{repo}/branches/{encoded}")
    except GitHubApiError as exc:
        if exc.status in (403, 404):
            return None
        raise
    data = resp.data if isinstance(resp.data, dict) else {}
    commit = data.get("commit") if isinstance(data, dict) else None
    sha = commit.get("sha") if isinstance(commit, dict) else None
    return sha if isinstance(sha, str) and sha else None


def _select_mirror_branch(api: GitHubApi, owner: str, repo: str, upstream_default: Optional[str]) -> Optional[str]:
    candidates = []
    if upstream_default:
        candidates.append(upstream_default)
    for fallback in ("main", "master"):
        if fallback not in candidates:
            candidates.append(fallback)
    for candidate in candidates:
        if _branch_sha(api, owner, repo, candidate):
            return candidate
    return None


def _dispatch_workflow(owner: str, repo: str, workflow: str, ref: str, inputs: Dict[str, str]) -> None:
    token = _require_env("DISPATCH_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = json.dumps({"ref": ref, "inputs": inputs}, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gh-actions-upstream-poll",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status >= 300:
                raise SystemExit(f"Workflow dispatch failed ({resp.status})")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise SystemExit(f"Workflow dispatch failed ({exc.code}): {body[:200]}") from exc


def main() -> int:
    cfg = load_config()
    org_filter = _optional_env("INPUT_ORG")
    if org_filter and org_filter != cfg.org:
        log_event("poll_skip", reason="org filter mismatch", org=cfg.org, filter=org_filter)
        return 0
    repo_filter = _optional_env("INPUT_REPO")

    app_token = read_required_secret_file("GITHUB_APP_TOKEN")
    api = GitHubApi(app_token, user_agent="gh-actions-upstream-poll")
    repos = discover_fork_repos(api, cfg.org, repo_filter)

    repo_owner = _require_env("GITHUB_REPOSITORY").split("/")[0]
    repo_name = _require_env("GITHUB_REPOSITORY").split("/")[1]
    workflow = _optional_env("ORCHESTRATOR_WORKFLOW") or "org-fork-orchestrator.yml"
    ref = _optional_env("ORCHESTRATOR_REF") or _optional_env("GITHUB_REF_NAME") or "main"

    triggered = 0
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        try:
            details = api.get(f"/repos/{cfg.org}/{name}")
        except GitHubApiError as exc:
            log_event("poll_skip", repo=name, reason=f"repo lookup failed ({exc.status})")
            continue
        info = details.data if isinstance(details.data, dict) else {}
        if not info.get("fork") or not isinstance(info.get("parent"), dict):
            continue
        parent = info.get("parent") or {}
        upstream_owner = parent.get("owner", {}).get("login")
        upstream_repo = parent.get("name")
        upstream_default = parent.get("default_branch")
        if not upstream_owner or not upstream_repo:
            continue
        mirror_branch = _select_mirror_branch(api, cfg.org, name, upstream_default)
        if not mirror_branch:
            log_event("poll_skip", repo=name, reason="mirror branch missing")
            continue
        upstream_sha = _branch_sha(api, upstream_owner, upstream_repo, upstream_default or mirror_branch)
        if not upstream_sha:
            log_event("poll_skip", repo=name, reason="upstream sha unavailable")
            continue
        mirror_sha = _branch_sha(api, cfg.org, name, mirror_branch)
        if not mirror_sha:
            log_event("poll_skip", repo=name, reason="mirror sha missing")
            continue
        if upstream_sha == mirror_sha:
            continue
        _dispatch_workflow(
            repo_owner,
            repo_name,
            workflow,
            ref,
            {"repo": name, "org": cfg.org},
        )
        triggered += 1
        log_event("poll_dispatch", repo=name, org=cfg.org, upstream=redact_text(upstream_repo))
        time.sleep(1)

    log_event("poll_complete", org=cfg.org, triggered=triggered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
