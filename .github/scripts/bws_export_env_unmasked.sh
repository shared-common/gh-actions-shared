#!/bin/sh
set -eu

for key in "$@"; do
  value="$(printenv "$key" || true)"
  if [ -z "$value" ]; then
    echo "Missing secret: $key" >&2
    exit 1
  fi
  export "$key=$value"
done
