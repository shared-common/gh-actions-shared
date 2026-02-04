import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from log_sanitize import sanitize

GITHUB_API = "https://api.github.com"
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

_REF_INVALID = re.compile(r"[ ~^:?*[\]\\]")
_REPO_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


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
    file_path = os.environ.get(f"{name}_FILE", "").strip()
    if not file_path:
        raise SystemExit(f"Missing required secret file env var: {name}_FILE")
    path = Path(file_path)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing secret file for {name}: {file_path}") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read secret file for {name}: {file_path}") from exc
    if not value:
        raise SystemExit(f"Empty secret file for {name}")
    return value


def load_json(path: str, label: str = "JSON") -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} file not found: {path}") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read {label} file: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{label} file is not valid JSON ({exc.msg}) at line {exc.lineno} column {exc.colno}"
        ) from exc


def config_path(name: str) -> str:
    return str(CONFIG_DIR / name)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def create_app_jwt(app_id: str, pem_path: str) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 30, "exp": now + 9 * 60, "iss": app_id}
    encoded = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(payload).encode())}"
    try:
        signature = subprocess.check_output(
            ["openssl", "dgst", "-sha256", "-sign", pem_path],
            input=encoded.encode("utf-8"),
        )
    except FileNotFoundError as exc:
        raise SystemExit("openssl not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Failed to sign JWT with app PEM") from exc
    return f"{encoded}.{b64url(signature)}"


def github_request(
    token: str,
    method: str,
    path: str,
    payload: Optional[dict] = None,
    *,
    retries: int = 3,
    timeout: int = 30,
) -> Any:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "gh-actions-shared",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
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
                    raise ApiError(resp.status, "Invalid JSON response from GitHub API") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            body = sanitize(body)
            if exc.code == 403 and attempt < retries - 1:
                headers = exc.headers or {}
                retry_after_raw = headers.get("Retry-After")
                wait = None
                if retry_after_raw and retry_after_raw.isdigit():
                    wait = int(retry_after_raw)
                else:
                    remaining = headers.get("X-RateLimit-Remaining")
                    reset_raw = headers.get("X-RateLimit-Reset")
                    if remaining == "0" and reset_raw and reset_raw.isdigit():
                        reset_at = int(reset_raw)
                        wait = max(0, reset_at - int(time.time()))
                if wait is not None:
                    wait = max(1, min(60, wait))
                    time.sleep(wait)
                    attempt += 1
                    continue
            if exc.code in {500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(exc.code, body or "GitHub API error") from exc
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(0, f"Network error contacting GitHub API: {exc}") from exc


def github_request_public(
    method: str,
    path: str,
    payload: Optional[dict] = None,
    *,
    retries: int = 3,
    timeout: int = 30,
) -> Any:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gh-actions-shared",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
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
                    raise ApiError(resp.status, "Invalid JSON response from GitHub API") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            body = sanitize(body)
            if exc.code == 403 and attempt < retries - 1:
                headers = exc.headers or {}
                retry_after_raw = headers.get("Retry-After")
                wait = None
                if retry_after_raw and retry_after_raw.isdigit():
                    wait = int(retry_after_raw)
                else:
                    remaining = headers.get("X-RateLimit-Remaining")
                    reset_raw = headers.get("X-RateLimit-Reset")
                    if remaining == "0" and reset_raw and reset_raw.isdigit():
                        reset_at = int(reset_raw)
                        wait = max(0, reset_at - int(time.time()))
                if wait is not None:
                    wait = max(1, min(60, wait))
                    time.sleep(wait)
                    attempt += 1
                    continue
            if exc.code in {500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(exc.code, body or "GitHub API error") from exc
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                attempt += 1
                continue
            raise ApiError(0, f"Network error contacting GitHub API: {exc}") from exc


def get_installation_token(app_id: str, pem_path: str, installation_id: int) -> str:
    jwt = create_app_jwt(app_id, pem_path)
    data = github_request(jwt, "POST", f"/app/installations/{installation_id}/access_tokens")
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise SystemExit("Failed to obtain installation token")
    return str(token)


def parse_installations(value: str) -> Dict[str, int]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit("GH_INSTALL_JSON is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SystemExit("GH_INSTALL_JSON must be a JSON object mapping org to installation id")
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


def validate_repo_full_name(value: str) -> Tuple[str, str]:
    if not isinstance(value, str) or "/" not in value:
        raise SystemExit("repo_full_name must be in the form <org>/<repo>")
    org, repo = value.split("/", 1)
    if not _REPO_PART.match(org):
        raise SystemExit(f"Invalid org name: {org}")
    if not _REPO_PART.match(repo):
        raise SystemExit(f"Invalid repo name: {repo}")
    return org, repo


def validate_ref_name(value: str, label: str = "ref") -> None:
    if not value or value.strip() != value:
        raise SystemExit(f"{label} is empty or has surrounding whitespace")
    if value.startswith("/") or value.endswith("/"):
        raise SystemExit(f"{label} must not start or end with '/'")
    if value.endswith(".lock"):
        raise SystemExit(f"{label} must not end with .lock")
    if "//" in value or ".." in value or "@{" in value:
        raise SystemExit(f"{label} contains invalid sequence")
    if _REF_INVALID.search(value):
        raise SystemExit(f"{label} contains invalid characters")
    for ch in value:
        if ord(ch) < 32 or ord(ch) == 127:
            raise SystemExit(f"{label} contains control characters")


def allowed_orgs(install_json: str) -> List[str]:
    mapping = parse_installations(install_json)
    return sorted(mapping.keys())


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


def get_branch_sha_public(owner: str, repo: str, branch: str) -> str:
    ref = urllib.parse.quote(branch, safe="")
    data = github_request_public("GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
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
