import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

from json_schema import load_json, validate  # noqa: E402


def main() -> int:
    schema_path = os.environ.get("SCHEMA_PATH")
    json_path = os.environ.get("JSON_PATH")
    if not schema_path or not json_path:
        raise SystemExit("Missing SCHEMA_PATH or JSON_PATH")
    schema = load_json(schema_path, "schema")
    instance = load_json(json_path, "json")
    validate(instance, schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
