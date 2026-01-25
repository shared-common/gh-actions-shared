from __future__ import annotations

import json
import os
from typing import Any


def load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate(instance: Any, schema: dict, path: str = "$") -> None:
    expected_type = schema.get("type")
    if expected_type:
        if expected_type == "object" and not isinstance(instance, dict):
            raise ValueError(f"{path} expected object")
        if expected_type == "array" and not isinstance(instance, list):
            raise ValueError(f"{path} expected array")
        if expected_type == "string" and not isinstance(instance, str):
            raise ValueError(f"{path} expected string")
        if expected_type == "boolean" and not isinstance(instance, bool):
            raise ValueError(f"{path} expected boolean")
    if "enum" in schema:
        if instance not in schema["enum"]:
            raise ValueError(f"{path} not in enum")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise ValueError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, sub_schema in properties.items():
                if key in instance:
                    validate(instance[key], sub_schema, f"{path}.{key}")
    if isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for idx, item in enumerate(instance):
                validate(item, items, f"{path}[{idx}]")


def main() -> int:
    schema_path = os.environ.get("SCHEMA_PATH")
    json_path = os.environ.get("JSON_PATH")
    if not schema_path or not json_path:
        raise SystemExit("Missing SCHEMA_PATH or JSON_PATH")
    schema = load(schema_path)
    instance = load(json_path)
    validate(instance, schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
