from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from _common import ApiError, get_branch_sha, require_secret, validate_repo_full_name
from branch_policy import BranchPolicy, load_branch_policy
from gitlab_sync_profile import resolve_profile_values


@dataclass(frozen=True)
class GitlabTarget:
    project_path: str
    git_username: str
    api_token: str
    base_url: str


def load_input() -> dict:
    path = os.environ.get("INPUT_PATH")
    if not path:
        raise SystemExit("Missing INPUT_PATH")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing INPUT_PATH file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc


def _require_branch(policy: BranchPolicy, env_name: str) -> str:
    spec = policy.by_env.get(env_name)
    if not spec:
        raise SystemExit(f"Branch policy missing {env_name}")
    return spec.full_name


def build_tracked_branches(policy: BranchPolicy) -> Dict[str, str]:
    main_branch = _require_branch(policy, "GIT_BRANCH_MAIN")
    staging_branch = _require_branch(policy, "GIT_BRANCH_STAGING")
    return {
        f"github/{main_branch}": main_branch,
        f"github/{staging_branch}": staging_branch,
    }


def select_sync_sources(input_data: dict, tracked_sources: Sequence[str]) -> List[str]:
    unique_sources = list(dict.fromkeys(tracked_sources))
    job_type = str(input_data.get("job_type") or "create").strip()
    if job_type in {"create", "polling"}:
        return unique_sources
    ref = input_data.get("ref")
    if isinstance(ref, str) and ref.startswith("refs/heads/"):
        branch = ref[len("refs/heads/") :]
        if branch in unique_sources:
            return [branch]
    return unique_sources


def require_gitlab_group_path(input_data: dict) -> str:
    value = input_data.get("gitlab_group_path")
    if isinstance(value, str):
        group_path = value.strip()
    else:
        mapping_raw = require_secret("GL_MAPPING_JSON")
        try:
            mapping = json.loads(mapping_raw)
        except json.JSONDecodeError as exc:
            raise SystemExit("GL_MAPPING_JSON is not valid JSON") from exc
        if not isinstance(mapping, dict):
            raise SystemExit("GL_MAPPING_JSON must be a JSON object mapping org to GitLab group path")
        candidates = []
        target_org = os.environ.get("TARGET_ORG", "").strip()
        if target_org:
            candidates.append(target_org)
        target_profile = os.environ.get("TARGET_PROFILE", "").strip()
        if target_profile:
            candidates.append(target_profile)
        repo_full_name = input_data.get("repo_full_name")
        if isinstance(repo_full_name, str) and "/" in repo_full_name:
            candidates.append(repo_full_name.split("/", 1)[0].strip())
        group_path = ""
        seen = set()
        for key in candidates:
            if not key or key in seen:
                continue
            seen.add(key)
            mapped = mapping.get(key)
            if isinstance(mapped, str) and mapped.strip():
                group_path = mapped.strip()
                break
    if "/" not in group_path:
        raise SystemExit("gitlab_group_path must include at least one slash or be resolvable from GL_MAPPING_JSON")
    return group_path


def resolve_gitlab_target(target_profile: str, repo_name: str, group_path: str) -> GitlabTarget:
    git_username, api_token = resolve_profile_values(target_profile, require_secret)

    return GitlabTarget(
        project_path=f"{group_path}/{repo_name}",
        git_username=git_username,
        api_token=api_token,
        base_url=require_secret("GL_BASE_URL"),
    )


