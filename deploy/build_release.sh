#!/usr/bin/env bash
# Build the Stage B release image from a clean checkout of main
# (spec 08 D8 and section 9).
#
#   deploy/build_release.sh
#
# 1. Clones main from this checkout's GitHub remote (origin) into a new
#    temporary folder, so local changes and other branches never get in.
# 2. Checks with `gh run list` (read-only) that CI passed for that commit
#    on main (deploy/ci_passed.py).
# 3. Builds voltrix-support-bot:<kb-version>-<yyyymmdd>-<git-short-sha>,
#    the D8 tag WITHOUT -local, for x86_64, with --provenance=false and
#    --sbom=false: Lambda needs a single image manifest, not an index with
#    build attestations.
# 4. Runs that checkout's own deploy/check_stage_a.py on the image (free, no
#    AWS): AC-D2, AC-D3, AC-D5, non-root user, image contents, secret scan.
#
# No AWS call and no push here; deploy/push_image.py pushes. Needs git,
# Docker, gh (logged in) and the project .venv.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PYTHON="${PYTHON:-${ROOT}/.venv/bin/python}"
REPOSITORY="voltrix-support-bot"

if [[ $# -gt 0 ]]; then
  echo "usage: deploy/build_release.sh" >&2
  exit 2
fi

origin_url="$(git remote get-url origin)"
workdir="$(mktemp -d "${TMPDIR:-/tmp}/voltrix-release-XXXXXX")"
trap 'rm -rf "$workdir"' EXIT
checkout="${workdir}/checkout"

echo "Cloning main from ${origin_url}"
git clone --quiet --branch main --single-branch "$origin_url" "$checkout"
commit="$(git -C "$checkout" rev-parse HEAD)"
short_sha="$(git -C "$checkout" rev-parse --short=7 HEAD)"
if [[ -n "$(git -C "$checkout" status --porcelain)" ]]; then
  echo "error: the fresh checkout of main is not clean" >&2
  exit 1
fi
echo "main is at ${commit}"

"$PYTHON" "${ROOT}/deploy/ci_passed.py" "$commit"

kb_version="$(tr -d '[:space:]' < "${checkout}/data/ACTIVE_KB_VERSION")"
if ! [[ "$kb_version" =~ ^v[0-9]+$ ]]; then
  echo "error: data/ACTIVE_KB_VERSION on main must contain one version such as v2" >&2
  exit 1
fi
tag="${kb_version}-$(date -u +%Y%m%d)-${short_sha}"
image="${REPOSITORY}:${tag}"

# A tag names exactly one image: never rebuild over an existing one.
if docker image inspect "$image" >/dev/null 2>&1; then
  echo "error: ${image} already exists locally; remove it first (docker image rm ${image}) to rebuild" >&2
  exit 1
fi

docker build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --build-arg GIT_COMMIT="$commit" \
  --build-arg GIT_TREE="clean" \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --tag "$image" \
  "$checkout"
echo "Built ${image} from main ${commit} (git tree: clean)"

echo "Stage A checks on the release image (free, no AWS):"
"$PYTHON" "${checkout}/deploy/check_stage_a.py" "$image"

echo "Release image ready: ${image}"
echo "Next: .venv/bin/python deploy/push_image.py ${tag}"
