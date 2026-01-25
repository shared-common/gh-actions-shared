from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List

from secret_env import ensure_file_env, read_required_secret_file

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _parse_list(value: str, label: str) -> List[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise SystemExit(f"Missing {label} entries")
    invalid = [item for item in items if not NAME_RE.match(item)]
    if invalid:
        raise SystemExit(f"Invalid {label} values: {', '.join(invalid)}")
    if len(set(items)) != len(items):
        raise SystemExit(f"Duplicate {label} entries")
    return items


def _read_env_list(key: str, label: str) -> List[str]:
    ensure_file_env(key)
    value = read_required_secret_file(key).strip()
    return _parse_list(value, label)


def _read_env_value(key: str, label: str) -> str:
    ensure_file_env(key)
    value = read_required_secret_file(key).strip()
    if not value:
        raise SystemExit(f"Missing {label} value")
    if not NAME_RE.match(value):
        raise SystemExit(f"Invalid {label} value: {value}")
    return value


def build_org_matrix(org_keys: Iterable[str]) -> Dict[str, List[Dict[str, str]]]:
    orgs: List[str] = []
    for key in org_keys:
        orgs.append(_read_env_value(key, f"org ({key})"))
    if len(set(orgs)) != len(orgs):
        raise SystemExit("Duplicate org entries")
    org_filter = os.environ.get("INPUT_ORG")
    if org_filter:
        candidate = org_filter.strip()
        if not NAME_RE.match(candidate):
            raise SystemExit(f"Invalid org filter: {candidate}")
        if candidate not in orgs:
            raise SystemExit(f"Requested org not configured: {candidate}")
        orgs = [candidate]
    return {"include": [{"github_org": org} for org in orgs]}


def build_gitlab_matrix(
    *,
    org_keys: Iterable[str],
    group_key: str,
    subgroup_keys: Iterable[str],
) -> Dict[str, List[Dict[str, str]]]:
    orgs = [_read_env_value(key, f"org ({key})") for key in org_keys]
    if len(set(orgs)) != len(orgs):
        raise SystemExit("Duplicate org entries")
    group = _read_env_value(group_key, f"gitlab group ({group_key})")
    subgroups = [_read_env_value(key, f"gitlab subgroup ({key})") for key in subgroup_keys]
    if len(orgs) != len(subgroups):
        raise SystemExit("Org/subgroup counts must match")
    return {
        "include": [
            {"github_org": org, "gitlab_group": group, "gitlab_subgroup": subgroup}
            for org, subgroup in zip(orgs, subgroups)
        ]
    }
