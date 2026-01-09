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

for file in "$out_dir"/*; do
  if [ -f "$file" ]; then
    max_bytes="${MAX_SECRET_BYTES:-65536}"
    file_bytes="$(wc -c < "$file" | tr -d '[:space:]')"
    if [ -z "$file_bytes" ] || [ "$file_bytes" -gt "$max_bytes" ]; then
      printf '%s\n' "Secret file too large: $file" >&2
      exit 1
    fi
  fi
done
