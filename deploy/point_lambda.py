"""Point the Lambda function voltrix-support-bot at an image tag, and set
IMAGE_TAG to it (spec 08 sections 5, 7 and 9). Also the rollback: run it
with the previous tag.

    .venv/bin/python deploy/point_lambda.py <tag>            # read-only checks and the plan
    .venv/bin/python deploy/point_lambda.py <tag> --confirm  # update the function

Without --confirm it only reads (as the IAM user voltrix-deploy): the
function must match spec 08 section 7 (image package, x86_64, 2048 MB, 60 s,
the bot's execution role, no VPC) and section 5 (VOLTRIX_SECRETS_SOURCE,
HANDOFF_DIR, no other variables than those two, IMAGE_TAG and
AWS_LWA_ASYNC_INIT, so never a secret); the tag must be in ECR.

With --confirm: two updates, each waited for (Round 2 Q9): the image, then
IMAGE_TAG (the other variables are kept unchanged). Requests already
running finish on the old version. Afterwards the function must run
exactly the ECR digest of the tag.

Exit 0 done (or nothing to do), 1 refused or failed, 5 plan only.
"""

import argparse
import sys

from stage_b import (EXIT_DRY_RUN, EXIT_FAILED, EXIT_OK, FUNCTION, REPOSITORY, Aws, DeployError,
                     check_release_tag, concurrency_note, environment_of, lambda_problems, run_process)


def plan(tag: str, aws: Aws) -> dict:
    aws.identity()
    function = aws.function()
    configuration, code = function["Configuration"], function.get("Code") or {}
    problems = lambda_problems(configuration)
    if problems:
        raise DeployError("the function does not match spec 08: " + "; ".join(problems))
    image = aws.ecr_image(tag)
    if image is None:
        raise DeployError(f"{REPOSITORY}:{tag} is not in ECR; push it first (deploy/push_image.py)")
    env = environment_of(configuration)
    return {
        "tag": tag,
        "digest": image["imageDigest"],
        "env": env,
        "previous_tag": env.get("IMAGE_TAG", ""),
        "previous_image": code.get("ResolvedImageUri") or code.get("ImageUri", ""),
        "concurrency": aws.reserved_concurrency(),
        "already": code.get("ResolvedImageUri") == aws.digest_uri(image["imageDigest"]) and env.get("IMAGE_TAG") == tag,
    }


def deploy(p: dict, aws: Aws) -> dict:
    aws.wait_updated()  # no other update may be in progress
    aws.update_code(aws.image_uri(p["tag"]))
    aws.wait_updated()
    aws.update_environment({**p["env"], "IMAGE_TAG": p["tag"]})
    aws.wait_updated()

    function = aws.function()
    configuration, code = function["Configuration"], function.get("Code") or {}
    wrong = []
    if code.get("ResolvedImageUri") != aws.digest_uri(p["digest"]):
        wrong.append(f"the function runs {code.get('ResolvedImageUri')!r}, not the digest of {p['tag']}")
    if environment_of(configuration).get("IMAGE_TAG") != p["tag"]:
        wrong.append("IMAGE_TAG was not set")
    if configuration.get("LastUpdateStatus") != "Successful" or configuration.get("State") != "Active":
        wrong.append(f"state {configuration.get('State')}, last update {configuration.get('LastUpdateStatus')}")
    if wrong:
        raise DeployError("; ".join(wrong))
    return function


def main(argv: list[str] | None = None, runner=run_process) -> int:
    parser = argparse.ArgumentParser(prog="deploy/point_lambda.py", description="Point Lambda at an image tag.")
    parser.add_argument("tag", help="the tag to deploy, or the previous tag to roll back")
    parser.add_argument("--confirm", action="store_true", help="really update the function")
    args = parser.parse_args(argv)
    aws = Aws(runner)
    try:
        check_release_tag(args.tag)
        p = plan(args.tag, aws)
        print(f"Function {FUNCTION} matches spec 08 sections 5 and 7.")
        print(f"Now:  IMAGE_TAG={p['previous_tag'] or '(not set)'}, image {p['previous_image']}")
        print(f"Next: IMAGE_TAG={p['tag']}, image {aws.digest_uri(p['digest'])}")
        note, expected = concurrency_note(p["concurrency"])
        print(f"Concurrency: {note}" + ("" if expected else "  <- check in the Lambda console"))
        if p["already"]:
            print("The function already runs this tag. Nothing to do.")
            return EXIT_OK
        if p["previous_tag"]:
            print(f"Rollback afterwards: .venv/bin/python deploy/point_lambda.py {p['previous_tag']} --confirm")
        if not args.confirm:
            print("Plan only: nothing changed. Add --confirm to update the function.")
            return EXIT_DRY_RUN
        deploy(p, aws)
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED
    print(f"Done: {FUNCTION} runs {REPOSITORY}:{args.tag} ({p['digest']}).")
    print("Next: .venv/bin/python deploy/check_stage_b.py")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
