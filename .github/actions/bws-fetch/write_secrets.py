import os
import re
from pathlib import Path

NAME_RE = re.compile(r"^[A-Z0-9_]+$")


def main() -> int:
    secrets_raw = os.environ.get("SECRETS", "")
    output_dir = Path(os.environ.get("OUTPUT_DIR", "bws"))
    output_dir.mkdir(parents=True, exist_ok=True)
    secrets = [item.strip() for item in secrets_raw.split(",") if item.strip()]
    if not secrets:
        raise SystemExit("No secrets specified")

    env_file = os.environ.get("GITHUB_ENV")
    if not env_file:
        raise SystemExit("GITHUB_ENV not set")

    env_lines = []
    output_dir_resolved = output_dir.resolve()
    for name in secrets:
        if not NAME_RE.match(name):
            raise SystemExit(f"Invalid secret name: {name}")
        value = os.environ.get(name, "")
        if not value:
            raise SystemExit(f"Missing secret: {name}")
        path = output_dir / name
        path_resolved = path.resolve()
        if output_dir_resolved not in path_resolved.parents and path_resolved != output_dir_resolved:
            raise SystemExit("Secret path escapes output directory")
        path.write_text(value, encoding="utf-8")
        os.chmod(path, 0o600)
        env_lines.append(f"{name}_FILE={path}")

    with open(env_file, "a", encoding="utf-8") as handle:
        handle.write("\n".join(env_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
