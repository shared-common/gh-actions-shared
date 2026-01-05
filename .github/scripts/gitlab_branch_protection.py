from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from discover_repos import discover_fork_repos
from github_api import GitHubApi, GitHubApiError


@dataclass(frozen=True)
class GitLabProtectionConfig:
    github_org: str
    github_prefix: str
    github_staging_branch: str
    gitlab_token: str
    gitlab_group: str
    gitlab_subgroup: str
    gitlab_host: str

    @property
    def staging_ref(self) -> str:
        return f"{self.github_prefix}/{self.github_staging_branch}"

    @property
    def release_ref(self) -> str:
        return f"{self.github_prefix}/release"

    def gitlab_project_path(self, repo: str) -> str:
        return f"{self.gitlab_group}/{self.gitlab_subgroup}/{repo}.git"


_REQUIRED_ENV = {
    "GH_BRANCH_PREFIX",
    "GH_BRANCH_STAGING",
    "GL_TOKEN_MCZFORKS",
    "GL_GROUP_ZFORKS",
    "GL_GROUP_TBOX",
    "GL_GROUP_SECOPS",
    "GL_GROUP_WIKI",
    "GL_GROUP_ZDIVERGE",
    "GL_GROUP_GENERAL",
    "GITHUB_APP_TOKEN_FILE",
    "GL_TOKEN_MCZFORKS_FILE",
}


class GitLabApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class GitLabApi:
    def __init__(self, token: str, host: str) -> None:
        self._token = token
        self._base = f"https://{host}/api/v4"

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("POST", path, payload=payload)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self._base}{path}"
        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "PRIVATE-TOKEN": self._token,
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
        return self._request_with_retry(req)

    def _request_with_retry(self, req: urllib.request.Request) -> Any:
        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                    return json.loads(body.decode("utf-8")) if body else None
            except urllib.error.HTTPError as exc:
                status = exc.code
                body = exc.read().decode("utf-8") if exc.fp else ""
                if status in (429, 500, 502, 503, 504):
                    time.sleep(min(2**attempt, 10))
                    continue
                raise GitLabApiError(status, body or "GitLab API error") from exc
            except urllib.error.URLError as exc:
                if attempt == max_attempts:
                    raise GitLabApiError(0, f"Network error: {exc}") from exc
                time.sleep(min(2**attempt, 10))
        raise GitLabApiError(0, "GitLab API retry limit exceeded")


def _env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"Missing required env var: {name}")
    return value




def _secret_file_path(env_key: str, file_key: str) -> str:
    direct = os.environ.get(env_key)
    if direct:
        raise ValueError(f"{env_key} must not be set; use {file_key} instead")
    path = os.environ.get(file_key)
    if not path:
        raise ValueError(f"Missing required env var: {file_key}")
    return path


def _read_secret_file(path: str, label: str, max_bytes: int = 64 * 1024) -> str:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"{label} file too large")
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _github_token() -> str:
    path = _secret_file_path("GITHUB_APP_TOKEN", "GITHUB_APP_TOKEN_FILE")
    return _read_secret_file(path, "GITHUB_APP_TOKEN")


def _gitlab_token() -> str:
    path = _secret_file_path("GL_TOKEN_MCZFORKS", "GL_TOKEN_MCZFORKS_FILE")
    return _read_secret_file(path, "GL_TOKEN_MCZFORKS")


def _resolve_org_and_group() -> tuple[str, str, str]:
    org_map = {
        "GH_ORG_TBOX": ("GL_GROUP_ZFORKS", "GL_GROUP_TBOX"),
        "GH_ORG_SECOPS": ("GL_GROUP_ZFORKS", "GL_GROUP_SECOPS"),
        "GH_ORG_WIKI": ("GL_GROUP_ZFORKS", "GL_GROUP_WIKI"),
        "GH_ORG_DIVERGE": ("GL_GROUP_ZDIVERGE", "GL_GROUP_GENERAL"),
    }
    org_values = {key: os.environ.get(key, "").strip() for key in org_map}
    active_orgs = {key: value for key, value in org_values.items() if value}
    if not active_orgs:
        raise ValueError("Missing required org value")
    if len(active_orgs) > 1:
        raise ValueError(f"Multiple org values set: {', '.join(sorted(active_orgs.keys()))}")
    org_key, github_org = next(iter(active_orgs.items()))
    group_key, subgroup_key = org_map[org_key]
    gitlab_group = os.environ.get(group_key, "").strip()
    gitlab_subgroup = os.environ.get(subgroup_key, "").strip()
    if not gitlab_group:
        raise ValueError(f"Missing required gitlab group value: {group_key}")
    if not gitlab_subgroup:
        raise ValueError(f"Missing required gitlab subgroup value: {subgroup_key}")
    return github_org, gitlab_group, gitlab_subgroup


def load_config() -> GitLabProtectionConfig:
    github_org, gitlab_group, gitlab_subgroup = _resolve_org_and_group()
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(sorted(missing))}")
    return GitLabProtectionConfig(
        github_org=github_org,
        github_prefix=_env("GH_BRANCH_PREFIX"),
        github_staging_branch=_env("GH_BRANCH_STAGING"),
        gitlab_token=_gitlab_token(),
        gitlab_group=gitlab_group,
        gitlab_subgroup=gitlab_subgroup,
        gitlab_host=os.environ.get("GL_HOST", "gitlab.com"),
    )


