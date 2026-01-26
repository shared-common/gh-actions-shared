import re
from typing import Iterable, List

from _common import load_json


def apply_filters(repos: Iterable[dict], config_path: str) -> List[dict]:
    config = load_json(config_path)
    exclude_prefixes = config.get("exclude_prefixes", []) if isinstance(config, dict) else []
    exclude_exact = config.get("exclude_exact", []) if isinstance(config, dict) else []
    exclude_regex = config.get("exclude_regex", []) if isinstance(config, dict) else []
    regexes = []
    for pattern in exclude_regex:
        if not isinstance(pattern, str):
            continue
        try:
            regexes.append(re.compile(pattern))
        except re.error as exc:
            raise SystemExit(f"Invalid exclude_regex pattern: {pattern}") from exc

    filtered: List[dict] = []
    for repo in repos:
        name = str(repo.get("name", ""))
        if name in exclude_exact:
            continue
        if any(name.startswith(prefix) for prefix in exclude_prefixes):
            continue
        if any(r.search(name) for r in regexes):
            continue
        filtered.append(repo)
    return filtered
