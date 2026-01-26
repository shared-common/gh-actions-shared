import json
import re
from pathlib import Path
from typing import Any, Mapping


def load_json(path: str, label: str = "JSON") -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} file not found: {path}") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read {label} file: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{label} file is not valid JSON ({exc.msg}) at line {exc.lineno} column {exc.colno}"
        ) from exc


def _schema_type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    return True


def validate(instance: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(_schema_type_matches(instance, t) for t in expected_type):
            raise ValueError(f"{path} expected type {expected_type}")
    elif isinstance(expected_type, str):
        if not _schema_type_matches(instance, expected_type):
            raise ValueError(f"{path} expected type {expected_type}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValueError(f"{path} not in enum")

    if isinstance(instance, str):
        min_len = schema.get("minLength")
        max_len = schema.get("maxLength")
        pattern = schema.get("pattern")
        if isinstance(min_len, int) and len(instance) < min_len:
            raise ValueError(f"{path} shorter than minLength")
        if isinstance(max_len, int) and len(instance) > max_len:
            raise ValueError(f"{path} longer than maxLength")
        if isinstance(pattern, str) and not re.match(pattern, instance):
            raise ValueError(f"{path} does not match pattern")

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            raise ValueError(f"{path} has fewer than minItems")
        if isinstance(max_items, int) and len(instance) > max_items:
            raise ValueError(f"{path} has more than maxItems")
        items = schema.get("items")
        if isinstance(items, dict):
            for idx, item in enumerate(instance):
                validate(item, items, f"{path}[{idx}]")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in instance:
                    raise ValueError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if isinstance(properties, dict):
            for key, sub_schema in properties.items():
                if key in instance:
                    if isinstance(sub_schema, dict):
                        validate(instance[key], sub_schema, f"{path}.{key}")
        for key, value in instance.items():
            if isinstance(properties, dict) and key in properties:
                continue
            if additional is False:
                raise ValueError(f"{path}.{key} is not allowed")
            if isinstance(additional, dict):
                validate(value, additional, f"{path}.{key}")