def _sanitize_text(text: str, secrets: Iterable[str]) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def _gitlab_request(
    method: str,
    base_url: str,
    path: str,
    token: str,
    payload: Optional[dict] = None,
    *,
    retries: int = 3,
    timeout: int = 30,
) -> Any:
    url = f"{base_url.rstrip('/')}/api/v4{path}"
    data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
    req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if not body:
                    return None
                try:
                    return json.loads(body.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise ApiError(resp.status, "Invalid JSON response from GitLab API") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            body = _sanitize_text(body, (token,))
            if exc.code in {500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(exc.code, body or "GitLab API error") from exc
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(0, f"Network error contacting GitLab API: {exc}") from exc


def _get_gitlab_project(base_url: str, token: str, project_path: str) -> Optional[dict]:
    encoded = urllib.parse.quote(project_path, safe="")
    try:
        data = _gitlab_request("GET", base_url, f"/projects/{encoded}", token)
    except ApiError as exc:
        if exc.status == 404:
            return None
        raise
    return data if isinstance(data, dict) else None


def _get_gitlab_group_id(base_url: str, token: str, group_path: str) -> int:
    encoded = urllib.parse.quote(group_path, safe="")
    try:
        data = _gitlab_request("GET", base_url, f"/groups/{encoded}", token)
    except ApiError as exc:
        if exc.status != 404:
            raise
        data = _search_gitlab_group(base_url, token, group_path)
        if data is None:
            project = _get_gitlab_project(base_url, token, group_path)
            if project:
                raise SystemExit(f"GitLab path exists as a project, not a group: {group_path}") from exc
            raise SystemExit(f"GitLab group not found or not accessible: {group_path}") from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise SystemExit(f"Unable to resolve GitLab group id for {group_path}")
    return int(data["id"])


def _search_gitlab_group(base_url: str, token: str, group_path: str) -> Optional[dict]:
    target_full = group_path.lower()
    target_name = group_path.rsplit("/", 1)[-1].lower()
    search = urllib.parse.quote(target_name, safe="")
    page = 1
    while True:
        data = _gitlab_request(
            "GET",
            base_url,
            f"/groups?search={search}&per_page=100&page={page}",
            token,
        )
        if not isinstance(data, list) or not data:
            return None
        for item in data:
            if not isinstance(item, dict):
                continue
            full_path = str(item.get("full_path", "")).lower()
            if full_path == target_full:
                return item
        if len(data) < 100:
            return None
        page += 1


def _find_project_in_group(base_url: str, token: str, group_id: int, project_path: str, project_name: str) -> Optional[dict]:
    target_path = project_name.lower()
    target_full = project_path.lower()
    search = urllib.parse.quote(project_name, safe="")
    page = 1
    while True:
        data = _gitlab_request(
            "GET",
            base_url,
            f"/groups/{group_id}/projects?search={search}&per_page=100&page={page}",
            token,
        )
        if not isinstance(data, list) or not data:
            return None
        for item in data:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).lower()
            path_ns = str(item.get("path_with_namespace", "")).lower()
            if path_ns == target_full or path == target_path:
                return item
        if len(data) < 100:
            return None
        page += 1


def _is_project_exists_error(exc: ApiError) -> bool:
    if exc.status not in {400, 409}:
        return False
    msg = str(exc).lower()
    return "already exists" in msg or "has already been taken" in msg or "path has already been taken" in msg


def ensure_gitlab_project(target: GitlabTarget) -> tuple[dict, bool]:
    existing = _get_gitlab_project(target.base_url, target.api_token, target.project_path)
    if existing:
        return existing, False

    group_path = "/".join(target.project_path.split("/")[:-1])
    if not group_path:
        raise SystemExit("GitLab project path must include a group path")
    group_id = _get_gitlab_group_id(target.base_url, target.api_token, group_path)
    project_name = target.project_path.split("/")[-1]
    existing = _find_project_in_group(target.base_url, target.api_token, group_id, target.project_path, project_name)
    if existing:
        return existing, False

    payload = {
        "name": project_name,
        "path": project_name,
        "namespace_id": group_id,
        "visibility": os.environ.get("GL_PROJECT_VISIBILITY", "private").strip() or "private",
    }
    try:
        created = _gitlab_request("POST", target.base_url, "/projects", target.api_token, payload)
    except ApiError as exc:
        if not _is_project_exists_error(exc):
            raise
        existing = _get_gitlab_project(target.base_url, target.api_token, target.project_path)
        if existing:
            return existing, False
        existing = _find_project_in_group(target.base_url, target.api_token, group_id, target.project_path, project_name)
        if existing:
            return existing, False
        raise
    if not isinstance(created, dict):
        raise SystemExit("GitLab project create returned invalid response")
    return created, True


def _gitlab_branch_exists(base_url: str, token: str, project_id: int, branch: str) -> bool:
    encoded = urllib.parse.quote(branch, safe="")
    try:
        _gitlab_request("GET", base_url, f"/projects/{project_id}/repository/branches/{encoded}", token)
        return True
    except ApiError as exc:
        if exc.status == 404:
            return False
        raise


def _get_gitlab_branch_sha(base_url: str, token: str, project_id: int, branch: str) -> Optional[str]:
    encoded = urllib.parse.quote(branch, safe="")
    try:
        data = _gitlab_request("GET", base_url, f"/projects/{project_id}/repository/branches/{encoded}", token)
    except ApiError as exc:
        if exc.status == 404:
            return None
        raise
    if not isinstance(data, dict):
        return None
    commit = data.get("commit")
    if not isinstance(commit, dict):
        return None
    commit_id = commit.get("id")
    return str(commit_id) if isinstance(commit_id, str) else None


def _run(cmd: List[str], cwd: Optional[str] = None, *, secrets: Iterable[str] = ()) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(_sanitize_text(stderr, secrets))
    return proc


def _branch_exists(remote_url: str, branch: str, *, secrets: Iterable[str] = ()) -> bool:
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", remote_url, branch],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(_sanitize_text(stderr, secrets))
    return bool(proc.stdout.strip())


def _fetch_branch(
    repo_path: str,
    remote_url: str,
    branch: str,
    fetched: set[str],
    *,
    remote_name: str,
    secrets: Iterable[str],
) -> None:
    if branch not in fetched:
        _run(
            [
                "git",
                "-C",
                repo_path,
                "fetch",
                remote_url,
                f"refs/heads/{branch}:refs/heads/{branch}",
            ],
            secrets=secrets,
        )
        fetched.add(branch)
    _run(
        [
            "git",
            "-C",
            repo_path,
            "lfs",
            "fetch",
            remote_name,
            f"refs/heads/{branch}",
        ],
        secrets=secrets,
    )


def _lfs_push(repo_path: str, remote_name: str, ref: str, *, source_remote: Optional[str], secrets: Iterable[str]) -> None:
    try:
        _run(
            [
                "git",
                "-C",
                repo_path,
                "lfs",
                "push",
                remote_name,
                f"refs/heads/{ref}",
            ],
            secrets=secrets,
        )
    except SystemExit as exc:
        if "Unable to find source for object" not in str(exc) or not source_remote:
            raise
        _run(["git", "-C", repo_path, "lfs", "fetch", "--all", source_remote], secrets=secrets)
        _run(
            [
                "git",
                "-C",
                repo_path,
                "lfs",
                "push",
                remote_name,
                f"refs/heads/{ref}",
            ],
            secrets=secrets,
        )


def _push_branch(
    repo_path: str,
    remote_url: str,
    source_branch: str,
    target_branch: str,
    *,
    remote_name: str,
    lfs_ref: str,
    secrets: Iterable[str],
    allow_existing: bool = False,
    allow_force_if_needed: bool = False,
    expected_remote_sha: Optional[str] = None,
) -> None:
    _lfs_push(repo_path, remote_name, lfs_ref, source_remote="github", secrets=secrets)
    command = [
        "git",
        "-C",
        repo_path,
        "push",
        remote_url,
        f"refs/heads/{source_branch}:refs/heads/{target_branch}",
    ]
    proc = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode == 0:
        return
    stderr = _sanitize_text(proc.stderr.decode("utf-8", errors="replace").strip(), secrets)
    if allow_existing and "already exists" in stderr.lower():
        return
    if allow_force_if_needed and _should_force_retry(stderr):
        force_command = [
            "git",
            "-C",
            repo_path,
            "push",
            "--force-with-lease="
            + _build_force_with_lease(target_branch, expected_remote_sha),
            remote_url,
            f"refs/heads/{source_branch}:refs/heads/{target_branch}",
        ]
        force_proc = subprocess.run(force_command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if force_proc.returncode == 0:
            return
        stderr = _sanitize_text(force_proc.stderr.decode("utf-8", errors="replace").strip(), secrets)
    raise SystemExit(stderr)


def _normalize_sha(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value.strip().lower() or None


def _build_force_with_lease(target_branch: str, expected_remote_sha: Optional[str]) -> str:
    target_ref = f"refs/heads/{target_branch}"
    normalized_sha = _normalize_sha(expected_remote_sha)
    if normalized_sha:
        return f"{target_ref}:{normalized_sha}"
    return target_ref


def _should_force_retry(stderr: str) -> bool:
    lowered = stderr.lower()
    patterns = (
        "non-fast-forward",
        "[rejected]",
        "fetch first",
        "failed to update ref",
        "cannot lock ref",
        "stale info",
    )
    return any(pattern in lowered for pattern in patterns)


def _set_default_branch(base_url: str, token: str, project_id: int, branch: str, current: Optional[str]) -> bool:
    if current == branch:
        return False
    try:
        _gitlab_request("PUT", base_url, f"/projects/{project_id}", token, {"default_branch": branch})
    except ApiError as exc:
        if exc.status == 403:
            return False
        raise
    return True


def _protect_branches(base_url: str, token: str, project_id: int, branches: Sequence[str], *, allow_force_push: bool) -> List[str]:
    try:
        existing = _gitlab_request("GET", base_url, f"/projects/{project_id}/protected_branches", token)
    except ApiError as exc:
        if exc.status == 403:
            return []
        raise
    existing_map = {
        str(item.get("name")): item
        for item in existing
        if isinstance(existing, list) and isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(existing, list) else {}
    changed: List[str] = []
    for branch in branches:
        branch_entry = existing_map.get(branch)
        encoded_branch = urllib.parse.quote(branch, safe="")
        if branch_entry:
            current_allow_force_push = bool(branch_entry.get("allow_force_push"))
            if current_allow_force_push == allow_force_push:
                continue
            try:
                _gitlab_request(
                    "PATCH",
                    base_url,
                    f"/projects/{project_id}/protected_branches/{encoded_branch}?allow_force_push={'true' if allow_force_push else 'false'}",
                    token,
                )
            except ApiError as exc:
                if exc.status == 403:
                    continue
                raise
            changed.append(branch)
            continue
        payload = {
            "name": branch,
            "push_access_level": 40,
            "merge_access_level": 40,
            "unprotect_access_level": 40,
            "allow_force_push": allow_force_push,
        }
        try:
            _gitlab_request("POST", base_url, f"/projects/{project_id}/protected_branches", token, payload)
        except ApiError as exc:
            if exc.status not in {403, 409, 422}:
                raise
        else:
            changed.append(branch)
    return changed


def _protect_tags(base_url: str, token: str, project_id: int, tags: Sequence[str]) -> List[str]:
    try:
        existing = _gitlab_request("GET", base_url, f"/projects/{project_id}/protected_tags", token)
    except ApiError as exc:
        if exc.status == 403:
            return []
        raise
    existing_names = {
        item.get("name")
        for item in existing
        if isinstance(existing, list) and isinstance(item, dict)
    } if isinstance(existing, list) else set()
    created: List[str] = []
    for tag in tags:
        if tag in existing_names:
            continue
        payload = {"name": tag, "create_access_level": 40}
        try:
            _gitlab_request("POST", base_url, f"/projects/{project_id}/protected_tags", token, payload)
        except ApiError as exc:
            if exc.status not in {403, 409, 422}:
                raise
        else:
            created.append(tag)
    return created


def main() -> int:
    input_data = load_input()
    repo_full_name = input_data.get("repo_full_name")
    org, repo_name = validate_repo_full_name(repo_full_name)
    job_type = str(input_data.get("job_type") or "create").strip()
    if job_type not in {"create", "polling", "sync"}:
        raise SystemExit(f"Unsupported job_type: {job_type}")

    policy = load_branch_policy()
    required_branches = [spec.full_name for spec in policy.order]
    tracked_updates = build_tracked_branches(policy)
    tracked_sources = list(tracked_updates.values())
    tracked_targets = list(tracked_updates.keys())
    main_branch = _require_branch(policy, "GIT_BRANCH_MAIN")

    target_org = os.environ.get("TARGET_ORG", "").strip()
    if not target_org:
        raise SystemExit("Missing TARGET_ORG")
    if target_org != org:
        raise SystemExit("TARGET_ORG does not match repo_full_name")
    target_profile = os.environ.get("TARGET_PROFILE", "").strip()
    if not target_profile:
        raise SystemExit("Missing TARGET_PROFILE")
    target = resolve_gitlab_target(target_profile, repo_name, require_gitlab_group_path(input_data))
    project, project_created = ensure_gitlab_project(target)
    project_id = project.get("id") if isinstance(project, dict) else None
    if not project_id:
        raise SystemExit("Failed to resolve GitLab project ID")

    gh_install_token = require_secret("GH_INSTALL_TOKEN")

    github_url = f"https://x-access-token:{urllib.parse.quote(gh_install_token, safe='')}@github.com/{org}/{repo_name}.git"
    base_host = target.base_url.replace("https://", "").replace("http://", "").rstrip("/")
    gitlab_url = (
        f"https://{urllib.parse.quote(target.git_username, safe='')}:{urllib.parse.quote(target.api_token, safe='')}"
        f"@{base_host}/{target.project_path}.git"
    )
    secrets = (gh_install_token, target.api_token, target.git_username)
    os.environ["GIT_TERMINAL_PROMPT"] = "0"

    results: Dict[str, List[str]] = {"created": [], "updated": [], "skipped": []}

    with tempfile.TemporaryDirectory() as repo_dir:
        repo_path = os.path.join(repo_dir, "repo.git")
        _run(["git", "init", "--bare", repo_path], secrets=secrets)
        _run(["git", "-C", repo_path, "remote", "add", "github", github_url], secrets=secrets)
        _run(["git", "-C", repo_path, "remote", "add", "gitlab", gitlab_url], secrets=secrets)
        _run(["git", "-C", repo_path, "lfs", "install", "--local"], secrets=secrets)

        fetched: set[str] = set()
        if project_created:
            results["created"].append(f"project:{target.project_path}")

        for branch in required_branches:
            if _gitlab_branch_exists(target.base_url, target.api_token, int(project_id), branch):
                continue
            if _branch_exists(gitlab_url, branch, secrets=secrets):
                continue
            _fetch_branch(repo_path, github_url, branch, fetched, remote_name="github", secrets=secrets)
            _push_branch(
                repo_path,
                gitlab_url,
                branch,
                branch,
                remote_name="gitlab",
                lfs_ref=branch,
                secrets=secrets,
                allow_existing=True,
            )
            results["created"].append(branch)

        for target_branch, source_branch in tracked_updates.items():
            if _gitlab_branch_exists(target.base_url, target.api_token, int(project_id), target_branch):
                continue
            if _branch_exists(gitlab_url, target_branch, secrets=secrets):
                continue
            _fetch_branch(repo_path, github_url, source_branch, fetched, remote_name="github", secrets=secrets)
            _push_branch(
                repo_path,
                gitlab_url,
                source_branch,
                target_branch,
                remote_name="gitlab",
                lfs_ref=source_branch,
                secrets=secrets,
                allow_existing=True,
            )
            results["created"].append(target_branch)

        ref_sha_cache: Dict[str, Optional[str]] = {}
        ref_value = input_data.get("ref")
        after_value = _normalize_sha(input_data.get("after"))
        if isinstance(ref_value, str) and ref_value.startswith("refs/heads/") and after_value:
            ref_sha_cache[ref_value[len("refs/heads/") :]] = after_value

        for source_branch in select_sync_sources(input_data, tracked_sources):
            target_branch = f"github/{source_branch}"
            gh_sha = ref_sha_cache.get(source_branch)
            if gh_sha is None:
                gh_sha = _normalize_sha(get_branch_sha(gh_install_token, org, repo_name, source_branch))
                ref_sha_cache[source_branch] = gh_sha
            gl_sha = _normalize_sha(_get_gitlab_branch_sha(target.base_url, target.api_token, int(project_id), target_branch))
            if gh_sha and gl_sha == gh_sha:
                results["skipped"].append(target_branch)
                continue
            _fetch_branch(repo_path, github_url, source_branch, fetched, remote_name="github", secrets=secrets)
            _push_branch(
                repo_path,
                gitlab_url,
                source_branch,
                target_branch,
                remote_name="gitlab",
                lfs_ref=source_branch,
                secrets=secrets,
                allow_force_if_needed=True,
                expected_remote_sha=gl_sha,
            )
            if gl_sha is None:
                results["created"].append(target_branch)
            else:
                results["updated"].append(target_branch)

    current_default = project.get("default_branch") if isinstance(project, dict) else None
    if _set_default_branch(target.base_url, target.api_token, int(project_id), main_branch, current_default):
        results["updated"].append(f"default:{main_branch}")

    protected = _protect_branches(
        target.base_url,
        target.api_token,
        int(project_id),
        tracked_targets,
        allow_force_push=True,
    )
    results["created"].extend([f"protected:{branch}" for branch in protected])
    protected_tags = _protect_tags(target.base_url, target.api_token, int(project_id), ["*"])
    results["created"].extend([f"protected-tag:{tag}" for tag in protected_tags])

    payload = {
        "repo": repo_full_name,
        "job_type": job_type,
        "results": results,
    }
    event_id = input_data.get("event_id")
    if isinstance(event_id, str) and event_id:
        payload["event_id"] = event_id

    output_path = os.environ.get("OUTPUT_PATH")
    if output_path:
        Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
