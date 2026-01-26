import json
from pathlib import Path

from branch_policy import load_branch_policy


def main() -> int:
    policy = load_branch_policy()
    plan = {
        "prefix": policy.prefix,
        "order": [spec.name for spec in policy.order],
        "branches": {spec.name_env: spec.full_name for spec in policy.order},
    }

    output = Path("branch-plan.json")
    output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
