#!/bin/sh
set -eu

if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo "GITHUB_OUTPUT is not set" >&2
  exit 1
fi

for key in "$@"; do
  value="$(printenv "$key" || true)"
  if [ -z "$value" ]; then
    echo "Missing secret: $key" >&2
    exit 1
  fi
  printf '%s\n' "$value" | while IFS= read -r line; do
    if [ -n "$line" ]; then
      printf '::add-mask::%s\n' "$line"
    fi
  done
  printf "%s<<EOF\n%s\nEOF\n" "$key" "$value" >> "$GITHUB_OUTPUT"
done
