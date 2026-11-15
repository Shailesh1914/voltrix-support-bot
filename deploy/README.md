Container and deployment (spec 08 sections 5, 6 and 10; Session D).

Stage A: the laptop container, no AWS (below). Stage B: the same image on
AWS Lambda (section "Stage B" at the end).

## Build (AC-D1)

From a clean checkout, with Docker and git (no Python needed):

    deploy/build_image.sh

This builds `voltrix-support-bot:<kb-version>-<yyyymmdd>-<git-short-sha>-local`
for x86_64. `deploy/build_image.sh --print-tag` prints the tag only. The
first build takes about 10 minutes; later builds that change only code
take about a minute.

What the build does (see the comments in `../Dockerfile`):
- installs `requirements.txt` exactly as CI does (CPU-only torch) and checks
  every pin (`check_pins.py`);
- downloads the pinned embedding model with the project's own loader;
- turns the model hub off, builds the index of the version in
  `data/ACTIVE_KB_VERSION` with CI's command, and checks its manifest
  (`check_manifest.py`);
- writes `/app/BUILD_INFO.txt`: commit, tree state (clean or modified),
  build date, KB version, Python, base image, adapter, `pip freeze`.

Pins: `python:3.14.10-slim-trixie` and AWS Lambda Web Adapter 1.1.0, both
by digest (in the Dockerfile).

## Run on the laptop

    deploy/run_local.sh [IMAGE]

- Opens http://127.0.0.1:8080 (localhost only). Ctrl+C stops it.
- IMAGE defaults to the newest `voltrix-support-bot:*-local` image.
- `~/.config/voltrix/secrets.env` is mounted read-only at
  `/home/app/.config/voltrix/secrets.env` (never `--env-file`). It must hold
  `VOLTRIX_ANTHROPIC_API_KEY` and `VOLTRIX_ACCESS_CODE` (12+ characters).
- The project's `handoffs/` is mounted at `/app/handoffs`; handoff records
  are appended to `handoffs/handoffs.jsonl` as with `python -m query.ask`.
- The container runs as uid 1000. The secrets file and `handoffs/` must be
  readable (and `handoffs/` writable) by uid 1000.
- `--dry-run` prints the docker command without running it.

## Checks

| Check | Command | Paid? |
|---|---|---|
| AC-D1 | `deploy/build_image.sh` from a clean checkout | no |
| AC-D2, AC-D3, AC-D5, start-up time, no secret in image/history/settings | `.venv/bin/python deploy/check_stage_a.py voltrix-support-bot:<tag>` | no |
| AC-D4 | `deploy/run_local.sh` in one terminal, then `.venv/bin/python deploy/compare_tickets.py --confirm` in another | yes, 6 calls |
| Unit tests of these scripts | `.venv/bin/python -m pytest deploy/tests` | no |

`check_stage_a.py` uses a FAKE secrets file it makes itself (random dummy
key and code) and deletes afterwards; it never reads the real one. For
AC-D5 it runs the container with `--network none` and checks from inside:
`/health` must answer, and `/ask` for T-001 must come back as a 200
`service_error` escalation, which means the model and retrieval ran
offline and only the (blocked) Claude call failed.

`compare_tickets.py` asks for the access code with a hidden prompt, first
makes two free checks (same `kb_version`; the code is accepted, using a
blank question that is refused before retrieval), then runs T-001, T-002
(answer) and T-043 (escalate) on both sides. The rule (Stage B Round 4,
for spec 08 v1.3): the decision must be the same on both sides, and each
side must pass the ticket's label by the spec 05 rules (checked with
`evals/eval_scoring.passes`, read only): answered and citing at least one
expected article, or escalated for any reason except `service_error`. The
same citation set is `match`; a different set where both pass is
`differs (both valid)`, also a pass. Without `--confirm` it makes no call.
Exit 0 = AC-D4 passed, 1 = `MISMATCH (decision)`, `INVALID (...)` or an
error, 4 = a service_error (re-run), 5 = dry run.

## Files

- `../Dockerfile`, `../.dockerignore`: the image. `.dockerignore` lets in
  only what the build copies.
