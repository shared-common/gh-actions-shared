#!/bin/sh
set -eu

if [ -z "${GITHUB_ENV:-}" ]; then
  echo "GITHUB_ENV is not set" >&2
  exit 1
fi

for key in "$@"; do
  value="$(printenv "$key" || true)"
  if [ -z "$value" ]; then
    echo "Missing secret: $key" >&2
    exit 1
  fi
  printf "%s<<EOF\n%s\nEOF\n" "$key" "$value" >> "$GITHUB_ENV"
done
