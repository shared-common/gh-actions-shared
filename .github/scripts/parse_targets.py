from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List


def main() -> int:
    input_path = os.environ.get("INPUT_PATH")
    if not input_path:
        raise SystemExit("Missing INPUT_PATH")
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    targets: List[dict] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                targets.append({"repo_full_name": item})
            elif isinstance(item, dict) and "repo_full_name" in item:
                targets.append(item)
    output = Path(os.environ.get("OUTPUT_PATH", "targets.json"))
    output.write_text(json.dumps(targets, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
