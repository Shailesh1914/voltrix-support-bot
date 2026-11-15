# Step 13.5–13.6 – AWS Lambda (Stage B)

Spec 08 v1.3. Branch `stage-b`. Region ap-south-1 (Mumbai).

## Result

| Check | Result | Run by |
|---|---|---|
| AC-D7 free part (`check_stage_b.py`): /health v2 and tag, three 401 cases, X-Request-Id, CSP header, /docs off, no key prefix | **11 passed, 0 failed** | Shailesh, 2026-11-15 |
| AC-D7 / AC-D4 on Lambda (`compare_tickets.py --url`) | **Passed** under the v1.3 rule (runs below) | Shailesh, 2026-11-15 |
| AC-D8 no reserved concurrency; workspace `voltrix-deployed` limit USD 5 | Checked in the consoles | Shailesh |
| AC-D9 secret search (repo 265 files / 92 commits, image 46,895 files, Lambda settings, logs 422 events) | **Passed**: no secret; 6 AWS documentation example key ids reported as examples | Shailesh, 2026-11-15 |
| First real question in the browser (E-17) | Answered, cited KB-037, safety step first | Shailesh, 2026-11-14 |
| AC-D10 switch-off | To do after the demo (Task 13.7) | |

## AC-D4 runs on Lambda (all recorded, none hidden)

| Run | T-001 | T-002 | T-043 | Outcome |
|---|---|---|---|---|
| 1 | laptop service_error / Lambda KB-001 | laptop service_error / Lambda KB-002, KB-025 | laptop service_error / Lambda escalated | Inconclusive (re-run gave the same) |
| 2 (new laptop key) | KB-001 / KB-001 | laptop KB-002, KB-025 / Lambda KB-002 | escalated / escalated | **FAILED** under the v1.2 rule (exact citation set) |
| 3 (v1.3 rule) | KB-001 / KB-001 match | laptop KB-002 / Lambda KB-002, KB-025: differs (both valid) | escalated / escalated match | **PASSED** |

- Run 1: the laptop key `voltrix-bot-dev` had expired on 2026-11-13 (30-day expiry). HTTP 401 AuthenticationError. Not a leak: the AC-D9 repo search covers all 92 commits. New laptop key `voltrix-bot-dev-2` created.
- Runs 1–3 show that the same bot cites KB-025 for T-002 sometimes and sometimes not, on both sides. That is model variance, not deployment drift (same index hashes, same search, same prompt). T-002's label expects KB-002; both sets are correct under spec 05.
- Decision: AC-D4 is judged by the spec 05 label rules (spec 08 v1.3). `compare_tickets.py` uses Session E's `evals/eval_scoring.passes()` for this.

## Start-up measurement (`measure_cold_start.py`, 2026-11-15)

| Run | AWS_LWA_ASYNC_INIT | To /health 200 | Init Duration | Duration | Billed | Max memory | INIT_REPORT |
|---|---|---|---|---|---|---|---|
| 1 | true | 21.2 s | 9.8 s | 11.0 s | 20.8 s | 865 MB | - |
| 2 | false | 20.4 s | - | 10.1 s | 10.1 s | 865 MB | 10000 ms init timeout |
| 3 | true | 12.6 s | 9.8 s | 2.5 s | 12.3 s | 865 MB | - |
| 4 | false | 20.1 s | - | 9.9 s | 9.9 s | 865 MB | 10000 ms init timeout |
| 5 | true | 12.5 s | 9.8 s | 2.4 s | 12.3 s | 865 MB | - |
| 6 | false | 20.4 s | - | 10.0 s | 10.0 s | 865 MB | 10000 ms init timeout |

Decision: `AWS_LWA_ASYNC_INIT=true` (no timeouts, about 8 s faster). Run 1 is the first start after a change (image layers pulled). Memory stays at 2048 MB: less memory also means less CPU and a slower start.

## What was set up (console, Shailesh)

- Anthropic: workspace `voltrix-deployed`, monthly limit USD 5; key `voltrix-lambda` created there and copied straight into Parameter Store.
- Parameter Store: `/voltrix/anthropic-key`, `/voltrix/access-code` (Standard, SecureString, `alias/aws/ssm`). The Stage B access code differs from the laptop one.
- ECR `voltrix-support-bot`: Immutable. Image `v2-20261114-406e022` (from main 406e022, 537 MB compressed).
- CloudWatch log group `/aws/lambda/voltrix-support-bot`, 7 days. Leftover `/aws/lambda/voltrix-test` from Task 13.1 to delete.
- IAM: role `voltrix-support-bot-lambda` (one policy), user `voltrix-deploy` (one policy, no console access), access key in the laptop profile `voltrix-deploy`. AWS CLI's offer to connect AI agents through an AWS MCP server: answered "never".
- Lambda: classic function `voltrix-support-bot`, x86_64, 2048 MB, 60 s, four environment variables, Function URL auth NONE, BUFFERED, CORS off. No reserved concurrency: the account limit is 10.
- No `kms:Decrypt` statement needed: the app read both parameters at start-up.

## Scripts (Session D, `deploy/`)

`build_release.sh`, `ci_passed.py`, `push_image.py`, `point_lambda.py`, `check_stage_b.py`, `measure_cold_start.py`, `check_secrets_stage_b.py`, `compare_tickets.py --url`, shared `stage_b.py`. All AWS calls use the profile `voltrix-deploy` and stop for any other caller; anything that changes AWS needs `--confirm`. `deploy/tests/`: 187 passed, 0 failed, 0 skipped (not in CI).

## Key expiry dates (important)

| Key | Used by | Expires |
|---|---|---|
| `voltrix-ci` | evaluation gate in CI | 2026-11-30 |
| `voltrix-lambda` | deployed bot | 2026-12-13 (demo before this) |
| `voltrix-bot-dev-2` | laptop bot | 30 days from 2026-11-15 |

## Costs

- AWS: about USD 0.05 per month (ECR storage); everything else inside the free tier.
- Claude: about USD 0.006 per answered question; refused requests and escalations without a Claude call cost nothing.

## Next iteration

- Add `deploy/tests/` to CI (it caught two stale spec-wording tests only by luck).
- Short-lived AWS credentials instead of a long-lived access key.
- Try Lambda Web Functions (no adapter needed).
- 500 log line: add the error class name.
- Lock file for unpinned packages (CI and image together).
- Key expiry: put expiry dates where they are seen (a reminder before the CI key expires).
