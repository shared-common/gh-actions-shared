from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("Missing GITHUB_EVENT_PATH")
    data = json.loads(Path(event_path).read_text(encoding="utf-8"))
    payload = data.get("client_payload") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        payload = {}
    if "job_type" not in payload:
        payload["job_type"] = os.environ.get("JOB_TYPE", "create")
    output = Path(os.environ.get("OUTPUT_PATH", "normalized.json"))
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
