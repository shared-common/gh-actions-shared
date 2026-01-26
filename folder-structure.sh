#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./folder-structure.sh [--path /path/to/dir]
Prints relative folder paths from the target directory.
USAGE
}

root="."
while [ "$#" -gt 0 ]; do
  case "$1" in
    --path)
      root="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '%s\n' "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

test -n "$root" || { printf '%s\n' "--path requires a value" >&2; exit 1; }
if [ ! -d "$root" ]; then
  printf '%s\n' "Path not found: $root" >&2
  exit 1
fi
root="$(cd "$root" && pwd)"

EXCLUDE_DIRS=(
  .git .hg .svn
  .idea .vscode
  node_modules bower_components
  dist build out target bin obj
  .next .nuxt .svelte-kit .vite .parcel-cache .turbo .nx
  .cache .pytest_cache .mypy_cache .ruff_cache .tox
  .venv venv env .direnv
  vendor Pods Carthage DerivedData
  .gradle .terraform .terragrunt-cache .cargo .npm .pnpm-store .yarn .yarn-cache
  __pycache__
)

build_prune() {
  local -n out=$1
  out=( -type d \( )
  for d in "${EXCLUDE_DIRS[@]}"; do
    out+=( -name "$d" -o )
  done
  unset 'out[${#out[@]}-1]'
  out+=( \) -prune -o )
}

prune_expr=()
build_prune prune_expr

find "$root" "${prune_expr[@]}" -type d -mindepth 1 -printf '%P\n' | LC_ALL=C sort
