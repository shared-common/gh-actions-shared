#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  printf '%s\n' "Usage: $0 <ENV_KEY> <OUTPUT_PATH>" >&2
  exit 1
fi

key="$1"
out_path="$2"
value="$(printenv "$key" || true)"
if [ -z "$value" ]; then
  printf '%s\n' "Missing secret: $key" >&2
  exit 1
fi

mkdir -p "$(dirname "$out_path")"
printf '%s' "$value" > "$out_path"
chmod 600 "$out_path"

no_mask_keys="${BWS_NO_MASK_KEYS:-}"
if [ -n "$no_mask_keys" ]; then
  case ",${no_mask_keys}," in
    *,"${key}",*) exit 0 ;;
  esac
fi

printf '%s\n' "$value" | while IFS= read -r line; do
  if [ -n "$line" ]; then
    printf '::add-mask::%s\n' "$line"
  fi
done
