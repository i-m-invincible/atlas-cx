# Atlas CX

Customer Operations & Service Intelligence Platform. The repository contains the
M0 foundation and M1 identity and customer core. Atlas CX is standalone.

Staff can sign in, manage customers and contacts, search and filter records,
archive records, and administer workspace membership and teams according to
their role. Administrators issue single-use staff and portal setup links.
Portal users have a separate identity boundary; case submission and messaging
are planned for M2. No case, analytics, health scoring, RAG, or worker workflow
is implemented. Unknown health and activity remain unknown.

Read the unchanged [product specification](docs/PRODUCT_SPEC.md),
[design system](docs/DESIGN_SYSTEM.md), [wireframes](docs/Atlas_CX_Wireframe_Atlas.pdf),
[AGENTS.md](AGENTS.md), and [roadmap](docs/ROADMAP.md) before coding.
[Source provenance](docs/SOURCES.md) records original names and hashes.

## Local containers

Requirements: Docker Engine/Desktop with Compose v2 supporting `up --wait`.

```sh
cp .env.example .env
docker compose config --quiet
docker compose up --build -d --wait
python scripts/smoke.py
```

PowerShell: use `Copy-Item .env.example .env` for the first command.
Open [Atlas CX](http://localhost:8080) and [API docs](http://localhost:8000/api/docs).
The proxy serves frontend and API from one origin; ports bind only to loopback.
PostgreSQL 17 includes pgvector 0.8.2. A separate migration job runs before API
startup. The API receives only the non-owner `atlas_app` database credential.

Initialize a workspace through the operator CLI. It prompts for the password;
do not put passwords in command arguments or shell history.

```sh
docker compose run --rm -it migrate .venv/bin/python -m app.modules.identity.operator bootstrap --workspace example --name "Example workspace" --email admin@example.com --display-name "Workspace administrator"
```

Use your own email and workspace name. There is no default administrator or
public registration. Repeating bootstrap with the same account verifies its
password and does not reset it. Once an administrator exists, add staff through
Settings. Copy each setup link through a trusted channel; Atlas CX does not
send email. Links expire after 24 hours and can be consumed once. People with an
existing Atlas CX account must enter their current password.

Operator recovery, after verifying the person's identity outside Atlas CX:

```sh
docker compose run --rm -it migrate .venv/bin/python -m app.modules.identity.operator recover --email admin@example.com
```

Recovery prints a sensitive single-use link to the operator terminal. Do not
paste it into logs or issues. Workspace administrators cannot reset another
person's global password.

`docker compose down` retains local data. Adding `--volumes` erases it.
Role initialization runs only for a fresh volume; changing example values does
not rotate existing database passwords. Example credentials and signing keys are
public local-development values. Production configuration rejects those signing
keys and requires an HTTPS public origin. The local stack has no public TLS or
backup automation.

## Host development

Use Node 24.17.0, npm 11, Python 3.12.13, and uv 0.11.2. Exact dependencies are
locked in package-lock.json and backend/uv.lock.

```sh
npm ci
docker compose up -d --wait db
docker compose run --rm migrate
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Run `npm run dev` from another terminal at the repository root. For Vite
development, set `PUBLIC_ORIGIN=http://localhost:5173` in the host API environment
before starting it. Vite proxies `/api` to port 8000. The origin must match exactly
for browser mutations; there is no wildcard CORS. Cookies remain Secure,
HttpOnly, and SameSite=Lax, including on the local loopback development origin.

Host processes use the localhost database URLs in .env.example. Alembic and the
operator CLI require an explicit `MIGRATION_DATABASE_URL` environment variable;
they never fall back to the API credential. Never give that variable to the API.
Liveness works without PostgreSQL; readiness and authenticated work require it.

## Checks

```sh
npm run check
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Default pytest selects unit/HTTP tests. Integration tests require an expendable,
migrated PostgreSQL database: set `TEST_DATABASE_URL` to its `atlas_app` URL and
`MIGRATION_DATABASE_URL` to its `atlas_migrator` URL, then run
`uv run pytest -m integration`. Tests exercise the actual non-owner role,
forced RLS, authentication, CSRF, CRUD, constraints, setup links, and revocation.
SQLite cannot verify these controls. Fixture cleanup uses the migration role.

From the root:

```sh
npx playwright install chromium
npm run test:e2e
python scripts/verify_sources.py
```

Browser tests exercise customer interactions at 1440, 1024, 700, and 390 pixels,
plus the foundation's 320-pixel shell checks. Test-only API fixtures provide
deterministic UI states. The separate real-stack test skips unless
`E2E_BASE_URL` is set. CI runs it against Compose with randomly generated,
synthetic identities prepared by `backend/scripts/seed_m1_browser.py`. That
script writes a private, ignored temporary credentials file, never a default
account. Do not run it against a database containing real customer data.

Regenerate contracts after API schema changes:

```sh
cd backend
uv run python -m scripts.export_openapi
cd ..
npm run api:generate
```

CI checks quality, contracts, dependencies, source hashes, PostgreSQL isolation,
M0 data preservation during upgrade, rollback/repeat upgrades, container builds,
health smoke checks, and a real browser authentication/customer/portal flow.
It does not deploy. See [verification evidence](docs/VERIFICATION.md),
[changed files](docs/M1_FILE_MANIFEST.md), and
[identity/customer architecture](docs/architecture/0002-identity-customer-core.md).
The next milestone is **M2: the portal request → agent reply → resolution slice**.
