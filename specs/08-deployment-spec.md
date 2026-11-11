# Spec 08: Deployment

Version: 1.0
Status: Draft for review
Owner: Shailesh (only the owner changes this file)
Implemented by: Session Q (web interface), Session D (container, AWS deployment)

## 1. Purpose

Make the Voltrix VX-200 support bot usable from a browser, first in a container on the laptop, then on AWS Lambda. The bot's behaviour must not change: the deployed bot answers and escalates exactly as the tested bot does (specs 02, 03, 05). Deployment only wraps it.

This is a learning project. Cost must stay close to zero, and everything must be easy to switch off.

## 2. Out of scope (this iteration)

- User accounts, logins, chat history.
- Custom domain names, HTTPS certificates of our own, API Gateway.
- Automatic deployment from CI. Deployment is done by hand, following this spec.
- Storing handoff records permanently in AWS.

## 3. Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Web framework | FastAPI, served by uvicorn |
| D2 | Endpoints | `GET /`, `GET /health`, `POST /ask` (section 4) |
| D3 | Access control | Access code in a request header; wrong or missing code is refused before any retrieval or Claude call |
| D4 | Anthropic key | A new key used only by the deployed bot. Laptop: read from the secrets file outside the project. AWS: read from Parameter Store, Standard tier, SecureString |
| D5 | Spending limits | Lambda reserved concurrency 2; monthly spend limit on the new Anthropic key set in the Anthropic console (USD 5); AWS budget USD 5 (email warning only) |
| D6 | AWS credentials | A new IAM user for deployment with only the permissions in section 8. The admin login is not used for deployment |
| D7 | Container | Python 3.14 (same minor version as the project), CPU-only torch, embedding model and active KB index inside the image |
| D8 | Image tags | ECR tag immutability: Immutable. Tag format `<kb-version>-<yyyymmdd>-<git-short-sha>`, for example `v2-20261112-a1b2c3d`. The tag `latest` is not used |
| D9 | Order | Stage A (laptop container) must pass section 10 before Stage B (Lambda) starts |
| D10 | Switching off | Section 11; done after the demo |
| D11 | Lambda adapter | AWS Lambda Web Adapter (awslabs), copied into the image. Exact version pinned by Session D, after checking its current documentation |

## 4. Web interface (Session Q)

### 4.1 `GET /health`

- No access code needed.
- Does not call Claude and does not run retrieval.
- Returns HTTP 200 with JSON: `status` ("ok"), `kb_version` (from `data/ACTIVE_KB_VERSION`), `model_id` (from `query/config.py`), `image_tag` (from the environment variable `IMAGE_TAG`, or "local" if not set).
- Never returns any secret or part of a secret.

### 4.2 `POST /ask`

- Header `X-Access-Code` is required.
- Body JSON: `{"question": "<text>"}`.
- Checks, in this order, before anything else happens:
  1. Access code missing or wrong → HTTP 401, JSON `{"error": "access denied"}`. The comparison uses a constant-time compare.
  2. Body not valid JSON, `question` missing, empty after trimming, or longer than 1000 characters → HTTP 400 with a short `error` message.
- Then the question goes through the existing query flow (`query/flow.py`), unchanged. The web layer adds no new prompt text, no new checks and no changes to the threshold.
- Success → HTTP 200 with the same fields the existing flow returns (decision answer or escalate, answer text, citations, handoff id when escalated). Field names are listed in Session Q's tests and must match the flow's result.
- If the Anthropic call fails after the configured retries → HTTP 503, JSON `{"error": "service temporarily unavailable"}`. No stack trace is returned.

### 4.3 `GET /`

- One simple HTML page: an access code field, a question box, an Ask button, and an area showing the answer, citations or the escalation message.
- Plain HTML, CSS and a little JavaScript inside the page. No external scripts or fonts.
- The page shows a note: "Demo bot for a fictional product (Voltrix VX-200). Synthetic data only."
- The access code typed in the page is kept only in the page's memory, not stored in the browser.

### 4.4 Logging

- One log line per `/ask` request: request id, decision, latency in milliseconds, HTTP status.
- The question text, the answer text, the access code and the Anthropic key are never logged.

### 4.5 Handoff records

- Written to the folder named by the environment variable `HANDOFF_DIR` (laptop default: `handoffs/`, already gitignored).
- On Lambda, `HANDOFF_DIR=/tmp/handoffs`. These files disappear when Lambda recycles the environment. This is accepted for this iteration (section 2).

### 4.6 Tests (Session Q)

- Use a fake Claude client. No paid calls in structural tests.
- Expected values (status codes, limits such as 1000 characters, error messages, field names) are taken from this spec, not from the code.
- Must prove: `/health` works without a code and never calls Claude; a wrong or missing code gives 401 and makes zero Claude calls and zero retrieval calls; the 400 cases; a correct request returns the flow's result unchanged; the 503 case; no secret appears in any response or log line.

## 5. Secrets and settings

