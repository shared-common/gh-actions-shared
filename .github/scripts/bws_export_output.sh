#!/bin/sh
set -eu

if [ -z "${GITHUB_OUTPUT:-}" ]; then
  printf '%s\n' "GITHUB_OUTPUT is not set" >&2
  exit 1
fi

for key in "$@"; do
  value="$(printenv "$key" || true)"
  if [ -z "$value" ]; then
    printf '%s\n' "Missing secret: $key" >&2
    exit 1
  fi
  printf "%s<<EOF\n%s\nEOF\n" "$key" "$value" >> "$GITHUB_OUTPUT"
done
