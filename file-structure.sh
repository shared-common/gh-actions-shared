#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./file-structure.sh [--path /path/to/dir]
Prints relative file paths from the target directory.
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

EXCLUDE_FILES=(
  .DS_Store Thumbs.db Desktop.ini
  '*.log' '*.tmp' '*.bak' '*.swp' '*.swo'
  '*.pyc' '*.pyo' '*.class'
  '*.o' '*.a' '*.so' '*.dylib' '*.dll' '*.exe' '*.bin' '*.out'
  '*.pid' '*.seed'
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

build_file_filter() {
  local -n out=$1
  out=( -type f )
  for p in "${EXCLUDE_FILES[@]}"; do
    out+=( ! -name "$p" )
  done
}

prune_expr=()
file_filter=()
build_prune prune_expr
build_file_filter file_filter

find "$root" "${prune_expr[@]}" "${file_filter[@]}" -printf '%P\n' | LC_ALL=C sort
