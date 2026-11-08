# Atlas CX

Customer Operations & Service Intelligence Platform. This repository currently
implements Step 3: project initialization, corresponding to the M0 foundation.
It is a standalone project with no Churn Atlas integration or churn prediction.

The foundation contains a responsive React application shell, Organic tokens and
self-hosted fonts, a FastAPI health API, a workspace database boundary with forced
row-level security, Alembic migrations, and a local same-origin container setup.
Customer records, authentication, cases, portal workflows, knowledge/RAG, health
scoring, analytics, and workers are not implemented yet. The UI labels planned
sections and displays no invented customer data or metrics.

Read the unchanged [product specification](docs/PRODUCT_SPEC.md),
[design system](docs/DESIGN_SYSTEM.md), and [wireframe atlas](docs/Atlas_CX_Wireframe_Atlas.pdf)
before coding. [AGENTS.md](AGENTS.md) defines permanent engineering rules.
[Source provenance](docs/SOURCES.md) records the original names and hashes.

## Local containers

Requirements: Docker Engine/Desktop with Compose v2 supporting `up --wait`.
No hosted services, paid resources, or AI model downloads are required.

```sh
cp .env.example .env
docker compose config --quiet
docker compose up --build -d --wait
python scripts/smoke.py
```

In PowerShell, use `Copy-Item .env.example .env` for the first command.
Open [the application](http://localhost:8080),
[API docs](http://localhost:8000/api/docs),
[liveness](http://localhost:8080/api/v1/health/live), and
[readiness](http://localhost:8080/api/v1/health/ready).
The proxy serves frontend and API from one origin. Ports bind only to loopback.
The separate migration job finishes before API startup; the API does not receive
migration or queue credentials. PostgreSQL 17 includes pgvector 0.8.2.

```sh
docker compose logs -f api
docker compose down
```

`down` retains the database volume. Do not add `--volumes` unless you intend to
erase local data. Role initialization runs only for a fresh database volume;
changing example passwords does not rotate credentials in an existing database.
The example passwords are public development values. This stack has no public
TLS, backup automation, or production access policy; it is a local environment.

## Host development

Use Node.js 24.17.0, npm 11, Python 3.12.13, and uv 0.11.2. Versions are recorded in
the runtime files; exact dependencies are locked in package-lock.json and
backend/uv.lock. Use `npm ci` and `uv sync --locked` after checkout.

```sh
npm ci
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal at the repository root:

```sh
npm run dev
```

Open [Vite](http://localhost:5173); its `/api` proxy targets port 8000. The shell
and liveness work without PostgreSQL. Readiness returns 503 until the database
is reachable with the application role, pgvector is installed, and migrations
match this release. For a host API plus container database:

```sh
docker compose up -d --wait db
docker compose run --rm migrate
```

Host processes use the localhost URLs in `.env.example`. Alembic requires an
explicit `MIGRATION_DATABASE_URL` environment variable; it does not silently use
the API credential. Set it in the operator terminal before `uv run alembic upgrade head`.
`PUBLIC_ORIGIN` is reserved for M1's Origin/CSRF checks; M0 has no authenticated
browser mutations. It does not configure Vite's proxy. There is no CORS wildcard.

## Checks

```sh
npm run check
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

The default pytest command selects unit/HTTP tests. The PostgreSQL integration
suite is separate and must run against an expendable migrated test database:
set `TEST_DATABASE_URL` to its `atlas_app` URL and `MIGRATION_DATABASE_URL` to its
`atlas_migrator` URL, then run `uv run pytest -m integration`. It verifies actual
RLS reads/writes, missing context, connection reuse, role safety, and pgvector.
It fails if those explicit URLs are missing; SQLite is not a substitute.

From the root, install the browser once and run the shell checks:

```sh
npx playwright install chromium
npm run test:e2e
python scripts/verify_sources.py
```

Playwright tests reflow at 1440, 1024, 700, 390, and 320 CSS pixels, drawer keyboard
behavior, reduced motion, and serious/critical axe violations. No screen-reader
certification or full product-flow coverage is claimed. Test-only network stubs
exercise health failures; the production client always calls the real API.

Regenerate contracts after API schema changes:

```sh
cd backend
uv run python -m scripts.export_openapi
cd ..
npm run api:generate
```

CI checks generated drift, frontend/backend quality, browser behavior, source
hashes, dependency advisories, image builds, empty migration/rollback/upgrade,
real PostgreSQL isolation, and same-origin HTTP smoke checks. It does not deploy.
See the [created file manifest](docs/FILE_MANIFEST.md), [verification evidence](docs/VERIFICATION.md) for actual execution results,
[architecture decisions](docs/architecture/0001-foundation.md), and the
[next milestone](docs/ROADMAP.md): M1 Identity and customer core.
