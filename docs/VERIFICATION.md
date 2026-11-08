# Verification evidence

## M1 identity and customer core

Date: 8 November 2026. Same Windows toolchain as the foundation record below.
All required source files were read before coding; the authoritative source
documents remain byte-identical.

- Backend: 21 unit/HTTP tests passed. The first CI run passed 27 PostgreSQL cases;
  seven additional role, transfer, recovery, and concurrency cases await CI.
- Frontend: production build, strict TypeScript, ESLint, and formatting passed.
  All 16 unit tests passed, including explicit contact conflict review/re-save.
- Ruff lint, formatting, and strict mypy passed.
- All 17 browser interaction/reflow checks passed locally at 1440, 1024, 700,
  and 390 px, plus foundation shell checks at 320 px. Representative list/detail/
  form screenshots across the required sizes were visually inspected.
- Docker and PostgreSQL are unavailable on this host. CI passed the M0 data
  preservation upgrade, rollback/repeat upgrades, real-role isolation suite,
  container builds, and same-origin health smoke checks.
- The initial real-stack browser test reached customer/contact persistence and
  portal setup, then checked permissions before portal login finished because
  its heading selector also matched the sign-in heading. The selector was made
  exact. The corrected full flow awaits CI; it is not counted as a pass yet.

No case authorization, release load/restore test, screen-reader certification,
deployment, or production-readiness claim is made. M2 adds the real case vertical
slice and its same-customer/contact case-access tests.

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
