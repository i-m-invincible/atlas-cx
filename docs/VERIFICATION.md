# Verification evidence

## M2 case vertical slice

Date: 9 November 2026 (India time). The required specifications, wireframes,
engineering rules, roadmap, and M1 architecture record were read before coding.
The product/design specifications and PDF remain byte-identical. No dependency
was added for M2; the existing locked installations were used locally and clean
installations are repeated by CI.

| Check                     | Observed result                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend quality           | Ruff lint/format and strict mypy passed; all 52 unit/HTTP tests passed locally.                                                                                                                                                                                                                                                                                                                                 |
| PostgreSQL                | 64 integration cases passed in CI against PostgreSQL 17/pgvector using the actual non-owner, non-superuser, non-BYPASSRLS `atlas_app` role.                                                                                                                                                                                                                                                                     |
| API behavior              | Creation and numbering, default/pinned configuration, assignment, competing claims, all invalid-transition fixtures, resolution/reopening, terminal closure, immutable messages, audit atomicity, monotonic read markers, filters/cursors, and idempotent retries are covered.                                                                                                                                  |
| Privacy                   | Tests cover cross-workspace IDs/associations, two contacts sharing one customer, public/private message separation, safe portal DTOs, mass-assignment rejection, revoked access, direct RLS reads/writes, and role restrictions.                                                                                                                                                                                |
| Clocks                    | Independent fixed-time fixtures cover first response, pending pauses, direct resolution from pending, strict overdue boundaries, snapshotted targets, and new cycles retaining prior resolutions.                                                                                                                                                                                                               |
| Migrations and containers | CI passed M0 and M1 preservation fixtures, empty-schema downgrade/repeat upgrades, Compose validation, both image builds, and health/security-header smoke checks.                                                                                                                                                                                                                                              |
| Frontend quality          | Formatting, ESLint, strict TypeScript, Vite build, and all 27 unit/integration tests passed locally.                                                                                                                                                                                                                                                                                                            |
| Deterministic browsers    | All 29 checks passed in the local regression suite. Two real-stack tests skip locally; skips are not passes.                                                                                                                                                                                                                                                                                                    |
| Responsive review         | Support and portal interactions tested at 1440, 1024, 700, and 390px. Screenshots were inspected for conversation/form layouts and resolution dialogs. Mobile dialog viewport dimensions, keyboard focus containment, draft preservation, Back focus/filter restoration, and horizontal overflow are asserted. Automated axe checks found no serious/critical violations on the tested support/portal surfaces. |
| Real-stack M2 browser     | Both M1 and M2 real-stack browser tests passed in CI against Compose, using persisted API data without route mocks.                                                                                                                                                                                                                                                                                             |
| Local Docker/PostgreSQL   | Unavailable on this Windows host. All actual database/container results come from GitHub Actions.                                                                                                                                                                                                                                                                                                               |

The real-stack scenario creates a portal request, reloads persisted data, claims
and edits assignment, posts a private note and public reply, asks for information,
resumes through a portal response, resolves, reopens, verifies the preserved prior
cycle, resolves again, and closes. It also attempts another contact's read/reply/
reopen and another workspace's case ID, and checks secure cookies and empty
browser storage. Its synthetic fixtures live only in a disposable database;
random credentials are written to ignored private files and never printed.

Observed failures were fixed: scoped migration-fixture cleanup needed a staff
audience; transition references had to be removed before test messages; imported
PostgreSQL fixtures had to remain registered after linting; queue Back focus
needed to follow the shell's heading focus; and delayed heading focus needed to
respect users who had already started typing. Browser-test selectors were also
corrected for the portal's navigation/empty-state links and the synthetic member
label. The real-stack flow found that a reply's success notice could precede its
version refresh; state actions now stay disabled through the write/refresh and
take the confirmed version when opened. Desktop dialogs are explicitly centered
after visual review exposed the CSS reset's removal of their automatic margins.
Creation retries are checked before archived-record validation so an
authorized retry returns the original case without creating a new request.

Configuration publication UI, five presets, follow-up tasks, ratings, and CSV
imports remain M3. No RAG, analytics, or health computation was added. These
results do not constitute full manual screen-reader, restore, load, or production
release validation. Workspace transactions still serialize conservatively;
throughput has not been measured. Nothing was merged to main or deployed.

The M0/M1 sections below are historical milestone records; their statements about
case functionality being absent describe those earlier increments.

Both CI jobs passed on checkpoint `739f1887feb4c09dbb7bd0656c8edeca01e08553`.
The logs confirm 52 backend tests, 64 PostgreSQL integration tests, 27 frontend
tests, 29 deterministic Chromium checks, and two Compose browser workflows.
[Pull request CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42513324350)
and [branch CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42513319337)
record the results. The handoff review removed trailing spaces from the M2
migration SQL and verified that the migration diff contains only whitespace.

## M1 identity and customer core

Date: 8 November 2026. Same Windows toolchain as the foundation record below.
AGENTS.md, both specifications, ROADMAP.md, and the wireframe PDF were read before
coding. All three authoritative source documents remain byte-identical.

