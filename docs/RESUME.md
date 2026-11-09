# Atlas CX saved checkpoint

This record captures the M2 pause and handoff on 9 November 2026 (India time).
The development branch is `feature/atlas-cx-development` and the review is
[PR #1](https://github.com/i-m-invincible/atlas-cx/pull/1).

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

Both CI jobs also passed on the saved checkpoint
`739f1887feb4c09dbb7bd0656c8edeca01e08553`. Local Docker and PostgreSQL were
unavailable, so the database and container evidence comes from GitHub Actions.
[Checkpoint PR CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42513324350)

## Handoff

The handoff records the passing checkpoint, the M2 file manifest, and the
verification limits. Start M3 when requested, using the scope in the roadmap.
[Verification](VERIFICATION.md) · [Changed files](M2_FILE_MANIFEST.md) · [Roadmap](ROADMAP.md)

Full manual screen-reader review, load/capacity measurements, and restore/release
validation remain later release work. No RAG, analytics, health computation,
email delivery, paid resources, or deployment was added in M2.
