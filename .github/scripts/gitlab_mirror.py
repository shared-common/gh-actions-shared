from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from discover_repos import discover_fork_repos
from github_api import GitHubApi, GitHubApiError
from secret_env import (
    has_env_or_file,
    read_optional_value,
    read_required_secret_file,
    read_required_value,
)


@dataclass(frozen=True)
class GitLabConfig:
    github_org: str
    github_prefix: str
    github_product_branch: str
    github_staging_branch: str
    github_feature_branch: str
    github_release_branch: str
    gitlab_token: str
    gitlab_group: str
    gitlab_subgroup: str
    gitlab_host: str

    @property
    def product_ref(self) -> str:
        return f"{self.github_prefix}/{self.github_product_branch}"

    @property
    def staging_ref(self) -> str:
        return f"{self.github_prefix}/{self.github_staging_branch}"

    @property
    def feature_ref(self) -> str:
        return f"{self.github_prefix}/{self.github_feature_branch}"

    @property
    def release_ref(self) -> str:
        return f"{self.github_prefix}/{self.github_release_branch}"

    def gitlab_project_path(self, repo: str) -> str:
        return f"{self.gitlab_group}/{self.gitlab_subgroup}/{repo}.git"


_REQUIRED_ENV = {
    "GH_BRANCH_PREFIX",
    "GH_BRANCH_PRODUCT",
    "GH_BRANCH_STAGING",
    "GH_BRANCH_FEATURE",
    "GH_BRANCH_RELEASE",
    "GITHUB_APP_TOKEN_FILE",
    "GL_TOKEN_DERIVED_FILE",
}


def _github_token() -> str:
    return read_required_secret_file("GITHUB_APP_TOKEN")


def _gitlab_token() -> str:
    return read_required_secret_file("GL_TOKEN_DERIVED")


def _resolve_org_and_group() -> tuple[str, str, str]:
    org_map = {
        "GH_ORG_TOOLS": ("GL_GROUP_TOP_DERIVED", "GL_GROUP_SUB_TOOLS"),
        "GH_ORG_SECOPS": ("GL_GROUP_TOP_DERIVED", "GL_GROUP_SUB_SECOPS"),
        "GH_ORG_WIKI": ("GL_GROUP_TOP_DERIVED", "GL_GROUP_SUB_WIKI"),
        "GH_ORG_DIVERGE": ("GL_GROUP_TOP_DERIVED", "GL_GROUP_SUB_DIVERGE"),
    }
    org_values = {key: read_optional_value(key, allow_env=False) or "" for key in org_map}
    active_orgs = {key: value for key, value in org_values.items() if value}
    if not active_orgs:
        raise ValueError("Missing required org value")
    if len(active_orgs) > 1:
        raise ValueError(f"Multiple org values set: {', '.join(sorted(active_orgs.keys()))}")
    org_key, github_org = next(iter(active_orgs.items()))
    group_key, subgroup_key = org_map[org_key]
    gitlab_group = read_optional_value(group_key, allow_env=False) or ""
    gitlab_subgroup = read_optional_value(subgroup_key, allow_env=False) or ""
    if not gitlab_group:
        raise ValueError(f"Missing required gitlab group value: {group_key}")
    if not gitlab_subgroup:
        raise ValueError(f"Missing required gitlab subgroup value: {subgroup_key}")
    return github_org, gitlab_group, gitlab_subgroup


def load_config() -> GitLabConfig:
    github_org, gitlab_group, gitlab_subgroup = _resolve_org_and_group()
    missing = [name for name in _REQUIRED_ENV if not has_env_or_file(name)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(sorted(missing))}")
    return GitLabConfig(
        github_org=github_org,
        github_prefix=read_required_value("GH_BRANCH_PREFIX", allow_env=False),
        github_product_branch=read_required_value("GH_BRANCH_PRODUCT", allow_env=False),
        github_staging_branch=read_required_value("GH_BRANCH_STAGING", allow_env=False),
        github_feature_branch=read_required_value("GH_BRANCH_FEATURE", allow_env=False),
        github_release_branch=read_required_value("GH_BRANCH_RELEASE", allow_env=False),
        gitlab_token=read_required_secret_file("GL_TOKEN_DERIVED"),
        gitlab_group=gitlab_group,
        gitlab_subgroup=gitlab_subgroup,
        gitlab_host=read_optional_value("GL_HOST", allow_env=True) or "gitlab.com",
    )


