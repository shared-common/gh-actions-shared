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


def _installation_id(jwt_token: str, org: str) -> int:
    data = _request("GET", f"https://api.github.com/orgs/{org}/installation", jwt_token)
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError("Failed to resolve GitHub App installation id")
    return int(data["id"])


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a GitHub App installation token.")
    parser.add_argument("--app-id-file", required=True)
    parser.add_argument("--pem-file", required=True)
    parser.add_argument("--org", required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()

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
    installation_id = _installation_id(jwt_token, args.org)
    token = _access_token(jwt_token, installation_id, args.repo.strip() or None)

    os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as handle:
        handle.write(token)
    os.chmod(args.output_file, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
