# Foundation architecture

Status: implemented for Step 3, the M0 foundation.

Atlas CX uses one FastAPI application and one PostgreSQL database. Domain code
lives in `backend/app/modules`; shared transaction and HTTP infrastructure lives
in `backend/app/platform`. Only the workspace root exists today. There are no
customer, case, assistant, analytics, or worker implementations.

The API uses synchronous SQLAlchemy 2.0 and psycopg 3, as required by PRODUCT_SPEC
section 14. Database routes run in FastAPI's synchronous handler pool. Health
liveness checks only the process. Readiness checks connectivity, the exact Alembic
head, pgvector 0.8.x, and a non-owner, non-superuser, non-BYPASSRLS runtime role.
Generation is not a readiness dependency.

The workspace root's `id` is the tenant boundary. Future tenant-owned child tables
will carry `workspace_id`, composite relationships, and their own forced RLS
policies. The foundation policy restricts both reads and writes. The transaction
helper sets workspace context locally so it cannot survive connection reuse.
This protects accidental unscoped queries; it is not authentication and cannot
defend a compromised application credential that deliberately selects a scope.
The auth dependency denies all private access until M1 verifies opaque sessions.
No workspace header, provisioning endpoint, or customer endpoint is exposed.

Database initialization creates three separate roles. `atlas_migrator` owns the
schema objects; `atlas_app` receives explicit object grants; `atlas_queue` is
reserved without business-table privileges. The database operator installs
pgvector. The API receives only its own URL. A separate one-shot migration
container runs before API startup. M0 has no existing release fixture; CI tests
empty migration, downgrade/upgrade of this empty schema, and repeated upgrade.

React uses strict TypeScript, React Router, Vite, and Tailwind's official Vite
plugin. The single CSS token set preserves the Organic palette and font bindings.
WOFF2 assets are bundled locally from Fontsource packages rather than fetched
from a third-party origin in the browser. Native dialog supplies modal focus and
Escape behavior. Planned navigation is plain labelled text, not fake controls.
No sign-in or workspace identity is simulated. Server-state/form libraries will
be added when M1 introduces their first actual consumers.

OpenAPI is exported from FastAPI and generates TypeScript types. A small health
client uses those generated types and checks its minimal response at runtime.
CI detects drift in both artifacts. Unit tests cover safe failures and retries;
PostgreSQL tests cover real RLS using `atlas_app`. Browser tests cover reflow,
drawer keyboard behavior, reduced motion, and automated accessibility checks.
These checks do not establish WCAG certification or the full MVP release gates.

Compose currently contains database, migration job, API, and static web proxy.
The full topology's core worker, AI worker, and optional Ollama are intentionally
deferred until their implementing milestones. No idle worker or fake job loop is
present. Containers and actions are pinned to verified registry/commit digests.
This configuration is for loopback-only development, without public TLS or backup
automation. It must not be represented as a production deployment.

Implementation references: [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite),
[SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/core/connections.html),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), and
[pgvector](https://github.com/pgvector/pgvector). Behavioral requirements remain
the preserved specifications, not these library documents.

The dependency lock overrides minimatch versions 7 through 11.0.0 with 11.0.1
to address GHSA-g3hv-75wg-m249 in development tooling. Frontend lint and build
checks validate the resulting tree. Older minimatch major versions used by the
OpenAPI tool are outside that advisory range and remain unchanged.
