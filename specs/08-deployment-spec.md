# Spec 08: Deployment

Status: Version 1.1, approved by Shailesh on 2026-11-11
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
| D4 | Anthropic key | A new key used only by the deployed bot. Laptop: read from the secrets file outside the project, mounted read-only into the container. AWS: read from Parameter Store, Standard tier, SecureString |
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
- Body JSON: `{"question": "<text>"}`. Extra fields are ignored.
- Checks, in this order, before anything else happens:
  1. Access code missing or wrong → HTTP 401, JSON `{"error": "access denied"}`. The comparison uses a constant-time compare. This check runs before the body is read, so a bad code with a bad body gives 401.
  2. Body problems → HTTP 400 with exactly these `error` texts:

| Case | `error` |
|---|---|
| Body is not valid JSON, or not a JSON object | `invalid request body` |
| `question` missing | `question is required` |
| `question` is not a string | `question must be text` |
| `question` empty after trimming spaces | `question is empty` |
| `question` longer than 1000 characters (counted as sent, before trimming) | `question is longer than 1000 characters` |

- Then the question goes through the existing query flow (`query/flow.py`), unchanged. The web layer adds no new prompt text, no new checks and no changes to the threshold.
- Success → HTTP 200 with the flow's result unchanged: `status`, `answer`, `citations`, `escalation_reason`, `handoff_id` (the field names of spec 02 "Output").
- Anthropic failures are handled by the flow as spec 02 decision 6 says: the result is an escalation with reason `service_error` and a handoff id, returned with HTTP 200. The web layer does not turn this into another status code.
- Any other unexpected error → HTTP 500, JSON `{"error": "internal error"}`. No stack trace is returned.
- Every `/ask` response carries an `X-Request-Id` header (a uuid4 made by the app), the same id as in the log line.

### 4.3 `GET /`

- One simple HTML page: an access code field, a question box, an Ask button, and an area showing the answer, citations or the escalation message.
- Plain HTML, CSS and a little JavaScript inside the page. No external scripts or fonts.
- The page shows a note: "Demo bot for a fictional product (Voltrix VX-200). Synthetic data only."
- The access code typed in the page is kept only in the page's memory, not stored in the browser.

### 4.4 Logging

- One request log line per `/ask` request: request id, decision (`-` for 400, 401 and 500), latency in milliseconds, HTTP status.
- Uvicorn's own access log is turned off (it would add a second line and the client IP).
- The existing warning from `query/anthropic_api.py` on an API failure (error class and HTTP status only) is allowed in addition.
- The question text, the answer text, the access code and the Anthropic key are never logged.

### 4.5 Handoff records

- When the environment variable `HANDOFF_DIR` is set, handoff records go to the file `handoffs.jsonl` inside that folder. When it is not set, spec 02 decision 8 applies unchanged (`HANDOFF_PATH`, default `handoffs/handoffs.jsonl`). Setting both stops the start-up.
- On Lambda, `HANDOFF_DIR=/tmp/handoffs`. These files disappear when Lambda recycles the environment. This is accepted for this iteration (section 2).

### 4.6 Tests (Session Q)

- Use a fake Claude client. No paid calls in structural tests.
- Expected values (status codes, limits such as 1000 characters, error messages, field names) are taken from this spec, not from the code.
- Must prove: `/health` works without a code and never calls Claude; a wrong or missing code gives 401 and makes zero Claude calls and zero retrieval calls; each 400 case with its exact text; a correct request returns the flow's result unchanged; a service error comes back as a 200 escalation; the 500 case; the start-up rules of section 5; no secret appears in any response or log line.
- These tests live in `tests/structural/web/` and run in CI (spec 06).

## 5. Secrets and settings

The setting `VOLTRIX_SECRETS_SOURCE` (not a secret) says where secrets come from: `file` (default) or `parameter_store`. Any other value stops the start-up.

| Setting | Laptop (Stage A) | Lambda (Stage B) |
|---|---|---|
| `VOLTRIX_SECRETS_SOURCE` | `file` (or not set) | `parameter_store` |
| Anthropic key | `VOLTRIX_ANTHROPIC_API_KEY` in the secrets file outside the project, mounted read-only into the container | Parameter Store SecureString `/voltrix/anthropic-key` |
| Access code | `VOLTRIX_ACCESS_CODE` in the same secrets file | Parameter Store SecureString `/voltrix/access-code` |
| `IMAGE_TAG` | not set | the image tag |
| `HANDOFF_DIR` | not set (spec 02 default) | `/tmp/handoffs` |

Rules:
- The key keeps the project's existing name `VOLTRIX_ANTHROPIC_API_KEY`. Variables starting with `ANTHROPIC_` are refused, in both modes.
- The laptop container gets the secrets file as a read-only mount, not with `--env-file`, so the values do not show in `docker inspect`.
- In `parameter_store` mode, the app reads the two parameters once at start-up (with decryption) and keeps them in memory. If the key or the access code is also set as an environment variable, the start-up stops, so secrets never sit in Lambda's environment settings.
- No secret is written into the image, the Dockerfile, GitHub, CI settings, notes or screenshots.
- The access code must be at least 12 characters. A shorter code stops the start-up.
- Start-up errors name the setting that is wrong, never its value.
- The access code is chosen by the owner and changed after the demo.

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
- AC-D6: The tests in `tests/structural/web/` pass in CI, with no skipped tests (spec 06 v1.2).

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
- 1.1 (2026-11-11): answers to Session Q's Round 1 questions. 503 removed (service errors stay 200 escalations, spec 02 decision 6); exact 400 texts; 500 case; X-Request-Id; logging details; HANDOFF_DIR rule; VOLTRIX_SECRETS_SOURCE; secret names; read-only mount; minimum code length enforced; web tests run in CI.
