#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <ENV_KEY> <OUTPUT_PATH>" >&2
  exit 1
fi

key="$1"
out_path="$2"
value="$(printenv "$key" || true)"
if [ -z "$value" ]; then
  echo "Missing secret: $key" >&2
  exit 1
fi

mkdir -p "$(dirname "$out_path")"
printf '%s' "$value" > "$out_path"
chmod 600 "$out_path"
