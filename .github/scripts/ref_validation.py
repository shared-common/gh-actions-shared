from __future__ import annotations

from typing import Iterable


_DISALLOWED_CHARS = {"~", "^", ":", "?", "*", "[", "\\"}


def _has_control_or_space(value: str) -> bool:
    for ch in value:
        if ch <= " " or ch == "\x7f":
            return True
    return False


def _component_invalid(component: str) -> bool:
    return (
        not component
        or component.startswith(".")
        or component.endswith(".")
        or component.endswith(".lock")
    )


def validate_ref_name(name: str, *, label: str = "ref") -> None:
    if not name or name.strip() != name:
        raise ValueError(f"{label} name is empty or has leading/trailing whitespace")
    if name == "@":
        raise ValueError(f"{label} name cannot be '@'")
    if name.startswith("/") or name.endswith("/"):
        raise ValueError(f"{label} name has leading/trailing slash: {name}")
    if "//" in name:
        raise ValueError(f"{label} name contains '//': {name}")
    if ".." in name:
        raise ValueError(f"{label} name contains '..': {name}")
    if "@{" in name:
        raise ValueError(f"{label} name contains '@{{': {name}")
    if name.endswith(".lock"):
        raise ValueError(f"{label} name ends with '.lock': {name}")
    if _has_control_or_space(name):
        raise ValueError(f"{label} name contains whitespace/control chars: {name}")
    if any(ch in _DISALLOWED_CHARS for ch in name):
        raise ValueError(f"{label} name contains invalid characters: {name}")
    components = name.split("/")
    if any(_component_invalid(component) for component in components):
        raise ValueError(f"{label} name has invalid path component: {name}")


def validate_ref_names(names: Iterable[str], *, label: str = "ref") -> None:
    for name in names:
        validate_ref_name(name, label=label)
