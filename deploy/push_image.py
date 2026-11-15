"""Push a release image to the ECR repository voltrix-support-bot
(spec 08 D8, sections 8 and 9).

    .venv/bin/python deploy/push_image.py <tag>            # plan only: no AWS call
    .venv/bin/python deploy/push_image.py <tag> --confirm  # push

The tag is the one deploy/build_release.sh printed (no -local). Before the
push: the local image is linux/amd64 and built from the commit in its tag;
the caller is the IAM user voltrix-deploy; the repository has tag
immutability Immutable; the tag is not in ECR yet. The ECR login token goes
to `docker login --password-stdin` and is never printed or written by this
script; `docker logout` runs afterwards in every case. After the push: the
ECR digest equals the pushed digest, and the manifest is a single image
(what Lambda accepts).

Exit 0 pushed, 1 refused or failed, 5 plan only.
"""

import argparse
import json
import re
import sys

from stage_b import (EXIT_DRY_RUN, EXIT_FAILED, EXIT_OK, REPOSITORY, Aws, DeployError,
                     check_release_tag, last_line, run_process)

PUSHED_DIGEST = re.compile(r"digest: (sha256:[0-9a-f]{64})")
SINGLE_IMAGE_MANIFESTS = {
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
}


def docker(runner, *args: str, input: str | None = None, check: bool = True):
    result = runner(["docker", *args], input=input)
    if check and result.returncode != 0:
        raise DeployError(f"docker {args[0]} failed (exit {result.returncode}): {last_line(result.stderr)}")
    return result


def local_image(tag: str, runner) -> dict:
    result = docker(runner, "image", "inspect", f"{REPOSITORY}:{tag}", check=False)
    if result.returncode != 0:
        raise DeployError(f"no local image {REPOSITORY}:{tag}; build it with deploy/build_release.sh")
    return json.loads(result.stdout)[0]


def local_image_problems(info: dict, tag: str) -> list[str]:
    problems = []
    if info.get("Os") != "linux" or info.get("Architecture") != "amd64":
        problems.append(f"the image is {info.get('Os')}/{info.get('Architecture')}, spec 08 wants linux/amd64 (x86_64)")
    labels = (info.get("Config") or {}).get("Labels") or {}
    revision = labels.get("org.opencontainers.image.revision", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not revision.startswith(tag.rsplit("-", 1)[1]):
        problems.append(f"the image was not built from the commit in its tag (revision label {revision!r})")
    return problems


def push(tag: str, aws: Aws, runner) -> dict:
    aws.identity()
    mutability = aws.repository().get("imageTagMutability")
    if mutability != "IMMUTABLE":
        raise DeployError(f"the ECR repository {REPOSITORY} has tag mutability {mutability!r}; "
                          "spec 08 D8 wants Immutable (set it in the ECR console)")
    if aws.ecr_image(tag) is not None:
        raise DeployError(f"{REPOSITORY}:{tag} is already in ECR; tags are immutable, build a new one")

    registry, remote = aws.registry(), aws.image_uri(tag)
    token = aws.secret_text("ecr", "get-login-password")
    try:
        docker(runner, "login", "--username", "AWS", "--password-stdin", registry, input=token)
    finally:
        del token
    try:
        docker(runner, "tag", f"{REPOSITORY}:{tag}", remote)
        pushed = docker(runner, "push", remote)
    finally:
        docker(runner, "logout", registry, check=False)
        docker(runner, "image", "rm", remote, check=False)  # removes the extra name only

    match = PUSHED_DIGEST.search(pushed.stdout or "")
    detail = aws.ecr_image(tag)
    if detail is None:
        raise DeployError(f"{tag} is not in ECR after the push")
    if not match or detail.get("imageDigest") != match.group(1):
        raise DeployError(f"the ECR digest {detail.get('imageDigest')} differs from the pushed digest "
                          f"{match.group(1) if match else 'unknown'}")
    media_type = detail.get("imageManifestMediaType")
    if media_type not in SINGLE_IMAGE_MANIFESTS:
        raise DeployError(f"the pushed manifest is {media_type!r}, not a single image; Lambda will refuse it "
                          "(build with deploy/build_release.sh, which sets --provenance=false --sbom=false)")
    return detail


def main(argv: list[str] | None = None, runner=run_process) -> int:
    parser = argparse.ArgumentParser(prog="deploy/push_image.py", description="Push a release image to ECR.")
    parser.add_argument("tag", help="e.g. v2-20261113-406e022 (from deploy/build_release.sh)")
    parser.add_argument("--confirm", action="store_true", help="really push (without it: plan only, no AWS call)")
    args = parser.parse_args(argv)
    try:
        check_release_tag(args.tag)
        problems = local_image_problems(local_image(args.tag, runner), args.tag)
        if problems:
            raise DeployError("; ".join(problems))
        print(f"Local image {REPOSITORY}:{args.tag}: linux/amd64, built from the commit in its tag")
        if not args.confirm:
            print(f"Plan: push to <account>.dkr.ecr.ap-south-1.amazonaws.com/{REPOSITORY}:{args.tag} "
                  "as the IAM user voltrix-deploy. No AWS call made. Add --confirm to push.")
            return EXIT_DRY_RUN
        detail = push(args.tag, Aws(runner), runner)
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED
    size_mb = detail.get("imageSizeInBytes", 0) / 1_000_000
    print(f"Pushed {REPOSITORY}:{args.tag}, digest {detail['imageDigest']}, {size_mb:.0f} MB compressed in ECR")
    print(f"Next: .venv/bin/python deploy/point_lambda.py {args.tag}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
