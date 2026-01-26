from dataclasses import dataclass
from typing import Dict, List, Optional

from _common import config_path, load_json, require_secret, validate_ref_name


@dataclass(frozen=True)
class BranchSpec:
    name_env: str
    name: str
    full_name: str
    track: str
    update: bool


@dataclass(frozen=True)
class BranchPolicy:
    prefix: str
    order: List[BranchSpec]
    by_env: Dict[str, BranchSpec]


def _require_list(value, label: str) -> list:
    if not isinstance(value, list):
        raise SystemExit(f"{label} must be a list")
    return value


def _require_str(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be a non-empty string")
    return value


def load_branch_policy(path: Optional[str] = None) -> BranchPolicy:
    policy_path = path or config_path("branch-policy.json")
    policy = load_json(policy_path, "branch policy")
    if not isinstance(policy, dict):
        raise SystemExit("Branch policy must be a JSON object")

    prefix_env = _require_str(policy.get("prefixEnv"), "prefixEnv")
    prefix = require_secret(prefix_env)
    validate_ref_name(prefix, "branch prefix")

    create_order_raw = _require_list(policy.get("createOrder"), "createOrder")
    branches_raw = _require_list(policy.get("branches"), "branches")

    by_env: Dict[str, BranchSpec] = {}
    for item in branches_raw:
        if not isinstance(item, dict):
            raise SystemExit("Branch policy entry must be an object")
        name_env = _require_str(item.get("nameEnv"), "branch nameEnv")
        name = require_secret(name_env)
        validate_ref_name(name, name_env)
        track = _require_str(item.get("track"), f"{name_env}.track")
        if track not in {"upstream", "main"}:
            raise SystemExit(f"{name_env}.track must be 'upstream' or 'main'")
        update = bool(item.get("update", False))
        full = f"{prefix}/{name}"
        validate_ref_name(full, f"{name_env} full ref")
        if name_env in by_env:
            raise SystemExit(f"Duplicate branch nameEnv: {name_env}")
        by_env[name_env] = BranchSpec(
            name_env=name_env,
            name=name,
            full_name=full,
            track=track,
            update=update,
        )

    order: List[BranchSpec] = []
    for env_name in create_order_raw:
        if not isinstance(env_name, str):
            raise SystemExit("createOrder entries must be strings")
        spec = by_env.get(env_name)
        if not spec:
            raise SystemExit(f"createOrder references unknown env: {env_name}")
        order.append(spec)

    if len({spec.full_name for spec in order}) != len(order):
        raise SystemExit("Branch policy createOrder contains duplicates")

    return BranchPolicy(prefix=prefix, order=order, by_env=by_env)
