import json
import os
from pathlib import Path

from _common import get_installation_token_for_org, require_env, require_secret, validate_repo_full_name


def load_input() -> dict:
    path = os.environ.get("INPUT_PATH")
    if not path:
        raise SystemExit("Missing INPUT_PATH")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing INPUT_PATH file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INPUT_PATH contains invalid JSON: {exc.msg}") from exc


def main() -> int:
    payload = load_input()
    repo_full_name = payload.get("repo_full_name")
    org, _repo = validate_repo_full_name(repo_full_name)
    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = require_env("GH_ORG_SHARED_APP_PEM_FILE")
    install_json = require_secret("GH_INSTALL_JSON")
    token = get_installation_token_for_org(app_id, pem_path, install_json, org)
    output_path = os.environ.get("OUTPUT_PATH")
    if output_path:
        Path(output_path).write_text(token, encoding="utf-8")
    else:
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