| Check                       | Observed result                                                                                                                                                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dependencies                | Locked frontend/backend dependencies installed; clean installations repeated in CI. npm audit reported zero known vulnerabilities.                                                                                                                                                         |
| Frontend quality            | Formatting, ESLint, strict TypeScript, Vite production build, and all 18 unit tests passed locally.                                                                                                                                                                                        |
| Backend quality             | Ruff lint/format, strict mypy, and 21 unit/HTTP tests passed locally and in CI.                                                                                                                                                                                                            |
| PostgreSQL integration      | 35 cases passed in CI using PostgreSQL 17/pgvector and the real non-owner, non-superuser, non-BYPASSRLS `atlas_app` role.                                                                                                                                                                  |
| Security and writes         | Verified cookie/session rotation and expiry, CSRF/Origin rejection, role checks, tenant isolation, same-customer contact RLS, setup acceptance/single use, portal revocation, ownership transfer, recovery, concurrent password changes, ETags, audit atomicity, and database constraints. |
| Migration and containers    | CI passed preservation of an existing M0 workspace during upgrade, empty-schema rollback, repeat upgrades, both container builds, and same-origin health/security-header smoke checks.                                                                                                     |
| Deterministic browser tests | 17 passed locally and in CI. The real-stack test is explicitly skipped without E2E_BASE_URL; this skip is not counted as a pass.                                                                                                                                                           |
| Real-stack browser          | 1 passed in CI against Compose: staff login, Secure/HttpOnly/Lax cookie, cross-workspace denial, persisted customer/contact creation, portal setup/login, staff CRM denial, portal navigation, and logout. No API mocks in this test.                                                      |
| Responsive review           | Customer interactions tested at 1440, 1024, 700, and 390 px; foundation shell also tested at 320 px. Representative list, detail, and form screenshots across the required widths were inspected. Automated axe checks passed for the tested surfaces.                                     |
| Local Docker/PostgreSQL     | Not available on the Windows host. Database and container results above come from GitHub Actions.                                                                                                                                                                                          |

The complete security implementation at `905572c2191f3786d3193b1e72beb3ff98a692a0`
passed [branch CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42503800856)
and [pull-request CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42503804942).
The final selector pagination and filter-reset regressions passed locally;
the [pull-request checks](https://github.com/i-m-invincible/atlas-cx/pull/1/checks)
repeat the entire suite on each push.

Observed failures were fixed: password whitespace was initially trimmed by a
shared input configuration; session-cache clearing could leave sign-in state
stale; the real-stack test's portal heading also matched its sign-in heading;
and pending existing-account access could be activated before setup acceptance.
Regression coverage now exercises those boundaries. Contact conflicts retain the
draft and require explicit review and save. Member/team selectors follow all API
pages, and clearing tag filters also clears the visible field.

No test failure is being left unresolved. These results do not constitute
case authorization, release load/restore validation, a full screen-reader audit,
deployment, or production-readiness evidence. Authenticated transactions currently
serialize within a workspace for correctness; throughput has not been measured.
M2 adds the actual case vertical slice and its same-customer/contact case tests.

## M0 foundation

Verification date: 8 November 2026. Host: Windows, Node 24.17.0, npm 11.13.0,
managed CPython 3.12.13, uv 0.11.2. No application was deployed.

| Check                           | Observed result                                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Authoritative sources           | All three were read before implementation; SHA-256 checks confirm exact preserved bytes.                                                                |
| Dependency installation         | Backend and frontend dependencies installed; locks committed. A fresh `npm ci` succeeded.                                                               |
| Frontend build                  | Vite production build passed; both local WOFF2 font assets emitted.                                                                                     |
| Frontend unit tests             | 5 passed: successful health response, network failure/retry, HTTP error, invalid payload, and pending/unmount behavior.                                 |
| Backend unit/HTTP tests         | 10 passed; 5 PostgreSQL tests explicitly deselected, not counted as passes.                                                                             |
| Backend lint/format/types       | Ruff and strict mypy passed.                                                                                                                            |
| Frontend lint/format/types      | Passed with ESLint 10 and strict TypeScript, including the drawer correction.                                                                           |
| HTTP liveness                   | Real localhost GET `/api/v1/health/live` returned 200 with `data.status=ok` and a request ID.                                                           |
| HTTP readiness without DB       | Real localhost GET `/api/v1/health/ready` returned 503, as required when PostgreSQL is absent.                                                          |
| Browser checks                  | 8 passed after fixing the observed drawer focus-wrap failure. Screenshots at 1440, 390, and 320 px were visually inspected.                             |
| npm audit                       | Fresh dependency resolution reported zero vulnerabilities after a minimatch 11.0.1 override. Python pip-audit also reported no known vulnerabilities.   |
| Local Docker                    | Not executed: Docker executable/daemon unavailable on this host.                                                                                        |
| PostgreSQL/pgvector integration | 5 passed in CI against real PostgreSQL 17/pgvector under `atlas_app`; no PostgreSQL server is available locally.                                        |
| Container and migration checks  | Passed in CI: Compose validation, both image builds, fresh migration, empty-schema downgrade/upgrade, repeat upgrade, and same-origin HTTP smoke tests. |

The initial sandbox blocked DNS and Windows asyncio's local socket pair. Required
dependency downloads and socket-based tests were rerun with execution approval.
These were environment restrictions, not test passes. The browser failure led to
explicit wrapping of focus at the navigation drawer's first and last controls.

No customer/case/RAG workflow, backup restore, load benchmark, full manual zoom,
NVDA/VoiceOver review, or real-data security certification is claimed. The full
specification's release gates belong to later milestones. The next milestone is
M1 Identity and customer core, defined in ROADMAP.md.

Implementation commit `409653c12feb48848b774b5d4aa62ed633a59572` passed both
[branch CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42482011281) and
[pull-request CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42482041628).
CI also repeated the 10 backend unit tests, 5 frontend unit tests, and 8 browser
checks successfully on Ubuntu. No test failures remain in the foundation suite.
The verification-record update changes documentation only.
