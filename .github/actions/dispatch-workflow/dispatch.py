from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    token = os.environ.get("TOKEN")
    owner = os.environ.get("OWNER")
    repo = os.environ.get("REPO")
    event_type = os.environ.get("EVENT_TYPE")
    payload_path = os.environ.get("PAYLOAD_PATH")
    payload_inline = os.environ.get("PAYLOAD")
    if not token or not owner or not repo or not event_type:
        raise SystemExit("Missing required inputs")
    payload = {}
    if payload_path:
        with open(payload_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    elif payload_inline:
        payload = json.loads(payload_inline)
    body = json.dumps({"event_type": event_type, "client_payload": payload}).encode("utf-8")
    req = urllib.request.Request(
        url=f"https://api.github.com/repos/{owner}/{repo}/dispatches",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "gh-actions-shared",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 204):
            raise SystemExit(f"Dispatch failed: {resp.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
