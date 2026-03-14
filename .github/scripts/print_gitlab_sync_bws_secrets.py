import argparse

from gitlab_sync_profile import format_required_bws_secrets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--include-github-app", action="store_true")
    parser.add_argument("--mode", choices=("create", "sync"), default="create")
    args = parser.parse_args()
    print(format_required_bws_secrets(args.profile, include_github_app=args.include_github_app, mode=args.mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
