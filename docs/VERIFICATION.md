# Verification evidence

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
