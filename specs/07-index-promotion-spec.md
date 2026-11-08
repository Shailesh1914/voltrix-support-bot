# Index Promotion Spec — Voltrix VX-200 Support Bot

Status: Version 1.0, approved by Shailesh on 2026-11-01

## Goal (Section 2.4)
A new knowledge-base version is a data deployment. It reaches users
only after it passes the same evaluation as code, and the previous
version stays available for an instant rollback.

## The active version
- The version the bot serves is a committed one-line file:
  data/ACTIVE_KB_VERSION (for example "v1"). It replaces the
  ACTIVE_KB_VERSION setting in .env; the bot refuses to start if
  .env still sets it, so there is only one source.
- Only Shailesh changes this file (data/ is read-only for every
  session). Every change goes through a pull request.
- Because data/ is a gate path (spec 06), changing the file runs
  the evaluation gate on the version written in it.

## Promoting a new version
1. The new version's articles are committed in data/kb_<version>/.
2. Ticket labels are reviewed against the new version, with written
   reasons. A label may be widened ("any") with an article that
   exists only in the new version; this does not change the score
   on older versions.
3. Free check: Part A on the new version. Retrieval recall must not
   be lower than on the current version, or the difference is
   explained in writing.
4. A pull request changes data/ACTIVE_KB_VERSION to the new version.
   The evaluation gate runs on that version. The pull request is
   merged only if the gate passes (AC1 >= 85%, AC2 >= 95% on the
   full set, spec 02).
5. No regression: every ticket that passes on the current version
   must also pass on the new one, or the difference is explained in
   writing before merging.

## Keeping the old version
- The previous version's articles (data/kb_<old>/) stay in the
  repository; nothing is deleted while a rollback to it is possible.
- Indexes are built from data/ (never committed); CI builds every
  version that tests or the gate need.

## Rolling back
- Rollback = GitHub's "Revert" on the promotion pull request. The
  revert pull request changes the file back and runs the gate on
  the old version; it is merged only if the gate passes.
- Rollback drill: after each promotion, a revert pull request is
  opened, its gate must pass, and it is then closed WITHOUT merging.
  The drill is recorded in notes/.

## Threshold
ESCALATION_THRESHOLD (0.60) is not changed by a promotion. The
Part A report on the new version shows its score distribution; if
the lowest answer score falls near or below 0.60, this is flagged
in writing before promoting.

## Acceptance criteria
1. The bot reads its version only from data/ACTIVE_KB_VERSION; a
   .env setting for it is refused.
2. The gate (and Part B) evaluate the version in that file.
3. Changing that file in a pull request runs the gate.
4. The promotion to v2 passes the gate and is merged.
5. The rollback drill's gate passes on v1, and the drill is closed
   without merging.