- `build_image.sh`, `run_local.sh`: build and run.
- `check_pins.py`, `check_manifest.py`: run inside the build.
- `check_stage_a.py`, `compare_tickets.py`: Stage A acceptance checks.
- `build_release.sh`, `ci_passed.py`, `push_image.py`, `point_lambda.py`:
  Stage B release, push and deploy (and rollback).
- `check_stage_b.py`, `measure_cold_start.py`, `check_secrets_stage_b.py`:
  Stage B checks (AC-D7, start-up measurement, AC-D9).
- `stage_b.py`: shared Stage B code (names, region, the voltrix-deploy guard).
- `tests/`: pytest tests of the above (fakes only: no image, no AWS, no network).

## Stage B: AWS Lambda (spec 08 sections 7 to 11)

Region ap-south-1 (Mumbai). Function and ECR repository `voltrix-support-bot`,
execution role `voltrix-support-bot-lambda`, log group
`/aws/lambda/voltrix-support-bot`. The one-time setup (role, function,
Function URL, concurrency, log group, deployment user) is done by the owner
in the console. Every AWS call in these scripts runs as the IAM user
`voltrix-deploy` (CLI profile `voltrix-deploy`, region given explicitly);
a script stops if the caller is anyone else. Every script that changes
something prints its plan and does nothing without `--confirm`.

| Step | Command | Who | AWS / paid? |
|---|---|---|---|
| Build from a clean checkout of `main`, CI checked, Stage A checks run | `deploy/build_release.sh` | Session D or owner | no AWS (gh read-only) |
| Push to ECR | `.venv/bin/python deploy/push_image.py <tag> --confirm` | owner's go-ahead | AWS |
| Point Lambda at the tag, set `IMAGE_TAG` | `.venv/bin/python deploy/point_lambda.py <tag> --confirm` | owner's go-ahead | AWS |
| Roll back | `.venv/bin/python deploy/point_lambda.py <previous-tag> --confirm` | owner | AWS |
| AC-D7: AC-D2, AC-D3 through the Function URL | `.venv/bin/python deploy/check_stage_b.py` | Session D or owner | free |
| AC-D7: AC-D4 through the Function URL | `.venv/bin/python deploy/compare_tickets.py --url <Function URL> --confirm` | owner | 6 paid calls |
| Start-up measurement (async init off/on) | `.venv/bin/python deploy/measure_cold_start.py --confirm` | owner's go-ahead | free |
| AC-D8: no reserved concurrency (account limit 10 is the cap), Anthropic spend limit | the consoles | owner | - |
| AC-D9: no secret in repo, image, Lambda settings, logs | `.venv/bin/python deploy/check_secrets_stage_b.py --tag <tag>` | owner (hidden prompt) | free |

Notes:
- The release tag is `<kb-version>-<yyyymmdd>-<git-short-sha>` (D8), never
  `-local` or `latest`. The ECR repository must have tag immutability
  Immutable; `push_image.py` checks this and refuses an existing tag.
- `build_release.sh` builds with `--provenance=false --sbom=false`: Lambda
  needs a single image manifest. `push_image.py` checks the pushed manifest.
- The ECR login token goes to `docker login --password-stdin` only, and
  `docker logout` runs after every push.
- `point_lambda.py` makes two updates (image, then `IMAGE_TAG`), waiting for
  each. It refuses a function that differs from spec 08 section 7, or that
  has any environment variable other than `VOLTRIX_SECRETS_SOURCE`,
  `HANDOFF_DIR`, `IMAGE_TAG` and `AWS_LWA_ASYNC_INIT`.
- `check_secrets_stage_b.py` asks for the access code (and optionally the
  key) with hidden prompts and searches on the laptop. The values are never
  printed, put on a command line or sent to AWS.
- Concurrency (Stage B Round 3): no reserved concurrency, because the account
  limit is 10 and Lambda keeps 10 unreserved. The account limit of 10 is the
  cap. Pause = Lambda's Throttle (function concurrency 0). `point_lambda.py`
  shows the setting; `check_stage_b.py` and `measure_cold_start.py` stop if
  the function is throttled.
- `measure_cold_start.py` puts `AWS_LWA_ASYNC_INIT` back to its old value at
  the end. The owner decides the final value (spec 08 section 7).
