#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  printf '%s\n' "Usage: $0 <OUTPUT_DIR> <ENV_KEY> [ENV_KEY...]" >&2
  exit 1
fi

out_dir="$1"
shift

mkdir -p "$out_dir"

for key in "$@"; do
  /bin/sh .github/scripts/bws_export_secret_file.sh "$key" "${out_dir}/${key}"
done
