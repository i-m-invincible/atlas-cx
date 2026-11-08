# Atlas CX saved checkpoint

Paused at the user's request on 9 November 2026 (India time). Do not restart the
foundation or M1, discard changes, merge main, deploy, or start M3 before closing
the M2 handoff.

## Completed

M2 backend and frontend are committed and pushed to
`feature/atlas-cx-development`. The tested code commit is
`f58ddd69f6834d1d3d6067a274c11e60f81be0cc`. The subsequent checkpoint commit
preserves README, roadmap, verification, file manifest, architecture decisions,
and this resume record.

Implemented: default published case configuration; portal creation and own-contact
request access; inbox/list/search/filters; claim and assignment; public replies,
private notes, read markers; prescribed transitions; resolution/reopening cycles;
response/resolution clocks; ETag concurrency; idempotent retries; audit events;
forced RLS/composite constraints; responsibility transfer and archive guards.
Organic support/portal screens include drafts, errors, conflict review, keyboard
focus, responsive layouts, and linked customer cases. M0/M1 authentication and
customer functionality remain in place. Authoritative sources are unchanged.

## Verified

- Backend: Ruff lint/format, strict mypy, 52 unit/HTTP tests.
- Real PostgreSQL/pgvector: 64 integration tests using `atlas_app`, including
  workspace isolation, contacts sharing one customer, concurrent claims,
  transitions/clocks, database constraints, and private-message isolation.
- Frontend: formatting, ESLint, TypeScript, Vite build, 27 unit/integration tests.
- Chromium: 29 deterministic checks, including 1440/1024/700/390px interactions,
  keyboard/draft/conflict behavior, assignment, reduced motion, and automated axe.
- Compose CI: M0/M1 preservation upgrades, rollback/repeat upgrade, both image
  builds, health/security-header smoke checks, and both M1/M2 real-stack browser
  workflows. The M2 browser test verifies persisted portal → staff reply →
  resolution → reopen → closure, and cross-contact/workspace denial.
- Source hash verification passed. Representative screenshots were inspected.

Both jobs passed on the tested code commit in
[PR CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42512924979).
No observed failure remains on that commit. Local Docker/PostgreSQL is unavailable;
database/container evidence comes from CI. The checkpoint documentation push
triggers another run; it has not been observed at the pause.

## Resume tomorrow

1. Open this repository at
   `C:\Users\aryan\OneDrive\Desktop\atlas cx\atlas-cx`. Run `git status --short --branch`
   and `git log -3 --oneline`. Stay on `feature/atlas-cx-development`; preserve any
   newer user changes. Fetch origin and compare HEAD before pulling or editing.
2. Read `AGENTS.md`, both specifications, `docs/ROADMAP.md`, the wireframe PDF,
   and architecture records 0002/0003. Read this record and VERIFICATION.md.
3. Inspect the latest checks on [PR #1](https://github.com/i-m-invincible/atlas-cx/pull/1).
   Confirm the documentation checkpoint's exact HEAD passed. If any new failure
   appears, inspect its logs and fix only the observed issue before expanding scope.
4. Review the M2 diff/file manifest, update the verification record if needed, and
   finish the seven-part M2 report. The PR remains open against main; do not merge.
5. After the M2 handoff, the next implementation milestone is M3 Configuration
   and follow-up: published versions, five presets, bounded fields, tasks, ratings
   with exactly-one low-feedback task, and CSV imports. Begin it only when requested.

Full manual screen-reader review, load/capacity measurements, and restore/release
validation remain later release work. No RAG, analytics, health computation,
email delivery, paid resources, or deployment was added in M2.
