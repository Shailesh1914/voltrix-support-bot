#!/usr/bin/env bash
# Run the Stage A image on the laptop (spec 08 section 5).
#
#   deploy/run_local.sh [IMAGE]            run in the foreground (Ctrl+C stops it)
#   deploy/run_local.sh --dry-run [IMAGE]  print the docker command only
#
# IMAGE defaults to the newest voltrix-support-bot:*-local image.
# - The secrets file (~/.config/voltrix/secrets.env) is mounted READ-ONLY.
#   It is never passed with --env-file or -e, so no value is in docker inspect.
#   This script only checks that the file exists; it never reads it.
# - The project's handoffs/ folder is mounted at /app/handoffs (writable by
#   uid 1000, the container user), so handoff records are kept (Round 2 Q5).
# - The port is published on 127.0.0.1 only: http://127.0.0.1:8080
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

SECRETS_FILE="${HOME}/.config/voltrix/secrets.env"
CONTAINER_SECRETS="/home/app/.config/voltrix/secrets.env"
HANDOFFS_DIR="${ROOT}/handoffs"
APP_UID=1000

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi

image="${1:-}"
if [[ -z "$image" ]]; then
  image="$(docker images --filter 'reference=voltrix-support-bot:*-local' \
             --format '{{.CreatedAt}}\t{{.Repository}}:{{.Tag}}' | sort -r | head -n 1 | cut -f 2)"
  if [[ -z "$image" ]]; then
    echo "error: no voltrix-support-bot:*-local image; run deploy/build_image.sh first" >&2
    exit 1
  fi
fi

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "error: the secrets file ${SECRETS_FILE} does not exist" >&2
  exit 1
fi

mkdir -p "$HANDOFFS_DIR"
if [[ "$(stat -c %u "$HANDOFFS_DIR")" != "$APP_UID" ]]; then
  echo "error: ${HANDOFFS_DIR} must be owned by uid ${APP_UID} (the container user)" >&2
  exit 1
fi

cmd=(docker run --rm --name voltrix-local
     --publish 127.0.0.1:8080:8080
     --mount "type=bind,src=${SECRETS_FILE},dst=${CONTAINER_SECRETS},readonly"
     --mount "type=bind,src=${HANDOFFS_DIR},dst=/app/handoffs"
     "$image")

if $dry_run; then
  printf '%q ' "${cmd[@]}"
  echo
  exit 0
fi

echo "Starting ${image} on http://127.0.0.1:8080 (Ctrl+C stops it)" >&2
exec "${cmd[@]}"