def _gitlab_project_id(cfg: GitLabProtectionConfig, repo: str) -> str:
    path = f"{cfg.gitlab_group}/{cfg.gitlab_subgroup}/{repo}"
    return urllib.parse.quote(path, safe="")


def _list_protected_branches(
    api: GitLabApi, cfg: GitLabProtectionConfig, repo: str
) -> List[Dict[str, Any]]:
    project_id = _gitlab_project_id(cfg, repo)
    data = api.get(f"/projects/{project_id}/protected_branches")
    return data if isinstance(data, list) else []


def _ensure_branch_protection(api: GitLabApi, cfg: GitLabProtectionConfig, repo: str, branch: str) -> str:
    rules = _list_protected_branches(api, cfg, repo)
    for rule in rules:
        if rule.get("name") == branch:
            return "already protected"
    project_id = _gitlab_project_id(cfg, repo)
    payload = {
        "name": branch,
        "push_access_level": 40,
        "merge_access_level": 40,
        "unprotect_access_level": 40,
    }
    try:
        api.post(f"/projects/{project_id}/protected_branches", payload)
        return "protected"
    except GitLabApiError as exc:
        if exc.status in (409, 422):
            return "already protected"
        raise


def _remove_branch_protection(api: GitLabApi, cfg: GitLabProtectionConfig, repo: str, branch: str) -> str:
    project_id = _gitlab_project_id(cfg, repo)
    branch_id = urllib.parse.quote(branch, safe="")
    try:
        api.delete(f"/projects/{project_id}/protected_branches/{branch_id}")
        return "removed"
    except GitLabApiError as exc:
        if exc.status == 404:
            return "absent"
        raise


def process_repo(api: GitHubApi, cfg: GitLabProtectionConfig, repo: Dict[str, Any]) -> Dict[str, Any]:
    owner = cfg.github_org
    name = repo.get("name")
    result: Dict[str, Any] = {"name": name}
    if not name:
        result["notes"] = ["Skipped: missing repo name"]
        return result

    try:
        repo_details_resp = api.get(f"/repos/{owner}/{name}")
    except GitHubApiError as exc:
        result["notes"] = [f"Skipped: failed to fetch repo metadata ({exc.status})"]
        return result

    repo_details = repo_details_resp.data if isinstance(repo_details_resp.data, dict) else {}
    if repo_details.get("archived") or repo_details.get("disabled"):
        result["notes"] = ["Skipped: archived or disabled"]
        return result

    if not repo_details.get("fork") or not repo_details.get("parent"):
        result["notes"] = ["Skipped: not a fork or missing upstream"]
        return result

    gitlab_api = GitLabApi(cfg.gitlab_token, cfg.gitlab_host)
    try:
        _gitlab_project_id(cfg, name)
    except Exception as exc:  # noqa: BLE001 - safe summary path
        result["notes"] = [f"Skipped: invalid gitlab project ({exc})"]
        return result

    try:
        result["protect_mcr_staging"] = _ensure_branch_protection(
            gitlab_api,
            cfg,
            name,
            cfg.staging_ref,
        )
    except GitLabApiError as exc:
        result["protect_mcr_staging"] = f"failed ({exc.status})"

    try:
        result["protect_mcr_release"] = _ensure_branch_protection(gitlab_api, cfg, name, cfg.release_ref)
    except GitLabApiError as exc:
        result["protect_mcr_release"] = f"failed ({exc.status})"

    cleanup_targets = [
        "github/*",
        "github/main",
        f"github/{cfg.github_prefix}/main",
        f"github/{cfg.staging_ref}",
        f"github/{cfg.release_ref}",
        f"{cfg.github_prefix}/main",
        f"{cfg.github_prefix}/feature/initial",
        f"{cfg.github_prefix}/snapshot",
    ]

    cleanup_results: Dict[str, str] = {}
    for branch in cleanup_targets:
        try:
            cleanup_results[branch] = _remove_branch_protection(gitlab_api, cfg, name, branch)
        except GitLabApiError as exc:
            cleanup_results[branch] = f"failed ({exc.status})"
    result["cleanup"] = cleanup_results
    return result


def _summary_lines(results: List[Dict[str, Any]]) -> str:
    lines = ["# GitLab branch protection summary", ""]
    if not results:
        lines.append("- No repositories processed.")
        return "\n".join(lines)
    for repo in results:
        name = repo.get("name")
        lines.append(f"## {name}")
        if "notes" in repo:
            lines.append(f"- **notes**: {repo['notes']}")
            continue
        for key in ("protect_mcr_staging", "protect_mcr_release", "cleanup"):
            if key in repo:
                lines.append(f"- **{key}**: {repo[key]}")
    return "\n".join(lines)


def main() -> int:
    token = _github_token()
    repo_filter = os.environ.get("INPUT_REPO") or None
    if repo_filter:
        repo_filter = repo_filter.strip() or None
    cfg = load_config()
    api = GitHubApi(token=token)
    repos = discover_fork_repos(api, cfg.github_org, repo_filter)

    results: List[Dict[str, Any]] = []
    for repo in repos:
        results.append(process_repo(api, cfg, repo))

    summary = _summary_lines(results)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")
    else:
        print(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
