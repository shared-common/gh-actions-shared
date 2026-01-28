import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

from log_sanitize import sanitize  # noqa: E402


def main() -> int:
    token = os.environ.get("TOKEN")
    owner = os.environ.get("OWNER")
    repo = os.environ.get("REPO")
    workflow = os.environ.get("WORKFLOW")
    ref = os.environ.get("REF")
    payload_path = os.environ.get("INPUTS_PATH")
    payload_inline = os.environ.get("INPUTS")
    if not token or not owner or not repo or not workflow or not ref:
        raise SystemExit("Missing required inputs")
    payload = {}
    if payload_path:
        try:
            with open(payload_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError as exc:
            raise SystemExit(f"Payload file not found: {payload_path}") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Payload file contains invalid JSON: {exc.msg}") from exc
    elif payload_inline:
        try:
            payload = json.loads(payload_inline)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Payload inline JSON invalid: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Inputs payload must be a JSON object")
    inputs = {str(key): str(value) for key, value in payload.items() if value is not None}
    body = json.dumps({"ref": ref, "inputs": inputs}).encode("utf-8")
    req = urllib.request.Request(
        url=f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "gh-actions-shared",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 204):
                raise SystemExit(f"Dispatch failed: {resp.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        body = sanitize(body)
        raise SystemExit(f"Dispatch failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Dispatch failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