| Setting | Laptop (Stage A) | Lambda (Stage B) |
|---|---|---|
| Anthropic key | Secrets file outside the project, passed to the container at run time | Parameter Store SecureString `/voltrix/anthropic-key` |
| Access code | Secrets file outside the project, passed at run time | Parameter Store SecureString `/voltrix/access-code` |
| `IMAGE_TAG` | not set | the image tag |
| `HANDOFF_DIR` | `handoffs/` | `/tmp/handoffs` |

Rules:
- The key variable keeps the name the project already uses (never `ANTHROPIC_API_KEY`).
- No secret is written into the image, the Dockerfile, GitHub, CI settings, notes or screenshots.
- On Lambda, the app reads the two parameters once at start-up (with decryption) and keeps them in memory.
- The access code is at least 12 characters, chosen by the owner, and changed after the demo.

## 6. Container image (Session D)

- Base: an official Python 3.14 slim image, version pinned.
- Installs the project's pinned dependencies, CPU-only torch, FastAPI, uvicorn and boto3 (pinned versions).
- The embedding model (BAAI/bge-small-en-v1.5, the pinned revision from spec 01) is downloaded during the image build. At run time the model is loaded from the image only (`HF_HUB_OFFLINE=1`). No downloads at run time.
- The index for the active KB version is built during the image build with the same command CI uses, and its manifest is checked. Only the active KB version goes into the image.
- Runs as a non-root user. Listens on port 8080.
- Contains the AWS Lambda Web Adapter (D11), with its readiness check pointed at `/health`. On the laptop the adapter does nothing, so the same image runs in both places.
- A `.dockerignore` keeps out `.env`, `.venv/`, `.git/`, `handoffs/`, `evals/` results and `notes/`.
- Architecture: x86_64.

## 7. Lambda settings (Stage B)

| Setting | Value |
|---|---|
| Package type | Container image from ECR repository `voltrix-support-bot` |
| Architecture | x86_64 |
| Memory | 2048 MB |
| Timeout | 60 seconds |
| Reserved concurrency | 2 |
| Function URL | Auth type NONE (protection is the access code) |
| Log retention | CloudWatch log group kept 7 days |
| Region | the region already used for Task 13.1 checks |

A cold start (first request after a quiet period) is allowed to take longer than normal. This is accepted for a demo.

## 8. AWS permissions

Deployment IAM user (new, used only from the laptop):
- push images to the ECR repository `voltrix-support-bot` only;
- create and update the Lambda function for this bot only;
- pass the bot's execution role only.

Lambda execution role:
- read the two parameters `/voltrix/anthropic-key` and `/voltrix/access-code` only (with decryption);
- write its own CloudWatch logs.

Nothing else. Session D lists the exact policy JSON in `deploy/` and the owner reviews it before creating it.

## 9. Updating and rolling back

- A KB promotion (spec 07) or a code change means a new image with a new tag. Lambda is pointed at the new tag. Requests already running finish on the old version.
- Rollback: point Lambda back at the previous tag. Because tags are immutable, the previous tag is exactly the image that was tested.
- Only images built from a commit on `main` that passed CI are deployed.

## 10. Acceptance criteria

Stage A, laptop container:
- AC-D1: The image builds from a clean checkout with one documented command.
- AC-D2: `GET /health` returns 200 with `kb_version` equal to `data/ACTIVE_KB_VERSION`.
- AC-D3: `POST /ask` with a wrong code returns 401.
- AC-D4: For 3 tickets from `evals/support_questions.jsonl` (2 answer, 1 escalate), the container gives the same decision and the same cited articles as `query/ask.py` on the laptop.
- AC-D5: The container works with the network blocked for the model (no model download at run time).
- AC-D6: Session Q's structural tests pass in CI, with no skipped tests.

Stage B, Lambda:
- AC-D7: AC-D2, AC-D3 and AC-D4 pass again through the Function URL.
- AC-D8: Reserved concurrency is 2, and the Anthropic spend limit is set (checked by the owner in the consoles).
- AC-D9: No secret appears in the image, the repository, or the CloudWatch logs (checked by a search).
- AC-D10: The switch-off steps in section 11 were run once after the demo and recorded in `notes/`.

## 11. Switching off

Pause (keeps everything, costs about nothing): set the Lambda reserved concurrency to 0. The Function URL then refuses all requests.

Full removal, in this order:
1. Delete the Function URL and the Lambda function.
2. Delete the images in ECR (and the repository if no longer needed).
3. Delete the two parameters in Parameter Store.
4. Delete the CloudWatch log group.
5. Deactivate and delete the deployment IAM user's access key.
6. Disable the bot's Anthropic key in the Anthropic console.

Expected cost while running: Lambda and Parameter Store Standard stay within free limits for demo use. ECR storage for a ~1–2 GB image may cost a few cents to about USD 0.20 per month, so old images are deleted.

## 12. Change log

- 1.0 (2026-11-11): first version.
