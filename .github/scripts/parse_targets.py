import json
import os
from pathlib import Path
from typing import List

from _common import validate_repo_full_name


def main() -> int:
    input_path = os.environ.get("INPUT_PATH")
    if not input_path:
        raise SystemExit("Missing INPUT_PATH")
    try:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing INPUT_PATH file: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc
    targets: List[dict] = []
    seen = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                org, repo = validate_repo_full_name(item)
                key = f"{org}/{repo}"
                if key not in seen:
                    targets.append({"repo_full_name": key})
                    seen.add(key)
            elif isinstance(item, dict) and "repo_full_name" in item:
                org, repo = validate_repo_full_name(item["repo_full_name"])
                key = f"{org}/{repo}"
                if key not in seen:
                    targets.append({**item, "repo_full_name": key})
                    seen.add(key)
    output = Path(os.environ.get("OUTPUT_PATH", "targets.json"))
    output.write_text(json.dumps(targets, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
