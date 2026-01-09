#!/bin/sh
set -eu

if [ -z "${GITHUB_ENV:-}" ]; then
  printf '%s\n' "GITHUB_ENV is not set" >&2
  exit 1
fi

for key in "$@"; do
  value="$(printenv "$key" || true)"
  if [ -z "$value" ]; then
    printf '%s\n' "Missing secret: $key" >&2
    exit 1
  fi
  printf "%s=%s\n" "$key" "$value" >> "$GITHUB_ENV"
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    printf '%s\n' "::add-mask::$value"
  fi
done
