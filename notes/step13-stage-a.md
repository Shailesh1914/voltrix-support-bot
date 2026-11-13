# Step 13.4 – Container on the laptop (Stage A)

Built by Session D on branch `container-stage-a`, 2026-11-12/13. Spec 08 v1.2.

## Result

| Check | Result | Who |
|---|---|---|
| AC-D1 image builds from a clean checkout, one command | Pass (`deploy/build_image.sh`; 39 articles, 187 chunks, manifest check passed) | Session D |
| AC-D2 `/health` 200, kb_version = v2 | Pass | Session D |
| AC-D3 wrong or missing code gives 401 | Pass | Session D |
| AC-D4 same decision and cited articles as `query/ask.py` | **Pass** (table below) | Shailesh, 2026-11-13 |
| AC-D5 works with `--network none` | Pass (`/health` 200; `/ask` gave a `service_error` escalation, no model hub access) | Session D |
| Non-root user | Pass (uid 1000; only `handoffs/` writable) | Session D |
| Secret scan (docker inspect, history, logs, files) | Nothing found | Session D |
| Lambda adapter on the laptop | In the image, not running | Session D |
| `deploy/tests/` | 76 passed, 0 failed, 0 skipped (not in CI yet) | Session D |

## AC-D4 (6 paid calls)

| Ticket | Label | Laptop (`query/ask.py`) | Container | Result |
|---|---|---|---|---|
| T-001 | answer | answered [KB-001] | answered [KB-001] | match |
| T-002 | answer | answered [KB-002, KB-025] | answered [KB-002, KB-025] | match |
| T-043 | escalate | escalated (insufficient_context) [] | escalated (insufficient_context) [] | match |

Container log: one line per request, no question text. Latency 3.5 s and 2.5 s (answers), 1.2 s (escalation). Image tag `v2-20261112-d98f7e5-local`.

## Numbers

- Start-up until `/health` answers: 12.4 s, 9.6 s, 9.5 s; 12.9 s with `--network none`. Mostly the torch import and model loading. Matters for Lambda's start-up limit (Stage B).
- Image: 2.33 GB uncompressed (amd64). Build: about 6 minutes from scratch, 1–2 minutes when only code changes.
- First build showed 171 minutes; the index step alone takes 16 s, so the laptop most likely slept. Keep the laptop awake during builds.
- The image's index hashes equal the laptop's `indexes/v2`, even with Python 3.14.10 against 3.14.6.
- Build cache: 8.5 GB on the laptop (`docker builder prune` frees it).

## Decisions (now in spec 08 v1.2)

- Install `requirements.txt` exactly as CI; `/app/BUILD_INFO.txt` holds `pip freeze`, commit and date.
- Stage A uses the existing project key; the separate key is for Stage B only.
- Laptop container mounts the project's `handoffs/` folder.
- Stage A images are laptop only, tag suffix `-local`; Stage B rebuilds from `main`.
- AC-D5 means the whole network blocked (`--network none`).

## For Stage B

- Decide the adapter's start-up setting (asynchronous init) after measuring start-up on Lambda.
- Lambda runs the container as its own user, not uid 1000; that is why everything except `handoffs/` is world-readable.

## Next iteration

- 500 log line: add the error class name (needs a spec change and a small Session Q change).
- Add `deploy/tests/` to CI (needs a spec 06 change).
- Lock file for packages that `requirements.txt` does not pin (for CI and the image together).
