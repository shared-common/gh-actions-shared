from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

from logging_util import redact_text

MAX_SECRET_BYTES = 64 * 1024
DEFAULT_ALLOWED_ENV = {
    "BWS_ACCESS_TOKEN",
    "BWS_PROJECT_ID",
    "GITHUB_ACTIONS",
    "GITHUB_ENV",
    "GITHUB_OUTPUT",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_WORKFLOW",
    "GITHUB_JOB",
    "GITHUB_REF",
    "GITHUB_REF_NAME",
    "GITHUB_SHA",
    "GITHUB_REPOSITORY",
    "GITHUB_SERVER_URL",
    "GITHUB_API_URL",
    "RUNNER_TEMP",
    "RUNNER_OS",
    "RUNNER_ARCH",
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONPATH",
    "pythonLocation",
    "Python_ROOT_DIR",
    "Python2_ROOT_DIR",
    "Python3_ROOT_DIR",
    "PKG_CONFIG_PATH",
    "LD_LIBRARY_PATH",
    "INPUT_REPO",
}
DEFAULT_ALLOWED_SUFFIXES = (
    "_FILE",
)
DEFAULT_ALLOWED_PREFIXES = (
    "ACTIONS_",
    "GITHUB_",
)
SENSITIVE_NAME_MARKERS = (
    "TOKEN",
    "SECRET",
    "KEY",
    "PASSWORD",
    "CREDENTIAL",
    "AUTH",
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _sign_rs256(pem_path: str, message: bytes) -> str:
    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", pem_path],
            input=message,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("openssl not found; required for JWT signing") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"openssl signing failed: {redact_text(err)}")
    return _b64url(proc.stdout)


def _jwt(app_id: str, pem_path: str) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 30, "exp": now + 9 * 60, "iss": app_id}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig_b64 = _sign_rs256(pem_path, signing_input)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "gh-actions-orchestrator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data_bytes is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"GitHub API error ({exc.code}): {redact_text(body)}") from exc


def _app_access(jwt_token: str) -> None:
    data = _request("GET", "https://api.github.com/app", jwt_token)
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError("GitHub App access check failed")


def _installation_id(jwt_token: str, org: str) -> int:
    data = _request("GET", "https://api.github.com/app/installations", jwt_token)
    if not isinstance(data, list):
        raise RuntimeError("Failed to list GitHub App installations")
    for item in data:
        account = item.get("account") if isinstance(item, dict) else None
        if isinstance(account, dict) and account.get("login") == org and item.get("id"):
            return int(item["id"])
    raise RuntimeError("Failed to resolve GitHub App installation id")



def _access_token(jwt_token: str, installation_id: int, repo: str | None) -> str:
    payload: dict | None = None
    if repo:
        payload = {"repositories": [repo]}
    data = _request(
        "POST",
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        jwt_token,
        payload=payload,
    )
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError("Missing installation access token in response")
    return token


def _is_allowed(
    name: str,
    allowed: set[str],
    allowed_suffixes: tuple[str, ...],
    allowed_prefixes: tuple[str, ...],
) -> bool:
    if name in allowed:
        return True
    if any(name.endswith(suffix) for suffix in allowed_suffixes):
        return True
    return any(name.startswith(prefix) for prefix in allowed_prefixes)


def _assert_allowed_env(
    allowed: set[str],
    allowed_suffixes: tuple[str, ...],
    allowed_prefixes: tuple[str, ...],
) -> None:
    denylist = set()
    for key, value in os.environ.items():
        if not value:
            continue
        if _is_allowed(key, allowed, allowed_suffixes, allowed_prefixes):
            continue
        upper = key.upper()
        if any(marker in upper for marker in SENSITIVE_NAME_MARKERS):
            denylist.add(key)
    if denylist:
        names = ", ".join(sorted(denylist))
        raise RuntimeError(f"Unexpected env vars present: {names}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a GitHub App installation token.")
    parser.add_argument("--app-id-file", required=True)
    parser.add_argument("--pem-file", required=True)
    parser.add_argument("--org", required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--policy-allowed-env", default="")
    args = parser.parse_args()

    if args.policy_allowed_env:
        allowed = {name.strip() for name in args.policy_allowed_env.split(",") if name.strip()}
        _assert_allowed_env(allowed, DEFAULT_ALLOWED_SUFFIXES, DEFAULT_ALLOWED_PREFIXES)
    else:
        _assert_allowed_env(DEFAULT_ALLOWED_ENV, DEFAULT_ALLOWED_SUFFIXES, DEFAULT_ALLOWED_PREFIXES)

    if not os.path.exists(args.app_id_file):
        raise SystemExit(f"App ID file not found: {args.app_id_file}")
    if os.path.getsize(args.app_id_file) > MAX_SECRET_BYTES:
        raise SystemExit("App ID file too large")
    with open(args.app_id_file, "r", encoding="utf-8") as handle:
        app_id = handle.read().strip()
    pem_path = args.pem_file
    if not os.path.exists(pem_path):
        raise SystemExit(f"PEM file not found: {pem_path}")
    jwt_token = _jwt(app_id, pem_path)
    _app_access(jwt_token)
    installation_id = _installation_id(jwt_token, args.org)
    token = _access_token(jwt_token, installation_id, args.repo.strip() or None)

    os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as handle:
        handle.write(token)
    os.chmod(args.output_file, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