class GitCommandError(RuntimeError):
    pass


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

    def put(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("PUT", path, payload=payload)

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
                    time.sleep(min(2 ** attempt, 10))
                    continue
                raise GitLabApiError(status, body or "GitLab API error") from exc
            except urllib.error.URLError as exc:
                if attempt == max_attempts:
                    raise GitLabApiError(0, f"Network error: {exc}") from exc
                time.sleep(min(2 ** attempt, 10))
        raise GitLabApiError(0, "GitLab API retry limit exceeded")


def _secrets_to_redact() -> List[str]:
    candidates = [_github_token(), _gitlab_token()]
    return [value for value in candidates if value]


def _redact(value: str, secrets: List[str]) -> str:
    redacted = value
    for secret in secrets:
        redacted = redacted.replace(secret, "***")
    return redacted


def _run_git(args: List[str], cwd: Optional[str] = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    secrets = _secrets_to_redact()
    stdout = _redact(result.stdout.strip(), secrets)
    stderr = _redact(result.stderr.strip(), secrets)
    if result.returncode != 0:
        raise GitCommandError(stderr or stdout)
    return stdout


def _run_git_with_token(args: List[str], token: str, cwd: Optional[str] = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("utf-8")
    env["GIT_ASKPASS"] = "/bin/false"
    result = subprocess.run(
        ["git", "-c", f"http.extraHeader=Authorization: Basic {basic}", *args],
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    secrets = _secrets_to_redact()
    stdout = _redact(result.stdout.strip(), secrets)
    stderr = _redact(result.stderr.strip(), secrets)
    if result.returncode != 0:
        raise GitCommandError(stderr or stdout)
    return stdout


def _run_git_with_gitlab_token(args: List[str], token: str, cwd: Optional[str] = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    basic = base64.b64encode(f"oauth2:{token}".encode("utf-8")).decode("utf-8")
    env["GIT_ASKPASS"] = "/bin/false"
    result = subprocess.run(
        ["git", "-c", f"http.extraHeader=Authorization: Basic {basic}", *args],
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    secrets = _secrets_to_redact()
    stdout = _redact(result.stdout.strip(), secrets)
    stderr = _redact(result.stderr.strip(), secrets)
    if result.returncode != 0:
        raise GitCommandError(stderr or stdout)
    return stdout


def _gitlab_url(cfg: GitLabConfig, repo: str) -> str:
    return f"https://{cfg.gitlab_host}/{cfg.gitlab_project_path(repo)}"


def _github_url(org: str, repo: str) -> str:
    return f"https://github.com/{org}/{repo}.git"


def _gitlab_project_id(cfg: GitLabConfig, repo: str) -> str:
    path = f"{cfg.gitlab_group}/{cfg.gitlab_subgroup}/{repo}"
    return urllib.parse.quote(path, safe="")


def _gitlab_namespace_id(api: GitLabApi, full_path: str) -> int:
    path = urllib.parse.quote(full_path, safe="")
    data = api.get(f"/namespaces/{path}")
    if not isinstance(data, dict) or not data.get("id"):
        raise GitLabApiError(0, f"Failed to resolve namespace id for {full_path}")
    return int(data["id"])


def _gitlab_user_id(api: GitLabApi) -> int:
    data = api.get("/user")
    if not isinstance(data, dict) or not data.get("id"):
        raise GitLabApiError(0, "Failed to resolve GitLab user id")
    return int(data["id"])


def _gitlab_branch_exists(api: GitLabApi, cfg: GitLabConfig, repo: str, branch: str) -> bool:
    project_id = _gitlab_project_id(cfg, repo)
    branch_id = urllib.parse.quote(branch, safe="")
    try:
        api.get(f"/projects/{project_id}/repository/branches/{branch_id}")
        return True
    except GitLabApiError as exc:
        if exc.status == 404:
            return False
        raise


def _validate_branch_name(name: str) -> None:
    if not name:
        raise ValueError("Branch name is empty")
    if name.strip("/") != name:
        raise ValueError(f"Branch name has leading/trailing slash: {name}")
    if "//" in name:
        raise ValueError(f"Branch name contains //: {name}")


def _validate_branch_config(cfg: GitLabConfig) -> None:
    for name in (cfg.github_prefix, cfg.github_product_branch, cfg.github_staging_branch, cfg.github_feature_branch, cfg.github_release_branch):
        _validate_branch_name(name)

def _ensure_gitlab_project(api: GitLabApi, cfg: GitLabConfig, repo: str) -> str:
    project_id = _gitlab_project_id(cfg, repo)
    try:
        api.get(f"/projects/{project_id}")
        return "exists"
    except GitLabApiError as exc:
        if exc.status != 404:
            raise
    namespace_id = _gitlab_namespace_id(api, f"{cfg.gitlab_group}/{cfg.gitlab_subgroup}")
    payload = {
        "name": repo,
        "path": repo,
        "namespace_id": namespace_id,
        "visibility": "private",
    }
    try:
        api.post("/projects", payload)
        return "created"
    except GitLabApiError as exc:
        if exc.status == 409:
            return "exists"
        raise


def _set_default_branch(api: GitLabApi, cfg: GitLabConfig, repo: str, branch: str) -> None:
    project_id = _gitlab_project_id(cfg, repo)
    api.put(f"/projects/{project_id}", {"default_branch": branch})


def _ref_sha(api: GitHubApi, owner: str, repo: str, ref: str) -> Optional[str]:
    try:
        resp = api.get(f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
    except GitHubApiError as exc:
        if exc.status == 404:
            return None
        raise
    if isinstance(resp.data, dict):
        return resp.data.get("object", {}).get("sha")
    return None


def _ls_remote(remote: str, ref: str) -> Optional[str]:
    try:
        output = _run_git(["ls-remote", "--heads", remote, f"refs/heads/{ref}"])
    except GitCommandError:
        return None
    if not output:
        return None
    return output.split()[0]


def _fetch_ref(remote: str, ref: str, repo_dir: str) -> None:
    _run_git(["fetch", remote, ref], cwd=repo_dir)


def _fetch_sha(remote: str, sha: str, repo_dir: str) -> None:
    _run_git(["fetch", remote, sha], cwd=repo_dir)


def _is_ancestor(repo_dir: str, older: str, newer: str) -> bool:
    try:
        _run_git(["merge-base", "--is-ancestor", older, newer], cwd=repo_dir)
        return True
    except GitCommandError:
        return False


def _push_ref(repo_dir: str, remote: str, sha: str, target_ref: str) -> None:
    if not target_ref or target_ref.strip("/") != target_ref:
        raise GitCommandError(f"Invalid target ref: {target_ref}")
    _run_git(["push", remote, f"{sha}:refs/heads/{target_ref}"], cwd=repo_dir)


def process_repo(
    api: GitHubApi,
    cfg: GitLabConfig,
    repo: Dict[str, Any],
) -> Dict[str, Any]:
    owner = cfg.github_org
    name = repo.get("name")
    result: Dict[str, Any] = {"name": name}
    if not name:
        result["notes"] = ["Skipped: missing repo name"]
        return result
    try:
        repo_details_resp = api.get(f"/repos/{owner}/{name}")
        repo_details = repo_details_resp.data if isinstance(repo_details_resp.data, dict) else {}
    except GitHubApiError as exc:
        result["notes"] = [f"Skipped: failed to fetch repo metadata ({exc.status})"]
        return result

    if repo_details.get("archived") or repo_details.get("disabled"):
        result["notes"] = ["Skipped: archived or disabled"]
        return result

    if not repo_details.get("fork") or not repo_details.get("parent"):
        result["notes"] = ["Skipped: not a fork or missing upstream"]
        return result

    product_ref = cfg.product_ref
    staging_ref = cfg.staging_ref
    feature_ref = cfg.feature_ref
    release_ref = cfg.release_ref
    for ref in (product_ref, staging_ref, feature_ref, release_ref):
        if not ref or ref.strip("/") != ref:
            result["notes"] = [f"Skipped: invalid ref {ref}"]
            return result

    product_sha = _ref_sha(api, owner, name, product_ref)
    staging_sha = _ref_sha(api, owner, name, staging_ref)
    feature_sha = _ref_sha(api, owner, name, feature_ref)

    missing = [
        ref
        for ref, sha in (
            (product_ref, product_sha),
            (staging_ref, staging_sha),
            (feature_ref, feature_sha),
        )
        if sha is None
    ]
    if missing:
        result["notes"] = [f"Skipped: missing refs {', '.join(missing)}"]
        return result

    gitlab_api = GitLabApi(cfg.gitlab_token, cfg.gitlab_host)
    try:
        project_status = _ensure_gitlab_project(gitlab_api, cfg, name)
    except GitLabApiError as exc:
        result["notes"] = [f"Skipped: gitlab project error ({exc.status})"]
        return result
    result["gitlab_project"] = project_status

    _gitlab_user_id(gitlab_api)

    with tempfile.TemporaryDirectory(prefix=f"gitlab-mirror-{name}-") as repo_dir:
        _run_git(["init", "--bare"], cwd=repo_dir)

        github_remote = _github_url(owner, name)
        gitlab_remote = _gitlab_url(cfg, name)

        _run_git(["remote", "add", "origin", github_remote], cwd=repo_dir)
        _run_git(["remote", "add", "gitlab", gitlab_remote], cwd=repo_dir)

        # fetch source SHAs (full history to avoid shallow push rejection)
        for sha in (product_sha, staging_sha, feature_sha):
            if sha:
                _run_git_with_token(["fetch", "origin", sha], _github_token(), cwd=repo_dir)

        mirror_targets = {
            f"github/{product_ref}": product_sha,
            f"github/{staging_ref}": staging_sha,
        }

        dev_targets = {
            product_ref: product_sha,
            staging_ref: staging_sha,
            feature_ref: feature_sha,
            release_ref: product_sha,
        }

        mirror_targets = {k: v for k, v in mirror_targets.items() if v}
        dev_targets = {k: v for k, v in dev_targets.items() if v}

        mirror_results: Dict[str, str] = {}
        dev_results: Dict[str, str] = {}
        branch_presence: Dict[str, str] = {}

        # Update mirror targets (FF-only)
        for target_ref, sha in mirror_targets.items():
            if not sha:
                mirror_results[target_ref] = "skipped: missing source"
                continue
            remote_sha = _ls_remote(gitlab_remote, target_ref)
            if remote_sha:
                try:
                    _run_git_with_gitlab_token(["fetch", "gitlab", target_ref], cfg.gitlab_token, cwd=repo_dir)
                except GitCommandError as exc:
                    mirror_results[target_ref] = f"skipped: fetch failed ({exc})"
                    continue
                if not _is_ancestor(repo_dir, remote_sha, sha):
                    mirror_results[target_ref] = "skipped: diverged"
                    continue
            try:
                _run_git_with_gitlab_token(["push", "gitlab", f"{sha}:refs/heads/{target_ref}"], cfg.gitlab_token, cwd=repo_dir)
                mirror_results[target_ref] = "updated" if remote_sha else "created"
            except GitCommandError as exc:
                mirror_results[target_ref] = f"failed: {exc}"
                continue

        # Create dev targets only if missing (create-once)
        for target_ref, sha in dev_targets.items():
            if not sha:
                dev_results[target_ref] = "skipped: missing source"
                continue
            remote_sha = _ls_remote(gitlab_remote, target_ref)
            if remote_sha:
                dev_results[target_ref] = "exists"
                continue
            try:
                _run_git_with_gitlab_token(["push", "gitlab", f"{sha}:refs/heads/{target_ref}"], cfg.gitlab_token, cwd=repo_dir)
                dev_results[target_ref] = "created"
            except GitCommandError as exc:
                dev_results[target_ref] = f"failed: {exc}"

        # Ensure default branch is mcr/main (product)
        if _gitlab_branch_exists(gitlab_api, cfg, name, product_ref):
            try:
                _set_default_branch(gitlab_api, cfg, name, product_ref)
                result["gitlab_default_branch"] = product_ref
            except GitLabApiError as exc:
                result["gitlab_default_branch"] = f"failed ({exc.status})"
        else:
            result["gitlab_default_branch"] = "skipped: branch missing"

        # Final branch presence check (API-based)
    for branch in [
        f"github/{product_ref}",
        f"github/{staging_ref}",
        product_ref,
        staging_ref,
        feature_ref,
        release_ref,
    ]:
        try:
            present = _gitlab_branch_exists(gitlab_api, cfg, name, branch)
            branch_presence[branch] = "present" if present else "missing"
        except GitLabApiError as exc:
            branch_presence[branch] = f"error ({exc.status})"

        result["gitlab_mirror"] = mirror_results
        result["gitlab_dev_branches"] = dev_results
        result["gitlab_branches"] = branch_presence
        result["gitlab_default_branch"] = result.get("gitlab_default_branch")
        return result


def format_summary(cfg: GitLabConfig, results: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# GitLab mirror summary")
    lines.append("")
    lines.append("## Config")
    config_items = {
        "github_org": cfg.github_org,
        "github_prefix": cfg.github_prefix,
        "github_product_branch": cfg.github_product_branch,
        "github_staging_branch": cfg.github_staging_branch,
        "gitlab_group": cfg.gitlab_group,
        "gitlab_subgroup": cfg.gitlab_subgroup,
        "gitlab_host": cfg.gitlab_host,
    }
    for key, value in sorted(config_items.items()):
        lines.append(f"- **{key}**: `{value}`")
    lines.append("")
    lines.append("## Repositories")
    if not results:
        lines.append("- No repositories processed.")
        return "\n".join(lines)
    for repo in results:
        if not isinstance(repo, dict):
            lines.append("### <unknown>")
            lines.append("- **notes**: invalid repository result")
            continue
        name = repo.get("name")
        lines.append(f"### {name}")
        if "notes" in repo:
            lines.append(f"- **notes**: {repo['notes']}")
            continue
        if "gitlab_default_branch" in repo:
            lines.append(f"- **gitlab_default_branch**: {repo['gitlab_default_branch']}")
        lines.append(f"- **gitlab_mirror**: {json.dumps(repo.get('gitlab_mirror', {}))}")
        lines.append(f"- **gitlab_dev_branches**: {json.dumps(repo.get('gitlab_dev_branches', {}))}")
        lines.append(f"- **gitlab_branches**: {json.dumps(repo.get('gitlab_branches', {}))}")
    return "\n".join(lines)


def any_gitlab_project_created(results: List[Dict[str, Any]]) -> bool:
    for repo in results:
        if isinstance(repo, dict) and repo.get("gitlab_project") == "created":
            return True
    return False


def _preflight(api: GitHubApi, cfg: GitLabConfig) -> Dict[str, str]:
    summary: Dict[str, str] = {}
    org_resp = api.get(f"/orgs/{cfg.github_org}")
    if not isinstance(org_resp.data, dict) or org_resp.data.get("login") != cfg.github_org:
        raise GitHubApiError(0, "GitHub org access check failed")
    summary["github_org_access"] = "ok"

    gitlab_api = GitLabApi(cfg.gitlab_token, cfg.gitlab_host)
    namespace_path = f"{cfg.gitlab_group}/{cfg.gitlab_subgroup}"
    _gitlab_namespace_id(gitlab_api, namespace_path)
    summary["gitlab_namespace_access"] = "ok"
    _gitlab_user_id(gitlab_api)
    summary["gitlab_user_access"] = "ok"
    return summary


def main() -> int:
    token = _github_token()
    cfg = load_config()
    _validate_branch_config(cfg)
    repo_filter = os.environ.get("INPUT_REPO") or None
    if repo_filter:
        repo_filter = repo_filter.strip() or None

    api = GitHubApi(token=token)
    preflight = _preflight(api, cfg)
    repos = discover_fork_repos(api, cfg.github_org, repo_filter)
    results: List[Dict[str, Any]] = []
    for repo in repos:
        try:
            result = process_repo(api, cfg, repo)
        except Exception as exc:
            name = repo.get("name") if isinstance(repo, dict) else None
            result = {"name": name, "notes": [f"Skipped: processing error ({exc})"]}
        if isinstance(result, dict):
            results.append(result)
        else:
            results.append({"name": None, "notes": ["Skipped: invalid result"]})
    summary = format_summary(cfg, results)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("## Preflight\n")
            for key, value in sorted(preflight.items()):
                handle.write(f"- **{key}**: `{value}`\n")
            handle.write("\n")
            handle.write(summary)
            handle.write("\n")
    else:
        print(summary)

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        created_flag = "true" if any_gitlab_project_created(results) else "false"
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"gitlab_created={created_flag}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
