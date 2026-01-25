from __future__ import annotations

import json
import os
from pathlib import Path

from _common import get_installation_token_for_org, list_org_repos, require_env, require_secret
from repo_filters import apply_filters


def main() -> int:
    org = require_env("TARGET_ORG")
    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")
    filters_path = os.environ.get("REPO_FILTERS_PATH", "configs/repo-filters.json")

    token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    repos = list_org_repos(token, org)
    repos = [repo for repo in repos if not repo.get("archived")]
    repos = apply_filters(repos, filters_path)

    output = Path(os.environ.get("OUTPUT_PATH", "discover.json"))
    output.write_text(json.dumps(repos, indent=2), encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
