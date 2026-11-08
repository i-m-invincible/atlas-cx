# Step 3 verification

Verification date: 8 November 2026. Host: Windows, Node 24.17.0, npm 11.13.0,
managed CPython 3.12.13, uv 0.11.2. No application was deployed.

| Check                           | Observed result                                                                                                                                                 |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Authoritative sources           | All three were read before implementation; SHA-256 checks confirm exact preserved bytes.                                                                        |
| Dependency installation         | Backend and frontend dependencies installed; locks committed. A fresh `npm ci` succeeded.                                                                       |
| Frontend build                  | Vite production build passed; both local WOFF2 font assets emitted.                                                                                             |
| Frontend unit tests             | 5 passed: successful health response, network failure/retry, HTTP error, invalid payload, and pending/unmount behavior.                                         |
| Backend unit/HTTP tests         | 10 passed; 5 PostgreSQL tests explicitly deselected, not counted as passes.                                                                                     |
| Backend lint/format/types       | Ruff and strict mypy passed.                                                                                                                                    |
| Frontend lint/format/types      | Passed with ESLint 10 and strict TypeScript, including the drawer correction.                                                                                   |
| HTTP liveness                   | Real localhost GET `/api/v1/health/live` returned 200 with `data.status=ok` and a request ID.                                                                   |
| HTTP readiness without DB       | Real localhost GET `/api/v1/health/ready` returned 503, as required when PostgreSQL is absent.                                                                  |
| Browser checks                  | 8 passed after fixing the observed drawer focus-wrap failure. Screenshots at 1440, 390, and 320 px were visually inspected.                                     |
| npm audit                       | Fresh dependency resolution reported zero vulnerabilities after a minimatch 11.0.1 override. Python pip-audit also reported no known vulnerabilities.           |
| Local Docker                    | Not executed: Docker executable/daemon unavailable on this host.                                                                                                |
| PostgreSQL/pgvector integration | Not executed locally: no PostgreSQL server. CI is configured to run all five integration tests under `atlas_app`.                                               |
| Container and migration checks  | CI configured for Compose validation, image builds, fresh migration, empty-schema downgrade/upgrade, repeat upgrade, and HTTP smoke tests; run results pending. |

The initial sandbox blocked DNS and Windows asyncio's local socket pair. Required
dependency downloads and socket-based tests were rerun with execution approval.
These were environment restrictions, not test passes. The browser failure led to
explicit wrapping of focus at the navigation drawer's first and last controls.

No customer/case/RAG workflow, backup restore, load benchmark, full manual zoom,
NVDA/VoiceOver review, or real-data security certification is claimed. The full
specification's release gates belong to later milestones. The next milestone is
M1 Identity and customer core, defined in ROADMAP.md.
