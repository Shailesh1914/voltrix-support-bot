#!/usr/bin/env bash
# Build the Stage A (laptop) image: the one documented command (AC-D1).
#
#   deploy/build_image.sh              build voltrix-support-bot:<tag>
#   deploy/build_image.sh --print-tag  print the tag only, build nothing
#
# Tag: <kb-version>-<yyyymmdd>-<git-short-sha>-local (spec 08 D8 format,
# plus -local: a Stage A image is for the laptop only, Round 2 Q9). The
# date is UTC. Needs Docker and git; no Python, no .venv, no AWS.
set -euo pipefail

cd "$(dirname "$0")/.."

REPOSITORY="voltrix-support-bot"

kb_version="$(tr -d '[:space:]' < data/ACTIVE_KB_VERSION)"
if ! [[ "$kb_version" =~ ^v[0-9]+$ ]]; then
  echo "error: data/ACTIVE_KB_VERSION must contain one version such as v2" >&2
  exit 1
fi
commit="$(git rev-parse HEAD)"
short_sha="$(git rev-parse --short=7 HEAD)"
tag="${kb_version}-$(date -u +%Y%m%d)-${short_sha}-local"

if [[ "${1:-}" == "--print-tag" ]]; then
  echo "$tag"
  exit 0
elif [[ $# -gt 0 ]]; then
  echo "usage: deploy/build_image.sh [--print-tag]" >&2
  exit 2
fi

# "modified" when the working tree differs from the commit, so BUILD_INFO.txt
# never claims an image is exactly a commit when it is not.
if [[ -n "$(git status --porcelain)" ]]; then
  tree="modified"
else
  tree="clean"
fi

docker build \
  --platform linux/amd64 \
  --build-arg GIT_COMMIT="$commit" \
  --build-arg GIT_TREE="$tree" \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --tag "${REPOSITORY}:${tag}" \
  .

echo "Built ${REPOSITORY}:${tag} (git tree: ${tree})"
