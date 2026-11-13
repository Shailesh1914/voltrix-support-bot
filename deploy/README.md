Container and deployment (spec 08 sections 5, 6 and 10; Session D).

Stage A: the laptop container. No AWS. Stage B (Lambda) is not built yet.

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
(answer) and T-043 (escalate) on both sides and compares the status and
the set of cited `article_id`s. Without `--confirm` it makes no call.
Exit 0 = AC-D4 passed, 1 = mismatch or error, 4 = a service_error
(re-run), 5 = dry run.

## Files

- `../Dockerfile`, `../.dockerignore`: the image. `.dockerignore` lets in
  only what the build copies.
- `build_image.sh`, `run_local.sh`: build and run.
- `check_pins.py`, `check_manifest.py`: run inside the build.
- `check_stage_a.py`, `compare_tickets.py`: Stage A acceptance checks.
- `tests/`: pytest tests of the above (fakes only, no image needed).
