# Step 13 – Deployment decisions and facts not recorded elsewhere

Written by Shailesh on 2026-11-16, after the architecture review found these gaps.

## AWS budget

- The AWS budget `voltrix-project-budget` exists: created before Step 13, confirmed in Task 13.1 Check 4 (2026-11-11). Monthly cost budget of USD 5, email alert only, no actions.

## Why AWS Lambda (and not ECS Fargate or App Runner)

- Learning project: cost close to zero and easy to switch off were the main goals (spec 08 section 1).
- Lambda costs nothing while idle (pay per request, free tier) and scales to zero.
- ECS Fargate needs a load balancer and usually a NAT gateway; both cost money every hour, even when nobody uses the bot.
- App Runner also keeps a paid minimum while the service is running.
- A container image on Lambda lets the bot keep its own Python 3.14 (Lambda's built-in Python goes up to 3.13 only) and the exact same image as on the laptop (Stage A).
- Path chosen on 2026-11-09: laptop container first (A), then Lambda with a Function URL (B).
- Trade-off accepted: a cold start of about 12.5 s (spec 08 section 7).

## Why numpy brute-force search (and not a vector database)

- The data is tiny: 39 articles, 187 chunks (kb_v2).
- A full dot product over 187 vectors takes milliseconds and is exact (no approximate search).
- No extra service to run, secure or pay for.
- Deterministic and verifiable: identical results across runs, and the index files have SHA-256 hashes in the manifest (idempotent builds, spec 01).
- A vector database (or FAISS) becomes worth it at many thousands to millions of chunks, or when several processes must update the index.

## Why SSM Parameter Store (and not Secrets Manager)

- Parameter Store Standard tier is free; Secrets Manager costs about USD 0.40 per secret per month.
- Two values only, read once at start-up.
- Secrets Manager's main extra is automatic rotation, which a short demo bot does not need. Keys are changed by hand and the bot is switched off after the demo.

## Why the Function URL (and not API Gateway)

- Simplest public HTTPS endpoint for one function, no extra service or cost.
- API Gateway, custom domains and own certificates are out of scope (spec 08 section 2).
- Protection is the access code checked by the app before any work; spending is capped by the Anthropic workspace limit.

## Why a separate Anthropic key per environment

- CI gate, laptop and deployed bot each have their own key, so an expiry, a leak or a switch-off affects one place only.
- Seen in practice: the laptop key expired on 2026-11-13 while the deployed bot kept working on its own key.

## Measured build time

- Release image build from scratch: 341 s (5.7 minutes) with `--no-cache` (Stage A). Code-only rebuilds: 1–2 minutes. The "about 10 minutes" in `deploy/README.md` was an estimate made before the first build.

## Test counts after Step 13

- Structural tests in CI: ingestion 232, query 571, web 185, evals 378 (1,366 in total). Web went from 182 to 185 when three tests for the spec 08 v1.2 rules were added.
- `deploy/tests/`: 187 (not in CI).

## Known small issue

- The comment above `ESCALATION_THRESHOLD` in `query/config.py` still says "NOT YET SET", although the value is 0.60 since 2026-10-18. To be fixed by Session Q (a `query/` change, so the paid gate runs; do it before the CI key expires on 2026-11-30).
