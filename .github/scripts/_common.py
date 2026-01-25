from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

GITHUB_API = "https://api.github.com"


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def optional_env(name: str) -> Optional[str]:
    value = os.environ.get(name, "").strip()
    return value or None


def require_secret(name: str) -> str:
    file_path = os.environ.get(f\"{name}_FILE\", \"\").strip()
    if not file_path:
        raise SystemExit(f\"Missing required secret file env var: {name}_FILE\")
    with open(file_path, \"r\", encoding=\"utf-8\") as handle:
        value = handle.read().strip()
    if not value:
        raise SystemExit(f\"Empty secret file for {name}\")
    return value


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def create_app_jwt(app_id: str, pem_path: str) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 30, "exp": now + 9 * 60, "iss": app_id}
    encoded = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(payload).encode())}"
    signature = subprocess.check_output(
        ["openssl", "dgst", "-sha256", "-sign", pem_path],
        input=encoded.encode("utf-8"),
    )
    return f"{encoded}.{b64url(signature)}"


def github_request(token: str, method: str, path: str, payload: Optional[dict] = None) -> Any:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "gh-actions-shared",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise ApiError(exc.code, body or "GitHub API error") from exc


def get_installation_token(app_id: str, pem_path: str, installation_id: int) -> str:
    jwt = create_app_jwt(app_id, pem_path)
    data = github_request(jwt, "POST", f"/app/installations/{installation_id}/access_tokens")
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise SystemExit("Failed to obtain installation token")
    return str(token)


def parse_installations(value: str) -> Dict[str, int]:
    data = json.loads(value)
    if not isinstance(data, dict):
        return {}
    out: Dict[str, int] = {}
    for key, val in data.items():
        if isinstance(val, int):
            out[key] = val
    return out


def get_installation_token_for_org(app_id: str, pem_path: str, install_json: str, org: str) -> str:
    mapping = parse_installations(install_json)
    install_id = mapping.get(org)
    if not install_id:
        raise SystemExit(f"Missing installation id for org: {org}")
    return get_installation_token(app_id, pem_path, install_id)


def list_org_repos(token: str, org: str) -> List[dict]:
    repos: List[dict] = []
    page = 1
    while True:
        path = f"/orgs/{org}/repos?per_page=100&page={page}"
        data = github_request(token, "GET", path)
        if not isinstance(data, list):
            break
        repos.extend([item for item in data if isinstance(item, dict)])
        if len(data) < 100:
            break
        page += 1
    return repos


def get_repo(token: str, owner: str, repo: str) -> dict:
    data = github_request(token, "GET", f"/repos/{owner}/{repo}")
    return data if isinstance(data, dict) else {}


def get_branch_sha(token: str, owner: str, repo: str, branch: str) -> str:
    ref = urllib.parse.quote(branch, safe="")
    data = github_request(token, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
    sha = data.get("object", {}).get("sha") if isinstance(data, dict) else None
    if not sha:
        raise SystemExit(f"Missing SHA for branch {branch}")
    return str(sha)


def branch_exists(token: str, owner: str, repo: str, branch: str) -> bool:
    ref = urllib.parse.quote(branch, safe="")
    try:
        github_request(token, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
        return True
    except ApiError as exc:
        if exc.status == 404:
            return False
        raise


def create_branch(token: str, owner: str, repo: str, branch: str, sha: str) -> None:
    github_request(
        token,
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": sha},
    )


def update_branch(token: str, owner: str, repo: str, branch: str, sha: str, force: bool = False) -> None:
    ref = urllib.parse.quote(branch, safe="")
    github_request(
        token,
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{ref}",
        {"sha": sha, "force": force},
    )
