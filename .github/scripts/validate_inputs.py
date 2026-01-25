from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

REQUIRED = ["repo_full_name", "job_type"]


def load_payload() -> Dict[str, Any]:
    input_path = os.environ.get("INPUT_PATH")
    if input_path:
        return json.loads(Path(input_path).read_text(encoding="utf-8"))
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("Missing INPUT_PATH or GITHUB_EVENT_PATH")
    data = json.loads(Path(event_path).read_text(encoding="utf-8"))
    payload = data.get("client_payload") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        raise SystemExit("Missing client_payload")
    return payload


def main() -> int:
    payload = load_payload()
    for key in REQUIRED:
        if key not in payload:
            raise SystemExit(f"Missing required input: {key}")
    if "job_type" not in payload:
        payload["job_type"] = "create"
    output = Path(os.environ.get("OUTPUT_PATH", "validated.json"))
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
