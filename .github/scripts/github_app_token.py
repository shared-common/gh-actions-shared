import argparse
from pathlib import Path

from _common import allowed_orgs, get_installation_token_for_org, require_env, require_secret


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    app_id = require_secret("GH_ORG_SHARED_APP_ID")
    pem_path = Path(require_env("GH_ORG_SHARED_APP_PEM_FILE"))
    install_json = require_secret("GH_INSTALL_JSON")

    if args.org not in allowed_orgs(install_json):
        raise SystemExit(f"Org '{args.org}' is not in installation mapping")

    token = get_installation_token_for_org(app_id, str(pem_path), install_json, args.org)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(token, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
