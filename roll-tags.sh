#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./roll-tags.sh --<tag>

Example:
  ./roll-tags.sh --v0.0.1

Behavior:
  - Updates shared workflow allowlists to the provided tag.
  - Commits the workflow changes.
  - Creates an annotated tag and pushes both commit and tag.
EOF
}

log() {
  printf '%s\n' "$*"
}

run() {
  log "+ $*"
  "$@"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 || "${1:0:2}" != "--" ]]; then
  usage >&2
  exit 2
fi

TAG="${1#--}"
if [[ -z "$TAG" ]]; then
  echo "Error: tag is required." >&2
  exit 2
fi

if [[ ! "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Error: invalid tag '${TAG}'." >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
if [[ "$(basename "$ROOT")" != "gh-actions-shared" ]]; then
  echo "Error: must run from gh-actions-shared repo." >&2
  exit 1
fi

if [[ -n "$(git -C "$ROOT" status --porcelain)" ]]; then
  echo "Error: working tree is not clean. Commit or stash first." >&2
  exit 1
fi

BRANCH="$(git -C "$ROOT" branch --show-current)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Error: current branch is '${BRANCH}', expected 'main'." >&2
  exit 1
fi

run git -C "$ROOT" fetch --tags origin
if git -C "$ROOT" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  echo "Error: tag '${TAG}' already exists. Refusing to move tags." >&2
  exit 1
fi

WORKFLOWS_DIR="${ROOT}/.github/workflows"
if [[ ! -d "$WORKFLOWS_DIR" ]]; then
  echo "Error: workflows directory not found." >&2
  exit 1
fi

mapfile -d '' FILES < <(find "$WORKFLOWS_DIR" -maxdepth 1 -type f -name '*.yml' -print0)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "Error: no workflow files found." >&2
  exit 1
fi

log "Updating allowlisted tag in shared workflows to '${TAG}'"
for file in "${FILES[@]}"; do
  run sed -i -E \
    "s|(allowed_refs=\")v[^\"]+(\")|\\1${TAG}\\2|g" \
    "$file"
done

if git -C "$ROOT" diff --quiet -- "$WORKFLOWS_DIR"; then
  echo "Error: no workflow changes detected; nothing to commit." >&2
  exit 1
fi

log "Workflow changes:"
run git -C "$ROOT" diff --stat -- "$WORKFLOWS_DIR"
run git -C "$ROOT" add "$WORKFLOWS_DIR"
run git -C "$ROOT" commit -m "chore: roll shared tag to ${TAG}"
run git -C "$ROOT" tag -a "$TAG" -m "gh-actions-shared ${TAG}"
run git -C "$ROOT" push origin main
run git -C "$ROOT" push origin "$TAG"
