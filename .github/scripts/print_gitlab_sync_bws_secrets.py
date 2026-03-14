import argparse

from gitlab_sync_profile import format_required_bws_secrets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    print(format_required_bws_secrets(args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
