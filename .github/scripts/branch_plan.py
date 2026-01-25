from __future__ import annotations

import json
from pathlib import Path

from _common import require_secret


def main() -> int:
    prefix = require_secret("GIT_BRANCH_PREFIX")
    main = require_secret("GIT_BRANCH_MAIN")
    staging = require_secret("GIT_BRANCH_STAGING")
    release = require_secret("GIT_BRANCH_RELEASE")
    snapshot = require_secret("GIT_BRANCH_SNAPSHOT")
    feature = require_secret("GIT_BRANCH_FEATURE")

    plan = {
        "prefix": prefix,
        "order": [main, staging, release, snapshot, feature],
        "branches": {
            "main": f"{prefix}/{main}",
            "staging": f"{prefix}/{staging}",
            "release": f"{prefix}/{release}",
            "snapshot": f"{prefix}/{snapshot}",
            "feature": f"{prefix}/{feature}",
        },
    }

    output = Path("branch-plan.json")
    output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
