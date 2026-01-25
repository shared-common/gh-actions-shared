from __future__ import annotations

import json
import os
from pathlib import Path


def render_summary(data: object) -> str:
    lines = ["# Orchestrator Summary", ""]
    if isinstance(data, dict):
        results = data.get("results") if isinstance(data, dict) else None
        repo = data.get("repo")
        job = data.get("job_type")
        if repo:
            lines.append(f"- Repo: `{repo}`")
        if job:
            lines.append(f"- Job type: `{job}`")
        if isinstance(results, dict):
            for key in ("created", "updated", "skipped"):
                items = results.get(key, [])
                if isinstance(items, list):
                    lines.append(f"- {key.title()}: {len(items)}")
    elif isinstance(data, list):
        lines.append(f"- Items: {len(data)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    input_path = os.environ.get("INPUT_PATH")
    if not input_path:
        raise SystemExit("Missing INPUT_PATH")
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    summary = render_summary(data)
    output = Path(os.environ.get("OUTPUT_PATH", "summary.md"))
    output.write_text(summary, encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
