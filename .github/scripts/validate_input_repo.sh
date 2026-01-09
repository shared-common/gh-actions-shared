#!/bin/sh
set -eu

if [ -z "${INPUT_REPO:-}" ]; then
  exit 0
fi

case "$INPUT_REPO" in
  *[!A-Za-z0-9._-]*)
    printf '%s\n' "Invalid repo name: $INPUT_REPO" >&2
    exit 1
    ;;
esac

case "$INPUT_REPO" in
  .*|*/*)
    printf '%s\n' "Invalid repo name: $INPUT_REPO" >&2
    exit 1
    ;;
esac
